# routers/camera_routes.py
"""攝影機 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from modules.settings import get_settings
from routers.dashboard_routes import verify_token

router = APIRouter(prefix="/api", tags=["cameras"])

settings = get_settings()


class CameraInfo(BaseModel):
    """攝影機資訊"""
    id: str
    label: str


class CamerasResponse(BaseModel):
    """攝影機列表回應"""
    cameras: list[CameraInfo]


@router.get("/cameras", response_model=CamerasResponse)
async def list_cameras(
    request: Request,
    token: str = Depends(verify_token),
):
    """列出所有可用的攝影機"""
    cameras = settings.get_cameras()
    return CamerasResponse(
        cameras=[
            CameraInfo(id=cam.camera_id, label=cam.label)
            for cam in cameras
        ]
    )
