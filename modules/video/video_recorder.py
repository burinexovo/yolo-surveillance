# modules/video_recorder.py
from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Optional, Tuple, Union

import cv2

logger = logging.getLogger(__name__)


def _faststart_worker(queue: Queue, enable_hls: bool = True):
    """
    背景執行緒：處理 ffmpeg 佇列
    1. 將 moov atom 移到檔案開頭（faststart）
    2. 轉換成 HLS 格式（可選）
    """
    while True:
        file_path = queue.get()
        if file_path is None:  # 結束信號
            break

        try:
            path = Path(file_path)
            if not path.exists():
                continue

            # === Step 1: Faststart ===
            temp_path = path.with_suffix(".tmp.mp4")
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(path),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(temp_path)
                ],
                capture_output=True,
                timeout=60,
            )

            if result.returncode == 0 and temp_path.exists():
                temp_path.replace(path)
                logger.debug("faststart 處理完成: %s", path.name)
            else:
                temp_path.unlink(missing_ok=True)
                logger.warning("faststart 處理失敗: %s", path.name)
                continue  # 跳過 HLS 轉換

            # === Step 2: HLS 轉換 ===
            if enable_hls:
                _convert_to_hls(path)

        except subprocess.TimeoutExpired:
            logger.warning("處理逾時: %s", file_path)
        except Exception as e:
            logger.exception("處理錯誤: %s", e)
        finally:
            queue.task_done()


def _convert_to_hls(mp4_path: Path):
    """
    將 MP4 轉換成 HLS 格式

    輸出結構：
    20260129_143000_raw.mp4
    20260129_143000_raw/
    ├── playlist.m3u8
    ├── seg_000.ts
    ├── seg_001.ts
    └── ...
    """
    # HLS 目錄：與 MP4 同名（去掉 .mp4）
    hls_dir = mp4_path.with_suffix("")
    hls_dir.mkdir(exist_ok=True)

    playlist_path = hls_dir / "playlist.m3u8"

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(mp4_path),
                "-c:v", "copy",          # 複製視訊 codec（不重新編碼）
                "-c:a", "copy",          # 複製音訊 codec
                "-hls_time", "2",        # 每段 2 秒
                "-hls_list_size", "0",   # 保留所有段落
                "-hls_segment_filename", str(hls_dir / "seg_%03d.ts"),
                "-f", "hls",
                str(playlist_path)
            ],
            capture_output=True,
            timeout=120,
        )

        if result.returncode == 0:
            logger.debug("HLS 轉換完成: %s", hls_dir.name)
        else:
            logger.warning("HLS 轉換失敗: %s - %s", mp4_path.name, result.stderr.decode()[-200:])

    except subprocess.TimeoutExpired:
        logger.warning("HLS 轉換逾時: %s", mp4_path.name)
    except Exception as e:
        logger.exception("HLS 轉換錯誤: %s", e)


@dataclass(frozen=True)
class RecorderConfig:
    output_dir: Union[str, Path] = "recordings"
    camera_id: Optional[str] = None  # 若有值，輸出到 {output_dir}/{camera_id}/{date}/
    save_raw: bool = False
    save_annot: bool = False
    fps: int = 30
    fourcc: str = "mp4v"
    segment_minutes: int = 3
    target_size: Optional[Tuple[int, int]] = (960, 540)  # (width, height)
    enable_faststart: bool = True  # 啟用 ffmpeg faststart 後處理


class VideoRecorder:
    """
    用法（在 main.py）：
        rec = VideoRecorder(RecorderConfig(save_raw=True, save_annot=True))
        rec.start()
        rec.write(raw_frame, annot_frame)
        rec.stop()
    """

    def __init__(self, cfg: RecorderConfig):
        if not cfg.save_raw and not cfg.save_annot:
            raise ValueError(
                "At least one of save_raw/save_annot must be True")

        self.cfg = cfg
        self.output_dir = Path(cfg.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.recording = False
        self.raw_writer: Optional[cv2.VideoWriter] = None
        self.annot_writer: Optional[cv2.VideoWriter] = None
        self.segment_start_time: Optional[float] = None
        self.segment_seconds = cfg.segment_minutes * 60

        # 追蹤當前錄製的檔案路徑（用於 faststart 後處理）
        self._current_raw_path: Optional[Path] = None
        self._current_annot_path: Optional[Path] = None

        # faststart 後處理佇列
        self._faststart_queue: Optional[Queue] = None
        self._faststart_thread: Optional[threading.Thread] = None
        if cfg.enable_faststart:
            self._faststart_queue = Queue()
            self._faststart_thread = threading.Thread(
                target=_faststart_worker,
                args=(self._faststart_queue,),
                daemon=True,
                name="FaststartWorker"
            )
            self._faststart_thread.start()

    # ---- internal helpers ----
    def _make_today_dir(self) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        # 若有 camera_id，使用 {output_dir}/{camera_id}/{date}/ 結構
        if self.cfg.camera_id:
            day_dir = self.output_dir / self.cfg.camera_id / today
        else:
            day_dir = self.output_dir / today
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _release_writers(self) -> None:
        # 記錄要處理的檔案路徑
        raw_path = self._current_raw_path
        annot_path = self._current_annot_path

        if self.raw_writer is not None:
            self.raw_writer.release()
            self.raw_writer = None
        if self.annot_writer is not None:
            self.annot_writer.release()
            self.annot_writer = None

        # 清除當前路徑
        self._current_raw_path = None
        self._current_annot_path = None

        # 佇列 faststart 後處理
        if self._faststart_queue is not None:
            if raw_path and raw_path.exists():
                self._faststart_queue.put(str(raw_path))
            if annot_path and annot_path.exists():
                self._faststart_queue.put(str(annot_path))

    def _init_writers(self, frame_for_size) -> None:
        self._release_writers()

        fourcc = cv2.VideoWriter_fourcc(*self.cfg.fourcc)
        self.segment_start_time = time.time()

        day_dir = self._make_today_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 決定輸出尺寸
        if self.cfg.target_size is not None:
            frame_w, frame_h = self.cfg.target_size
        else:
            frame_h, frame_w = frame_for_size.shape[:2]

        if self.cfg.save_raw:
            raw_path = day_dir / f"{timestamp}_raw.mp4"
            self._current_raw_path = raw_path
            self.raw_writer = cv2.VideoWriter(
                str(raw_path), fourcc, self.cfg.fps, (frame_w, frame_h)
            )

        if self.cfg.save_annot:
            annot_path = day_dir / f"{timestamp}_annot.mp4"
            self._current_annot_path = annot_path
            self.annot_writer = cv2.VideoWriter(
                str(annot_path), fourcc, self.cfg.fps, (frame_w, frame_h)
            )

    # ---- public API ----
    def start(self) -> None:
        self.recording = True
        self.segment_start_time = None  # 讓下一幀觸發 init

    def write(self, raw_frame=None, annotated_frame=None) -> None:
        if not self.recording:
            return
        if raw_frame is None and annotated_frame is None:
            return

        now = time.time()

        frame_for_size = raw_frame if raw_frame is not None else annotated_frame

        need_new_segment = (
            self.segment_start_time is None
            or (now - self.segment_start_time) >= self.segment_seconds
            or (self.raw_writer is None and self.annot_writer is None)
        )
        if need_new_segment:
            self._init_writers(frame_for_size)

        # resize（只對有要寫的 frame 做）
        if self.cfg.target_size is not None:
            if raw_frame is not None:
                raw_frame = cv2.resize(raw_frame, self.cfg.target_size)
            if annotated_frame is not None:
                annotated_frame = cv2.resize(
                    annotated_frame, self.cfg.target_size)

        if self.cfg.save_raw and self.raw_writer is not None and raw_frame is not None:
            self.raw_writer.write(raw_frame)

        if self.cfg.save_annot and self.annot_writer is not None and annotated_frame is not None:
            self.annot_writer.write(annotated_frame)

    def stop(self, wait_faststart: bool = False) -> None:
        self.recording = False
        self._release_writers()

        # 關閉 faststart 執行緒
        if self._faststart_queue is not None:
            if wait_faststart:
                # 等待佇列處理完成
                self._faststart_queue.join()
            # 發送結束信號
            self._faststart_queue.put(None)

        if self._faststart_thread is not None and wait_faststart:
            self._faststart_thread.join(timeout=5.0)

    # optional: with 語法
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False