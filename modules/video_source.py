# modules/video_source.py
from __future__ import annotations

import os
from typing import Optional
from modules.settings import get_settings
from modules.rtsp_reader import RTSPReader, RTSPReaderConfig

settings = get_settings()

_reader: Optional[RTSPReader] = None
_started: bool = False


def get_reader() -> RTSPReader:
    """
    取得全域共用的 RTSPReader。
    第一次呼叫時會建立並 start()，之後都重用同一個。
    """
    global _reader, _started

    if _reader is None:
        _reader = RTSPReader(
            RTSPReaderConfig(
                # url=settings.rtsp_url_stream1,
                url=settings.device_camera0,
                drop_grab_n=2,
            )
        )

    if not _started:
        _reader.start()
        _started = True

    return _reader
