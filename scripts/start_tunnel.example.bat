@echo off
REM === Cloudflare Tunnel Startup Script (for NSSM service) ===
REM Copy this file to start_tunnel.bat and update the paths below

REM === Start cloudflared tunnel with explicit config path ===
REM Update these paths:
REM   1. Path to cloudflared.exe (find with: Get-ChildItem -Path "C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\*cloudflared*" -Recurse -Filter "*.exe")
REM   2. Path to your .cloudflared config folder
"C:\Users\YourUsername\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" tunnel --config "C:\Users\YourUsername\.cloudflared\config.yml" run your-tunnel-name
