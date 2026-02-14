from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# 讓 scripts/ 能 import 專案根目錄的模組
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.constants import RECORDING_RETENTION_DAYS


@dataclass(frozen=True)
class CleanupConfig:
    root: Path
    keep_days: int
    dry_run: bool


def parse_yyyymmdd(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return None


def cleanup(cfg: CleanupConfig) -> int:
    if not cfg.root.exists():
        print(f"root not found: {cfg.root}")
        return 0

    cutoff = datetime.now() - timedelta(days=cfg.keep_days)
    deleted = 0

    # 支援兩種結構：
    # 舊結構: recordings/YYYYMMDD/
    # 新結構: recordings/{camera_id}/YYYYMMDD/

    for p in sorted(cfg.root.iterdir()):
        if not p.is_dir():
            continue

        # 檢查是否為日期資料夾（舊結構）
        d = parse_yyyymmdd(p.name)
        if d is not None:
            if d < cutoff:
                deleted += _delete_folder(p, cfg.dry_run)
            continue

        # 否則視為 camera_id 資料夾（新結構），遍歷其子目錄
        for date_dir in sorted(p.iterdir()):
            if not date_dir.is_dir():
                continue

            d = parse_yyyymmdd(date_dir.name)
            if d is None:
                continue

            if d < cutoff:
                deleted += _delete_folder(date_dir, cfg.dry_run)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
          f"Done. deleted_folders={deleted} (keep_days={cfg.keep_days})")
    return deleted


def _delete_folder(path: Path, dry_run: bool) -> int:
    """刪除資料夾，返回 1 表示成功"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if dry_run:
        print(f"[{timestamp}] [DRY] would delete: {path}")
    else:
        print(f"[{timestamp}] delete: {path}")
        shutil.rmtree(path, ignore_errors=False)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="recordings", help="recordings 根目錄")
    ap.add_argument("--keep-days", type=int, default=RECORDING_RETENTION_DAYS, help="保留天數")
    ap.add_argument("--dry-run", action="store_true", help="只列出不刪除")
    args = ap.parse_args()

    cfg = CleanupConfig(
        root=Path(args.root).expanduser().resolve(),
        keep_days=args.keep_days,
        dry_run=args.dry_run,
    )
    cleanup(cfg)


if __name__ == "__main__":
    main()
