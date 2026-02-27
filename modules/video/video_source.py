# modules/video_source.py
from __future__ import annotations

import os
from typing import Optional
from modules.settings import get_settings
from modules.video.rtsp_reader import RTSPReader, RTSPReaderConfig

settings = get_settings()

# 多攝影機支援：使用 dict 儲存各攝影機的 reader
_readers: dict[str, RTSPReader] = {}
_started: dict[str, bool] = {}


def get_reader(camera_id: str = "cam1") -> Optional[RTSPReader]:
    """
    取得指定 camera_id 的 RTSPReader。
    第一次呼叫時會建立並 start()，之後都重用同一個。

    Args:
        camera_id: 攝影機 ID（預設 "cam1"）

    Returns:
        RTSPReader 實例，若該攝影機未設定則回傳 None
    """
    global _readers, _started

    camera = settings.get_camera_by_id(camera_id)
    if camera is None:
        return None

    if camera_id not in _readers:
        _readers[camera_id] = RTSPReader(
            RTSPReaderConfig(
                # !!~ 主攝像頭測試用
                url=camera.rtsp_url,
                # url=settings.device_camera0,  # 用本機攝像頭
                drop_grab_n=1,  # 更流暢，延遲略高
            )
        )
        _started[camera_id] = False

    if not _started.get(camera_id, False):
        _readers[camera_id].start()
        _started[camera_id] = True

    return _readers[camera_id]


# 向後相容：保留舊的無參數呼叫方式
def get_default_reader() -> Optional[RTSPReader]:
    """取得預設攝影機（cam1）的 RTSPReader"""
    return get_reader("cam1")
