# modules/settings.py
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from functools import lru_cache


class CameraConfig(BaseModel):
    """攝影機設定"""
    camera_id: str      # "cam1", "cam2"
    label: str          # "門口攝影機", "店內攝影機"
    rtsp_url: str
    has_yolo: bool = False


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
    device_camera0: Optional[str] = None  # 作為 camera1_rtsp_url 的回退值

    # =========================
    # Multi-Camera Config
    # =========================
    # Camera 1 (with YOLO)
    camera1_id: str = "cam1"
    camera1_label: str = "門口攝影機"
    camera1_rtsp_url: Optional[str] = None  # 回退到 device_camera0
    camera1_has_yolo: bool = True

    # Camera 2 (view only)
    camera2_id: str = "cam2"
    camera2_label: str = "店內攝影機"
    camera2_rtsp_url: Optional[str] = None
    camera2_has_yolo: bool = False

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
    yolo26_model_m_path: Optional[Path] = None

    # =========================
    # Trackers
    # =========================
    tracker_botsort_path: Optional[Path] = None
    tracker_bytetrack_path: Optional[Path] = None

    # =========================
    # Alert / Notify Controls
    # =========================
    notify_cooldown: Optional[float] = 10.0

    # =========================
    # After Hours Alert
    # =========================
    after_hours_start: str = "23:00"  # 非營業時段開始（HH:MM）
    after_hours_end: str = "06:30"    # 非營業時段結束（HH:MM）
    after_hours_notify_cooldown: float = 600.0  # 冷卻時間（秒），預設 10 分鐘

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
    # Debug Mode
    # ======================
    debug: bool = False  # 預設關閉，正式環境不啟用 debug

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

    def get_cameras(self) -> list[CameraConfig]:
        """取得所有已設定的攝影機列表"""
        cameras = []

        # Camera 1 (用 device_camera0 作為回退)
        cam1_url = self.camera1_rtsp_url or self.device_camera0
        if cam1_url:
            cameras.append(CameraConfig(
                camera_id=self.camera1_id,
                label=self.camera1_label,
                rtsp_url=cam1_url,
                has_yolo=self.camera1_has_yolo,
            ))

        # Camera 2
        if self.camera2_rtsp_url:
            cameras.append(CameraConfig(
                camera_id=self.camera2_id,
                label=self.camera2_label,
                rtsp_url=self.camera2_rtsp_url,
                has_yolo=self.camera2_has_yolo,
            ))

        return cameras

    def get_camera_by_id(self, camera_id: str) -> Optional[CameraConfig]:
        """依 camera_id 取得攝影機設定"""
        for cam in self.get_cameras():
            if cam.camera_id == camera_id:
                return cam
        return None


@lru_cache
def get_settings() -> Settings:
    # 確保整個程式生命週期只建立一個 Settings 實例
    return Settings()
