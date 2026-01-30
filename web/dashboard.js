// web/dashboard.js
console.log("✅ dashboard.js VERSION = 2026-01-31 14:00");
console.log("Dashboard loaded");

// === 設定 ===
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

        this.els.form.addEventListener("submit", (e) => this.handleSubmit(e));
    },

    show() {
        this.els.overlay.classList.remove("hidden");
        this.els.input.focus();
    },

    hide() {
        this.els.overlay.classList.add("hidden");
    },

    showError(msg) {
        this.els.error.textContent = msg;
        this.els.error.classList.remove("hidden");
    },

    hideError() {
        this.els.error.classList.add("hidden");
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

                // 隱藏登入畫面，初始化 Dashboard
                this.hide();
                initDashboard();
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

// === DOM 元素 ===
const elements = {
    insideCount: document.getElementById("insideCount"),
    todayVisits: document.getElementById("todayVisits"),
    lastEntryTime: document.getElementById("lastEntryTime"),
    systemStatus: document.getElementById("systemStatus"),
    totalVisits: document.getElementById("totalVisits"),
    avgDailyVisits: document.getElementById("avgDailyVisits"),
    peakDay: document.getElementById("peakDay"),
    peakHour: document.getElementById("peakHour"),
    lastUpdate: document.getElementById("lastUpdate"),
    rangeSelect: document.getElementById("rangeSelect"),
    refreshBtn: document.getElementById("refreshBtn"),
};

// === Chart.js 實例 ===
let hourlyChart = null;
let dailyChart = null;

// === 主題切換 ===
const THEME_KEY = "dashboard-theme";

function getChartColors(theme) {
    return theme === "dark"
        ? { grid: "#333", text: "#999" }
        : { grid: "#ddd", text: "#666" };
}

function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const theme = saved === "dark" ? "dark" : "light";
    applyTheme(theme, false);
}

function applyTheme(theme, updateCharts = true) {
    // 同時設定 html 和 body 的 attribute/class，確保 Safari 相容性
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.classList.remove("light-theme", "dark-theme");
    document.documentElement.classList.add(theme + "-theme");

    // Safari 需要在 body 上也設定 class 才能正確繼承 CSS 變數
    document.body.classList.remove("light-theme", "dark-theme");
    document.body.classList.add(theme + "-theme");

    const btn = document.getElementById("themeToggle");
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
    localStorage.setItem(THEME_KEY, theme);

    if (updateCharts) {
        updateChartColors(theme);
    }
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    applyTheme(current === "dark" ? "light" : "dark");
}

function updateChartColors(theme) {
    const colors = getChartColors(theme);

    if (hourlyChart) {
        hourlyChart.options.scales.x.ticks.color = colors.text;
        hourlyChart.options.scales.x.grid.color = colors.grid;
        hourlyChart.options.scales.y.ticks.color = colors.text;
        hourlyChart.options.scales.y.grid.color = colors.grid;
        hourlyChart.update();
    }

    if (dailyChart) {
        dailyChart.options.scales.x.ticks.color = colors.text;
        dailyChart.options.scales.x.grid.color = colors.grid;
        dailyChart.options.scales.y.ticks.color = colors.text;
        dailyChart.options.scales.y.grid.color = colors.grid;
        dailyChart.update();
    }
}

// === 驗證函式 ===
async function verifyDashboardAuth() {
    const res = await fetch(`/auth/dashboard?token=${encodeURIComponent(token)}`);
    if (!res.ok) {
        throw new Error("auth failed");
    }
    return await res.json();
}

function disableDashboardUI() {
    elements.rangeSelect.disabled = true;
    elements.refreshBtn.disabled = true;
    elements.systemStatus.textContent = "驗證失敗";
}

// === API 呼叫 ===
async function fetchAPI(endpoint, params = {}) {
    const url = new URL(API_BASE + endpoint, window.location.origin);
    url.searchParams.set("token", token);

    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) {
            url.searchParams.set(k, v);
        }
    });

    const res = await fetch(url);
    if (!res.ok) {
        if (res.status === 403) {
            alert("憑證已失效，請重新取得連結");
            throw new Error("token invalid");
        }
        throw new Error(`API error: ${res.status}`);
    }
    return res.json();
}

// === 更新即時狀態 ===
async function updateRealtime() {
    try {
        const data = await fetchAPI("/realtime");

        elements.insideCount.textContent = data.inside_count;
        elements.todayVisits.textContent = data.today_visits;
        elements.lastEntryTime.textContent = data.last_entry_ts
            ? new Date(data.last_entry_ts).toLocaleTimeString("zh-TW")
            : "尚無資料";
        elements.systemStatus.textContent = data.system_status === "running"
            ? "正常運作"
            : "異常";

    } catch (e) {
        console.error("updateRealtime error:", e);
    }
}

// === 更新每小時分布圖表 ===
async function updateHourlyChart() {
    try {
        const data = await fetchAPI("/hourly");

        const labels = data.hourly_data.map(d => `${d.hour}:00`);
        const values = data.hourly_data.map(d => d.count);

        if (hourlyChart) {
            hourlyChart.data.labels = labels;
            hourlyChart.data.datasets[0].data = values;
            hourlyChart.update();
        } else {
            const theme = document.documentElement.getAttribute("data-theme") || "light";
            const colors = getChartColors(theme);
            const ctx = document.getElementById("hourlyChart").getContext("2d");
            hourlyChart = new Chart(ctx, {
                type: "bar",
                data: {
                    labels,
                    datasets: [{
                        label: "訪客數",
                        data: values,
                        backgroundColor: "rgba(59, 130, 246, 0.7)",
                        borderColor: "rgba(59, 130, 246, 1)",
                        borderWidth: 1,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: colors.text },
                            grid: { color: colors.grid },
                        },
                        x: {
                            ticks: { color: colors.text },
                            grid: { color: colors.grid },
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
    } catch (e) {
        console.error("updateHourlyChart error:", e);
    }
}

// === 更新每日趨勢圖表 ===
async function updateDailyChart() {
    const range = elements.rangeSelect.value;

    try {
        const data = await fetchAPI("/daily", { range });

        const labels = data.daily_data.map(d => {
            const date = new Date(d.date);
            return `${date.getMonth() + 1}/${date.getDate()}`;
        });
        const values = data.daily_data.map(d => d.count);

        if (dailyChart) {
            dailyChart.data.labels = labels;
            dailyChart.data.datasets[0].data = values;
            dailyChart.update();
        } else {
            const theme = document.documentElement.getAttribute("data-theme") || "light";
            const colors = getChartColors(theme);
            const ctx = document.getElementById("dailyChart").getContext("2d");
            dailyChart = new Chart(ctx, {
                type: "line",
                data: {
                    labels,
                    datasets: [{
                        label: "訪客數",
                        data: values,
                        borderColor: "rgba(34, 197, 94, 1)",
                        backgroundColor: "rgba(34, 197, 94, 0.1)",
                        fill: true,
                        tension: 0.3,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: colors.text },
                            grid: { color: colors.grid },
                        },
                        x: {
                            ticks: {
                                color: colors.text,
                                maxTicksLimit: 15,
                            },
                            grid: { color: colors.grid },
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
    } catch (e) {
        console.error("updateDailyChart error:", e);
    }
}

// === 更新統計摘要 ===
async function updateSummary() {
    const range = elements.rangeSelect.value;

    try {
        const data = await fetchAPI("/summary", { range });

        elements.totalVisits.textContent = data.total_visits.toLocaleString();
        elements.avgDailyVisits.textContent = data.avg_daily_visits.toFixed(1);

        if (data.peak_day) {
            const peakDate = new Date(data.peak_day.date);
            elements.peakDay.textContent =
                `${peakDate.getMonth() + 1}/${peakDate.getDate()} (${data.peak_day.count}人)`;
        } else {
            elements.peakDay.textContent = "-";
        }

        if (data.peak_hour) {
            elements.peakHour.textContent =
                `${data.peak_hour.hour}:00 (平均${data.peak_hour.avg_count.toFixed(1)}人)`;
        } else {
            elements.peakHour.textContent = "-";
        }

    } catch (e) {
        console.error("updateSummary error:", e);
    }
}

// === 更新全部 ===
async function refreshAll() {
    const now = new Date();
    elements.lastUpdate.textContent = now.toLocaleTimeString("zh-TW");

    await Promise.all([
        updateRealtime(),
        updateHourlyChart(),
        updateDailyChart(),
        updateSummary(),
        recording.loadDate(),  // 也更新錄影列表
    ]);
}

// === 事件綁定 ===
elements.rangeSelect.addEventListener("change", () => {
    updateDailyChart();
    updateSummary();
});

elements.refreshBtn.addEventListener("click", refreshAll);

document.getElementById("themeToggle").addEventListener("click", toggleTheme);

// 即時畫面按鈕 - 開新分頁（繼承當前主題）
document.getElementById("watchBtn")?.addEventListener("click", () => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
    window.open(`/watch?theme=${currentTheme}`, "_blank");
});

// === 錄影回放模組 ===
const recording = {
    recordings: [],
    events: [],
    currentIndex: -1,
    currentCameraId: "cam1",
    hls: null,  // HLS.js 實例
    initialized: false,  // 是否已初始化

    // DOM 元素
    els: {
        cameraSelect: null,
        dateInput: null,
        summary: null,
        timeline: null,
        video: null,
        clipInfo: null,
        prevBtn: null,
        nextBtn: null,
        clipsList: null,
    },

    async init() {
        this.els = {
            cameraSelect: document.getElementById("recordingCamera"),
            dateInput: document.getElementById("recordingDate"),
            summary: document.getElementById("recordingSummary"),
            timeline: document.getElementById("timelineTrack"),
            video: document.getElementById("videoPlayer"),
            clipInfo: document.getElementById("clipInfo"),
            prevBtn: document.getElementById("prevClip"),
            nextBtn: document.getElementById("nextClip"),
            clipsList: document.getElementById("clipsList"),
        };

        // 設定日期選擇器預設值為今天
        const today = new Date().toISOString().split("T")[0];
        this.els.dateInput.value = today;

        // 綁定事件
        this.els.cameraSelect.addEventListener("change", () => {
            this.currentCameraId = this.els.cameraSelect.value;
            this.loadDate();
        });
        this.els.dateInput.addEventListener("change", () => this.loadDate());
        this.els.prevBtn.addEventListener("click", () => this.playPrev());
        this.els.nextBtn.addEventListener("click", () => this.playNext());
        this.els.video.addEventListener("ended", () => this.onVideoEnded());

        // 載入攝影機列表
        await this.loadCameras();

        // 標記為已初始化
        this.initialized = true;

        // 載入今天的錄影
        this.loadDate();
    },

    async loadCameras() {
        try {
            // 注意：cameras API 在 /api/cameras，不在 /api/dashboard 下
            const url = new URL("/api/cameras", window.location.origin);
            url.searchParams.set("token", token);
            const response = await fetch(url);
            if (!response.ok) throw new Error("Failed to load cameras");
            const res = await response.json();

            this.els.cameraSelect.innerHTML = "";

            res.cameras.forEach((cam) => {
                const opt = document.createElement("option");
                opt.value = cam.id;
                opt.textContent = cam.label;
                if (cam.id === this.currentCameraId) opt.selected = true;
                this.els.cameraSelect.appendChild(opt);
            });

            // 如果目前選擇的攝影機不在列表中，選擇第一個
            if (res.cameras.length > 0 && !res.cameras.find(c => c.id === this.currentCameraId)) {
                this.currentCameraId = res.cameras[0].id;
                this.els.cameraSelect.value = this.currentCameraId;
            }
        } catch (e) {
            console.error("loadCameras error:", e);
            this.els.cameraSelect.innerHTML = '<option value="cam1">預設攝影機</option>';
        }
    },

    async loadDate() {
        // 防止在初始化前被調用
        if (!this.initialized || !this.els.dateInput) return;

        const dateValue = this.els.dateInput.value;
        if (!dateValue) return;

        const dateStr = dateValue.replace(/-/g, "");

        try {
            // 並行載入錄影列表和事件
            const [recRes, evtRes] = await Promise.all([
                fetchAPI("/recordings", { date: dateStr, camera_id: this.currentCameraId }),
                fetchAPI("/events", { date: dateStr }),
            ]);

            this.recordings = recRes.recordings || [];
            this.events = evtRes.events || [];
            this.currentIndex = -1;

            // 更新摘要
            if (this.recordings.length > 0) {
                this.els.summary.textContent =
                    `${this.recordings.length} 段錄影，共 ${recRes.total_size_mb} MB`;
            } else {
                this.els.summary.textContent = "該日期無錄影";
            }

            // 渲染時間線和片段列表
            this.renderTimeline();
            this.renderClipsList();
            this.updateNavButtons();

            // 預設選擇最新的可播放錄影（不自動播放）
            if (this.recordings.length > 0) {
                const latestIndex = this.recordings.length - 1;
                this.playClip(latestIndex, false);
            } else {
                // 無錄影時重設播放器
                this.els.video.src = "";
                this.els.clipInfo.textContent = "該日期無錄影";
            }

        } catch (e) {
            console.error("loadDate error:", e);
            this.els.summary.textContent = "載入失敗";
        }
    },

    renderTimeline() {
        this.els.timeline.innerHTML = "";

        // 渲染錄影片段
        this.recordings.forEach((rec, idx) => {
            const startTime = new Date(rec.start_time);
            const startMinutes = startTime.getHours() * 60 + startTime.getMinutes();
            const duration = rec.duration_seconds / 60; // 轉換為分鐘

            // 計算位置和寬度 (一天 1440 分鐘)
            const left = (startMinutes / 1440) * 100;
            const width = Math.max((duration / 1440) * 100, 0.2); // 最小寬度

            const clip = document.createElement("div");
            clip.className = "timeline-clip";
            clip.style.left = `${left}%`;
            clip.style.width = `${width}%`;
            clip.title = `${startTime.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" })}`;
            clip.dataset.index = idx;
            clip.addEventListener("click", () => this.playClip(idx));

            this.els.timeline.appendChild(clip);
        });

        // 渲染事件標記
        this.events.forEach((evt) => {
            const evtTime = new Date(evt.entry_time);
            const evtMinutes = evtTime.getHours() * 60 + evtTime.getMinutes();
            const left = (evtMinutes / 1440) * 100;

            const marker = document.createElement("div");
            marker.className = "timeline-event";
            marker.style.left = `${left}%`;
            marker.dataset.time = evtTime.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
            marker.dataset.eventId = evt.id;
            marker.title = `訪客入店: ${marker.dataset.time}`;
            marker.addEventListener("click", () => this.jumpToEvent(evt));

            this.els.timeline.appendChild(marker);
        });
    },

    renderClipsList() {
        this.els.clipsList.innerHTML = "";

        if (this.recordings.length === 0) {
            this.els.clipsList.innerHTML = '<div class="no-clips">該日期無錄影</div>';
            return;
        }

        this.recordings.forEach((rec, idx) => {
            const startTime = new Date(rec.start_time);
            const timeStr = startTime.toLocaleTimeString("zh-TW", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });

            const item = document.createElement("div");
            item.className = "clip-item";
            item.textContent = timeStr;
            item.dataset.index = idx;
            item.addEventListener("click", () => this.playClip(idx));

            this.els.clipsList.appendChild(item);
        });
    },

    playClip(index, autoPlay = true) {
        if (index < 0 || index >= this.recordings.length) return;

        const rec = this.recordings[index];
        const dateStr = this.els.dateInput.value.replace(/-/g, "");

        // 清理之前的 HLS 實例
        if (this.hls) {
            this.hls.destroy();
            this.hls = null;
        }

        // 優先使用 HLS（如果可用且瀏覽器支援）
        if (rec.hls_available && Hls.isSupported()) {
            const segmentName = rec.filename.replace(".mp4", "");
            const hlsUrl = `${API_BASE}/recordings/${this.currentCameraId}/${dateStr}/${segmentName}/playlist.m3u8?token=${encodeURIComponent(token)}`;

            this.hls = new Hls({
                // 優化載入速度
                maxBufferLength: 10,        // 最多緩衝 10 秒
                maxMaxBufferLength: 30,     // 最大緩衝 30 秒
                startLevel: 0,              // 立即從第一個品質開始
                maxLoadingDelay: 4,         // 最大載入延遲 4 秒
                lowLatencyMode: true,       // 低延遲模式
                xhrSetup: (xhr, url) => {
                    // 確保所有 HLS 請求都帶有 token
                    if (!url.includes("token=")) {
                        const separator = url.includes("?") ? "&" : "?";
                        const newUrl = `${url}${separator}token=${encodeURIComponent(token)}`;
                        xhr.open("GET", newUrl, true);
                    }
                }
            });

            // 錯誤處理
            this.hls.on(Hls.Events.ERROR, (event, data) => {
                console.error("HLS 錯誤:", data.type, data.details, data);
                if (data.fatal) {
                    console.error("HLS 致命錯誤，嘗試回退到 MP4");
                    this.hls.destroy();
                    this.hls = null;
                    // 回退到 MP4
                    const videoUrl = `${API_BASE}/recordings/${this.currentCameraId}/${dateStr}/${rec.filename}?token=${encodeURIComponent(token)}`;
                    this.els.video.src = videoUrl;
                    if (autoPlay) {
                        this.els.video.play().catch(e => console.log("Auto-play blocked:", e));
                    }
                }
            });

            this.hls.loadSource(hlsUrl);
            this.hls.attachMedia(this.els.video);
            this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
                console.log("HLS manifest 載入成功");
                if (autoPlay) {
                    this.els.video.play().catch(e => console.log("Auto-play blocked:", e));
                }
            });
            console.log("使用 HLS 串流:", segmentName, "URL:", hlsUrl);
        } else {
            // Fallback: 直接使用 MP4
            const videoUrl = `${API_BASE}/recordings/${this.currentCameraId}/${dateStr}/${rec.filename}?token=${encodeURIComponent(token)}`;
            this.els.video.src = videoUrl;
            if (autoPlay) {
                this.els.video.play().catch(e => console.log("Auto-play blocked:", e));
            }
            console.log("使用 MP4:", rec.filename);
        }

        this.currentIndex = index;
        this.updateActiveStates();
        this.updateNavButtons();

        // 更新播放資訊
        const startTime = new Date(rec.start_time);
        const timeStr = startTime.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
        const hlsTag = rec.hls_available ? " [HLS]" : "";
        this.els.clipInfo.textContent = `${timeStr} (${index + 1}/${this.recordings.length})${hlsTag}`;
    },

    updateActiveStates() {
        // 更新時間線高亮
        this.els.timeline.querySelectorAll(".timeline-clip").forEach((el, idx) => {
            el.classList.toggle("active", idx === this.currentIndex);
        });

        // 更新片段列表高亮
        this.els.clipsList.querySelectorAll(".clip-item").forEach((el, idx) => {
            el.classList.toggle("active", idx === this.currentIndex);
        });
    },

    updateNavButtons() {
        this.els.prevBtn.disabled = this.currentIndex <= 0;
        this.els.nextBtn.disabled = this.currentIndex < 0 || this.currentIndex >= this.recordings.length - 1;
    },

    playPrev() {
        if (this.currentIndex > 0) {
            this.playClip(this.currentIndex - 1);
        }
    },

    playNext() {
        if (this.currentIndex < this.recordings.length - 1) {
            this.playClip(this.currentIndex + 1);
        }
    },

    onVideoEnded() {
        // 自動播放下一段
        if (this.currentIndex < this.recordings.length - 1) {
            this.playNext();
        }
    },

    // 輪詢檢查新轉檔完成的錄影
    async pollForNewRecordings() {
        // 防止在初始化前被調用
        if (!this.initialized || !this.els.dateInput) return;

        const dateValue = this.els.dateInput.value;
        if (!dateValue) return;

        // 只在查看「今天」時才輪詢
        const today = new Date().toISOString().split("T")[0];
        if (dateValue !== today) return;

        const dateStr = dateValue.replace(/-/g, "");

        try {
            const recRes = await fetchAPI("/recordings", { date: dateStr, camera_id: this.currentCameraId });
            const newRecordings = recRes.recordings || [];

            // 比對是否有新增的錄影
            if (newRecordings.length > this.recordings.length) {
                const addedCount = newRecordings.length - this.recordings.length;
                console.log(`發現 ${addedCount} 個新轉檔完成的錄影`);

                this.recordings = newRecordings;

                // 更新摘要
                this.els.summary.textContent =
                    `${this.recordings.length} 段錄影，共 ${recRes.total_size_mb} MB`;

                // 重新渲染（保持當前播放狀態）
                this.renderTimeline();
                this.renderClipsList();
                this.updateActiveStates();
            }
        } catch (e) {
            // 靜默失敗，不影響使用者體驗
            console.debug("pollForNewRecordings error:", e);
        }
    },

    jumpToEvent(evt) {
        const evtTime = new Date(evt.entry_time);

        // 找到包含此事件的錄影片段
        let targetIndex = -1;
        let seekTime = 0;

        for (let i = 0; i < this.recordings.length; i++) {
            const rec = this.recordings[i];
            const recStart = new Date(rec.start_time);
            const recEnd = new Date(recStart.getTime() + rec.duration_seconds * 1000);

            if (evtTime >= recStart && evtTime <= recEnd) {
                targetIndex = i;
                seekTime = (evtTime - recStart) / 1000;
                break;
            }
        }

        if (targetIndex === -1) {
            // 如果事件不在任何錄影範圍內，找最接近的錄影
            let minDiff = Infinity;
            for (let i = 0; i < this.recordings.length; i++) {
                const rec = this.recordings[i];
                const recStart = new Date(rec.start_time);
                const diff = Math.abs(evtTime - recStart);
                if (diff < minDiff) {
                    minDiff = diff;
                    targetIndex = i;
                }
            }
        }

        if (targetIndex >= 0) {
            this.playClip(targetIndex);

            // 如果有精確時間點，seek 到該位置
            if (seekTime > 0) {
                this.els.video.addEventListener("loadedmetadata", () => {
                    if (seekTime < this.els.video.duration) {
                        this.els.video.currentTime = seekTime;
                    }
                }, { once: true });
            }
        }
    },
};

// === Dashboard 初始化函式 ===
async function initDashboard() {
    try {
        await verifyDashboardAuth();
        // 驗證成功，載入資料
        refreshAll();

        // 初始化錄影回放模組
        await recording.init();

        // 每 30 秒自動更新即時狀態 + 錄影列表（輪詢新轉檔完成的影片）
        setInterval(() => {
            updateRealtime();
            recording.pollForNewRecordings();
        }, 30000);

        // 每 5 分鐘更新圖表
        setInterval(() => {
            updateHourlyChart();
            updateDailyChart();
            updateSummary();
        }, 300000);
    } catch (e) {
        console.error("Dashboard auth failed:", e);
        // Token 無效，清除並顯示登入畫面
        localStorage.removeItem("pin_token");
        token = null;
        pinLogin.show();
    }
}

// === 初始化 ===
window.addEventListener("load", () => {
    initTheme();
    pinLogin.init();

    if (token) {
        // 有 Token，嘗試驗證
        initDashboard();
    } else {
        // 沒有 Token，顯示 PIN 登入
        pinLogin.show();
    }
});
