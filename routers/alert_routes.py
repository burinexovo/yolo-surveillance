# routers/alert_routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from modules.notifications.alert_manager import alert_manager

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
)


class AlertUpdate(BaseModel):
    enabled: bool


@router.get("/all-users")
async def get_all_alerts():
    """列出所有 user 的通知狀態"""
    return alert_manager.get_all()


@router.get("/{user_id}")
async def get_user_alert(user_id: str):
    """查詢某個 user 的通知狀態"""
    try:
        enabled = alert_manager.get_notifications(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "notifications_enabled": enabled,
    }


@router.patch("/{user_id}")
async def update_user_alert(user_id: str, body: AlertUpdate):
    """更新某個 user 的通知開關"""
    try:
        alert_manager.set_notifications(user_id, body.enabled)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user_id,
        "notifications_enabled": body.enabled,
    }
