# === TCM 服務安裝腳本 (PowerShell) ===
# 需要以管理員身份執行
# 執行方式: 右鍵 PowerShell -> 以系統管理員身份執行 -> cd 到專案目錄 -> .\scripts\install_services.ps1

param(
    [string]$ProjectPath = "D:\Code\yolo11-detect",  # 修改為你的專案路徑
    [string]$LogPath = "D:\tcm-logs"                  # 日誌存放路徑
)

# 檢查是否以管理員身份執行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "錯誤: 請以管理員身份執行此腳本" -ForegroundColor Red
    Write-Host "右鍵點擊 PowerShell -> 以系統管理員身份執行" -ForegroundColor Yellow
    exit 1
}

# 檢查 NSSM 是否已安裝
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "錯誤: 找不到 NSSM，請先安裝" -ForegroundColor Red
    Write-Host "安裝方式: winget install nssm" -ForegroundColor Yellow
    Write-Host "或從 https://nssm.cc/download 下載" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TCM 服務安裝程式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "專案路徑: $ProjectPath" -ForegroundColor Gray
Write-Host "日誌路徑: $LogPath" -ForegroundColor Gray
Write-Host ""

# 建立日誌目錄
if (-not (Test-Path $LogPath)) {
    Write-Host "建立日誌目錄: $LogPath" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

# 腳本路徑
$serverScript = Join-Path $ProjectPath "scripts\start_server.bat"
$tunnelScript = Join-Path $ProjectPath "scripts\start_tunnel.bat"

# 檢查腳本是否存在
if (-not (Test-Path $serverScript)) {
    Write-Host "錯誤: 找不到 $serverScript" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $tunnelScript)) {
    Write-Host "錯誤: 找不到 $tunnelScript" -ForegroundColor Red
    exit 1
}

# === 安裝 tcm-server 服務 ===
Write-Host "[1/2] 安裝 tcm-server 服務..." -ForegroundColor Green

# 先移除舊服務（如果存在）
$existingServer = nssm status tcm-server 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  移除舊的 tcm-server 服務..." -ForegroundColor Yellow
    nssm stop tcm-server 2>$null
    nssm remove tcm-server confirm 2>$null
}

# 安裝服務
nssm install tcm-server $serverScript
nssm set tcm-server AppDirectory $ProjectPath
nssm set tcm-server AppStdout "$LogPath\server.log"
nssm set tcm-server AppStderr "$LogPath\server_err.log"
nssm set tcm-server AppStdoutCreationDisposition 4  # 追加模式
nssm set tcm-server AppStderrCreationDisposition 4
nssm set tcm-server AppRestartDelay 5000            # 崩潰後 5 秒重啟
nssm set tcm-server Description "TCM Shop CCTV Server (uvicorn)"
nssm set tcm-server Start SERVICE_AUTO_START        # 開機自動啟動

Write-Host "  tcm-server 安裝完成" -ForegroundColor Green

# === 安裝 tcm-tunnel 服務 ===
Write-Host "[2/2] 安裝 tcm-tunnel 服務..." -ForegroundColor Green

# 先移除舊服務（如果存在）
$existingTunnel = nssm status tcm-tunnel 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  移除舊的 tcm-tunnel 服務..." -ForegroundColor Yellow
    nssm stop tcm-tunnel 2>$null
    nssm remove tcm-tunnel confirm 2>$null
}

# 安裝服務
nssm install tcm-tunnel $tunnelScript
nssm set tcm-tunnel AppStdout "$LogPath\tunnel.log"
nssm set tcm-tunnel AppStderr "$LogPath\tunnel_err.log"
nssm set tcm-tunnel AppStdoutCreationDisposition 4
nssm set tcm-tunnel AppStderrCreationDisposition 4
nssm set tcm-tunnel AppRestartDelay 5000
nssm set tcm-tunnel Description "TCM Cloudflare Tunnel"
nssm set tcm-tunnel Start SERVICE_AUTO_START

Write-Host "  tcm-tunnel 安裝完成" -ForegroundColor Green

# === 啟動服務 ===
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  啟動服務" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "啟動 tcm-server..." -ForegroundColor Yellow
nssm start tcm-server
Start-Sleep -Seconds 3

Write-Host "啟動 tcm-tunnel..." -ForegroundColor Yellow
nssm start tcm-tunnel
Start-Sleep -Seconds 2

# === 顯示狀態 ===
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  服務狀態" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "tcm-server:" -ForegroundColor White
nssm status tcm-server

Write-Host ""
Write-Host "tcm-tunnel:" -ForegroundColor White
nssm status tcm-tunnel

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安裝完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "日誌位置:" -ForegroundColor Gray
Write-Host "  Server: $LogPath\server.log" -ForegroundColor Gray
Write-Host "  Tunnel: $LogPath\tunnel.log" -ForegroundColor Gray
Write-Host ""
Write-Host "管理指令:" -ForegroundColor Gray
Write-Host "  nssm status tcm-server    # 查看狀態" -ForegroundColor Gray
Write-Host "  nssm restart tcm-server   # 重啟服務" -ForegroundColor Gray
Write-Host "  nssm stop tcm-server      # 停止服務" -ForegroundColor Gray
Write-Host "  nssm edit tcm-server      # GUI 編輯設定" -ForegroundColor Gray
Write-Host ""
Write-Host "即時查看日誌:" -ForegroundColor Gray
Write-Host "  Get-Content $LogPath\server.log -Wait" -ForegroundColor Gray
Write-Host ""
