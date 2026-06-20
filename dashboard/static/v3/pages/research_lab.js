/**
 * Research Lab - Hypothesis Generation Workspace
 * ES6 Module for v3 Dashboard
 */

// Hardcoded dataset metadata (categories with datasets)
const datasetMeta = {
  categories: [
    {
      name: "Metals",
      datasets: [
        {
          name: "Gold (XAUUSD)",
          symbol: "XAUUSD",
          dataset: "Gold (XAUUSD)",
          size: "2.1 GB",
          timeframe: "M1-M15",
          refreshed: "2 min ago"
        }
      ]
    },
    {
      name: "Crypto (L2)",
      datasets: [
        {
          name: "BTC-USD L2",
          symbol: "BTC-USD",
          dataset: "BTC-USD L2",
          size: "4.3 GB",
          timeframe: "1s-1m",
          refreshed: "15 sec ago"
        },
        {
          name: "ETH-USD L2",
          symbol: "ETH-USD",
          dataset: "ETH-USD L2",
          size: "3.8 GB",
          timeframe: "1s-1m",
          refreshed: "22 sec ago"
        }
      ]
    },
    {
      name: "Equities",
      datasets: [
        {
          name: "AAPL Equities",
          symbol: "AAPL",
          dataset: "AAPL Equities",
          size: "1.2 GB",
          timeframe: "M1-M15",
          refreshed: "5 min ago"
        }
      ]
    }
  ]
};

// Pre-loaded observation demo cards
const mockObs = [
  {
    id: "obs_001",
    type: "STAT_SIG",
    title: "Volume-Price Correlation Spike",
    tags: ["volume", "liquidity", "intraday"],
    timestamp: "2025-06-19T14:32:00Z",
    body: "Detected significant correlation (r=0.82) between volume surges and price acceleration in BTC-USD L2 during Asian session. This pattern repeats with 73% confidence across last 50 occurrences."
  },
  {
    id: "obs_002",
    type: "ANOMALY",
    title: "Gold Order Book Imbalance",
    tags: ["metals", "liquidity", "pre-market"],
    timestamp: "2025-06-19T12:15:00Z",
    body: "Unusual order book skew detected on XAUUSD: bid/ask depth ratio = 4.2:1 (typical: 1.1:1). Usually precedes 15-30 pip move within 5 minutes."
  },
  {
    id: "obs_003",
    type: "REGIME_SHIFT",
    title: "Crypto Volatility Regime Change",
    tags: ["crypto", "volatility", "regime"],
    timestamp: "2025-06-19T10:00:00Z",
    body: "ATR percentile moved from 15% to 82% over 2 hours. Volatility expanding regime confirmed by GARCH(1,1) forecast. Position sizes should be reduced by 40%."
  }
];

// Preset output strings for mock execution
const blockOutputs = {
  "data_load": `Dataset loaded: 150,000 bars
Memory: 2.1 GB
Features: 47
Timeframe: M15
Date range: 2020-01-01 to 2025-06-19
Missing values: 0.00%`,
  "alpha_signal": `Alpha signal computed
Signal strength: 0.73
Z-score: 2.4
P-value: 0.008
Sharpe (OOS): 1.42
IC (Information Coefficient): 0.031
Bootstrap confidence: [0.021, 0.041]`,
  "regime_detect": `Regime detection complete
Current regime: volatility_expanding
Trend strength: 0.68
ADX: 34.2
ATR %: 0.0047 (82nd percentile)
Market state: trending_high_vol`,
  "feature_eng": `Feature engineering pipeline
Generated features: 47
- Lag returns: [1, 5, 10, 20, 50]
- Volume ratios: [1h, 4h, 1d]
- Technical indicators: 12 (RSI, MACD, ATR, BB)
- Market microstructure: 8 (bid-ask spread, depth ratio)
- Regime flags: 3
Feature selection: mutual info (top 20 retained)`,
  "backtest_stub": `Backtest stub executed
Initial capital: $100,000
Total trades: 247
Win rate: 54.3%
Net profit: $12,450
Sharpe ratio: 1.18
Max drawdown: -8.7%
Profit factor: 1.42`,
  "validation": `Validation checks passed
No data leakage detected
No look-ahead bias
Out-of-sample tested (2024-01 to 2025-06)
Monte Carlo p-value: 0.032
Survival bias check: PASS
Transaction costs: included (2.5 bps)`,
  "risk_calc": `Risk metrics computed
VaR (95%, 1-day): -2.4%
Expected shortfall: -3.1%
Tail risk ratio: 0.67
Correlation with SPX: 0.23
Beta: 0.84
Max adverse excursion: -1.8%`
};

// Default file tabs for a new dataset
const defaultFiles = [
  { name: "data_loader.py", active: true, content: `# Data ingestion
import pandas as pd
from data.repository import OHLCVRepository

repo = OHLCVRepository()
df = repo.get(symbol="${symbol}", timeframe="M15")
print("Loading complete")` },
  { name: "feature_engineering.py", active: false, content: `# Feature pipeline
from ml.feature_engineer import FeatureEngineer

fe = FeatureEngineer()
features = fe.build(df, include_regime=True)
print("Features generated")` },
  { name: "alpha_model.py", active: false, content: `# Alpha computation
from ml.predictor import Predictor

pred = Predictor()
signals = pred.generate(df, features)
print("Alpha signals ready")` },
  { name: "backtest_stub.py", active: false, content: `# Backtest outline
from quant.backtest_engine import BacktestEngine

engine = BacktestEngine()
results = engine.run(signals)
print("Backtest complete")` }
];

// State
let activeDataset = null;
let executedBlocks = new Set();
let observationCounter = 1;
let statsInterval = null;
let blockCounter = 0;

/**
 * Initialize module: bind events, initial render
 */
export function init() {
  log.debug("Research Lab: initializing");

  // Dataset card clicks (event delegation)
  document.getElementById("dataset-categories")?.addEventListener("click", (e) => {
    const card = e.target.closest(".dataset-card");
    if (card) {
      const datasetName = card.dataset.dataset;
      activateDataset(datasetName);
    }
  });

  // Tab clicks
  document.getElementById("workspace-tabs")?.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab-button");
    if (tab) {
      const filename = tab.dataset.file;
      switchTab(filename);
    }
  });

  // Run button clicks (event delegation on code blocks)
  document.getElementById("code-blocks")?.addEventListener("click", (e) => {
    if (e.target.classList.contains("run-btn")) {
      const blockId = e.target.dataset.blockId;
      runBlock(blockId);
    }
  });

  // Observation form
  const obsForm = document.getElementById("observation-form");
  document.getElementById("obs-save-btn")?.addEventListener("click", addObservation);
  document.getElementById("obs-cancel-btn")?.addEventListener("click", () => {
    obsForm.classList.add("hidden");
  });
  document.getElementById("add-obs-btn")?.addEventListener("click", () => {
    obsForm.classList.remove("hidden");
  });

  // Commit hypothesis
  document.getElementById("commit-hypothesis-btn")?.addEventListener("click", commitObservation);

  // Terminal input
  document.getElementById("terminal-input")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("terminal-input-field");
    if (input?.value.trim()) {
      sendChat(input.value.trim());
      input.value = "";
    }
  });

  // Refresh viz button
  document.getElementById("refresh-viz-btn")?.addEventListener("click", renderViz);

  // Custom event listener for hypothesis creation
  window.addEventListener("research.hypothesis.created", (e) => {
    log.info("Hypothesis committed successfully: %s", e.detail.title);
  });

  // Initial render
  renderDatasets();
  renderObservations();
}

/**
 * Populate left panel with dataset categories and cards
 */
export function renderDatasets() {
  const container = document.getElementById("dataset-categories");
  if (!container) return;

  container.innerHTML = datasetMeta.categories.map(cat => `
    <div class="category-group">
      <div class="text-outline text-[11px] uppercase font-bold mb-1.5">${cat.name}</div>
      <div class="space-y-1">
        ${cat.datasets.map(ds => `
          <div class="dataset-card bg-background border border-outline-variant rounded p-2.5 cursor-pointer hover:border-primary hover:bg-surface-container-high transition-colors"
               data-symbol="${ds.symbol}"
               data-dataset="${ds.dataset}">
            <div class="font-body-sm text-on-surface font-medium mb-1">${ds.name}</div>
            <div class="text-outline text-[10px] space-y-0.5">
              <div>Size: ${ds.size}</div>
              <div>Timeframe: ${ds.timeframe}</div>
              <div>Refreshed: ${ds.refreshed}</div>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `).join("");

  log.info("Dataset explorer rendered: %d categories", datasetMeta.categories.length);
}

/**
 * Activate dataset: load into notebook, add file tabs, clear workspace
 */
export function activateDataset(datasetName) {
  log.debug("Activating dataset: %s", datasetName);
  activeDataset = datasetName;

  // Find dataset info
  let datasetInfo = null;
  for (const cat of datasetMeta.categories) {
    const found = cat.datasets.find(ds => ds.dataset === datasetName);
    if (found) {
      datasetInfo = found;
      break;
    }
  }

  if (!datasetInfo) {
    log.warning("Dataset not found: %s", datasetName);
    return;
  }

  // Show workspace content, hide empty state
  document.getElementById("workspace-empty")?.classList.add("hidden");
  document.getElementById("workspace-content")?.classList.remove("hidden");

  // Reset executed blocks
  executedBlocks.clear();
  blockCounter = 0;
  updateRuntimeStats();

  // Create file tabs
  const tabsContainer = document.getElementById("workspace-tabs");
  const codeBlocksContainer = document.getElementById("code-blocks");

  // Clear existing
  tabsContainer.innerHTML = "";
  codeBlocksContainer.innerHTML = "";

  // Add tabs with dataset-specific substitutions
  const files = defaultFiles.map(f => ({
    ...f,
    content: f.content.replace(/\$\{symbol\}/g, datasetInfo.symbol)
  }));

  files.forEach(file => {
    // Create tab button
    const tabBtn = document.createElement("button");
    tabBtn.className = `tab-button px-3 py-1 text-[11px] font-label-sm rounded-t-lg border border-transparent ${file.active ? "bg-surface-container text-primary border-outline-variant" : "bg-surface-container-highest text-outline hover:bg-surface-container"}`;
    tabBtn.textContent = file.name;
    tabBtn.dataset.file = file.name;
    tabsContainer.appendChild(tabBtn);

    // Create code block panel
    const block = document.createElement("div");
    block.className = `code-block bg-background border border-outline-variant rounded-lg p-4 ${file.active ? "" : "hidden"}`;
    block.dataset.file = file.name;

    block.innerHTML = `
      <div class="flex justify-between items-center mb-3">
        <div class="font-body-sm text-on-surface font-medium">${file.name}</div>
        <button class="run-btn bg-primary text-on-primary px-2 py-0.5 rounded text-[10px] font-label-sm hover:opacity-90 flex items-center gap-1"
                data-block-id="${file.name}">
          <span class="material-symbols-outlined text-[14px]">play_arrow</span>
          Run
        </button>
      </div>
      <pre class="bg-surface-container-highest rounded p-3 text-[11px] font-mono text-on-surface overflow-x-auto mb-3"><code>${escapeHtml(file.content)}</code></pre>
      <div class="output-panel hidden">
        <div class="text-[10px] uppercase font-bold text-outline mb-1.5">Output</div>
        <pre class="bg-surface-container-highest rounded p-3 text-[10px] font-mono text-on-surface overflow-x-auto"><code class="output-content"></code></pre>
      </div>
    `;

    codeBlocksContainer.appendChild(block);
  });

  // Render initial visualization
  setTimeout(renderViz, 100);

  log.info("Dataset activated: %s (%s)", datasetName, datasetInfo.symbol);
}

/**
 * Switch to a file tab
 */
export function switchTab(filename) {
  // Update tab buttons
  const tabs = document.querySelectorAll(".tab-button");
  tabs.forEach(tab => {
    if (tab.dataset.file === filename) {
      tab.className = "tab-button px-3 py-1 text-[11px] font-label-sm rounded-t-lg bg-surface-container text-primary border border-outline-variant";
    } else {
      tab.className = "tab-button px-3 py-1 text-[11px] font-label-sm rounded-t-lg bg-surface-container-highest text-outline hover:bg-surface-container border border-transparent";
    }
  });

  // Show/hide code blocks
  const blocks = document.querySelectorAll(".code-block");
  blocks.forEach(block => {
    if (block.dataset.file === filename) {
      block.classList.remove("hidden");
    } else {
      block.classList.add("hidden");
    }
  });
}

/**
 * Simulate Python code execution with mock output
 */
export function runBlock(blockId) {
  if (executedBlocks.has(blockId)) {
    log.debug("Block already executed: %s", blockId);
    return;
  }

  log.debug("Running block: %s", blockId);

  // Find the block
  const block = document.querySelector(`[data-block-id="${blockId}"]`)?.closest(".code-block");
  if (!block) return;

  // Show loading state
  const runBtn = block.querySelector(".run-btn");
  runBtn.disabled = true;
  runBtn.innerHTML = `<span class="material-symbols-outlined text-[14px]">hourglass_empty</span> Running...`;

  // Simulate execution delay
  setTimeout(() => {
    // Find appropriate output
    let outputKey = "data_load";
    if (blockId.includes("feature")) outputKey = "feature_eng";
    else if (blockId.includes("alpha")) outputKey = "alpha_signal";
    else if (blockId.includes("backtest")) outputKey = "backtest_stub";
    else if (blockId.includes("validation")) outputKey = "validation";
    else if (blockId.includes("risk")) outputKey = "risk_calc";
    else if (blockId.includes("regime")) outputKey = "regime_detect";

    const outputText = blockOutputs[outputKey] || "Execution complete (no output defined)";
    outputBlock(blockId, outputText);

    // Update button state
    runBtn.disabled = false;
    runBtn.innerHTML = `<span class="material-symbols-outlined text-[14px]">play_arrow</span> Run`;

    // Track execution
    executedBlocks.add(blockId);
    blockCounter++;
    updateRuntimeStats();

    log.info("Block executed: %s", blockId);
  }, 700);
}

/**
 * Display execution output in collapsible panel
 */
export function outputBlock(blockId, outputText) {
  const block = document.querySelector(`[data-block-id="${blockId}"]`)?.closest(".code-block");
  if (!block) return;

  const outputPanel = block.querySelector(".output-panel");
  const outputContent = block.querySelector(".output-content");

  outputContent.textContent = outputText;
  outputPanel.classList.remove("hidden");

  // Expand output panel smoothly
  outputPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/**
 * Render 12×10 heatmap visualization with gradient (cols × rows)
 */
export function renderViz() {
  const canvas = document.getElementById("alpha-heatmap");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const cellSize = 40;
  const rows = 10;
  const cols = 12;

  canvas.width = cols * cellSize;
  canvas.height = rows * cellSize;

  // Generate random alpha intensities (0.0 to 1.0)
  const data = [];
  for (let r = 0; r < rows; r++) {
    const row = [];
    for (let c = 0; c < cols; c++) {
      row.push(Math.random());
    }
    data.push(row);
  }

  // Draw cells
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const intensity = data[r][c];
      const color = getHeatmapColor(intensity);
      ctx.fillStyle = color;
      ctx.fillRect(c * cellSize, r * cellSize, cellSize, cellSize);
      ctx.strokeStyle = "#e0e0e0";
      ctx.strokeRect(c * cellSize, r * cellSize, cellSize, cellSize);
    }
  }

  log.debug("Visualization rendered: %dx%d heatmap", cols, rows);
}

/**
 * Get color for heatmap intensity (blue → yellow → red)
 */
function getHeatmapColor(intensity) {
  // intensity: 0.0 (blue) → 0.5 (yellow) → 1.0 (red)
  if (intensity < 0.5) {
    // Blue to Yellow
    const t = intensity / 0.5;
    const r = Math.round(59 + (254 - 59) * t);
    const g = Math.round(130 + (227 - 130) * t);
    const b = Math.round(246 + (66 - 246) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // Yellow to Red
    const t = (intensity - 0.5) / 0.5;
    const r = Math.round(254 + (239 - 254) * t);
    const g = Math.round(227 + (68 - 227) * t);
    const b = Math.round(66 + (68 - 66) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
}

/**
 * Populate right panel with observation cards
 */
export function renderObservations() {
  const container = document.getElementById("observations-list");
  if (!container) return;

  if (mockObs.length === 0) {
    container.innerHTML = '<div class="text-outline text-[12px] italic">No observations yet</div>';
    return;
  }

  container.innerHTML = mockObs.map(obs => createObservationCard(obs)).join("");
  log.info("Observations rendered: %d cards", mockObs.length);
}

/**
 * Create HTML for an observation card
 */
function createObservationCard(obs) {
  const date = new Date(obs.timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });

  const badgeClass = getBadgeClass(obs.type);
  const badgeLabel = getBadgeLabel(obs.type);

  const tagsHtml = obs.tags.map(tag => `
    <span class="inline-block bg-surface-container border border-outline-variant text-[9px] uppercase px-1.5 py-0.5 mr-1 mb-1">${tag}</span>
  `).join("");

  return `
    <div class="bg-background border border-outline-variant rounded-lg p-2.5" data-obs-id="${obs.id}">
      <div class="flex justify-between items-start mb-1.5">
        <span class="${badgeClass} text-[9px] font-label-sm uppercase px-1.5 py-0.5 rounded-full">${badgeLabel}</span>
        <span class="text-outline text-[10px]">${date}</span>
      </div>
      <div class="font-body-sm text-on-surface font-medium mb-1">${escapeHtml(obs.title)}</div>
      <div class="text-[11px] text-on-surface-variant mb-2 line-clamp-2">${escapeHtml(obs.body)}</div>
      <div class="flex flex-wrap">${tagsHtml}</div>
    </div>
  `;
}

/**
 * Get badge CSS class for observation type
 */
function getBadgeClass(type) {
  const classes = {
    "STAT_SIG": "bg-primary text-on-primary",
    "ANOMALY": "bg-error text-on-error",
    "DATA_GAP": "bg-surface-container text-outline border border-outline-variant",
    "VOLATILITY": "bg-warning text-on-warning-container",
    "REGIME_SHIFT": "bg-secondary text-on-secondary-container",
    "MODEL_ALERT": "bg-tertiary text-on-tertiary-container",
    "CORRELATION": "bg-surface-container text-on-surface-variant border border-outline-variant",
    "RISK": "bg-error text-on-error"
  };
  return classes[type] || "bg-surface-container text-outline border border-outline-variant";
}

/**
 * Get badge label for observation type
 */
function getBadgeLabel(type) {
  return type.replace("_", " ").toLowerCase();
}

/**
 * Add new observation from form
 */
export async function addObservation() {
  const type = document.getElementById("obs-type").value;
  const note = document.getElementById("obs-note").value.trim();
  const tagsInput = document.getElementById("obs-tags").value.trim();
  const tags = tagsInput ? tagsInput.split(",").map(t => t.trim().toLowerCase()).filter(t => t) : [];

  if (!note) {
    log.warning("Observation note empty");
    return;
  }

  const newObs = {
    id: `obs_${Date.now()}`,
    type,
    title: note.length > 60 ? note.substring(0, 57) + "..." : note,
    tags,
    timestamp: new Date().toISOString(),
    body: note
  };

  // Add to list
  mockObs.unshift(newObs);
  renderObservations();

  // Clear form and hide
  document.getElementById("obs-note").value = "";
  document.getElementById("obs-tags").value = "";
  document.getElementById("observation-form").classList.add("hidden");

  log.info("Observation added: %s", newObs.title);
}

/**
 * Commit observation as hypothesis to backend
 */
export async function commitObservation() {
  if (mockObs.length === 0) {
    log.warning("No observations to commit");
    return;
  }

  // Use the most recent uncommitted observation
  const latestObs = mockObs[0];

  const payload = {
    title: latestObs.title,
    description: latestObs.body,
    type: latestObs.type,
    tags: latestObs.tags,
    dataset: activeDataset || "Unknown",
    metadata: {
      source: "research_lab",
      created_at: latestObs.timestamp,
      block_count: blockCounter
    }
  };

  try {
    log.info("Committing hypothesis: %s", payload.title);

    const response = await window.apiFetch("/api/quant/hypotheses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Unknown error" }));
      throw new Error(error.error || "Failed to commit hypothesis");
    }

    const result = await response.json();
    log.info("Hypothesis committed successfully: id=%s", result.id);

    // Dispatch custom event
    const event = new CustomEvent("research.hypothesis.created", {
      detail: { ...payload, id: result.id }
    });
    window.dispatchEvent(event);

    // Redirect to hypotheses page
    window.location.href = "/hypotheses";

  } catch (error) {
    log.error("Failed to commit hypothesis: %s", error.message);
    // Optionally show toast or alert
    alert(`Failed to commit: ${error.message}`);
  }
}

/**
 * Update runtime stats (mock values every 5s)
 */
export function updateRuntimeStats() {
  // Update blocks executed count
  document.getElementById("stat-blocks").textContent = blockCounter;

  if (activeDataset) {
    // Start interval if not already running
    if (!statsInterval) {
      statsInterval = setInterval(() => {
        // Mock RAM with small random increment
        const ramGB = (2.0 + Math.random() * 0.3).toFixed(1);
        document.getElementById("stat-ram").textContent = `${ramGB} GB`;

        // Mock GPU (if available)
        const gpuPct = Math.floor(10 + Math.random() * 60);
        document.getElementById("stat-gpu").textContent = `${gpuPct}%`;

        // Compute bar (random width)
        const computePct = Math.floor(20 + Math.random() * 70);
        const computeBar = document.getElementById("stat-compute-bar");
        computeBar.style.width = `${computePct}%`;

        // Update last run (just now)
        const now = new Date();
        document.getElementById("stat-last-run").textContent =
          `${now.getHours()}:${now.getMinutes().toString().padStart(2, "0")}`;

      }, 5000);

      // Initial values
      statsInterval();
    }
  }
}

/**
 * Send chat message to AI (terminal interface)
 */
export async function sendChat(message) {
  log.debug("Chat message: %s", message);

  const terminalContent = document.getElementById("terminal-content");
  if (terminalContent) {
    // Add user message
    const userMsg = document.createElement("div");
    userMsg.className = "mb-2";
    userMsg.innerHTML = `<span class="text-primary font-bold">user@research:~$</span> ${escapeHtml(message)}`;
    terminalContent.appendChild(userMsg);
    terminalContent.scrollTop = terminalContent.scrollHeight;
  }

  try {
    const response = await window.apiFetch("/api/v2/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        context: "research"
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Add AI response
    if (terminalContent) {
      const aiMsg = document.createElement("div");
      aiMsg.className = "mb-3";
      aiMsg.innerHTML = `<span class="text-secondary font-bold">ai@research:~$</span> ${escapeHtml(data.response)}`;
      terminalContent.appendChild(aiMsg);
      terminalContent.scrollTop = terminalContent.scrollHeight;
    }

    log.debug("Chat response received");

  } catch (error) {
    log.error("Chat failed: %s", error.message);
    if (terminalContent) {
      const errMsg = document.createElement("div");
      errMsg.className = "mb-2 text-error";
      errMsg.textContent = `Error: ${error.message}`;
      terminalContent.appendChild(errMsg);
    }
  }
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Auto-initialize on module load if dataset-categories exists
if (document.getElementById("dataset-categories")) {
  init();
}

// Default export - removed addFileTab (not defined)
export default {
  init,
  renderDatasets,
  activateDataset,
  runBlock,
  outputBlock,
  renderViz,
  renderObservations,
  addObservation,
  commitObservation,
  updateRuntimeStats,
  sendChat
};
