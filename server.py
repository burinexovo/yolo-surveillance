# server.py
from pathlib import Path
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from modules.yolo_runtime import YoloRuntime
from modules.settings import get_settings
from modules.shop_state_manager import shop_state_manager  # instance

from routers.alert_routes import router as alert_router
from routers.state_routes import router as state_router
from routers.auth_routes import router as auth_router
from routers.watch_routes import router as watch_router
from modules.signaling.router import router as signaling_router

from utils.logging import setup_logging


settings = get_settings()

runtime = YoloRuntime(
    settings=settings,
    shop_state_manager=shop_state_manager,
    show_window=False,
    run_in_thread=True,
)

setup_logging(
    # level=logging.INFO,        # production
    level=logging.DEBUG,         # debug 用
    log_file="logs/app.log",     # 可選
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === Startup ===
    runtime.start()
    logger.info("🚀 YoloRuntime started")

    yield

    # === Shutdown ===
    runtime.stop()
    logger.info("🛑 YoloRuntime stopped")


app = FastAPI(
    title="TCM Shop CCTV System",
    lifespan=lifespan,
)

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
app.include_router(signaling_router)


if __name__ == "__main__":
    import uvicorn
    # public command: uvicorn server:app --host 0.0.0.0 --port 8000
    # cloudflared tunnel run tcm-backend
    # debug command: uvicorn server:app --reload

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
