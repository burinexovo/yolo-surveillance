# modules/signaling/manager.py
import json
from modules.webrtc.gateway import WebRTCGateway
from typing import Optional
from modules.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
if settings.rtsp_url_stream1 is None:
    raise RuntimeError("RTSP_URL_STREAM 未設定")


class SignalingManager:
    def __init__(self, ws):
        self.ws = ws
        self.gateway: Optional[WebRTCGateway] = None

    async def handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "watch":
            logger.info("WebRTC watch: %s", msg)
            camera_id = msg["camera_id"]
            self.gateway = WebRTCGateway(
                # url=settings.rtsp_url_stream1,
                url=settings.rtsp_url_stream2,
                # url=settings.device_camera0,
                camera_id=camera_id,
                signaling=self,
                settings=settings
            )
            await self.gateway.start()

        elif msg_type == "answer":
            logger.info("WebRTC get answer: %s", msg)
            await self.gateway.receive_answer(msg)

        elif msg_type == "ice":
            logger.info("WebRTC get ice: %s", msg["candidate"])
            await self.gateway.receive_ice(msg["candidate"])

    async def send(self, payload: dict):
        await self.ws.send_text(json.dumps(payload))

    def close(self):
        if self.gateway:
            self.gateway.close()
