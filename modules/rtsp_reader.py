# modules/rtsp_reader.py
from __future__ import annotations
import cv2
import time
import threading
from dataclasses import dataclass
from typing import Optional, Tuple, Union
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RTSPReaderConfig:
    url: str
    backend: int = cv2.CAP_FFMPEG
    buffer_size: int = 1
    reconnect_sec: float = 2.0
    drop_grab_n: int = 2  # 0~5 自己調：越大越低延遲，但FPS越低


class RTSPReader:
    def __init__(self, cfg: RTSPReaderConfig):
        self.cfg = cfg
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name="RTSPReader", daemon=True)

        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._ts: float = 0.0
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        self._t.start()

    def stop(self) -> None:
        self._stop.set()
        self._t.join(timeout=2.0)
        self._release()

    def get_latest(self) -> Tuple[Optional[np.ndarray], float]:
        # 回傳 copy，避免外面畫框/resize 影響內部最新frame
        with self._lock:
            if self._frame is None:
                return None, 0.0
            return self._frame.copy(), self._ts

    def _open(self) -> bool:
        self._release()
        logger.debug("Url: %s", self.cfg.url)

        if self.cfg.url == "DEVICE_CAMERA0":
            cap = cv2.VideoCapture(0)
        else:
            cap = cv2.VideoCapture(self.cfg.url, self.cfg.backend)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, self.cfg.buffer_size)

        if not cap.isOpened():
            cap.release()
            return False
        self._cap = cap
        return True

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._cap is None and not self._open():
                time.sleep(self.cfg.reconnect_sec)
                continue

            assert self._cap is not None

            # 丟舊幀（可選）
            for _ in range(max(0, self.cfg.drop_grab_n)):
                self._cap.grab()

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._release()
                time.sleep(self.cfg.reconnect_sec)
                continue

            now = time.time()
            with self._lock:
                self._frame = frame
                self._ts = now
