# modules/signaling/router.py
from __future__ import annotations

import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from modules.signaling.manager import SignalingManager

# 引入 Token 快取與 lock（與 dashboard_routes 共用）
from routers.dashboard_routes import _pin_token_cache, _token_cache, _token_lock

router = APIRouter()


@router.websocket("/ws")
async def signaling_ws(ws: WebSocket):
    # 在 accept() 前驗證 token
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    # 驗證 token（PIN 或 Workers token）- 執行緒安全
    now = time.time()
    with _token_lock:
        valid = (
            (token in _pin_token_cache and _pin_token_cache[token] > now) or
            (token in _token_cache and _token_cache[token] > now)
        )
    if not valid:
        await ws.close(code=4003, reason="Invalid token")
        return

    await ws.accept()
    mgr = SignalingManager(ws)

    try:
        while True:
            msg = await ws.receive_json()
            await mgr.handle_message(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await mgr.close()
