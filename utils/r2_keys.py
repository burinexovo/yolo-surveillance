# utils/r2_keys.py
from datetime import datetime

def make_datetime_key(ext: str, prefix: str = "") -> str:
    now = datetime.now()
    date_folder = now.strftime("%Y/%m/%d")
    filename = now.strftime("%Y-%m-%d_%H-%M-%S")
    key = f"{date_folder}/{filename}{ext}"
    if prefix:
        key = f"{prefix.rstrip('/')}/{key}"
    return key