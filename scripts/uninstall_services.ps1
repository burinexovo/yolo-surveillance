# === TCM Service Uninstall Script (PowerShell) ===
# Run as Administrator

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Error: Please run this script as Administrator" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TCM Service Uninstaller" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Confirm
$confirm = Read-Host "Are you sure you want to remove tcm-server and tcm-tunnel services? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Cancelled" -ForegroundColor Yellow
    exit 0
}

# Stop and remove tcm-server
Write-Host "[1/2] Removing tcm-server..." -ForegroundColor Yellow
$status = nssm status tcm-server 2>$null
if ($LASTEXITCODE -eq 0) {
    nssm stop tcm-server 2>$null
    Start-Sleep -Seconds 2
    nssm remove tcm-server confirm
    Write-Host "  tcm-server removed" -ForegroundColor Green
} else {
    Write-Host "  tcm-server service not found, skipping" -ForegroundColor Gray
}

# Stop and remove tcm-tunnel
Write-Host "[2/2] Removing tcm-tunnel..." -ForegroundColor Yellow
$status = nssm status tcm-tunnel 2>$null
if ($LASTEXITCODE -eq 0) {
    nssm stop tcm-tunnel 2>$null
    Start-Sleep -Seconds 2
    nssm remove tcm-tunnel confirm
    Write-Host "  tcm-tunnel removed" -ForegroundColor Green
} else {
    Write-Host "  tcm-tunnel service not found, skipping" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Services Removed" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Log files were not deleted. To clean up, manually delete D:\tcm-logs" -ForegroundColor Gray
Write-Host ""
