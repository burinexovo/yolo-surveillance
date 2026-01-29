from modules.notifications.audio_alert import init_audio, play_alert_async
import time
import os
import warnings
from dotenv import load_dotenv

# 關 pygame / pkg_resources 雜訊
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

load_dotenv()

AUDIO_ALERT_PATH = os.getenv("AUDIO_ALERT_PATH")


init_audio(AUDIO_ALERT_PATH)
play_alert_async(times=1, audio_path=AUDIO_ALERT_PATH)

time.sleep(10)

print("finish")
