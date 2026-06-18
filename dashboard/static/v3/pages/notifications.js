// Notifications Page Module
// Handles full-page notifications view with filtering, pagination, batch actions

(function() {
  'use strict';

  // State
  const state = {
    notifications: [],
    currentPage: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
    isLoading: false,
    selection: new Set(),
    filters: {
      type: '',
      isRead: false, // default: unread only; null = all, true = read only
    },
    pollIntervalId: null,
    pollIntervalMs: 8000,
  };

  // Constants for localStorage keys
  const STORAGE_KEYS = {
    FILTER_TYPE: 'notifications_page_filter_type',
    FILTER_READ: 'notifications_page_filter_unread_only',
  };

  // Icon mapping for notification types
  const TYPE_ICONS = {
    trade: 'swap_horiz',
    strategy: 'psychology',
    backtest: 'assessment',
    ml: 'hub',
    ai: 'smart_toy',
    system: 'info',
    error: 'error',
    warning: 'warning',
  };

  // Type color mapping
  const TYPE_COLORS = {
    trade: '#10B981',
    strategy: '#3B82F6',
    backtest: '#8B5CF6',
    ml: '#8B5CF6',
    ai: '#F59E0B',
    system: '#6B7280',
    error: '#EF4444',
    warning: '#F59E0B',
  };

  /**
   * Initialize the page
   */
  async function init() {
    console.log('Notifications page initializing...');

    // Load config for poll interval
    await loadConfig();

    // Restore filter preferences from localStorage
    restoreFilters();

    // Setup event listeners
    setupEventListeners();

    // Initial load
    await loadNotifications();

    // Start polling
    startPolling();

    // Cleanup on page unload
    window.addEventListener('beforeunload', cleanup);

    // Handle responsive layout on resize
    window.addEventListener('resize', handleResize);

    console.log('Notifications page initialized');
  }

  /**
   * Load configuration for poll interval
   */
  async function loadConfig() {
    try {
      const config = await window.apiFetch('/api/config/public');
      if (config?.dashboard?.poll_interval_ms) {
        state.pollIntervalMs = config.dashboard.poll_interval_ms;
      }
    } catch (err) {
      console.log('Config not available, using default poll interval');
    }
  }

  /**
   * Restore filter preferences from localStorage
   */
  function restoreFilters() {
    try {
      const savedType = localStorage.getItem(STORAGE_KEYS.FILTER_TYPE);
      const savedRead = localStorage.getItem(STORAGE_KEYS.FILTER_READ);

      if (savedType !== null) {
        state.filters.type = savedType;
        const typeSelect = document.getElementById('notifications-filter-type');
        if (typeSelect) typeSelect.value = savedType;
      }

      if (savedRead !== null) {
        state.filters.isRead = savedRead === 'true';
        const unreadToggle = document.getElementById('notifications-filter-unread-only');
        if (unreadToggle) unreadToggle.checked = state.filters.isRead === false; // checked only when isRead is false (unread only)
      }

      updateClearFiltersButton();
    } catch (e) {
      console.warn('Failed to restore filter preferences:', e);
    }
  }

  /**
   * Save filter preferences to localStorage
   */
  function saveFilters() {
    try {
      localStorage.setItem(STORAGE_KEYS.FILTER_TYPE, state.filters.type);
      localStorage.setItem(STORAGE_KEYS.FILTER_READ, state.filters.isRead.toString());
      updateClearFiltersButton();
    } catch (e) {
      console.warn('Failed to save filter preferences:', e);
    }
  }

  /**
   * Setup all event listeners
   */
  function setupEventListeners() {
    // Filter: type dropdown
    const typeSelect = document.getElementById('notifications-filter-type');
    if (typeSelect) {
      typeSelect.addEventListener('change', (e) => {
        state.filters.type = e.target.value;
        state.currentPage = 1; // Reset to first page
        saveFilters();
        loadNotifications();
      });
    }

    // Filter: unread only checkbox
    const unreadToggle = document.getElementById('notifications-filter-unread-only');
    if (unreadToggle) {
      unreadToggle.addEventListener('change', (e) => {
        state.filters.isRead = e.target.checked ? false : null; // false = unread only, null = all
        state.currentPage = 1;
        saveFilters();
        loadNotifications();
      });
    }

    // Clear filters button
    const clearFiltersBtn = document.getElementById('notifications-clear-filters');
    if (clearFiltersBtn) {
      clearFiltersBtn.addEventListener('click', clearFilters);
    }

    // Refresh button
    const refreshBtn = document.getElementById('notifications-refresh');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => loadNotifications(true));
    }

    // Batch actions: select all checkbox
    const selectAll = document.getElementById('notifications-select-all');
    if (selectAll) {
      selectAll.addEventListener('change', (e) => {
        toggleSelectAll(e.target.checked);
      });
    }

    // Batch actions: mark selected read
    const batchMarkReadBtn = document.getElementById('notifications-batch-mark-read');
    if (batchMarkReadBtn) {
      batchMarkReadBtn.addEventListener('click', batchMarkRead);
    }

    // Batch actions: delete selected
    const batchDeleteBtn = document.getElementById('notifications-batch-delete');
    if (batchDeleteBtn) {
      batchDeleteBtn.addEventListener('click', batchDelete);
    }

    // Clear selection button
    const clearSelectionBtn = document.getElementById('notifications-clear-selection');
    if (clearSelectionBtn) {
      clearSelectionBtn.addEventListener('click', clearSelection);
    }

    // Pagination
    const prevBtn = document.getElementById('notifications-prev-page');
    const nextBtn = document.getElementById('notifications-next-page');
    if (prevBtn) prevBtn.addEventListener('click', () => changePage(state.currentPage - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => changePage(state.currentPage + 1));
  }

  /**
   * Load notifications from API
   */
  async function loadNotifications(showLoading = true) {
    if (state.isLoading) return;
    state.isLoading = true;

    const loadingEl = document.getElementById('notifications-loading');
    const tableContainer = document.getElementById('notifications-table-container');
    const cardsContainer = document.getElementById('notifications-cards-container');
    const paginationEl = document.getElementById('notifications-pagination');

    if (showLoading) {
      if (loadingEl) loadingEl.classList.remove('hidden');
      if (tableContainer) tableContainer.classList.add('hidden');
      if (cardsContainer) cardsContainer.classList.add('hidden');
      if (paginationEl) paginationEl.classList.add('hidden');
    }

    try {
      // Build query params
      const params = new URLSearchParams({
        page: state.currentPage,
        limit: state.pageSize,
      });
      if (state.filters.type) params.append('type', state.filters.type);
      if (state.filters.isRead !== null) params.append('is_read', state.filters.isRead);

      const response = await window.apiFetch(`/api/v3/notifications?${params.toString()}`);

      state.notifications = response.items || [];
      state.total = response.total || 0;
      state.totalPages = Math.ceil(state.total / state.pageSize);

      // Clear selection when loading new data
      clearSelectionInternal();

      // Render
      renderNotifications();
      updatePagination();

      // Show/hide empty state
      showEmptyStateIfNeeded();

    } catch (err) {
      console.error('Failed to load notifications:', err);
      // Could show error toast
    } finally {
      state.isLoading = false;
      if (loadingEl) loadingEl.classList.add('hidden');
    }
  }

  /**
   * Render notifications list
   */
  function renderNotifications() {
    const tableBody = document.getElementById('notifications-table-body');
    const cardsContainer = document.getElementById('notifications-cards-container');
    const isMobile = window.innerWidth < 768;

    if (isMobile) {
      // Render mobile cards
      if (cardsContainer) {
        if (state.notifications.length === 0) {
          cardsContainer.innerHTML = '';
          cardsContainer.classList.add('hidden');
        } else {
          cardsContainer.classList.remove('hidden');
          cardsContainer.innerHTML = state.notifications.map(notif => renderNotificationCard(notif)).join('');
          attachCardEventListeners(cardsContainer);
        }
      }
      if (tableBody) tableBody.innerHTML = '';
    } else {
      // Render desktop table
      if (tableBody) {
        if (state.notifications.length === 0) {
          tableBody.innerHTML = `
            <tr>
              <td colspan="5" class="px-4 py-8 text-center text-on-surface-variant">
                No notifications match your filters
              </td>
            </tr>
          `;
        } else {
          tableBody.innerHTML = state.notifications.map(notif => renderTableRow(notif)).join('');
          attachTableRowEventListeners(tableBody);
        }
      }
      if (cardsContainer) cardsContainer.innerHTML = '';
    }

    // Update select all checkbox state
    updateSelectAllCheckbox();

    // Update batch toolbar visibility
    updateBatchToolbar();
  }

  /**
   * Render table row for a notification
   */
  function renderTableRow(notif) {
    const timeStr = formatRelativeTime(new Date(notif.created_at));
    const isSelected = state.selection.has(notif.id);
    const icon = TYPE_ICONS[notif.type] || 'notifications';
    const color = TYPE_COLORS[notif.type] || '#9CA3AF';
    const isRead = notif.is_read;

    return `
      <tr class="hover:bg-surface-container transition-colors ${isSelected ? 'bg-primary/10' : ''}" data-id="${notif.id}">
        <td class="px-4 py-3">
          <input type="checkbox" class="notification-select rounded border-outline-variant ${isSelected ? 'checked' : ''}" data-id="${notif.id}" aria-label="Select notification">
        </td>
        <td class="px-4 py-3">
          <span class="material-symbols-rounded text-lg" style="color: ${color}" aria-hidden="true">${icon}</span>
        </td>
        <td class="px-4 py-3">
          <div class="flex flex-col">
            <span class="font-medium text-on-surface ${isRead ? '' : 'font-bold'}">${window.utils.escapeHtml(notif.title)}</span>
            <span class="text-sm text-on-surface-variant truncate max-w-md">${window.utils.escapeHtml(notif.message)}</span>
          </div>
        </td>
        <td class="px-4 py-3 text-sm text-on-surface-variant">${timeStr}</td>
        <td class="px-4 py-3 text-right">
          <div class="flex items-center justify-end gap-2">
            ${!isRead ? `
              <button class="mark-read-btn p-1.5 rounded bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest hover:text-on-surface transition-colors" data-id="${notif.id}" title="Mark as read">
                <span class="material-symbols-rounded text-sm">done</span>
              </button>
            ` : ''}
            <button class="delete-btn p-1.5 rounded bg-surface-container-high text-on-surface-variant hover:bg-error hover:text-white transition-colors" data-id="${notif.id}" title="Delete">
              <span class="material-symbols-rounded text-sm">delete</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  /**
   * Render mobile card for a notification
   */
  function renderNotificationCard(notif) {
    const timeStr = formatRelativeTime(new Date(notif.created_at));
    const isSelected = state.selection.has(notif.id);
    const icon = TYPE_ICONS[notif.type] || 'notifications';
    const color = TYPE_COLORS[notif.type] || '#9CA3AF';
    const isRead = notif.is_read;

    return `
      <div class="bg-surface border border-outline-variant rounded-lg p-4 ${isSelected ? 'border-primary bg-primary/10' : ''}" data-id="${notif.id}">
        <div class="flex items-start gap-3">
          <div class="flex items-center gap-3">
            <input type="checkbox" class="notification-select rounded border-outline-variant flex-shrink-0 mt-1" data-id="${notif.id}" ${isSelected ? 'checked' : ''} aria-label="Select notification">
            <span class="material-symbols-rounded text-2xl flex-shrink-0" style="color: ${color}" aria-hidden="true">${icon}</span>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2 mb-1">
              <h4 class="font-bold text-on-surface ${isRead ? '' : 'font-semibold'} truncate">${window.utils.escapeHtml(notif.title)}</h4>
              <span class="text-xs text-on-surface-variant flex-shrink-0">${timeStr}</span>
            </div>
            <p class="text-sm text-on-surface-variant mb-3">${window.utils.escapeHtml(notif.message)}</p>
            <div class="flex items-center gap-2">
              ${!isRead ? `
                <button class="mark-read-btn flex items-center gap-1 px-2.5 py-1.5 text-xs font-label rounded bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest transition-colors" data-id="${notif.id}">
                  <span class="material-symbols-rounded text-sm">done</span>
                  Read
                </button>
              ` : ''}
              <button class="delete-btn flex items-center gap-1 px-2.5 py-1.5 text-xs font-label rounded bg-surface-container-high text-on-surface-variant hover:bg-error hover:text-white transition-colors" data-id="${notif.id}">
                <span class="material-symbols-rounded text-sm">delete</span>
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Attach event listeners to table rows
   */
  function attachTableRowEventListeners(container) {
    // Selection checkboxes
    container.querySelectorAll('.notification-select').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const id = e.target.getAttribute('data-id');
        if (e.target.checked) {
          state.selection.add(id);
        } else {
          state.selection.delete(id);
        }
        updateBatchToolbar();
        updateSelectAllCheckbox();
        // Update row styling
        const row = e.target.closest('tr');
        if (row) {
          if (e.target.checked) row.classList.add('bg-primary/10');
          else row.classList.remove('bg-primary/10');
        }
      });
    });

    // Mark read buttons
    container.querySelectorAll('.mark-read-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        await toggleNotificationRead(id);
      });
    });

    // Delete buttons
    container.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        await deleteNotification(id);
      });
    });
  }

  /**
   * Attach event listeners to mobile cards
   */
  function attachCardEventListeners(container) {
    // Selection checkboxes
    container.querySelectorAll('.notification-select').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const id = e.target.getAttribute('data-id');
        if (e.target.checked) {
          state.selection.add(id);
        } else {
          state.selection.delete(id);
        }
        updateBatchToolbar();
        updateSelectAllCheckbox();
        // Update card styling
        const card = e.target.closest('div[data-id]');
        if (card) {
          if (e.target.checked) card.classList.add('border-primary', 'bg-primary/10');
          else card.classList.remove('border-primary', 'bg-primary/10');
        }
      });
    });

    // Mark read buttons
    container.querySelectorAll('.mark-read-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        await toggleNotificationRead(id);
      });
    });

    // Delete buttons
    container.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.getAttribute('data-id');
        await deleteNotification(id);
      });
    });
  }

  /**
   * Toggle notification read status (only marking as read)
   */
  async function toggleNotificationRead(id) {
    try {
      const notif = state.notifications.find(n => n.id === id);
      if (!notif) return;

      const newReadState = !notif.is_read;
      // API only supports setting is_read=true
      if (!newReadState) return; // don't attempt to mark as unread

      await window.apiFetch(`/api/v3/notifications/${id}/read`, {
        method: 'PATCH',
        body: { is_read: newReadState },
      });

      // Update local state
      notif.is_read = newReadState;

      // If filtering by unread only and marking as read, remove from list
      if (state.filters.isRead === false && newReadState) {
        // Reload to refresh list
        await loadNotifications();
      } else {
        // Just re-render current view
        renderNotifications();
      }

    } catch (err) {
      console.error('Failed to toggle notification read status:', err);
      // Could show error toast
    }
  }

  /**
   * Delete a notification
   */
  async function deleteNotification(id) {
    if (!confirm('Are you sure you want to delete this notification?')) {
      return;
    }

    try {
      await window.apiFetch(`/api/v3/notifications/${id}`, {
        method: 'DELETE',
      });

      // Remove from local state
      state.selection.delete(id);
      state.notifications = state.notifications.filter(n => n.id !== id);
      state.total -= 1;
      state.totalPages = Math.ceil(state.total / state.pageSize);

      // If we're on the last page and it becomes empty, go to previous page
      if (state.currentPage > state.totalPages && state.totalPages > 0) {
        state.currentPage = state.totalPages;
      }

      renderNotifications();
      updatePagination();
      updateBatchToolbar();

    } catch (err) {
      console.error('Failed to delete notification:', err);
    }
  }

  /**
   * Batch mark selected as read
   */
  async function batchMarkRead() {
    if (state.selection.size === 0) return;

    try {
      // For each selected notification, mark as read
      const promises = Array.from(state.selection).map(id =>
        window.apiFetch(`/api/v3/notifications/${id}/read`, {
          method: 'PATCH',
          body: { is_read: true },
        }).catch(err => {
          console.error(`Failed to mark notification ${id} as read:`, err);
          return null;
        })
      );

      await Promise.all(promises);

      // Update local state
      state.notifications.forEach(notif => {
        if (state.selection.has(notif.id)) {
          notif.is_read = true;
        }
      });

      // Clear selection
      clearSelection();

      // If filter is unread only, reload to remove read items
      if (state.filters.isRead === false) {
        await loadNotifications();
      } else {
        renderNotifications();
      }

    } catch (err) {
      console.error('Failed to batch mark as read:', err);
    }
  }

  /**
   * Batch delete selected
   */
  async function batchDelete() {
    if (state.selection.size === 0) return;

    if (!confirm(`Are you sure you want to delete ${state.selection.size} notification(s)?`)) {
      return;
    }

    try {
      // Delete each selected notification
      const promises = Array.from(state.selection).map(id =>
        window.apiFetch(`/api/v3/notifications/${id}`, {
          method: 'DELETE',
        }).catch(err => {
          console.error(`Failed to delete notification ${id}:`, err);
          return null;
        })
      );

      await Promise.all(promises);

      // Remove from local state
      const removedCount = state.selection.size;
      state.notifications = state.notifications.filter(n => !state.selection.has(n.id));
      state.total -= removedCount;
      state.selection.clear();

      // Adjust page if needed
      state.totalPages = Math.ceil(state.total / state.pageSize);
      if (state.currentPage > state.totalPages && state.totalPages > 0) {
        state.currentPage = state.totalPages;
      }

      clearSelectionInternal();
      renderNotifications();
      updatePagination();
      updateBatchToolbar();

    } catch (err) {
      console.error('Failed to batch delete:', err);
    }
  }

  /**
   * Toggle select all on current page
   */
  function toggleSelectAll(checked) {
    if (checked) {
      // Select all visible notifications
      state.notifications.forEach(notif => state.selection.add(notif.id));
    } else {
      // Clear selection
      state.selection.clear();
    }
    renderNotifications();
    updateBatchToolbar();
  }

  /**
   * Clear selection
   */
  function clearSelection() {
    clearSelectionInternal();
    renderNotifications();
    updateBatchToolbar();
  }

  /**
   * Clear selection without re-rendering
   */
  function clearSelectionInternal() {
    state.selection.clear();
  }

  /**
   * Update batch toolbar visibility
   */
  function updateBatchToolbar() {
    const toolbar = document.getElementById('notifications-batch-toolbar');
    const countSpan = document.getElementById('notifications-selected-count');

    if (state.selection.size > 0) {
      if (toolbar) toolbar.classList.remove('hidden');
      if (countSpan) countSpan.textContent = `${state.selection.size} selected`;
    } else {
      if (toolbar) toolbar.classList.add('hidden');
    }

    // Update select all checkbox
    updateSelectAllCheckbox();
  }

  /**
   * Update select all checkbox state
   */
  function updateSelectAllCheckbox() {
    const selectAll = document.getElementById('notifications-select-all');
    if (!selectAll) return;

    const visibleCount = state.notifications.length;
    const selectedVisibleCount = state.notifications.filter(n => state.selection.has(n.id)).length;

    selectAll.checked = visibleCount > 0 && selectedVisibleCount === visibleCount;
    selectAll.indeterminate = selectedVisibleCount > 0 && selectedVisibleCount < visibleCount;
  }

  /**
   * Update pagination controls
   */
  function updatePagination() {
    const rangeSpan = document.getElementById('notifications-range');
    const totalSpan = document.getElementById('notifications-total');
    const currentPageSpan = document.getElementById('notifications-current-page');
    const prevBtn = document.getElementById('notifications-prev-page');
    const nextBtn = document.getElementById('notifications-next-page');
    const paginationEl = document.getElementById('notifications-pagination');

    // Hide pagination if only one page
    if (state.totalPages <= 1) {
      if (paginationEl) paginationEl.classList.add('hidden');
      return;
    }

    if (paginationEl) paginationEl.classList.remove('hidden');

    const start = (state.currentPage - 1) * state.pageSize + 1;
    const end = Math.min(state.currentPage * state.pageSize, state.total);

    if (rangeSpan) rangeSpan.textContent = `${start}-${end}`;
    if (totalSpan) totalSpan.textContent = state.total;
    if (currentPageSpan) currentPageSpan.textContent = state.currentPage;

    if (prevBtn) prevBtn.disabled = state.currentPage === 1;
    if (nextBtn) nextBtn.disabled = state.currentPage === state.totalPages;
  }

  /**
   * Change page
   */
  async function changePage(newPage) {
    if (newPage < 1 || newPage > state.totalPages || newPage === state.currentPage) {
      return;
    }
    state.currentPage = newPage;
    await loadNotifications();
  }

  /**
   * Clear all filters
   */
  function clearFilters() {
    state.filters.type = '';
    state.filters.isRead = false; // default back to unread only
    state.currentPage = 1;

    const typeSelect = document.getElementById('notifications-filter-type');
    const unreadToggle = document.getElementById('notifications-filter-unread-only');

    if (typeSelect) typeSelect.value = '';
    if (unreadToggle) unreadToggle.checked = true; // checked means unread only

    saveFilters();
    loadNotifications();
  }

  /**
   * Update clear filters button visibility
   */
  function updateClearFiltersButton() {
    const btn = document.getElementById('notifications-clear-filters');
    if (!btn) return;

    const hasActiveFilters = state.filters.type || (state.filters.isRead !== false);
    if (hasActiveFilters) {
      btn.classList.remove('hidden');
    } else {
      btn.classList.add('hidden');
    }
  }

  /**
   * Show empty state if no notifications, otherwise hide
   */
  function showEmptyStateIfNeeded() {
    const emptyEl = document.getElementById('notifications-empty');
    const tableContainer = document.getElementById('notifications-table-container');
    const cardsContainer = document.getElementById('notifications-cards-container');
    const paginationEl = document.getElementById('notifications-pagination');

    if (state.notifications.length === 0) {
      if (emptyEl) emptyEl.classList.remove('hidden');
      if (tableContainer) tableContainer.classList.add('hidden');
      if (cardsContainer) cardsContainer.classList.add('hidden');
      if (paginationEl) paginationEl.classList.add('hidden');
    } else {
      if (emptyEl) emptyEl.classList.add('hidden');
      if (window.innerWidth < 768) {
        if (cardsContainer) cardsContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
      } else {
        if (tableContainer) tableContainer.classList.remove('hidden');
        if (cardsContainer) cardsContainer.classList.add('hidden');
      }
    }
  }

  /**
   * Start polling for updates
   */
  function startPolling() {
    stopPolling();
    state.pollIntervalId = setInterval(() => {
      // Only refresh if page is visible
      if (document.visibilityState === 'visible') {
        loadNotifications(false); // Don't show loading spinner on refresh
      }
    }, state.pollIntervalMs);
  }

  /**
   * Stop polling
   */
  function stopPolling() {
    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
      state.pollIntervalId = null;
    }
  }

  /**
   * Cleanup on page unload
   */
  function cleanup() {
    stopPolling();
  }

  /**
   * Format relative time (e.g., "5 min ago")
   */
  function formatRelativeTime(date) {
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return `${Math.floor(diff / 86400)} days ago`;
  }

  /**
   * Handle window resize for responsive layout
   */
  function handleResize() {
    if (state.notifications.length > 0) {
      showEmptyStateIfNeeded();
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Handle resize
  window.addEventListener('resize', handleResize);

})();
