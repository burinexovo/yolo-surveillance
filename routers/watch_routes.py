# routers/watch_routes.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from modules.workers_auth import verify_with_workers

router = APIRouter(tags=["watch"])
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _expired_html(msg: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>連結已失效</title>
</head>
<body style="font-family:-apple-system,system-ui;padding:24px;">
  <h2>觀看連結已失效或過期</h2>
  <p>{msg}</p>
  <p>請關閉此頁，回到 LINE 再點一次「即時畫面」。</p>
  <script>alert({msg!r});</script>
</body>
</html>"""


@router.get("/watch")
async def watch_page(
    request: Request,
    token: str = Query(..., min_length=10),
):
    # settings = request.app.state.settings

    # result = await verify_with_workers(
    #     workers_base_url=settings.workers_base_url,
    #     internal_token=settings.internal_token,
    #     token=token,
    #     scope="watch",
    # )

    # if not result.ok:
    #     # 這裡統一用 HTML 呈現，避免 {"detail": ...}
    #     return HTMLResponse(
    #         _expired_html("觀看連結已失效或過期，請回到 LINE 重新取得連結。"),
    #         status_code=403,
    #     )

    return FileResponse(WEB_DIR / "index.html")