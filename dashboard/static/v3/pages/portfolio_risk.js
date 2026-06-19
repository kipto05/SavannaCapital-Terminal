/**
 * Portfolio Risk Monitor Page
 * Renders real-time risk metrics, positions, allocation, and alerts
 * Enhanced with improved error handling, backoff, concurrency guard, and status bar
 */

(function () {
  'use strict';

  // Color palette for asset classes
  const COLORS = {
    fx: '#00daf3',
    crypto: '#e9c400',
    equities: '#bcc7de',
    metals: '#ffecad',
    other: '#849396',
    positive: '#10B981',
    negative: '#EF4444',
    neutral: '#6B7280',
  };

  // State
  let lastData = null;
  let pollIntervalId = null;
  let pollInterval = 6000; // Default 6 seconds
  let isLoading = false;
  let errorCount = 0;
  let backoffUntil = 0;

  // Formatting helpers
  function fmt(n, dp = 0) {
    if (n === undefined || n === null || isNaN(n)) return '—';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toFixed(dp);
  }

  function fmtUSD(n) {
    if (n === undefined || n === null || isNaN(n)) return '$—';
    return '$' + fmt(n, 0);
  }

  function severityIcon(sev) {
    if (sev === 'error') return '<span class="material-symbols-outlined text-error text-[18px]">warning</span>';
    if (sev === 'warning') return '<span class="material-symbols-outlined text-tertiary text-[18px]">priority_high</span>';
    return '<span class="material-symbols-outlined text-outline text-[18px]">info</span>';
  }

  function severityClass(sev) {
    if (sev === 'error') return 'text-error';
    if (sev === 'warning') return 'text-tertiary';
    return 'text-outline';
  }

  // Status bar control
  function showStatus(message, type = 'error') {
    const bar = document.getElementById('risk-status-bar');
    if (bar) {
      bar.textContent = message;
      // Simple styling: default error styling; could be enhanced for type
      bar.className = 'px-4 py-2 bg-error/10 border-b border-error text-error text-sm';
      bar.classList.remove('hidden');
    }
  }

  function hideStatus() {
    const bar = document.getElementById('risk-status-bar');
    if (bar) {
      bar.classList.add('hidden');
    }
  }

  // API fetch wrapper with backoff and concurrency guard
  async function loadData() {
    const now = Date.now();
    if (isLoading) {
      // Already a fetch in progress, return cached data if available
      return lastData;
    }
    if (now < backoffUntil) {
      // Still in backoff period
      const remaining = Math.ceil((backoffUntil - now) / 1000);
      showStatus(`Connection in backoff – retrying in ${remaining}s`, 'error');
      return lastData;
    }

    try {
      isLoading = true;
      const response = await window.apiFetch('/api/v3/risk/overview');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      // Success: reset error count and backoff
      errorCount = 0;
      backoffUntil = 0;
      hideStatus();
      return data;
    } catch (err) {
      errorCount++;
      // Exponential backoff: 2^errorCount seconds, capped at 30 seconds
      const delay = Math.min(30000, 1000 * Math.pow(2, errorCount - 1));
      backoffUntil = Date.now() + delay;
      console.warn('PortfolioRisk: loadData failed (errorCount=' + errorCount + '):', err);
      const remaining = Math.ceil(delay / 1000);
      showStatus(`Error fetching risk data – retrying in ${remaining}s (attempt ${errorCount})`, 'error');
      // Return cached data if available to keep UI somewhat updated
      return lastData;
    } finally {
      isLoading = false;
    }
  }

  // Data validation (lightweight check)
  function isValidRiskData(d) {
    if (!d || typeof d !== 'object') return false;
    // Check for presence of expected top-level fields; they can be empty arrays/objects but should exist
    return ('kpis' in d) && ('positions' in d) && ('asset_allocation' in d) &&
           ('strategy_exposure_usd' in d) && ('correlation' in d) && ('alerts' in d);
  }

  // Render KPIs
  function renderKPIs(d) {
    if (!d || !d.kpis) {
      ['kpi-daily-dd', 'kpi-weekly-dd', 'kpi-exposure', 'kpi-var', 'kpi-margin'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
          el.textContent = '—';
          el.className = 'font-data-lg text-data-lg text-outline';
        }
      });
      // Also reset margin bar
      const bar = document.getElementById('bar-margin');
      if (bar) bar.style.width = '0%';
      return;
    }

    const k = d.kpis;

    const ddEl = document.getElementById('kpi-daily-dd');
    if (ddEl) {
      const val = k.daily_dd_pct || 0;
      ddEl.textContent = val.toFixed(2) + '%';
      ddEl.className = 'font-data-lg text-data-lg ' + (val < 0 ? 'text-error' : 'text-primary-fixed-dim');
    }

    const wdEl = document.getElementById('kpi-weekly-dd');
    if (wdEl) {
      const val = k.weekly_dd_pct || 0;
      wdEl.textContent = val.toFixed(2) + '%';
      wdEl.className = 'font-data-lg text-data-lg ' + (val < 0 ? 'text-error' : 'text-primary-fixed-dim');
    }

    const expEl = document.getElementById('kpi-exposure');
    if (expEl) {
      expEl.textContent = fmtUSD(k.total_exposure_usd || 0);
    }

    const varEl = document.getElementById('kpi-var');
    const varPctEl = document.getElementById('kpi-var-pct');
    if (varEl) {
      varEl.textContent = fmtUSD(k.var_95_1d_usd || 0);
      varEl.className = 'font-data-lg text-data-lg text-on-surface';
    }
    if (varPctEl) {
      if ((k.total_exposure_usd || 0) > 0) {
        varPctEl.textContent = (((k.var_95_1d_usd || 0) / k.total_exposure_usd) * 100).toFixed(2) + '% NAV';
      } else {
        varPctEl.textContent = '—';
      }
    }

    const marginEl = document.getElementById('kpi-margin');
    const marginBar = document.getElementById('bar-margin');
    if (marginEl) {
      const val = k.margin_usage_pct || 0;
      marginEl.textContent = val.toFixed(1) + '%';
      marginEl.className = 'font-data-lg text-data-lg ' + (val > 70 ? 'text-error' : 'text-tertiary');
    }
    if (marginBar) {
      marginBar.style.width = Math.min(k.margin_usage_pct || 0, 100) + '%';
    }
  }

  // Render Positions Table
  function renderPositions(d) {
    const tbody = document.getElementById('positions-tbl');
    const countEl = document.getElementById('positions-count');
    if (!tbody || !countEl) return;

    if (!d || !d.positions || d.positions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="px-4 py-6 text-center text-outline">No open positions</td></tr>';
      countEl.textContent = '0 positions';
      return;
    }

    // Apply sorting
    const sortBy = document.getElementById('sortSelect') ? document.getElementById('sortSelect').value : 'exposure_desc';
    let sortedPositions = [...d.positions];

    sortedPositions.sort((a, b) => {
      switch (sortBy) {
        case 'exposure_desc':
          return (b.exposure_usd || 0) - (a.exposure_usd || 0);
        case 'exposure_asc':
          return (a.exposure_usd || 0) - (b.exposure_usd || 0);
        case 'concentration_desc':
          return (b.concentration_pct || 0) - (a.concentration_pct || 0);
        case 'risk_desc':
          return (b.risk_score || 0) - (a.risk_score || 0);
        default:
          return 0;
      }
    });

    countEl.textContent = sortedPositions.length + ' positions';

    const rows = sortedPositions.map(p => {
      const pnl = p.pnl || 0;
      const pnlC = pnl > 0 ? 'text-primary-fixed-dim' : pnl < 0 ? 'text-error' : 'text-outline';
      const sideC = p.dir === 'Long' ? 'text-primary-fixed-dim' : 'text-error';
      // risk_pct > 5% as error
      const riskC = (p.risk_pct || 0) > 5 ? 'text-error' : 'text-on-surface';

      return `<tr class="hover:bg-surface-container-high transition-colors">
        <td class="px-4 py-2 font-mono text-[10px]">${escapeHtml(p.account || '—')}</td>
        <td class="px-4 py-2 font-mono font-medium text-primary text-[10px]">${escapeHtml(p.symbol)}</td>
        <td class="px-4 py-2 text-[10px]" style="color:${sideC}">${escapeHtml(p.dir)}</td>
        <td class="px-4 py-2 text-right font-mono text-[10px]">${(p.entry || 0).toFixed(5)}</td>
        <td class="px-4 py-2 text-right font-mono text-[10px]">${(p.price || 0).toFixed(5)}</td>
        <td class="px-4 py-2 text-right font-mono text-[10px]">${(p.size || 0).toFixed(2)}</td>
        <td class="px-4 py-2 text-center font-mono text-outline text-label-sm">
          ${p.sl ? p.sl.toFixed(5) : '—'} / ${p.tp ? p.tp.toFixed(5) : '—'}
        </td>
        <td class="px-4 py-2 text-right font-mono ${pnlC} text-[10px]">${pnl.toFixed(2)}</td>
        <td class="px-4 py-2 text-right font-mono text-[10px] ${riskC}">${(p.risk_pct || 0).toFixed(2)}%</td>
      </tr>`;
    }).join('');

    tbody.innerHTML = rows;
  }

  // Render Asset Allocation Donut
  function renderAlloc(d) {
    const alloc = d ? (d.asset_allocation || {}) : {};
    const entries = Object.entries(alloc).filter(e => e[1] > 0);
    const grossEl = document.getElementById('alloc-gross');
    const legendEl = document.getElementById('alloc-legend');
    const canvas = document.getElementById('alloc-canvas');

    if (!grossEl || !legendEl || !canvas) return;

    if (!entries.length) {
      grossEl.textContent = '$0';
      legendEl.innerHTML = '<div class="text-[10px] text-outline text-center">No allocation data</div>';
      return;
    }

    // Show gross exposure from KPIs if available
    if (d && d.kpis && d.kpis.total_exposure_usd !== undefined) {
      grossEl.textContent = fmtUSD(d.kpis.total_exposure_usd);
    } else {
      grossEl.textContent = '$0';
    }

    // Draw donut
    try {
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        console.warn('PortfolioRisk: Canvas context not available');
        return;
      }

      const cx = 64, cy = 64, r = 54, lw = 16;
      ctx.clearRect(0, 0, 128, 128);
      const total = entries.reduce((sum, e) => sum + e[1], 0) || 1;
      let start = -Math.PI / 2;

      entries.forEach(e => {
        const sweep = (e[1] / total) * 2 * Math.PI;
        ctx.beginPath();
        ctx.arc(cx, cy, r, start, start + sweep);
        ctx.strokeStyle = COLORS[e[0]] || COLORS.other;
        ctx.lineWidth = lw;
        ctx.lineCap = 'round';
        ctx.stroke();
        start += sweep;
      });
    } catch (err) {
      console.error('PortfolioRisk: Error rendering allocation chart:', err);
    }

    // Legend
    legendEl.innerHTML = entries.map(e => `
      <div class="flex items-center justify-between text-[11px]">
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full" style="background:${COLORS[e[0]] || COLORS.other}"></div>
          ${escapeHtml(e[0].charAt(0).toUpperCase() + e[0].slice(1))}
        </div>
        <span class="font-data-md">${e[1].toFixed(1)}%</span>
      </div>
    `).join('');
  }

  // Render Strategy Exposure Bars
  function renderStratExp(d) {
    const box = document.getElementById('strat-bars');
    if (!box) return;

    if (!d || !d.strategy_exposure_usd || !Object.keys(d.strategy_exposure_usd).length) {
      box.innerHTML = '<div class="text-[10px] text-on-surface-variant text-center py-4">No data</div>';
      return;
    }

    const entries = Object.entries(d.strategy_exposure_usd);
    const max = Math.max(...entries.map(e => e[1]));

    box.innerHTML = entries.map(e => {
      const pct = max > 0 ? (e[1] / max * 100) : 0;
      return `<div>
        <div class="flex items-center justify-between text-[10px] mb-1">
          <span class="uppercase">${escapeHtml(e[0].replace(/_/g, ' '))}</span>
          <span class="text-primary-fixed-dim">${fmtUSD(e[1])}</span>
        </div>
        <div class="w-full h-1.5 bg-surface-container-highest rounded-full">
          <div class="h-full bg-primary-fixed-dim rounded-full" style="width:${pct.toFixed(1)}%"></div>
        </div>
      </div>`;
    }).join('');
  }

  // Render Correlation Matrix
  function renderCorrelation(d) {
    const emptyEl = document.getElementById('corr-empty');
    const headersEl = document.getElementById('corr-headers');
    const bodyEl = document.getElementById('corr-body');
    const gridEl = document.getElementById('corr-grid');

    if (!emptyEl || !headersEl || !bodyEl || !gridEl) return;

    if (!d || !d.correlation || !d.correlation.labels || d.correlation.labels.length < 2) {
      emptyEl.style.display = '';
      headersEl.innerHTML = '';
      bodyEl.innerHTML = '';
      return;
    }

    emptyEl.style.display = 'none';
    const { labels, matrix } = d.correlation;
    const n = labels.length;

    gridEl.style.gridTemplateColumns = `repeat(${n}, 1fr)`;
    gridEl.style.gridTemplateRows = `repeat(${n}, auto)`;

    // Headers row
    headersEl.innerHTML = labels.map(l =>
      `<div class="text-[9px] uppercase text-center text-on-surface-variant flex items-center justify-center">${escapeHtml(l)}</div>`
    ).join('');

    // Body rows
    let bodyHtml = '';
    labels.forEach((lbl, i) => {
      bodyHtml += `<div class="text-[9px] uppercase text-on-surface-variant flex items-center">${escapeHtml(lbl)}</div>`;
      if (matrix[i]) {
        matrix[i].forEach((v, j) => {
          let cls = 'flex items-center justify-center text-[10px]';
          if (i === j) {
            cls += ' bg-primary-container/40 font-bold';
          } else if (Math.abs(v) > 0.5) {
            cls += v > 0 ? ' bg-error/30 text-error font-bold' : ' bg-primary-container/40';
          } else {
            cls += ' bg-surface-container-highest';
          }
          bodyHtml += `<div class="${cls}">${(i === j ? 1.0 : v).toFixed(2)}</div>`;
        });
      } else {
        bodyHtml += labels.map(() => `<div class="flex items-center justify-center text-[10px] bg-surface-container-highest">—</div>`).join('');
      }
    });
    bodyEl.innerHTML = bodyHtml;
  }

  // Render Risk Alerts
  function renderAlerts(d) {
    const listEl = document.getElementById('alerts-list');
    const countEl = document.getElementById('alerts-count');
    if (!listEl || !countEl) return;

    if (!d || !d.alerts || d.alerts.length === 0) {
      listEl.innerHTML = '<div class="p-4 text-[10px] text-on-surface-variant text-center">No alerts</div>';
      countEl.textContent = '0';
      return;
    }

    countEl.textContent = d.alerts.length;

    listEl.innerHTML = d.alerts.map(a => `
      <div class="p-2 flex gap-3 hover:bg-surface-container-high cursor-pointer transition-colors">
        ${severityIcon(a.severity)}
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-bold ${severityClass(a.severity)} uppercase">${escapeHtml(a.symbol)}</span>
            <span class="text-[9px] text-on-surface-variant">${a.ts ? a.ts.split('T')[1].split('.')[0] : ''}</span>
          </div>
          <p class="text-[11px] leading-tight mt-1 text-on-surface-variant">${escapeHtml(a.message)}</p>
        </div>
      </div>
    `).join('');
  }

  // Export to CSV
  function exportToCSV(d) {
    if (!d || !d.positions || d.positions.length === 0) {
      alert('No data to export');
      return;
    }

    const headers = ['Symbol', 'Account', 'Direction', 'Entry', 'Current Price', 'Size', 'SL', 'TP', 'Unrealized P&L', 'Risk %', 'Exposure USD', 'Concentration %'];
    const rows = d.positions.map(p => [
      p.symbol,
      p.account || '',
      p.dir || '',
      p.entry || 0,
      p.price || 0,
      p.size || 0,
      p.sl || '',
      p.tp || '',
      p.pnl || 0,
      p.risk_pct || 0,
      p.exposure_usd || 0,
      p.concentration_pct || 0
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => typeof cell === 'string' ? `"${cell}"` : cell).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `portfolio_risk_export_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  // Setup sort handler
  function setupSortHandler() {
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
      sortSelect.addEventListener('change', () => {
        if (lastData) {
          renderAll(lastData);
        }
      });
    }
  }

  // Setup export button
  function setupExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        if (lastData) {
          exportToCSV(lastData);
        } else {
          alert('No data available to export');
        }
      });
    }
  }

  // Setup refresh button
  function setupRefreshButton() {
    const btn = document.getElementById('risk-refresh-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        tick().finally(() => {
          btn.classList.remove('opacity-50', 'cursor-not-allowed');
        });
      });
    }
  }

  // Main render dispatcher with data validation
  function renderAll(d) {
    // Validate data structure before rendering
    if (!d || typeof d !== 'object') {
      console.warn('PortfolioRisk: Invalid data format', d);
      showStatus('Invalid data format received', 'error');
      return;
    }

    // Ensure expected top-level keys exist (use empty defaults if missing)
    const safe = {
      kpis: d.kpis || {},
      positions: Array.isArray(d.positions) ? d.positions : [],
      asset_allocation: typeof d.asset_allocation === 'object' ? d.asset_allocation : {},
      strategy_exposure_usd: typeof d.strategy_exposure_usd === 'object' ? d.strategy_exposure_usd : {},
      correlation: d.correlation || { labels: [], matrix: [] },
      alerts: Array.isArray(d.alerts) ? d.alerts : []
    };

    // Use safe data for rendering
    lastData = d;
    renderKPIs(d);
    renderPositions(d);
    renderAlloc(d);
    renderStratExp(d);
    renderCorrelation(d);
    renderAlerts(d);
  }

  // Polling tick
  function tick() {
    return loadData().then(d => {
      if (d) {
        renderAll(d);
      }
    }).catch(err => {
      console.error('PortfolioRisk: tick failed:', err);
    });
  }

  function startPolling() {
    if (pollIntervalId) clearInterval(pollIntervalId);
    pollIntervalId = setInterval(tick, pollInterval);
  }

  function stopPolling() {
    if (pollIntervalId) {
      clearInterval(pollIntervalId);
      pollIntervalId = null;
    }
  }

  // Read config for poll interval
  if (window.config && window.config.dashboard && window.config.dashboard.poll_interval_ms) {
    pollInterval = window.config.dashboard.poll_interval_ms;
  }

  // Initialize
  function init() {
    setupRefreshButton();
    setupExportButton();
    setupSortHandler();
    tick();
    startPolling();

    // Cleanup on page unload
    window.addEventListener('beforeunload', stopPolling);

    // Pause polling when page hidden to save resources
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopPolling();
      } else {
        tick();
        startPolling();
      }
    });
  }

  // XSS protection
  function escapeHtml(str) {
    if (str === undefined || str === null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();