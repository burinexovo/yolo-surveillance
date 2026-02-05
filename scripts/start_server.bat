@echo off
REM === TCM Server 啟動腳本 (供 NSSM 服務使用) ===
REM 請將 PROJECT_PATH 替換為實際路徑，例如 D:\Code\yolo11-detect

REM === 切換到專案目錄 ===
cd /d PROJECT_PATH

REM === 啟用 Conda 環境 ===
REM 根據你的 Conda 安裝路徑調整
call C:\Users\User\anaconda3\Scripts\activate.bat yolo-surveillance

REM === 啟動 uvicorn ===
uvicorn server:app --host 0.0.0.0 --port 8000
