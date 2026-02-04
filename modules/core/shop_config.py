"""店家設定管理模組"""
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DAY_MAP = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


@dataclass
class ShopConfig:
    """店家設定（從 shop.json 載入）"""
    cameras: dict
    entry_cooldown: float
    after_hours_cooldown: float
    after_hours: dict
    dashboard_pin: Optional[str]

    @classmethod
    def load(cls, path: Path = Path("config/shop.json")) -> "ShopConfig":
        """載入設定檔"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            cameras=data.get("cameras", {}),
            entry_cooldown=data.get("notifications", {}).get("entry_cooldown", 10.0),
            after_hours_cooldown=data.get("notifications", {}).get("after_hours_cooldown", 600.0),
            after_hours=data.get("after_hours", {}),
            dashboard_pin=data.get("dashboard_pin"),
        )

    def get_camera_label(self, camera_id: str) -> str:
        """取得攝影機標籤"""
        return self.cameras.get(camera_id, {}).get("label", camera_id)

    def is_after_hours(self) -> bool:
        """判斷當前是否為非營業時段"""
        now = datetime.now()
        day_key = DAY_MAP[now.weekday()]
        now_time = now.time()

        periods = self.after_hours.get(day_key, [])
        for period in periods:
            if self._time_in_range(now_time, period["start"], period["end"]):
                return True
        return False

    @staticmethod
    def _time_in_range(now_time, start_str: str, end_str: str) -> bool:
        """判斷時間是否在範圍內（支援跨午夜）"""
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()

        if start > end:
            return now_time >= start or now_time <= end
        else:
            return start <= now_time <= end


# 全域實例（程式啟動時載入一次）
_shop_config: Optional[ShopConfig] = None


def get_shop_config(path: Path = Path("config/shop.json")) -> ShopConfig:
    """取得店家設定（單例）"""
    global _shop_config
    if _shop_config is None:
        _shop_config = ShopConfig.load(path)
        logger.info("Loaded shop config from %s", path)
    return _shop_config


def reload_shop_config(path: Path = Path("config/shop.json")) -> ShopConfig:
    """重新載入設定（供 API 使用）"""
    global _shop_config
    _shop_config = ShopConfig.load(path)
    logger.info("Reloaded shop config from %s", path)
    return _shop_config
