# Portfolio Risk Monitor — Implementation Tasks (Compressed)

**Feature:** Portfolio Risk Monitor page rebuild for v3 dashboard  
**Branch:** `v3-dashboard`  
**Status:** Planned  
**Reference:** `DASHBOARD_DOCUMENTATION.md`, `V3_FRONTEND_REDESIGN_PLAN.md`, `V3_SEQUENTIAL_BUILD_PLAN.md`  
**v2 Reference:** `dashboard/templates/pages/page_portfolio_risk.html`  
**v3 Deliverables:**
- Template: `dashboard/templates/v3/pages/portfolio_risk.html`
- JavaScript: `dashboard/static/v3/pages/portfolio_risk.js`
- API endpoint: `GET /api/v3/risk/overview` (in `dashboard/app.py`)

---

## Feature Description

The Portfolio Risk Monitor displays real-time risk metrics: 5 KPI panels (Daily DD %, Weekly DD %, Total Exposure USD, VaR 95% 1D USD, Margin Usage %), open positions table, asset allocation donut (Canvas), strategy exposure bars, correlation matrix, and risk alerts. Polls every 6 seconds.

---

## Task List

### 1. Analyze v2 and Define v3 API Contract

**Description:**
- Review v2 implementation to understand data structures, rendering logic, color scheme, polling, and helper functions
- Define complete JSON schema for `/api/v3/risk/overview` response including:
  - `kpis`: daily_dd_pct, weekly_dd_pct, total_exposure_usd, var_95_1d_usd, margin_usage_pct
  - `positions[]`: account, symbol, side, entry, price, size, sl, tp, pnl, risk_pct
  - `asset_allocation`: {crypto, fx, equities, metals, fixed_income} → percentage
  - `strategy_exposure_usd`: {group_name} → usd exposure
  - `correlation_matrix`: {labels[], matrix[][]}
  - `alerts[]`: {severity, symbol, message, ts}
- Document alert thresholds (concentration >35%, daily DD < -2%, margin >80%, free margin <20%)
- Create sample response for development

**Dependencies:** None  
**Acceptance:** Schema documented; sample data created; backend agreement on feasibility

---

### 2. Implement Backend Endpoint `/api/v3/risk/overview`

**Description:**
- Add FastAPI route in `dashboard/app.py` (or appropriate router)
- Query open positions from `Trade` table (status='open' or live positions)
- Compute KPIs from account snapshots and position data
- Calculate asset allocation by symbol → asset class mapping (need asset class mapping strategy)
- Compute strategy exposure grouped by strategy group (map strategies to groups: trend, mean_reversion, etc.)
- Build correlation matrix from recent trade returns per strategy group (last 30 days)
- Generate alerts by evaluating thresholds
- Return JSON-serializable response with proper types and ISO date strings

**Acceptance:**
- Endpoint returns 200 with correct schema
- Requires JWT auth (`_get_current_user` dependency)
- Handles zero positions gracefully
- Query performance <500ms
- All data validated and typed

**Dependencies:** Task 1  
**Risks:** Correlation computation may need caching; asset class mapping needs definition

---

### 3. Create Complete HTML Template and JavaScript Module

**Description:** (All in one pass — multiple file writes)

**A. Template** (`dashboard/templates/v3/pages/portfolio_risk.html`):
- Extend `v3/_base.html`
- Structure: 5 KPI panels (top row), main grid with positions table + right sidebar (alloc donut + strat exposure bars), bottom row (correlation matrix + alerts)
- All required IDs: `kpi-daily-dd`, `kpi-weekly-dd`, `kpi-exposure`, `kpi-var`, `kpi-margin`, `positions-tbl`, `positions-count`, `alloc-canvas`, `alloc-gross`, `alloc-legend`, `strat-bars`, `corr-grid`, `corr-headers`, `corr-body`, `alerts-list`, `alerts-count`
- Use MD3 design tokens: `surface-container-low`, `outline-variant`, `primary-fixed-dim`, etc.
- Responsive layout; sticky header for table; canvas container 128×128

**B. JavaScript** (`dashboard/static/v3/pages/portfolio_risk.js`):
- IIFE module with self-initialization
- Polling: 6000ms interval (respect `window.config?.dashboard?.poll_interval_ms` if present)
- `tick()` → `loadData()` → `renderAll()`
- Render functions:
  - `renderKPIs(d)`, `renderPositions(d)`, `renderAlloc(d)` (Canvas donut), `renderStratExp(d)` (bars), `renderCorrelation(d)` (CSS grid), `renderAlerts(d)`
- Helpers: `fmt()`, `fmtUSD()`, `severityIcon()`, `severityClass()`
- Error handling: keep previous data on failure, log warnings, show toast on repeated errors
- Status bar integration (use `showStatus()` / `hideStatus()` from base if available)
- Cleanup on `beforeunload`

**Acceptance:**
- All IDs match template
- Canvas donut renders correctly with legend and center label
- Correlation matrix displays N×N grid with diagonal highlighting and strong correlation styling
- Positions table scrolls with sticky header
- All formatting correct (5 decimals for prices, 2 for size/risk, colorized PnL)
- No console errors

**Dependencies:** Task 2 (API endpoint available)  
**Risks:** Canvas rendering may need tweaking; ensure no memory leaks

---

### 4. Add Loading States, Error Handling, and Responsive Behavior

**Description:**
- Enhance template with loading indicators ("—" for KPIs, "Loading…" for others)
- Add empty states ("No open positions", "No alerts", "Insufficient data for correlation")
- Implement retry logic: guard against overlapping ticks; exponential backoff for 429/503
- Validate data before rendering (check required fields)
- Add sidebar collapse responsiveness: test with 48px and 240px widths; ensure no horizontal overflow
- Verify all breakpoints (desktop, tablet, mobile)
- Add `min-h-0` where needed for flex children scrolling

**Acceptance:**
- Initial load shows loading states appropriately
- Errors show toast notifications, not `alert()`
- Old data persists during refresh
- Layout intact at all widths
- No horizontal scrollbar on sidebar collapse

**Dependencies:** Task 3  
**Risks:** Table may overflow; may need horizontal scroll within container

---

### 5. Test, Document, and Finalize

**Description:**
- Manual integration testing: verify all KPIs, positions table, donut, bars, correlation matrix, alerts render correctly
- Test polling cycles (data updates without flicker)
- Test error scenarios (disconnect backend, invalid data)
- Test empty states (no positions, no alerts)
- Verify no console errors or warnings
- Update `DASHBOARD_DOCUMENTATION.md` with API schema, page description, screenshots
- OPTIONAL: integrate with notification system if alerts should trigger bell notifications
- Commit all changes with conventional commit message

**Acceptance:**
- Feature fully functional in browser
- Documentation updated
- No known defects
- Git history clean

**Dependencies:** Tasks 1-4  
**Risks:** Minor visual tweaks may be needed after review

---

**Total Tasks:** 5  
**Key Dependencies:** API contract defined first; backend then frontend; testing last  
**Notes:**
- Task 3 combines multiple file writes but they are distinct files (HTML vs JS) — dev agent will write each separately
- All files follow v3 design system and coding standards
- Backend must ensure efficient correlation computation (cache if needed)
