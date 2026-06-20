# Phase 3: Trade Operations — Task Plan

**Generated:** 2025-06-16  
**Branch:** v3-dashboard  
**Reference:** V3_SEQUENTIAL_BUILD_PLAN.md (pages 136-188)  
**Goal:** Implement Trade Operations page with live executions, execution quality metrics, historical trade log, and journal annotations panel.

---

## Current State Assessment

### Existing Assets
- Base layout templates: `_base.html`, `_sidebar.html`, `_topbar.html` ✓
- Shared JS: `api.js`, `charts.js`, `utils.js` ✓
- API endpoints required for this phase are already available in:
  - `dashboard/app.py`: `/api/mt5/positions`, `/api/mt5/orders`, `/api/trades/recent`
  - `dashboard/v2/`: `/api/v2/accounts/summary`, `/api/v2/engine/status`, `/api/v2/mt5/connection`, `/api/v2/journal/annotations`
- Route handler in `dashboard/app.py` (line 707-709): `/trade-ops` → renders `trade_ops` page

### Missing Assets
- `dashboard/templates/v3/pages/trade_operations.html` (to create)
- `dashboard/static/v3/pages/trade_operations.js` (to create)

---

## Task List

### T1: Create HTML Template Structure
**File:** `dashboard/templates/v3/pages/trade_operations.html`  
**Depends on:** Foundation templates (Phase 0-1)  
**Risk:** LOW

Create page extending `_base.html` with:
- Fixed top bar (h-12): search input, filters button, account selector, regime button, connection status, notifications icon, profile avatar
- Main grid (12 columns):
  - Panel 1-3 (col-span-8): Live Executions & Pending Orders table with sticky header
  - Panel 4 (col-span-4): Execution Quality metrics (4 metric boxes + progress bars for slippage, latency, fill rate, rejections)
  - Panel 5 (col-span-7): Historical Trade Log table
  - Panel 6 (col-span-5): Journal & Annotations panel with tag chips, observation form, annotation list
- Fixed bottom bar (h-6): port label, sync timestamp, engine status, ticker clock
- All UI components using design system classes (Tailwind, Material palette)
- Proper data-bind attributes for JavaScript initialization

**Checklist:**
- [ ] Page extends `_base.html` with correct active nav state
- [ ] Top bar contains all required controls in flex layout
- [ ] Main grid uses Tailwind grid-cols-12 with proper col-span classes
- [ ] Tables use sticky headers (`sticky top-0`) with correct z-index
- [ ] Bottom bar fixed at bottom with monospace ticker clock
- [ ] All placeholder containers have unique IDs for JS mounting
- [ ] Empty states present for tables (e.g., "No executions" message)
- [ ] Responsive classes ensure mobile/tablet compatibility

---

### T2: Implement JavaScript Core Functions
**File:** `dashboard/static/v3/pages/trade_operations.js`  
**Depends on:** T1, `shared/api.js`, `shared/utils.js`  
**Risk:** LOW

Implement the following functions:

1. **`init()`** — calls `loadAll()` on DOMContentLoaded
2. **`loadAll()`** — parallel fetch: `loadExecutions()`, `loadExecQuality()`, `loadHistoricalLog()`, `updatePort()`, `updateEngineStatus()`
3. **`loadExecutions()`** — GET `/api/mt5/positions` and `/api/mt5/orders`, render both into unified table with type badge (POSITION/ORDER)
4. **`loadExecQuality()`** — compute metrics from recent trades (last 50), update progress bars for slippage, latency, fill rate, rejections
5. **`loadHistoricalLog()`** — GET `/api/trades/recent?limit=50`, render table, bind click to populate journal panel
6. **`updatePort()`** — GET `/api/v2/accounts/summary`, update port label in bottom bar
7. **`updateEngineStatus()`** — GET `/api/v2/engine/status`, update engine status indicator (green/red dot) and latency
8. **`updateTicker()`** — update clock every second with UTC time
9. **`reloadAll()`** — wrapper to refresh all data panels

**Helper functions:**
- `computeExecQuality(trades)` — calculate avg slippage, fill rate, rejection rate from recent closed trades
- `renderExecutionsTable(positions, orders)` — unified table with columns: Symbol, Side, Entry, Current Price, SL, TP, Lot, PnL, Actions (Close button)
- `renderExecQuality(metrics)` — update 4 metric boxes and progress bar widths
- `renderHistoricalTable(trades)` — table with columns: Time, Symbol, Side, Entry, Exit, Lot, PnL, Tags
- `populateJournalFromTrade(tradeId)` — load annotations for selected trade, highlight selected row
- `loadAnnotations(tradeId)` — GET `/api/v2/journal/annotations?trade_id=`
- `addObservation()` — POST new annotation with note + tag from form, then refresh list
- `commitObservation()` — combine note and tag, call `addObservation()`, clear form
- `flash(msg, type?)` — temporary toast notification (reuse from shared/utils.js if available)

**Polling:** `setInterval(loadAll, 8000)` (configurable later via `config.dashboard.poll_interval_ms`)

**Checklist:**
- [ ] All data fetched via `window.apiFetch()` (respects JWT)
- [ ] Tables render with correct number formatting (price decimals, PnL colors: green/red)
- [ ] Close position button shows confirmation before calling MT5 adapter (stub for now)
- [ ] Historical trade click highlights row and populates journal panel
- [ ] Journal annotation form submits via POST,成功后清空表单并刷新列表
- [ ] Delete button on annotations calls DELETE endpoint, removes from DOM on success
- [ ] Tag chips toggle visual state on click (for future filtering)
- [ ] Engine status indicator: green (running), red (stopped), yellow (error)
- [ ] Ticker clock updates every second, shows UTC time in HH:MM:SS format
- [ ] Polling refreshes data without flicker or race conditions (debounce if needed)
- [ ] Error handling: apiFetch failures show `flash()` error message, keep old data

---

### T3: Styling and Responsive Validation
**File:** `dashboard/static/v3/styles.css` (if needed) or inline classes  
**Depends on:** T1, T2  
**Risk:** LOW

- Ensure tables scroll horizontally on mobile (`overflow-x-auto`)
- Sticky headers maintain position during scroll
- Progress bars animate smoothly on updates
- Modal dialogs (if any) centered with backdrop
- Test breakpoints: mobile (<768px), tablet (768-1024px), desktop (>1024px)
- Sidebar collapse interaction doesn't break layout (already ensured by base template)

**Checklist:**
- [ ] Tables use `min-w-full` and container with `overflow-x-auto` on small screens
- [ ] Progress bars have transition CSS for smooth width changes
- [ ] Top bar controls wrap or truncate on narrow viewports
- [ ] Bottom bar stays fixed without overlapping content (adequate padding-bottom on main)
- [ ] All interactive elements have hover/focus states

---

### T4: Integration Testing
**Depends on:** T1, T2, T3  
**Risk:** MEDIUM

1. **Route Testing**
   - Navigate to `/trade-ops` (or `/v3/trade_operations` if using v3 renderer)
   - Verify page loads without 404s (template exists, static assets load)
   - Check browser console for JS errors

2. **Data Loading**
   - Verify all 5 panels populate with data or empty states
   - Confirm `loadAll()` completes within polling interval (8s)
   - Check that no API calls are made to wrong endpoints (inspect Network tab)

3. **Interaction Testing**
   - Click historical trade → journal panel populates with its annotations
   - Submit new annotation → appears in list immediately
   - Delete annotation → removed from DOM after successful DELETE
   - Close position button (mock) → shows confirmation, logs action

4. **Polling**
   - Wait 8s → verify data refreshes automatically
   - Simulate API error (offline mode) → error toast shows, old data preserved

5. **Cross-browser check** (at least Chrome, Firefox)

**Checklist:**
- [ ] No console errors or warnings (except expected 401 if not logged in)
- [ ] All API calls return 200/201 (or graceful 401/403 handling)
- [ ] Tables update in place without full page reload
- [ ] Polling interval consistent (no overlapping requests)
- [ ] Memory leak check: intervals cleared on page navigate away (if SPA behavior)

---

## Notes and Assumptions

1. **API v2 vs v3**: The build plan references both `/api/` and `/api/v2/` endpoints. All required endpoints exist in the v2 router mounted at `/api/v2/`. For consistency with existing code, using `/api/v2/` endpoints is preferred.

2. **Execution Quality Metrics**: The build plan mentions "Execution Quality" with 4 metric boxes and progress bars. The exact metrics are:
   - Slippage (average % difference between expected and actual fill)
   - Latency (ms from signal to execution)
   - Fill Rate (percentage of orders filled)
   - Rejections (percentage of orders rejected)
   
   These will be computed from recent closed trades (last 50). If data is insufficient, show "N/A" or mock values.

3. **Account Selector**: Top bar includes "Account selector". Since multi-account support exists in v2 (`/api/v2/accounts/`), the selector should fetch accounts and allow switching. This is a stub for now – selection can highlight the chosen account in UI but actual MT5 operations will use default `config.mt5.login`.

4. **Regime Button**: Likely a toggle for trading regime (trending/ranging). This can be a UI placeholder that sends a websocket message or stores preference in localStorage. Since no specific backend endpoint, treat as frontend-only toggle for now.

5. **Tag Chips**: The journal panel includes "Tag chips selection". These are likely predefined tags (e.g., "post-mortem", "alpha-factor", "regime-change") that can be toggled to filter annotations. Implement as clickable badges that toggle active state; actual filtering can be stub.

6. **Close Position**: The "Close position" button on each execution row should:
   - Show confirmation modal (use `_modal.html` partial)
   - Call MT5 adapter to close position (this would require `/api/mt5/position/{id}/close` endpoint which may not exist yet)
   - On success, remove from table and show success toast
   
   If endpoint doesn't exist, log to console and show "Not implemented" toast.

7. **Bottom Bar**: Includes port label, sync timestamp (last data refresh), engine status, ticker clock.
   - Port label: probably static "Savanna Capital Quant OS" or selected portfolio name
   - Sync timestamp: update after each successful `loadAll()`
   - Engine status: from `/api/v2/engine/status` (`running` boolean)
   - Ticker clock: simple `setInterval` updating text content

8. **Sticky Headers**: The "Live Executions & Pending Orders" table spans col-span-8 and should have sticky header. Use Tailwind `sticky top-0` on `<thead>` and ensure parent has `overflow-y-auto` with a fixed height (e.g., `max-h-[calc(100vh-200px)]`). The bottom bar is fixed, so adjust main content padding accordingly.

9. **Search Input**: Top bar search input can filter the historical trade log in real-time (client-side). For executions, it may filter by symbol. This is a frontend filter; no backend endpoint needed yet.

10. **Filters Button**: Likely opens a dropdown with additional filters (date range, strategy, outcome). Can be stub for now – clicking opens empty dropdown or shows "Coming soon" toast.

---

## Deliverables

1. `dashboard/templates/v3/pages/trade_operations.html` — full HTML template
2. `dashboard/static/v3/pages/trade_operations.js` — full JavaScript module
3. (Optional) `dashboard/static/v3/styles.css` updates if custom styles needed

---

## Completion Criteria

- [ ] Page renders at `/trade-ops` and `/v3/trade_operations` (both routes if needed)
- [ ] All 6 panels visible and correctly sized (8+4+7+5 columns sum to 12? Actually panel layout is: 8 cols for executions, 4 for exec quality, 7 for historical log, 5 for journal = 24 cols total, so must be a 2-row layout: row1 = 8+4=12 cols, row2 = 7+5=12 cols)
- [ ] Data loads from real APIs (no mock data in final version, but can fallback to mock if API fails for demo)
- [ ] Historical trade selection populates journal panel with annotations
- [ ] New annotation created via form appears in list
- [ ] Delete annotation removes it from DB and UI
- [ ] Polling updates data every 8s without visual glitches
- [ ] No console errors in normal operation
- [ ] Responsive: tables scroll on mobile, top bar controls wrap, bottom bar remains visible

---

## Post-Implementation Steps

1. Run py_compile on new .py files (none in this phase)
2. Verify HTML structure with Jinja2 (no template syntax errors)
3. Test with browser DevTools: Network tab shows all API calls succeed (200)
4. Add to git staging when complete and user confirms functionality
5. Update `SESSION_STATE.md` with completion note

---

**End of Plan**
