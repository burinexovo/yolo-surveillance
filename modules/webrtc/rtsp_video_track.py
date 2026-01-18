from aiortc import VideoStreamTrack
from av import VideoFrame
from modules.rtsp_reader import RTSPReader
import asyncio


class RTSPVideoTrack(VideoStreamTrack):
    def __init__(self, reader: RTSPReader):
        super().__init__()
        self.reader = reader
        self._last_ts = 0.0

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

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base

        return video_frame