/**
 * Theme Manager
 * Handles light/dark theme toggle with localStorage persistence
 */

(function() {
  'use strict';

  const THEME_KEY = 'v3.theme';
  const DARK_CLASS = 'dark';
  const LIGHT_CLASS = 'light';

  /**
   * Initialize the theme system
   */
  function init() {
    // Apply saved theme or system preference
    applyTheme(getSavedTheme());

    // Setup toggle button
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', toggle);
    }

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      // If user hasn't explicitly chosen a theme, follow system
      if (!localStorage.getItem(THEME_KEY)) {
        applyTheme(e.matches ? DARK_CLASS : LIGHT_CLASS);
      }
    });

    // Also update Chart.js colors when theme changes
    window.addEventListener('theme:toggle', updateChartTheme);
  }

  /**
   * Get saved theme from localStorage
   * @returns {string}
   */
  function getSavedTheme() {
    return localStorage.getItem(THEME_KEY) || detectSystemTheme();
  }

  /**
   * Detect system theme preference
   * @returns {string}
   */
  function detectSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK_CLASS : LIGHT_CLASS;
  }

  /**
   * Apply theme to document
   * @param {string} theme - 'dark' or 'light'
   */
  function applyTheme(theme) {
    const html = document.documentElement;

    if (theme === DARK_CLASS) {
      html.classList.add(DARK_CLASS);
      html.classList.remove(LIGHT_CLASS);
    } else {
      html.classList.remove(DARK_CLASS);
      html.classList.add(LIGHT_CLASS);
    }

    localStorage.setItem(THEME_KEY, theme);
    window.dispatchEvent(new CustomEvent('theme:changed', { detail: { theme } }));
  }

  /**
   * Toggle between dark and light theme
   */
  function toggle() {
    const html = document.documentElement;
    const currentTheme = html.classList.contains(DARK_CLASS) ? DARK_CLASS : LIGHT_CLASS;
    const newTheme = currentTheme === DARK_CLASS ? LIGHT_CLASS : DARK_CLASS;

    applyTheme(newTheme);
  }

  /**
   * Set theme explicitly
   * @param {string} theme - 'dark' or 'light'
   */
  function setTheme(theme) {
    if (theme === DARK_CLASS || theme === LIGHT_CLASS) {
      applyTheme(theme);
    }
  }

  /**
   * Get current theme
   * @returns {string}
   */
  function getCurrentTheme() {
    return document.documentElement.classList.contains(DARK_CLASS) ? DARK_CLASS : LIGHT_CLASS;
  }

  /**
   * Update Chart.js instances to match the current theme
   * This should be called after a theme change to update any charts
   */
  function updateChartTheme() {
    const theme = getCurrentTheme();

    // Update Chart.js default colors based on theme
    const textColor = theme === DARK_CLASS ? '#e0e2ea' : '#1c2025';
    const gridColor = theme === DARK_CLASS ? '#3b494c' : '#e0e2ea';

    // If Chart.js global registry exists, update defaults
    if (window.Chart && Chart.defaults) {
      Chart.defaults.color = textColor;
      Chart.defaults.borderColor = gridColor;

      // Update all existing charts
      Object.values(Chart.instances).forEach((chart) => {
        if (chart.options.scales) {
          if (chart.options.scales.x) {
            chart.options.scales.x.ticks.color = textColor;
            chart.options.scales.x.grid.color = gridColor;
          }
          if (chart.options.scales.y) {
            chart.options.scales.y.ticks.color = textColor;
            chart.options.scales.y.grid.color = gridColor;
          }
        }
        if (chart.options.plugins && chart.options.plugins.legend) {
          chart.options.plugins.legend.labels.color = textColor;
        }
        chart.update('none');
      });
    }

    // Dispatch custom event for chart components to listen
    window.dispatchEvent(new CustomEvent('theme:updated', { detail: { theme } }));
  }

  /**
   * Check if dark mode is currently active
   * @returns {boolean}
   */
  function isDarkMode() {
    return document.documentElement.classList.contains(DARK_CLASS);
  }

  // Expose public API
  window.themeManager = {
    init,
    toggle,
    setTheme,
    getCurrentTheme,
    isDarkMode,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
