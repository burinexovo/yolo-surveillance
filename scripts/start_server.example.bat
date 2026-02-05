@echo off
REM === TCM Server Startup Script (for NSSM service) ===
REM Copy this file to start_server.bat and update the paths below

REM === Change to project directory ===
cd /d D:\Path\To\yolo-surveillance

REM === Activate Conda environment ===
REM Adjust the path based on your Conda installation
call C:\Users\YourUsername\anaconda3\Scripts\activate.bat yolo-surveillance

REM === Start uvicorn ===
uvicorn server:app --host 0.0.0.0 --port 8000
