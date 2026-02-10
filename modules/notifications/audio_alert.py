# modules/audio_alert.py
import logging
import random
import threading
import time
from pathlib import Path
from pygame import mixer
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)

_initialized = False
_greetings: list[Path] = []


def init_audio(audio_path: str):
    """
    初始化音效系統（只能呼叫一次）
    """
    global _initialized, _greetings

    if _initialized:
        return

    mixer.init()
    mixer.music.load(audio_path)  # 提前驗證音檔有效

    # 收集同目錄下除了 alert.mp3 以外的所有 mp3 作為 greeting
    sounds_dir = Path(audio_path).parent
    alert_name = Path(audio_path).name
    _greetings = [f for f in sounds_dir.glob("*.mp3") if f.name != alert_name]
    logger.info("已載入 %d 個 greeting 音檔: %s",
                len(_greetings), [f.name for f in _greetings])

    _initialized = True


def _alert_worker(times: int, audio_path: str):
    for _ in range(times):
        # 1) 提示音
        try:
            mixer.music.load(audio_path)
            mixer.music.play()
            while mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logger.error("提示音播放失敗: %s", e)

        # 2) 隨機播放一個 greeting
        if _greetings:
            chosen = random.choice(_greetings)
            try:
                mixer.music.load(str(chosen))
                mixer.music.play()
                while mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e:
                logger.error("greeting 播放失敗 (%s): %s", chosen.name, e)

        time.sleep(5)


def play_alert_async(times: int, audio_path: str):
    """
    非同步播放警報
    """
    if not _initialized:
        raise RuntimeError("Audio not initialized. Call init_audio() first.")

    t = threading.Thread(
        target=_alert_worker,
        args=(times, audio_path),
        daemon=True,
    )
    t.start()
