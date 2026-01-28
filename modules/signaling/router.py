# modules/signaling/router.py
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from modules.signaling.manager import SignalingManager

router = APIRouter()


@router.websocket("/ws")
async def signaling_ws(ws: WebSocket):
    await ws.accept()
    mgr = SignalingManager(ws)

    try:
        while True:
            msg = await ws.receive_json()
            await mgr.handle_message(msg)
    except WebSocketDisconnect:
        pass
    finally:
        mgr.close()
