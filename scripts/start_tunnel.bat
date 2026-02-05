@echo off
REM === Cloudflare Tunnel Startup Script (for NSSM service) ===

REM === Start cloudflared tunnel with explicit config path ===
"C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" tunnel --config "C:\Users\User\.cloudflared\config.yml" run tcm-backend
