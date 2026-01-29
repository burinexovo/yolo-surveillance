# modules/audio_alert.py
import pyttsx3
import threading
import time
from pygame import mixer
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

_engine = None
_initialized = False


def init_audio(audio_path: str, rate: int = 120):
    """
    初始化音效系統（只能呼叫一次）
    """
    global _engine, _initialized

    if _initialized:
        return

    mixer.init()
    mixer.music.load(audio_path)  # 提前驗證音檔有效

    _engine = pyttsx3.init()
    _engine.setProperty("rate", rate)

    _initialized = True


def _alert_worker(times: int, audio_path: str):
    for _ in range(times):
        mixer.music.load(audio_path)
        mixer.music.play()
        time.sleep(0.5)

        text = "咕咕咕\n嘿！有客人來囉\n咕咕咕"
        _engine.say(text)
        _engine.runAndWait()
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

# from pygame import mixer
# import time
# import threading
# import pyttsx3
# import warnings
# import os
# warnings.filterwarnings("ignore", category=UserWarning)

# mixer.init()
# engine = pyttsx3.init()
# engine.setProperty("rate", 120)


# def alert_worker(times, audio_path):
#     """背景執行的警報流程，不要在主線程直接跑它。"""
#     for i in range(times):
#         mixer.music.load(audio_path)
#         mixer.music.play()
#         time.sleep(0.5)

#         text = "咕咕咕\n嘿！有客人來囉\n咕咕咕"
#         engine.say(text)
#         engine.runAndWait()
#         time.sleep(5)


# def play_alert_async(times, audio_path):
#     """Thread control"""
#     t = threading.Thread(target=alert_worker, args=(
#         times, audio_path,), daemon=True)
#     t.start()


# if __name__ == "__main__":
#     play_alert_async(times=1, audio_path="../assets/alert.mp3")

#     # 主執行緒不能中斷
#     time.sleep(10)
