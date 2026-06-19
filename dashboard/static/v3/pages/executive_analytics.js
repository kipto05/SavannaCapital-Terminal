/**
 * Executive Analytics Page Module
 * Handles performance tearsheet, NAV growth, capital allocation, risk/return scatter, drawdown profile
 */

(function() {
  'use strict';

  // Chart instances - store to destroy before re-creating
  const charts = {
    nav: null,
    allocation: null,
    scatter: null,
    drawdown: null,
  };

  // State
  const state = {
    analyticsData: null,
    currentRange: '1D', // default range
    isLoading: false,
    reportHistory: [],
    pollIntervalId: null,
    pollIntervalMs: 30000, // default 30s
    isPageVisible: true,
  };

  // Range button labels mapping to hours
  const RANGE_HOURS = {
    '1H': 1,
    '4H': 4,
    '1D': 24,
    'MAX': null, // all data
  };

  /**
   * Initialize the page
   */
  async function init() {
    console.log('Executive Analytics page initializing...');

    // Setup event listeners
    setupEventListeners();

    // Fetch poll interval configuration
    await fetchPollInterval();

    // Initial data load
    await loadAnalytics();

    // Start polling after initial load
    startPolling();

    console.log('Executive Analytics page initialized');
  }

  /**
   * Fetch poll interval from config API
   */
  async function fetchPollInterval() {
    try {
      const config = await window.apiFetch('/api/config/public');
      if (config && config.poll_interval_ms) {
        state.pollIntervalMs = config.poll_interval_ms;
        console.log('Poll interval set to', state.pollIntervalMs, 'ms');
      }
    } catch (err) {
      console.warn('Failed to fetch poll interval, using default 30000ms:', err);
    }
  }

  /**
   * Start polling for data updates
   */
  function startPolling() {
    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
    }

    state.pollIntervalId = setInterval(() => {
      // Only poll if page is visible
      if (state.isPageVisible) {
        console.log('Polling for analytics updates...');
        loadAnalytics(false); // false = don't show spinner on refresh button
      }
    }, state.pollIntervalMs);

    console.log('Polling started with interval', state.pollIntervalMs, 'ms');
  }

  /**
   * Stop polling
   */
  function stopPolling() {
    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
      state.pollIntervalId = null;
      console.log('Polling stopped');
    }
  }

  /**
   * Handle page visibility change
   */
  function handleVisibilityChange() {
    state.isPageVisible = document.visibilityState === 'visible';
    console.log('Page visibility changed:', state.isPageVisible ? 'visible' : 'hidden');

    // If page became visible and polling isn't active, restart it
    if (state.isPageVisible && !state.pollIntervalId) {
      startPolling();
    }
  }

  /**
   * Show status message
   * @param {string} message - Message to display
   * @param {boolean} isError - Whether this is an error message
   */
  function showStatus(message, isError = false) {
    const statusBar = document.getElementById('ex-status-bar');
    if (!statusBar) return;

    statusBar.textContent = message;
    statusBar.classList.remove('hidden');

    // Apply error styling if it's an error
    if (isError) {
      statusBar.classList.add('bg-error/10', 'border-error', 'text-error');
    } else {
      statusBar.classList.remove('bg-error/10', 'border-error', 'text-error');
      statusBar.classList.add('bg-info/10', 'border-info', 'text-info');
    }

    // Auto-hide success/status messages after a few seconds
    if (!isError) {
      setTimeout(() => {
        statusBar.classList.add('hidden');
      }, 5000);
    }
  }

  /**
   * Hide status bar
   */
  function hideStatus() {
    const statusBar = document.getElementById('ex-status-bar');
    if (statusBar) {
      statusBar.classList.add('hidden');
    }
  }

  /**
   * Setup all event listeners
   */
  function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('ex-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => loadAnalytics(true));
    }

    // Range buttons
    const rangeButtons = document.querySelectorAll('.ex-range-btn');
    rangeButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const range = e.target.getAttribute('data-range');
        if (range && range !== state.currentRange) {
          state.currentRange = range;
          updateRangeButtons();
          if (state.analyticsData) {
            renderNavChart(); // Re-render with filtered data
          }
        }
      });
    });

    // Generate report button (in header)
    const generateReportBtn = document.getElementById('ex-generate-report-btn');
    if (generateReportBtn) {
      generateReportBtn.addEventListener('click', generateReport);
    }

    // Generate modal button (in report panel)
    const generateModalBtn = document.getElementById('ex-generate-modal-btn');
    if (generateModalBtn) {
      generateModalBtn.addEventListener('click', generateReport);
    }

    // Modal close button
    const modalCloseBtn = document.getElementById('ex-modal-close-btn');
    if (modalCloseBtn) {
      modalCloseBtn.addEventListener('click', closeModal);
    }

    // Modal backdrop click closes modal
    const modalBackdrop = document.getElementById('ex-modal-backdrop');
    if (modalBackdrop) {
      modalBackdrop.addEventListener('click', closeModal);
    }

    // PDF download button (stub)
    const pdfBtn = document.getElementById('ex-modal-pdf-btn');
    if (pdfBtn) {
      pdfBtn.addEventListener('click', () => {
        console.log('PDF download requested - not yet implemented');
      });
    }

    // Escape key closes modal
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeModal();
      }
    });

    // Page visibility change
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      if (state.pollIntervalId) {
        clearInterval(state.pollIntervalId);
      }
    });
  }

  /**
   * Load analytics data from API
   * @param {boolean} showLoading - Whether to show loading state on refresh button
   */
  async function loadAnalytics(showLoading = true) {
    if (state.isLoading) return;
    state.isLoading = true;

    // Show loading state on refresh button
    const refreshBtn = document.getElementById('ex-refresh-btn');
    if (refreshBtn && showLoading) {
      refreshBtn.classList.add('opacity-50', 'cursor-not-allowed');
      refreshBtn.disabled = true;
    }

    try {
      const response = await window.apiFetch('/api/v3/analytics');

      // Store data
      state.analyticsData = response;
      state.currentRange = '1D'; // reset to default

      // Update range buttons to default
      updateRangeButtons();

      // Render all components
      renderKPIs(response);
      renderNavChart();
      renderAllocationChart(response);
      renderScatterChart(response);
      renderDrawdownChart(response);

      // Show success status
      const timestamp = new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      showStatus(`Updated at ${timestamp}`, false);

    } catch (err) {
      console.error('Failed to load analytics:', err);
      showStatus(`Error: ${err.message || 'Unknown error'}`, true);
    } finally {
      state.isLoading = false;
      if (refreshBtn) {
        refreshBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        refreshBtn.disabled = false;
      }
    }
  }

  /**
   * Update range button styling
   */
  function updateRangeButtons() {
    const rangeButtons = document.querySelectorAll('.ex-range-btn');
    rangeButtons.forEach(btn => {
      const range = btn.getAttribute('data-range');
      if (range === state.currentRange) {
        btn.classList.remove('bg-background', 'border', 'border-outline-variant');
        btn.classList.add('bg-primary', 'text-on-primary');
      } else {
        btn.classList.add('bg-background', 'border', 'border-outline-variant');
        btn.classList.remove('bg-primary', 'text-on-primary');
      }
    });
  }

  /**
   * Render KPI tiles
   */
  function renderKPIs(data) {
    // Cumulative Return
    const cumretEl = document.getElementById('ex-cumret-val');
    const cumretDeltaEl = document.getElementById('ex-cumret-delta');
    if (cumretEl && data.cumulative_return !== undefined) {
      const cumret = data.cumulative_return;
      cumretEl.textContent = window.utils.formatPercent(cumret);
      cumretEl.className = `font-data-lg text-[28px] tabular-nums font-medium ${cumret >= 0 ? 'text-success' : 'text-error'}`;
      if (cumretDeltaEl) {
        cumretDeltaEl.textContent = `vs 1M: ${window.utils.formatPercent(data.cumulative_return_1m || 0)}`;
      }
    }

    // Sharpe Ratio
    const sharpeEl = document.getElementById('ex-sharpe-val');
    const sharpeTierEl = document.getElementById('ex-sharpe-tier');
    if (sharpeEl && data.sharpe_ratio !== undefined) {
      const sharpe = data.sharpe_ratio;
      sharpeEl.textContent = sharpe.toFixed(2);
      sharpeEl.className = `font-data-lg text-[28px] tabular-nums font-medium ${getSharpeTierColor(sharpe)}`;
      if (sharpeTierEl) {
        sharpeTierEl.textContent = getSharpeTier(sharpe);
      }
    }

    // Alpha vs Risk-Free
    const alphaEl = document.getElementById('ex-alpha-val');
    const alphaRfEl = document.getElementById('ex-alpha-rf');
    if (alphaEl && data.alpha !== undefined) {
      const alpha = data.alpha;
      alphaEl.textContent = window.utils.formatPercent(alpha);
      alphaEl.className = `font-data-lg text-[28px] tabular-nums font-medium ${alpha >= 0 ? 'text-success' : 'text-error'}`;
      if (alphaRfEl) {
        alphaRfEl.textContent = `vs risk-free ${window.utils.formatPercent(data.risk_free_rate || 0.02)}`;
      }
    }

    // Calmar Ratio
    const calmarEl = document.getElementById('ex-calmar-val');
    const calmarTagEl = document.getElementById('ex-calmar-tag');
    if (calmarEl && data.calmar_ratio !== undefined) {
      const calmar = data.calmar_ratio;
      calmarEl.textContent = calmar.toFixed(2);
      calmarEl.className = `font-data-lg text-[28px] tabular-nums font-medium ${calmar >= 2 ? 'text-success' : calmar >= 1 ? 'text-warning' : 'text-error'}`;
      if (calmarTagEl) {
        calmarTagEl.textContent = data.max_drawdown ? `${window.utils.formatPercent(data.max_drawdown)} max DD` : 'CAGR ÷ Max DD';
      }
    }
  }

  /**
   * Get Sharpe tier classification
   */
  function getSharpeTier(sharpe) {
    if (sharpe >= 3.0) return 'Exceptional';
    if (sharpe >= 2.0) return 'Excellent';
    if (sharpe >= 1.5) return 'Good';
    if (sharpe >= 1.0) return 'Acceptable';
    return 'Poor';
  }

  /**
   * Get color class for Sharpe ratio
   */
  function getSharpeTierColor(sharpe) {
    if (sharpe >= 2.0) return 'text-success';
    if (sharpe >= 1.5) return 'text-primary';
    if (sharpe >= 1.0) return 'text-warning';
    return 'text-error';
  }

  /**
   * Render NAV Growth chart with risk-free benchmark
   */
  function renderNavChart() {
    if (!state.analyticsData || !state.analyticsData.nav_series) {
      console.warn('No NAV series data available');
      return;
    }

    const canvas = document.getElementById('ex-nav-canvas');
    if (!canvas) {
      console.error('Canvas #ex-nav-canvas not found');
      return;
    }

    // Destroy existing chart
    if (charts.nav) {
      charts.nav.destroy();
    }

    const navData = filterNavByRange(state.analyticsData.nav_series, state.currentRange);

    // Prepare datasets
    const labels = navData.map(d => d.date);
    const equityValues = navData.map(d => d.nav);
    const riskFreeValues = navData.map(d => d.risk_free);

    // Get colors
    const primaryColor = window.CHART_COLORS?.primary || '#c3f5ff';
    const benchmarkColor = window.CHART_COLORS?.benchmark || '#9CA3AF';
    const surfaceColor = window.CHART_COLORS?.surface || '#101419';
    const onSurfaceColor = window.CHART_COLORS?.on_surface || '#e0e2ea';
    const outlineColor = window.CHART_COLORS?.outline_variant || '#3b494c';

    charts.nav = new Chart(canvas, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Composite NAV',
            data: equityValues,
            borderColor: primaryColor,
            backgroundColor: `${primaryColor}20`,
            fill: true,
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            pointHoverBackgroundColor: primaryColor,
          },
          {
            label: 'Risk-Free Rate',
            data: riskFreeValues,
            borderColor: benchmarkColor,
            backgroundColor: 'transparent',
            borderDash: [5, 5],
            fill: false,
            tension: 0.0,
            borderWidth: 1,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index',
        },
        plugins: {
          legend: {
            display: false, // Use custom legend in HTML
          },
          tooltip: {
            backgroundColor: surfaceColor,
            titleColor: onSurfaceColor,
            bodyColor: onSurfaceColor,
            borderColor: outlineColor,
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            titleFont: {
              family: 'Geist, sans-serif',
              size: 13,
              weight: '600',
            },
            bodyFont: {
              family: 'Geist, sans-serif',
              size: 12,
            },
            displayColors: true,
            callbacks: {
              label: function(context) {
                if (context.dataset.label === 'Composite NAV') {
                  return `NAV: ${window.utils.formatCurrency(context.parsed.y)}`;
                } else if (context.dataset.label === 'Risk-Free Rate') {
                  return `Risk-Free: ${window.utils.formatPercent(context.parsed.y)}`;
                }
                return context.dataset.label + ': ' + context.parsed.y;
              },
            },
          },
        },
        scales: {
          x: {
            grid: {
              color: outlineColor,
              drawBorder: false,
              tickColor: 'transparent',
            },
            ticks: {
              color: onSurfaceColor,
              font: {
                family: 'Geist, sans-serif',
                size: 11,
              },
              maxRotation: 0,
              autoSkip: true,
            },
          },
          y: {
            position: 'right',
            grid: {
              color: outlineColor,
              drawBorder: false,
              tickColor: 'transparent',
            },
            ticks: {
              color: onSurfaceColor,
              font: {
                family: 'Geist, sans-serif',
                size: 11,
              },
              callback: function(value) {
                return window.utils.formatCurrency(value);
              },
            },
          },
        },
      },
    });
  }

  /**
   * Filter NAV data by range
   */
  function filterNavByRange(data, range) {
    if (!data || data.length === 0) return [];
    const hours = RANGE_HOURS[range];
    if (hours === null) return data; // MAX returns all
    // Assuming data is ordered by date ascending, return last N hours
    return data.slice(-hours);
  }

  /**
   * Render Capital Allocation donut chart
   */
  function renderAllocationChart(data) {
    if (!data || !data.capital_allocation) {
      console.warn('No capital allocation data available');
      return;
    }

    const canvas = document.getElementById('ex-alloc-canvas');
    if (!canvas) {
      console.error('Canvas #ex-alloc-canvas not found');
      return;
    }

    // Destroy existing chart
    if (charts.allocation) {
      charts.allocation.destroy();
    }

    const allocation = data.capital_allocation;
    const colors = allocation.map((item, index) => {
      // Use consistent colors for strategies
      const colorPalette = [
        '#c3f5ff', '#00e5ff', '#3B82F6', '#10B981', '#F59E0B', '#8B5CF6',
        '#EF4444', '#6B7280', '#14B8A6', '#F97316', '#EC4899', '#6366F1'
      ];
      return colorPalette[index % colorPalette.length];
    });

    charts.allocation = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: allocation.map(d => d.strategy),
        datasets: [{
          data: allocation.map(d => d.allocation),
          backgroundColor: colors,
          borderColor: window.CHART_COLORS?.surface_container || '#1c2025',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: {
            display: false, // Use custom legend in HTML
          },
          tooltip: {
            backgroundColor: window.CHART_COLORS?.surface_container || '#1c2025',
            titleColor: window.CHART_COLORS?.on_surface || '#e0e2ea',
            bodyColor: window.CHART_COLORS?.on_surface || '#e0e2ea',
            borderColor: window.CHART_COLORS?.outline_variant || '#3b494c',
            borderWidth: 1,
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              label: function(context) {
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const value = context.parsed;
                const percentage = ((value / total) * 100).toFixed(1);
                return `${context.label}: ${window.utils.formatNumber(value)} (${percentage}%)`;
              },
            },
          },
        },
      },
    });

    // Update center label with total active allocation
    const centerEl = document.getElementById('ex-alloc-center');
    const totalAllocation = allocation.reduce((sum, item) => sum + item.allocation, 0);
    if (centerEl) {
      centerEl.textContent = window.utils.formatNumber(totalAllocation);
    }

    // Update AUM label
    const aumEl = document.getElementById('ex-alloc-aum');
    if (aumEl && data.total_aum) {
      aumEl.textContent = window.utils.formatCurrency(data.total_aum);
    }

    // Render legend
    const legendEl = document.getElementById('ex-alloc-legend');
    if (legendEl && allocation.length > 0) {
      legendEl.innerHTML = allocation.map((item, index) => `
        <div class="flex items-center justify-between px-2 py-1 rounded hover:bg-surface-container transition-colors">
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-sm" style="background-color: ${colors[index]}"></span>
            <span class="text-xs text-on-surface-variant font-label-sm">${window.utils.escapeHtml(item.strategy)}</span>
          </div>
          <span class="text-xs text-on-surface font-label-sm tabular-nums">${((item.allocation / totalAllocation) * 100).toFixed(1)}%</span>
        </div>
      `).join('');
    }
  }

  /**
   * Render Risk/Return scatter chart
   */
  function renderScatterChart(data) {
    if (!data || !data.strategy_metrics) {
      console.warn('No strategy metrics data available');
      return;
    }

    const canvas = document.getElementById('ex-scatter-canvas');
    if (!canvas) {
      console.error('Canvas #ex-scatter-canvas not found');
      return;
    }

    // Destroy existing chart
    if (charts.scatter) {
      charts.scatter.destroy();
    }

    const metrics = data.strategy_metrics;
    const primaryColor = window.CHART_COLORS?.primary || '#c3f5ff';
    const onSurfaceColor = window.CHART_COLORS?.on_surface || '#e0e2ea';
    const outlineColor = window.CHART_COLORS?.outline_variant || '#3b494c';

    // Convert to bubble chart data (bubble size = sqrt(trades))
    const bubbleData = metrics.map(m => ({
      x: m.max_drawdown * 100, // x-axis: Drawdown % (convert to positive for display)
      y: m.sharpe_ratio || 0,
      r: Math.sqrt(m.trades || 1) * 2, // scale bubble size
      strategy: m.strategy,
      trades: m.trades,
      pnl: m.net_pnl_r,
    }));

    charts.scatter = new Chart(canvas, {
      type: 'bubble',
      data: {
        datasets: [{
          label: 'Strategies',
          data: bubbleData,
          backgroundColor: `${primaryColor}60`,
          borderColor: primaryColor,
          borderWidth: 1,
          hoverBackgroundColor: primaryColor,
          hoverBorderColor: onSurfaceColor,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: window.CHART_COLORS?.surface_container || '#1c2025',
            titleColor: onSurfaceColor,
            bodyColor: onSurfaceColor,
            borderColor: outlineColor,
            borderWidth: 1,
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              title: function(context) {
                return context[0].raw.strategy;
              },
              label: function(context) {
                const raw = context.raw;
                return [
                  `Sharpe: ${raw.y.toFixed(2)}`,
                  `Max DD: ${raw.x.toFixed(1)}%`,
                  `Trades: ${raw.trades}`,
                  `Net PnL: ${window.utils.formatPercent(raw.pnl)}`,
                ];
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Risk (Max DD %)',
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
            },
            grid: {
              color: outlineColor,
              drawBorder: false,
            },
            ticks: {
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
              callback: function(value) {
                return value.toFixed(1) + '%';
              },
            },
            // Invert so lower drawdown (better) is on the left (or keep as-is)
          },
          y: {
            title: {
              display: true,
              text: 'Return (Sharpe)',
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
            },
            grid: {
              color: outlineColor,
              drawBorder: false,
            },
            ticks: {
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
            },
          },
        },
      },
    });
  }

  /**
   * Render Drawdown Profile bar chart
   */
  function renderDrawdownChart(data) {
    if (!data || !data.drawdown_events) {
      console.warn('No drawdown events data available');
      return;
    }

    const canvas = document.getElementById('ex-dd-canvas');
    if (!canvas) {
      console.error('Canvas #ex-dd-canvas not found');
      return;
    }

    // Destroy existing chart
    if (charts.drawdown) {
      charts.drawdown.destroy();
    }

    const events = data.drawdown_events;
    const onSurfaceColor = window.CHART_COLORS?.on_surface || '#e0e2ea';
    const outlineColor = window.CHART_COLORS?.outline_variant || '#3b494c';

    // Color bars based on severity
    const getBarColor = (dd) => {
      if (dd >= 0.10) return '#EF4444'; // red - severe
      if (dd >= 0.05) return '#F59E0B'; // amber - moderate
      return '#10B981'; // green - acceptable
    };

    charts.drawdown = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: events.map((e, i) => `DD ${i + 1}`), // Could use dates
        datasets: [{
          label: 'Drawdown (%)',
          data: events.map(e => e.drawdown * 100),
          backgroundColor: events.map(e => getBarColor(e.drawdown)),
          borderRadius: 4,
          borderWidth: 0,
        }],
      },
      options: {
        indexAxis: 'y', // Horizontal bar chart
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: window.CHART_COLORS?.surface_container || '#1c2025',
            titleColor: onSurfaceColor,
            bodyColor: onSurfaceColor,
            borderColor: outlineColor,
            borderWidth: 1,
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              title: function(context) {
                const idx = context[0].dataIndex;
                return events[idx]?.period || `Event ${idx + 1}`;
              },
              label: function(context) {
                const raw = context.raw;
                const idx = context.dataIndex;
                const event = events[idx];
                return [
                  `Drawdown: ${raw.toFixed(2)}%`,
                  `Duration: ${event?.duration_days || 'N/A'} days`,
                  `Recovery: ${event?.recovery_days || 'N/A'} days`,
                ];
              },
            },
          },
        },
        scales: {
          x: {
            grid: {
              color: outlineColor,
              drawBorder: false,
            },
            ticks: {
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
              callback: function(value) {
                return value + '%';
              },
            },
            title: {
              display: true,
              text: 'Drawdown %',
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
            },
          },
          y: {
            grid: {
              color: outlineColor,
              drawBorder: false,
            },
            ticks: {
              color: onSurfaceColor,
              font: { family: 'Geist, sans-serif', size: 11 },
            },
          },
        },
      },
    });

    // Update stats footer
    const ddMaxEl = document.getElementById('ex-dd-max');
    const ddRecoveryEl = document.getElementById('ex-dd-recovery');
    const ddAvgEl = document.getElementById('ex-dd-avg');

    if (ddMaxEl && events.length > 0) {
      const maxDd = Math.max(...events.map(e => e.drawdown));
      ddMaxEl.textContent = window.utils.formatPercent(maxDd);
    }

    if (ddRecoveryEl && events.length > 0) {
      const avgRecovery = events.reduce((sum, e) => sum + (e.recovery_days || 0), 0) / events.length;
      ddRecoveryEl.textContent = `Recovery: ${avgRecovery.toFixed(0)} days avg`;
    }

    if (ddAvgEl && events.length > 0) {
      const avgDd = events.reduce((sum, e) => sum + e.drawdown, 0) / events.length;
      ddAvgEl.textContent = `Avg Depth: ${window.utils.formatPercent(avgDd)}`;
    }
  }

  /**
   * Generate new report (opens modal with tearsheet)
   */
  async function generateReport() {
    const modal = document.getElementById('ex-tearsheet-modal');
    const bodyEl = document.getElementById('ex-tearsheet-body');
    const dateEl = document.getElementById('ex-modal-date');

    if (!modal || !bodyEl) {
      console.error('Modal elements not found');
      return;
    }

    // Show loading state
    modal.classList.remove('hidden');
    bodyEl.innerHTML = '<div class="text-outline text-center py-12">Generating report…</div>';
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    }

    try {
      const response = await window.apiFetch('/api/v3/reports', {
        method: 'POST',
        // No body needed, or could include date range
      });

      // Assume response contains HTML string or URL to tearsheet
      if (response.html || response.url) {
        if (response.html) {
          bodyEl.innerHTML = response.html;
        } else if (response.url) {
          bodyEl.innerHTML = `<iframe src="${response.url}" class="w-full h-full border-0" style="min-height: 600px;"></iframe>`;
        }
      } else {
        bodyEl.innerHTML = '<div class="text-outline text-center py-12">Report generated successfully. No content to display.</div>';
      }

      // Could add to report history
      if (response.report_id) {
        addReportToHistory(response.report_id, new Date());
      }

    } catch (err) {
      console.error('Failed to generate report:', err);
      bodyEl.innerHTML = '<div class="text-error text-center py-12">Failed to generate report. Please try again.</div>';
    }
  }

  /**
   * Add report to history list
   */
  function addReportToHistory(reportId, date) {
    state.reportHistory.unshift({ id: reportId, date });
    renderReportHistory();
  }

  /**
   * Render report history list
   */
  function renderReportHistory() {
    const historyEl = document.getElementById('ex-report-history');
    if (!historyEl) return;

    if (state.reportHistory.length === 0) {
      historyEl.innerHTML = '<div class="text-center py-6 text-outline">No reports generated yet.</div>';
      return;
    }

    historyEl.innerHTML = state.reportHistory.map(report => `
      <div class="flex items-center justify-between px-2 py-2 rounded hover:bg-surface-container transition-colors">
        <div class="flex flex-col">
          <span class="text-xs text-on-surface font-label-sm">Tear Sheet ${report.id.slice(-8)}</span>
          <span class="text-[10px] text-on-surface-variant font-label-sm">${new Date(report.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <button class="text-primary text-xs font-label-sm hover:underline" data-id="${report.id}">View</button>
      </div>
    `).join('');

    // Add click listeners for view buttons
    historyEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        console.log('View report:', btn.getAttribute('data-id'));
        // Could fetch and display historical report
      });
    });
  }

  /**
   * Close modal
   */
  function closeModal() {
    const modal = document.getElementById('ex-tearsheet-modal');
    if (modal) {
      modal.classList.add('hidden');
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
