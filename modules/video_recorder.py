# modules/video_recorder.py
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2


@dataclass(frozen=True)
class RecorderConfig:
    output_dir: Union[str, Path] = "recordings"
    save_raw: bool = False
    save_annot: bool = False
    fps: int = 30
    fourcc: str = "mp4v"
    segment_minutes: int = 1
    target_size: Optional[Tuple[int, int]] = (960, 540)  # (width, height)


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

    # ---- internal helpers ----
    def _make_today_dir(self) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        day_dir = self.output_dir / today
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _release_writers(self) -> None:
        if self.raw_writer is not None:
            self.raw_writer.release()
            self.raw_writer = None
        if self.annot_writer is not None:
            self.annot_writer.release()
            self.annot_writer = None

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
            self.raw_writer = cv2.VideoWriter(
                str(raw_path), fourcc, self.cfg.fps, (frame_w, frame_h)
            )

        if self.cfg.save_annot:
            annot_path = day_dir / f"{timestamp}_annot.mp4"
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

    def stop(self) -> None:
        self.recording = False
        self._release_writers()

    # optional: with 語法
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False