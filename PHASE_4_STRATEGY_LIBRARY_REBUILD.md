# Phase 4: Strategy Library Rebuild

**Generated:** 2025-06-16  
**Branch:** v3-dashboard  
**Reference:** V3_SEQUENTIAL_BUILD_PLAN.md (pages 189-245), V3_FRONTEND_REDESIGN_PLAN.md (pages 76-98)  
**Source Template:** dashscreens/stitch_savanna_quant_os/strategy_library/code.html

---

## 1. Introduction

Phase 4 implements the Strategy Library page, a central hub for viewing, managing, and refactoring trading strategies. The UI is based on a reference template `code.html` that demonstrates a sophisticated 3‑column layout with a slide‑up detail panel, charts, and modals. The implementation must integrate with the existing V3 design system (Material Design 3 tokens, Geist/JetBrains Mono fonts) and reuse shared partials (`_kpi_tile.html`, `_data_table.html`, `_chart_card.html`, `_status_badge.html`, `_modal.html`).

---

## 2. Layout and Widgets (from reference)

### 2.1 Overall Structure
- **Top bar** (fixed height): search input, view toggles, regime filter, ML override.
- **Left sidebar** (240px): filter controls (asset class, status, tags).
- **Center content** (responsive grid or table): displays strategy list.
- **Right slide‑up panel** (340px): detail view for a selected strategy.
- **Footer/bottom bar** may include sync timestamp, engine status, ticker – not present in reference; if needed, reuse generic bottom bar from other pages.

### 2.2 Widget Details

#### Top Bar
- `input[type="search"]` – placeholder "Search strategies..."
- Button group: Table, Grid, Evidence (active class indicates current view)
- Dropdown: Regime (All, Trending, Ranging, Volatile)
- Toggle switch: ML Override (include/exclude ML‑prioritized strategies)

#### Left Sidebar (Filters)
- Asset Class: `<select>` with options (All, Crypto, Forex, Stocks, Commodities, Indices)
- Status: checkboxes or toggle buttons for Active, Inactive, Paused
- Tag filter: list of clickable chips (e.g., "post‑mortem", "alpha‑factor", "regime‑change")
- Clear filters: button with icon

#### Center – Strategy List
**Grid View** (default)
- Card component (padding, surface background, subtle border):
  - Header: strategy `name` (bold) and `label` (subtitle)
  - Badges: `symbol` (e.g., BTCUSD), `timeframe` (e.g., M15), `status` (active/inactive), `version`
  - Metrics row (4‑col grid): Trades, Win Rate, Profit Factor, Sharpe (or Max DD)
  - Optional: sparkline (mini Chart.js line) showing recent equity curve
  - Actions row: toggle active (switch), copy (icon button), edit params (icon button), details (icon button)

**Table View**
- Columns: Name, Label, Symbol, TF, Status, Version, Trades, WR, PF, Sharpe, Max DD, ML toggle, Actions
- Sticky header
- Sortable? (optional)

**Evidence View**
- Timeline or table combining: recent trades, generated signals, backtest runs, version changes.
- Each entry type indicated by icon + description + timestamp.

#### Right Detail Panel (Slide‑up)
- Panel slides up from bottom‑right with CSS `transform: translateY(0)` from `translateY(100%)`; backdrop optional.
- **Header**: strategy name (display) and close (✕) button.
- **Tabs/Sections** (vertical navigation or accordion):
  1. **Overview** – 7 KPI tiles in a grid:
     - Total Trades, Win Rate, Profit Factor, Sharpe Ratio, Max Drawdown, Return (since inception), Risk (current risk per trade)
  2. **Equity Curve** – Chart.js line chart with fill under curve; x‑axis time, y‑axis equity.
  3. **Monte Carlo** – 50 simulated equity paths (light opacity 0.3) plus median path highlighted.
  4. **Monthly Returns** – Bar chart (or heatmap) with 12 months per year; green for positive, red for negative; opacity proportional to return magnitude.
  5. **Trades** – table of recent trades (open/closed) with columns: ID, Side, Entry, Exit, Lot, PnL, Commission, Tags.
  6. **Backtest Results** – list of backtest runs; each expandable to show trades and metrics.
  7. **Version History** – list of parameter versions with timestamp and diff (optional).
  8. **Deployment History** – timeline of when strategy was activated/deployed.
  9. **Settings** – button opens Edit Params modal.
- **Action Buttons** (maybe in header or footer):
  - Edit Params (opens modal)
  - Copy Strategy (opens modal)
  - Toggle Active (immediate)
  - Deploy (queue for live trading)

#### Modals
Both modals use `_modal.html` partial.

**Edit Params Modal**
- Title: "Edit Strategy Parameters"
- Textarea with JSON content (pretty‑printed).
- Validation: on OK, try `JSON.parse`; if invalid, show error and prevent close.
- Save via `PUT /api/v3/strategies/{name}/params` (or similar).
- Buttons: Cancel, Save.

**Copy Strategy Modal**
- Title: "Copy Strategy"
- Fields:
  - New Strategy Name (text input, required)
  - Primary Symbol (text input, optional, defaults to source symbol)
  - Description (maybe)
- On OK: POST `/api/v3/strategies/copy` with payload `{source_name, new_name, symbol, params (optional)}`.
- Buttons: Cancel, Create.

---

## 3. Task List (14 tasks)

**TASK LIST — Phase 4: Strategy Library Rebuild**

Generated: 2025-06-16

1. **Read and analyze reference template** — Examine `dashscreens/stitch_savanna_quant_os/strategy_library/code.html` to extract all UI components, layout structure, data requirements, and behavior specifications.  
   Depends on: none  
   Risk: LOW

2. **Create `dashboard/templates/v3/pages/strategy_library.html`** — Implement the 3‑column layout (240px left filters, 8‑column center grid, 340px right detail panel) extending `_base.html` with all design system classes (Material Design 3 palette, Geist/JetBrains Mono fonts).  
   Depends on: Task 1  
   Risk: MEDIUM

3. **Create `dashboard/static/v3/pages/strategy_library.js` module** — Set up module scaffold: `init()`, `loadAll()`, API fetching via `window.apiFetch`, view toggles (Table/Grid/Evidence), filter logic, detail panel open/close.  
   Depends on: Task 1  
   Risk: MEDIUM

4. **Implement strategy grid and table rendering** — Functions `renderGrid(strategies)` and `renderTable(strategies)`, correct data binding, click handlers to open detail panel, view toggle with `localStorage` persistence.  
   Depends on: Task 3  
   Risk: LOW

5. **Implement detail panel charts** — Initialize Chart.js instances for equity curve (line + fill), Monte Carlo (50 light lines, opacity 0.3), and monthly returns (bar chart); ensure charts destroy/recreate on panel open/close to avoid memory leaks.  
   Depends on: Task 3, Task 4  
   Risk: MEDIUM

6. **Implement detail panel metrics and tables** — Add KPI tile grid, trade history table, backtest results accordion, version history list, deployment timeline. Fetch data from corresponding API endpoints.  
   Depends on: Task 4, Task 5  
   Risk: LOW

7. **Implement modals (Edit Params, Copy Strategy)** — Build modals using `_modal.html` partial; JSON validation in Edit Params; Copy Strategy form with name/symbol inputs; ensure modal IDs/URIs are prefixed with `strategy-library-` to avoid conflicts.  
   Depends on: Task 3, Task 4  
   Risk: [CONFLICT RISK]

8. **Wire all API endpoints** — Implement GET/POST/PUT calls for:
   - GET `/api/v3/strategies/` (list)
   - GET `/api/v3/strategies/{name}/equity`
   - GET `/api/v3/strategies/{name}/monte-carlo`
   - GET `/api/v3/strategies/{name}/performance` (for KPIs)
   - GET `/api/v3/strategies/{name}/trades`
   - GET `/api/v3/strategies/{name}/backtests`
   - GET `/api/v3/strategies/{name}/versions`
   - GET `/api/v3/strategies/{name}/evidence` (combined log)
   - POST `/api/v3/strategies/{name}/toggle`
   - PUT `/api/v3/strategies/{name}/params`
   - POST `/api/v3/strategies/copy`
   Include error handling and loading states.  
   Depends on: Task 3, Task 4, Task 5, Task 6  
   Risk: MEDIUM

9. **Implement filter and view controls** — Wire search input, asset class dropdown, status toggles, tag chips; connect regime filter and ML override toggle; apply filters to strategy list in both grid and table views.  
   Depends on: Task 4, Task 8  
   Risk: LOW

10. **Set up polling (30s)** — `setInterval(() => loadAll(), 30000)`; if detail panel open, refresh detail data only; clear interval on `beforeunload`.  
    Depends on: Task 8, Task 9  
    Risk: LOW

11. **Add loading states and error handling** — Spinners/skeletons for all async operations; `flash()` messages for errors; proper empty‑state rendering (e.g., “No strategies match your filters”).  
    Depends on: Task 8, Task 9, Task 10  
    Risk: LOW

12. **Verify design system compliance** — Ensure colors use MD3 tokens, typography uses Geist/JetBrains Mono, spacing follows 4px grid, and components reuse shared partials (`_kpi_tile`, `_data_table`, `_chart_card`, `_status_badge`).  
    Depends on: Task 2, Task 5, Task 6  
    Risk: LOW

13. **Test accessibility and responsiveness** — Keyboard navigation, ARIA labels, color contrast; test breakpoints (mobile/tablet/desktop); ensure charts resize correctly.  
    Depends on: Task 2, Task 12  
    Risk: LOW

14. **Integration testing and verification** — Test full flow: load strategies, open detail, edit params, copy strategy, toggle active, view charts; verify no console errors; use mock API (`?mock=1`) if backend endpoints not ready.  
    Depends on: Task 8, Task 10, Task 11, Task 12, Task 13  
    Risk: MEDIUM

---

## 4. Acceptance Criteria

- Page renders at `/v3/strategy_library` without errors.
- All 3 views (Table, Grid, Evidence) switch correctly and persist preference in `localStorage`.
- Filters (search, asset class, status, tags, regime, ML override) filter the strategy list instantly.
- Clicking a strategy opens the right detail panel; panel slides smoothly.
- All charts (equity, Monte Carlo, monthly returns) render with correct data and resize properly.
- Modals open/close; Edit Params validates JSON; Copy Strategy creates a new strategy via API.
- Polling updates data every 30s without UI flicker.
- No console errors or warnings in normal operation.
- Mobile/tablet/desktop layouts stable (tables scroll horizontally if needed).
- All colors, fonts, spacing follow the MD3 design system.
- Reusable partials used where applicable.

---

## 5. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API endpoints missing or mismatched | High | Review existing v2/v3 APIs; add stubs if needed; use `apiFetch` with fallback |
| Chart performance with many Monte Carlo lines | Medium | Limit to 50 lines, use `dataset.hidden` toggles, optimize rendering |
| Modal ID conflicts with other pages | Medium | Prefix all IDs with `strategy-library-` |
| Copy strategy requires new backend endpoint | Medium | If not present, implement minimal copy handler in strategies router |
| Reference template uses different class names | Low | Map to design tokens; create translation layer if needed |
| Large number of strategies causes slowdown | Medium | Implement virtual scroll for table/grid if necessary; debounce filter |

---

## 6. Notes and Assumptions

- The reference template `code.html` is a standalone prototype. We will **override** any parts that are less detailed or conflict with the overall system feel (e.g., if it uses custom colors not in MD3, replace with tokens). The goal is to preserve the *feel* and usability.
- The V3 backend already provides many strategy‑related endpoints under `/api/v2/`; new endpoints (equity, Monte Carlo, evidence, copy) may need to be created in Phase 4. If not ready, the frontend will use mock data when `?mock=1` is present.
- The `_base.html` layout already includes sidebar and topbar; the strategy library page must **not** duplicate them. Remove any navigation elements from the reference template.
- All file writes will use the **Write** tool with UTF‑8 encoding; after each HTML write, we will run a quick sanity check (Jinja2 compile, `<html` tag presence).
- The task list is ordered to minimize rework; tasks that produce shared infrastructure (like chart components) come before dependent features.
- The copy/refactor feature creates a new strategy record with a new name and optionally a new primary symbol. The parameter set is duplicated; user can then edit params via the Edit Params modal.
- If any task touches execution logic or MT5 adapter, it would be marked SAFETY CRITICAL, but this phase is frontend‑centric; no safety‑critical changes are expected.

---

**End of document**
