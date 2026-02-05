@echo off
REM === Cleanup Recordings Script ===
REM Copy this file to cleanup_recordings.bat and update the paths below

REM === Change to project directory ===
cd /d D:\Path\To\yolo-surveillance

REM === Activate Conda environment ===
call C:\Users\YourUsername\anaconda3\Scripts\activate.bat yolo-surveillance

REM === Run cleanup script ===
python scripts/cleanup_recordings.py --root recordings --keep-days 10 --dry-run >> logs\cleanup_recordings.log 2>&1
