// web/dashboard.js
console.log("Dashboard loaded");

// === 設定 ===
const params = new URLSearchParams(window.location.search);
const token = params.get("token");

if (!token) {
    alert("缺少訪問憑證");
    throw new Error("missing token");
}

const API_BASE = "/api/dashboard";

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
    ]);
}

// === 事件綁定 ===
elements.rangeSelect.addEventListener("change", () => {
    updateDailyChart();
    updateSummary();
});

elements.refreshBtn.addEventListener("click", refreshAll);

document.getElementById("themeToggle").addEventListener("click", toggleTheme);

// === 初始化 ===
window.addEventListener("load", () => {
    initTheme();

    (async () => {
        try {
            await verifyDashboardAuth();
            // 驗證成功，載入資料
            refreshAll();

            // 每 30 秒自動更新即時狀態
            setInterval(updateRealtime, 30000);

            // 每 5 分鐘更新圖表
            setInterval(() => {
                updateHourlyChart();
                updateDailyChart();
                updateSummary();
            }, 300000);
        } catch (e) {
            console.error("Dashboard auth failed:", e);
            disableDashboardUI();
            alert("訪問連結已失效或過期");
        }
    })();
});
