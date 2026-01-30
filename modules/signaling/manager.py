# modules/signaling/manager.py
import json
from modules.webrtc.gateway import WebRTCGateway
from typing import Optional
from modules.settings import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()


class SignalingManager:
    def __init__(self, ws):
        self.ws = ws
        self.gateway: Optional[WebRTCGateway] = None

    async def handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "watch":
            logger.info("WebRTC watch: %s", msg)
            camera_id = msg.get("camera_id", "cam1")

            # 依 camera_id 查詢攝影機設定
            camera = settings.get_camera_by_id(camera_id)
            if camera is None:
                await self.send({
                    "type": "error",
                    "message": f"未知的攝影機: {camera_id}"
                })
                return

            self.gateway = WebRTCGateway(
                url=camera.rtsp_url,
                camera_id=camera_id,
                signaling=self,
                settings=settings
            )
            await self.gateway.start()

        elif msg_type == "answer":
            if self.gateway:
                logger.info("WebRTC get answer: %s", msg)
                await self.gateway.receive_answer(msg)

        elif msg_type == "ice":
            if self.gateway and msg.get("candidate"):
                logger.info("WebRTC get ice: %s", msg["candidate"])
                await self.gateway.receive_ice(msg["candidate"])

    async def send(self, payload: dict):
        await self.ws.send_text(json.dumps(payload))

    async def close(self):
        if self.gateway:
            await self.gateway.close()
