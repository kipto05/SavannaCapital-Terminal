/**
 * Topbar Component
 * Handles notifications dropdown (resizable, draggable), profile menu, and mobile menu
 */

(function() {
  'use strict';

  const NOTIFICATIONS_KEY = 'v3.notifications.read';
  const PROFILE_MENU_KEY = 'v3.profile.menu.open';
  // localStorage keys for panel state
  const PANEL_STORAGE_KEYS = {
    width: 'notifications_panel_width',
    height: 'notifications_panel_height',
    top: 'notifications_panel_top',
    left: 'notifications_panel_left',
  };

  /**
   * Initialize the topbar
   */
  function init() {
    setupNotifications();
    setupProfileMenu();
    setupMobileMenu();
    updateHeaderInfo();
  }

  /**
   * Setup notifications dropdown with real API
   */
  function setupNotifications() {
    const notifBtn = document.getElementById('notifications-btn');
    const notifDropdown = document.getElementById('notifications-dropdown');
    const notifList = document.getElementById('notifications-list');
    const unreadToggle = document.getElementById('unread-only-toggle');
    const markAllBtn = document.getElementById('mark-all-read-btn');
    const closeBtn = document.getElementById('notifications-close');
    const header = document.getElementById('notifications-header');
    const resizeHandle = document.getElementById('notifications-resize-handle');

    if (!notifBtn || !notifDropdown) return;

    // State
    let currentFilterUnreadOnly = true;
    let isLoading = false;
    let notificationsCache = [];

    // Restore panel position and size from localStorage
    restorePanelState(notifDropdown);

    // Fetch initial unread count for badge
    fetchUnreadCount().catch(console.error);

    // Toggle dropdown on button click
    notifBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = notifDropdown.classList.contains('open');
      if (isOpen) {
        closeDropdown(notifDropdown);
      } else {
        openNotificationsDropdown(notifDropdown);
      }
    });

    // Close button in header
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeDropdown(notifDropdown);
      });
    }

    // Filter toggle
    if (unreadToggle) {
      unreadToggle.addEventListener('change', (e) => {
        currentFilterUnreadOnly = e.target.checked;
        if (notifDropdown.classList.contains('open')) {
          loadAndRenderNotifications();
        }
      });
    }

    // Mark all read button
    if (markAllBtn) {
      markAllBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
          await window.apiFetch('/api/v3/notifications/mark-all-read', { method: 'POST' });
          // Refresh list and badge
          await loadAndRenderNotifications();
          await fetchUnreadCount();
        } catch (error) {
          console.error('Failed to mark all read:', error);
        }
      });
    }

    // Setup drag on header
    if (header) {
      setupDrag(header, notifDropdown);
    }

    // Setup resize on handle
    if (resizeHandle) {
      setupResize(resizeHandle, notifDropdown);
    }

    // Open dropdown and load notifications
    function openNotificationsDropdown(dropdown) {
      dropdown.classList.add('open');
      loadAndRenderNotifications();

      // Close when clicking outside
      document.addEventListener('click', closeNotificationsHandler, { once: true });

      // Close on ESC key
      document.addEventListener('keydown', onKeyDown, { once: true });
    }

    // Handle ESC key
    function onKeyDown(e) {
      if (e.key === 'Escape' || e.key === 'ESC') {
        closeDropdown(notifDropdown);
      }
    }

    // Handler to close dropdown when clicking outside
    function closeNotificationsHandler(e) {
      const dropdown = document.getElementById('notifications-dropdown');
      const btn = document.getElementById('notifications-btn');
      if (dropdown && !dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {
        closeDropdown(dropdown);
      }
    }

    // Load and render notifications from API
    async function loadAndRenderNotifications() {
      if (isLoading) return;
      isLoading = true;
      renderLoading();

      try {
        const isRead = currentFilterUnreadOnly ? false : null;
        // Build query string
        const params = new URLSearchParams({
          page: '1',
          limit: '20'
        });
        if (isRead !== null) {
          params.append('is_read', isRead);
        }
        const response = await window.apiFetch(`/api/v3/notifications?${params.toString()}`);
        notificationsCache = response.items;
        renderNotificationList(notificationsCache);
      } catch (error) {
        console.error('Failed to load notifications:', error);
        renderError();
      } finally {
        isLoading = false;
      }
    }

    // Mark individual notification as read
    async function markNotificationRead(notificationId) {
      try {
        await window.apiFetch(`/api/v3/notifications/${notificationId}/read`, {
          method: 'PATCH',
          body: { is_read: true }
        });
        // Update local cache
        const notif = notificationsCache.find(n => n.id === notificationId);
        if (notif) {
          notif.is_read = true;
        }
        // Re-render if filter is "unread only" to remove the item
        if (currentFilterUnreadOnly) {
          await loadAndRenderNotifications();
        }
        // Update badge count
        await fetchUnreadCount();
      } catch (error) {
        console.error('Failed to mark notification read:', error);
      }
    }

    // Fetch unread count for badge
    async function fetchUnreadCount() {
      try {
        const response = await window.apiFetch('/api/v3/notifications?page=1&limit=1&is_read=false');
        updateNotificationsBadge(response.unread_count);
      } catch (error) {
        console.error('Failed to fetch unread count:', error);
      }
    }

    // Render loading state
    function renderLoading() {
      if (notifList) {
        notifList.innerHTML = `
          <div class="flex items-center justify-center py-8">
            <span class="material-symbols-rounded animate-spin text-2xl text-primary">refresh</span>
          </div>
        `;
      }
    }

    // Render error state
    function renderError() {
      if (notifList) {
        notifList.innerHTML = `
          <div class="text-center py-8 text-error text-sm">
            Failed to load notifications
          </div>
        `;
      }
    }

    // Render notification list
    function renderNotificationList(notifications) {
      if (!notifList) return;

      if (!notifications || notifications.length === 0) {
        notifList.innerHTML = '<div class="text-center py-8 text-neutral text-sm">No notifications</div>';
        return;
      }

      notifList.innerHTML = notifications.map(notif => {
        const timeStr = formatRelativeTime(new Date(notif.created_at));
        const isRead = notif.is_read;
        const iconMap = {
          trade: 'swap_horiz',
          strategy: 'analytics',
          backtest: 'assessment',
          ai: 'psychology',
          system: 'info',
          error: 'error',
          warning: 'warning',
        };
        const icon = iconMap[notif.type] || 'notifications';

        return `
          <div class="notification-item ${isRead ? 'read' : 'unread'} p-3 border-b border-outline-variant transition-colors" data-id="${notif.id}">
            <div class="flex items-start gap-3">
              <span class="material-symbols-rounded text-lg flex-shrink-0" style="color: ${getNotificationColor(notif.type)}">
                ${icon}
              </span>
              <div class="flex-1 min-w-0">
                <h4 class="font-medium text-sm mb-1 truncate">${window.utils.escapeHtml(notif.title)}</h4>
                <p class="text-xs text-neutral truncate">${window.utils.escapeHtml(notif.message)}</p>
                <div class="flex items-center justify-between mt-1">
                  <span class="text-xs text-neutral opacity-60">${timeStr}</span>
                  ${!isRead ? `
                    <button class="mark-read-btn text-xs px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest transition-colors" data-id="${notif.id}">
                      Mark read
                    </button>
                  ` : ''}
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');

      // Add event listeners for individual mark read buttons
      notifList.querySelectorAll('.mark-read-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const notifId = btn.getAttribute('data-id');
          await markNotificationRead(notifId);
        });
      });
    }
  }

  /**
   * Restore panel position and size from localStorage
   * @param {HTMLElement} panel
   */
  function restorePanelState(panel) {
    try {
      const width = localStorage.getItem(PANEL_STORAGE_KEYS.width);
      const height = localStorage.getItem(PANEL_STORAGE_KEYS.height);
      const top = localStorage.getItem(PANEL_STORAGE_KEYS.top);
      const left = localStorage.getItem(PANEL_STORAGE_KEYS.left);

      if (width) panel.style.width = width;
      if (height) panel.style.height = height;
      if (top) panel.style.top = top;
      if (left) panel.style.left = left;
    } catch (e) {
      console.warn('Failed to restore panel state:', e);
    }
  }

  /**
   * Save panel position and size to localStorage
   * @param {HTMLElement} panel
   */
  function savePanelState(panel) {
    try {
      localStorage.setItem(PANEL_STORAGE_KEYS.width, panel.style.width);
      localStorage.setItem(PANEL_STORAGE_KEYS.height, panel.style.height);
      localStorage.setItem(PANEL_STORAGE_KEYS.top, panel.style.top);
      localStorage.setItem(PANEL_STORAGE_KEYS.left, panel.style.left);
    } catch (e) {
      console.warn('Failed to save panel state:', e);
    }
  }

  /**
   * Setup drag functionality on title bar
   * @param {HTMLElement} handle
   * @param {HTMLElement} panel
   */
  function setupDrag(handle, panel) {
    let isDragging = false;
    let startX, startY, startLeft, startTop;

    handle.addEventListener('mousedown', (e) => {
      if (e.target.closest('button')) return; // Don't drag if clicking button

      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      startLeft = panel.offsetLeft;
      startTop = panel.offsetTop;

      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    function onMouseMove(e) {
      if (!isDragging) return;

      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      const newLeft = startLeft + dx;
      const newTop = startTop + dy;

      panel.style.left = `${newLeft}px`;
      panel.style.top = `${newTop}px`;
    }

    function onMouseUp() {
      if (isDragging) {
        isDragging = false;
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        savePanelState(panel);
      }
    }
  }

  /**
   * Setup resize functionality on handle
   * @param {HTMLElement} handle
   * @param {HTMLElement} panel
   */
  function setupResize(handle, panel) {
    let isResizing = false;
    let startX, startY, startWidth, startHeight;

    handle.addEventListener('mousedown', (e) => {
      isResizing = true;
      startX = e.clientX;
      startY = e.clientY;
      startWidth = panel.offsetWidth;
      startHeight = panel.offsetHeight;

      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    function onMouseMove(e) {
      if (!isResizing) return;

      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      const newWidth = Math.max(300, startWidth + dx); // Min width 300px
      const newHeight = Math.max(200, startHeight + dy); // Min height 200px

      panel.style.width = `${newWidth}px`;
      panel.style.height = `${newHeight}px`;
    }

    function onMouseUp() {
      if (isResizing) {
        isResizing = false;
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        savePanelState(panel);
      }
    }
  }

  /**
   * Close dropdown with animation
   * @param {HTMLElement} dropdown
   */
  function closeDropdown(dropdown) {
    dropdown.classList.remove('open');
  }

  /**
   * Update the notifications badge count
   * @param {number} count
   */
  function updateNotificationsBadge(count) {
    const badge = document.getElementById('notifications-badge');
    if (badge) {
      if (count > 0) {
        badge.textContent = count > 99 ? '99+' : count.toString();
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }
  }

  /**
   * Format relative time (e.g., "5 min ago")
   * @param {Date} date
   * @returns {string}
   */
  function formatRelativeTime(date) {
    const now = new Date();
    const diff = Math.floor((now - new Date(date)) / 1000);

    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  }

  /**
   * Get notification type color
   * @param {string} type
   * @returns {string}
   */
  function getNotificationColor(type) {
    const colors = {
      trade: '#10B981',
      strategy: '#3B82F6',
      backtest: '#8B5CF6',
      ai: '#F59E0B',
      system: '#6B7280',
      error: '#EF4444',
      warning: '#F59E0B',
    };
    return colors[type] || window.CHART_COLORS?.on_surface || '#9CA3AF';
  }

  /**
   * Setup profile menu dropdown
   */
  function setupProfileMenu() {
    const profileBtn = document.getElementById('profile-btn');
    const profileDropdown = document.getElementById('profile-dropdown');

    if (!profileBtn || !profileDropdown) return;

    profileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = profileDropdown.classList.contains('open');
      if (isOpen) {
        closeDropdown(profileDropdown);
      } else {
        openProfileDropdown(profileDropdown);
      }
    });

    // Handle menu actions
    profileDropdown.addEventListener('click', (e) => {
      const menuItem = e.target.closest('[data-action]');
      if (menuItem) {
        const action = menuItem.getAttribute('data-action');
        handleProfileAction(action);
        closeDropdown(profileDropdown);
      }
    });
  }

  /**
   * Open the profile dropdown
   * @param {HTMLElement} dropdown
   */
  function openProfileDropdown(dropdown) {
    dropdown.classList.add('open');
    document.addEventListener('click', closeProfileHandler, { once: true });
  }

  /**
   * Handler to close profile dropdown when clicking outside
   * @param {Event} e
   */
  function closeProfileHandler(e) {
    const dropdown = document.getElementById('profile-dropdown');
    const btn = document.getElementById('profile-btn');
    if (dropdown && !dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {
      closeDropdown(dropdown);
    }
  }

  /**
   * Handle profile menu action
   * @param {string} action
   */
  function handleProfileAction(action) {
    switch (action) {
      case 'settings':
        window.location.href = '/settings';
        break;
      case 'logout':
        window.location.href = '/auth/logout';
        break;
      default:
        console.warn('Unknown profile action:', action);
    }
  }

  /**
   * Setup mobile menu toggle
   */
  function setupMobileMenu() {
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('mobile-overlay');

    if (!mobileMenuBtn || !sidebar) return;

    mobileMenuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
      if (overlay) {
        overlay.classList.toggle('open');
      }
    });

    if (overlay) {
      overlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('open');
      });
    }
  }

  /**
   * Update header with user info and current page
   */
  function updateHeaderInfo() {
    const userDisplay = document.getElementById('user-display');
    const pageTitle = document.getElementById('page-title');

    if (pageTitle) {
      pageTitle.textContent = getPageTitle();
    }

    // Could fetch user data from API here if needed
    if (userDisplay) {
      const user = window.currentUser || { name: 'User' };
      userDisplay.textContent = user.name || 'User';
    }
  }

  /**
   * Get page title based on current path
   * @returns {string}
   */
  function getPageTitle() {
    const path = window.location.pathname;

    const titles = {
      '/': 'Dashboard',
      '/account': 'Account',
      '/trades': 'Trades',
      '/strategies': 'Strategies',
      '/quant': 'Quant Research',
      '/ml': 'Machine Learning',
      '/ai_advisor': 'AI Advisor',
      '/transcription': 'Transcription',
      '/settings': 'Settings',
    };

    return titles[path] || 'Savanna Capital';
  }

  // Expose globally
  window.topbar = {
    init,
    updateHeaderInfo,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
