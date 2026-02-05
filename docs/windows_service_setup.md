# Windows 後台服務設定指南

本文件說明如何使用 NSSM 將 TCM Server 和 Cloudflare Tunnel 設定為 Windows 服務，實現穩定的後台執行。

## 目錄

- [前置需求](#前置需求)
- [快速安裝](#快速安裝)
- [手動安裝](#手動安裝)
- [日常維護](#日常維護)
- [疑難排解](#疑難排解)
- [移除服務](#移除服務)

---

## 前置需求

### 1. 安裝 NSSM

```powershell
# 方法一：使用 winget（推薦）
winget install nssm

# 方法二：手動下載
# 從 https://nssm.cc/download 下載，解壓後將 nssm.exe 加入 PATH
```

### 2. 確認 Cloudflare Tunnel 已設定

```powershell
# 確認 cloudflared 已安裝且 tunnel 已建立
cloudflared tunnel list
```

---

## 快速安裝

### 步驟 1：修改啟動腳本路徑

編輯 `scripts/start_server.bat`，將 `PROJECT_PATH` 替換為你的專案實際路徑：

```batch
cd /d D:\Code\yolo11-detect  # 替換為你的路徑
```

### 步驟 2：執行安裝腳本

1. 右鍵點擊 PowerShell → **以系統管理員身份執行**
2. 切換到專案目錄：
   ```powershell
   cd D:\Code\yolo11-detect
   ```
3. 執行安裝腳本（修改參數為你的路徑）：
   ```powershell
   .\scripts\install_services.ps1 -ProjectPath "D:\Code\yolo11-detect" -LogPath "D:\tcm-logs"
   ```

### 步驟 3：驗證安裝

```powershell
# 查看服務狀態
nssm status tcm-server
nssm status tcm-tunnel

# 確認網頁可存取
# 本地: http://localhost:8000
# 遠端: 你的 Cloudflare Tunnel URL
```

---

## 手動安裝

如果自動安裝腳本無法使用，可手動執行以下步驟：

### 1. 註冊服務

```powershell
# 以管理員身份執行 PowerShell

# 安裝 tcm-server
nssm install tcm-server "D:\Code\yolo11-detect\scripts\start_server.bat"
nssm set tcm-server AppDirectory "D:\Code\yolo11-detect"
nssm set tcm-server AppRestartDelay 5000
nssm set tcm-server Start SERVICE_AUTO_START

# 安裝 tcm-tunnel
nssm install tcm-tunnel "D:\Code\yolo11-detect\scripts\start_tunnel.bat"
nssm set tcm-tunnel AppRestartDelay 5000
nssm set tcm-tunnel Start SERVICE_AUTO_START
```

### 2. 設定日誌輸出（可選但建議）

```powershell
# 建立日誌目錄
mkdir D:\tcm-logs

# 設定 tcm-server 日誌
nssm set tcm-server AppStdout "D:\tcm-logs\server.log"
nssm set tcm-server AppStderr "D:\tcm-logs\server_err.log"
nssm set tcm-server AppStdoutCreationDisposition 4  # 追加模式
nssm set tcm-server AppStderrCreationDisposition 4

# 設定 tcm-tunnel 日誌
nssm set tcm-tunnel AppStdout "D:\tcm-logs\tunnel.log"
nssm set tcm-tunnel AppStderr "D:\tcm-logs\tunnel_err.log"
nssm set tcm-tunnel AppStdoutCreationDisposition 4
nssm set tcm-tunnel AppStderrCreationDisposition 4
```

### 3. 啟動服務

```powershell
nssm start tcm-server
nssm start tcm-tunnel
```

---

## 日常維護

### 查看服務狀態

```powershell
nssm status tcm-server
nssm status tcm-tunnel

# 或使用 Windows 服務管理介面
services.msc
```

### 重啟服務（修改程式碼後）

```powershell
# 方法一：使用 NSSM 指令
nssm restart tcm-server

# 方法二：使用一鍵重啟腳本（需以管理員執行）
.\scripts\restart_services.bat
```

### 查看即時日誌

```powershell
# 查看 server 日誌（類似 Linux 的 tail -f）
Get-Content D:\tcm-logs\server.log -Wait

# 查看 tunnel 日誌
Get-Content D:\tcm-logs\tunnel.log -Wait

# 查看錯誤日誌
Get-Content D:\tcm-logs\server_err.log -Wait
```

### 使用 GUI 編輯服務設定

```powershell
nssm edit tcm-server
```

### 開發模式 vs 生產模式

| 情境 | 建議 |
|------|------|
| 開發中 | 停止服務，直接在 terminal 執行 `uvicorn server:app --reload` |
| 部署後 | 啟動 NSSM 服務 |
| 修改程式碼後 | `nssm restart tcm-server` |

---

## 疑難排解

### 服務無法啟動

1. **檢查日誌**
   ```powershell
   Get-Content D:\tcm-logs\server_err.log
   ```

2. **手動執行腳本確認**
   ```powershell
   # 直接執行看是否有錯誤
   D:\Code\yolo11-detect\scripts\start_server.bat
   ```

3. **確認 Conda 環境路徑正確**
   編輯 `scripts/start_server.bat`，確認 Conda 路徑：
   ```batch
   call C:\Users\User\anaconda3\Scripts\activate.bat yolo-surveillance
   ```

### 端口被佔用

```powershell
# 查看 8000 端口佔用
netstat -ano | findstr :8000

# 終止佔用的程序
taskkill /PID <PID> /F
```

### 服務狀態顯示 Running 但無法存取

1. 檢查防火牆設定
2. 確認 `--host 0.0.0.0` 參數存在
3. 查看日誌確認 uvicorn 是否正常啟動

### Cloudflare Tunnel 連線問題

```powershell
# 確認 tunnel 狀態
cloudflared tunnel info tcm-backend

# 查看 tunnel 日誌
Get-Content D:\tcm-logs\tunnel.log -Wait
```

---

## 移除服務

### 使用腳本移除

```powershell
# 以管理員身份執行
.\scripts\uninstall_services.ps1
```

### 手動移除

```powershell
# 停止服務
nssm stop tcm-server
nssm stop tcm-tunnel

# 移除服務
nssm remove tcm-server confirm
nssm remove tcm-tunnel confirm
```

---

## 常用指令速查表

| 操作 | 指令 |
|------|------|
| 查看狀態 | `nssm status tcm-server` |
| 啟動服務 | `nssm start tcm-server` |
| 停止服務 | `nssm stop tcm-server` |
| 重啟服務 | `nssm restart tcm-server` |
| 編輯設定 | `nssm edit tcm-server` |
| 移除服務 | `nssm remove tcm-server confirm` |
| 查看即時日誌 | `Get-Content D:\tcm-logs\server.log -Wait` |
| Windows 服務管理 | `services.msc` |

---

## Tips 使用步驟

1. 安裝 NSSM
winget install nssm
2. 修改 scripts/start_server.bat 中的路徑：
   - PROJECT_PATH → 你的專案實際路徑
   - Conda 路徑（如需要）
3. 以管理員身份執行安裝腳本
.\scripts\install_services.ps1 -ProjectPath "D:\Code\yolo11-detect" -LogPath "D:\tcm-logs"
4. 日常維護
   - 修改程式碼後：nssm restart tcm-server
   - 查看日誌：Get-Content D:\tcm-logs\server.log -Wait

---
## 備選方案：PM2

如果已有 Node.js 環境，可考慮使用 PM2：

```powershell
# 安裝
npm install -g pm2
npm install -g pm2-windows-startup

# 建立設定檔 ecosystem.config.js
pm2 start ecosystem.config.js

# 設定開機自啟
pm2 save
pm2-startup install
```

詳見 PM2 官方文件：https://pm2.keymetrics.io/docs/usage/startup/
