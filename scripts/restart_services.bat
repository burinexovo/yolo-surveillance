@echo off
REM === TCM 服務一鍵重啟腳本 ===
REM 需要以管理員身份執行

echo ========================================
echo   TCM Services Restart
echo ========================================
echo.

echo [1/4] Stopping tcm-server...
nssm stop tcm-server
timeout /t 2 /nobreak >nul

echo [2/4] Stopping tcm-tunnel...
nssm stop tcm-tunnel
timeout /t 2 /nobreak >nul

echo [3/4] Starting tcm-server...
nssm start tcm-server
timeout /t 3 /nobreak >nul

echo [4/4] Starting tcm-tunnel...
nssm start tcm-tunnel
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   Services Status
echo ========================================
echo.
echo tcm-server:
nssm status tcm-server
echo.
echo tcm-tunnel:
nssm status tcm-tunnel
echo.
echo ========================================
echo   Done!
echo ========================================
pause
