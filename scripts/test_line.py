# scripts/test_line.py
import os
from datetime import datetime
from dotenv import load_dotenv

from modules.line_notify import LineConfig, push_message

load_dotenv()

cfg = LineConfig(
    access_token=os.getenv("LINE_ACCESS_TOKEN"),
    user_file=os.getenv("USER_ID_FILE_PATH"),
)

curr_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

push_message(
    cfg,
    msg=f"推播測試 {curr_time}",
    img_url="https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?q=80&w=2886&auto=format&fit=crop",
)
