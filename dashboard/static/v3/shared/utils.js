/**
 * Utility Functions
 * Common date and number formatting utilities
 */

/**
 * Format a date to a readable string
 * @param {Date|string|number} date - Date to format
 * @param {Object} options - Intl.DateTimeFormatOptions
 * @returns {string}
 */
function formatDate(date, options = {}) {
  const d = new Date(date);
  if (isNaN(d.getTime())) return 'Invalid date';

  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  };
  return d.toLocaleDateString('en-US', { ...defaultOptions, ...options });
}

/**
 * Format a date and time to a readable string
 * @param {Date|string|number} date - Date to format
 * @param {Object} options - Intl.DateTimeFormatOptions
 * @returns {string}
 */
function formatDateTime(date, options = {}) {
  const d = new Date(date);
  if (isNaN(d.getTime())) return 'Invalid date';

  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  };
  return d.toLocaleString('en-US', { ...defaultOptions, ...options });
}

/**
 * Format a time only (HH:MM)
 * @param {Date|string|number} date - Date to format
 * @returns {string}
 */
function formatTime(date) {
  const d = new Date(date);
  if (isNaN(d.getTime())) return 'Invalid date';
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/**
 * Format a number as currency (USD)
 * @param {number} value - Value to format
 * @param {string} currency - Currency code (default USD)
 * @param {number} minimumFractionDigits - Decimal places
 * @returns {string}
 */
function formatCurrency(value, currency = 'USD', minimumFractionDigits = 2) {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits,
    maximumFractionDigits: minimumFractionDigits,
  }).format(value);
}

/**
 * Format a number with thousand separators
 * @param {number} value - Value to format
 * @param {number} minimumFractionDigits - Decimal places
 * @param {number} maximumFractionDigits - Decimal places
 * @returns {string}
 */
function formatNumber(value, minimumFractionDigits = 2, maximumFractionDigits = 2) {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(value);
}

/**
 * Format a percentage
 * @param {number} value - Decimal value (0.05 = 5%)
 * @param {number} decimals - Decimal places
 * @returns {string}
 */
function formatPercent(value, decimals = 2) {
  if (value === null || value === undefined) return '-';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a number as compact (e.g., 1.2K, 1.5M)
 * @param {number} value - Value to format
 * @returns {string}
 */
function formatCompact(value) {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string}
 */
function truncate(text, maxLength = 50) {
  if (!text || typeof text !== 'string') return '';
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

/**
 * Format pip value for forex
 * @param {number} pip - Pip value
 * @returns {string}
 */
function formatPip(pip) {
  return pip.toFixed(1);
}

/**
 * Calculate percent change
 * @param {number} current - Current value
 * @param {number} previous - Previous value
 * @returns {number} Decimal change
 */
function percentChange(current, previous) {
  if (previous === 0) return 0;
  return (current - previous) / Math.abs(previous);
}

/**
 * Sanitize HTML to prevent XSS
 * @param {string} str - String to sanitize
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function}
 */
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Throttle function calls
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in ms
 * @returns {Function}
 */
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Get parameter from URL query string
 * @param {string} name - Parameter name
 * @returns {string | null}
 */
function getUrlParameter(name) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

// Export for ES modules usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    formatDate,
    formatDateTime,
    formatTime,
    formatCurrency,
    formatNumber,
    formatPercent,
    formatCompact,
    truncate,
    formatPip,
    percentChange,
    escapeHtml,
    debounce,
    throttle,
    getUrlParameter,
  };
}

// Also expose globally for script usage
window.utils = {
  formatDate,
  formatDateTime,
  formatTime,
  formatCurrency,
  formatNumber,
  formatPercent,
  formatCompact,
  truncate,
  formatPip,
  percentChange,
  escapeHtml,
  debounce,
  throttle,
  getUrlParameter,
};
