import json
import os
import subprocess
from dotenv import load_dotenv

from pathlib import Path

load_dotenv()

KV_USERS_NAMESPACE_ID = os.getenv("KV_USERS_NAMESPACE_ID")
KV_USERS_PREFIX = os.getenv("KV_USERS_PREFIX")

# 1) list keys
out = subprocess.check_output([
    "wrangler", "kv", "key", "list",
    "--namespace-id", KV_USERS_NAMESPACE_ID,
    "--prefix", KV_USERS_PREFIX, "--remote"
], text=True)

keys = json.loads(out)
result = {}

# 2) get each value
for item in keys:
    key = item["name"]
    val = subprocess.check_output([
        "wrangler", "kv", "key", "get", key,
        "--namespace-id", KV_USERS_NAMESPACE_ID, "--remote"
    ], text=True).strip()

    # key: user:Uxxx -> Uxxx
    user_id = key[len(KV_USERS_PREFIX):]
    result[user_id] = json.loads(val) if val else {}

# 3) write to users.json
# BASE_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT = BASE_DIR.parent   # 視你的檔案位置調整
# config_path = PROJECT_ROOT / "config" / "users_kv.json"
# config_path.parent.mkdir(parents=True, exist_ok=True)

with open("config/users_kv.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=4)

print(f"Saved {len(result)} users to users_from_kv.json")
