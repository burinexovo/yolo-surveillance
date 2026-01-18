# scripts/test_r2_upload.py
import os
from pathlib import Path
from dotenv import load_dotenv

import cv2

from modules.cloudflare_r2 import CloudflareR2, R2Config
from utils.r2_keys import make_datetime_key

load_dotenv()

cfg = R2Config(
    access_key=os.getenv("R2_ACCESS_KEY"),
    secret_key=os.getenv("R2_SECRET_KEY"),
    bucket=os.getenv("R2_BUCKET"),
    endpoint=os.getenv("R2_ENDPOINT"),
    public_url=os.getenv("R2_PUBLIC_URL"),
)

# 讀圖 → encode → upload
path = Path("photos/smile_cat.png")
img = cv2.imread(str(path))
ok, buf = cv2.imencode(".png", img)
if not ok:
    raise RuntimeError("cv2.imencode failed")

r2 = CloudflareR2(cfg)
key = make_datetime_key(ext=".png")
url = r2.upload_bytes(buf.tobytes(), key=key, content_type="image/png")

print("Uploaded:", url)
