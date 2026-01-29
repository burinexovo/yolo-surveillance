# modules/video/camera_recorder.py
"""
獨立攝影機錄影服務
- 與 YOLO 分離，可為任意攝影機錄影
- 每個攝影機一個實例
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from modules.settings import CameraConfig
from modules.video.rtsp_reader import RTSPReader, RTSPReaderConfig
from modules.video.video_recorder import VideoRecorder, RecorderConfig
from modules.video.recording_worker import RecordingWorker, RecordingConfig

logger = logging.getLogger(__name__)


@dataclass
class CameraRecorderConfig:
    """攝影機錄影設定"""
    camera: CameraConfig
    fps: int = 30
    segment_minutes: int = 3
    target_size: tuple[int, int] = (960, 540)
    output_dir: str = "recordings"


class CameraRecorder:
    """
    獨立攝影機錄影服務

    用法：
        config = CameraRecorderConfig(camera=cam_config)
        recorder = CameraRecorder(config)
        recorder.start()
        ...
        recorder.stop()
    """

    def __init__(self, cfg: CameraRecorderConfig):
        self.cfg = cfg
        self.camera = cfg.camera
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 元件（延遲初始化）
        self._reader: Optional[RTSPReader] = None
        self._recorder: Optional[VideoRecorder] = None
        self._worker: Optional[RecordingWorker] = None

    def start(self) -> None:
        """啟動錄影"""
        if self._running:
            logger.warning("CameraRecorder %s 已在運行", self.camera.camera_id)
            return

        self._running = True

        # 初始化 RTSP reader
        self._reader = RTSPReader(RTSPReaderConfig(
            url=self.camera.rtsp_url,
            drop_grab_n=1,
        ))
        self._reader.start()

        # 初始化錄影器（輸出到 recordings/{camera_id}/{date}/）
        self._recorder = VideoRecorder(RecorderConfig(
            output_dir=self.cfg.output_dir,
            camera_id=self.camera.camera_id,
            save_raw=True,
            save_annot=False,
            fps=self.cfg.fps,
            segment_minutes=self.cfg.segment_minutes,
            target_size=self.cfg.target_size,
        ))
        self._recorder.start()

        # 初始化錄影 worker
        self._worker = RecordingWorker(
            self._recorder,
            RecordingConfig(fps=self.cfg.fps, name=f"RecWorker-{self.camera.camera_id}")
        )
        self._worker.start()

        # 啟動主迴圈執行緒
        self._thread = threading.Thread(
            target=self._loop,
            name=f"CameraRecorder-{self.camera.camera_id}",
            daemon=True,
        )
        self._thread.start()

        logger.info("CameraRecorder 啟動: %s (%s)", self.camera.camera_id, self.camera.label)

    def stop(self) -> None:
        """停止錄影"""
        self._running = False

        if self._worker:
            self._worker.stop()
        if self._recorder:
            self._recorder.stop()
        if self._reader:
            self._reader.stop()

        if self._thread:
            self._thread.join(timeout=3.0)

        logger.info("CameraRecorder 停止: %s", self.camera.camera_id)

    def _loop(self) -> None:
        """主迴圈：持續從 reader 取得畫面並送到 worker"""
        last_ts = 0.0

        while self._running:
            if self._reader is None:
                time.sleep(0.1)
                continue

            frame, ts = self._reader.get_latest()

            if frame is not None and ts > last_ts:
                last_ts = ts
                if self._worker:
                    self._worker.update(raw_frame=frame)

            time.sleep(0.01)  # ~100 FPS 上限，避免 busy loop
