# routers/web_routes.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@router.get("/watch")
async def watch_page(
    request: Request,
    token: Optional[str] = Query(None),
):
    """
    即時畫面頁面。
    - 有 token: 前端直接驗證使用
    - 無 token: 前端顯示 PIN 登入畫面
    """
    return FileResponse(WEB_DIR / "watch.html")


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    token: Optional[str] = Query(None),
):
    """
    Dashboard 頁面。
    - 有 token: 前端直接驗證使用
    - 無 token: 前端顯示 PIN 登入畫面
    """
    return FileResponse(WEB_DIR / "dashboard.html")
