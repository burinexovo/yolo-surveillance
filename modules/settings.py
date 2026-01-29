# modules/settings.py
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # =========================
    # LINE Messaging API
    # =========================
    line_access_token: str
    line_channel_secret: str

    # =========================
    # Cloudflare
    # =========================
    cloudflare_id: str
    cloudflare_api: str

    # =========================
    # Cloudflare R2
    # =========================
    r2_access_key: str
    r2_secret_key: str
    r2_bucket: str
    r2_endpoint: str
    r2_public_url: str

    # =========================
    # Cloudflare KV
    # =========================
    kv_users_namespace_id: Optional[str] = None
    kv_users_prefix: Optional[str] = None
    kv_watch_token_namespace_id: Optional[str] = None
    kv_watch_token_prefix: Optional[str] = None

    # =========================
    # Cloudflare Workers
    # =========================
    workers_base_url: Optional[str] = None

    # =========================
    # Video Inputs / Streaming
    # =========================
    device_camera0: Optional[str] = None
    rtsp_url_stream1: Optional[str] = None
    rtsp_url_stream2: Optional[str] = None

    # =========================
    # Directories
    # =========================
    video_save_dir: Optional[Path] = None
    assets_dir: Optional[Path] = None
    screenshot_dir: Optional[Path] = None
    photos_dir: Optional[Path] = None

    # =========================
    # Notifications / Sound
    # =========================
    audio_alert_path: Optional[Path] = None

    # =========================
    # User Config
    # =========================
    user_id_file_path: Optional[Path] = None

    # =========================
    # YOLO Model paths
    # =========================
    yolo11_model_l_path: Optional[Path] = None
    yolo11_model_m_path: Optional[Path] = None
    yolo11_model_s_path: Optional[Path] = None
    yolo11_model_n_path: Optional[Path] = None

    # =========================
    # Trackers
    # =========================
    tracker_botsort_path: Optional[Path] = None
    tracker_bytetrack_path: Optional[Path] = None

    # =========================
    # Alert / Notify Controls
    # =========================
    notify_cooldown: Optional[float] = 10.0

    # ======================
    # Local Url
    # ======================
    local_url: Optional[str] = None

    # ======================
    # Internal token
    # ======================
    internal_token: Optional[str] = None

    # ======================
    # Dashboard PIN
    # ======================
    dashboard_pin: Optional[str] = None

    # ======================
    # WebRTC STUN/TURN
    # ======================
    STUN_URL1: Optional[str] = None
    STUN_URL2: Optional[str] = None
    # STUN_URL3: Optional[str] = None
    # STUN_URL4: Optional[str] = None

    TURN_URL1: Optional[str] = None
    TURN_STATIC_AUTH_SECRET: Optional[str] = None
    TURN_TTL_SEC_SERVER: Optional[int] = 3600


    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    # 確保整個程式生命週期只建立一個 Settings 實例
    return Settings()
