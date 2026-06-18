/**
 * Chart.js Configuration
 * Default configuration matching the design palette
 */

// Design system colors from _base.html
const CHART_COLORS = {
  // Primary palette
  primary: '#c3f5ff',
  primary_container: '#00e5ff',

  // Semantic colors
  win: '#10B981',      // Green for gains
  loss: '#EF4444',     // Red for losses
  neutral: '#6B7280',  // Grey for breakeven/neutral

  // Chart variants
  equity: '#3B82F6',   // Blue for equity curve
  benchmark: '#9CA3AF', // Grey for benchmark
  drawdown: 'rgba(239,68,68,0.2)', // Red transparent for drawdown
  accent: '#8B5CF6',   // Purple for ML predictions
  ai: '#F59E0B',       // Amber for AI advisor

  // Background and grid
  surface: '#101419',
  surface_container: '#1c2025',
  on_surface: '#e0e2ea',
  outline_variant: '#3b494c',
};

// Chart.js default configuration
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    intersect: false,
    mode: 'index',
  },
  plugins: {
    legend: {
      labels: {
        color: CHART_COLORS.on_surface,
        font: {
          family: 'Geist, sans-serif',
          size: 12,
        },
        usePointStyle: true,
        padding: 16,
      },
    },
    tooltip: {
      backgroundColor: CHART_COLORS.surface_container,
      titleColor: CHART_COLORS.on_surface,
      bodyColor: CHART_COLORS.on_surface,
      borderColor: CHART_COLORS.outline_variant,
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
    },
  },
  scales: {
    x: {
      grid: {
        color: CHART_COLORS.outline_variant,
        drawBorder: false,
        tickColor: 'transparent',
      },
      ticks: {
        color: CHART_COLORS.on_surface,
        font: {
          family: 'Geist, sans-serif',
          size: 11,
        },
        maxRotation: 0,
        autoSkip: true,
      },
    },
    y: {
      grid: {
        color: CHART_COLORS.outline_variant,
        drawBorder: false,
        tickColor: 'transparent',
      },
      ticks: {
        color: CHART_COLORS.on_surface,
        font: {
          family: 'Geist, sans-serif',
          size: 11,
        },
      },
    },
  },
};

/**
 * Create a line chart for equity curve
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @returns {Chart}
 */
function createEquityChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) {
    throw new Error(`Canvas element '${canvasId}' not found`);
  }

  // Destroy existing chart if it exists
  if (window.equityChartInstance) {
    window.equityChartInstance.destroy();
  }

  window.equityChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels || [],
      datasets: [
        {
          label: 'Equity',
          data: data.equity || [],
          borderColor: CHART_COLORS.equity,
          backgroundColor: `${CHART_COLORS.equity}20`,
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: CHART_COLORS.equity,
        },
        {
          label: 'Drawdown',
          data: data.drawdown || [],
          borderColor: CHART_COLORS.loss,
          backgroundColor: CHART_COLORS.drawdown,
          fill: true,
          tension: 0.0,
          borderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        tooltip: {
          ...chartDefaults.plugins.tooltip,
          callbacks: {
            label: function(context) {
              if (context.dataset.label === 'Equity') {
                return `Equity: ${window.utils.formatCurrency(context.parsed.y)}`;
              } else if (context.dataset.label === 'Drawdown') {
                return `Drawdown: ${window.utils.formatPercent(context.parsed.y)}`;
              }
              return context.dataset.label + ': ' + context.parsed.y;
            },
          },
        },
      },
      scales: {
        ...chartDefaults.scales,
        y: {
          ...chartDefaults.scales.y,
          position: 'right',
          ticks: {
            ...chartDefaults.scales.y.ticks,
            callback: function(value) {
              return window.utils.formatCurrency(value);
            },
          },
        },
      },
    },
  });

  return window.equityChartInstance;
}

/**
 * Create a bar chart for monthly returns
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data
 * @returns {Chart}
 */
function createMonthlyReturnsChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) {
    throw new Error(`Canvas element '${canvasId}' not found`);
  }

  // Destroy existing chart
  if (window.monthlyReturnsChartInstance) {
    window.monthlyReturnsChartInstance.destroy();
  }

  const colors = data.values.map((val) => {
    if (val > 0) return CHART_COLORS.win;
    if (val < 0) return CHART_COLORS.loss;
    return CHART_COLORS.neutral;
  });

  window.monthlyReturnsChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels || [],
      datasets: [
        {
          label: 'Return',
          data: data.values || [],
          backgroundColor: colors,
          borderRadius: 4,
          borderWidth: 0,
        },
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: {
          display: false,
        },
      },
      scales: {
        ...chartDefaults.scales,
        y: {
          ...chartDefaults.scales.y,
          ticks: {
            ...chartDefaults.scales.y.ticks,
            callback: function(value) {
              return window.utils.formatPercent(value);
            },
          },
        },
      },
    },
  });

  return window.monthlyReturnsChartInstance;
}

/**
 * Create a pie chart for trade distribution
 * @param {string} canvasId - Canvas element ID
 * @param {Array} data - Chart data [{ label, value, color }]
 * @returns {Chart}
 */
function createPieChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) {
    throw new Error(`Canvas element '${canvasId}' not found`);
  }

  if (window.pieChartInstance) {
    window.pieChartInstance.destroy();
  }

  window.pieChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map((d) => d.label),
      datasets: [
        {
          data: data.map((d) => d.value),
          backgroundColor: data.map((d) => d.color),
          borderColor: CHART_COLORS.surface_container,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: CHART_COLORS.on_surface,
            font: {
              family: 'Geist, sans-serif',
              size: 11,
            },
            padding: 12,
            usePointStyle: true,
          },
        },
        tooltip: {
          backgroundColor: CHART_COLORS.surface_container,
          titleColor: CHART_COLORS.on_surface,
          bodyColor: CHART_COLORS.on_surface,
          borderColor: CHART_COLORS.outline_variant,
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

  return window.pieChartInstance;
}

/**
 * Update chart data
 * @param {Chart} chart - Chart instance
 * @param {Object} newData - New data object
 */
function updateChartData(chart, newData) {
  if (!chart || !chart.data) return;
  chart.data = newData;
  chart.update('none');
}

/**
 * Destroy a chart instance
 * @param {Chart} chart - Chart instance to destroy
 */
function destroyChart(chart) {
  if (chart && typeof chart.destroy === 'function') {
    chart.destroy();
  }
}

// Expose globally
window.chartManager = {
  createEquityChart,
  createMonthlyReturnsChart,
  createPieChart,
  updateChartData,
  destroyChart,
  colors: CHART_COLORS,
};

window.CHART_COLORS = CHART_COLORS;

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    chartDefaults,
    CHART_COLORS,
    createEquityChart,
    createMonthlyReturnsChart,
    createPieChart,
    updateChartData,
    destroyChart,
  };
}
