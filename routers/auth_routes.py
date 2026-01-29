# routers/auth_routes.py
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Any

import httpx

# 引入 PIN Token 快取（與 dashboard_routes 共用）
from routers.dashboard_routes import _pin_token_cache

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_settings(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")
    return settings

# def _expired_html(msg: str) -> str:
#     return f"""<!doctype html>
#             <html lang="zh-Hant">
#             <head>
#             <meta charset="utf-8" />
#             <meta name="viewport" content="width=device-width,initial-scale=1" />
#             <title>連結已失效</title>
#             </head>
#             <body style="font-family:-apple-system,system-ui;padding:24px;">
#             <h2>觀看連結已失效或過期</h2>
#             <p>{msg}</p>
#             <p>請關閉此頁，回到 LINE 再點一次「即時畫面」。</p>
#             <script>alert({msg!r});</script>
#             </body>
#             </html>"""


class RtcConfigResponse(BaseModel):
    iceServers: list[Any]


def _build_ice_servers_from_settings(settings) -> list:
    """從 settings 組裝 ICE servers 列表"""
    import re
    import hashlib
    import base64
    import hmac as hmac_module

    ice_servers = []

    # STUN servers
    if settings.STUN_URL1:
        ice_servers.append({"urls": settings.STUN_URL1})
    if settings.STUN_URL2:
        ice_servers.append({"urls": settings.STUN_URL2})

    # TURN server（如果有設定）
    if settings.TURN_URL1 and settings.TURN_STATIC_AUTH_SECRET:
        # 從 TURN_URL1 解析 host 和 port (例如 turn:turn.yuanshoushen.com:3478)
        match = re.match(r"turn:([^:]+):(\d+)", settings.TURN_URL1)
        if match:
            host, port = match.groups()
            turn_urls = [
                f"turn:{host}:{port}?transport=udp",
                f"turn:{host}:{port}?transport=tcp",
            ]
        else:
            # fallback: 直接使用原始 URL
            turn_urls = [settings.TURN_URL1]

        # 產生 TURN 臨時憑證（time-limited credentials）
        ttl = settings.TURN_TTL_SEC_SERVER or 3600
        exp = int(time.time()) + ttl
        username = f"{exp}:watch:pin-user"
        hmac_key = settings.TURN_STATIC_AUTH_SECRET.encode()
        credential = base64.b64encode(
            hmac_module.new(hmac_key, username.encode(), hashlib.sha1).digest()
        ).decode()

        ice_servers.append({
            "urls": turn_urls,
            "username": username,
            "credential": credential,
        })

    return ice_servers


@router.get("/rtc-config", response_model=RtcConfigResponse)
async def rtc_config(
    request: Request,
    token: str = Query(..., min_length=10),
    scope: str = Query("watch"),
):
    settings = _get_settings(request)

    # 優先檢查 PIN Token
    now = time.time()
    if token in _pin_token_cache and _pin_token_cache[token] > now:
        # PIN Token 有效，從 settings 組裝 RTC config
        ice_servers = _build_ice_servers_from_settings(settings)
        return {"iceServers": ice_servers}

    # PIN Token 不存在或過期，呼叫 Workers 驗證
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(
            f"{settings.workers_base_url}/internal/rtc-config",
            headers={"x-internal-token": settings.internal_token},
            json={"token": token, "scope": scope},
        )

    if r.status_code == 200:
        data = r.json()
        if not isinstance(data, dict) or "iceServers" not in data or not isinstance(data["iceServers"], list):
            raise HTTPException(status_code=502, detail="bad rtc-config from workers")
        return {"iceServers": data["iceServers"]}

    # 把常見的 auth 失敗統一成 403
    if r.status_code in (400, 401, 403, 404):
        raise HTTPException(status_code=403, detail="token invalid")

    raise HTTPException(status_code=502, detail="workers rtc-config failed")


@router.get("/dashboard")
async def dashboard(
    request: Request,
    token: str = Query(..., min_length=10),
    scope: str = Query("dashboard:read"),
):
    # 優先檢查 PIN Token
    now = time.time()
    if token in _pin_token_cache and _pin_token_cache[token] > now:
        return {"ok": True, "source": "pin"}

    # PIN Token 不存在或過期，呼叫 Workers 驗證
    settings = _get_settings(request)

    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(
            f"{settings.workers_base_url}/internal/dashboard",
            headers={"x-internal-token": settings.internal_token},
            json={"token": token, "scope": scope},
        )
    if r.status_code == 200:
        data = r.json()
        return data.get("ok")

    # 把常見的 auth 失敗統一成 403
    if r.status_code in (400, 401, 403, 404):
        raise HTTPException(status_code=403, detail="token invalid")

    raise HTTPException(status_code=502, detail="workers dashboard failed")
