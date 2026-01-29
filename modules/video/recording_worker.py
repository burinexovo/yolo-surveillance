# modules/recording_worker.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from modules.video.video_recorder import VideoRecorder
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordingConfig:
    fps: int = 30
    name: str = "RecordingWorker"
    copy_frame: bool = True


class RecordingWorker:
    """
    用法：
        rec = VideoRecorder(RecorderConfig(save_raw=True, fps=30))
        rec.start()

        worker = RecordingWorker(rec, RecordingConfig(fps=30))
        worker.start()

        while True:
            ... 
            YOLO
            worker.update(raw_frame=frame, annotated_frame=annotated_frame)
            ...

        worker.stop()
        rec.stop()
    """

    def __init__(self, recoder: VideoRecorder, cfg: RecordingConfig):
        if cfg.fps <= 0:
            raise ValueError("fps must be > 0")

        self.recorder = recoder
        self.cfg = cfg

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None

        self._latest_raw: Optional[np.ndarray] = None
        self._latest_annot: Optional[np.ndarray] = None

    def start(self) -> None:
        # 如果 tread 存在而且在跑就代表已經在錄影了
        if self._t and self._t.is_alive():
            return

        # 沒有錄影就開始錄影
        self._stop.clear()  # 切換成綠燈
        self._t = threading.Thread(target=self._loop, name=self.cfg.name, daemon=True)
        self._t.start()

    def stop(self, join: bool = True) -> None:
        self._stop.set()  # 切換成紅燈

        # 結束，與主線程合併
        if join and self._t:
            self._t.join(timeout=2.0)

    def update(self, raw_frame: Optional[np.ndarray] = None, annotated_frame: Optional[np.ndarray] = None) -> None:
        """
        主執行緒每幀呼叫一次
        - 只保留最新的一幀
        """

        # 都沒有要錄的畫面就不用更新
        if raw_frame is None and annotated_frame is None:
            return

        # 主執行緒沒有要求需要額外 copy 的話就copy(如果主執行緒沒做，在這邊就要 copy)
        if self.cfg.copy_frame:
            raw_frame = raw_frame.copy() if raw_frame is not None else None
            annotated_frame = annotated_frame.copy() if annotated_frame is not None else None

        # 鎖著的就更新幀
        with self._lock:
            if raw_frame is not None:
                self._latest_raw = raw_frame
            if annotated_frame is not None:
                self._latest_annot = annotated_frame

    def _loop(self) -> None:
        interval = 1.0 / self.cfg.fps
        next_ts = time.monotonic()

        while not self._stop.is_set():
            now = time.monotonic()
            if now < next_ts:
                time.sleep(min(0.002, next_ts - now))
                continue

            with self._lock:
                raw = self._latest_raw
                annot = self._latest_annot

            # 寫檔
            try:
                self.recorder.write(raw_frame=raw, annotated_frame=annot)
            except Exception as e:
                logger.exception("%s recoder.write failed", self.cfg.name)

            next_ts += interval
            if next_ts < time.monotonic() - 0.5:
                next_ts = time.monotonic()
