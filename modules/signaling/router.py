# modules/signaling/router.py
from __future__ import annotations

import time
import logging
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from modules.signaling.manager import SignalingManager
from modules.settings import get_settings

# 引入 Token 快取與 lock（與 dashboard_routes 共用）
from routers.dashboard_routes import (
    _pin_token_cache, _token_cache, _token_lock, CACHE_TTL
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _verify_ws_token(token: str) -> bool:
    """
    驗證 WebSocket token。
    1. 先檢查本地快取（PIN token 或已驗證的 Workers token）
    2. 快取未命中時，調用 Workers API 驗證
    """
    now = time.time()

    # 先檢查本地快取
    with _token_lock:
        if token in _pin_token_cache and _pin_token_cache[token] > now:
            return True
        if token in _token_cache and _token_cache[token] > now:
            return True

    # 快取未命中，調用 Workers 驗證
    settings = get_settings()
    if not settings.workers_base_url:
        return False

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{settings.workers_base_url}/internal/rtc-config",
                headers={"x-internal-token": settings.internal_token},
                json={"token": token, "scope": "watch"},
            )
        if r.status_code == 200:
            # 驗證成功，加入快取
            with _token_lock:
                _token_cache[token] = now + CACHE_TTL
            return True
    except httpx.RequestError as e:
        logger.warning("WebSocket token verification failed: %s", e)

    return False


@router.websocket("/ws")
async def signaling_ws(ws: WebSocket):
    # 在 accept() 前驗證 token
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    # 驗證 token（支援 PIN token 和 Workers token）
    valid = await _verify_ws_token(token)
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
