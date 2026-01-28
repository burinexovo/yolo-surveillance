# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

TCM Shop CCTV 監控系統 - 使用 YOLO11 進行人員偵測和追蹤，提供即時串流、訪客計數、LINE 通知等功能。

## 常用指令

```bash
# 安裝依賴
pip install -r requirements.txt

# 開發模式（支援熱重載）
uvicorn server:app --reload

# 正式環境
uvicorn server:app --host 0.0.0.0 --port 8000

# Cloudflare Tunnel（遠端存取）
cloudflared tunnel run tcm-backend
```

測試腳本位於 `scripts/` 目錄：
```bash
python scripts/test_rtsp.py    # 測試 RTSP 連線
python scripts/test_audio.py   # 測試音效警報
python scripts/test_line.py    # 測試 LINE 通知
python scripts/test_r2.py      # 測試 R2 上傳
```

## 系統架構

```
輸入層 (RTSPReader)
    ↓
偵測追蹤層 (YoloRuntime + ByteTrack)
    ↓
    ├─→ 狀態管理層 (ShopStateManager + VisitorDB/SQLite)
    ├─→ 通知層 (EventWorker → LINE + 音效 + R2)
    ├─→ 錄影層 (VideoRecorder + RecordingWorker)
    └─→ 串流層 (WebRTCGateway → 瀏覽器)
```

**核心資料流程**：
1. `RTSPReader` 持續讀取攝影機畫面
2. `YoloRuntime._loop()` 每幀執行 YOLO11 推論
3. 區域偵測（門口 → 店內）觸發 `ShopStateManager.record_entry()`
4. 同步寫入 SQLite (`VisitorDB`) + 推送 LINE 通知

## 主要模組

| 模組 | 職責 |
|------|------|
| `modules/yolo_runtime.py` | 主協調器：YOLO 推論、追蹤、區域判定 |
| `modules/shop_state_manager.py` | 執行緒安全的訪客狀態管理 |
| `modules/visitor_db.py` | SQLite 訪客資料持久化 |
| `modules/settings.py` | Pydantic 設定管理（讀取 .env） |
| `modules/signaling/` | WebRTC 信令處理 |
| `modules/webrtc/` | WebRTC 串流實作 |

## API 端點

| 路徑 | 說明 |
|------|------|
| `/watch?token=` | 即時串流頁面 |
| `/dashboard?token=` | 訪客統計儀表板 |
| `/api/dashboard/*` | 統計 API（realtime, hourly, daily, summary） |
| `/alerts/*` | 使用者通知偏好設定 |
| `/shop-state` | 當前店鋪狀態查詢 |
| `/ws/signaling` | WebRTC 信令 WebSocket |

## 設定檔

- `.env` - 環境變數（LINE API、R2、RTSP URL 等）
- `config/users.json` - 使用者列表與通知設定
- `config/botsort.yaml`, `config/bytetrack.yaml` - 追蹤器參數
- `utils/constants.py` - ROI 區域座標（門口/店內多邊形）

## 輸出目錄

- `recordings/` - 錄影檔案（依日期分類）
- `logs/app.log` - 應用程式日誌
- `data/visitors.db` - SQLite 訪客統計資料庫
- `assets/screenshots/` - 事件截圖

## 注意事項

- 中文註解為主
- 使用 Cloudflare Tunnel 進行遠端存取（見 `docs/cloudflare_tunnel_deploy.md`）
- ROI 區域調整可用 `scripts/get_roi_position.py` 互動式工具
