#!/usr/bin/env python3
"""
將現有 MP4 錄影檔轉換成 HLS 格式
用法: python scripts/convert_to_hls.py [--dry-run]
"""

import argparse
import subprocess
import sys
from pathlib import Path

RECORDINGS_DIR = Path(__file__).parent.parent / "recordings"


def convert_mp4_to_hls(mp4_path: Path, dry_run: bool = False) -> bool:
    """將單一 MP4 轉換成 HLS"""
    hls_dir = mp4_path.with_suffix("")
    playlist_path = hls_dir / "playlist.m3u8"

    # 已經轉換過就跳過
    if playlist_path.exists():
        return False

    if dry_run:
        print(f"[DRY-RUN] 會轉換: {mp4_path.name}")
        return True

    # 建立 HLS 目錄
    hls_dir.mkdir(exist_ok=True)

    try:
        # 重新編碼為 H.264（瀏覽器 HLS 相容）
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(mp4_path),
                "-c:v", "libx264",       # 轉換為 H.264
                "-preset", "fast",       # 編碼速度
                "-crf", "28",            # 品質（28 較小檔案）
                "-maxrate", "1M",        # 最大位元率 1Mbps
                "-bufsize", "2M",        # 緩衝區大小
                "-c:a", "aac",           # 音訊轉 AAC
                "-b:a", "64k",           # 音訊位元率
                "-hls_time", "2",
                "-hls_list_size", "0",
                "-hls_segment_filename", str(hls_dir / "seg_%03d.ts"),
                "-f", "hls",
                str(playlist_path)
            ],
            capture_output=True,
            timeout=300,  # 編碼需要更多時間
        )

        if result.returncode == 0:
            print(f"✓ 轉換完成: {mp4_path.name}")
            return True
        else:
            print(f"✗ 轉換失敗: {mp4_path.name}")
            print(f"  錯誤: {result.stderr.decode()[-200:]}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ 轉換逾時: {mp4_path.name}")
        return False
    except Exception as e:
        print(f"✗ 轉換錯誤: {mp4_path.name} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="將 MP4 錄影檔轉換成 HLS 格式")
    parser.add_argument("--dry-run", action="store_true", help="只顯示要轉換的檔案，不實際轉換")
    parser.add_argument("--date", type=str, help="只處理特定日期 (YYYYMMDD)")
    parser.add_argument("--camera", type=str, help="只處理特定攝影機 (cam1, cam2)")
    args = parser.parse_args()

    if not RECORDINGS_DIR.exists():
        print(f"錄影目錄不存在: {RECORDINGS_DIR}")
        sys.exit(1)

    # 尋找所有 MP4 檔案
    mp4_files = []

    for mp4 in RECORDINGS_DIR.rglob("*_raw.mp4"):
        # 過濾條件
        if args.date and args.date not in str(mp4):
            continue
        if args.camera and args.camera not in str(mp4):
            continue

        mp4_files.append(mp4)

    mp4_files.sort()

    if not mp4_files:
        print("沒有找到需要轉換的 MP4 檔案")
        sys.exit(0)

    print(f"找到 {len(mp4_files)} 個 MP4 檔案")
    print("-" * 50)

    converted = 0
    skipped = 0

    for mp4 in mp4_files:
        if convert_mp4_to_hls(mp4, dry_run=args.dry_run):
            converted += 1
        else:
            skipped += 1

    print("-" * 50)
    if args.dry_run:
        print(f"[DRY-RUN] 會轉換: {converted}, 已存在/跳過: {skipped}")
    else:
        print(f"轉換完成: {converted}, 跳過: {skipped}")


if __name__ == "__main__":
    main()
