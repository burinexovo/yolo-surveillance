# routers/dashboard_routes.py
from __future__ import annotations

import time
import secrets
import logging
from datetime import date, timedelta
from typing import Optional, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel

from modules.storage.visitor_db import visitor_db
from modules.core.shop_state_manager import shop_state_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# === Token 快取 ===
_token_cache: dict[str, float] = {}  # token → expiry_timestamp
CACHE_TTL = 300  # 5 分鐘

# === PIN 登入產生的 Token 快取 ===
_pin_token_cache: dict[str, float] = {}  # token → expiry_timestamp
PIN_TOKEN_TTL = 86400  # 24 小時


def _get_settings(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")
    return settings


async def verify_token(request: Request, token: str = Query(..., min_length=10)):
    """
    驗證 dashboard token，帶本地快取。
    - PIN Token 快取命中且未過期 → 直接放行
    - Workers Token 快取命中且未過期 → 直接放行
    - 否則呼叫 Workers 驗證，成功後存入快取
    """
    now = time.time()

    # 優先檢查 PIN Token 快取
    if token in _pin_token_cache and _pin_token_cache[token] > now:
        return token

    # 檢查 Workers Token 快取
    if token in _token_cache and _token_cache[token] > now:
        return token

    # 快取未命中或過期，呼叫 Workers 驗證
    settings = _get_settings(request)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                f"{settings.workers_base_url}/internal/dashboard",
                headers={"x-internal-token": settings.internal_token},
                json={"token": token, "scope": "dashboard:read"},
            )
    except httpx.RequestError as e:
        logger.error(f"Workers request failed: {e}")
        raise HTTPException(status_code=502, detail="Workers unreachable")

    if r.status_code == 200:
        # 驗證成功，存入快取
        _token_cache[token] = now + CACHE_TTL
        return token

    if r.status_code in (400, 401, 403, 404):
        # 驗證失敗，從快取移除（如果存在）
        _token_cache.pop(token, None)
        raise HTTPException(status_code=403, detail="token invalid")

    raise HTTPException(status_code=502, detail="Workers dashboard auth failed")


# === PIN 登入 ===

class PinLoginRequest(BaseModel):
    pin: str


class PinLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    expires_in: Optional[int] = None
    message: Optional[str] = None


@router.post("/pin-login", response_model=PinLoginResponse)
async def pin_login(request: Request, body: PinLoginRequest):
    """
    使用 PIN 碼登入 Dashboard，回傳 Token。
    """
    settings = _get_settings(request)

    # 檢查是否有設定 PIN
    if not settings.dashboard_pin:
        logger.warning("PIN login attempted but DASHBOARD_PIN not configured")
        raise HTTPException(status_code=503, detail="PIN login not configured")
    
    # 驗證 PIN
    if body.pin != settings.dashboard_pin:
        logger.info("PIN login failed: incorrect PIN")
        return PinLoginResponse(
            success=False,
            message="PIN 碼錯誤",
        )

    # 產生 Token
    token = secrets.token_urlsafe(32)
    now = time.time()
    _pin_token_cache[token] = now + PIN_TOKEN_TTL

    logger.info("PIN login successful, token issued")
    return PinLoginResponse(
        success=True,
        token=token,
        expires_in=PIN_TOKEN_TTL,
    )


# === Response Models ===

class RealtimeResponse(BaseModel):
    inside_count: int
    today_visits: int
    last_entry_ts: Optional[str]
    system_status: str
    had_visitor_last_10min: bool


class HourlyItem(BaseModel):
    hour: int
    count: int


class HourlyResponse(BaseModel):
    date: str
    hourly_data: list[HourlyItem]


class DailyItem(BaseModel):
    date: str
    count: int


class DailyResponse(BaseModel):
    range: str
    start_date: str
    end_date: str
    daily_data: list[DailyItem]


class PeakDay(BaseModel):
    date: str
    count: int


class PeakHour(BaseModel):
    hour: int
    avg_count: float


class SummaryResponse(BaseModel):
    range: str
    total_visits: int
    avg_daily_visits: float
    peak_day: Optional[PeakDay]
    peak_hour: Optional[PeakHour]


# === Range Type ===
RangeType = Literal["7d", "14d", "30d", "90d", "365d"]

RANGE_DAYS = {
    "7d": 7,
    "14d": 14,
    "30d": 30,
    "90d": 90,
    "365d": 365,
}


# === API Endpoints ===

@router.get("/realtime", response_model=RealtimeResponse)
async def get_realtime(
    request: Request,
    token: str = Depends(verify_token),
):
    """取得即時狀態"""

    state = shop_state_manager.snapshot()

    return RealtimeResponse(
        inside_count=state.inside_count,
        today_visits=state.today_visits,
        last_entry_ts=state.last_entry_ts.isoformat() if state.last_entry_ts else None,
        system_status="running",
        had_visitor_last_10min=state.had_visitor_in_last_minutes(10),
    )


@router.get("/hourly", response_model=HourlyResponse)
async def get_hourly(
    request: Request,
    token: str = Depends(verify_token),
    target_date: Optional[str] = Query(
        None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """取得指定日期的每小時分布"""

    d = date.fromisoformat(target_date) if target_date else date.today()
    hourly = visitor_db.get_hourly_distribution(d)

    return HourlyResponse(
        date=d.isoformat(),
        hourly_data=[HourlyItem(hour=h.hour, count=h.count) for h in hourly],
    )


@router.get("/daily", response_model=DailyResponse)
async def get_daily(
    request: Request,
    token: str = Depends(verify_token),
    range: RangeType = Query("7d"),
):
    """取得每日訪客趨勢"""

    days = RANGE_DAYS[range]
    daily = visitor_db.get_daily_trend(days)

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    return DailyResponse(
        range=range,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        daily_data=[DailyItem(date=d.date, count=d.count) for d in daily],
    )


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    request: Request,
    token: str = Depends(verify_token),
    range: RangeType = Query("30d"),
):
    """取得統計摘要"""

    days = RANGE_DAYS[range]
    summary = visitor_db.get_summary(days)

    return SummaryResponse(
        range=range,
        total_visits=summary["total_visits"],
        avg_daily_visits=summary["avg_daily_visits"],
        peak_day=PeakDay(**summary["peak_day"]) if summary["peak_day"] else None,
        peak_hour=PeakHour(**summary["peak_hour"]) if summary["peak_hour"] else None,
    )
