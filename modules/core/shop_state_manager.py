from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta, date
from collections import deque
import copy
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class ShopState:
    system_alerts_enabled: bool = True
    inside_count: int = 0
    today_visits: int = 0
    last_entry_ts: Optional[datetime] = None
    entry_log: deque = field(default_factory=lambda: deque(maxlen=500))
    _current_date: date = field(default_factory=date.today)

    def set_sys_alerts(self, enabled):
        self.system_alerts_enabled = enabled

    def record_entry(self):
        """記錄一次進店（客流量 +1）"""
        now = datetime.now()
        today = now.date()

        # 跨日重置
        if today != self._current_date:
            self.today_visits = 0
            self._current_date = today

        self.today_visits += 1
        self.last_entry_ts = now
        self.entry_log.append(now)

    def set_inside_count(self, count: int):
        """直接設定店內人數（基於偵測數量）"""
        self.inside_count = max(0, count)

    def had_visitor_in_last_minutes(self, mins=10):
        now = datetime.now()
        return any(t >= now - timedelta(minutes=mins) for t in self.entry_log)


class ShopStateManager:
    """
    管理單一 ShopState 實例，負責：
    - thread-safe 更新
    - 對外提供 snapshot / 狀態查詢
    - 同步寫入 SQLite 持久化
    """

    def __init__(self) -> None:
        self._state = ShopState()
        self._lock = threading.Lock()
        self._db = None  # lazy import 避免循環引用
        self._restore_from_db()

    def _restore_from_db(self) -> None:
        """啟動時從 SQLite 恢復今日訪客數"""
        try:
            db = self._get_db()
            self._state.today_visits = db.get_today_visits()
            logger.info("從 DB 恢復今日訪客數: %d", self._state.today_visits)
        except Exception as e:
            logger.warning("無法從 DB 恢復訪客數: %s", e)

    def _get_db(self):
        """延遲載入 visitor_db 避免循環引用"""
        if self._db is None:
            from modules.storage.visitor_db import visitor_db
            self._db = visitor_db
        return self._db

    # === 更新用 API（給 YoloRuntime 呼叫）===

    def record_entry(self) -> None:
        """記錄一次進店（客流量 +1），寫入記憶體 + SQLite"""
        with self._lock:
            self._state.record_entry()

        # 寫入 SQLite（在 lock 外執行，避免阻塞）
        try:
            self._get_db().record_entry()
        except Exception as e:
            logger.exception("Failed to record entry to DB")

    def set_inside_count(self, count: int) -> None:
        """直接設定店內人數（基於即時偵測數量）"""
        with self._lock:
            self._state.set_inside_count(count)

    def set_system_alerts(self, enabled: bool) -> None:
        with self._lock:
            self._state.system_alerts_enabled = enabled

    # === 查詢用 API（給 routers / webhook 用）===

    def snapshot(self) -> ShopState:
        """回傳一份複製的 state，避免外面不小心改到原始物件。"""
        with self._lock:
            return copy.deepcopy(self._state)

    def system_alerts_enabled(self) -> bool:
        with self._lock:
            return self._state.system_alerts_enabled


# 🔥 全專案共用的 manager 單例
shop_state_manager = ShopStateManager()
