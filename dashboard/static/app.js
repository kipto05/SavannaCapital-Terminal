/* dashboard/static/app.js — shared runtime for all dashboard pages.
 *
 * Provides:
 *  - Token refresh interceptor (401 → /auth/refresh → retry once)
 *  - Shared apiFetch via window.apiFetch (restored from sessionStorage in _base.html)
 *  - Common render functions for table rows and Chart.js instances
 *  - Poll loop utility
 */

/* ── Token refresh ──────────────────────────────────────────────────────────
 *
 * _base.html (login.html when on public page) sets:
 *   window.authToken          — short-lived access token (30 min)
 *   window.__JWT__            — same value, alias used by apiFetch
 *   sessionStorage.refresh_token  — long-lived refresh token (7 days)
 *
 * If an API call returns 401, apiFetch transparently calls /auth/refresh
 * (using the sessionStorage refresh_token), stores the new access_token in
 * both window.authToken and sessionStorage, then retries the original call.
 * If refresh also fails (or no refresh token), redirect to /login.
 */

(function () {
  var _refreshing = null;

  window._refreshAccessToken = function () {
    if (_refreshing) return _refreshing;
    var rt = sessionStorage.getItem('refresh_token');
    if (!rt) return Promise.reject(new Error('No refresh token'));
    _refreshing = fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error('refresh failed: ' + r.status);
        return r.json();
      })
      .then(function (data) {
        var tok = data.access_token;
        window.authToken = tok;
        window.__JWT__ = tok;
        sessionStorage.setItem('access_token', tok);
        return tok;
      })
      .catch(function (err) {
        _clearAuth();
        window.location.href = '/login';
        throw err;
      })
      .finally(function () {
        _refreshing = null;
      });
    return _refreshing;
  };

  function _clearAuth() {
    window.authToken = '';
    window.__JWT__ = '';
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
  }

  /* Patch apiFetch to intercept 401 and retry once after refresh */
  var _orig = window.apiFetch;
  window.apiFetch = function (url, opts) {
    opts = opts || {};
    return _orig(url, opts).catch(function (err) {
      var status = err.status || (err.response && err.response.status);
      if (status === 401) return _refreshAccessToken().then(function () {
        return _orig(url, opts);
      });
      throw err;
    });
  };
})();

/* ── esc (HTML escape) ────────────────────────────────────────────────────── */
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Render helpers ───────────────────────────────────────────────────────── */

var COLORS = {
  equity: '#3B82F6',
  benchmark: '#9CA3AF',
  drawdown: 'rgba(239,68,68,0.2)',
  win: '#10B981',
  loss: '#EF4444',
  neutral: '#6B7280',
  accent: '#8B5CF6',
  ai: '#F59E0B',
  primary: '#00e5ff',
  info: '#9cf0ff',
};

/* Destroy previous Chart on a canvas if present */
function destroyChart(canvas, key) {
  if (!canvas) return;
  var inst = canvas[key];
  if (inst) {
    try { inst.destroy(); } catch (e) { /* ignore */ }
  }
}

/* ── Status badge ─────────────────────────────────────────────────────────── */
function badge(status) {
  var map = {
    complete: 'bg-green-900 text-green-300',
    running: 'bg-purple-900 text-purple-300',
    pending: 'bg-yellow-900 text-yellow-300',
    failed: 'bg-red-900 text-red-300',
    active: 'bg-green-900 text-green-300',
    inactive: 'bg-gray-700 text-gray-300',
    deployed: 'bg-green-900 text-green-300',
    draft: 'bg-yellow-900 text-yellow-300',
  };
  var cls = map[status] || 'bg-gray-700 text-gray-300';
  return '<span class="px-1.5 py-0.5 text-label-sm rounded ' + cls + '">' + esc(status) + '</span>';
}

/* ── PnL colour ───────────────────────────────────────────────────────────── */
function pnlColour(v) {
  if (v == null) return '#6B7280';
  if (v > 0) return '#10B981';
  if (v < 0) return '#EF4444';
  return '#6B7280';
}

/* ── Date formatter (UTC) ─────────────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}
function fmtDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/* ── Show an error in a <td colspan> row ──────────────────────────────────── */
function showTableError(tbody, msg) {
  tbody.innerHTML =
    '<tr><td colspan="99" class="px-cell-padding-x py-3 text-error font-label-sm">' +
    esc(msg) + '</td></tr>';
}
