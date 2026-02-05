# === TCM 服務移除腳本 (PowerShell) ===
# 需要以管理員身份執行

# 檢查是否以管理員身份執行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "錯誤: 請以管理員身份執行此腳本" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TCM 服務移除程式" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 確認
$confirm = Read-Host "確定要移除 tcm-server 和 tcm-tunnel 服務嗎? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "已取消" -ForegroundColor Yellow
    exit 0
}

# 停止並移除 tcm-server
Write-Host "[1/2] 移除 tcm-server..." -ForegroundColor Yellow
$status = nssm status tcm-server 2>$null
if ($LASTEXITCODE -eq 0) {
    nssm stop tcm-server 2>$null
    Start-Sleep -Seconds 2
    nssm remove tcm-server confirm
    Write-Host "  tcm-server 已移除" -ForegroundColor Green
} else {
    Write-Host "  tcm-server 服務不存在，跳過" -ForegroundColor Gray
}

# 停止並移除 tcm-tunnel
Write-Host "[2/2] 移除 tcm-tunnel..." -ForegroundColor Yellow
$status = nssm status tcm-tunnel 2>$null
if ($LASTEXITCODE -eq 0) {
    nssm stop tcm-tunnel 2>$null
    Start-Sleep -Seconds 2
    nssm remove tcm-tunnel confirm
    Write-Host "  tcm-tunnel 已移除" -ForegroundColor Green
} else {
    Write-Host "  tcm-tunnel 服務不存在，跳過" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  服務已移除" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "注意: 日誌檔案未刪除，如需清理請手動刪除 D:\tcm-logs" -ForegroundColor Gray
Write-Host ""
