# modules/webrtc/gatway.py
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import time

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.rtcconfiguration import RTCIceServer, RTCConfiguration
from aiortc.sdp import candidate_from_sdp

from modules.webrtc.rtsp_video_track import RTSPVideoTrack
from modules.video.video_source import get_reader

logger = logging.getLogger(__name__)


def make_turn_rest_credential(*, static_secret: str, label: str, ttl_sec: int) -> tuple[str, str, int]:
    """
    coturn time-limited credential (REST API style)
    username: "<exp>:<label>"  (exp = unix seconds)
    credential: base64(hmac-sha1(static_secret, username))
    """
    now = int(time.time())
    exp = now + int(ttl_sec)

    username = f"{exp}:{label}"
    digest = hmac.new(
        static_secret.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    credential = base64.b64encode(digest).decode("utf-8")
    return username, credential, exp


class WebRTCGateway:
    def __init__(self, url, camera_id: str, signaling, settings):
        self.rtsp_url = url
        self.camera_id = camera_id
        self.signaling = signaling

        ice_servers: list[RTCIceServer] = []

        # STUN（可留）
        if getattr(settings, "STUN_URL1", None):
            ice_servers.append(RTCIceServer(urls=settings.STUN_URL1))
        if getattr(settings, "STUN_URL2", None):
            ice_servers.append(RTCIceServer(urls=settings.STUN_URL2))

        # TURN
        turn_url = getattr(settings, "TURN_URL1", None)
        # ← 新增：跟 coturn static-auth-secret 一樣
        turn_secret = getattr(settings, "TURN_STATIC_AUTH_SECRET", None)
        if turn_url and turn_secret:
            # 後端 TTL 可以長一點，減少連線中/重連剛好過期
            ttl_sec = int(getattr(settings, "TURN_TTL_SEC_SERVER", 3600))  # 預設 1 小時
            label = f"server:{camera_id}"

            username, credential, exp = make_turn_rest_credential(
                static_secret=turn_secret,
                label=label,
                ttl_sec=ttl_sec,
            )
            logger.info("TURN(server) credential exp=%s label=%s", exp, label)

            ice_servers.append(
                RTCIceServer(
                    urls=[
                        f'{turn_url}?transport=udp',
                        f'{turn_url}?transport=tcp'
                    ],
                    username=username,
                    credential=credential,
                )
            )
        else:
            logger.warning(
                "TURN not configured for server side (TURN_URL1 or TURN_STATIC_AUTH_SECRET missing)")

        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))

    async def start(self):
        # 設為 WebRTC Track（取得現有畫面）
        reader = get_reader(self.camera_id)
        if reader is None:
            await self.signaling.send({
                "type": "error",
                "message": f"攝影機 {self.camera_id} 無法使用"
            })
            return

        video_track = RTSPVideoTrack(reader)
        sender = self.pc.addTrack(video_track)

        # 設定 H264 為優先編碼（較佳壓縮率與品質）
        self._set_h264_preferred(sender)

        @self.pc.on("icegatheringstatechange")
        async def on_ice_gather():
            logger.info("WebRTC ice gathering state: %s", self.pc.iceGatheringState)

        @self.pc.on("iceconnectionstatechange")
        async def on_ice_conn():
            logger.info("WebRTC ice connection state: %s", self.pc.iceConnectionState)

        # 1) 產生 offer
        offer = await self.pc.createOffer()

        # 2) 設 localDescription（啟動 ICE gathering）
        await self.pc.setLocalDescription(offer)

        # 3) 等 ICE 收完（也可以改成 trickle ICE，不用等 complete）
        while self.pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)

        # 4) 送出最新 localDescription
        local = self.pc.localDescription
        await self.signaling.send(
            {"type": local.type, "sdp": local.sdp}   # ← 修正：不要用 type_sdp
        )

    async def receive_answer(self, msg):
        logger.info("WebRTC receive answer: %s", msg.get("type"))
        answer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
        await self.pc.setRemoteDescription(answer)

    async def receive_ice(self, candidate):
        logger.info("WebRTC receive candidate")
        if candidate is None:
            await self.pc.addIceCandidate(None)
            return

        ice = candidate_from_sdp(candidate["candidate"])
        ice.sdpMid = candidate.get("sdpMid")
        ice.sdpMLineIndex = candidate.get("sdpMLineIndex")
        await self.pc.addIceCandidate(candidate=ice)

    def _set_h264_preferred(self, sender):
        """設定 H264 為優先編碼"""
        try:
            for t in self.pc.getTransceivers():
                if t.sender == sender:
                    caps = t.sender.getCapabilities("video")
                    if caps:
                        codecs = caps.codecs
                        h264 = [c for c in codecs if "h264" in c.mimeType.lower()]
                        others = [c for c in codecs if "h264" not in c.mimeType.lower()]
                        if h264:
                            t.setCodecPreferences(h264 + others)
                            logger.info("H264 codec preference set")
                    break
        except Exception as e:
            logger.warning("Failed to set H264 preference: %s", e)

    async def close(self):
        await self.pc.close()
