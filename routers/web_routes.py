# routers/web_routes.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@router.get("/watch")
async def watch_page(
    request: Request,
    token: str = Query(..., min_length=10),
):
    return FileResponse(WEB_DIR / "index.html")


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    token: str = Query(..., min_length=10),
):
    return FileResponse(WEB_DIR / "dashboard.html")
