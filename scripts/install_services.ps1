# === TCM Service Installation Script (PowerShell) ===
# Run as Administrator
# Usage: Right-click PowerShell -> Run as Administrator -> cd to project -> .\scripts\install_services.ps1

param(
    [string]$ProjectPath = "D:\Code\yolo-surveillance",
    [string]$LogPath = "D:\tcm-logs"
)

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Error: Please run this script as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as Administrator" -ForegroundColor Yellow
    exit 1
}

# Check if NSSM is installed
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "Error: NSSM not found. Please install it first." -ForegroundColor Red
    Write-Host "Install: winget install nssm" -ForegroundColor Yellow
    Write-Host "Or download from: https://nssm.cc/download" -ForegroundColor Yellow
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TCM Service Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project Path: $ProjectPath" -ForegroundColor Gray
Write-Host "Log Path: $LogPath" -ForegroundColor Gray
Write-Host ""

# Create log directory
if (-not (Test-Path $LogPath)) {
    Write-Host "Creating log directory: $LogPath" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

# Script paths
$serverScript = Join-Path $ProjectPath "scripts\start_server.bat"
$tunnelScript = Join-Path $ProjectPath "scripts\start_tunnel.bat"

# Check if scripts exist
if (-not (Test-Path $serverScript)) {
    Write-Host "Error: $serverScript not found" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $tunnelScript)) {
    Write-Host "Error: $tunnelScript not found" -ForegroundColor Red
    exit 1
}

# === Install tcm-server service ===
Write-Host "[1/2] Installing tcm-server service..." -ForegroundColor Green

# Remove existing service if exists
$existingServer = nssm status tcm-server 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Removing existing tcm-server service..." -ForegroundColor Yellow
    nssm stop tcm-server 2>$null
    nssm remove tcm-server confirm 2>$null
}

# Install service
nssm install tcm-server $serverScript
nssm set tcm-server AppDirectory $ProjectPath
nssm set tcm-server AppStdout "$LogPath\server.log"
nssm set tcm-server AppStderr "$LogPath\server_err.log"
nssm set tcm-server AppStdoutCreationDisposition 4
nssm set tcm-server AppStderrCreationDisposition 4
nssm set tcm-server AppRestartDelay 5000
nssm set tcm-server Description "TCM Shop CCTV Server (uvicorn)"
nssm set tcm-server Start SERVICE_AUTO_START

Write-Host "  tcm-server installed" -ForegroundColor Green

# === Install tcm-tunnel service ===
Write-Host "[2/2] Installing tcm-tunnel service..." -ForegroundColor Green

# Remove existing service if exists
$existingTunnel = nssm status tcm-tunnel 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Removing existing tcm-tunnel service..." -ForegroundColor Yellow
    nssm stop tcm-tunnel 2>$null
    nssm remove tcm-tunnel confirm 2>$null
}

# Install service
nssm install tcm-tunnel $tunnelScript
nssm set tcm-tunnel AppStdout "$LogPath\tunnel.log"
nssm set tcm-tunnel AppStderr "$LogPath\tunnel_err.log"
nssm set tcm-tunnel AppStdoutCreationDisposition 4
nssm set tcm-tunnel AppStderrCreationDisposition 4
nssm set tcm-tunnel AppRestartDelay 5000
nssm set tcm-tunnel Description "TCM Cloudflare Tunnel"
nssm set tcm-tunnel Start SERVICE_AUTO_START

Write-Host "  tcm-tunnel installed" -ForegroundColor Green

# === Start services ===
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "Starting tcm-server..." -ForegroundColor Yellow
nssm start tcm-server
Start-Sleep -Seconds 3

Write-Host "Starting tcm-tunnel..." -ForegroundColor Yellow
nssm start tcm-tunnel
Start-Sleep -Seconds 2

# === Show status ===
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "tcm-server:" -ForegroundColor White
nssm status tcm-server

Write-Host ""
Write-Host "tcm-tunnel:" -ForegroundColor White
nssm status tcm-tunnel

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Log locations:" -ForegroundColor Gray
Write-Host "  Server: $LogPath\server.log" -ForegroundColor Gray
Write-Host "  Tunnel: $LogPath\tunnel.log" -ForegroundColor Gray
Write-Host ""
Write-Host "Management commands:" -ForegroundColor Gray
Write-Host "  nssm status tcm-server    # Check status" -ForegroundColor Gray
Write-Host "  nssm restart tcm-server   # Restart service" -ForegroundColor Gray
Write-Host "  nssm stop tcm-server      # Stop service" -ForegroundColor Gray
Write-Host "  nssm edit tcm-server      # GUI settings" -ForegroundColor Gray
Write-Host ""
Write-Host "View logs in real-time:" -ForegroundColor Gray
Write-Host "  Get-Content $LogPath\server.log -Wait" -ForegroundColor Gray
Write-Host ""
