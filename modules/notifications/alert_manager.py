# modules/alert_manager.py
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any
from modules.settings import get_settings


@dataclass
class AlertManager:
    config_path: Path
    users: Dict[str, Any] = field(default_factory=dict)

    def load(self):
        """載入 users.json → 填到 self.users"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.users = json.load(f)
        else:
            self.users = {}

    def save(self):
        """把 self.users 寫回 users.json"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def set_notifications(self, user_id: str, enabled: bool):
        """設定 notifications_enabled"""
        if user_id not in self.users:
            raise KeyError(f"User {user_id} not found.")

        self.users[user_id]["notifications_enabled"] = enabled
        self.save()

    def get_notifications(self, user_id: str) -> bool:
        """取得單一 user notifications_enabled"""
        if user_id not in self.users:
            raise KeyError(f"User {user_id} not found.")

        return self.users[user_id].get("notifications_enabled", True)

    def get_all(self):
        """回傳所有資料"""
        return self.users


settings = get_settings()
if settings.user_id_file_path is None:
    raise RuntimeError("USER_ID_FILE_PATH 未設定")

alert_manager = AlertManager(config_path=settings.user_id_file_path)
alert_manager.load()
