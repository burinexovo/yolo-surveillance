# utils/logging.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(*, level: int = logging.INFO, log_file: str | None = None,):
    # 2025-01-22 14:03:21 | INFO    | modules.yolo_runtime | Person entered
    fmt = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | "
        "%(name)s | %(message)s"
    )

    handlers = [logging.StreamHandler()]

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3,
                encoding="utf-8",
            )
        )

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=handlers,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 🔕 關掉 Ultralytics YOLO 的雜訊
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
