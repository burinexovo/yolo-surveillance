// web/watch.js
console.log("✅ watch.js VERSION = 2026-01-29 04:00");

// === 主題切換 ===
const THEME_KEY = "watch-theme";

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const theme = saved === "dark" ? "dark" : "light";
  applyTheme(theme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.classList.remove("light-theme", "dark-theme");
  document.documentElement.classList.add(theme + "-theme");
  document.body.classList.remove("light-theme", "dark-theme");
  document.body.classList.add(theme + "-theme");

  const btn = document.getElementById("themeToggle");
  if (btn) {
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }
  localStorage.setItem(THEME_KEY, theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
}

// === 1. 一些設定 ===
let hasVideo = false;
const params = new URLSearchParams(window.location.search);
let token = params.get("token") || localStorage.getItem("pin_token");

const API_BASE = "/api/dashboard";

// === PIN 登入模組 ===
const pinLogin = {
  els: {
    overlay: null,
    form: null,
    input: null,
    submit: null,
    error: null,
  },

  init() {
    this.els = {
      overlay: document.getElementById("loginOverlay"),
      form: document.getElementById("pinForm"),
      input: document.getElementById("pinInput"),
      submit: document.getElementById("pinSubmit"),
      error: document.getElementById("loginError"),
    };

    if (this.els.form) {
      this.els.form.addEventListener("submit", (e) => this.handleSubmit(e));
    }
  },

  show() {
    if (this.els.overlay) {
      this.els.overlay.classList.remove("hidden");
      this.els.input?.focus();
    }
  },

  hide() {
    if (this.els.overlay) {
      this.els.overlay.classList.add("hidden");
    }
  },

  showError(msg) {
    if (this.els.error) {
      this.els.error.textContent = msg;
      this.els.error.classList.remove("hidden");
    }
  },

  hideError() {
    if (this.els.error) {
      this.els.error.classList.add("hidden");
    }
  },

  async handleSubmit(e) {
    e.preventDefault();
    this.hideError();

    const pin = this.els.input.value.trim();
    if (!pin) {
      this.showError("請輸入 PIN 碼");
      return;
    }

    this.els.submit.disabled = true;
    this.els.submit.textContent = "驗證中...";

    try {
      const res = await fetch(`${API_BASE}/pin-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });

      const data = await res.json();

      if (data.success && data.token) {
        // 儲存 Token 到 sessionStorage
        localStorage.setItem("pin_token", data.token);
        token = data.token;

        // 隱藏登入畫面，初始化 WebRTC
        this.hide();
        initWatch();
      } else {
        this.showError(data.message || "登入失敗");
        this.els.input.value = "";
        this.els.input.focus();
      }
    } catch (err) {
      console.error("PIN login error:", err);
      this.showError("網路錯誤，請稍後再試");
    } finally {
      this.els.submit.disabled = false;
      this.els.submit.textContent = "登入";
    }
  },
};

// 根據 http/https 自動組成 ws/wss
const WS_URL =
  (location.protocol === "https:" ? "wss://" : "ws://") +
  location.host +
  `/ws?token=${encodeURIComponent(token)}`;

// 要看哪一支攝影機（之後可以從 URL query 拿）
const CAMERA_ID = "shop_cam_1";

// WebRTC STUN server
// const RTC_CONFIG = {
//   iceServers: [
//     {urls: 'stun:stun.l.google.com:19302'},
//     {urls: 'stun:stun1.l.google.com:19302'},
//     // {
// 		// 	urls: 'stun:stun.nextcloud.com:443'
// 		// },
// 		// {
// 		// 	urls: 'stun:openrelay.metered.ca:80'
// 		// },
//     {
// 			urls: 'turn:turn.yuanshoushen.com:3478',
// 			username: 'tcm-webrtc-cctv',
// 			credential: 'uArp-J3V7-XLWw4-i9Zi',
//     },
// 		// {
// 		// 	urls: 'turn:openrelay.metered.ca:80',
// 		// 	username: 'openrelayproject',
// 		// 	credential: 'openrelayproject',
// 		// },
// 		// {
// 		// 	urls: 'turn:openrelay.metered.ca:443',
// 		// 	username: 'openrelayproject',
// 		// 	credential: 'openrelayproject',
// 		// },
// 		// {
// 		// 	urls: 'turn:openrelay.metered.ca:443?transport=tcp',
// 		// 	username: 'openrelayproject',
// 		// 	credential: 'openrelayproject',
// 		// },
// 	],
// };
let RTC_CONFIG_CACHE = null;

async function getRtcConfigOrThrow() {
  // 可以選擇不快取，每次都抓（更保險但多一次請求）
  if (RTC_CONFIG_CACHE) return RTC_CONFIG_CACHE;

  const res = await fetch(`/auth/rtc-config?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`rtc-config failed: ${res.status}`);
  }

  const cfg = await res.json(); // 期望 { iceServers: [...] }
  if (!cfg || !Array.isArray(cfg.iceServers)) {
    throw new Error("rtc-config bad shape");
  }

  RTC_CONFIG_CACHE = cfg;
  return cfg;
}


// === 2. DOM 元件 ===

const videoEl = document.getElementById("remoteVideo");
const statusEl = document.getElementById("status");
const reconnectBtn = document.getElementById("reconnectBtn");
const loadingOverlay = document.getElementById("loadingOverlay");
console.log("loadingOverlay:", loadingOverlay);
console.log("loadingOverlay exists?", !!loadingOverlay);

window.__dbg = { loadingOverlay };

// === 3. 全域變數 ===

let pc = null; // RTCPeerConnection
let socket = null; // WebSocket

// === 4. 小工具 ===

function logStatus(msg) {
  console.log("[STATUS]", msg);
  statusEl.textContent = msg;
}

function disableWatchUI() {
  reconnectBtn.disabled = true;
  logStatus("連結已失效");
}

function showLoading(text = "連線中…") {
  if (!loadingOverlay) {
    console.warn("showLoading: loadingOverlay is null");
    return;
  }
  loadingOverlay.style.display = "flex";
  const t = loadingOverlay.querySelector(".loading-text");
  if (t) t.textContent = text;

  console.log("[LOADING] show:", text, "display=", getComputedStyle(loadingOverlay).display);
}

function hideLoading() {
  if (!loadingOverlay) {
    console.warn("hideLoading: loadingOverlay is null");
    return;
  }
  loadingOverlay.style.display = "none";
  console.log("[LOADING] hide, display=", getComputedStyle(loadingOverlay).display);
}

// === 5. 建立 / 重建 WebRTC PeerConnection ===

function createPeerConnection(rtcConfig) {
  if (pc) {
    pc.close();
    pc = null;
  }

  pc = new RTCPeerConnection(rtcConfig);

  // 收到遠端的 media track（就是 RTSP 轉過來的影像）
  pc.ontrack = (event) => {
    console.log("ontrack", event);

    // ✅ 有些瀏覽器 event.streams 會是空的
    let stream = event.streams && event.streams[0];

    if (!stream) {
      // 用 track 自己組一個 MediaStream（保證有）
      stream = new MediaStream([event.track]);
    }

    // 只要拿到有效 stream 就掛上去並關掉 loading
    if (videoEl.srcObject !== stream) {
      videoEl.srcObject = stream;
      // 某些瀏覽器需要呼叫 play
      videoEl.play?.().catch(() => {});
      hasVideo = true;       // ✅ 代表已經拿到畫面
      hideLoading();
      logStatus("已接收到影像流");
    }
  };
  // pc.ontrack = (event) => {
  //   console.log("ontrack", event);
  //   const [stream] = event.streams;
  //   if (videoEl.srcObject !== stream) {
  //     videoEl.srcObject = stream;
  //     hideLoading();
  //     logStatus("已接收到影像流");
  //   }
  // };

  pc.onicegatheringstatechange = () => {
    if (hasVideo) return; // ✅ 有畫面就別再顯示 loading

    if (pc.iceGatheringState === "gathering") {
      showLoading("收集 ICE 中…");
    } else if (pc.iceGatheringState === "complete") {
      showLoading("建立媒體通道中…");
    }
  };

  // 本地 ICE candidate 產生時，送給後端
  pc.onicecandidate = (event) => {
    console.log("📤 local ICE from browser:", event.candidate);
    if (event.candidate && socket && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: "ice",
          candidate: event.candidate,
        }),
      );
    } else if (!event.candidate) {
      console.log("📤 ICE gathering 完成");
    } else {
      console.log("呱呱")
    }
  };

  pc.onconnectionstatechange = () => {
    console.log("connection state:", pc.connectionState);
    if (pc.connectionState === "connected") {
      logStatus("WebRTC 已連線");
    } else if (pc.connectionState === "failed") {
      hideLoading();
      logStatus("WebRTC 連線失敗");
    }
  };
}

// === 6. 建立 WebSocket，負責 signaling ===

function connectWebSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.close();
  }

  logStatus("連線到伺服器中...");
  // logStatus(WS_URL)
  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    logStatus("WebSocket 已連線，請求即時畫面...");
    // 通知後端「我要看哪一支攝影機」
    const msg = {
      type: "watch", // 自訂協定，後端看到就會啟動 RTSP + WebRTC
      camera_id: CAMERA_ID,
    };
    socket.send(JSON.stringify(msg));
  };

  socket.onmessage = async (event) => {
    const msg = JSON.parse(event.data);
    console.log("收到訊息:", msg);

    // 這裡假設後端會直接把 pc.localDescription 原封不動 JSON 傳過來
    if (msg.type === "offer") {
      // 後端（Python Gateway）當 offerer，前端當 answerer
      logStatus("收到 offer，建立 WebRTC 回應...");
      if (!pc) {
        createPeerConnection();
      }

      await pc.setRemoteDescription(new RTCSessionDescription(msg));

      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // 回傳 answer 給伺服器
      socket.send(JSON.stringify(pc.localDescription));
      logStatus("已送出 answer，等待 ICE 建立連線...");
    } else if (msg.type === "ice") {
      // 後端丟來的 ICE candidate
      if (pc && msg.candidate) {
        try {
          await pc.addIceCandidate(msg.candidate);
        } catch (err) {
          console.error("addIceCandidate 失敗:", err);
        }
      }
    } else if (msg.type === "error") {
      logStatus(`伺服器錯誤：${msg.message}`);
    }
  };

  socket.onclose = () => {
    logStatus("WebSocket 已關閉");
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
    logStatus("WebSocket 發生錯誤");
  };
}

// 驗證 token
// async function verifyToken(token) {
//   const res = await fetch(`/auth/verify?token=${encodeURIComponent(token)}`);
//   if (!res.ok) {
//     throw new Error("token invalid");
//   }
//   return await res.json(); // { ok, uid, scope }
// }

// === 7. 初始化 WebRTC 連線 ===

async function initWatch() {
  try {
    showLoading("建立即時連線中…");
    const rtcConfig = await getRtcConfigOrThrow();
    console.log("rtc-config ok:", rtcConfig);
    // ✅ 到這裡，才開始 WebRTC / WebSocket
    createPeerConnection(rtcConfig);
    connectWebSocket();
  } catch (e) {
    console.error(e);
    // Token 無效，清除並顯示登入畫面
    localStorage.removeItem("pin_token");
    token = null;
    hideLoading();
    pinLogin.show();
  }
}

// === 8. 頁面載入時自動連線 ===

window.addEventListener("load", () => {
  // 初始化主題
  initTheme();
  document.getElementById("themeToggle")?.addEventListener("click", toggleTheme);

  // 初始化 PIN 登入
  pinLogin.init();

  if (token) {
    // 有 Token，嘗試連線
    initWatch();
  } else {
    // 沒有 Token，顯示 PIN 登入
    pinLogin.show();
  }
});

// === 9. 手動重新連線按鈕 ===

reconnectBtn.addEventListener("click", async () => {
  try {
    showLoading("重新連線中…");

    // ✅ 重連前再抓一次：順便驗 token + 避免 TURN 短期憑證過期
    RTC_CONFIG_CACHE = null; // 想保守就清掉，不保守可不清
    const rtcConfig = await getRtcConfigOrThrow();

    // 全部重建
    if (pc) { pc.close(); pc = null; }
    if (socket) { socket.close(); socket = null; }

    videoEl.srcObject = null;
    hasVideo = false;

    createPeerConnection(rtcConfig);
    connectWebSocket();

  } catch (e) {
    console.error(e);
    // Token 無效，清除並顯示登入畫面
    localStorage.removeItem("pin_token");
    token = null;
    hideLoading();
    pinLogin.show();
  }
});

// reconnectBtn.addEventListener("click", async () => {
//   try {
//     await verifyToken(token);
//   } catch (e) {
//     disableWatchUI();
//     hideLoading();
//     alert("觀看連結已失效或過期");
//     return;
//   }

//   // 簡單粗暴：全部重建
//   if (pc) { pc.close(); pc = null; }
//   if (socket) { socket.close(); socket = null; }

//   videoEl.srcObject = null;
//   createPeerConnection();
//   connectWebSocket();
// });

