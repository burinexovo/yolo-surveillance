@echo off

REM === 切到專案目錄 ===
cd /d PROJECT_PATH

REM === 啟用 conda ===
call C:\Users\User\anaconda3\Scripts\activate.bat yolo-surveillance

REM === 執行清理腳本 ===
python scripts/cleanup_recordings.py --root recordings --keep-days 10 --dry-run >> logs\cleanup_recordings.log 2>&1