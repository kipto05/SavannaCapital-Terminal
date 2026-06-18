// Strategy Library Page - JavaScript (ES Module)
// Handles strategy listing, filtering, detail views, and administration

// Determine if we should use mock mode
const urlParams = new URLSearchParams(window.location.search);
const USE_MOCK = urlParams.get('mock') === '1';

// Mock data and API implementation
const MOCK_STRATEGIES = [
  {
    name: "momentum_reversion",
    label: "Momentum Reversion",
    symbol: "BTCUSD",
    timeframe: "M15",
    status: "active",
    version: "2.3.0",
    total_trades: 342,
    win_rate: 0.583,
    sharpe_ratio: 1.85,
    profit_factor: 1.92,
    max_drawdown: 0.124,
    avg_win: 0.025,
    avg_loss: -0.015,
    total_pnl: 125000,
    tags: ["momentum", "reversion"],
    params: { rsi_period: 14, rsi_oversold: 30, rsi_overbought: 70, atr_multiplier: 2.0 },
    active: true,
    description: "A momentum-based mean reversion strategy for crypto assets.",
    market_regime: "ranging",
    ml_prioritized: true,
  },
  {
    name: "band_reversion",
    label: "Band Reversion",
    symbol: "EURUSD",
    timeframe: "M15",
    status: "inactive",
    version: "1.5.2",
    total_trades: 567,
    win_rate: 0.512,
    sharpe_ratio: 0.95,
    profit_factor: 1.45,
    max_drawdown: 0.085,
    avg_win: 0.018,
    avg_loss: -0.012,
    total_pnl: 78000,
    tags: ["reversion", "bands"],
    params: { bb_period: 20, bb_std: 2.0, rsi_period: 14 },
    active: false,
    description: " Bollinger Bands based reversion strategy for forex pairs.",
    market_regime: "ranging",
    ml_prioritized: false,
  },
  {
    name: "stochastic_trend",
    label: "Stochastic Trend",
    symbol: "GBPUSD",
    timeframe: "M15",
    status: "active",
    version: "2.1.0",
    total_trades: 421,
    win_rate: 0.567,
    sharpe_ratio: 1.34,
    profit_factor: 1.68,
    max_drawdown: 0.092,
    avg_win: 0.022,
    avg_loss: -0.013,
    total_pnl: 95000,
    tags: ["trend", "stochastic"],
    params: { stoch_k: 14, stoch_d: 3, stoch_smooth: 3 },
    active: true,
    description: "Trend following strategy using stochastic oscillator.",
    market_regime: "trending",
    ml_prioritized: true,
  }
];

// Mock helper functions
function mockConfigPublic() {
  return {
    engine: {
      poll_interval_seconds: 5,
      snapshot_interval_seconds: 60,
    },
    dashboard: {
      host: "127.0.0.1",
      port: 8000,
      poll_interval_ms: 8000,
      recent_trades_count: 50,
    },
    risk: {
      max_open_trades: 10,
      max_daily_drawdown: 0.05,
      max_lot_size: 100.0,
    },
  };
}

function getMockPerformance(name) {
  const strat = MOCK_STRATEGIES.find(s => s.name === name);
  if (!strat) throw new Error("Strategy not found");
  return {
    total_trades: strat.total_trades,
    win_rate: strat.win_rate,
    profit_factor: strat.profit_factor,
    sharpe_ratio: strat.sharpe_ratio,
    max_drawdown: strat.max_drawdown,
    total_return: 1.27,
    risk_per_trade: 0.02,
    current_equity: 100000 + strat.total_pnl,
  };
}

function getMockEquity(name) {
  const points = [];
  let equity = 1.0;
  points.push({ index: 0, equity: equity, timestamp: null });
  const numTrades = 100;
  for (let i = 1; i <= numTrades; i++) {
    const change = (Math.random() - 0.48) * 0.1;
    equity += change;
    if (equity < 0.5) equity = 0.5;
    points.push({
      index: i,
      equity: parseFloat(equity.toFixed(6)),
      timestamp: new Date(Date.now() - (numTrades - i) * 3600000).toISOString()
    });
  }
  return { points, final_equity: parseFloat(equity.toFixed(6)) };
}

function getMockMonteCarlo(name) {
  const simulations = 50;
  const curves = [];
  for (let s = 0; s < simulations; s++) {
    const curve = [1.0];
    let equity = 1.0;
    for (let i = 0; i < 200; i++) {
      const r = (Math.random() - 0.55) * 0.1;
      equity += r;
      curve.push(parseFloat(equity.toFixed(6)));
    }
    curves.push(curve);
  }
  return curves;
}

function getMockTrades(name) {
  const strat = MOCK_STRATEGIES.find(s => s.name === name);
  const trades = [];
  const now = new Date();
  for (let i = 0; i < 20; i++) {
    const side = Math.random() > 0.5 ? 'BUY' : 'SELL';
    const entry = 1.1000 + Math.random() * 0.1;
    const exit = entry + (Math.random() - 0.5) * 0.05;
    const pnl = side === 'BUY' ? (exit - entry) * 100000 : (entry - exit) * 100000;
    const lot = 0.1 + Math.random() * 0.9;
    trades.push({
      opened_at: new Date(now.getTime() - i * 3600000).toISOString(),
      side,
      entry_price: parseFloat(entry.toFixed(5)),
      exit_price: parseFloat(exit.toFixed(5)),
      lot_size: parseFloat(lot.toFixed(2)),
      pnl: parseFloat(pnl.toFixed(2)),
      commission: 5.0,
      tags: ["test"],
    });
  }
  return { total: trades.length, limit: 50, offset: 0, trades };
}

function getMockBacktests(name) {
  const runs = [];
  for (let i = 0; i < 3; i++) {
    runs.push({
      id: i + 1,
      total_return: 0.2 + Math.random() * 0.5,
      sharpe_ratio: 1 + Math.random(),
      win_rate: 0.5 + Math.random() * 0.2,
      profit_factor: 1.2 + Math.random() * 0.8,
      total_trades: 100 + Math.floor(Math.random() * 200),
      start_date: "2024-01-01",
      end_date: "2024-12-31",
      status: "complete",
      params: { period: 20, multiplier: 2 },
    });
  }
  return runs;
}

function getMockVersions(name) {
  const strat = MOCK_STRATEGIES.find(s => s.name === name);
  return [
    { version: strat.version, description: "Current version", created_at: new Date().toISOString() },
    { version: "2.2.0", description: "Improved SL", created_at: new Date(Date.now() - 86400000 * 2).toISOString() },
    { version: "2.1.0", description: "Added regime filter", created_at: new Date(Date.now() - 86400000 * 5).toISOString() },
  ];
}

function getMockEvidence(name) {
  return [
    { type: "backtest", status: "complete", description: "Backtest completed successfully", timestamp: new Date().toISOString(), icon: "check_circle" },
    { type: "trade", side: "BUY", symbol: "BTCUSD", pnl_r: 0.025, description: "Trade executed", timestamp: new Date(Date.now() - 3600000).toISOString(), icon: "swap_horiz" },
  ];
}

function getMockDeployments(name) {
  return [
    { action: "deployed", target: "Live", version: "2.3.0", timestamp: new Date().toISOString(), user: "admin" },
    { action: "undeployed", target: "Paper", version: "2.2.0", timestamp: new Date(Date.now() - 86400000).toISOString(), user: "system" },
  ];
}

function getMockBacktestDetails(url) {
  const id = url.split('/').pop();
  return {
    id,
    total_return: 0.35,
    sharpe_ratio: 1.6,
    win_rate: 0.58,
    profit_factor: 1.8,
    max_drawdown: 0.08,
    total_trades: 150,
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    params: { period: 20, multiplier: 2 },
    equity_curve: getMockEquity("any").points.map(p => p.equity),
    monthly_returns: Array(12).fill(0).map(() => (Math.random() - 0.4) * 0.1),
  };
}

// Real API fetch fallback (when not using mock and no global apiFetch)
function realApiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: { 'Authorization': `Bearer ${window.authToken || ''}`, ...(options.headers || {}) },
  }).then(res => {
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  });
}

// Mock API fetch implementation
async function mockApiFetch(url, options = {}) {
  await new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 200));
  console.log(`[MOCK] ${options.method || 'GET'} ${url}`);

  const method = options.method || 'GET';

  // Config public endpoint
  if (url === '/api/config/public' || url.includes('/api/config/public')) {
    return mockConfigPublic();
  }

  // Strategies list - GET /api/v3/strategies/
  if (url.includes('/api/v3/strategies/') && method === 'GET') {
    const trimmed = url.replace(/\/+$/, '');
    if (trimmed.endsWith('/api/v3/strategies') || trimmed.endsWith('/api/v3/strategies/')) {
      return MOCK_STRATEGIES;
    }
  }

  const nameMatch = url.match(/\/api\/v3\/strategies\/([^\/?]+)/);
  if (nameMatch) {
    const name = nameMatch[1];
    const getStrategy = () => {
      const s = MOCK_STRATEGIES.find(s => s.name === name);
      if (!s) throw new Error(`Strategy not found: ${name}`);
      return s;
    };

    // Toggle
    if (url.includes('/toggle') && method === 'POST') {
      const body = options.body ? JSON.parse(options.body) : {};
      const strat = getStrategy();
      strat.active = body.active ?? true;
      return { name: strat.name, is_active: strat.active };
    }

    // Params update
    if (url.includes('/params') && method === 'PUT') {
      const body = options.body ? JSON.parse(options.body) : {};
      const strat = getStrategy();
      if (!body.params || typeof body.params !== 'object') {
        throw new Error('Invalid params');
      }
      strat.params = { ...strat.params, ...body.params };
      const v = parseFloat(strat.version) || 1;
      strat.version = (v + 0.1).toFixed(1).replace(/\.?0+$/, '');
      return { name: strat.name, version: strat.version, params: strat.params };
    }

    // Copy strategy - POST /api/v3/strategies/copy
    if (url.includes('/strategies/copy') || url.endsWith('/api/v3/strategies/copy')) {
      const body = options.body ? JSON.parse(options.body) : {};
      const { source_name, new_name, symbol, description } = body;
      if (!source_name || !new_name) {
        throw new Error('source_name and new_name are required');
      }
      const source = MOCK_STRATEGIES.find(s => s.name === source_name);
      if (!source) throw new Error(`Source strategy not found: ${source_name}`);
      const exists = MOCK_STRATEGIES.find(s => s.name === new_name);
      if (exists) throw new Error(`Strategy ${new_name} already exists`);
      const clone = {
        ...source,
        name: new_name,
        symbol: symbol || source.symbol,
        label: description || source.label,
        active: false,
        version: "1.0.0",
        total_trades: 0,
        win_rate: 0,
        sharpe_ratio: 0,
        profit_factor: 0,
        max_drawdown: 0,
        avg_win: 0,
        avg_loss: 0,
        total_pnl: 0,
        params: { ...source.params },
      };
      MOCK_STRATEGIES.push(clone);
      return { name: clone.name, label: clone.label, version: clone.version };
    }

    // Performance
    if (url.includes('/performance') && method === 'GET') {
      return getMockPerformance(name);
    }

    // Equity
    if (url.includes('/equity') && method === 'GET') {
      return getMockEquity(name);
    }

    // Monte Carlo
    if (url.includes('/monte-carlo') && method === 'GET') {
      return getMockMonteCarlo(name);
    }

    // Trades
    if (url.includes('/trades') && method === 'GET') {
      return getMockTrades(name);
    }

    // Backtests
    if (url.includes('/backtests') && method === 'GET') {
      return getMockBacktests(name);
    }

    // Versions
    if (url.includes('/versions') && method === 'GET') {
      return getMockVersions(name);
    }

    // Evidence
    if (url.includes('/evidence') && method === 'GET') {
      return getMockEvidence(name);
    }

    // Deployments
    if (url.includes('/deployments') && method === 'GET') {
      return getMockDeployments(name);
    }

    // Single strategy endpoint
    if (url === `/api/v3/strategies/${name}` || url === `/api/v3/strategies/${name}/`) {
      return getStrategy();
    }
  }

  // Backtest details modal
  if (url.includes('/api/backtest-runs/') && method === 'GET') {
    return getMockBacktestDetails(url);
  }

  throw new Error(`Mock: Unhandled endpoint ${method} ${url}`);
}

// Assign the appropriate apiFetch implementation
if (USE_MOCK) {
  window.apiFetch = mockApiFetch;
} else if (!window.apiFetch) {
  window.apiFetch = realApiFetch;
}

// ==================== STATE ====================
let strategies = [];
let currentView = 'grid'; // 'grid', 'table', 'evidence'
let currentDetailName = null;
let pollIntervalId = null;
let pollIntervalMs = 8000;
let detailCharts = {};
let tradeModalCharts = {};
let backtestModalCharts = {};
let lastFocusedElement = null; // For focus restoration

// ==================== FORMATTING HELPERS ====================

function formatNumber(num, decimals = 2) {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(num);
}

function formatPercent(num, decimals = 1) {
  return `${num >= 0 ? '+' : ''}${formatNumber(num * 100, decimals)}%`;
}

function formatCurrency(num) {
  return `$${formatNumber(num, 2)}`;
}

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
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function getStatusBadge(status) {
  const statusClasses = {
    active: 'bg-green-900/30 text-green-400 border-green-700/50',
    inactive: 'bg-surface-container text-on-surface-variant border-outline-variant',
    archived: 'bg-surface-container text-on-surface-variant border-outline-variant'
  };
  const cls = statusClasses[status] || statusClasses.inactive;
  return `<span class="inline-flex items-center px-2.5 py-1 font-label text-xs font-medium border rounded-full ${cls}">${status}</span>`;
}

// ==================== CORE FUNCTIONS ====================

async function init() {
  // Load config for poll interval
  await loadConfig();

  // Restore view preference
  const savedView = localStorage.getItem('strategy-library-view');
  if (savedView && ['grid', 'table', 'evidence'].includes(savedView)) {
    currentView = savedView;
  }

  // Setup event listeners
  setupEventListeners();

  // Initial load
  await loadAll();

  // Start polling
  if (pollIntervalId) clearInterval(pollIntervalId);
  pollIntervalId = setInterval(() => {
    if (currentDetailName) {
      refreshDetailData(currentDetailName);
    } else {
      loadAll();
    }
  }, 30000);

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    if (pollIntervalId) clearInterval(pollIntervalId);
  });

  // Keyboard navigation: Escape to close detail panel
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const panel = document.getElementById('strategy-library-detail-panel');
      if (panel && !panel.classList.contains('hidden') && !panel.style.transform.includes('100%')) {
        closeDetailPanel();
      }
      closeAllModals();
    }
  });
}

async function loadAll() {
  const globalLoader = document.getElementById('strategy-library-global-loader');
  if (globalLoader) globalLoader.classList.remove('hidden');

  try {
    const res = await window.apiFetch('/api/v3/strategies/');
    strategies = res.data || res || [];
    applyFilters();
  } catch (err) {
    console.error('Failed to load strategies:', err);
    flash('Error loading strategies', 'error');
    strategies = [];
    applyFilters();
  } finally {
    if (globalLoader) globalLoader.classList.add('hidden');
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

function applyFilters() {
  const search = document.getElementById('strategy-library-search')?.value.toLowerCase() || '';
  const assetClass = document.getElementById('strategy-library-asset-class')?.value || '';
  const regime = document.getElementById('strategy-library-filter-regime')?.value || '';
  const mlOverride = document.getElementById('strategy-library-ml-override')?.checked || false;

  // Get active status filters via aria-pressed
  const activeStatusButtons = document.querySelectorAll('[data-status-filter]');
  const activeStatuses = Array.from(activeStatusButtons)
    .filter(btn => btn.getAttribute('aria-pressed') === 'true')
    .map(btn => btn.dataset.statusFilter);

  // Get active tag filters via aria-pressed
  const activeTagButtons = document.querySelectorAll('[data-tag]');
  const activeTags = Array.from(activeTagButtons)
    .filter(btn => btn.getAttribute('aria-pressed') === 'true')
    .map(btn => btn.dataset.tag);

  const filtered = strategies.filter(s => {
    // Search text
    if (search) {
      const matchName = (s.name || '').toLowerCase().includes(search);
      const matchSymbol = (s.symbol || '').toLowerCase().includes(search);
      const matchTags = (s.tags || []).some(tag => tag.toLowerCase().includes(search));
      if (!matchName && !matchSymbol && !matchTags) return false;
    }

    // Asset class
    if (assetClass && (s.asset_class || s.assetClass) !== assetClass) {
      return false;
    }

    // Status
    if (activeStatuses.length > 0 && !activeStatuses.includes(s.status)) {
      return false;
    }

    // Tags
    if (activeTags.length > 0 && !activeTags.some(tag => (s.tags || []).includes(tag))) {
      return false;
    }

    // Regime
    if (regime && (s.market_regime || s.regime) !== regime) {
      return false;
    }

    // ML override
    if (mlOverride && !s.ml_prioritized) {
      return false;
    }

    return true;
  });

  // Render based on current view
  if (currentView === 'grid') {
    renderGrid(filtered);
  } else if (currentView === 'table') {
    renderTable(filtered);
  } else if (currentView === 'evidence') {
    renderEvidence(filtered);
  }
}

function setView(viewName) {
  currentView = viewName;
  localStorage.setItem('strategy-library-view', viewName);

  // Toggle view wrappers
  const gridView = document.getElementById('strategy-library-grid-view');
  const tableView = document.getElementById('strategy-library-table-view');
  const evidenceView = document.getElementById('strategy-library-evidence-view');

  if (gridView) {
    if (viewName === 'grid') gridView.classList.remove('hidden');
    else gridView.classList.add('hidden');
  }
  if (tableView) {
    if (viewName === 'table') tableView.classList.remove('hidden');
    else tableView.classList.add('hidden');
  }
  if (evidenceView) {
    if (viewName === 'evidence') evidenceView.classList.remove('hidden');
    else evidenceView.classList.add('hidden');
  }

  // Update view toggle button states and aria-pressed
  document.querySelectorAll('[data-view-toggle]').forEach(btn => {
    const isActive = btn.dataset.viewToggle === viewName;
    if (isActive) {
      btn.classList.add('bg-surface-container', 'border-primary', 'text-primary');
      btn.classList.remove('bg-background', 'border-outline-variant', 'text-on-surface-variant');
      btn.setAttribute('aria-pressed', 'true');
    } else {
      btn.classList.remove('bg-surface-container', 'border-primary', 'text-primary');
      btn.classList.add('bg-surface', 'border-outline-variant', 'text-on-surface-variant');
      btn.setAttribute('aria-pressed', 'false');
    }
  });

  applyFilters();
}

// ==================== RENDERING ====================

function renderGrid(strategiesList) {
  const grid = document.getElementById('strategy-library-grid');
  if (!grid) return;

  if (strategiesList.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full flex flex-col items-center justify-center py-12 text-center">
        <span class="material_symbols_outlined text-[48px] text-on-surface-variant mb-4" aria-hidden="true">search_off</span>
        <p class="font-headline-md text-headline-md text-on-surface mb-2">No strategies found</p>
        <p class="font-body-md text-body-md text-on-surface-variant">Try adjusting your filters</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = strategiesList.map(s => {
    const statusBadge = getStatusBadge(s.status || 'inactive');
    const winRate = s.win_rate !== undefined ? formatPercent(s.win_rate) : '—';
    const sharpe = s.sharpe_ratio !== undefined ? formatNumber(s.sharpe_ratio, 2) : '—';
    const profitFactor = s.profit_factor !== undefined ? formatNumber(s.profit_factor, 2) : '—';
    const totalTrades = s.total_trades || s.trades_count || 0;
    const label = s.label || s.description || '';
    const timeframe = s.timeframe || s.tf || '—';
    const version = s.version || 'v1.0.0';

    // Tags
    const tagsHtml = (s.tags || []).slice(0, 3).map(tag =>
      `<span class="bg-surface-container-high border border-outline-variant px-2.5 py-1 font-label-xs text-on-surface-variant rounded">${tag}</span>`
    ).join(' ');

    // Badges: symbol, timeframe, status, version
    const badgesHtml = [
      s.symbol,
      timeframe,
      s.status,
      version
    ].map(badge => {
      if (!badge || badge === '—') return '';
      return `<span class="bg-surface-container-high border border-outline-variant px-2.5 py-1 font-label-xs text-on-surface-variant rounded">${badge}</span>`;
    }).join(' ');

    return `
      <div class="bg-surface-container border border-outline-variant rounded-lg p-4 hover:border-primary transition-colors cursor-pointer strategy-card" data-strategy-name="${s.name}" role="button" tabindex="0" aria-label="Strategy: ${s.name}. Status: ${s.status}. Win rate: ${winRate}">
        <!-- Header: name + status -->
        <div class="flex justify-between items-start mb-2">
          <div class="flex-1">
            <h3 class="font-headline-sm text-headline-sm text-on-surface font-bold mb-1">${s.name}</h3>
            <p class="font-label-sm text-on-surface-variant">${label}</p>
          </div>
          ${statusBadge}
        </div>

        <!-- Badges row -->
        <div class="flex flex-wrap gap-2 mb-3">
          ${badgesHtml}
        </div>

        <!-- Metrics grid -->
        <div class="grid grid-cols-2 gap-3 mb-3">
          <div>
            <div class="text-on-surface-variant text-xs mb-0.5">Total Trades</div>
            <div class="font-data text-data text-on-surface">${totalTrades}</div>
          </div>
          <div>
            <div class="text-on-surface-variant text-xs mb-0.5">Win Rate</div>
            <div class="font-data text-data text-on-surface">${winRate}</div>
          </div>
          <div>
            <div class="text-on-surface-variant text-xs mb-0.5">Sharpe Ratio</div>
            <div class="font-data text-data text-on-surface">${sharpe}</div>
          </div>
          <div>
            <div class="text-on-surface-variant text-xs mb-0.5">Profit Factor</div>
            <div class="font-data text-data text-on-surface">${profitFactor}</div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2 pt-2 border-t border-outline-variant">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" class="strategy-toggle" data-name="${s.name}" ${s.active ? 'checked' : ''} aria-label="Toggle ${s.name} active">
            <span class="font-label-xs text-on-surface-variant">Active</span>
          </label>
          <div class="flex-1"></div>
          <button class="strategy-details-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Details" aria-label="View details for ${s.name}">
            <span class="material_symbols_outlined text-base" aria-hidden="true">visibility</span>
          </button>
          <button class="strategy-copy-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Copy Strategy" aria-label="Copy strategy ${s.name}">
            <span class="material_symbols_outlined text-base" aria-hidden="true">content_copy</span>
          </button>
          <button class="strategy-edit-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Edit Parameters" aria-label="Edit parameters for ${s.name}">
            <span class="material_symbols_outlined text-base" aria-hidden="true">edit</span>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function renderTable(strategiesList) {
  const tbody = document.getElementById('strategy-library-table-body');
  if (!tbody) return;

  if (strategiesList.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="13" class="px-4 py-8 text-center text-on-surface-variant">
          No strategies match your current filters
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = strategiesList.map(s => {
    const statusBadge = getStatusBadge(s.status || 'inactive');
    const mlBadge = s.ml_prioritized ?
      `<span class="bg-accent text-white px-2.5 py-1 font-label-xs font-medium border rounded-full">ML</span>` :
      '<span class="text-on-surface-variant font-label-xs">—</span>';
    const totalTrades = s.total_trades || s.trades_count || 0;
    const winRate = s.win_rate !== undefined ? formatPercent(s.win_rate) : '—';
    const profitFactor = s.profit_factor !== undefined ? formatNumber(s.profit_factor, 2) : '—';
    const sharpe = s.sharpe_ratio !== undefined ? formatNumber(s.sharpe_ratio, 2) : '—';
    const maxDrawdown = s.max_drawdown !== undefined ? formatPercent(s.max_drawdown) : '—';
    const label = s.label || '';
    const timeframe = s.timeframe || s.tf || '—';
    const version = s.version || 'v1.0.0';

    return `
      <tr class="hover:bg-surface-container cursor-pointer strategy-row" data-strategy-name="${s.name}" role="button" tabindex="0" aria-label="Strategy: ${s.name}. Status: ${s.status}. Win rate: ${winRate}">
        <td class="px-4 py-3">
          <div class="font-bold text-on-surface">${s.name}</div>
        </td>
        <td class="px-4 py-3 font-data text-sm text-on-surface-variant">${label}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface">${s.symbol || '—'}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface text-center">${timeframe}</td>
        <td class="px-4 py-3">${statusBadge}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface-variant">${version}</td>
        <td class="px-4 py-3 text-right font-data text-on-surface">${totalTrades}</td>
        <td class="px-4 py-3 text-right font-data text-on-surface">${winRate}</td>
        <td class="px-4 py-3 text-right font-data text-on-surface">${profitFactor}</td>
        <td class="px-4 py-3 text-right font-data text-on-surface">${sharpe}</td>
        <td class="px-4 py-3 text-right font-data text-on-surface">${maxDrawdown}</td>
        <td class="px-4 py-3 text-center">${mlBadge}</td>
        <td class="px-4 py-3">
          <div class="flex items-center gap-1.5">
            <button class="strategy-details-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Details" aria-label="View details for ${s.name}">
              <span class="material_symbols_outlined text-base" aria-hidden="true">visibility</span>
            </button>
            <button class="strategy-edit-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Edit Parameters" aria-label="Edit parameters for ${s.name}">
              <span class="material_symbols_outlined text-base" aria-hidden="true">edit</span>
            </button>
            <button class="strategy-copy-btn p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-variant rounded transition-colors focus:outline-none focus:ring-2 focus:ring-primary" data-name="${s.name}" title="Copy Strategy" aria-label="Copy strategy ${s.name}">
              <span class="material_symbols_outlined text-base" aria-hidden="true">content_copy</span>
            </button>
            <label class="flex items-center cursor-pointer" title="Toggle Active">
              <input type="checkbox" class="strategy-toggle" data-name="${s.name}" ${s.active ? 'checked' : ''} aria-label="Toggle ${s.name} active">
            </label>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function renderEvidence(strategiesList) {
  const container = document.getElementById('strategy-library-evidence');
  if (!container) return;

  if (strategiesList.length === 0) {
    container.innerHTML = `
      <div class="flex flex-col items-center justify-center py-12 text-center">
        <span class="material_symbols_outlined text-[48px] text-on-surface-variant mb-4" aria-hidden="true">search_off</span>
        <p class="font-headline-md text-headline-md text-on-surface mb-2">No strategies to show</p>
        <p class="font-body-md text-body-md text-on-surface-variant">Select a strategy from the grid or table to view its evidence timeline</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <span class="material_symbols_outlined text-[48px] text-on-surface-variant mb-4" aria-hidden="true">psychology</span>
      <p class="font-headline-md text-headline-md text-on-surface mb-2">Evidence View</p>
      <p class="font-body-md text-body-md text-on-surface-variant">Select a strategy from the grid or table to view its trade annotations, screenshots, and reasoning timeline.</p>
    </div>
  `;
}

// ==================== DETAIL PANEL ====================

function openDetailPanel() {
  const panel = document.getElementById('strategy-library-detail-panel');
  if (panel) {
    panel.classList.remove('hidden');
    // For mobile: slide in from right; for desktop: slide up from bottom
    if (window.innerWidth < 768) {
      panel.style.transform = 'translateX(0)';
    } else {
      panel.style.transform = 'translateY(0)';
    }
    // Trap focus inside panel
    trapFocus(panel);
  }
}

function closeDetailPanel() {
  const panel = document.getElementById('strategy-library-detail-panel');
  if (panel) {
    if (window.innerWidth < 768) {
      panel.style.transform = 'translateX(100%)';
    } else {
      panel.style.transform = 'translateY(100%)';
    }
    setTimeout(() => {
      panel.classList.add('hidden');
      if (lastFocusedElement) {
        lastFocusedElement.focus();
      }
    }, 300);
  }
}

function trapFocus(element) {
  const focusableEls = element.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const firstFocusable = focusableEls[0];
  const lastFocusable = focusableEls[focusableEls.length - 1];

  if (firstFocusable) firstFocusable.focus();

  element.addEventListener('keydown', function focusTrap(e) {
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === firstFocusable) {
          e.preventDefault();
          lastFocusable.focus();
        }
      } else {
        if (document.activeElement === lastFocusable) {
          e.preventDefault();
          firstFocusable.focus();
        }
      }
    }
  });
}

async function openDetail(name) {
  const strategy = strategies.find(s => s.name === name);
  if (!strategy) return;

  currentDetailName = name;
  lastFocusedElement = document.activeElement;

  openDetailPanel();

  // Set title
  const titleEl = document.getElementById('strategy-library-detail-title');
  if (titleEl) titleEl.textContent = `${strategy.name} — Details`;

  // Populate basic info
  const descEl = document.getElementById('detail-description');
  if (descEl) descEl.textContent = strategy.description || 'No description available.';

  // Populate badges
  const badgesContainer = document.getElementById('strategy-badges');
  if (badgesContainer) {
    const tags = (strategy.tags || []).slice(0, 3);
    badgesContainer.innerHTML = tags.map(tag =>
      `<span class="bg-surface-container-high border border-outline-variant px-2.5 py-1 font-label-xs text-on-surface-variant rounded">${tag}</span>`
    ).join('');
  }

  // Populate KPI grid with static data first, then refresh
  renderDetailKPI(strategy);
  await loadStrategyPerformance(name);

  // Load detailed sections
  await loadDetailEquity(name);
  await loadDetailMonteCarlo(name);
  await loadDetailMonthly(name);
  await loadStrategyTrades(name);
  await loadStrategyBacktestRuns(name);
  await loadStrategyVersions(name);
  await loadStrategyEvidence(name);
  await loadStrategyDeployments(name);
}

function renderDetailKPI(strategy) {
  const grid = document.getElementById('strategy-library-kpi-grid');
  if (!grid) return;

  const winRate = strategy.win_rate !== undefined ? formatPercent(strategy.win_rate) : '—';
  const sharpe = strategy.sharpe_ratio !== undefined ? formatNumber(strategy.sharpe_ratio, 2) : '—';
  const profitFactor = strategy.profit_factor !== undefined ? formatNumber(strategy.profit_factor, 2) : '—';
  const totalPnL = strategy.total_pnl !== undefined ? formatCurrency(strategy.total_pnl) : '—';
  const avgWin = strategy.avg_win !== undefined ? formatCurrency(strategy.avg_win) : '—';
  const avgLoss = strategy.avg_loss !== undefined ? formatCurrency(strategy.avg_loss) : '—';
  const maxDrawdown = strategy.max_drawdown !== undefined ? formatPercent(strategy.max_drawdown) : '—';

  grid.innerHTML = `
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Win Rate</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${winRate}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Sharpe</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${sharpe}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Profit Factor</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${profitFactor}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Total PnL</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${totalPnL}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Avg Win</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-success">${avgWin}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Avg Loss</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-error">${avgLoss}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Max DD</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${maxDrawdown}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Trades</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${strategy.total_trades || strategy.trades_count || 0}</span>
        </div>
      </div>
    </div>
  `;
}

// ==================== API LOADERS FOR DETAIL SECTIONS ====================

async function loadStrategyPerformance(name) {
  const container = document.getElementById('strategy-library-kpi-grid');
  if (!container) return;

  showLoadingInTab('kpi');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/performance`);
    const metrics = res.data || res || {};

    // Render KPI tiles using helper
    renderKPITiles(metrics);
  } catch (err) {
    console.error('Failed to load performance:', err);
    showAlertInSection('kpi-container', 'Failed to load performance metrics.');
  } finally {
    hideLoadingInTab('kpi');
  }
}

function renderKPITiles(metrics) {
  const container = document.getElementById('strategy-library-kpi-grid');
  if (!container) return;

  const totalTrades = metrics.total_trades ?? metrics.trades_count ?? 0;
  const winRate = metrics.win_rate !== undefined ? formatPercent(metrics.win_rate) : '—';
  const profitFactor = metrics.profit_factor !== undefined ? formatNumber(metrics.profit_factor, 2) : '—';
  const sharpe = metrics.sharpe_ratio !== undefined ? formatNumber(metrics.sharpe_ratio, 2) : '—';
  const maxDrawdown = metrics.max_drawdown !== undefined ? formatPercent(metrics.max_drawdown) : '—';
  const totalReturn = metrics.total_return !== undefined ? formatPercent(metrics.total_return) : '—';
  const riskPerTrade = metrics.risk_per_trade !== undefined ? formatPercent(metrics.risk_per_trade) : '—';

  container.innerHTML = `
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Total Trades</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${totalTrades}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Win Rate</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${winRate}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Profit Factor</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${profitFactor}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Sharpe Ratio</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${sharpe}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Max Drawdown</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${maxDrawdown}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Total Return</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${totalReturn}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Risk per Trade</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${riskPerTrade}</span>
        </div>
      </div>
    </div>
    <div class="bg-surface border border-outline-variant rounded-lg p-4">
      <div class="flex flex-col space-y-2">
        <span class="text-on-surface-variant text-xs mb-0.5">Current Equity</span>
        <div class="flex items-baseline space-x-2">
          <span class="font-data text-2xl font-semibold text-on-surface">${metrics.current_equity !== undefined ? formatCurrency(metrics.current_equity) : '—'}</span>
        </div>
      </div>
    </div>
  `;
}

async function loadStrategyTrades(name) {
  const tbody = document.getElementById('detail-trades-body');
  if (!tbody) return;

  showLoadingInTab('trades');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/trades`);
    const trades = Array.isArray(res) ? res : (res.data || res.trades || []);

    renderTradesTable(trades);
  } catch (err) {
    console.error('Failed to load trades:', err);
    showAlertInSection('trades', 'Failed to load trades.');
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="px-4 py-3 text-center text-error font-data text-sm">
          Error loading trades
        </td>
      </tr>
    `;
  } finally {
    hideLoadingInTab('trades');
  }
}

function renderTradesTable(trades) {
  const tbody = document.getElementById('detail-trades-body');
  if (!tbody) return;

  if (trades.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="px-4 py-3 text-center text-on-surface-variant font-data text-sm">
          No trades to display
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = trades.map(trade => {
    const date = new Date(trade.opened_at || trade.entry_time || trade.created_at).toLocaleDateString();
    const side = trade.side || trade.direction || '—';
    const entry = trade.entry_price || trade.entry || 0;
    const exit = trade.exit_price || trade.exit || 0;
    const lot = trade.lot_size || trade.volume || 0;
    const pnl = trade.pnl || trade.realized_pnl || 0;
    const commission = trade.commission || 0;
    const tags = trade.tags ? trade.tags.join(', ') : '';

    const pnlClass = pnl > 0 ? 'text-success' : pnl < 0 ? 'text-error' : '';

    return `
      <tr class="hover:bg-surface-container">
        <td class="px-4 py-3 font-data text-sm text-on-surface">${date}</td>
        <td class="px-4 py-3 font-data text-sm font-bold text-on-surface">${side}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${entry.toFixed(5)}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${exit.toFixed(5)}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${lot.toFixed(2)}</td>
        <td class="px-4 py-3 font-data text-sm ${pnlClass}">${formatCurrency(pnl)}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface-variant text-right">${formatCurrency(commission)}</td>
        <td class="px-4 py-3 font-data text-sm text-on-surface-variant truncate max-w-[80px]">${tags}</td>
      </tr>
    `;
  }).join('');
}

async function loadStrategyBacktestRuns(name) {
  const container = document.getElementById('strategy-library-backtests');
  if (!container) return;

  showLoadingInTab('backtests');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/backtests`);
    const runs = Array.isArray(res) ? res : (res.data || res.runs || []);

    renderBacktestRunsList(runs);
  } catch (err) {
    console.error('Failed to load backtests:', err);
    showAlertInSection('backtest-results', 'Failed to load backtest runs.');
    container.innerHTML = `
      <div class="text-xs text-error text-center py-4">
        Error loading backtest runs
      </div>
    `;
  } finally {
    hideLoadingInTab('backtests');
  }
}

function renderBacktestRunsList(runs) {
  const container = document.getElementById('strategy-library-backtests');
  if (!container) return;

  if (runs.length === 0) {
    container.innerHTML = `
      <div class="text-xs text-on-surface-variant text-center py-4">
        No backtest runs yet. Click "Run New Backtest" to test this strategy.
      </div>
      <button class="w-full mt-2 bg-surface-container-high border border-outline-variant rounded px-3 py-2 font-label-sm text-on-surface hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary">
        Run New Backtest
      </button>
    `;
    return;
  }

  const getStatusConfig = (status) => {
    switch (status) {
      case 'complete':
        return { cls: 'bg-green-900/30 text-green-400 border-green-700/50', label: 'Complete' };
      case 'running':
        return { cls: 'bg-blue-900/30 text-blue-400 border-blue-700/50', label: 'Running' };
      case 'failed':
        return { cls: 'bg-red-900/30 text-red-400 border-red-700/50', label: 'Failed' };
      default:
        return { cls: 'bg-surface-container text-on-surface-variant border-outline-variant', label: status || 'Unknown' };
    }
  };

  container.innerHTML = `
    <div class="space-y-2">
      ${runs.map(run => {
        const totalReturn = run.total_return !== undefined ? formatPercent(run.total_return) : '—';
        const sharpe = run.sharpe_ratio !== undefined ? formatNumber(run.sharpe_ratio, 2) : '—';
        const winRate = run.win_rate !== undefined ? formatPercent(run.win_rate) : '—';
        const profitFactor = run.profit_factor !== undefined ? formatNumber(run.profit_factor, 2) : '—';
        const totalTrades = run.total_trades || run.trades_count || 0;
        const startDate = run.start_date || run.start || '—';
        const endDate = run.end_date || run.end || '—';
        const status = run.status || 'complete';
        const st = getStatusConfig(status);

        return `
          <div class="bg-surface border border-outline-variant rounded-lg p-3">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="font-label-sm text-label-sm text-on-surface font-bold mb-1">Backtest Run #${run.id || run.backtest_id || run.run_id}</div>
                <div class="text-on-surface-variant font-label-xs">${startDate} to ${endDate}</div>
              </div>
              <span class="inline-flex items-center px-2.5 py-1 font-label text-xs font-medium border rounded-full ${st.cls}">${st.label}</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2 text-xs">
              <div>
                <div class="text-on-surface-variant">Total Return</div>
                <div class="font-data text-data text-on-surface">${totalReturn}</div>
              </div>
              <div>
                <div class="text-on-surface-variant">Sharpe</div>
                <div class="font-data text-data text-on-surface">${sharpe}</div>
              </div>
              <div>
                <div class="text-on-surface-variant">Win Rate</div>
                <div class="font-data text-data text-on-surface">${winRate}</div>
              </div>
              <div>
                <div class="text-on-surface-variant">Trades</div>
                <div class="font-data text-data text-on-surface">${totalTrades}</div>
              </div>
            </div>
            <button class="view-backtest-details-btn w-full bg-surface-container-high border border-outline-variant rounded px-3 py-2 font-label-sm text-on-surface hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
              data-backtest-id="${run.id || run.backtest_id || run.run_id}">
              View Details
            </button>
          </div>
        `;
      }).join('')}
      <button class="w-full mt-2 bg-surface-container-high border border-outline-variant rounded px-3 py-2 font-label-sm text-on-surface hover:border-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary">
        Run New Backtest
      </button>
    </div>
  `;
}

async function loadStrategyVersions(name) {
  const container = document.getElementById('strategy-library-versions');
  if (!container) return;

  showLoadingInTab('versions');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/versions`);
    const versions = Array.isArray(res) ? res : (res.data || res.versions || []);

    renderVersionList(versions);
  } catch (err) {
    console.error('Failed to load versions:', err);
    showAlertInSection('version-history', 'Failed to load version history.');
  } finally {
    hideLoadingInTab('versions');
  }
}

function renderVersionList(versions) {
  const container = document.getElementById('strategy-library-versions');
  if (!container) return;

  if (versions.length === 0) {
    container.innerHTML = `
      <div class="font-label-xs text-on-surface-variant text-center py-4">
        No version history available.
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="space-y-2">
      ${versions.map(v => {
        const createdAt = new Date(v.created_at || v.timestamp || Date.now()).toLocaleDateString();
        const description = v.description || 'Version update';
        const version = v.version || v.tag || 'unknown';

        return `
          <div class="flex items-start gap-2 text-xs border-l-2 border-primary pl-2">
            <span class="material_symbols_outlined text-primary text-sm mt-1" aria-hidden="true">history</span>
            <div class="flex-1">
              <div class="text-on-surface font-bold">${version}</div>
              <div class="text-on-surface-variant">${description}</div>
            </div>
            <span class="text-on-surface-variant">${createdAt}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

async function loadStrategyEvidence(name) {
  const container = document.getElementById('strategy-library-evidence');
  if (!container) return;

  // Evidence view is only relevant in evidence tab
  if (currentView !== 'evidence') return;

  showLoadingInTab('evidence');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/evidence`);
    const items = Array.isArray(res) ? res : (res.data || res.evidence || []);

    renderEvidenceFeed(items);
  } catch (err) {
    console.error('Failed to load evidence:', err);
    showAlertInSection('evidence-feed', 'Failed to load evidence.');
  } finally {
    hideLoadingInTab('evidence');
  }
}

function renderEvidenceFeed(items) {
  const container = document.getElementById('strategy-library-evidence');
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `
      <div class="font-label-xs text-on-surface-variant text-center py-4">
        No evidence items available.
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="space-y-2" role="list">
      ${items.map(item => {
        const icon = item.icon || 'receipt_long';
        const description = item.description || 'No description';
        const timestamp = new Date(item.timestamp || item.created_at || Date.now()).toLocaleString();
        const type = item.type || 'info';

        const iconColors = {
          info: 'text-primary',
          warning: 'text-warning',
          error: 'text-error',
          success: 'text-success'
        };
        const iconColor = iconColors[type] || 'text-primary';

        return `
          <div class="flex items-start gap-2 text-xs" role="listitem">
            <span class="material_symbols_outlined ${iconColor} text-sm mt-1" aria-hidden="true">${icon}</span>
            <div class="flex-1">
              <div class="text-on-surface font-bold">${description}</div>
              <div class="text-on-surface-variant font-label-xs">${timestamp}</div>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

async function loadStrategyDeployments(name) {
  const container = document.getElementById('strategy-library-deployments');
  if (!container) return;

  showLoadingInTab('deployments');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/deployments`);
    const events = Array.isArray(res) ? res : (res.data || res.deployments || []);

    renderDeploymentTimeline(events);
  } catch (err) {
    console.error('Failed to load deployments:', err);
    showAlertInSection('deployment-history', 'Failed to load deployment history.');
  } finally {
    hideLoadingInTab('deployments');
  }
}

function renderDeploymentTimeline(events) {
  const container = document.getElementById('strategy-library-deployments');
  if (!container) return;

  if (events.length === 0) {
    container.innerHTML = `
      <div class="font-label-xs text-on-surface-variant text-center py-4">
        No deployment history available.
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="space-y-2">
      ${events.map(evt => {
        const action = evt.action || evt.event || 'deployed';
        const target = evt.target || evt.environment || 'unknown';
        const version = evt.version || 'unknown';
        const timestamp = new Date(evt.timestamp || evt.created_at || Date.now()).toLocaleString();
        const user = evt.user || 'system';

        const icon = action === 'deployed' ? 'play_circle' : action === 'undeployed' ? 'stop_circle' : 'settings';
        const statusColor = action === 'deployed' ? 'border-primary' : 'border-outline-variant';

        return `
          <div class="flex items-start gap-2 text-xs border-l-2 ${statusColor} pl-2">
            <span class="material_symbols_outlined text-primary text-sm mt-1" aria-hidden="true">${icon}</span>
            <div class="flex-1">
              <div class="text-on-surface font-bold">${action.toUpperCase()} — ${target}</div>
              <div class="text-on-surface-variant font-label-xs">Version ${version} by ${user}</div>
            </div>
            <span class="text-on-surface-variant font-label-xs">${timestamp}</span>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

async function refreshDetailData(name) {
  await Promise.all([
    loadStrategyPerformance(name),
    loadDetailEquity(name),
    loadDetailMonthly(name),
    loadStrategyTrades(name),
    loadStrategyBacktestRuns(name),
    loadStrategyVersions(name),
    loadStrategyEvidence(name),
    loadStrategyDeployments(name)
  ]);
}

// ==================== DETAIL CHARTS ====================

async function loadDetailEquity(name) {
  const canvas = document.getElementById('strategy-library-equity-chart');
  if (!canvas) return;

  // Destroy existing chart
  if (detailCharts['equity']) {
    detailCharts['equity'].destroy();
  }

  const container = canvas.parentElement;
  const loader = container.querySelector('.strategy-library-loading-spinner');
  if (loader) loader.classList.remove('hidden');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/equity`);
    let data;

    // Parse response - support two formats
    if (Array.isArray(res)) {
      data = res;
    } else if (res.data && Array.isArray(res.data)) {
      data = res.data;
    } else if (res.dates && res.equity) {
      data = res.dates.map((date, i) => ({ date, equity: res.equity[i] }));
    } else {
      console.warn('Equity data malformed:', res);
      return;
    }

    if (data.length === 0) {
      console.warn('Equity data empty');
      return;
    }

    // Determine if dates provided
    const hasDates = data[0].date !== undefined;
    const labels = hasDates ? data.map(d => d.date) : data.map((_, i) => i);
    const values = data.map(d => d.equity);

    const ctx = canvas.getContext('2d');
    detailCharts['equity'] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Equity Curve',
          data: values,
          borderColor: '#3B82F6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.1,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          x: {
            display: hasDates,
            grid: { display: false },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(128, 128, 128, 0.1)' },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to load equity curve:', err);
  } finally {
    if (loader) loader.classList.add('hidden');
  }
}

async function loadDetailMonteCarlo(name) {
  const canvas = document.getElementById('strategy-library-montecarlo-chart');
  if (!canvas) return;

  if (detailCharts['montecarlo']) {
    detailCharts['montecarlo'].destroy();
  }

  const container = canvas.parentElement;
  const loader = container.querySelector('.strategy-library-loading-spinner');
  if (loader) loader.classList.remove('hidden');

  try {
    const res = await window.apiFetch(`/api/v3/strategies/${name}/monte-carlo`);
    let simulations = [];

    if (res.simulations && Array.isArray(res.simulations)) {
      simulations = res.simulations;
    } else if (Array.isArray(res)) {
      simulations = res;
    } else {
      console.warn('Monte Carlo data malformed:', res);
      return;
    }

    if (simulations.length === 0) {
      console.warn('No Monte Carlo simulations available');
      return;
    }

    // Limit to 50 simulations
    const sims = simulations.slice(0, 50);
    const maxLength = Math.max(...sims.map(s => s.length));
    const stepLabels = Array.from({ length: maxLength }, (_, i) => i);

    // Build datasets for individual simulations (neutral, low opacity)
    const datasets = sims.map(sim => ({
      label: 'Simulation',
      data: sim,
      borderColor: 'rgba(100, 100, 100, 0.3)',
      fill: false,
      pointRadius: 0,
      tension: 0.1,
    }));

    // Compute median path across all simulations
    const medianPath = [];
    for (let i = 0; i < maxLength; i++) {
      const values = simulations
        .filter(s => i < s.length)
        .map(s => s[i])
        .sort((a, b) => a - b);
      if (values.length > 0) {
        const mid = Math.floor(values.length / 2);
        const median = values.length % 2 === 0 ? (values[mid - 1] + values[mid]) / 2 : values[mid];
        medianPath.push(median);
      } else {
        medianPath.push(null);
      }
    }

    // Add median line
    datasets.push({
      label: 'Median',
      data: medianPath,
      borderColor: '#8B5CF6',
      backgroundColor: '#8B5CF6',
      fill: false,
      pointRadius: 0,
      tension: 0.1,
      borderWidth: 2,
    });

    const ctx = canvas.getContext('2d');
    detailCharts['montecarlo'] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: stepLabels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          x: {
            display: false,
          },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(128, 128, 128, 0.1)' },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to load Monte Carlo:', err);
  } finally {
    if (loader) loader.classList.add('hidden');
  }
}

async function loadDetailMonthly(name) {
  const canvas = document.getElementById('strategy-library-returns-chart');
  if (!canvas) return;

  if (detailCharts['monthly']) {
    detailCharts['monthly'].destroy();
  }

  const container = canvas.parentElement;
  const loader = container.querySelector('.strategy-library-loading-spinner');
  if (loader) loader.classList.remove('hidden');

  try {
    // Try both endpoints: performance?metric=monthly and direct performance
    let res;
    try {
      res = await window.apiFetch(`/api/v3/strategies/${name}/performance?metric=monthly`);
    } catch (e) {
      // Fallback to generic performance endpoint
      res = await window.apiFetch(`/api/v3/strategies/${name}/performance`);
    }

    let monthlyReturns = null;

    // Check for monthly_returns field
    if (res.monthly_returns && Array.isArray(res.monthly_returns)) {
      monthlyReturns = res.monthly_returns;
    } else if (res.months && Array.isArray(res.months) && res.returns && Array.isArray(res.returns)) {
      monthlyReturns = res.returns;
    } else if (Array.isArray(res) && res.length === 12) {
      monthlyReturns = res;
    } else {
      console.warn('Monthly returns data malformed or missing:', res);
      monthlyReturns = null;
    }

    if (!monthlyReturns || monthlyReturns.length === 0) {
      console.warn('No monthly returns data available');
      return;
    }

    // Ensure exactly 12 values (pad or truncate)
    if (monthlyReturns.length < 12) {
      const padded = new Array(12).fill(null);
      monthlyReturns.forEach((val, i) => { padded[i] = val; });
      monthlyReturns = padded;
    } else {
      monthlyReturns = monthlyReturns.slice(0, 12);
    }

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    const ctx = canvas.getContext('2d');
    detailCharts['monthly'] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: months,
        datasets: [{
          label: 'Return',
          data: monthlyReturns,
          backgroundColor: monthlyReturns.map(r => r >= 0 ? '#10B981' : '#EF4444'),
          borderRadius: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                const value = context.raw;
                return `Return: ${(value * 100).toFixed(1)}%`;
              }
            }
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
          y: {
            grid: { color: 'rgba(128, 128, 128, 0.1)' },
            ticks: {
              color: '#9CA3AF',
              font: { size: 10 },
              callback: value => `${(value * 100).toFixed(0)}%`,
            },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to load monthly returns:', err);
  } finally {
    if (loader) loader.classList.add('hidden');
  }
}

// Legacy placeholders - now delegated to API loaders
async function loadDetailTrades(name) {
  const tbody = document.getElementById('detail-trades-body');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="8" class="px-4 py-3 text-center text-on-surface-variant font-data text-sm">
        Loading trades...
      </td>
    </tr>
  `;
}

async function loadDetailBacktests(name) {
  const container = document.getElementById('strategy-library-backtests');
  if (!container) return;

  container.innerHTML = `
    <div class="flex items-center gap-2 text-xs">
      <span class="material_symbols_outlined text-primary text-sm animate-spin">refresh</span>
      <span class="text-on-surface-variant">Loading backtest runs...</span>
    </div>
  `;
}

async function loadDetailVersions(name) {
  const container = document.getElementById('strategy-library-versions');
  if (!container) return;

  container.innerHTML = `
    <div class="flex items-center gap-2 text-xs">
      <span class="material_symbols_outlined text-primary text-sm animate-spin">refresh</span>
      <span class="text-on-surface-variant">Loading version history...</span>
    </div>
  `;
}

async function loadDetailDeployments(name) {
  const container = document.getElementById('strategy-library-deployments');
  if (!container) return;

  container.innerHTML = `
    <div class="flex items-start gap-2 text-xs">
      <span class="material_symbols_outlined text-primary text-sm animate-spin">refresh</span>
      <span class="text-on-surface-variant">Loading deployment history...</span>
    </div>
  `;
}

// ==================== TRADE MODAL ====================

let currentTradeModalStrategy = null;
let currentBacktestModalStrategy = null;
let currentBacktestModalId = null;

async function openTradeModal(strategyName) {
  currentTradeModalStrategy = strategyName;
  lastFocusedElement = document.activeElement;

  const modal = document.getElementById('trade-modal');
  const contentDiv = document.getElementById('trade-modal-content');
  if (!modal || !contentDiv) return;

  // Clear previous content and show loading
  contentDiv.innerHTML = `
    <div class="flex items-center justify-center py-8">
      <span class="material_symbols_outlined text-primary text-[24px] animate-spin">refresh</span>
      <span class="ml-2 text-on-surface-variant">Loading trades...</span>
    </div>
  `;
  modal.classList.remove('hidden');

  // Focus trap after modal opens
  setTimeout(() => trapFocus(modal), 100);

  try {
    // Fetch all trades for this strategy
    const endpoint = currentDetailName
      ? `/api/v3/strategies/${currentDetailName}/trades`
      : `/api/trades?strategy=${strategyName}`;
    const res = await window.apiFetch(endpoint);
    const trades = Array.isArray(res) ? res : (res.data || res.trades || []);

    if (trades.length === 0) {
      contentDiv.innerHTML = `
        <div class="text-center py-8 text-on-surface-variant">
          <span class="material_symbols_outlined text-[48px] text-on-surface-variant mb-4">inbox</span>
          <p>No trades found for this strategy</p>
        </div>
      `;
      return;
    }

    // Build trade table following data-table pattern
    const tableHtml = `
      <div class="overflow-x-auto custom-scrollbar">
        <table class="w-full border-collapse" role="table" aria-label="Trade history">
          <thead class="sticky top-0 bg-surface-container z-10">
            <tr>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-left whitespace-nowrap" scope="col">Date</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-left whitespace-nowrap" scope="col">Side</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-right whitespace-nowrap" scope="col">Entry</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-right whitespace-nowrap" scope="col">Exit</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-right whitespace-nowrap" scope="col">Lot</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-right whitespace-nowrap" scope="col">PnL</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-right whitespace-nowrap" scope="col">Comm.</th>
              <th class="px-4 py-3 font-label text-xs font-medium text-on-surface border-b border-outline-variant text-left whitespace-nowrap" scope="col">Tags</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant">
            ${trades.map(trade => {
              const date = new Date(trade.opened_at || trade.entry_time || trade.created_at).toLocaleDateString();
              const side = trade.side || trade.direction || '—';
              const entry = trade.entry_price || trade.entry || 0;
              const exit = trade.exit_price || trade.exit || 0;
              const lot = trade.lot_size || trade.volume || 0;
              const pnl = trade.pnl || trade.realized_pnl || 0;
              const commission = trade.commission || 0;
              const tags = trade.tags ? trade.tags.join(', ') : '';

              const pnlClass = pnl > 0 ? 'text-success' : pnl < 0 ? 'text-error' : '';

              return `
                <tr class="hover:bg-surface-container">
                  <td class="px-4 py-3 font-data text-sm text-on-surface">${date}</td>
                  <td class="px-4 py-3 font-data text-sm font-bold text-on-surface">${side}</td>
                  <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${entry.toFixed(5)}</td>
                  <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${exit.toFixed(5)}</td>
                  <td class="px-4 py-3 font-data text-sm text-on-surface text-right">${lot.toFixed(2)}</td>
                  <td class="px-4 py-3 font-data text-sm ${pnlClass}">${formatCurrency(pnl)}</td>
                  <td class="px-4 py-3 font-data text-sm text-on-surface-variant text-right">${formatCurrency(commission)}</td>
                  <td class="px-4 py-3 font-data text-sm text-on-surface-variant truncate max-w-[100px]">${tags}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
      <div class="mt-3 font-label-xs text-on-surface-variant" role="status">
        Showing ${trades.length} trade${trades.length !== 1 ? 's' : ''}
      </div>
    `;

    contentDiv.innerHTML = tableHtml;

  } catch (err) {
    console.error('Failed to load trades for modal:', err);
    contentDiv.innerHTML = `
      <div class="text-center py-8 text-error" role="alert">
        <span class="material_symbols_outlined text-[48px] mb-4" aria-hidden="true">error</span>
        <p>Failed to load trades</p>
        <p class="font-label-xs mt-2">${err.message}</p>
      </div>
    `;
  }
}

function closeTradeModal() {
  const modal = document.getElementById('trade-modal');
  if (modal) modal.classList.add('hidden');

  // Clear content and cleanup charts
  const contentDiv = document.getElementById('trade-modal-content');
  if (contentDiv) contentDiv.innerHTML = '';

  if (tradeModalCharts['equity']) {
    tradeModalCharts['equity'].destroy();
    tradeModalCharts['equity'] = null;
  }

  currentTradeModalStrategy = null;
  if (lastFocusedElement) {
    lastFocusedElement.focus();
  }
}

// ==================== BACKTEST MODAL ====================

async function openBacktestModal(strategyName, backtestId) {
  currentBacktestModalStrategy = strategyName;
  currentBacktestModalId = backtestId;
  lastFocusedElement = document.activeElement;

  const modal = document.getElementById('backtest-modal');
  const contentDiv = document.getElementById('backtest-modal-content');
  if (!modal || !contentDiv) return;

  // Clear previous content and show loading
  contentDiv.innerHTML = `
    <div class="flex items-center justify-center py-8">
      <span class="material_symbols_outlined text-primary text-[24px] animate-spin">refresh</span>
      <span class="ml-2 text-on-surface-variant">Loading backtest details...</span>
    </div>
  `;
  modal.classList.remove('hidden');

  // Focus trap after modal opens
  setTimeout(() => trapFocus(modal), 100);

  try {
    // Fetch backtest details
    // Support both /api/backtest-runs/{id} and /api/v3/strategies/{name}/backtest/{id}
    let res;
    try {
      res = await window.apiFetch(`/api/backtest-runs/${backtestId}`);
    } catch (e) {
      res = await window.apiFetch(`/api/v3/strategies/${strategyName}/backtest/${backtestId}`);
    }

    if (!res || typeof res !== 'object') {
      throw new Error('Invalid backtest data received');
    }

    // Render backtest details
    contentDiv.innerHTML = renderBacktestDetails(res);

    // Initialize charts if canvas elements exist
    const equityCanvas = document.getElementById('backtest-equity-chart');
    const returnsCanvas = document.getElementById('backtest-returns-chart');

    if (equityCanvas) {
      renderBacktestEquityChart(equityCanvas, res);
    }
    if (returnsCanvas) {
      renderBacktestReturnsChart(returnsCanvas, res);
    }

  } catch (err) {
    console.error('Failed to load backtest for modal:', err);
    contentDiv.innerHTML = `
      <div class="text-center py-8 text-error" role="alert">
        <span class="material_symbols_outlined text-[48px] mb-4" aria-hidden="true">error</span>
        <p>Failed to load backtest details</p>
        <p class="font-label-xs mt-2">${err.message}</p>
      </div>
    `;
  }
}

function renderBacktestDetails(data) {
  const totalReturn = data.total_return !== undefined ? formatPercent(data.total_return) : '—';
  const sharpe = data.sharpe_ratio !== undefined ? formatNumber(data.sharpe_ratio, 2) : '—';
  const winRate = data.win_rate !== undefined ? formatPercent(data.win_rate) : '—';
  const profitFactor = data.profit_factor !== undefined ? formatNumber(data.profit_factor, 2) : '—';
  const maxDrawdown = data.max_drawdown !== undefined ? formatPercent(data.max_drawdown) : '—';
  const totalTrades = data.total_trades || data.trades_count || 0;
  const startDate = data.start_date || data.start || '—';
  const endDate = data.end_date || data.end || '—';

  return `
    <div class="space-y-4">
      <!-- Summary metrics -->
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Total Return</div>
          <div class="font-data text-data text-on-surface text-lg">${totalReturn}</div>
        </div>
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Sharpe Ratio</div>
          <div class="font-data text-data text-on-surface text-lg">${sharpe}</div>
        </div>
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Win Rate</div>
          <div class="font-data text-data text-on-surface text-lg">${winRate}</div>
        </div>
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Profit Factor</div>
          <div class="font-data text-data text-on-surface text-lg">${profitFactor}</div>
        </div>
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Max Drawdown</div>
          <div class="font-data text-data text-on-surface text-lg">${maxDrawdown}</div>
        </div>
        <div class="bg-surface border border-outline-variant rounded-lg p-3">
          <div class="text-on-surface-variant font-label-xs uppercase mb-1">Total Trades</div>
          <div class="font-data text-data text-on-surface text-lg">${totalTrades}</div>
        </div>
      </div>

      <!-- Period -->
      <div class="bg-surface border border-outline-variant rounded-lg p-3">
        <div class="text-on-surface-variant font-label-xs uppercase mb-1">Backtest Period</div>
        <div class="font-body-md text-body-md text-on-surface">${startDate} to ${endDate}</div>
      </div>

      <!-- Equity curve chart -->
      <div class="bg-surface border border-outline-variant rounded-lg p-3">
        <div class="text-on-surface-variant font-label-xs uppercase mb-2">Equity Curve</div>
        <div style="height: 200px">
          <canvas id="backtest-equity-chart" role="img" aria-label="Backtest equity curve chart"></canvas>
        </div>
      </div>

      <!-- Monthly returns chart -->
      <div class="bg-surface border border-outline-variant rounded-lg p-3">
        <div class="text-on-surface-variant font-label-xs uppercase mb-2">Monthly Returns</div>
        <div style="height: 150px">
          <canvas id="backtest-returns-chart" role="img" aria-label="Monthly returns chart"></canvas>
        </div>
      </div>

      <!-- Strategy parameters -->
      <div class="bg-surface border border-outline-variant rounded-lg p-3">
        <div class="text-on-surface-variant font-label-xs uppercase mb-2">Parameters</div>
        <pre class="font-label-xs text-on-surface overflow-x-auto bg-surface-container p-3 rounded border border-outline-variant">${JSON.stringify(data.params || data.parameters || {}, null, 2)}</pre>
      </div>
    </div>
  `;
}

function renderBacktestEquityChart(canvas, data) {
  // Destroy existing chart if any
  if (backtestModalCharts['equity']) {
    backtestModalCharts['equity'].destroy();
  }

  try {
    let equityData;
    if (data.equity_curve && Array.isArray(data.equity_curve)) {
      equityData = data.equity_curve;
    } else if (data.dates && data.equity) {
      equityData = data.equity;
    } else if (Array.isArray(data)) {
      equityData = data;
    } else {
      console.warn('Backtest equity data not found');
      return;
    }

    const ctx = canvas.getContext('2d');
    backtestModalCharts['equity'] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: equityData.map((_, i) => i),
        datasets: [{
          label: 'Equity',
          data: equityData,
          borderColor: '#3B82F6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.1,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          x: {
            display: false,
          },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(128, 128, 128, 0.1)' },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to render backtest equity chart:', err);
  }
}

function renderBacktestReturnsChart(canvas, data) {
  // Destroy existing chart if any
  if (backtestModalCharts['monthly']) {
    backtestModalCharts['monthly'].destroy();
  }

  try {
    let monthlyReturns;
    if (data.monthly_returns && Array.isArray(data.monthly_returns)) {
      monthlyReturns = data.monthly_returns;
    } else if (data.returns && Array.isArray(data.returns)) {
      monthlyReturns = data.returns;
    } else {
      console.warn('Backtest monthly returns data not found');
      return;
    }

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // Ensure 12 values
    if (monthlyReturns.length < 12) {
      const padded = new Array(12).fill(null);
      monthlyReturns.forEach((val, i) => { padded[i] = val; });
      monthlyReturns = padded;
    } else {
      monthlyReturns = monthlyReturns.slice(0, 12);
    }

    const ctx = canvas.getContext('2d');
    backtestModalCharts['monthly'] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: months,
        datasets: [{
          label: 'Return',
          data: monthlyReturns,
          backgroundColor: monthlyReturns.map(r => r >= 0 ? '#10B981' : '#EF4444'),
          borderRadius: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                const value = context.raw;
                return `Return: ${(value * 100).toFixed(1)}%`;
              }
            }
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#9CA3AF', font: { size: 10 } },
          },
          y: {
            grid: { color: 'rgba(128, 128, 128, 0.1)' },
            ticks: {
              color: '#9CA3AF',
              font: { size: 10 },
              callback: value => `${(value * 100).toFixed(0)}%`,
            },
          },
        },
      },
    });
  } catch (err) {
    console.error('Failed to render backtest returns chart:', err);
  }
}

function closeBacktestModal() {
  const modal = document.getElementById('backtest-modal');
  if (modal) modal.classList.add('hidden');

  // Clear content and cleanup charts
  const contentDiv = document.getElementById('backtest-modal-content');
  if (contentDiv) contentDiv.innerHTML = '';

  // Destroy charts
  if (backtestModalCharts['equity']) {
    backtestModalCharts['equity'].destroy();
    backtestModalCharts['equity'] = null;
  }
  if (backtestModalCharts['monthly']) {
    backtestModalCharts['monthly'].destroy();
    backtestModalCharts['monthly'] = null;
  }

  currentBacktestModalStrategy = null;
  currentBacktestModalId = null;
  if (lastFocusedElement) {
    lastFocusedElement.focus();
  }
}

// ==================== EDIT PARAMS & COPY STRATEGY MODALS ====================

let currentEditingName = null;

function openEditModal(name) {
  const strategy = strategies.find(s => s.name === name);
  if (!strategy) {
    console.error('Strategy not found for edit:', name);
    return;
  }

  currentEditingName = name;
  lastFocusedElement = document.activeElement;

  const textarea = document.getElementById('strategy-library-edit-params-modal-textarea');
  const errorDiv = document.getElementById('strategy-library-edit-params-modal-error');
  const modal = document.getElementById('strategy-library-edit-params-modal');

  const params = strategy.params || {};
  if (textarea) {
    textarea.value = JSON.stringify(params, null, 2);
    textarea.classList.remove('border-error');
  }

  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
  }

  if (modal) {
    modal.classList.remove('hidden');
    setTimeout(() => trapFocus(modal), 100);
  }
}

function closeEditModal() {
  const modal = document.getElementById('strategy-library-edit-params-modal');
  if (modal) modal.classList.add('hidden');

  const textarea = document.getElementById('strategy-library-edit-params-modal-textarea');
  if (textarea) {
    textarea.value = '';
    textarea.classList.remove('border-error');
  }

  const errorDiv = document.getElementById('strategy-library-edit-params-modal-error');
  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
  }

  currentEditingName = null;
  if (lastFocusedElement) {
    lastFocusedElement.focus();
  }
}

function openCopyModal(name) {
  const strategy = strategies.find(s => s.name === name);
  if (!strategy) {
    console.error('Strategy not found for copy:', name);
    return;
  }

  currentEditingName = name;
  lastFocusedElement = document.activeElement;

  const nameInput = document.getElementById('strategy-library-copy-strategy-modal-name');
  const symbolInput = document.getElementById('strategy-library-copy-strategy-modal-symbol');
  const descInput = document.getElementById('strategy-library-copy-strategy-modal-description');
  const errorDiv = document.getElementById('strategy-library-copy-strategy-modal-error');
  const modal = document.getElementById('strategy-library-copy-strategy-modal');

  if (nameInput) nameInput.value = '';
  if (symbolInput) symbolInput.value = strategy.symbol || '';
  if (descInput) descInput.value = '';
  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
  }

  if (modal) {
    modal.classList.remove('hidden');
    setTimeout(() => trapFocus(modal), 100);
  }
}

function closeCopyModal() {
  const modal = document.getElementById('strategy-library-copy-strategy-modal');
  if (modal) modal.classList.add('hidden');

  const nameInput = document.getElementById('strategy-library-copy-strategy-modal-name');
  const symbolInput = document.getElementById('strategy-library-copy-strategy-modal-symbol');
  const descInput = document.getElementById('strategy-library-copy-strategy-modal-description');
  const errorDiv = document.getElementById('strategy-library-copy-strategy-modal-error');

  if (nameInput) nameInput.value = '';
  if (symbolInput) symbolInput.value = '';
  if (descInput) descInput.value = '';
  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
  }

  currentEditingName = null;
  if (lastFocusedElement) {
    lastFocusedElement.focus();
  }
}

async function saveEditParams() {
  const textarea = document.getElementById('strategy-library-edit-params-modal-textarea');
  const errorDiv = document.getElementById('strategy-library-edit-params-modal-error');
  const modal = document.getElementById('strategy-library-edit-params-modal');
  const saveBtn = document.getElementById('strategy-library-edit-params-modal-save');

  if (!textarea || !currentEditingName) {
    console.error('Missing textarea or currentEditingName');
    return;
  }

  const raw = textarea.value.trim();

  if (!raw) {
    if (errorDiv) {
      errorDiv.textContent = 'Parameters cannot be empty';
      errorDiv.classList.remove('hidden');
      errorDiv.setAttribute('aria-live', 'assertive');
    }
    textarea.classList.add('border-error');
    textarea.focus();
    return;
  }

  let params;
  try {
    params = JSON.parse(raw);
    if (typeof params !== 'object' || params === null || Array.isArray(params)) {
      throw new Error('Parameters must be a JSON object');
    }
    if (errorDiv) {
      errorDiv.classList.add('hidden');
      errorDiv.setAttribute('aria-live', 'off');
    }
    textarea.classList.remove('border-error');
  } catch (e) {
    if (errorDiv) {
      errorDiv.textContent = `Invalid JSON: ${e.message}`;
      errorDiv.classList.remove('hidden');
      errorDiv.setAttribute('aria-live', 'assertive');
    }
    textarea.classList.add('border-error');
    textarea.focus();
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="material_symbols_outlined animate-spin">refresh</span> Saving...';
  }

  try {
    await window.apiFetch(`/api/v3/strategies/${currentEditingName}/params`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ params }),
    });

    flash('Parameters saved successfully', 'success');
    closeEditModal();
    await loadAll();
  } catch (err) {
    console.error('Failed to save params:', err);
    const errMsg = err.message || 'Unknown error';
    flash(`Failed to save parameters: ${errMsg}`, 'error');
    if (errorDiv) {
      errorDiv.textContent = `Failed to save: ${errMsg}`;
      errorDiv.classList.remove('hidden');
      errorDiv.setAttribute('aria-live', 'assertive');
    }
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  }
}

async function confirmCopyStrategy() {
  const nameInput = document.getElementById('strategy-library-copy-strategy-modal-name');
  const symbolInput = document.getElementById('strategy-library-copy-strategy-modal-symbol');
  const descInput = document.getElementById('strategy-library-copy-strategy-modal-description');
  const errorDiv = document.getElementById('strategy-library-copy-strategy-modal-error');
  const confirmBtn = document.getElementById('strategy-library-copy-strategy-modal-confirm');

  if (!nameInput || !currentEditingName) {
    console.error('Missing inputs or currentEditingName');
    return;
  }

  const newName = nameInput.value.trim();
  if (!newName) {
    if (errorDiv) {
      errorDiv.textContent = 'Strategy name is required';
      errorDiv.classList.remove('hidden');
      errorDiv.setAttribute('aria-live', 'assertive');
    }
    nameInput.classList.add('border-error');
    nameInput.focus();
    return;
  }

  const symbol = symbolInput.value.trim() || undefined;
  const description = descInput.value.trim() || undefined;

  nameInput.classList.remove('border-error');
  if (errorDiv) {
    errorDiv.classList.add('hidden');
    errorDiv.setAttribute('aria-live', 'off');
  }

  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<span class="material_symbols_outlined animate-spin">refresh</span> Creating...';
  }

  try {
    await window.apiFetch('/api/v3/strategies/copy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_name: currentEditingName,
        new_name: newName,
        symbol,
        description,
      }),
    });

    flash('Strategy copied successfully', 'success');
    closeCopyModal();
    await loadAll();
  } catch (err) {
    console.error('Failed to copy strategy:', err);
    const errMsg = err.message || 'Unknown error';
    flash(`Failed to copy strategy: ${errMsg}`, 'error');
    if (errorDiv) {
      errorDiv.textContent = `Failed to copy: ${errMsg}`;
      errorDiv.classList.remove('hidden');
      errorDiv.setAttribute('aria-live', 'assertive');
    }
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Create';
    }
  }
}

// ==================== MODAL EVENT HANDLING ====================

function closeAllModals() {
  closeEditModal();
  closeCopyModal();
  closeTradeModal();
  closeBacktestModal();
}

// ==================== EVENT HANDLERS ====================

function setupEventListeners() {
  // View toggles
  document.querySelectorAll('[data-view-toggle]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const view = e.currentTarget.dataset.viewToggle;
      if (['grid', 'table', 'evidence'].includes(view)) {
        setView(view);
      }
    });
    // Keyboard activation
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const view = e.currentTarget.dataset.viewToggle;
        if (['grid', 'table', 'evidence'].includes(view)) {
          setView(view);
        }
      }
    });
  });

  // Status filter buttons
  document.querySelectorAll('[data-status-filter]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const currentPressed = e.currentTarget.getAttribute('aria-pressed') === 'true';
      e.currentTarget.setAttribute('aria-pressed', !currentPressed);
      applyFilters();
    });
    // Keyboard activation
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const currentPressed = e.currentTarget.getAttribute('aria-pressed') === 'true';
        e.currentTarget.setAttribute('aria-pressed', !currentPressed);
        applyFilters();
      }
    });
  });

  // Tag filter buttons
  document.querySelectorAll('[data-tag]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const currentPressed = e.currentTarget.getAttribute('aria-pressed') === 'true';
      e.currentTarget.setAttribute('aria-pressed', !currentPressed);
      applyFilters();
    });
    // Keyboard activation
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const currentPressed = e.currentTarget.getAttribute('aria-pressed') === 'true';
        e.currentTarget.setAttribute('aria-pressed', !currentPressed);
        applyFilters();
      }
    });
  });

  // Clear filters
  document.getElementById('strategy-library-clear-filters')?.addEventListener('click', () => {
    // Clear search
    const searchInput = document.getElementById('strategy-library-search');
    if (searchInput) searchInput.value = '';

    // Reset asset class select
    const assetSelect = document.getElementById('strategy-library-asset-class');
    if (assetSelect) assetSelect.value = '';

    // Reset regime select
    const regimeSelect = document.getElementById('strategy-library-filter-regime');
    if (regimeSelect) regimeSelect.value = '';

    // Reset ML override checkbox
    const mlCheckbox = document.getElementById('strategy-library-ml-override');
    if (mlCheckbox) mlCheckbox.checked = false;

    // Deactivate all status filters
    document.querySelectorAll('[data-status-filter]').forEach(btn => {
      btn.setAttribute('aria-pressed', 'false');
      btn.classList.remove('bg-surface-container-high', 'border-primary');
      btn.classList.add('bg-surface', 'border-outline-variant');
    });

    // Deactivate all tag filters
    document.querySelectorAll('[data-tag]').forEach(btn => {
      btn.setAttribute('aria-pressed', 'false');
      btn.classList.remove('bg-surface-container-high', 'border-primary');
      btn.classList.add('bg-surface', 'border-outline-variant');
    });

    applyFilters();
  });

  // Search input
  document.getElementById('strategy-library-search')?.addEventListener('input', applyFilters);

  // Asset class and regime selects
  document.getElementById('strategy-library-asset-class')?.addEventListener('change', applyFilters);
  document.getElementById('strategy-library-filter-regime')?.addEventListener('change', applyFilters);

  // ML override checkbox
  document.getElementById('strategy-library-ml-override')?.addEventListener('change', applyFilters);

  // Strategy cards click (grid view) - with keyboard support
  document.getElementById('strategy-library-grid')?.addEventListener('click', (e) => {
    const card = e.target.closest('.strategy-card');
    if (card && !e.target.closest('button')) {
      openDetailPanel();
      // Delay to allow panel animation
      setTimeout(() => {
        const name = card.dataset.strategyName;
        if (name) openDetail(name);
      }, 50);
    }

    // Toggle active
    const toggle = e.target.closest('.strategy-toggle');
    if (toggle) {
      e.stopPropagation();
      const name = toggle.dataset.name;
      toggleStrategy(name, toggle.checked);
    }

    // Copy button
    const copyBtn = e.target.closest('.strategy-copy-btn');
    if (copyBtn) {
      e.stopPropagation();
      openCopyModal(copyBtn.dataset.name);
    }

    // Edit button
    const editBtn = e.target.closest('.strategy-edit-btn');
    if (editBtn) {
      e.stopPropagation();
      openEditModal(editBtn.dataset.name);
    }

    // Details button
    const detailsBtn = e.target.closest('.strategy-details-btn');
    if (detailsBtn) {
      e.stopPropagation();
      openDetail(detailsBtn.dataset.name);
    }
  });

  // Keyboard activation for strategy cards
  document.getElementById('strategy-library-grid')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const card = e.target.closest('.strategy-card');
      if (card) {
        e.preventDefault();
        openDetailPanel();
        setTimeout(() => {
          const name = card.dataset.strategyName;
          if (name) openDetail(name);
        }, 50);
      }
    }
  });

  // Table rows click
  document.getElementById('strategy-library-table-body')?.addEventListener('click', (e) => {
    const row = e.target.closest('.strategy-row');
    if (row && !e.target.closest('button') && !e.target.closest('input[type="checkbox"]')) {
      openDetailPanel();
      setTimeout(() => {
        const name = row.dataset.strategyName;
        if (name) openDetail(name);
      }, 50);
    }

    // Edit button
    const editBtn = e.target.closest('.strategy-edit-btn');
    if (editBtn) {
      e.stopPropagation();
      openEditModal(editBtn.dataset.name);
    }

    // Copy button
    const copyBtn = e.target.closest('.strategy-copy-btn');
    if (copyBtn) {
      e.stopPropagation();
      openCopyModal(copyBtn.dataset.name);
    }

    // Details button
    const detailsBtn = e.target.closest('.strategy-details-btn');
    if (detailsBtn) {
      e.stopPropagation();
      openDetail(detailsBtn.dataset.name);
    }

    // Toggle active
    const toggle = e.target.closest('.strategy-toggle');
    if (toggle) {
      e.stopPropagation();
      const name = toggle.dataset.name;
      toggleStrategy(name, toggle.checked);
    }
  });

  // Keyboard activation for table rows
  document.getElementById('strategy-library-table-body')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      const row = e.target.closest('.strategy-row');
      if (row) {
        e.preventDefault();
        openDetailPanel();
        setTimeout(() => {
          const name = row.dataset.strategyName;
          if (name) openDetail(name);
        }, 50);
      }
    }
  });

  // Close detail panel
  document.getElementById('strategy-library-detail-close')?.addEventListener('click', closeDetailPanel);

  // View All Trades button (in detail panel)
  document.getElementById('strategy-library-view-all-trades')?.addEventListener('click', () => {
    if (currentDetailName) {
      openTradeModal(currentDetailName);
    }
  });

  // Backtest details button (dynamic, added to DOM)
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('view-backtest-details-btn')) {
      e.stopPropagation();
      const backtestId = e.target.dataset.backtestId;
      if (currentDetailName && backtestId) {
        openBacktestModal(currentDetailName, backtestId);
      }
    }
  });

  // Edit modal events
  document.getElementById('strategy-library-edit-params-modal-save')?.addEventListener('click', saveEditParams);
  document.getElementById('strategy-library-edit-params-modal-textarea')?.addEventListener('input', () => {
    const errorDiv = document.getElementById('strategy-library-edit-params-modal-error');
    if (errorDiv) errorDiv.classList.add('hidden');
  });
  document.getElementById('strategy-library-edit-params-modal-cancel')?.addEventListener('click', closeEditModal);

  // Copy modal events
  document.getElementById('strategy-library-copy-strategy-modal-confirm')?.addEventListener('click', confirmCopyStrategy);
  document.getElementById('strategy-library-copy-strategy-modal-name')?.addEventListener('input', () => {
    const errorDiv = document.getElementById('strategy-library-copy-strategy-modal-error');
    if (errorDiv) errorDiv.classList.add('hidden');
  });
  document.getElementById('strategy-library-copy-strategy-modal-cancel')?.addEventListener('click', closeCopyModal);

  // Close modals on overlay click
  document.querySelectorAll('.strategy-library-modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeAllModals();
      }
    });
  });

  // Close modal buttons
  document.querySelectorAll('.modal-close, .modal-close-cancel').forEach(btn => {
    btn.addEventListener('click', closeAllModals);
  });

  // Strategy library header action buttons
  document.getElementById('strategy-library-header-edit-params')?.addEventListener('click', () => {
    if (currentDetailName) {
      openEditModal(currentDetailName);
    } else {
      flash('No strategy selected', 'error');
    }
  });

  document.getElementById('strategy-library-header-copy-strategy')?.addEventListener('click', () => {
    if (currentDetailName) {
      openCopyModal(currentDetailName);
    } else {
      flash('No strategy selected', 'error');
    }
  });

  // Settings section Edit Params button
  document.getElementById('strategy-library-edit-params-btn')?.addEventListener('click', () => {
    if (currentDetailName) {
      openEditModal(currentDetailName);
    } else {
      flash('No strategy selected', 'error');
    }
  });

  // Handle window resize for panel positioning
  window.addEventListener('resize', () => {
    const panel = document.getElementById('strategy-library-detail-panel');
    if (panel && !panel.classList.contains('hidden')) {
      // Panel will adjust via CSS media queries
    }
  });
}

async function toggleStrategy(name, isActive) {
  try {
    await window.apiFetch(`/api/v3/strategies/${name}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: isActive }),
    });
    flash(`Strategy ${isActive ? 'activated' : 'deactivated'}`, 'success');
    await loadAll();
  } catch (err) {
    console.error('Toggle failed:', err);
    flash('Failed to update strategy status', 'error');
    // Revert toggle state
    await loadAll();
  }
}

// ==================== HELPER FUNCTIONS ====================

function showLoadingInTab(tabId) {
  const section = document.getElementById(getSectionIdForTab(tabId));
  if (section) {
    const loader = section.querySelector('.strategy-library-loading-spinner');
    if (loader) loader.classList.remove('hidden');
  }
}

function hideLoadingInTab(tabId) {
  const section = document.getElementById(getSectionIdForTab(tabId));
  if (section) {
    const loader = section.querySelector('.strategy-library-loading-spinner');
    if (loader) loader.classList.add('hidden');
  }
}

function getSectionIdForTab(tabId) {
  const mapping = {
    'kpi': 'strategy-library-kpi-grid',
    'trades': 'strategy-library-trades-table',
    'backtests': 'strategy-library-backtests',
    'versions': 'strategy-library-versions',
    'evidence': 'strategy-library-evidence',
    'deployments': 'strategy-library-deployments'
  };
  return mapping[tabId] || tabId;
}

function showAlertInSection(sectionId, message) {
  const container = document.getElementById(sectionId);
  if (container) {
    const alert = document.createElement('div');
    alert.className = 'font-label-xs text-error text-center py-2';
    alert.setAttribute('role', 'alert');
    alert.setAttribute('aria-live', 'polite');
    alert.textContent = message;
    container.innerHTML = '';
    container.appendChild(alert);

    // Auto-hide after 5 seconds
    setTimeout(() => {
      if (alert.parentNode) alert.remove();
    }, 5000);
  }
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', init);

export { init, loadAll };
export default { init, loadAll };
