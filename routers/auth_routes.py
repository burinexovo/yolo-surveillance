# routers/auth_routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Any

import httpx

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


@router.get("/rtc-config", response_model=RtcConfigResponse)
async def rtc_config(
    request: Request,
    token: str = Query(..., min_length=10),
    scope: str = Query("watch"),
):
    settings = _get_settings(request)

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
