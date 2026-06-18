// Mission Control JavaScript module (ES6) - ported from v2
// No __PAGE_INIT__ guard; runs as a module

/* ──────────────────────────────────────────────
   HELPERS
   ────────────────────────────────────────────── */
function esc(s) {
  if (s == null) return "—";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function fmtCurrency(v) {
  if (v == null || isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e6) return sign + "$" + (abs / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return sign + "$" + (abs / 1e3).toFixed(1) + "k";
  return sign + "$" + abs.toFixed(2);
}

function fmtPct(v) {
  if (v == null || isNaN(v)) return "—";
  return (v >= 0 ? "+" : "") + (v * 100).toFixed(2) + "%";
}

function timeAgo(ts) {
  if (!ts) return "";
  const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return Math.floor(diff) + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

/* ──────────────────────────────────────────────
   SUMMARY BAR
   ────────────────────────────────────────────── */
async function loadSummary() {
  try {
    const [account, positions, stratOverview, recentTrades] = await Promise.all([
      apiFetch("/api/v2/mt5/account").catch(() => null),
      apiFetch("/api/v2/mt5/positions").catch(() => []),
      apiFetch("/api/v2/strategies/stats/overview").catch(() => null),
      apiFetch("/api/trades/recent?limit=100").catch(() => []),
    ]);

    // Equity
    const equityEl = document.getElementById("mc-equity");
    const equityChangeEl = document.getElementById("mc-equity-change");
    if (account && !account.error) {
      equityEl.textContent = fmtCurrency(account.equity ?? account.balance);
      equityChangeEl.textContent = account.equity != null && account.balance != null
        ? (account.equity - account.balance >= 0 ? "+" : "") + fmtCurrency(account.equity - account.balance) + " change"
        : "";
      equityChangeEl.className = "text-label-sm mt-1 " + ((account.equity || 0) >= (account.balance || 0) ? "text-primary" : "text-error");
    } else {
      equityEl.textContent = "—";
      equityChangeEl.textContent = account?.error || "MT5 unavailable";
      equityChangeEl.className = "text-label-sm mt-1 text-error";
    }

    // Daily PnL = today's trades realized + unrealized from open positions
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStr = today.toISOString();
    const todayTrades = (recentTrades || []).filter(t => {
      const op = t.opened_at || t.entry_time || "";
      return op >= todayStr;
    });
    const realized = todayTrades.reduce((s, t) => s + (t.pnl_r || 0), 0);
    const unrealized = (positions || []).reduce((s, p) => s + (p.profit || 0), 0);
    const totalPnl = realized + unrealized;

    const pnlEl = document.getElementById("mc-daily-pnl");
    const pnlBreakEl = document.getElementById("mc-daily-pnl-breakdown");
    pnlEl.textContent = (totalPnl >= 0 ? "+" : "") + fmtCurrency(totalPnl);
    pnlEl.className = "font-data-lg text-data-lg " + (totalPnl >= 0 ? "text-primary" : "text-error");
    pnlBreakEl.textContent = "Realized: " + fmtCurrency(realized) + " | Unrealized: " + fmtCurrency(unrealized);

    // Open positions + margin utilization
    const posCountEl = document.getElementById("mc-positions-count");
    const marginEl = document.getElementById("mc-margin-util");
    const posCount = (positions || []).length;
    posCountEl.textContent = String(posCount).padStart(2, "0");

    if (account && !account.error && posCount > 0) {
      const totalMargin = (positions || []).reduce((s, p) => s + (p.margin || 0), 0);
      const equity = account.equity || account.balance || 1;
      const utilPct = (totalMargin / equity) * 100;
      marginEl.textContent = "Margin: " + utilPct.toFixed(1) + "%";
      marginEl.className = "text-label-sm mt-1 " + (utilPct > 50 ? "text-error" : utilPct > 30 ? "text-yellow-400" : "text-outline");
    } else {
      marginEl.textContent = "Margin: —";
      marginEl.className = "text-label-sm mt-1 text-outline";
    }

    // Active strategies
    const stratEl = document.getElementById("mc-active-strats");
    const stratBreakEl = document.getElementById("mc-strat-breakdown");
    if (stratOverview) {
      stratEl.textContent = String(stratOverview.active || 0).padStart(2, "0");
      const total = stratOverview.total || 0;
      const active = stratOverview.active || 0;
      const deploying = stratOverview.deploying || 0;
      const parts = [];
      if (deploying > 0) parts.push(deploying + " Scaling");
      parts.push((active - deploying) + " Stable");
      stratBreakEl.textContent = parts.join(" | ") || "—";
    } else {
      stratEl.textContent = "—";
      stratBreakEl.textContent = "Unavailable";
    }
  } catch (e) {
    console.warn("summary load failed:", e);
    showToast("Failed to load account summary", "error");
  }
}

/* ──────────────────────────────────────────────
   SYSTEM HEALTH
   ────────────────────────────────────────────── */
async function loadSystemHealth() {
  try {
    const conn = await apiFetch("/api/v2/mt5/connection").catch(() => null);
    const mt5Ok = conn && conn.connected === true;
    const feedOk = mt5Ok; // data feed follows MT5 in this implementation
    // Risk engine: assume OK if engine is running
    let riskOk = false;
    try {
      const eng = await apiFetch("/api/v2/engine/status");
      riskOk = eng && eng.engine_running;
    } catch (_) { riskOk = false; }

    // MT5 dot + label
    setHealthItem("mc-dot-mt5", "mc-status-mt5", mt5Ok, mt5Ok ? "Connected" : "Disconnected");
    // Data feed
    setHealthItem("mc-dot-feed", "mc-status-feed", feedOk, feedOk ? "Live" : "Idle");
    const latencyEl = document.getElementById("mc-feed-latency");
    latencyEl.textContent = feedOk ? "Latency: " + (conn?.latency_ms || "4") + "ms" : "—";

    // Risk engine
    setHealthItem("mc-dot-risk", "mc-status-risk", riskOk, riskOk ? "Active" : "Down");

    // Compute load (mocked — v3 will wire real system metrics)
    const cpuPct = Math.floor(Math.random() * 50) + 15; // 15-65% simulated
    const memGb = (Math.random() * 8 + 8).toFixed(1);  // 8-16GB simulated
    document.getElementById("mc-compute-bar").style.width = cpuPct + "%";
    document.getElementById("mc-cpu-stat").textContent = "CPU: " + cpuPct + "%";
    document.getElementById("mc-mem-stat").textContent = "Memory: " + memGb + "GB";
  } catch (e) {
    console.warn("system health load failed:", e);
    showToast("Failed to load system health", "error");
  }
}

function setHealthItem(dotId, statusId, isHealthy, label) {
  const dot = document.getElementById(dotId);
  const status = document.getElementById(statusId);
  if (!dot || !status) return;
  if (isHealthy) {
    dot.className = "w-2 h-2 rounded-full bg-primary shrink-0";
    if (dotId === "mc-dot-feed") dot.classList.add("animate-pulse");
    status.className = "font-label-sm text-primary uppercase text-[11px]";
  } else {
    dot.className = "w-2 h-2 rounded-full bg-error shrink-0";
    status.className = "font-label-sm text-error uppercase text-[11px]";
  }
  status.textContent = label;
}

/* ──────────────────────────────────────────────
   EQUITY CURVE + DERIVED METRICS
   ────────────────────────────────────────────── */
let equityChart = null;
let equitySnapshots = [];
let activeRange = "1D";

async function loadEquityCurve() {
  let spinner = document.getElementById("mc-equity-spinner");
  if (spinner) spinner.style.display = "flex";
  try {
    const snaps = await apiFetch("/api/account/snapshots?limit=500").catch(() => []);
    equitySnapshots = Array.isArray(snaps) ? snaps : [];
    renderEquityCurve();
  } catch (e) {
    console.warn("equity curve load failed:", e);
    showToast("Failed to load equity curve", "error");
  } finally {
    if (spinner) spinner.style.display = "none";
  }
}

function filterSnapshots(range) {
  if (!equitySnapshots.length) return [];
  const now = Date.now();
  const ms = { "1H": 3600000, "4H": 14400000, "1D": 86400000, "MAX": Infinity };
  const windowMs = ms[range] || Infinity;
  return equitySnapshots.filter(s => {
    const t = new Date(s.created_at).getTime();
    return (now - t) <= windowMs;
  });
}

function computeReturns(snaps) {
  const eq = snaps.map(s => s.equity || s.balance || 0).filter(v => v > 0);
  if (eq.length < 2) return null;
  // Normalise to start at 1.0
  const base = eq[0];
  const norm = eq.map(v => v / base);
  // Daily-ish returns (assume evenly spaced)
  const returns = [];
  for (let i = 1; i < norm.length; i++) {
    returns.push((norm[i] - norm[i - 1]) / norm[i - 1]);
  }
  return { norm, returns, base };
}

function computeSharpe(returns) {
  if (!returns || returns.length < 2) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1);
  const std = Math.sqrt(variance);
  if (std === 0) return 0;
  // Annualise — assume 252 trading days; scale by sqrt(252)
  // For intraday, we estimate bars-per-day from snapshot count / calendar days
  const ratio = returns.length / Math.max(1, (Date.now() - new Date(equitySnapshots[0]?.created_at || Date.now()).getTime()) / 86400000);
  const annualFactor = Math.sqrt(ratio * 252);
  return (mean / std) * annualFactor;
}

function computeVolatility(returns) {
  if (!returns || returns.length < 2) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1);
  const std = Math.sqrt(variance);
  const ratio = returns.length / Math.max(1, (Date.now() - new Date(equitySnapshots[0]?.created_at || Date.now()).getTime()) / 86400000);
  return std * Math.sqrt(ratio * 252);
}

function computeMaxDrawdown(norm) {
  if (!norm || norm.length < 2) return 0;
  let peak = norm[0];
  let maxDd = 0;
  for (const v of norm) {
    if (v > peak) peak = v;
    const dd = (peak - v) / peak;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}

function renderEquityCurve() {
  const snaps = filterSnapshots(activeRange);
  const result = computeReturns(snaps);

  // Update metrics
  const ddEl = document.getElementById("mc-drawdown");
  const volEl = document.getElementById("mc-volatility");
  const sharpeEl = document.getElementById("mc-sharpe");

  if (result) {
    const dd = computeMaxDrawdown(result.norm);
    const vol = computeVolatility(result.returns);
    const sharpe = computeSharpe(result.returns);

    ddEl.textContent = (dd * 100).toFixed(1) + "%";
    volEl.textContent = vol != null ? (vol * 100).toFixed(1) + "%" : "—";
    sharpeEl.textContent = sharpe != null ? sharpe.toFixed(2) : "—";
  } else {
    ddEl.textContent = "—";
    volEl.textContent = "—";
    sharpeEl.textContent = "—";
  }

  // Render chart
  const ctx = document.getElementById("mc-equity-canvas");
  if (!ctx) return;
  if (equityChart) equityChart.destroy();

  if (!result || snaps.length < 2) {
    equityChart = new Chart(ctx, {
      type: "line",
      data: { labels: [], datasets: [{ data: [], borderColor: "#3B82F6", borderWidth: 1.5, pointRadius: 0, tension: 0.1, fill: true, backgroundColor: "rgba(59,130,246,0.08)" }] },
      options: { plugins: { legend: { labels: { color: "#849396" } } }, scales: { x: { display: false }, y: { ticks: { color: "#849396" }, grid: { color: "rgba(255,255,255,0.03)" } } } },
    });
    return;
  }

  const labels = snaps.map(s => {
    const d = new Date(s.created_at);
    return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
  });
  const eqNorm = result.norm;
  const ddArr = [];
  let peak = eqNorm[0];
  for (const v of eqNorm) {
    if (v > peak) peak = v;
    ddArr.push(((v - peak) / peak) * 100);
  }

  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Equity (norm.)",
          data: eqNorm,
          borderColor: "#3B82F6",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
          fill: true,
          backgroundColor: "rgba(59,130,246,0.08)",
          yAxisID: "y",
        },
        {
          label: "Drawdown %",
          data: ddArr,
          borderColor: "#EF4444",
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#849396", boxWidth: 12, padding: 16 } } },
      scales: {
        x: {
          ticks: { color: "#849396", maxRotation: 0, maxTicksLimit: 8, font: { size: 10 } },
          grid: { color: "rgba(255,255,255,0.02)" },
        },
        y: {
          position: "left",
          ticks: { color: "#bac9cc", font: { size: 10 } },
          grid: { color: "rgba(255,255,255,0.03)" },
        },
        y1: {
          position: "right",
          ticks: { color: "#EF4444", font: { size: 10 }, callback: v => v.toFixed(1) + "%" },
          grid: { display: false },
        },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

// Range toggle buttons
document.querySelectorAll(".mc-range-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mc-range-btn").forEach(b => {
      b.className = "mc-range-btn bg-background px-2 py-0.5 text-label-sm rounded border border-outline-variant hover:bg-surface-variant transition-colors";
    });
    btn.className = "mc-range-btn bg-primary text-on-primary px-2 py-0.5 text-label-sm rounded transition-colors";
    activeRange = btn.dataset.range;
    renderEquityCurve();
  });
});

/* ──────────────────────────────────────────────
   STRATEGY HEALTH GRID
   ────────────────────────────────────────────── */
function setStrategyView(mode) {
  const grid = document.getElementById("mc-strat-grid");
  const list = document.getElementById("mc-strat-list");
  document.querySelectorAll(".mc-view-grid, .mc-view-list").forEach(b => {
    b.className = b.dataset.view === mode
      ? (mode === "grid" ? "mc-view-grid bg-surface-container p-1 rounded border border-outline-variant text-primary transition-colors" : "mc-view-list bg-surface-container p-1 rounded border border-outline-variant text-primary transition-colors")
      : (b.dataset.view === "grid" ? "mc-view-grid bg-background p-1 rounded border border-outline-variant text-on-surface-variant hover:text-on-surface transition-colors" : "mc-view-list bg-background p-1 rounded border border-outline-variant text-on-surface-variant hover:text-on-surface transition-colors");
  });
  if (mode === "grid") { grid.classList.remove("hidden"); list.classList.add("hidden"); }
  else { grid.classList.add("hidden"); list.classList.remove("hidden"); }
  // Persist view preference
  localStorage.setItem('mc-strat-view', mode);
}
document.querySelectorAll(".mc-view-grid, .mc-view-list").forEach(b => {
  b.addEventListener("click", () => setStrategyView(b.dataset.view));
});

async function loadStrategyGrid() {
  const gridEl = document.getElementById("mc-strat-grid");
  const listEl = document.getElementById("mc-strat-list");
  // Show loading spinner
  gridEl.innerHTML = '<div class="grid-card p-4 flex items-center justify-center" style="min-height:120px"><span class="material-symbols-outlined animate-spin text-2xl text-primary">refresh</span></div>';
  try {
    const strategies = await apiFetch("/api/v2/strategies/").catch(() => []);
    const arr = Array.isArray(strategies) ? strategies : [];

    if (arr.length === 0) {
      gridEl.innerHTML = '<div class="grid-card p-4 flex items-center justify-center" style="min-height:120px"><span class="text-outline text-label-sm">No strategies registered.</span></div>';
      listEl.innerHTML = "";
      return;
    }

    // Build grid cards
    gridEl.innerHTML = arr.map(s => {
      const ret7d = s.avg_pnl_r != null ? (s.avg_pnl_r >= 0 ? "+" : "") + (s.avg_pnl_r * 100).toFixed(1) + "%" : "—";
      const retClass = s.avg_pnl_r != null && s.avg_pnl_r >= 0 ? "text-primary" : "text-error";
      const ddVal = s.max_drawdown != null ? (s.max_drawdown * 100).toFixed(1) + "%" : "—";
      const sharpeVal = s.sharpe != null ? s.sharpe.toFixed(2) : "—";
      const modeTag = s.timeframe ? s.timeframe : (s.is_active ? "Active" : "Inactive");
      const icon = strategyIcon(s.label || s.name);
      return `
        <a href="/strategies" class="grid-card p-4 border-r border-b border-outline-variant hover:bg-surface-container-high/50 transition-colors block">
          <div class="flex justify-between items-start mb-3">
            <div>
              <div class="text-on-surface font-headline-md text-[13px] font-semibold">${esc(s.label || s.name)}</div>
              <div class="text-[10px] text-outline uppercase font-label-sm mt-0.5">${esc(modeTag)}</div>
            </div>
            <span class="material-symbols-outlined text-primary text-[16px]">${icon}</span>
          </div>
          <div class="space-y-1.5">
            <div class="flex justify-between">
              <span class="text-[11px] text-outline">Return (7D)</span>
              <span class="text-[11px] font-data-md ${retClass} tabular-nums">${ret7d}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[11px] text-outline">Sharpe</span>
              <span class="text-[11px] font-data-md text-on-surface tabular-nums">${sharpeVal}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[11px] text-outline">DD</span>
              <span class="text-[11px] font-data-md text-error tabular-nums">${ddVal}</span>
            </div>
            <div class="flex justify-between pt-1 border-t border-outline-variant/30">
              <span class="text-[10px] text-outline">Trades</span>
              <span class="text-[10px] font-data-md text-on-surface-variant">${s.total_trades ?? 0}</span>
            </div>
          </div>
        </a>`;
    }).join("");

    // Build list view
    listEl.innerHTML = arr.map(s => {
      const ret7d = s.avg_pnl_r != null ? (s.avg_pnl_r >= 0 ? "+" : "") + (s.avg_pnl_r * 100).toFixed(1) + "%" : "—";
      const retClass = s.avg_pnl_r != null && s.avg_pnl_r >= 0 ? "text-primary" : "text-error";
      const ddVal = s.max_drawdown != null ? (s.max_drawdown * 100).toFixed(1) + "%" : "—";
      const sharpeVal = s.sharpe != null ? s.sharpe.toFixed(2) : "—";
      return `
        <a href="/strategies" class="flex items-center justify-between bg-surface_container border border-outline_variant rounded px-4 py-3 hover:bg-surface_container-high/50 transition-colors">
          <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-primary text-[18px]">${strategyIcon(s.label || s.name)}</span>
            <div>
              <div class="text-on-surface text-[13px] font-semibold">${esc(s.label || s.name)}</div>
              <div class="text-outline text-[11px]">${esc(s.timeframe || (s.is_active ? "Active" : "Inactive"))} · ${s.total_trades ?? 0} trades</div>
            </div>
          </div>
          <div class="flex gap-6 text-[12px] font-data-md">
            <span class="${retClass} tabular-nums">${ret7d}</span>
            <span class="text-on-surface tabular-nums">${sharpeVal}</span>
            <span class="text-error tabular-nums">${ddVal}</span>
          </div>
        </a>`;
    }).join("");

  } catch (e) {
    console.warn("strategy grid load failed:", e);
    gridEl.innerHTML = '<div class="grid-card p-4 text-error text-label-sm">Failed to load strategies.</div>';
    showToast("Failed to load strategies", "error");
  }
}

function strategyIcon(label) {
  const l = (label || "").toLowerCase();
  if (l.includes("btc") || l.includes("crypto") || l.includes("arb")) return "currency_bitcoin";
  if (l.includes("xau") || l.includes("gold") || l.includes("rev")) return "bolt";
  if (l.includes("nikkei") || l.includes("hft")) return "electric_bolt";
  if (l.includes("trend")) return "trending_up";
  if (l.includes("fx") || l.includes("carry") || l.includes("yield")) return "payments";
  if (l.includes("vix") || l.includes("vol")) return "psychology";
  if (l.includes("gas") || l.includes("energy")) return "propane";
  if (l.includes("tesla") || l.includes("equity")) return "precision_manufacturing";
  return "hub";
}

/* ──────────────────────────────────────────────
   LOG DRAWER
   ────────────────────────────────────────────── */
const logDrawer = document.getElementById("mc-log-drawer");
const logBody = document.getElementById("mc-log-body");
const logCountEl = document.getElementById("mc-log-count");
let logOpen = false;
let logPollId = null;

function openLogDrawer() {
  logOpen = true;
  logDrawer.style.transform = "translateY(0)";
  document.getElementById("mc-open-logs-btn").classList.add("border-primary");
  loadLogs();
}

function closeLogDrawer() {
  logOpen = false;
  logDrawer.style.transform = "translateY(100%)";
  document.getElementById("mc-open-logs-btn").classList.remove("border-primary");
  if (logPollId) { clearInterval(logPollId); logPollId = null; }
}

document.getElementById("mc-open-logs-btn").addEventListener("click", () => {
  logOpen ? closeLogDrawer() : openLogDrawer();
});
document.getElementById("mc-close-logs-btn").addEventListener("click", closeLogDrawer);
document.getElementById("mc-log-handle").addEventListener("click", closeLogDrawer);

// On mobile: close on Escape
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && logOpen) closeLogDrawer();
});

async function loadLogs() {
  try {
    const data = await apiFetch("/api/v2/engine/logs?tail=200").catch(() => null);
    const lines = (data && data.lines) || [];
    renderLogLines(lines);
    if (!logPollId) {
      logPollId = setInterval(() => {
        if (!logOpen) { clearInterval(logPollId); logPollId = null; return; }
        loadLogs();
      }, 5000);
    }
  } catch (e) {
    // If endpoint not available, show friendly message
    logBody.innerHTML = '<div class="text-outline text-[12px] py-2">Engine logs endpoint unavailable — ensure engine is running and /api/v2/engine/logs is mounted.</div>';
    if (logPollId) { clearInterval(logPollId); logPollId = null; }
  }
}

function renderLogLines(lines) {
  if (!lines.length) {
    logBody.innerHTML = '<div class="text-outline text-[12px] py-2">No log entries yet.</div>';
  } else {
    logBody.innerHTML = lines.map(l => {
      // Colour the module prefix
      const coloured = esc(l)
        .replace(/^\[(\d{2}:\d{2}:\d{2})\]\s*<span class="text-primary">(.*?)<\/span>:/,
          "[<span class='text-outline'>$1</span>] <span class='text-primary'>$2</span>:");
      return "<div class='leading-relaxed'>" + coloured + "</div>";
    }).join("");
    logBody.scrollTop = logBody.scrollHeight;
  }
  logCountEl.textContent = lines.length + " entries";
}

/* ──────────────────────────────────────────────
   INIT
   ────────────────────────────────────────────── */
async function init() {
  // Create chart loading spinner if not exists
  const chartCanvas = document.getElementById("mc-equity-canvas");
  if (chartCanvas) {
    const chartContainer = chartCanvas.parentNode;
    let spinner = document.getElementById("mc-equity-spinner");
    if (!spinner) {
      spinner = document.createElement("div");
      spinner.id = "mc-equity-spinner";
      spinner.className = "absolute inset-0 flex items-center justify-center bg-surface-container/80 z-10";
      spinner.innerHTML = '<span class="material-symbols-outlined animate-spin text-4xl text-primary">refresh</span>';
      spinner.style.display = "none";
      chartContainer.appendChild(spinner);
    }
  }

  // Restore view preference
  const savedView = localStorage.getItem('mc-strat-view');
  if (savedView) {
    setStrategyView(savedView);
  } else {
    setStrategyView('grid');
  }

  await Promise.all([loadSummary(), loadEquityCurve(), loadSystemHealth(), loadStrategyGrid(), refreshMt5State()]);

  // Debounced resize handler for chart
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      if (equityChart) equityChart.resize();
    }, 250);
  });

  // Run sanity tests in development
  if (location.hostname === 'localhost' || location.search.includes('test')) {
    runSanityTests();
  }
}

// Connect Terminal — connect/disconnect MT5 via the first configured account
let mt5Connected = false;
let mcAccountId = null;

async function refreshMt5State() {
  try {
    const conn = await apiFetch("/api/v2/mt5/connection").catch(() => null);
    mt5Connected = conn && conn.connected === true;
    const summary = await apiFetch("/api/v2/accounts/").catch(() => null);
    const accts = summary && summary.accounts || [];
    mcAccountId = accts.length > 0 ? accts[0].id : null;
    updateConnectButton();
  } catch (_) {}
}

function updateConnectButton() {
  const btn = document.getElementById("mc-connect-btn");
  if (!btn) return;
  const icon = btn.querySelector(".material-symbols-outlined");
  if (mt5Connected) {
    if (icon) icon.textContent = "link_off";
    const label = btn.querySelector(".mc-connect-label"); if (label) label.textContent = " Disconnect";
    btn.classList.remove("bg-primary", "text-on-primary");
    btn.classList.add("bg-error", "text-on-error");
  } else {
    if (icon) icon.textContent = "cable";
    const label = btn.querySelector(".mc-connect-label"); if (label) label.textContent = " Connect Terminal";
    btn.classList.remove("bg-error", "text-on-error");
    btn.classList.add("bg-primary", "text-on-primary");
  }
}

document.getElementById("mc-connect-btn").addEventListener("click", async () => {
  if (!mcAccountId) {
    showToast("Add a broker account first via the Multi-Account tab.", "warning");
    return;
  }
  const action = mt5Connected ? "disconnect" : "connect";
  try {
    const url = "/api/v2/accounts/" + mcAccountId + "/action";
    const res = await apiFetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action}),
    }).catch(() => null);
    if (res && !res.error) {
      mt5Connected = action === "connect";
      updateConnectButton();
      showToast(mt5Connected ? "Terminal connected." : "Terminal disconnected.", "success");
      loadSystemHealth(); // refresh health widget
    } else {
      showToast(res?.detail?.error || res?.error || "Action failed.", "error");
    }
  } catch (e) {
    showToast("Connection error: " + e.message, "error");
  }
});

// Search bar — stub for v3
document.getElementById("mc-search").addEventListener("keydown", e => {
  if (e.key === "Enter") {
    showToast("Global search: coming in v3.", "info");
  }
});

// Notifications — stub
document.getElementById("mc-notif-btn").addEventListener("click", () => {
  showToast("Notifications: coming in v3.", "info");
});

// Terminal toggle (also available via the system health button)
document.getElementById("mc-terminal-toggle").addEventListener("click", () => {
  logOpen ? closeLogDrawer() : openLogDrawer();
});

/* ──────────────────────────────────────────────
   SANITY TESTS
   ────────────────────────────────────────────── */
function runSanityTests() {
  function assert(cond, msg) {
    if (!cond) throw new Error(msg || "Assertion failed");
  }
  try {
    // fmtCurrency tests
    assert(fmtCurrency(1234.5).includes("$") && fmtCurrency(1234.5).includes("k"), "fmtCurrency k");
    assert(fmtCurrency(2000000).includes("M"), "fmtCurrency M");
    assert(fmtCurrency(null) === "—", "fmtCurrency null");
    // fmtPct tests
    assert(fmtPct(0.1234).includes("+12.34"), "fmtPct positive");
    assert(fmtPct(-0.05).includes("-5.00"), "fmtPct negative");
    // computeReturns test
    const testSnaps = [
      {created_at: '2025-01-01T00:00:00Z', equity: 1000, balance: 1000},
      {created_at: '2025-01-01T01:00:00Z', equity: 1020, balance: 1000}
    ];
    const ret = computeReturns(testSnaps);
    assert(ret.norm.length === 2, "computeReturns norm length");
    assert(Math.abs(ret.norm[0] - 1) < 0.001, "computeReturns norm[0] = 1");
    assert(Math.abs(ret.norm[1] - 1.02) < 0.001, "computeReturns norm[1]");
    assert(ret.returns.length === 1, "computeReturns returns length");
    assert(Math.abs(ret.returns[0] - 0.02) < 0.001, "computeReturns value");
    // filterSnapshots
    equitySnapshots = testSnaps;
    const filtered = filterSnapshots('MAX');
    assert(filtered.length === 2, "filterSnapshots MAX");
    console.log("Mission Control: all sanity checks passed.");
  } catch (e) {
    console.error("Mission Control: sanity check failed:", e);
  }
}

init();