# server.py
from pathlib import Path
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from modules.core.yolo_runtime import YoloRuntime
from modules.settings import get_settings
from modules.core.shop_state_manager import shop_state_manager  # instance
from modules.video.camera_recorder import CameraRecorder, CameraRecorderConfig

from routers.alert_routes import router as alert_router
from routers.state_routes import router as state_router
from routers.auth_routes import router as auth_router
from routers.web_routes import router as watch_router
from routers.dashboard_routes import router as dashboard_router
from routers.recording_routes import router as recording_router
from routers.camera_routes import router as camera_router
from modules.signaling.router import router as signaling_router

from utils.logging import setup_logging


settings = get_settings()


# === 安全 Headers 中間件 ===
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """加入安全相關的 HTTP Headers"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 防止 MIME 類型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防止點擊劫持（頁面不允許被嵌入 iframe）
        response.headers["X-Frame-Options"] = "DENY"

        # XSS 防護（現代瀏覽器大多內建，但仍建議加上）
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 強制 HTTPS（僅在非 debug 模式啟用）
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # 限制 Referrer 資訊洩漏
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 權限政策：禁用不需要的功能
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(self)"
        )

        return response

# === cam1: YOLO + 錄影（由 YoloRuntime 處理）===
runtime = YoloRuntime(
    settings=settings,
    shop_state_manager=shop_state_manager,
    show_window=False,
    run_in_thread=True,
)

# === 非 YOLO 攝影機的獨立錄影服務 ===
camera_recorders: list[CameraRecorder] = []
for cam in settings.get_cameras():
    if not cam.has_yolo:  # cam2 等非 YOLO 攝影機
        recorder = CameraRecorder(CameraRecorderConfig(
            camera=cam,
            fps=30,
            segment_minutes=3,
        ))
        camera_recorders.append(recorder)

# 根據 settings.debug 決定 logging level
setup_logging(
    level=logging.DEBUG if settings.debug else logging.INFO,
    log_file="logs/app.log",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === Startup ===
    runtime.start()
    logger.info("YoloRuntime started (cam1)")

    for recorder in camera_recorders:
        recorder.start()
        logger.info("CameraRecorder started (%s)", recorder.camera.camera_id)

    yield

    # === Shutdown ===
    for recorder in camera_recorders:
        recorder.stop()

    runtime.stop()
    logger.info("All recorders stopped")


app = FastAPI(
    title="TCM Shop CCTV System",
    lifespan=lifespan,
    # 正式環境隱藏 docs
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# 加入安全 Headers 中間件
app.add_middleware(SecurityHeadersMiddleware)

# ✅ 全域共享設定
app.state.settings = settings

# ✅ 統一管理 web 目錄（給 StaticFiles + /watch 用）
WEB_DIR = Path(__file__).parent / "web"
app.state.web_dir = WEB_DIR

# ✅ 靜態檔案（/web/*）
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")

# ✅ routers
app.include_router(alert_router)
app.include_router(state_router)
app.include_router(auth_router)
app.include_router(watch_router)
app.include_router(dashboard_router)
app.include_router(recording_router)
app.include_router(camera_router)
app.include_router(signaling_router)


if __name__ == "__main__":
    import uvicorn
    # 正式環境: uvicorn server:app --host 0.0.0.0 --port 8000
    # 開發環境: DEBUG=true uvicorn server:app --reload
    # Cloudflare Tunnel: cloudflared tunnel run tcm-backend

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,  # 僅在 debug 模式啟用熱重載
    )
