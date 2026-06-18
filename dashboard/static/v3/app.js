/**
 * Main Application Entry Point
 * Initializes all frontend modules and coordinates component startup
 */

(function() {
  'use strict';

  // Core modules
  const modules = [
    '/static/v3/shared/api.js',
    '/static/v3/shared/utils.js',
    '/static/v3/shared/charts.js',
    '/static/v3/components/sidebar.js',
    '/static/v3/components/topbar.js',
  ];

  /**
   * Load a JavaScript module dynamically
   * @param {string} src
   * @returns {Promise}
   */
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      // Check if already loaded
      if (document.querySelector(`script[src="${src}"]`)) {
        console.log(`Module already loaded: ${src}`);
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.onload = () => {
        console.log(`Module loaded: ${src}`);
        resolve();
      };
      script.onerror = () => {
        console.error(`Failed to load module: ${src}`);
        reject(new Error(`Failed to load ${src}`));
      };
      document.head.appendChild(script);
    });
  }

  /**
   * Initialize the application
   */
  async function init() {
    console.log('Savanna Capital v3 Dashboard initializing...');

    try {
      // Load all modules in sequence
      for (const module of modules) {
        await loadScript(module);
      }

      console.log('All modules loaded successfully');

      // Initialize chart manager
      if (window.chartManager) {
        console.log('Chart manager initialized');
      }

      // Initialize sidebar (includes navigation highlighting)
      if (window.sidebar && window.sidebar.init) {
        window.sidebar.init();
      }

      // Initialize topbar (notifications, profile menu)
      if (window.topbar && window.topbar.init) {
        window.topbar.init();
      }

      // Set up global error handling
      setupErrorHandling();

      // Set up connection status monitoring
      setupConnectionStatus();

      // Set up route change handling for SPA-like behavior
      setupRouterListeners();

      console.log('Savanna Capital v3 Dashboard initialized successfully');
    } catch (error) {
      console.error('Failed to initialize dashboard:', error);
    }
  }

  /**
   * Setup global error handling
   */
  function setupErrorHandling() {
    window.addEventListener('error', (e) => {
      console.error('Global error:', e.error);
      // Could send to error reporting service
    });

    window.addEventListener('unhandledrejection', (e) => {
      console.error('Unhandled promise rejection:', e.reason);
      e.preventDefault();
    });
  }

  /**
   * Setup connection status monitoring
   */
  function setupConnectionStatus() {
    const connectionStatus = document.getElementById('connection-status');
    if (!connectionStatus) return;

    // Check connection status periodically
    setInterval(() => {
      if (navigator.onLine) {
        connectionStatus.classList.remove('offline');
        connectionStatus.classList.add('online');
      } else {
        connectionStatus.classList.remove('online');
        connectionStatus.classList.add('offline');
      }
    }, 5000);

    // Listen for online/offline events
    window.addEventListener('online', () => {
      connectionStatus.classList.remove('offline');
      connectionStatus.classList.add('online');
    });

    window.addEventListener('offline', () => {
      connectionStatus.classList.remove('online');
      connectionStatus.classList.add('offline');
    });
  }

  /**
   * Setup router listeners for page navigation
   * Since this is not a SPA, we listen for page load events
   */
  function setupRouterListeners() {
    // After initial load, sidebar and topbar will auto-initialize
    // Listen for visibility changes to refresh data
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Refresh page data if needed
        window.dispatchEvent(new Event('page:visible'));
      }
    });

    // Expose a manual refresh function
    window.refreshData = () => {
      console.log('Manual refresh triggered');
      window.dispatchEvent(new Event('data:refresh'));
    };
  }

  /**
   * Export module status for debugging
   * @returns {Object}
   */
  function getModuleStatus() {
    return {
      theme: !!window.themeManager,
      sidebar: !!window.sidebar,
      topbar: !!window.topbar,
      api: !!window.api,
      utils: !!window.utils,
      charts: !!window.chartManager,
    };
  }

  // Expose debug API
  window.appStatus = getModuleStatus;

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
