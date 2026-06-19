(function() {
  'use strict';

  // ============================================================================
  // COLORS PALETTE — Material Design 3 semantic tokens
  // ============================================================================
  const COLORS = {
    primary: '#c3f5ff',
    primaryContainer: '#00e5ff',
    onSurface: '#e0e2ea',
    onSurfaceVariant: '#bac9cc',
    outlineVariant: '#3b494c',
    surfaceContainer: '#1c2025',
    surfaceContainerHigh: '#23282d',
    error: '#ffb4ab',
    errorContainer: '#93000a',
    success: '#4ade80',
    warning: '#fbbf24',
    chart: {
      crypto: '#a855f7',
      fx: '#00e5ff',
      equities: '#fbbf24',
      metals: '#ffd700',
      fixedIncome: '#34d399'
    }
  };

  // ============================================================================
  // STATE
  // ============================================================================
  let state = {
    lastData: null,
    pollIntervalId: null,
    isLoading: false,
    errorCount: 0,
    backoffUntil: null,
    sortState: { column: 'var', direction: 'desc' },
    donutChart: null,
    stressChart: null,
    filters: { status: 'All', timeframe: 'All', assetClass: 'All' }
  };

  // ============================================================================
  // MOCK DATA
  // ============================================================================
  const MOCK_DATA = {
    overview: {
      var_95_1d_usd: 8421,
      beta: 1.23,
      margin_usage_pct: 45.2,
      net_pnl: 12500,
      var_pct_change: 0.5,
      margin_limit: 500000,
      net_pnl_pct: 1.5,
      var_breakdown: { crypto: 3000, fx: 2500, equities: 2000, metals: 920, fixed_income: 1 }
    },
    strategies: [
      { name: 'Momentum Reversion', symbol: 'BTCUSD', timeframe: 'M15', status: 'Active', asset_class: 'crypto', var_pct: 2.4, exposure_k: 50, max_dd_pct: 4.2, sharpe: 2.84, win_rate: 0.68 },
      { name: 'Band Reversion', symbol: 'EURUSD', timeframe: 'M15', status: 'Active', asset_class: 'fx', var_pct: 1.8, exposure_k: 35, max_dd_pct: 3.1, sharpe: 1.92, win_rate: 0.62 },
      { name: 'Stochastic Trend', symbol: 'GBPUSD', timeframe: 'M15', status: 'Paused', asset_class: 'fx', var_pct: 2.1, exposure_k: 25, max_dd_pct: 3.8, sharpe: 1.45, win_rate: 0.56 },
      { name: 'Session Breakout', symbol: 'XAUUSD', timeframe: 'M15', status: 'Active', asset_class: 'metals', var_pct: 1.5, exposure_k: 30, max_dd_pct: 2.9, sharpe: 2.21, win_rate: 0.64 },
      { name: 'Divergence Swing', symbol: 'XAGUSD', timeframe: 'M15', status: 'Inactive', asset_class: 'metals', var_pct: 2.6, exposure_k: 0, max_dd_pct: 4.5, sharpe: 0.00, win_rate: 0.00 },
      { name: 'VWAP Reversion', symbol: 'AAPL', timeframe: 'M5', status: 'Active', asset_class: 'equities', var_pct: 1.2, exposure_k: 20, max_dd_pct: 2.2, sharpe: 2.56, win_rate: 0.67 },
      { name: 'MACD Impulse', symbol: 'TSLA', timeframe: 'M15', status: 'Active', asset_class: 'equities', var_pct: 1.9, exposure_k: 22, max_dd_pct: 3.5, sharpe: 1.73, win_rate: 0.59 }
    ],
    alerts: [
      { id: 1, severity: 'warning', message: 'High concentration in BTC (42%)', symbol: 'BTC', timestamp: new Date().toISOString() },
      { id: 2, severity: 'info', message: 'Daily DD approaching 2% limit', symbol: 'PORTFOLIO', timestamp: new Date().toISOString() },
      { id: 3, severity: 'error', message: 'Position limit exceeded on BTCUSD', symbol: 'BTCUSD', timestamp: new Date().toISOString() }
    ],
    stressTests: [
      { id: 1, scenario: 'Market Crash (-20%)', impact_pct: -12.5, name: 'Market Crash (-20%)', value: -12.5 },
      { id: 2, scenario: 'Volatility Spike (+50%)', impact_pct: -8.3, name: 'Volatility Spike (+50%)', value: -8.3 },
      { id: 3, scenario: 'Liquidity Crisis', impact_pct: -5.2, name: 'Liquidity Crisis', value: -5.2 },
      { id: 4, scenario: 'Rate Hike Shock', impact_pct: -3.1, name: 'Rate Hike Shock', value: -3.1 }
    ],
    complianceEvents: [
      { id: 1, time: new Date().toISOString(), event: 'Position limit exceeded on BTCUSD', status: 'Breach' },
      { id: 2, time: new Date(Date.now()-3600000).toISOString(), event: 'Daily loss threshold 80% reached', status: 'Warning' },
      { id: 3, time: new Date(Date.now()-7200000).toISOString(), event: 'Margin call warning', status: 'OK' },
      { id: 4, time: new Date(Date.now()-10800000).toISOString(), event: 'Max drawdown threshold alert', status: 'OK' }
    ]
  };

  // ============================================================================
  // UTILITIES
  // ============================================================================
  function fmt(n, dp = 2) {
    if (typeof n !== 'number' || isNaN(n)) return '—';
    return n.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }

  function fmtUSD(n) {
    if (typeof n !== 'number' || isNaN(n)) return '—';
    const abs = Math.abs(n);
    if (abs >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return '$' + (n / 1e3).toFixed(2) + 'K';
    return '$' + n.toFixed(2);
  }

  function fmtPct(n) {
    if (typeof n !== 'number' || isNaN(n)) return '—';
    return (n * 100).toFixed(2) + '%';
  }

  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatTime(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  }

  function severityIcon(sev) {
    switch (sev?.toLowerCase()) {
      case 'error':
      case 'breach':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'info';
    }
  }

  function severityClass(sev) {
    switch (sev?.toLowerCase()) {
      case 'error':
      case 'breach':
        return 'bg-error/20 text-error';
      case 'warning':
        return 'bg-warning/20 text-warning';
      default:
        return 'bg-success/20 text-success';
    }
  }

  function statusClass(status) {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'bg-success/20 text-success';
      case 'paused':
        return 'bg-warning/20 text-warning';
      case 'inactive':
        return 'bg-surface-variant text-on-surface-variant';
      default:
        return 'bg-surface-variant text-on-surface-variant';
    }
  }

  function impactClass(impactPct) {
    return impactPct >= 0 ? 'text-success' : 'text-error';
  }

  // ============================================================================
  // SORTING
  // ============================================================================
  function getSortedStrategies(strategies) {
    // Apply filters
    let filtered = strategies;
    const { status, timeframe, assetClass } = state.filters;

    if (status !== 'All') {
      filtered = filtered.filter(s => s.status === status);
    }
    if (timeframe !== 'All') {
      filtered = filtered.filter(s => s.timeframe === timeframe);
    }
    if (assetClass !== 'All') {
      filtered = filtered.filter(s => s.asset_class === assetClass);
    }

    // Sort the filtered array
    const sorted = [...filtered];
    const { column, direction } = state.sortState;
    sorted.sort((a, b) => {
      let valA, valB;
      switch (column) {
        case 'name':
          valA = a.name?.toLowerCase() || '';
          valB = b.name?.toLowerCase() || '';
          return direction === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        case 'var':
          valA = a.var_pct || 0;
          valB = b.var_pct || 0;
          break;
        case 'exposure_k':
          valA = a.exposure_k || 0;
          valB = b.exposure_k || 0;
          break;
        case 'max_dd':
          valA = a.max_dd_pct || 0;
          valB = b.max_dd_pct || 0;
          break;
        case 'sharpe':
          valA = a.sharpe || 0;
          valB = b.sharpe || 0;
          break;
        case 'win_rate':
          valA = a.win_rate || 0;
          valB = b.win_rate || 0;
          break;
        default:
          return 0;
      }
      return direction === 'asc' ? valA - valB : valB - valA;
    });
    return sorted;
  }

  // ============================================================================
  // CSV EXPORT
  // ============================================================================
  function exportCsv() {
    const data = state.lastData;
    if (!data || !Array.isArray(data.strategies) || data.strategies.length === 0) {
      console.warn('No strategy data available for export');
      showStatus?.('No data to export', 'warning');
      return;
    }

    const strategies = getSortedStrategies(data.strategies);
    const headers = ['Strategy', 'Symbol', 'Timeframe', 'Status', 'VaR %', 'Exposure ($K)', 'Max DD %', 'Sharpe', 'Win Rate %'];

    // Helper function to sanitize string fields for CSV export
    // 1. HTML escape to prevent XSS when opened in spreadsheet apps
    // 2. Formula injection protection: prefix with single quote if starts with =, +, -, @
    // 3. CSV quoting: wrap in double quotes if contains comma, newline, or quote; double internal quotes
    const sanitizeForCsv = (rawValue) => {
      if (rawValue == null) return '';
      let str = String(rawValue);

      // HTML escaping
      str = escapeHtml(str);

      // Formula injection protection
      if (/^[=+\-@]/.test(str)) {
        str = "'" + str;
      }

      // CSV quoting: if contains comma, newline, or quote, wrap in quotes and escape internal quotes
      if (str.includes(',') || str.includes('\n') || str.includes('\r') || str.includes('"')) {
        str = '"' + str.replace(/"/g, '""') + '"';
      }

      return str;
    };

    const rows = strategies.map(s => {
      // String fields (sanitize with HTML escape, formula protection, CSV escaping)
      const name = sanitizeForCsv(s.name);
      const symbol = sanitizeForCsv(s.symbol);
      const timeframe = sanitizeForCsv(s.timeframe);
      const status = sanitizeForCsv(s.status);

      // Numeric fields (keep as-is, no HTML escaping needed)
      const varPct = fmtPct(s.var_pct);
      const exposure = fmtUSD(s.exposure_k * 1000);
      const maxDd = fmtPct(s.max_dd_pct);
      const sharpe = s.sharpe != null ? s.sharpe.toFixed(2) : '—';
      // Win Rate: one decimal place, not two like fmtPct
      const winRate = s.win_rate != null ? (s.win_rate * 100).toFixed(1) + '%' : '—';

      return [
        name,
        symbol,
        timeframe,
        status,
        varPct,
        exposure,
        maxDd,
        sharpe,
        winRate
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\n');
    // Prepend BOM for UTF-8 so Excel opens correctly
    const blob = new Blob(['﻿', csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'strategy_risk_metrics.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('CSV exported:', strategies.length, 'rows');
  }

  // ============================================================================
  // STATUS BAR
  // ============================================================================
  function showStatus(message, type = 'error') {
    const bar = document.getElementById('risk-status-bar');
    if (!bar) return;
    bar.textContent = message;
    bar.classList.remove('hidden');
    bar.className = 'px-4 py-2 border-b';
    if (type === 'error') {
      bar.classList.add('bg-error/10', 'border-error', 'text-error');
    } else if (type === 'success') {
      bar.classList.add('bg-success/10', 'border-success', 'text-success');
    } else {
      bar.classList.add('bg-warning/10', 'border-warning', 'text-warning');
    }
  }

  function hideStatus() {
    const bar = document.getElementById('risk-status-bar');
    if (bar) bar.classList.add('hidden');
  }

  // ============================================================================
  // DATA LOADING
  // ============================================================================
  async function loadData() {
    if (state.isLoading) {
      return state.lastData;
    }

    const useMock = window.USE_MOCKS || window.location.search.includes('mock=1');

    if (useMock) {
      await new Promise(r => setTimeout(r, 300));
      state.errorCount = 0;
      state.backoffUntil = null;
      hideStatus();
      return MOCK_DATA;
    }

    state.isLoading = true;

    try {
      const [overviewRes, strategiesRes, alertsRes, stressRes, complianceRes] = await Promise.all([
        window.apiFetch('/api/v3/risk/overview'),
        window.apiFetch('/api/v3/risk/strategies'),
        window.apiFetch('/api/v3/risk/alerts'),
        window.apiFetch('/api/v3/risk/stress-tests'),
        window.apiFetch('/api/v3/risk/compliance')
      ]).then(resps => resps.map(r => r.ok ? r.json() : Promise.reject(r.statusText)));

      state.isLoading = false;
      state.errorCount = 0;
      state.backoffUntil = null;
      hideStatus();

      return {
        overview: overviewRes.data || overviewRes,
        strategies: strategiesRes.data || strategiesRes,
        alerts: alertsRes.data || alertsRes,
        stressTests: stressRes.data || stressRes,
        complianceEvents: complianceRes.data || complianceRes
      };
    } catch (err) {
      state.isLoading = false;
      state.errorCount++;
      const backoffMs = Math.min(30000, 1000 * Math.pow(2, state.errorCount - 1));
      state.backoffUntil = Date.now() + backoffMs;

      showStatus(`API error (${err.message}), retrying in ${Math.ceil(backoffMs/1000)}s`, 'error');
      console.warn('loadData error:', err);

      // Return last known good data or empty fallback
      return state.lastData || {
        overview: MOCK_DATA.overview,
        strategies: [],
        alerts: [],
        stressTests: [],
        complianceEvents: []
      };
    }
  }

  // ============================================================================
  // VALIDATION
  // ============================================================================
  function isValidRiskData(d) {
    return d &&
           d.overview &&
           Array.isArray(d.strategies) &&
           Array.isArray(d.alerts) &&
           Array.isArray(d.stressTests) &&
           Array.isArray(d.complianceEvents);
  }

  // ============================================================================
  // RENDERING — KPIs
  // ============================================================================
  function renderKPIs(data) {
    const { overview } = data;
    if (!overview) return;

    // VaR
    const varEl = document.getElementById('kpi-var');
    const varPctEl = document.getElementById('kpi-var-pct');
    if (varEl) varEl.textContent = fmtUSD(overview.var_95_1d_usd);
    if (varPctEl) {
      // Assuming var_breakdown total is the VaR denominator; show percentage of portfolio
      const totalVar = Object.values(overview.var_breakdown || {}).reduce((a, b) => a + b, 0);
      varPctEl.textContent = totalVar > 0 ? fmtPct(totalVar / 100000) : '—'; // placeholder calc
    }

    // Beta
    const betaEl = document.getElementById('kpi-beta');
    if (betaEl) betaEl.textContent = overview.beta?.toFixed(2) || '—';

    // Margin Usage
    const marginEl = document.getElementById('kpi-margin');
    const barEl = document.getElementById('bar-margin');
    if (marginEl) marginEl.textContent = (overview.margin_usage_pct || 0).toFixed(1) + '%';
    if (barEl) {
      barEl.style.width = Math.min(overview.margin_usage_pct || 0, 100) + '%';
      barEl.className = `h-full rounded-full ${overview.margin_usage_pct > 80 ? 'bg-error' : 'bg-tertiary'}`;
    }

    // Net PnL
    const pnlEl = document.getElementById('kpi-pnl');
    if (pnlEl) {
      pnlEl.textContent = fmtUSD(overview.net_pnl);
      pnlEl.className = 'font-data-lg text-data-lg ' + (overview.net_pnl >= 0 ? 'text-success' : 'text-error');
    }
  }

  // ============================================================================
  // RENDERING — Strategy Table
  // ============================================================================
  function renderTable(data) {
    const tbody = document.getElementById('strategy-risk-tbody');
    if (!tbody) return;

    const strategies = getSortedStrategies(data.strategies);

    // Build rows
    tbody.innerHTML = strategies.map(s => `
      <tr data-symbol="${escapeHtml(s.symbol)}">
        <td class="px-4 py-2 font-data-md text-on-surface">${escapeHtml(s.name)}</td>
        <td class="px-4 py-2 font-data-md text-on-surface">${escapeHtml(s.symbol)}</td>
        <td class="px-4 py-2 font-data-md text-on-surface">${escapeHtml(s.timeframe)}</td>
        <td class="px-4 py-2 text-center">
          <span class="px-2 py-0.5 rounded text-[10px] font-label-sm ${statusClass(s.status)}">${escapeHtml(s.status)}</span>
        </td>
        <td class="px-4 py-2 text-right font-data-md text-on-surface">${fmtPct(s.var_pct)}</td>
        <td class="px-4 py-2 text-right font-data-md text-on-surface">${fmtUSD(s.exposure_k * 1000)}</td>
        <td class="px-4 py-2 text-right font-data-md text-on-surface">${fmtPct(s.max_dd_pct)}</td>
        <td class="px-4 py-2 text-right font-data-md text-on-surface">${s.sharpe?.toFixed(2) || '—'}</td>
        <td class="px-4 py-2 text-right font-data-md text-on-surface">${s.win_rate ? (s.win_rate * 100).toFixed(1) + '%' : '—'}</td>
        <td class="px-4 py-2 text-center">
          <button class="material-symbols-outlined text-[18px] text-on-surface-variant hover:text-primary cursor-pointer transition-colors"
                  data-action="details" title="View details">visibility</button>
        </td>
      </tr>
    `).join('');
  }

  // ============================================================================
  // RENDERING — VaR Donut
  // ============================================================================
  function renderVaRDonut(data) {
    const canvas = document.getElementById('var-donut-canvas');
    if (!canvas) return;

    const breakdown = data.overview?.var_breakdown || {};
    const labels = Object.keys(breakdown);
    const values = Object.values(breakdown);
    const total = values.reduce((a, b) => a + b, 0);

    if (labels.length === 0) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = COLORS.onSurfaceVariant;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data', canvas.width / 2, canvas.height / 2);
      return;
    }

    const colors = labels.map(l => COLORS.chart[l.toLowerCase()] || COLORS.primary);

    // Destroy previous chart
    if (state.donutChart) {
      state.donutChart.destroy();
    }

    // Create donut using Chart.js if available
    if (window.Chart && window.chartManager && window.chartManager.createDonutChart) {
      state.donutChart = window.chartManager.createDonutChart(canvas, labels, values, colors);
    } else {
      // Fallback minimal donut
      const ctx = canvas.getContext('2d');
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const radius = Math.min(centerX, centerY) - 10;
      let startAngle = -Math.PI / 2;

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      colors.forEach((color, i) => {
        const sliceAngle = (values[i] / total) * 2 * Math.PI;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        startAngle += sliceAngle;
      });

      // Inner hole for donut effect
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * 0.6, 0, 2 * Math.PI);
      ctx.fillStyle = COLORS.surfaceContainer;
      ctx.fill();

      state.donutChart = { resize: () => {} };
    }

    // Render legend
    const legendEl = document.getElementById('var-legend');
    if (legendEl) {
      legendEl.innerHTML = labels.map((label, i) => `
        <div class="flex items-center justify-between text-[10px]">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-sm" style="background:${colors[i]}"></div>
            <span class="text-on-surface-variant">${escapeHtml(label)}</span>
          </div>
          <span class="text-on-surface font-data-md">${values[i] >= 1000 ? fmtUSD(values[i]) : '$' + values[i].toFixed(0)}</span>
        </div>
      `).join('');
    }
  }

  // ============================================================================
  // RENDERING — Alerts
  // ============================================================================
  function renderAlerts(data) {
    const listEl = document.getElementById('alerts-list');
    const countEl = document.getElementById('alerts-count');
    if (!listEl) return;

    const alerts = data.alerts || [];
    if (countEl) countEl.textContent = alerts.length;

    if (alerts.length === 0) {
      listEl.innerHTML = '<div class="p-4 text-[10px] text-on-surface-variant text-center">No active alerts</div>';
      return;
    }

    listEl.innerHTML = alerts.map(a => `
      <div class="alert-item p-3 border-b border-outline-variant flex items-start gap-3">
        <span class="material-symbols-outlined text-[18px] flex-shrink-0 ${severityIcon(a.severity) === 'error' ? 'text-error' : severityIcon(a.severity) === 'warning' ? 'text-warning' : 'text-primary'}">
          ${severityIcon(a.severity)}
        </span>
        <div class="flex-1 min-w-0">
          <div class="font-label-sm text-on-surface break-words">${escapeHtml(a.message)}</div>
          <div class="text-[10px] text-on-surface-variant mt-1">${formatTime(a.timestamp)}</div>
        </div>
      </div>
    `).join('');
  }

  // ============================================================================
  // RENDERING — Stress Tests (CHART.JS HORIZONTAL BAR)
  // ============================================================================
  function renderStressTests(data) {
    const container = document.getElementById('stress-tests-list');
    if (!container) return;

    const tests = data.stressTests || [];

    if (tests.length === 0) {
      container.innerHTML = '<div class="p-4 text-[10px] text-on-surface-variant text-center">No stress tests</div>';
      return;
    }

    // Prepare chart data
    const labels = tests.map(t => t.scenario);
    const impacts = tests.map(t => t.impact_pct);
    const colors = impacts.map(impact => impact >= 0 ? COLORS.success : COLORS.error);

    // Destroy previous chart if exists
    if (state.stressChart) {
      state.stressChart.destroy();
      state.stressChart = null;
    }

    // Clear container and create canvas
    container.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.id = 'stress-chart';
    container.appendChild(canvas);

    // Create Chart.js horizontal bar chart if available
    if (window.Chart && window.chartManager && window.chartManager.createHorizontalBarChart) {
      try {
        state.stressChart = window.chartManager.createHorizontalBarChart(canvas, labels, impacts, colors);
      } catch (err) {
        console.error('Failed to create stress chart with chartManager:', err);
        fallbackRenderStressTests(tests, container);
      }
    } else if (window.Chart) {
      // Fallback: create chart directly with Chart.js
      try {
        const ctx = canvas.getContext('2d');
        state.stressChart = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Impact',
              data: impacts,
              backgroundColor: colors,
              borderColor: 'transparent',
              borderWidth: 0
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                display: false
              },
              tooltip: {
                callbacks: {
                  label: function(context) {
                    const value = context.raw;
                    return (value >= 0 ? '+' : '') + value.toFixed(1) + '%';
                  }
                }
              }
            },
            scales: {
              x: {
                grid: {
                  color: COLORS.outlineVariant + '20'
                },
                ticks: {
                  color: COLORS.onSurfaceVariant,
                  font: {
                    size: 10
                  },
                  callback: function(value) {
                    return value + '%';
                  }
                }
              },
              y: {
                grid: {
                  display: false
                },
                ticks: {
                  color: COLORS.onSurface,
                  font: {
                    size: 11
                  }
                }
              }
            },
            animation: {
              duration: 300
            }
          }
        });
      } catch (err) {
        console.error('Failed to create stress chart directly:', err);
        fallbackRenderStressTests(tests, container);
      }
    } else {
      // Chart.js not available — fallback to HTML list (original implementation)
      fallbackRenderStressTests(tests, container);
    }
  }

  // Fallback HTML list renderer (original implementation)
  function fallbackRenderStressTests(tests, container) {
    container.innerHTML = tests.map(t => `
      <div class="stress-item px-3 py-2 border-b border-outline-variant flex justify-between items-center">
        <span class="font-label-sm text-on-surface">${escapeHtml(t.scenario)}</span>
        <span class="font-data-md ${impactClass(t.impact_pct)}">${t.impact_pct > 0 ? '+' : ''}${t.impact_pct.toFixed(1)}%</span>
      </div>
    `).join('');
  }

  // ============================================================================
  // RENDERING — Compliance Log
  // ============================================================================
  function renderComplianceLog(data) {
    const tbody = document.getElementById('compliance-log-tbody');
    const countEl = document.getElementById('compliance-count');
    if (!tbody) return;

    const events = data.complianceEvents || [];
    if (countEl) countEl.textContent = events.length;

    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="px-4 py-4 text-center text-on-surface-variant text-[10px]">No compliance events</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(e => `
      <tr>
        <td class="px-4 py-2 text-[10px] font-label-sm text-on-surface-variant whitespace-nowrap">${formatTime(e.timestamp)}</td>
        <td class="px-4 py-2 font-data-md text-on-surface">${escapeHtml(e.event)}</td>
        <td class="px-4 py-2 text-center">
          <span class="px-2 py-0.5 rounded text-[10px] font-label-sm ${severityClass(e.status)}">${escapeHtml(e.status)}</span>
        </td>
      </tr>
    `).join('');
  }

  // ============================================================================
  // RENDERING — Main
  // ============================================================================
  function renderAll(data) {
    if (!isValidRiskData(data)) {
      console.warn('Invalid risk data:', data);
      return;
    }

    state.lastData = data;
    renderKPIs(data);
    renderTable(data);
    renderVaRDonut(data);
    renderAlerts(data);
    renderStressTests(data);
    renderComplianceLog(data);
  }

  // ============================================================================
  // POLLING
  // ============================================================================
  function tick() {
    // Check backoff at the beginning of tick
    if (state.backoffUntil && Date.now() < state.backoffUntil) {
      const remaining = Math.ceil((state.backoffUntil - Date.now()) / 1000);
      showStatus(`Retrying in ${remaining}s`, 'warning');
      if (state.lastData) renderAll(state.lastData);
      return;
    }

    loadData().then(data => {
      if (data) renderAll(data);
    }).catch(err => {
      console.error('tick error:', err);
    });
  }

  function startPolling() {
    stopPolling();
    const interval = window.config?.dashboard?.poll_interval_ms || 10000;
    state.pollIntervalId = setInterval(tick, interval);
  }

  function stopPolling() {
    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
      state.pollIntervalId = null;
    }
  }

  // ============================================================================
  // SORTING
  // ============================================================================
  function setupSortHandlers() {
    const table = document.getElementById('strategy-risk-table');
    if (!table) return;

    const headers = table.querySelectorAll('thead th');
    headers.forEach((th, index) => {
      // Determine sort key from column (approximate mapping)
      const sortKeys = ['name', 'symbol', 'timeframe', 'status', 'var', 'exposure', 'max_dd', 'sharpe', 'win_rate', 'actions'];
      const key = sortKeys[index];
      if (!key || key === 'actions') return;

      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        if (state.sortState.column === key) {
          state.sortState.direction = state.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
          state.sortState.column = key;
          state.sortState.direction = 'desc';
        }
        if (state.lastData) renderTable(state.lastData);
      });
    });
  }

  // ============================================================================
  // FILTER HANDLERS
  // ============================================================================
  function setupFilterHandlers() {
    const statusFilter = document.getElementById('filter-status');
    const timeframeFilter = document.getElementById('filter-timeframe');
    const assetFilter = document.getElementById('filter-asset');

    if (statusFilter) {
      statusFilter.addEventListener('change', (e) => {
        state.filters.status = e.target.value;
        if (state.lastData) renderTable(state.lastData);
      });
    }

    if (timeframeFilter) {
      timeframeFilter.addEventListener('change', (e) => {
        state.filters.timeframe = e.target.value;
        if (state.lastData) renderTable(state.lastData);
      });
    }

    if (assetFilter) {
      assetFilter.addEventListener('change', (e) => {
        state.filters.assetClass = e.target.value;
        if (state.lastData) renderTable(state.lastData);
      });
    }
  }

  // ============================================================================
  // INITIALIZATION
  // ============================================================================
  function init() {
    console.log('Risk & Compliance page initializing...');

    // Setup sort handlers
    setupSortHandlers();

    // Setup filter handlers
    setupFilterHandlers();

    // Refresh button
    const refreshBtn = document.getElementById('risk-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        tick();
      });
    }

    // Export CSV button
    const exportBtn = document.getElementById('export-csv-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportCsv);
    }

    // Initial load
    tick();

    // Start polling
    startPolling();

    // Visibility change to reduce load
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopPolling();
      } else {
        tick();
        startPolling();
      }
    });

    // Cleanup
    window.addEventListener('beforeunload', stopPolling);

    // Window resize for charts
    window.addEventListener('resize', () => {
      if (state.donutChart && state.donutChart.resize) {
        state.donutChart.resize();
      }
      if (state.stressChart && state.stressChart.resize) {
        state.stressChart.resize();
      }
    });

    console.log('Risk & Compliance page initialized');
  }

  // ============================================================================
  // BOOTSTRAP
  // ============================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose state for debugging
  window.riskComplianceState = state;

})();
