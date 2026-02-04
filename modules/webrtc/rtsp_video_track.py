from aiortc import VideoStreamTrack
from av import VideoFrame
from modules.video.rtsp_reader import RTSPReader
from utils import TARGET_WIDTH, TARGET_HEIGHT
import asyncio
import cv2


class RTSPVideoTrack(VideoStreamTrack):
    def __init__(self, reader: RTSPReader, target_size: tuple[int, int] | None = None):
        super().__init__()
        self.reader = reader
        self._last_ts = 0.0
        self._target_size = target_size or (TARGET_WIDTH, TARGET_HEIGHT)

    async def recv(self) -> VideoFrame:
        # 讓 aiortc 幫你決定 pts / time_base
        pts, time_base = await self.next_timestamp()

        # 等待新 frame
        while True:
            frame, ts = self.reader.get_latest()
            if frame is not None and ts > self._last_ts:
                self._last_ts = ts
                break
            await asyncio.sleep(0.001)

        # 縮放至目標解析度（維持比例）
        h, w = frame.shape[:2]
        target_w, target_h = self._target_size

        if w > target_w or h > target_h:
            scale = min(target_w / w, target_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        return video_frame
