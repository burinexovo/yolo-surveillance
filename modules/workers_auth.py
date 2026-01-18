# modules/workers_auth.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    status_code: int
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


async def verify_with_workers(
    *,
    workers_base_url: str,
    internal_token: str,
    token: str,
    scope: str = "watch",
    timeout: float = 5.0,
) -> VerifyResult:
    url = workers_base_url.rstrip("/") + "/internal/auth/verify"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
    }
    payload = {"token": token, "scope": scope}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as e:
        return VerifyResult(ok=False, status_code=502, error=f"workers request failed: {e}")

    # 嘗試解析 JSON（Workers 正常會回 JSON）
    data = None
    try:
        data = res.json()
    except Exception:
        data = None

    if res.status_code == 200 and isinstance(data, dict) and data.get("ok") is True:
        return VerifyResult(ok=True, status_code=200, data=data)

    # 失敗：保留 status_code +（如果有）error reason
    err = None
    if isinstance(data, dict):
        err = data.get("reason") or data.get("error")
    return VerifyResult(ok=False, status_code=res.status_code, data=data, error=err)
