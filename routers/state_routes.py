# routers/state_routes.py
from __future__ import annotations

from fastapi import APIRouter
from modules.core.shop_state_manager import shop_state_manager


router = APIRouter(prefix="/api", tags=["state"])


@router.get("/shop-state")
async def get_shop_state():
    state = shop_state_manager.snapshot()
    return {
        "system_alerts_enabled": state.system_alerts_enabled,
        "inside_count": state.inside_count,  # 目前店內人數
        "today_visits": state.today_visits,  # 今天有多少人來過
        "last_entry_ts": state.last_entry_ts.isoformat() if state.last_entry_ts else None,  # 最後來的
        "had_visitor_last_10min": state.had_visitor_in_last_minutes(10),  # 10分鐘客人數量
    }

#         f"📲 你的 LINE 推播通知：{user_notify}\n"
#         f"👥 店內目前：{shop_state.inside_count} 人\n"
#         f"🏪 今日來客：{shop_state.today_visits} 人\n"
#         f"🕒 最近入店：{last}\n"
#         f"⏳ 最近10分鐘入店：{recent}"


# @router.get("/shop")
# def make_line_status_message(user_id: str, shop_state: ShopState, alert_manager: AlertManager) -> str:
#     # 系統層級
#     # sys_notify = "啟用" if shop_state.system_alerts_enabled else "關閉"

#     # 使用者層級
#     try:
#         user_enabled = alert_manager.get_notifications(user_id)
#         user_notify = "啟用" if user_enabled else "關閉"
#     except KeyError:
#         user_notify = "未註冊"

#     last = shop_state.last_entry_ts.strftime(
#         "%H:%M") if shop_state.last_entry_ts else "尚無資料"
#     recent = "有" if shop_state.had_visitor_in_last_minutes(10) else "無"

#     return ( # 這邊是 LINE要做的
#         "📡 系統：正常運作中\n"
#         # f"🔔 店內系統提醒：{sys_notify}\n"
#         f"📲 你的 LINE 推播通知：{user_notify}\n"
#         f"👥 店內目前：{shop_state.inside_count} 人\n"
#         f"🏪 今日來客：{shop_state.today_visits} 人\n"
#         f"🕒 最近入店：{last}\n"
#         f"⏳ 最近10分鐘入店：{recent}"
#     )
