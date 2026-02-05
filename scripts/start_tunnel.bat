@echo off
REM === Cloudflare Tunnel 啟動腳本 (供 NSSM 服務使用) ===

REM === 啟動 cloudflared tunnel ===
cloudflared tunnel run tcm-backend
