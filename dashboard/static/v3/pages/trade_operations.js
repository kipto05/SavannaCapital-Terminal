// Trade Operations Page — JavaScript
// Handles trade executions, quality metrics, historical log, and journal annotations

// Ensure apiFetch exists (fallback if shared/api.js not loaded)
if (!window.apiFetch) {
  window.apiFetch = async (url, options = {}) => {
    const res = await fetch(url, {
      ...options,
      headers: { 'Authorization': `Bearer ${window.authToken || ''}`, ...(options.headers || {}) },
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  };
}

// State
let pollIntervalId = null;
let selectedTradeId = null;
let pollIntervalMs = 8000;

// Formatting helpers
function formatNumber(num, decimals = 2) {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(num);
}

function formatDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toISOString().slice(0, 16).replace('T', ' ');
}

function formatSideBadge(side) {
  const isBuy = side && side.toUpperCase() === 'BUY';
  const badgeClass = isBuy ? 'bg-success' : 'bg-error';
  return `<span class="badge ${badgeClass}">${side || 'UNKNOWN'}</span>`;
}

function formatPnL(pnl) {
  const formatted = formatNumber(pnl, 2);
  const colorClass = pnl > 0 ? 'text-success' : pnl < 0 ? 'text-error' : 'text-neutral';
  return `<span class="${colorClass}">${formatted}</span>`;
}

// Flash/Toast notification
function flash(msg, type = 'info') {
  const colors = { info: 'primary', error: 'error', success: 'success' };
  const color = colors[type] || colors.info;

  if (window.flash) {
    window.flash(msg, type);
    return;
  }

  const toast = document.createElement('div');
  toast.style.cssText = `position:fixed;top:20px;right:20px;padding:12px 20px;background:var(--color-${color});color:white;border-radius:4px;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:14px;max-width:300px;`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ==================== LOADERS ====================

async function loadExecutions() {
  try {
    const [positionsRes, ordersRes] = await Promise.all([
      window.apiFetch('/api/v2/mt5/positions'),
      window.apiFetch('/api/v2/mt5/orders'),
    ]);
    const positions = positionsRes.data || positionsRes || [];
    const orders = ordersRes.data || ordersRes || [];
    renderExecutionsTable(positions, orders);
  } catch (err) {
    flash(`Error loading executions: ${err.message}`, 'error');
    console.error('loadExecutions error:', err);
  }
}

async function loadExecQuality() {
  try {
    const res = await window.apiFetch('/api/trades/recent?limit=50');
    const trades = res.data || res || [];
    const metrics = computeExecQuality(trades);
    renderExecQuality(metrics);
  } catch (err) {
    flash(`Error loading execution quality: ${err.message}`, 'error');
    console.error('loadExecQuality error:', err);
  }
}

async function loadHistoricalLog() {
  try {
    const res = await window.apiFetch('/api/trades/recent?limit=50');
    const trades = res.data || res || [];
    renderHistoricalTable(trades);
  } catch (err) {
    flash(`Error loading historical log: ${err.message}`, 'error');
    console.error('loadHistoricalLog error:', err);
  }
}

async function updatePort() {
  try {
    const res = await window.apiFetch('/api/v2/accounts/summary');
    const accountName = res.account_name || res.name || 'Savanna Capital Quant OS';
    const el = document.getElementById('to-port-label');
    if (el) el.textContent = accountName;
  } catch (err) {
    console.error('updatePort error:', err);
  }
}

async function updateEngineStatus() {
  try {
    const res = await window.apiFetch('/api/v2/engine/status');
    const dot = document.getElementById('to-engine-status');
    const text = document.getElementById('to-engine-text');
    if (dot) {
      if (res.error) {
        dot.className = 'w-3 h-3 rounded-full bg-warning';
      } else if (res.running) {
        dot.className = 'w-3 h-3 rounded-full bg-success';
      } else {
        dot.className = 'w-3 h-3 rounded-full bg-error';
      }
    }
    if (text) {
      text.textContent = res.error ? 'Error' : (res.running ? 'Running' : 'Stopped');
    }
  } catch (err) {
    console.error('updateEngineStatus error:', err);
  }
}

async function loadConfig() {
  try {
    const res = await window.apiFetch('/api/config/public');
    if (res && res.dashboard && res.dashboard.poll_interval_ms) {
      pollIntervalMs = res.dashboard.poll_interval_ms;
    }
  } catch (err) {
    console.log('Config not available, using default poll interval');
  }
}

// ==================== MAIN LIFECYCLE ====================

async function loadAll() {
  await Promise.allSettled([
    loadExecutions(),
    loadExecQuality(),
    loadHistoricalLog(),
    updatePort(),
    updateEngineStatus(),
  ]);

  // Update sync timestamp
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
  const syncEl = document.getElementById('to-sync-ts');
  if (syncEl) syncEl.textContent = now;
}

function reloadAll() {
  return loadAll();
}

async function init() {
  // Start ticker immediately
  updateTicker();

  // Load config for poll interval
  await loadConfig();

  // Initialize regime display from localStorage
  const regimeEl = document.getElementById('to-regime-text');
  if (regimeEl) {
    const storedRegime = localStorage.getItem('regime');
    const defaultRegime = 'Trending';
    regimeEl.textContent = storedRegime || defaultRegime;
  }

  // Initial load
  loadAll().catch(err => console.error('Initial load failed:', err));

  // Setup polling
  if (pollIntervalId) clearInterval(pollIntervalId);
  pollIntervalId = setInterval(reloadAll, pollIntervalMs);

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    if (pollIntervalId) clearInterval(pollIntervalId);
  });

  // Event listeners
  document.getElementById('to-search-input')?.addEventListener('input', onSearch);
  document.getElementById('to-regime-btn')?.addEventListener('click', onRegimeClick);
  document.getElementById('to-add-observation')?.addEventListener('submit', commitObservation);
  document.getElementById('to-positions-tbody')?.addEventListener('click', onPositionsClick);
  document.getElementById('to-history-tbody')?.addEventListener('click', onHistoryClick);
}

// ==================== TICKER ====================

function updateTicker() {
  const tickerEl = document.getElementById('to-ticker');
  if (!tickerEl) return;
  const update = () => {
    const now = new Date();
    const utc = now.toISOString().slice(11, 19);
    tickerEl.textContent = `UTC ${utc}`;
  };
  update();
  setInterval(update, 1000);
}

// ==================== RENDERERS ====================

function renderExecutionsTable(positions, orders) {
  const tbody = document.getElementById('to-positions-tbody');
  if (!tbody) return;

  const items = [
    ...positions.map(p => ({ ...p, type: 'POSITION' })),
    ...orders.map(o => ({ ...o, type: 'ORDER' })),
  ].sort((a, b) => new Date(b.open_time || b.time) - new Date(a.open_time || a.time));

  tbody.innerHTML = items.map(item => {
    const ticket = item.ticket || item.id;
    const symbol = item.symbol || 'N/A';
    const side = item.side || (item.type === 'POSITION' ? (item.position_type === 'BUY' ? 'BUY' : 'SELL') : 'BUY');
    const entry = parseFloat(item.open_price || item.price_current || item.price || 0);
    const current = item.type === 'POSITION' ? parseFloat(item.price_current || item.open_price || 0) : parseFloat(item.price || 0);
    const sl = parseFloat(item.sl || 0) || '';
    const tp = parseFloat(item.tp || 0) || '';
    const lot = parseFloat(item.volume || item.lot_size || 0);
    const pnl = item.type === 'POSITION' ? parseFloat(item.profit || 0) : 0;

    return `
      <tr data-ticket="${ticket}" data-type="${item.type}">
        <td class="px-4 py-3">${symbol}</td>
        <td class="px-4 py-3">${formatSideBadge(side)}</td>
        <td class="px-4 py-3">${formatNumber(entry, 5)}</td>
        <td class="px-4 py-3">${formatNumber(current, 5)}</td>
        <td class="px-4 py-3">${sl !== '' ? formatNumber(sl, 5) : '-'}</td>
        <td class="px-4 py-3">${tp !== '' ? formatNumber(tp, 5) : '-'}</td>
        <td class="px-4 py-3">${formatNumber(lot, 5)}</td>
        <td class="px-4 py-3">${formatPnL(pnl)}</td>
        <td class="px-4 py-3">
          ${item.type === 'POSITION' ? `<button class="close-btn px-2 py-1 text-xs bg-error text-white rounded hover:bg-red-700" data-ticket="${ticket}">Close</button>` : ''}
        </td>
      </tr>
    `;
  }).join('');
}

function renderExecQuality(metrics) {
  const { slippage, latency, fillRate, rejections } = metrics;

  const setValue = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  const setBar = (id, pct) => {
    const el = document.getElementById(id);
    if (el) el.style.width = `${Math.min(pct * 100, 100)}%`;
  };

  setValue('to-slippage-value', `${(slippage * 100).toFixed(2)}%`);
  setBar('to-slippage-bar', slippage);
  setValue('to-latency-value', `${Math.round(latency)}ms`);
  setValue('to-fillrate-value', `${(fillRate * 100).toFixed(1)}%`);
  setBar('to-fillrate-bar', fillRate);
  setValue('to-rejections-value', formatNumber(rejections, 2));
  setBar('to-rejections-bar', Math.min(rejections * 10, 100));
}

function renderHistoricalTable(trades) {
  const tbody = document.getElementById('to-history-tbody');
  if (!tbody) return;

  tbody.innerHTML = trades.map(trade => {
    const time = formatDateTime(trade.opened_at || trade.created_at || trade.timestamp);
    const symbol = trade.symbol || 'N/A';
    const side = trade.side || 'BUY';
    const entry = parseFloat(trade.entry_price || trade.price || 0);
    const exit = parseFloat(trade.exit_price || 0);
    const lot = parseFloat(trade.lot_size || trade.volume || 0);
    const pnl = parseFloat(trade.pnl || trade.profit || 0);
    const tags = trade.tags ? trade.tags.split(',').map(t => t.trim()).filter(Boolean) : [];

    return `
      <tr data-trade-id="${trade.id}">
        <td class="px-4 py-3">${time}</td>
        <td class="px-4 py-3">${symbol}</td>
        <td class="px-4 py-3">${formatSideBadge(side)}</td>
        <td class="px-4 py-3">${formatNumber(entry, 5)}</td>
        <td class="px-4 py-3">${formatNumber(exit, 5)}</td>
        <td class="px-4 py-3">${formatNumber(lot, 5)}</td>
        <td class="px-4 py-3">${formatPnL(pnl)}</td>
        <td class="px-4 py-3">
          ${tags.length ? tags.map(t => `<span class="badge bg-primary text-xs mr-1">${t}</span>`).join('') : '-'}
        </td>
      </tr>
    `;
  }).join('');
}

// ==================== JOURNAL / ANNOTATIONS ====================

async function populateJournalFromTrade(tradeId) {
  selectedTradeId = tradeId;
  await loadAnnotations(tradeId);
}

async function loadAnnotations(tradeId) {
  const container = document.getElementById('to-annotations-container');
  if (!container) return;

  try {
    const res = await window.apiFetch(`/api/v2/journal/annotations?trade_id=${tradeId}`);
    const annotations = res.data || res || [];

    if (annotations.length === 0) {
      container.innerHTML = '<div class="text-muted">No observations</div>';
      return;
    }

    container.innerHTML = annotations.map(ann => {
      const time = formatDateTime(ann.created_at || ann.timestamp);
      const type = ann.tag || ann.type || 'note';
      const note = ann.note || ann.content || '';
      return `
        <div class="annotation-card mb-3 p-3 bg-base border border-border rounded" data-id="${ann.id}">
          <div class="flex justify-between items-start">
            <div class="flex-1">
              <span class="badge bg-primary text-xs mr-2">${type.toUpperCase()}</span>
              <span class="text-sm text-secondary">${time}</span>
            </div>
            <button class="delete-ann-btn text-error hover:text-red-700 text-lg" data-id="${ann.id}">&times;</button>
          </div>
          <p class="mt-2">${note}</p>
        </div>
      `;
    }).join('');

    // Attach delete handlers
    container.querySelectorAll('.delete-ann-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.target.dataset.id;
        try {
          await window.apiFetch(`/api/v2/journal/annotations/${id}`, { method: 'DELETE' });
          e.target.closest('.annotation-card').remove();
          flash('Observation deleted', 'success');
        } catch (err) {
          flash(`Error deleting observation: ${err.message}`, 'error');
        }
      });
    });
  } catch (err) {
    container.innerHTML = '<div class="text-error">Error loading observations</div>';
    console.error('loadAnnotations error:', err);
  }
}

async function addObservation() {
  const noteInput = document.getElementById('to-obsv-text');
  const typeSelect = document.getElementById('to-obsv-type');
  if (!noteInput || !typeSelect) return;

  const note = noteInput.value.trim();
  const tag = typeSelect.value;
  if (!note) return;

  try {
    await window.apiFetch('/api/v2/journal/annotations', {
      method: 'POST',
      body: { note, tag, trade_id: selectedTradeId },
    });
    noteInput.value = '';
    await loadAnnotations(selectedTradeId);
    flash('Observation added', 'success');
  } catch (err) {
    flash(`Error adding observation: ${err.message}`, 'error');
  }
}

function commitObservation(e) {
  e.preventDefault();
  addObservation();
}

// ==================== COMPUTATIONS ====================

function computeExecQuality(trades) {
  if (!trades || trades.length < 5) {
    return {
      slippage: 0.001,   // 0.1%
      latency: 25,       // ms
      fillRate: 0.99,    // 99%
      rejections: 0.0,
    };
  }

  const recent = trades.slice(0, 20);
  let totalSlippage = 0, totalLatency = 0, filled = 0, rejected = 0;

  recent.forEach(t => {
    const expected = t.expected_price || t.entry_price || 0;
    const actual = t.executed_price || t.entry_price || 0;
    if (expected && actual && expected !== 0) {
      totalSlippage += Math.abs(actual - expected) / expected;
      filled++;
    }
    const latency = t.latency_ms || 0;
    totalLatency += latency;
    if (t.status === 'REJECTED' || t.status === 'FAILED') rejected++;
  });

  return {
    slippage: filled > 0 ? totalSlippage / filled : 0.001,
    latency: totalLatency / recent.length,
    fillRate: filled / recent.length,
    rejections: rejected / recent.length,
  };
}

// ==================== EVENT HANDLERS ====================

function onSearch(e) {
  const query = e.target.value.toLowerCase();
  // Filter executions table
  document.querySelectorAll('#to-positions-tbody tr').forEach(row => {
    const symbol = row.dataset.ticket || row.textContent.toLowerCase();
    row.style.display = symbol.includes(query) ? '' : 'none';
  });
  // Filter history table
  document.querySelectorAll('#to-history-tbody tr').forEach(row => {
    const symbol = row.dataset.tradeId || row.textContent.toLowerCase();
    row.style.display = symbol.includes(query) ? '' : 'none';
  });
}

function onRegimeClick() {
  const regimes = ['Trending', 'Ranging', 'Volatile'];
  const current = localStorage.getItem('regime') || regimes[0];
  const nextIndex = (regimes.indexOf(current) + 1) % regimes.length;
  const next = regimes[nextIndex];
  localStorage.setItem('regime', next);
  const el = document.getElementById('to-regime-text');
  if (el) el.textContent = next;
}

function onPositionsClick(e) {
  const closeBtn = e.target.closest('.close-btn');
  if (closeBtn) {
    e.preventDefault();
    e.stopPropagation();
    const ticket = closeBtn.dataset.ticket;
    if (!ticket) return;
    if (!confirm('Close this position?')) return;

    closeBtn.disabled = true;
    window.apiFetch(`/api/v2/mt5/position/${ticket}/close`, { method: 'POST' })
      .then(() => {
        flash('Position closed', 'success');
        loadExecutions();
      })
      .catch(err => {
        if (err.message.includes('404') || err.message.includes('Not Implemented')) {
          flash('Not implemented yet', 'info');
        } else {
          flash(`Error closing position: ${err.message}`, 'error');
        }
        closeBtn.disabled = false;
      });
  }
}

function onHistoryClick(e) {
  const row = e.target.closest('tr[data-trade-id]');
  if (row) {
    // Remove selection from siblings
    document.querySelectorAll('#to-history-tbody tr.bg-surface-selected').forEach(r => {
      r.classList.remove('bg-surface-selected');
    });
    row.classList.add('bg-surface-selected');
    const tradeId = parseInt(row.dataset.tradeId, 10);
    populateJournalFromTrade(tradeId);
  }
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', init);

export { init, loadAll, reloadAll };
export default { init, loadAll, reloadAll };
