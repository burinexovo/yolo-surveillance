# routers/recording_routes.py
"""錄影回放相關 API 路由"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from modules.storage.visitor_db import visitor_db
from routers.dashboard_routes import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["recordings"])

# === 常數 ===
RECORDINGS_DIR = Path(__file__).parent.parent / "recordings"
DATE_PATTERN = re.compile(r"^\d{8}$")  # YYYYMMDD
FILENAME_PATTERN = re.compile(r"^\d{8}_\d{6}_raw\.mp4$")  # YYYYMMDD_HHMMSS_raw.mp4
HLS_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}_raw$")  # YYYYMMDD_HHMMSS_raw (HLS 目錄)
TS_FILE_PATTERN = re.compile(r"^seg_\d{3}\.ts$")  # seg_000.ts
CAMERA_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,20}$")  # 安全的 camera_id
DEFAULT_CAMERA_ID = "cam1"


# === Response Models ===

class RecordingItem(BaseModel):
    filename: str
    start_time: str  # ISO format
    duration_seconds: int
    size_bytes: int
    hls_available: bool = False  # HLS 版本是否可用


class RecordingsResponse(BaseModel):
    date: str
    recordings: List[RecordingItem]
    total_count: int
    total_size_mb: float


class EventItem(BaseModel):
    id: int
    entry_time: str  # ISO format


class EventsResponse(BaseModel):
    date: str
    events: List[EventItem]


# === 輔助函式 ===

def parse_filename_to_datetime(filename: str) -> Optional[datetime]:
    """從檔名解析開始時間，例如 20260128_143012_raw.mp4 → datetime"""
    match = re.match(r"^(\d{8})_(\d{6})_raw\.mp4$", filename)
    if not match:
        return None
    date_str, time_str = match.groups()
    try:
        return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def validate_date_param(date_str: str) -> str:
    """驗證日期參數格式，回傳 YYYYMMDD 格式"""
    # 支援 YYYY-MM-DD 或 YYYYMMDD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str.replace("-", "")
    if DATE_PATTERN.match(date_str):
        return date_str
    raise HTTPException(status_code=400, detail="Invalid date format")


def validate_filename(filename: str) -> None:
    """驗證檔名格式，防止路徑遍歷"""
    if not FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename format")


def validate_camera_id(camera_id: str) -> str:
    """驗證 camera_id 格式"""
    if not CAMERA_ID_PATTERN.match(camera_id):
        raise HTTPException(status_code=400, detail="Invalid camera_id format")
    return camera_id


def get_recording_dir(camera_id: str, date_str: str) -> Path:
    """取得指定攝影機和日期的錄影目錄，含路徑遍歷防護"""
    # 新結構: recordings/{camera_id}/{date_str}
    # 向後相容: 如果新結構不存在，檢查舊結構 recordings/{date_str}
    new_dir = RECORDINGS_DIR / camera_id / date_str
    old_dir = RECORDINGS_DIR / date_str

    # 優先使用新結構
    if new_dir.exists():
        date_dir = new_dir
    elif old_dir.exists() and camera_id == DEFAULT_CAMERA_ID:
        # 向後相容：舊錄影只對應預設攝影機
        date_dir = old_dir
    else:
        date_dir = new_dir  # 返回新結構路徑（可能不存在）

    # 二次確認路徑安全
    try:
        resolved = date_dir.resolve()
        resolved.relative_to(RECORDINGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    return date_dir


# === API Endpoints ===

@router.get("/recordings", response_model=RecordingsResponse)
async def list_recordings(
    request: Request,
    token: str = Depends(verify_token),
    date: str = Query(..., alias="date", description="日期 (YYYY-MM-DD 或 YYYYMMDD)"),
    camera_id: str = Query(DEFAULT_CAMERA_ID, description="攝影機 ID"),
):
    """列出指定日期和攝影機的所有錄影檔案"""
    date_str = validate_date_param(date)
    camera_id = validate_camera_id(camera_id)
    date_dir = get_recording_dir(camera_id, date_str)

    if not date_dir.exists():
        return RecordingsResponse(
            date=date_str,
            recordings=[],
            total_count=0,
            total_size_mb=0.0,
        )

    recordings = []
    total_size = 0

    for f in sorted(date_dir.glob("*_raw.mp4")):
        if not FILENAME_PATTERN.match(f.name):
            continue

        start_time = parse_filename_to_datetime(f.name)
        if not start_time:
            continue

        # 檢查 HLS 版本是否存在（轉檔完成）
        hls_dir = f.with_suffix("")  # 去掉 .mp4 變成目錄名
        hls_available = (hls_dir / "playlist.m3u8").exists()

        # 只返回 HLS 轉檔完成的錄影，避免播放正在處理中的檔案
        if not hls_available:
            continue

        stat = f.stat()
        size = stat.st_size
        total_size += size

        # 預設每段 60 秒（實際可從影片 metadata 取得，但這裡簡化處理）
        duration = 60

        recordings.append(RecordingItem(
            filename=f.name,
            start_time=start_time.isoformat(),
            duration_seconds=duration,
            size_bytes=size,
            hls_available=True,
        ))

    return RecordingsResponse(
        date=date_str,
        recordings=recordings,
        total_count=len(recordings),
        total_size_mb=round(total_size / (1024 * 1024), 2),
    )


@router.get("/events", response_model=EventsResponse)
async def list_events(
    request: Request,
    token: str = Depends(verify_token),
    date: str = Query(..., alias="date", description="日期 (YYYY-MM-DD 或 YYYYMMDD)"),
):
    """列出指定日期的所有訪客入店事件"""
    date_str = validate_date_param(date)

    # 將 YYYYMMDD 轉換為 date 物件
    try:
        target_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    entries = visitor_db.get_entries_by_date(target_date)

    return EventsResponse(
        date=date_str,
        events=[
            EventItem(id=e.id, entry_time=e.entry_time.isoformat())
            for e in entries
        ],
    )


@router.get("/recordings/{camera_id}/{date_str}/{filename}")
async def stream_recording(
    request: Request,
    camera_id: str,
    date_str: str,
    filename: str,
    token: str = Depends(verify_token),
):
    """串流播放錄影檔案，支援 HTTP Range Requests"""
    # 驗證參數
    camera_id = validate_camera_id(camera_id)
    date_str = validate_date_param(date_str)
    validate_filename(filename)

    # 建構檔案路徑
    date_dir = get_recording_dir(camera_id, date_str)
    file_path = date_dir / filename

    # 二次確認路徑安全
    try:
        resolved = file_path.resolve()
        resolved.relative_to(RECORDINGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    # 使用 FileResponse 自動處理 Range Requests
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename,
    )


# === HLS 串流端點 ===

@router.get("/recordings/{camera_id}/{date_str}/{segment_name}/playlist.m3u8")
async def get_hls_playlist(
    request: Request,
    camera_id: str,
    date_str: str,
    segment_name: str,
    token: str = Depends(verify_token),
):
    """取得 HLS 播放清單"""
    camera_id = validate_camera_id(camera_id)
    date_str = validate_date_param(date_str)

    # 驗證 segment_name 格式
    if not HLS_DIR_PATTERN.match(segment_name):
        raise HTTPException(status_code=400, detail="Invalid segment name")

    # 建構路徑
    date_dir = get_recording_dir(camera_id, date_str)
    hls_dir = date_dir / segment_name
    playlist_path = hls_dir / "playlist.m3u8"

    # 安全檢查
    try:
        resolved = playlist_path.resolve()
        resolved.relative_to(RECORDINGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="HLS playlist not found")

    return FileResponse(
        path=playlist_path,
        media_type="application/vnd.apple.mpegurl",
        filename="playlist.m3u8",
    )


@router.get("/recordings/{camera_id}/{date_str}/{segment_name}/{ts_file}")
async def get_hls_segment(
    request: Request,
    camera_id: str,
    date_str: str,
    segment_name: str,
    ts_file: str,
    token: str = Depends(verify_token),
):
    """取得 HLS 影片片段 (.ts)"""
    camera_id = validate_camera_id(camera_id)
    date_str = validate_date_param(date_str)

    # 驗證格式
    if not HLS_DIR_PATTERN.match(segment_name):
        raise HTTPException(status_code=400, detail="Invalid segment name")
    if not TS_FILE_PATTERN.match(ts_file):
        raise HTTPException(status_code=400, detail="Invalid ts file name")

    # 建構路徑
    date_dir = get_recording_dir(camera_id, date_str)
    ts_path = date_dir / segment_name / ts_file

    # 安全檢查
    try:
        resolved = ts_path.resolve()
        resolved.relative_to(RECORDINGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not ts_path.exists():
        raise HTTPException(status_code=404, detail="HLS segment not found")

    return FileResponse(
        path=ts_path,
        media_type="video/mp2t",
        filename=ts_file,
    )
