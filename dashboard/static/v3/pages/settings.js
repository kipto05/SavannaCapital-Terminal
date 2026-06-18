/**
 * Notification preferences page module.
 * Fetches user notification settings and provides UI to manage in-app and email preferences.
 */

(() => {
  'use strict';

  const state = {
    settings: [],
    originalSettings: [],
    isLoading: false,
    isSaving: false,
    isDirty: false,
    error: null,
  };

  const elements = {};

  async function init() {
    console.log('Settings page initializing...');
    cacheElements();
    await loadSettings();
    setupEventListeners();
    console.log('Settings page initialized');
  }

  function cacheElements() {
    elements.tableBody = document.getElementById('settings-table-body');
    elements.cardsContainer = document.getElementById('settings-cards');
    elements.loading = document.getElementById('settings-loading');
    elements.empty = document.getElementById('settings-empty');
    elements.saveBtn = document.getElementById('save-settings-btn');
    elements.saveText = document.getElementById('save-btn-text');
    elements.saveSpinner = document.getElementById('save-spinner');
    elements.saveStatus = document.getElementById('settings-status');
  }

  async function loadSettings() {
    state.isLoading = true;
    showLoading();

    try {
      const response = await window.apiFetch('/api/v3/notifications/settings');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.settings = data.map(s => ({
        ...s,
        in_app_enabled: Boolean(s.in_app_enabled),
        email_enabled: Boolean(s.email_enabled),
      }));
      state.originalSettings = JSON.parse(JSON.stringify(state.settings));
      state.isDirty = false;
      renderSettings();
      updateSaveButton();
    } catch (err) {
      console.error('Failed to load notification settings:', err);
      state.error = 'Failed to load settings. Please try again.';
      renderError();
    } finally {
      state.isLoading = false;
      hideLoading();
    }
  }

  function showLoading() {
    if (elements.loading) elements.loading.classList.remove('hidden');
  }

  function hideLoading() {
    if (elements.loading) elements.loading.classList.add('hidden');
  }

  function renderError() {
    const errorHtml = `
      <tr>
        <td colspan="3" class="px-4 py-8 text-center text-error">
          ${window.utils.escapeHtml(state.error)}
        </td>
      </tr>
    `;
    if (elements.tableBody) elements.tableBody.innerHTML = errorHtml;
    if (elements.cardsContainer) elements.cardsContainer.innerHTML = `
      <div class="py-8 text-center text-error">${window.utils.escapeHtml(state.error)}</div>
    `;
  }

  function renderSettings() {
    if (state.settings.length === 0) {
      if (elements.empty) elements.empty.classList.remove('hidden');
      if (elements.tableBody) elements.tableBody.innerHTML = '';
      if (elements.cardsContainer) elements.cardsContainer.innerHTML = '';
      return;
    }

    if (elements.empty) elements.empty.classList.add('hidden');

    const isMobile = window.innerWidth < 768;

    if (isMobile) {
      renderMobileCards();
    } else {
      renderDesktopTable();
    }
  }

  function renderDesktopTable() {
    const rows = state.settings.map((setting, index) => {
      const label = humanizeEventType(setting.event_type);
      return `
        <tr class="hover:bg-surface-container-high transition-colors" data-index="${index}">
          <td class="px-4 py-3 text-label-sm text-on-surface">${window.utils.escapeHtml(label)}</td>
          <td class="px-4 py-3 text-center">
            <label class="toggle-switch" aria-label="Toggle in-app notifications for ${window.utils.escapeHtml(label)}">
              <input type="checkbox" class="toggle-checkbox" data-index="${index}" data-field="in_app_enabled" ${setting.in_app_enabled ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </td>
          <td class="px-4 py-3 text-center">
            <label class="toggle-switch" aria-label="Toggle email notifications for ${window.utils.escapeHtml(label)}">
              <input type="checkbox" class="toggle-checkbox" data-index="${index}" data-field="email_enabled" ${setting.email_enabled ? 'checked' : ''}>
              <span class="toggle-slider"></span>
            </label>
          </td>
        </tr>
      `;
    }).join('');
    if (elements.tableBody) elements.tableBody.innerHTML = rows;
  }

  function renderMobileCards() {
    const cards = state.settings.map((setting, index) => {
      const label = humanizeEventType(setting.event_type);
      return `
        <div class="bg-surface-container border border-outline-variant rounded-lg p-4" data-index="${index}">
          <div class="font-label-md text-on-surface mb-3">${window.utils.escapeHtml(label)}</div>
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-label-sm text-on-surface-variant">In-App</span>
              <label class="toggle-switch" aria-label="Toggle in-app notifications for ${window.utils.escapeHtml(label)}">
                <input type="checkbox" class="toggle-checkbox" data-index="${index}" data-field="in_app_enabled" ${setting.in_app_enabled ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-label-sm text-on-surface-variant">Email</span>
              <label class="toggle-switch" aria-label="Toggle email notifications for ${window.utils.escapeHtml(label)}">
                <input type="checkbox" class="toggle-checkbox" data-index="${index}" data-field="email_enabled" ${setting.email_enabled ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
        </div>
      `;
    }).join('');
    if (elements.cardsContainer) elements.cardsContainer.innerHTML = cards;
  }

  function humanizeEventType(eventType) {
    const map = {
      strategy_signal: 'Strategy Signals',
      order_placed: 'Orders Placed',
      order_filled: 'Orders Filled',
      order_cancelled: 'Orders Cancelled',
      backtest_complete: 'Backtest Completion',
      ml_model_trained: 'ML Model Training',
      ai_suggestion: 'AI Suggestions',
      system_alert: 'System Alerts',
      trade_closed: 'Trade Closed',
      risk_limit_breached: 'Risk Limit Breaches',
      account_snapshot: 'Account Snapshots',
      hypothesis_update: 'Hypothesis Updates',
      transcription_processed: 'Transcription Processed',
    };
    if (map[eventType]) return map[eventType];
    return eventType.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
  }

  function setupEventListeners() {
    document.addEventListener('change', (e) => {
      if (e.target.matches('.toggle-checkbox')) {
        const index = parseInt(e.target.getAttribute('data-index'), 10);
        const field = e.target.getAttribute('data-field');
        if (index >= 0 && index < state.settings.length && field) {
          state.settings[index][field] = e.target.checked;
          if (!state.isDirty) {
            state.isDirty = true;
            updateSaveButton();
          }
        }
      }
    });

    if (elements.saveBtn) {
      elements.saveBtn.addEventListener('click', saveSettings);
    }

    let timeout;
    window.addEventListener('resize', () => {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        if (state.settings.length > 0) renderSettings();
      }, 200);
    });
  }

  async function saveSettings() {
    if (state.isSaving || !state.isDirty) return;

    state.isSaving = true;
    updateSaveButton();
    setSaveStatus('Saving...');

    try {
      const response = await window.apiFetch('/api/v3/notifications/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: state.settings }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }
      state.originalSettings = JSON.parse(JSON.stringify(state.settings));
      state.isDirty = false;
      setSaveStatus('Saved');
      setTimeout(() => setSaveStatus(''), 3000);
    } catch (err) {
      console.error('Save failed:', err);
      setSaveStatus('Failed to save. Please try again.', '#EF4444');
    } finally {
      state.isSaving = false;
      updateSaveButton();
    }
  }

  function updateSaveButton() {
    if (!elements.saveBtn) return;
    elements.saveBtn.disabled = !(state.isDirty && !state.isSaving);
    if (elements.saveText) {
      elements.saveText.textContent = state.isSaving ? 'Saving...' : 'Save changes';
    }
    if (elements.saveSpinner) {
      elements.saveSpinner.classList.toggle('hidden', !state.isSaving);
    }
  }

  function setSaveStatus(message, color) {
    if (elements.saveStatus) {
      elements.saveStatus.textContent = message;
      if (color) elements.saveStatus.style.color = color;
      if (message) {
        elements.saveStatus.classList.remove('hidden');
      } else {
        elements.saveStatus.classList.add('hidden');
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
