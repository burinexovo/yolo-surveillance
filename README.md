# TCM Shop CCTV 監控系統

使用 YOLO11 進行人員偵測和追蹤的即時監控系統，提供即時串流、訪客計數、LINE 通知等功能。

## 功能特色

- **即時人員偵測** - 使用 YOLO11 模型進行高效能物件偵測
- **多目標追蹤** - 整合 ByteTrack 演算法追蹤個別訪客
- **區域偵測** - 自訂 ROI 區域判定訪客進出
- **訪客統計** - SQLite 持久化儲存，提供統計儀表板
- **即時通知** - LINE Messaging API 推播進店通知
- **WebRTC 串流** - 低延遲即時影像串流
- **事件錄影** - 自動錄製事件片段並上傳至 Cloudflare R2
- **音效警報** - 訪客進店時播放提示音

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

## 安裝與執行

### 環境需求

- Python 3.10+
- FFmpeg（錄影功能需要）
- 支援 RTSP 的網路攝影機

### 安裝

```bash
# 安裝依賴
pip install -r requirements.txt
```

### 執行

```bash
# 開發模式（支援熱重載）
uvicorn server:app --reload

# 正式環境
uvicorn server:app --host 0.0.0.0 --port 8000

# Cloudflare Tunnel（遠端存取）
cloudflared tunnel run tcm-backend
```

### 測試腳本

```bash
python scripts/test_rtsp.py    # 測試 RTSP 連線
python scripts/test_audio.py   # 測試音效警報
python scripts/test_line.py    # 測試 LINE 通知
python scripts/test_r2.py      # 測試 R2 上傳
```

## 環境變數設定

建立 `.env` 檔案並設定以下變數：

```env
# RTSP 攝影機
RTSP_URL=rtsp://username:password@camera-ip:port/stream

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_CHANNEL_SECRET=your_secret

# Cloudflare R2
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket

# 驗證 Token
AUTH_TOKEN=your_auth_token
```

## API 端點

| 路徑 | 說明 |
|------|------|
| `/watch?token=` | 即時串流頁面 |
| `/dashboard?token=` | 訪客統計儀表板 |
| `/api/dashboard/realtime` | 即時統計 API |
| `/api/dashboard/hourly` | 每小時統計 API |
| `/api/dashboard/daily` | 每日統計 API |
| `/api/dashboard/summary` | 摘要統計 API |
| `/alerts/*` | 使用者通知偏好設定 |
| `/shop-state` | 當前店鋪狀態查詢 |
| `/ws/signaling` | WebRTC 信令 WebSocket |

## 目錄結構

```
yolo11-detect/
├── server.py              # FastAPI 應用程式入口
├── modules/               # 核心模組
│   ├── yolo_runtime.py    # YOLO 推論、追蹤、區域判定
│   ├── shop_state_manager.py  # 訪客狀態管理
│   ├── visitor_db.py      # SQLite 訪客資料持久化
│   ├── settings.py        # Pydantic 設定管理
│   ├── signaling/         # WebRTC 信令處理
│   └── webrtc/            # WebRTC 串流實作
├── routers/               # API 路由
├── config/                # 設定檔
│   ├── users.json         # 使用者列表與通知設定
│   ├── botsort.yaml       # BotSort 追蹤器參數
│   └── bytetrack.yaml     # ByteTrack 追蹤器參數
├── utils/                 # 工具函式
│   └── constants.py       # ROI 區域座標定義
├── scripts/               # 測試與工具腳本
├── models/                # YOLO 模型檔案
├── web/                   # 前端靜態檔案
├── assets/                # 靜態資源與截圖
├── recordings/            # 錄影檔案（依日期分類）
├── logs/                  # 應用程式日誌
└── data/                  # SQLite 資料庫
```

## 授權

MIT License
