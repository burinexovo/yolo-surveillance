from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


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
        print(f"⚠️ root not found: {cfg.root}")
        return 0

    cutoff = datetime.now() - timedelta(days=cfg.keep_days)
    deleted = 0

    for p in sorted(cfg.root.iterdir()):
        if not p.is_dir():
            continue

        d = parse_yyyymmdd(p.name)
        if d is None:
            # 非日期資料夾就跳過（避免誤刪）
            continue

        if d < cutoff:
            if cfg.dry_run:
                print(f"[DRY] would delete: {p}")
            else:
                print(f"🗑️ delete: {p}")
                shutil.rmtree(p, ignore_errors=False)
            deleted += 1

    print(f"Done. deleted_folders={deleted} (keep_days={cfg.keep_days})")
    return deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="recordings", help="recordings 根目錄")
    ap.add_argument("--keep-days", type=int, default=10, help="保留天數")
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
