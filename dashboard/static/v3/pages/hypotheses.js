/**
 * V3 Hypotheses Management - Kanban & Table Views
 * ES6 Module for v3 Dashboard
 */

// State
let allHypotheses = [];
let filteredHypotheses = [];
let currentView = localStorage.getItem("hypotheses_view") || "kanban";
let isTableCollapsed = localStorage.getItem("hypotheses_table_collapsed") === "true";

// Status configurations
const STATUS_COLUMNS = [
  { key: "DRAFT", label: "Draft", color: "bg-surface-container text-on-surface" },
  { key: "RESEARCHING", label: "Researching", color: "bg-secondary-container text-on-secondary-container" },
  { key: "BACKTESTING", label: "Backtesting", color: "bg-tertiary-container text-on-tertiary-container" },
  { key: "VALIDATED", label: "Validated", color: "bg-primary text-on-primary" },
  { key: "DEPLOYED", label: "Deployed", color: "bg-primary text-on-primary" },
  { key: "REJECTED", label: "Rejected", color: "bg-error text-on-error" }
];

/**
 * Initialize module: bind events, initial render
 */
export function initHypothesesPage() {
  log.debug("Hypotheses: initializing");

  // Apply initial view and collapse states
  setView(currentView);
  applySummaryCollapse();

  // View toggle buttons
  document.getElementById("kanbanViewBtn")?.addEventListener("click", () => setView("kanban"));
  document.getElementById("tableViewBtn")?.addEventListener("click", () => setView("table"));

  // Summary table collapse
  document.getElementById("summaryHeader")?.addEventListener("click", toggleSummaryTable);

  // Filters
  document.getElementById("statusFilter")?.addEventListener("change", applyFilters);
  document.getElementById("assetClassFilter")?.addEventListener("change", applyFilters);
  document.getElementById("searchInput")?.addEventListener("input", applyFilters);
  document.getElementById("showRejectedToggle")?.addEventListener("change", applyFilters);

  // New hypothesis modal
  document.getElementById("newHypothesisBtn")?.addEventListener("click", openModal);
  document.getElementById("closeModalBtn")?.addEventListener("click", closeModal);
  document.getElementById("cancelHypoBtn")?.addEventListener("click", closeModal);
  document.getElementById("saveHypoBtn")?.addEventListener("click", submitNewHypothesis);
  document.getElementById("hypothesis-modal-backdrop")?.addEventListener("click", (e) => {
    if (e.target.id === "hypothesis-modal-backdrop") closeModal();
  });

  // Refresh button
  document.getElementById("refreshBtn")?.addEventListener("click", () => loadHypotheses());

  // Polling
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") startPolling();
    else stopPolling();
  });
  if (document.visibilityState === "visible") startPolling();

  // External event
  document.addEventListener("research.hypothesis.created", () => loadHypotheses());

  // Initial data load
  loadHypotheses();
}

/**
 * Check if element #hypotheses-page exists (as per spec)
 */
function pageExists() {
  return document.getElementById("hypotheses-page") !== null;
}

/**
 * Auto-initialize on DOMContentLoaded if page element exists
 */
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    if (pageExists()) initHypothesesPage();
  });
} else {
  if (pageExists()) initHypothesesPage();
}

/**
 * Set view mode (kanban or table)
 */
function setView(view) {
  currentView = view;
  localStorage.setItem("hypotheses_view", view);

  const kanbanBoard = document.getElementById("kanbanBoard");
  const summaryTable = document.getElementById("summaryTable");
  const kanbanBtn = document.getElementById("kanbanViewBtn");
  const tableBtn = document.getElementById("tableViewBtn");

  const activeClasses = "px-3 py-1 bg-surface-container-highest text-primary font-label-sm text-label-sm";
  const inactiveClasses = "px-3 py-1 text-on-surface-variant hover:text-on-surface font-label-sm text-label-sm";

  if (view === "kanban") {
    if (summaryTable) summaryTable.classList.add("hidden");
    if (kanbanBoard) kanbanBoard.classList.remove("hidden");
    if (tableBtn) tableBtn.className = inactiveClasses;
    if (kanbanBtn) kanbanBtn.className = activeClasses;
  } else {
    if (kanbanBoard) kanbanBoard.classList.add("hidden");
    if (summaryTable) summaryTable.classList.remove("hidden");
    if (kanbanBtn) kanbanBtn.className = inactiveClasses;
    if (tableBtn) tableBtn.className = activeClasses;
  }
}

/**
 * Toggle summary table collapse
 */
function toggleSummaryTable() {
  isTableCollapsed = !isTableCollapsed;
  localStorage.setItem("hypotheses_table_collapsed", isTableCollapsed);
  const tbody = document.getElementById("summaryTableBody");
  const icon = document.getElementById("summaryToggleIcon");
  if (!tbody || !icon) return;
  if (isTableCollapsed) {
    tbody.classList.add("hidden");
    icon.textContent = "expand_more";
  } else {
    tbody.classList.remove("hidden");
    icon.textContent = "expand_less";
  }
}

/**
 * Apply the initial collapsed state (on load)
 */
function applySummaryCollapse() {
  const tbody = document.getElementById("summaryTableBody");
  const icon = document.getElementById("summaryToggleIcon");
  if (!tbody || !icon) return;
  if (isTableCollapsed) {
    tbody.classList.add("hidden");
    icon.textContent = "expand_more";
  } else {
    tbody.classList.remove("hidden");
    icon.textContent = "expand_less";
  }
}

/**
 * Load hypotheses from API
 */
export async function loadHypotheses(verbose = true) {
  try {
    const response = await window.apiFetch("/api/quant/hypotheses");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    allHypotheses = (data.hypotheses || data || []).map(h => ({
      ...h,
      status: h.status || "DRAFT"
    }));
    applyFilters();
    if (verbose) {
      log.info("Hypotheses loaded: %d total", allHypotheses.length);
    }
  } catch (error) {
    log.error("Failed to load hypotheses: %s", error.message);
    if (verbose) {
      showToastOrAlert("Failed to load hypotheses: " + error.message, "error");
    }
  }
}

/**
 * Apply current filters to allHypotheses and re-render
 */
export function applyFilters() {
  const statusFilterVal = document.getElementById("statusFilter")?.value || "";
  const assetFilterVal = document.getElementById("assetClassFilter")?.value || "";
  const searchQuery = (document.getElementById("searchInput")?.value || "").toLowerCase().trim();

  filteredHypotheses = allHypotheses.filter(h => {
    // Status filter
    if (statusFilterVal && h.status.toLowerCase() !== statusFilterVal) return false;
    // Asset filter
    if (assetFilterVal) {
      const assetClass = _assetClass(h.symbol).toLowerCase();
      if (assetClass !== assetFilterVal) return false;
    }
    // Text search
    if (searchQuery) {
      const title = (h.title || "").toLowerCase();
      const desc = (h.description || "").toLowerCase();
      if (!title.includes(searchQuery) && !desc.includes(searchQuery)) return false;
    }
    return true;
  });

  log.debug("Filters applied: status=%s asset=%s search=%s, result=%d", statusFilterVal, assetFilterVal, searchQuery, filteredHypotheses.length);

  renderKanban();
  renderTable();
  updateCount();
}

/**
 * Update hypothesis count label
 */
function updateCount() {
  const countEl = document.getElementById("hypothesisCount");
  if (countEl) {
    countEl.textContent = `${allHypotheses.length} Total Hypothesis${allHypotheses.length !== 1 ? 'ies' : 'y'}`;
  }
}

/**
 * Render Kanban board
 */
export function renderKanban() {
  const COLUMN_IDS = {
    draft: "column-draft",
    researching: "column-researching",
    backtesting: "column-backtesting",
    validated: "column-validated",
    deployed: "column-deployed",
    rejected: "column-rejected"
  };

  const statusOrder = ["draft", "researching", "backtesting", "validated", "deployed", "rejected"];

  statusOrder.forEach(status => {
    const colContainer = document.getElementById(COLUMN_IDS[status]);
    if (!colContainer) return;
    const statusHyps = filteredHypotheses.filter(h => h.status.toLowerCase() === status);
    if (statusHyps.length === 0) {
      colContainer.innerHTML = "";
      return;
    }
    colContainer.innerHTML = statusHyps.map(h => renderHypothesisCard(h)).join("");
  });

  // Rejected column visibility
  const rejectedCol = document.getElementById("rejectedColumn");
  if (rejectedCol) {
    const showRejected = document.getElementById("showRejectedToggle")?.checked ||
                         document.getElementById("statusFilter")?.value === "rejected";
    const hasRejected = filteredHypotheses.some(h => h.status.toLowerCase() === "rejected");
    if (showRejected && hasRejected) {
      rejectedCol.classList.remove("hidden");
    } else {
      rejectedCol.classList.add("hidden");
    }
  }

  log.debug("Kanban rendered");
}

/**
 * Render single hypothesis card for Kanban
 */
function renderHypothesisCard(hyp) {
  const assetClassRaw = _assetClass(hyp.symbol);
  const assetBadgeClass = getAssetBadgeClass(assetClassRaw);
  const assetClassDisplay = formatAssetClass(assetClassRaw);

  const statusKey = hyp.status.toUpperCase();
  const statusConfig = STATUS_COLUMNS.find(s => s.key === statusKey) || STATUS_COLUMNS[0];
  const confidence = hyp.confidence || 0;
  const confidencePct = Math.round(confidence * 100);

  // Actions based on status
  let actionsHtml = "";
  const statusLower = hyp.status.toLowerCase();
  if (statusLower === "draft") {
    actionsHtml = `
      <button class="flex-1 bg-primary text-on-primary px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.advanceHypothesis("${hyp.id}", "RESEARCHING")'>Advance</button>
      <button class="flex-1 bg-error text-on-error px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.discardHypothesis("${hyp.id}")'>Discard</button>`;
  } else if (statusLower === "researching") {
    actionsHtml = `
      <button class="flex-1 bg-primary text-on-primary px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.advanceHypothesis("${hyp.id}", "BACKTESTING")'>Backtest</button>
      <button class="flex-1 bg-error text-on-error px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.discardHypothesis("${hyp.id}")'>Discard</button>`;
  } else if (statusLower === "backtesting") {
    actionsHtml = `
      <button class="flex-1 bg-primary text-on-primary px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.advanceHypothesis("${hyp.id}", "VALIDATED")'>Validate</button>
      <button class="flex-1 bg-error text-on-error px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.discardHypothesis("${hyp.id}")'>Discard</button>`;
  } else if (statusLower === "validated") {
    actionsHtml = `
      <button class="flex-1 bg-primary text-on-primary px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.deployHypothesis("${hyp.id}")'>Deploy</button>
      <button class="flex-1 bg-error text-on-error px-2 py-1 rounded text-[10px] font-label-sm hover:opacity-90"
              onclick='window.discardHypothesis("${hyp.id}")'>Discard</button>`;
  } else if (statusLower === "deployed") {
    actionsHtml = `<div class="text-[10px] text-primary text-center">Deployed</div>`;
  } else if (statusLower === "rejected") {
    actionsHtml = `<div class="text-[10px] text-error text-center">Rejected</div>`;
  }

  return `
    <div class="bg-background border border-outline-variant rounded-lg p-3 shadow-sm">
      <div class="flex items-start justify-between mb-2">
        <span class="${assetBadgeClass} text-[9px] font-label-sm uppercase px-1.5 py-0.5 rounded-full">${assetClassDisplay}</span>
        <span class="${statusConfig.color} text-[9px] font-label-sm uppercase px-1.5 py-0.5 rounded-full">${statusConfig.label}</span>
      </div>
      <div class="font-body-sm text-on-surface font-medium mb-1.5 line-clamp-2">${escapeHtml(hyp.title)}</div>
      <div class="text-[10px] text-on-surface-variant mb-3 line-clamp-2">${escapeHtml(hyp.description || "")}</div>
      <div class="mb-2">
        <div class="flex justify-between text-[9px] text-outline mb-0.5">
          <span>Confidence</span>
          <span>${confidencePct}%</span>
        </div>
        <div class="h-2 bg-surface-variant rounded overflow-hidden">
          <div class="h-full bg-primary" style="width: ${confidencePct}%"></div>
        </div>
      </div>
      <div class="text-[9px] text-outline mb-3">${hyp.symbol} · ${hyp.timeframe || "N/A"}</div>
      <div class="flex gap-1.5">
        ${actionsHtml}
      </div>
    </div>
  `;
}

/**
 * Render Table (summary) view
 */
export function renderTable() {
  const tbody = document.getElementById("summaryTableBodyRows");
  if (!tbody) return;

  if (filteredHypotheses.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-4 text-center text-outline text-[12px]">No hypotheses match filters</td></tr>`;
    return;
  }

  tbody.innerHTML = filteredHypotheses.map(hyp => {
    const assetClassRaw = _assetClass(hyp.symbol);
    const assetBadgeClass = getAssetBadgeClass(assetClassRaw);
    const assetClassDisplay = formatAssetClass(assetClassRaw);
    const statusKey = hyp.status.toUpperCase();
    const statusConfig = STATUS_COLUMNS.find(s => s.key === statusKey) || STATUS_COLUMNS[0];
    const confidence = hyp.confidence || 0;
    const confidencePct = Math.round(confidence * 100);
    const id = hyp.id || "-";
    const title = hyp.title || "";
    const description = hyp.description || "";
    const timeframe = hyp.timeframe || "-";

    return `
      <tr class="border-t border-outline-variant hover:bg-surface-container transition-colors">
        <td class="px-4 py-2 text-[10px] font-mono text-outline">${id}</td>
        <td class="px-4 py-2">
          <div class="font-body-sm text-on-surface font-medium">${escapeHtml(title)}</div>
          <div class="text-[10px] text-on-surface-variant line-clamp-1">${escapeHtml(description)}</div>
        </td>
        <td class="px-4 py-2">
          <span class="${assetBadgeClass} text-[9px] font-label-sm uppercase px-1.5 py-0.5 rounded-full">${assetClassDisplay}</span>
        </td>
        <td class="px-4 py-2 text-[10px] text-on-surface-variant">${timeframe}</td>
        <td class="px-4 py-2">
          <div class="flex items-center gap-2">
            <div class="w-16 h-2 bg-surface-variant rounded overflow-hidden">
              <div class="h-full bg-primary" style="width: ${confidencePct}%"></div>
            </div>
            <span class="text-[10px] text-on-surface-variant">${confidencePct}%</span>
          </div>
        </td>
        <td class="px-4 py-2">
          <span class="${statusConfig.color} text-[9px] font-label-sm uppercase px-1.5 py-0.5 rounded-full">${statusConfig.label}</span>
        </td>
      </tr>
    `;
  }).join("");

  log.debug("Table rendered: %d rows", filteredHypotheses.length);
}

/**
 * Determine asset class from symbol
 * Returns: "crypto", "fx", "equities", "commodities", "other"
 */
export function _assetClass(symbol) {
  if (!symbol) return "other";
  const s = symbol.toUpperCase();
  // Crypto
  if (s.includes("BTC") || s.includes("ETH") || s.includes("XRP") || s.includes("DOGE") || s.includes("SOL")) {
    return "crypto";
  }
  // Metals -> Commodities
  if (s.includes("XAU") || s.includes("XAG")) {
    return "commodities";
  }
  // Forex (6-letter pairs with major currencies)
  if (/^[A-Z]{6}$/.test(s) && (s.includes("USD") || s.includes("EUR") || s.includes("GBP") || s.includes("JPY") || s.includes("AUD") || s.includes("CAD") || s.includes("NZD") || s.includes("CHF"))) {
    return "fx";
  }
  // Equities (shorter tickers)
  if (/^[A-Z]{1,5}$/.test(s)) {
    return "equities";
  }
  return "other";
}

/**
 * Format asset class for display (capitalized)
 */
function formatAssetClass(raw) {
  if (raw === "fx") return "FX";
  if (raw === "other") return "Other";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

/**
 * Get badge CSS class for asset class
 */
function getAssetBadgeClass(assetClass) {
  const map = {
    "fx": "bg-secondary-container text-on-secondary-container",
    "crypto": "bg-tertiary-container text-on-tertiary-container",
    "equities": "bg-error-container text-on-error-container",
    "commodities": "bg-secondary-container text-on-secondary-container",
    "other": "bg-surface-container text-on-surface-variant border border-outline-variant"
  };
  return map[assetClass] || map["other"];
}

/**
 * Advance hypothesis to new status
 */
export async function advanceHypothesis(id, newStatus) {
  try {
    log.info("Advancing hypothesis %s to %s", id, newStatus);
    await window.apiFetch(`/api/quant/hypotheses/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    await loadHypotheses();
  } catch (error) {
    log.error("Failed to advance hypothesis: %s", error.message);
    showToastOrAlert("Failed to update status: " + error.message, "error");
  }
}

/**
 * Deploy hypothesis (advance to DEPLOYED)
 */
export async function deployHypothesis(id) {
  await advanceHypothesis(id, "DEPLOYED");
}

/**
 * Discard hypothesis (delete)
 */
export async function discardHypothesis(id) {
  if (!confirm("Are you sure you want to discard this hypothesis?")) {
    return;
  }
  try {
    log.info("Discarding hypothesis %s", id);
    await window.apiFetch(`/api/quant/hypotheses/${id}`, {
      method: "DELETE"
    });
    await loadHypotheses();
    showToastOrAlert("Hypothesis discarded", "success");
  } catch (error) {
    log.error("Failed to discard hypothesis: %s", error.message);
    showToastOrAlert("Failed to discard: " + error.message, "error");
  }
}

/**
 * Open New Hypothesis modal
 */
export function openModal() {
  const modal = document.getElementById("newHypothesisModal");
  if (modal) modal.classList.remove("hidden");
}

/**
 * Close New Hypothesis modal
 */
export function closeModal() {
  const modal = document.getElementById("newHypothesisModal");
  if (modal) modal.classList.add("hidden");
}

/**
 * Submit new hypothesis
 */
export async function submitNewHypothesis() {
  const title = document.getElementById("hypoTitle")?.value.trim();
  const description = document.getElementById("hypoDescription")?.value.trim();
  const symbol = document.getElementById("hypoSymbol")?.value.trim();
  const timeframe = document.getElementById("hypoTimeframe")?.value;
  const status = document.getElementById("hypoStatus")?.value || "draft";

  if (!title || !symbol) {
    showToastOrAlert("Title and Symbol are required", "error");
    return;
  }

  const payload = {
    title,
    description: description || "",
    symbol,
    timeframe: timeframe || "",
    status
  };

  try {
    log.info("Creating new hypothesis: %s", title);
    const response = await window.apiFetch("/api/quant/hypotheses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Unknown error" }));
      throw new Error(error.error || "Failed to create hypothesis");
    }

    const result = await response.json();
    log.info("Hypothesis created: id=%s", result.id);

    closeModal();
    // Reset form fields
    document.getElementById("hypoTitle").value = "";
    document.getElementById("hypoDescription").value = "";
    document.getElementById("hypoSymbol").value = "";
    document.getElementById("hypoTimeframe").value = "";

    await loadHypotheses();

    // Dispatch event for other pages
    const event = new CustomEvent("research.hypothesis.created", {
      detail: payload
    });
    window.dispatchEvent(event);

    showToastOrAlert("Hypothesis created successfully", "success");
  } catch (error) {
    log.error("Failed to create hypothesis: %s", error.message);
    showToastOrAlert("Failed to create: " + error.message, "error");
  }
}

/**
 * Utility: showToast if available, else alert
 */
function showToastOrAlert(message, type = "info") {
  if (typeof window.showToast === "function") {
    window.showToast(message, type);
  } else {
    alert(message);
  }
}

/**
 * Utility: Escape HTML
 */
function escapeHtml(text) {
  if (text == null) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Polling management
let pollInterval = null;

function startPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(() => {
    loadHypotheses(false);
  }, 15000);
  log.debug("Hypotheses polling started");
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
    log.debug("Hypotheses polling stopped");
  }
}

// Export functions to window for inline event handlers
window.initHypothesesPage = initHypothesesPage;
window.advanceHypothesis = advanceHypothesis;
window.deployHypothesis = deployHypothesis;
window.discardHypothesis = discardHypothesis;
window.toggleView = setView;
window.toggleTable = toggleSummaryTable;
window.applyFilters = applyFilters;
window._assetClass = _assetClass;

// Default export
export default {
  initHypothesesPage,
  loadHypotheses,
  renderKanban,
  renderTable,
  applyFilters,
  _assetClass,
  advanceHypothesis,
  deployHypothesis,
  discardHypothesis,
  openModal,
  closeModal,
  submitNewHypothesis,
  setView,
  toggleSummaryTable
};