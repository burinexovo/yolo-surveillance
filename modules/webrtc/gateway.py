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
from modules.video_source import get_reader

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

        # TURN（後端也建議要有，因為你 aiortc 在本地 NAT 後面）
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
        self.pc.addTrack(RTSPVideoTrack(get_reader()))

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

    async def close(self):
        await self.pc.close()

# from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
# from aiortc.rtcconfiguration import RTCIceServer, RTCConfiguration
# from aiortc.contrib.media import MediaPlayer
# from aiortc.sdp import candidate_from_sdp
# from modules.webrtc.rtsp_video_track import RTSPVideoTrack
# from modules.video_source import get_reader
# import asyncio
# import logging

# logger = logging.getLogger(__name__)


# class WebRTCGateway:
#     def __init__(self, url, camera_id: str, signaling, settings):
#         self.rtsp_url = url
#         self.camera_id = camera_id
#         self.signaling = signaling
#         self.pc = RTCPeerConnection(
#             RTCConfiguration(
#                 iceServers=[
#                     RTCIceServer(urls=settings.STUN_URL1),
#                     RTCIceServer(urls=settings.STUN_URL2),
#                     RTCIceServer(
#                         urls=settings.TURN_URL1,
#                         username=settings.TURN_USERNAME1,
#                         credential=settings.TURN_SECRET1,
#                     ),
#                 ]
#             )
#         )

#     async def start(self):
#         # # 本機攝像頭
#         # player = MediaPlayer(
#         #     "default:none",
#         #     format="avfoundation",
#         #     options={
#         #         "framerate": "30",
#         #         "video_size": "1280x720"
#         #     }
#         # )

#         # # Tapo C210 rtsp (另外一條連線)
#         # player = MediaPlayer(self.rtsp_url)
#         # logger.info("WebRTCGateway start:", player.audio, player.video)

#         # 設為 WebRTC Track（取得現有畫面）
#         self.pc.addTrack(RTSPVideoTrack(get_reader()))
#         # self.pc.addTrack(player.video)

#         # 先綁事件，再開始 offer / ICE
#         @self.pc.on("icegatheringstatechange")
#         async def on_ice_gather():
#             logger.info("WebRTC ice gathering: %s", self.pc.iceConnectionState)

#         @self.pc.on("iceconnectionstatechange")
#         async def on_ice_conn():
#             logger.info("WebRTC ice connection stae changeL %s",
#                         self.pc.iceConnectionState)

#         # 1. 產生 offer
#         offer = await self.pc.createOffer()

#         # 2. 設成 localDescription（這一步會啟動 ICE gathering）
#         await self.pc.setLocalDescription(offer)

#         # 3. 等到 ICE 全部收完
#         while self.pc.iceGatheringState != "complete":
#             await asyncio.sleep(0.1)

#         # 4. 用「最新的」 localDescription 送出去
#         local = self.pc.localDescription
#         await self.signaling.send(
#             {"type": "offer", "sdp": local.sdp, "type_sdp": local.type}
#         )

#     async def receive_answer(self, msg):
#         logger.info("WebRTC receive answer: %s", msg)
#         answer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
#         await self.pc.setRemoteDescription(answer)

#     async def receive_ice(self, candidate):
#         logger.info("WebRTC receive candidate: %s", candidate)
#         if candidate is None:
#             await self.pc.addIceCandidate(None)
#             return
#         ice = candidate_from_sdp(candidate["candidate"])
#         ice.sdpMid = candidate.get("sdpMid")
#         ice.sdpMLineIndex = candidate.get("sdpMLineIndex")
#         await self.pc.addIceCandidate(candidate=ice)

#     async def close(self):
#         await self.pc.close()
