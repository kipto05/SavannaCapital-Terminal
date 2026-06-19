# Risk & Compliance Page (Phase 6) — Implementation Tasks

**Target Files:**
- `dashboard/templates/v3/pages/risk_compliance.html`
- `dashboard/static/v3/pages/risk_compliance.js`

**Dependencies:**
- Base template `dashboard/templates/v3/_base.html` and sidebar already exist
- Shared partials: `_kpi_tile.html`, `_data_table.html`, `_chart_card.html`
- Shared JS: `apiFetch`, Chart.js helpers from `shared/charts.js`
- Backend API endpoints at `/api/v3/risk/*` (or mock mode via `?mock=1`)

**References:**
- DASHBOARD_DOCUMENTATION.md pages 724-790
- V3_FRONTEND_REDESIGN_PLAN.md section 3.2 (pages 285-308)
- V3_SEQUENTIAL_BUILD_PLAN.md Phase 6 (pages 326-367)

---

## Task List

### 1. HTML Template Structure

#### 1.1 Setup base template structure
- Create file: `dashboard/templates/v3/pages/risk_compliance.html`
- Extend `{% extends "v3/_base.html" %}`
- Set title block: `{% block title %}Risk & Compliance | Savanna Capital{% endblock %}`
- Define `{% block content %}` with page structure
- Define `{% block scripts %}` to include JS file: `<script src="/static/v3/pages/risk_compliance.js"></script>`
- **Verification:** Open `/risk-compliance` and confirm template loads without errors (check browser console, network tab)

#### 1.2 Implement top telemetry bar (h-16 height)
- Add header section with page title and optional refresh button
- Create KPI tile row with 4 KPI cards using `{% include "v3/partials/_kpi_tile.html" %}`
- KPIs: VaR % (with absolute), Beta, Margin Usage (with bar), Net PnL
- Include IDs for each KPI element for JS updates: `id="kpi-var"`, `id="kpi-beta"`, `id="kpi-margin"`, `id="kpi-pnl"`
- **Verification:** KPI tiles render with static values, layout is 5 columns on large screens, 1 on mobile

#### 1.3 Implement left sidebar navigation (240px)
- Add section with navigation links as per spec: Risk Telemetry, Compliance, Stress Tests, Margin, Reports
- Use appropriate Material Icons for each item (e.g., `trending_up`, `gavel`, `speed`, `attach_money`, `description`)
- Add `active` class logic to highlight current "Risk Compliance" section
- Store navigation links with hrefs pointing to page anchors: `#telemetry`, `#compliance`, etc.
- **Verification:** Sidebar nav visible, icons display, 240px width, active state highlighted with primary color

#### 1.4 Implement main grid layout (3 columns)
- Create CSS Grid container: `<div class="grid grid-cols-1 lg:grid-cols-12 gap-1">`
- Center column: `class="lg:col-span-8"` for strategy risk metrics table
- Right sidebar: `class="lg:col-span-4"` for VaR donut, alerts, stress tests
- Bottom panel: full-width compliance log panel after grid
- **Verification:** Grid layers correctly, responsive on mobile/tablet, 1px gap shows grid lines (background color)

#### 1.5 Implement strategy risk metrics table section
- Create panel with header: "Strategy Risk Metrics"
- Use `_data_table.html` partial with custom columns:
  - Strategy name (font-mono)
  - Symbol
  - Timeframe
  - Status (badge)
  - VaR %
  - Exposure ($K)
  - Max DD %
  - Sharpe
  - Win Rate %
  - Actions (icon buttons)
- Table attributes: `id="strategy-risk-table"`, `class="w-full"`, sticky header (`sticky top-0`)
- Thead with `font-label text-[10px] uppercase text-on-surface-variant`
- Tbody empty, to be populated by JS
- **Verification:** Table renders with headers and empty rows, header sticky on scroll

#### 1.6 Implement right sidebar panels
- Panel A: VaR breakdown donut
  - Card with header "VaR Breakdown"
  - Canvas: `<canvas id="var-donut-canvas" width="400" height="200"></canvas>`
- Panel B: Active alerts
  - Header: "Active Alerts" with badge count `<span id="alerts-count">0</span>`
  - List container: `<div id="alerts-list" class="overflow-y-auto max-h-48">`
- Panel C: Stress test results
  - Header: "Stress Tests"
  - Container: `<div id="stress-tests-list">`
- Each panel should have proper borders, padding, and background classes
- **Verification:** All three panels visible, proper heights, scroll individually if content overflows

#### 1.7 Implement bottom compliance event log panel
- Full-width panel with header: "Compliance Event Log"
  - Include count badge: `<span id="compliance-count">0</span>`
- Scrollable table:
  ```html
  <div class="overflow-y-auto max-h-64">
    <table class="w-full">
      <thead>...</thead>
      <tbody id="compliance-log-tbody">...</tbody>
    </table>
  </div>
  ```
- Columns: Time (UTC HH:MM:SS), Event, Status (badge)
- **Verification:** Panel height h-64, scrollable, shows initial rows or empty state

#### 1.8 Add status bar and loading states
- Status bar for errors/messages: `<div id="risk-status-bar" class="hidden px-4 py-2 bg-error/10 border-b border-error text-error text-sm"></div>`
- Optional: loading skeleton overlay (can add later)
- **Verification:** Status bar hidden initially, shows on errors with appropriate message

---

### 2. JavaScript Module Implementation

#### 2.1 Create file structure and IIFE scaffold
- Create file: `dashboard/static/v3/pages/risk_compliance.js`
- Module pattern: `(function() { 'use strict'; ... })();`
- Define COLORS palette from design system:
  ```js
  const COLORS = {
    primary: '#c3f5ff',
    primaryContainer: '#00e5ff',
    onSurface: '#e0e2ea',
    onSurfaceVariant: '#bac9cc',
    outlineVariant: '#3b494c',
    surfaceContainer: '#1c2025',
    error: '#ffb4ab',
    errorContainer: '#93000a',
    success: '#4ade80', // or design system equivalent
    warning: '#fbbf24',
    chart: {
      crypto: '#a855f7',
      fx: '#00e5ff',
      equities: '#fbbf24',
      metals: '#ffd700',
      fixedIncome: '#34d399'
    }
  };
  ```
- Define state variables:
  ```js
  let state = {
    lastData: null,
    pollIntervalId: null,
    isLoading: false,
    errorCount: 0,
    backoffUntil: null,
    chartManager: window.chartManager || {}
  };
  ```
- **Verification:** No syntax errors, script loads without throwing (check console)

#### 2.2 Define formatting utility functions
- `fmt(n, dp=2)` — number with thousand separators, optional decimal places
- `fmtUSD(n)` — currency: `$` prefix, 2 decimals, K/M suffix for large numbers
- `fmtPct(n)` — percentage: multiply by 100, add `%`, 2 decimals
- `escapeHtml(str)` — replace `<` `>` `&` `"` with entities
- `severityIcon(sev)` — returns Material Icon name: `'error'` for breach, `'warning'` for warning, `'info'` for ok
- `severityClass(sev)` — returns Tailwind classes for styling
- **Verification:** Test with sample values: `fmtUSD(12345.67)` → `$12.35K`, `fmtPct(0.045)` → `4.50%`

#### 2.3 Define status bar helpers
- `showStatus(message, type='error')` — set text, remove hidden, apply appropriate classes (`bg-error/10 text-error` or `bg-success/10 text-success`)
- `hideStatus()` — add hidden class
- **Verification:** Show/hide works, correct CSS classes applied

#### 2.4 Implement API fetch with mock support and backoff
- `loadData()` async function:
  - Check mock mode: `window.location.search.includes('mock=1')` OR `window.USE_MOCKS`
  - If mock: return promise resolving to mockData after 300ms delay
  - If real: use `window.apiFetch` to call endpoints in parallel (`Promise.all`)
  - Guard: if `state.isLoading` return cached `state.lastData`
  - On error: increment `errorCount`, calculate backoff (e.g., `Math.min(30000, 1000 * 2 ** errorCount)`), set `state.backoffUntil`, showStatus with retry countdown
  - On success: reset errorCount, backoffUntil, update `state.lastData`
- Return data object containing: overview, strategies, alerts, stressTests, complianceEvents, varBreakdown
- **Verification:** Mock mode returns sample data; real mode handles 401/404; backoff displays countdown

#### 2.5 Implement data validation
- `isValidRiskData(d)` — checks for required keys: `d && d.overview && Array.isArray(d.strategies) && Array.isArray(d.complianceEvents)`
- In `renderAll()`: call validation; if invalid, log warning, use last known good data or show empty states
- **Verification:** Invalid data does not crash, shows status message but page remains usable

#### 2.6 Implement `renderKPIs(data)`
- Extract: `overview = data.overview`
- Update elements by ID:
  - `#kpi-var` → `fmtUSD(overview.var_95_1d_usd)`
  - `#kpi-beta` → `overview.beta.toFixed(2)`
  - `#kpi-margin` → `overview.margin_usage_pct.toFixed(1) + '%'` and update margin bar width
  - `#kpi-pnl` → `fmtUSD(overview.net_pnl)` with color class based on sign
- Apply colors: Var > threshold (e.g., >2% equity) → `text-error`; margin bar fill width = `margin_usage_pct`, color red if >80%
- **Verification:** KPIs update on data load, correct format, color changes based on thresholds

#### 2.7 Implement `renderTable(data)` for strategy metrics
- Extract `strategies = data.strategies`
- Apply current sort (default: sort by VaR descending)
- For each strategy, build table row:
  ```html
  <tr data-symbol="{{symbol}}">
    <td class="px-4 py-2 font-data-md">{{name}}</td>
    <td class="px-4 py-2 font-data-md">{{symbol}}</td>
    <td class="px-4 py-2 font-data-md">{{timeframe}}</td>
    <td class="px-4 py-2"><span class="status-badge {{statusClass}}">{{status}}</span></td>
    <td class="px-4 py-2 text-right font-data-md">{{fmtPct(var)}}</td>
    <td class="px-4 py-2 text-right font-data-md">{{fmtUSD(exposure_k * 1000)}}</td>
    <td class="px-4 py-2 text-right font-data-md">{{fmtPct(max_dd)}}</td>
    <td class="px-4 py-2 text-right font-data-md">{{sharpe.toFixed(2)}}</td>
    <td class="px-4 py-2 text-right font-data-md">{{(win_rate*100).toFixed(1)}}%</td>
    <td class="px-4 py-2 text-center">
      <button class="icon-btn" data-action="details" title="View details">visibility</button>
    </td>
  </tr>
  ```
- Helper `statusClass(status)` returns: active → `bg-success/20 text-success`, inactive → `bg-surface-variant text-on-surface-variant`, paused → `bg-warning/20 text-warning`
- Append to `#strategy-risk-table tbody`
- **Verification:** Table populates, sorting works on all numeric columns (click header toggles asc/desc), status badges have correct styles

#### 2.8 Implement `renderVaRDonut(data)`
- Get `varBreakdown = data.overview.var_breakdown` (object: `{asset_type: usd_value}`)
- Prepare Chart.js data:
  ```js
  const labels = Object.keys(varBreakdown);
  const values = Object.values(varBreakdown);
  const colors = labels.map(l => COLORS.chart[l.toLowerCase()] || COLORS.primary);
  ```
- Use `window.chartManager.createDonutChart('var-donut-canvas', labels, values, colors)`
- If chartManager not available, create chart directly with Chart.js and store in `state.donutChart`
- Destroy previous chart instance before re-creating
- Render legend: create `<div id="var-legend">` with color swatches and percentages
- **Verification:** Donut renders with segments, colors from CHART_COLORS, legend matches, responsive resize works

#### 2.9 Implement `renderAlerts(data)`
- Extract `alerts = data.alerts` array
- Clear `#alerts-list`
- Update count badge: `#alerts-count.textContent = alerts.length`
- For each alert:
  ```html
  <div class="alert-item p-2 border-b border-outline-variant flex items-start gap-2">
    <span class="material-symbols-outlined {{severityIconClass(alert.severity)}}">{{severityIcon(alert.severity)}}</span>
    <div class="flex-1">
      <div class="font-label-sm">{{alert.message}}</div>
      <div class="text-[10px] text-on-surface-variant">{{formatTime(alert.timestamp)}}</div>
    </div>
  </div>
  ```
- **Verification:** Alert count badge updates, alerts list scrollable, icons display with correct color (error=red, warning=amber, info=primary)

#### 2.10 Implement `renderStressTests(data)`
- Extract `stressTests = data.stress_tests` array
- Clear `#stress-tests-list`
- For each test:
  ```html
  <div class="stress-item px-3 py-2 border-b border-outline-variant flex justify-between items-center">
    <span class="font-label-sm">{{test.scenario}}</span>
    <span class="font-data-md {{impactClass(test.impact_pct)}}">{{test.impact_pct > 0 ? '+' : ''}}{{test.impact_pct.toFixed(1)}}%</span>
  </div>
  ```
- `impactClass`: negative → `text-error`, positive → `text-success`
- **Verification:** Stress tests display with scenario names and color-coded impacts

#### 2.11 Implement `renderComplianceLog(data)`
- Extract `events = data.complianceEvents` (sorted by timestamp desc)
- Clear `#compliance-log-tbody`
- For each event:
  ```html
  <tr>
    <td class="px-4 py-2 text-[10px] font-label-sm text-on-surface-variant">{{formatTime(event.timestamp)}}</td>
    <td class="px-4 py-2 font-data-md">{{event.event}}</td>
    <td class="px-4 py-2 text-center">
      <span class="status-badge {{severityClass(event.status)}}">{{event.status}}</span>
    </td>
  </tr>
  ```
- Update count badge: `#compliance-count.textContent = events.length`
- **Verification:** Log scrollable, timestamps in `font-label-sm`, status badges colored correctly (OK=green, Warning=amber, Breach=red)

#### 2.12 Implement polling for compliance events
- `tick()` function:
  - Calls `loadData()` to fetch all data
  - On success, calls `renderAll()` to update UI
  - Starts/stops based on visibility to save resources
- `startPolling()`: set interval using config: `const interval = window.config?.dashboard?.poll_interval_ms || 10000; state.pollIntervalId = setInterval(tick, interval);`
- `stopPolling()`: `clearInterval(state.pollIntervalId);`
- Add `document.addEventListener('visibilitychange', ...)` to pause when tab hidden to reduce load
- **Verification:** Compliance log updates every 10s, network requests visible in devtools, no duplicate intervals after re-render

#### 2.13 Implement sorting handlers for strategy table
- Attach click listeners to table headers (`#strategy-risk-table thead th`)
- On click, determine column and current sort direction; toggle
- Store sort state: `{ column: 'var', direction: 'desc' }`
- In `renderTable()`, sort `strategies` array before rendering:
  ```js
  strategies.sort((a, b) => {
    const valA = a[sortKey], valB = b[sortKey];
    const multiplier = sortDir === 'asc' ? 1 : -1;
    return (valA - valB) * multiplier;
  });
  ```
- Supported sort columns: var, exposure_k, max_dd_pct, sharpe, win_rate, name
- **Verification:** Clicking headers toggles sort direction (visual indicator), table reorders correctly

#### 2.14 Setup initialization and event listeners
- `init()` function:
  - Setup sort handlers
  - Setup refresh button (`#risk-refresh-btn`) to manually trigger `tick()`
  - Call `tick()` for initial load
  - Start polling
- Attach `init` to DOMContentLoaded: `document.addEventListener('DOMContentLoaded', init);`
- Add cleanup: `window.addEventListener('beforeunload', stopPolling);`
- **Verification:** Page loads, data fetches, UI populated, polling starts, manual refresh works

#### 2.15 Add canvas resize handling
- Store chart instances: when creating donut chart, store in `state.donutChart`
- On window resize: `window.addEventListener('resize', () => { if (state.donutChart) state.donutChart.resize(); });`
- If using chartManager, ensure it handles resize automatically (Chart.js responsive option)
- **Verification:** Resize window, donut chart re-renders with correct aspect ratio, no distortion

---

### 3. API Integration and Mock Data

#### 3.1 Define mock data structures
- Create mock data object matching API responses:
  ```js
  const MOCK_DATA = {
    overview: {
      var_95_1d_usd: 8421,
      beta: 1.23,
      margin_usage_pct: 45.2,
      net_pnl: 12500,
      var_breakdown: { crypto: 3000, fx: 2500, equities: 2000, metals: 920, fixed_income: 1 }
    },
    strategies: [
      { name: 'momentum_reversion', symbol: 'BTCUSD', timeframe: 'M15', status: 'Active', var_pct: 2.4, exposure_k: 50, max_dd_pct: 4.2, sharpe: 2.84, win_rate: 0.68 },
      // ... more (5-10 items)
    ],
    alerts: [
      { severity: 'warning', message: 'High concentration in BTC (42%)', timestamp: new Date().toISOString() },
      { severity: 'info', message: 'Daily DD approaching 2% limit', timestamp: new Date().toISOString() }
    ],
    stress_tests: [
      { scenario: 'Market Crash', impact_pct: -12.5 },
      { scenario: 'Volatility Spike', impact_pct: -8.3 },
      { scenario: 'Liquidity Crisis', impact_pct: -5.2 }
    ],
    compliance_events: [
      { timestamp: new Date().toISOString(), event: 'Position limit exceeded on BTCUSD', status: 'Breach' },
      { timestamp: new Date(Date.now()-3600000).toISOString(), event: 'Daily loss threshold 80% reached', status: 'Warning' },
      { timestamp: new Date(Date.now()-7200000).toISOString(), event: 'Margin call warning', status: 'OK' }
    ]
  };
  ```
- **Verification:** Mock data structure matches expected API contract, all fields present

#### 3.2 Implement mock fetch interceptor
- In `loadData()`, detect mock mode: `const useMock = window.USE_MOCKS || window.location.search.includes('mock=1');`
- If useMock: `await new Promise(r => setTimeout(r, 300)); return MOCK_DATA;`
- If real API fails (404) and not mock: log warning, fall back to MOCK_DATA to keep UI functional
- **Verification:** Add `?mock=1` to URL, confirm no network calls to `/api/v3/risk`, mock data displays; remove mock, if backend not ready, fallback to mock with warning

#### 3.3 Handle API errors and graceful degradation
- In `loadData()`, wrap each `apiFetch` in try-catch
- On failure for a specific endpoint, log error but still return partial data (use empty array for missing)
- Update `state.errorCount` and calculate backoff: `backoffMs = Math.min(30000, 1000 * 2 ** errorCount)`
- Set `state.backoffUntil = Date.now() + backoffMs`
- Show status: `showStatus('API error, retrying in ' + Math.ceil(backoffMs/1000) + 's', 'error');`
- On next `tick()`, if `state.backoffUntil > Date.now()`, skip fetch, show countdown
- **Verification:** Simulate 500 error with devtools, page shows retry countdown, other sections retain last data; after backoff expires, fetch retries

---

### 4. Navigation and Active State

#### 4.1 Ensure sidebar highlights active page
- In `_sidebar.html`, ensure the Risk & Compliance nav item exists with `data-page="risk_compliance"` or href `/risk-compliance`
- In `init()`, after DOM ready:
  ```js
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(el => el.classList.remove('active'));
  const active = Array.from(navItems).find(el => el.href.includes('/risk-compliance') || el.dataset.page === 'risk_compliance');
  if (active) active.classList.add('active');
  ```
- Or server-side: base template passes `active_page` variable; ensure route sets context `{"active": "risk_compliance"}` (but this is JS-only page)
- **Verification:** When on /risk-compliance, the left nav item is highlighted with primary border/background

#### 4.2 Add smooth scroll to sections (optional)
- Add anchor IDs to sections: `id="telemetry"`, `id="strategies"`, `id="compliance"`
- Nav links `href="#compliance"` will smooth scroll
- Add `html { scroll-behavior: smooth; }` in global CSS or JS `scrollIntoView({behavior: 'smooth'})`
- **Verification:** Click nav item, page smoothly scrolls to that section

---

### 5. Styling and Design System

#### 5.1 Apply design system colors and typography
- Use Tailwind classes throughout template:
  - Card containers: `bg-surface-container border border-outline-variant rounded`
  - Headers: `font-label-sm text-label-sm uppercase tracking-wider bg-surface-container-high px-4 py-2 border-b border-outline-variant`
  - Text: `text-on-surface`, secondary: `text-on-surface-variant`
  - Number values: `font-data-lg` or `font-data-md` from design system
- Ensure all colors are from the palette, not arbitrary hexes
- **Verification:** Inspect elements in browser devtools; computed colors match design tokens; fonts are Geist/JetBrains Mono

#### 5.2 Responsive layout testing
- Use responsive grid: `grid-cols-1 lg:grid-cols-12`
- KPI tiles: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`
- On mobile (`<1024px`), sidebar may become a drawer (depending on base template). Ensure it collapses correctly and main content margin adjusts.
- Table should scroll horizontally on small screens: wrap in `<div class="overflow-x-auto">`
- Right sidebar stacks below main on tablet? With `lg:col-span-4`, on small screens it will stack vertically (good)
- **Verification:** Resize browser to 375px, 768px, 1024px, 1440px; check layout at each breakpoint; no horizontal overflow, text legible

#### 5.3 Add hover states and transitions
- Table rows: `hover:bg-surface-container-high`
- Buttons: `hover:bg-surface-container hover:text-on-surface`
- KPI tiles: `hover:border-primary/40 transition-colors`
- Nav items: `hover:bg-surface-container-high`
- Add `transition-colors duration-200` where appropriate
- **Verification:** Hover interactions smooth, no layout shift; active states clear

---

### 6. Testing and Validation

#### 6.1 Verify all Phase 6 checkpoints
- [ ] Top telemetry bar displays KPI tiles with correct values
- [ ] Left sidebar navigation highlights active section
- [ ] Strategy risk table loads with correct columns
- [ ] Table sorting enabled on numeric columns
- [ ] VaR breakdown donut renders with segments
- [ ] Active alerts list shows severity icons and text
- [ ] Bottom compliance log scrollable; timestamps in `font-label-sm`
- [ ] New compliance events appear automatically every 10s
- [ ] Canvas charts resize correctly on window resize

#### 6.2 Verify mock mode functionality
- Open `/risk-compliance?mock=1`
- Confirm all sections populated with realistic sample data
- Check network tab: no calls to `/api/v3/risk` (only document request)
- Remove `?mock=1` and confirm real API calls happen (if backend ready)
- **Verification:** Toggle mock on/off, observe data source switch

#### 6.3 Verify error handling
- Simulate 500 error from one endpoint using devtools (Response override)
- Status bar shows retry countdown, other sections retain last valid data
- After max backoff reached, status bar shows error until success
- On successful response, error state clears automatically
- **Verification:** Induce errors, observe behavior; then restore endpoint, verify recovery

#### 6.4 Verify XSS protection
- Test with malicious data in API responses: e.g., `{"event": "<script>alert('xss')</script>"}`
- Ensure `escapeHtml()` is used before inserting into `innerHTML`
- Verify script does not execute, displays escaped text
- **Verification:** Inject test string in mock data, confirm it appears as literal text, not executed

#### 6.5 Verify pagination/scroll behavior
- If strategy list > 20 items, table should scroll within container (not page)
- Header must remain sticky during scroll
- Compliance log should maintain scroll position unless new data prepends
- **Verification:** Populate with 50+ strategies, test scrolling; header stays at top

---

### 7. Optional Enhancements (if time permits)

#### 7.1 Add CSV export for strategy table
- Add button "Export CSV" above table
- On click, build CSV from current sorted/filtered `strategies` array
- Download via blob URL

#### 7.2 Add filtering controls
- Above table: add dropdowns for status (All/Active/Inactive/Paused), timeframe, asset class
- Filter `strategies` array before rendering
- Add clear filters button

#### 7.3 Add stress test visualizations
- If stress_tests include time series, render mini line chart using Chart.js
- Show impact over scenarios

#### 7.4 Add tooltips to KPI tiles
- Add `title` attributes or custom tooltip explaining calculation (e.g., "VaR calculated using Monte Carlo at 95% confidence over 1 day")
- Can use native browser tooltip for simplicity

---

## Completion Criteria

The Risk & Compliance page is complete when:

1. Both HTML and JS files are created without syntax errors
2. All 9 Phase 6 checkpoints verified manually
3. Page loads at `/risk-compliance` with correct layout
4. Data displays in both mock mode and real API mode (if available)
5. Compliance log auto-updates every 10 seconds without flicker or full reload
6. Responsive on desktop (≥1024px), tablet (768-1023px), mobile (<768px)
7. No console errors or warnings on load, polling, or interactions
8. Sidebar navigation highlights "Risk & Compliance" when active
9. Design system colors, typography, spacing consistent with v3 spec
10. Shared components (`_kpi_tile.html`, `_data_table.html`, Chart.js) used correctly
11. API integration handles errors gracefully with exponential backoff and user feedback
12. XSS protection validated — all dynamic content escaped
13. Chart resizing works, sorting works on all numeric columns
14. Status bar displays errors and retry information

---

## CSV Task Summary

```
Task ID,Subject,Status,Dependencies
1.1,Create HTML file and extend base template,Pending,None
1.2,Implement top telemetry bar with KPI tiles,Pending,1.1
1.3,Implement left sidebar navigation (240px),Pending,1.1
1.4,Implement main 3-column grid layout,Pending,1.1
1.5,Implement strategy risk metrics table section,Pending,1.4
1.6,Implement right sidebar panels (VaR donut, alerts, stress tests),Pending,1.4
1.7,Implement bottom compliance event log panel,Pending,1.4
1.8,Add status bar and loading states,Pending,1.1
2.1,Create JS file with IIFE scaffold and COLORS,Pending,1.1
2.2,Define formatting utility functions,Pending,2.1
2.3,Define status bar helpers,Pending,2.1
2.4,Implement API fetch with mock support and backoff,Pending,2.3
2.5,Implement data validation,Pending,2.4
2.6,Implement renderKPIs,Pending,2.5
2.7,Implement renderTable for strategy metrics,Pending,2.6
2.8,Implement renderVaRDonut with Chart.js,Pending,2.6
2.9,Implement renderAlerts,Pending,2.6
2.10,Implement renderStressTests,Pending,2.6
2.11,Implement renderComplianceLog,Pending,2.6
2.12,Implement polling loop with config interval,Pending,2.11
2.13,Implement sorting handlers,Pending,2.7
2.14,Setup init and event listeners,Pending,2.13
2.15,Add canvas resize handling,Pending,2.8
3.1,Define mock data structures for all endpoints,Pending,2.4
3.2,Implement mock fetch interceptor,Pending,3.1
3.3,Handle API errors and fallbacks,Pending,3.2
4.1,Ensure sidebar active state highlighting,Pending,1.3
4.2,Add smooth scroll to sections (optional),Pending,4.1
5.1,Apply design system colors and typography,Pending,1.2-1.7
5.2,Responsive layout testing,Pending,5.1
5.3,Add hover states and transitions,Pending,5.1
6.1,Verify all Phase 6 checkpoints,Pending,6.3
6.2,Verify mock mode functionality,Pending,6.1
6.3,Verify error handling,Pending,6.2
6.4,Verify XSS protection,Pending,6.3
6.5,Verify pagination/scroll behavior,Pending,6.4
7.1,Add CSV export button (optional),Pending,6.5
7.2,Add filtering controls (optional),Pending,6.5
7.3,Add stress test visualizations (optional),Pending,6.5
7.4,Add KPI tooltips (optional),Pending,6.5
```

**Total estimated atomic tasks:** 50

---

**Implementation notes:**
- Proceed in order; each section builds on the previous.
- Use the **Write tool** exclusively for `.py` and `.html` files.
- After each file write, run Python/HTML verification:
  ```powershell
  .\venv\Scripts\python.exe -c "import py_compile; py_compile.compile('dashboard/templates/v3/pages/risk_compliance.html', doraise=True); print('OK')"
  ```
- For `.js` files, use ESLint or check console in browser.
- Always commit working code after each successful task batch.

---

**Ready to begin execution.**
