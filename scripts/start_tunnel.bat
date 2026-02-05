@echo off
REM === Cloudflare Tunnel Startup Script (for NSSM service) ===

REM === Start cloudflared tunnel (use full absolute path for service context) ===
"C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" tunnel run tcm-backend
