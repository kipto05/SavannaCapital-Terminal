/**
 * Sidebar Component
 * Handles collapse/expand toggle and active navigation highlighting
 */

(function() {
  'use strict';

  const SIDEBAR_KEY = 'v3.sidebar.collapsed';
  const SIDEBAR_WIDTH = '240px';
  const SIDEBAR_COLLAPSED_WIDTH = '48px';

  /**
   * Initialize the sidebar
   */
  function init() {
    const sidebar = document.getElementById('sidebar');
    const mainWrapper = document.getElementById('main-wrapper');

    if (!sidebar || !mainWrapper) {
      console.error('Sidebar or main wrapper not found');
      return;
    }

    // Restore collapsed state from localStorage
    const isCollapsed = localStorage.getItem(SIDEBAR_KEY) === 'true';
    if (isCollapsed) {
      collapse();
    }

    // Setup collapse button
    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    if (collapseBtn) {
      collapseBtn.addEventListener('click', toggle);
    }

    // Handle keyboard shortcut (Ctrl/Cmd + B for sidebar toggle)
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault();
        toggle();
      }
    });

    // Set active navigation link based on current path
    updateActiveNavLink();
    window.addEventListener('popstate', updateActiveNavLink);
  }

  /**
   * Toggle sidebar collapse state
   */
  function toggle() {
    const isCollapsed = localStorage.getItem(SIDEBAR_KEY) === 'true';
    if (isCollapsed) {
      expand();
    } else {
      collapse();
    }
  }

  /**
   * Collapse the sidebar
   */
  function collapse() {
    const sidebar = document.getElementById('sidebar');
    const mainWrapper = document.getElementById('main-wrapper');
    if (!sidebar || !mainWrapper) return;

    sidebar.style.width = SIDEBAR_COLLAPSED_WIDTH;
    sidebar.setAttribute('data-collapsed', 'true');
    mainWrapper.style.marginLeft = SIDEBAR_COLLAPSED_WIDTH;

    // Hide text labels
    const navLinks = sidebar.querySelectorAll('.nav-link-text');
    navLinks.forEach((el) => {
      el.classList.add('hidden');
      el.classList.remove('block');
    });

    // Show tooltips or icons-only mode
    const navItems = sidebar.querySelectorAll('.nav-item');
    navItems.forEach((item) => {
      item.classList.add('justify-center');
    });

    localStorage.setItem(SIDEBAR_KEY, 'true');
    window.dispatchEvent(new CustomEvent('sidebar:toggle', { detail: { collapsed: true } }));
  }

  /**
   * Expand the sidebar
   */
  function expand() {
    const sidebar = document.getElementById('sidebar');
    const mainWrapper = document.getElementById('main-wrapper');
    if (!sidebar || !mainWrapper) return;

    sidebar.style.width = SIDEBAR_WIDTH;
    sidebar.setAttribute('data-collapsed', 'false');
    mainWrapper.style.marginLeft = SIDEBAR_WIDTH;

    // Show text labels
    const navLinks = sidebar.querySelectorAll('.nav-link-text');
    navLinks.forEach((el) => {
      el.classList.remove('hidden');
      el.classList.add('block');
    });

    // Reset nav items alignment
    const navItems = sidebar.querySelectorAll('.nav-item');
    navItems.forEach((item) => {
      item.classList.remove('justify-center');
    });

    localStorage.setItem(SIDEBAR_KEY, 'false');
    window.dispatchEvent(new CustomEvent('sidebar:toggle', { detail: { collapsed: false } }));
  }

  /**
   * Check if sidebar is currently collapsed
   * @returns {boolean}
   */
  function isCollapsed() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return true;
    return sidebar.getAttribute('data-collapsed') === 'true';
  }

  /**
   * Update active navigation link based on current path
   */
  function updateActiveNavLink() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link[data-path]');

    navLinks.forEach((link) => {
      const path = link.getAttribute('data-path');
      if (!path) return;

      // Check for exact match or prefix match for nested routes
      const isActive = path === currentPath || currentPath.startsWith(path + '/');

      if (isActive) {
        link.classList.add('active');
        // Ensure parent nav group is expanded if applicable
        const parentGroup = link.closest('.nav-group');
        if (parentGroup) {
          parentGroup.classList.add('expanded');
        }
      } else {
        link.classList.remove('active');
      }
    });
  }

  /**
   * Programmatically set the active navigation item
   * @param {string} path - Path to make active
   */
  function setActiveNav(path) {
    const navLinks = document.querySelectorAll('.nav-link[data-path]');
    navLinks.forEach((link) => link.classList.remove('active'));

    const targetLink = document.querySelector(`.nav-link[data-path="${path}"]`);
    if (targetLink) {
      targetLink.classList.add('active');
    }
  }

  // Expose public API
  window.sidebar = {
    init,
    toggle,
    collapse,
    expand,
    isCollapsed,
    setActiveNav,
    updateActiveNavLink,
  };

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
