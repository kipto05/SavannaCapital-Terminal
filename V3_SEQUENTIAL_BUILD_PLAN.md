










# V3 Dashboard Sequential Build Plan

**Based on:** V3_FRONTEND_REDESIGN_PLAN.md, DASHBOARD_DOCUMENTATION.md
**Build Order:** 16 sequential phases from base to profile
**Checkpoints:** Each page/module includes template, JS, API, charts, and sub-components completion markers

---

## PHASE 0: FOUNDATION (Prerequisite for all pages)

### Files to Create First
- `dashboard/templates/v3/_base.html`
- `dashboard/templates/v3/_sidebar.html`
- `dashboard/templates/v3/_topbar.html`
- `dashboard/templates/v3/_theme.html`
- `dashboard/templates/v3/partials/_kpi_tile.html`
- `dashboard/templates/v3/partials/_data_table.html`
- `dashboard/templates/v3/partials/_chart_card.html`
- `dashboard/templates/v3/partials/_status_badge.html`
- `dashboard/templates/v3/partials/_form_field.html`
- `dashboard/templates/v3/partials/_modal.html`
- `dashboard/static/v3/app.js`
- `dashboard/static/v3/theme.js`
- `dashboard/static/v3/components/sidebar.js`
- `dashboard/static/v3/components/topbar.js`
- `dashboard/static/v3/components/charts.js`
- `dashboard/static/v3/shared/api.js`
- `dashboard/static/v3/shared/utils.js`
- `dashboard/static/v3/shared/websocket.js`
- `dashboard/static/v3/styles.css` (optional overrides)

**Checklist:**
- [ ] Base template extends with `{% block content %}`
- [ ] Sidebar renders all navigation items listed above
- [ ] Sidebar collapse reduces width to 48px, labels hidden
- [ ] Main content margin shifts from `ml-[240px]` to `ml-[48px]`
- [ ] Top bar fixed at top, visible on all pages (except those marked standalone later)
- [ ] Notifications icon shows badge with count (mocked)
- [ ] Profile avatar dropdown opens on click (settings/logout)
- [ ] Dark/light toggle persists across reloads
- [ ] Active page highlighted in sidebar
- [ ] All design system colors (Material Design 3 palette) available in Tailwind config

---

## PHASE 1: SIDEBAR & TOP BAR

**Output:** Global layout components used by all subsequent pages

**Components:**
1. **Sidebar** (`_sidebar.html` + `sidebar.js`)
   - Logo + version label
   - Navigation items: Mission Control, Trade Ops, Strategy Library, Portfolio Risk, Research, Hypotheses, Backtesting, Optimization, ML Center, AI Research, Accounts, Settings
   - Each item: icon + label (collapsed to icon only)
   - Active state highlighting
   - Collapse toggle button (chevron icon)

2. **Top Bar** (`_topbar.html` + `topbar.js`)
   - Left: App name ("Savanna Capital"), domain links (Research, Execution, Operations, Analytics)
   - Right: Deploy button, notifications icon (with badge), terminal icon, profile avatar, dark/light toggle

3. **Theme System** (`_theme.html` + `theme.js`)
   - CSS custom properties for colors (light/dark variants)
   - Theme toggle switches `class="dark"` on `<html>`
   - System preference detection on first load

**Checkpoints:**
- [ ] Sidebar renders all navigation items listed above
- [ ] Sidebar collapse reduces width to 48px, labels hidden
- [ ] Main content margin shifts from `ml-[240px]` to `ml-[48px]`
- [ ] Top bar fixed at top, visible on all pages (except those marked standalone later)
- [ ] Notifications icon shows badge with count (mocked)
- [ ] Profile avatar dropdown opens on click (settings/logout)
- [ ] Dark/light toggle persists across reloads
- [ ] Active page highlighted in sidebar
- [ ] Logo and branding present
- [ ] All navigation links resolve to correct routes

---

## PHASE 2: MISSION CONTROL

**Reference:** `mission_control_dashboard_2/code.html` (DASHBOARD_DOCUMENTATION pages 115-216)

**Files:**
- `dashboard/templates/v3/pages/mission_control.html`
- `dashboard/static/v3/pages/mission_control.js`

**Layout & Components:**
1. Top bar (from base) — no internal header
2. Summary Bar (4 KPI tiles): Total Equity, Daily PnL, Open Positions, Active Strategies
3. Equity Curve Section (8 cols):
   - Canvas line chart (equity + drawdown dual axis)
   - Range buttons: 1H, 4H, 1D, MAX
4. System Health (4 cols): MT5 Connection, DataFeed, RiskEngine, Backup status cards
5. Strategy View Toggle (Grid/List)
6. Strategy Grid/List (responsive)
   - Each card: Name, Symbol, TF, 7D Return, Sharpe, Max DD, Trades
7. Log Drawer (slide-up bottom panel):
   - Toggle button "Live Logs"
   - Scrollable log entries container
   - Auto-refresh when open

**API Endpoints (V3):**
- `GET /api/v3/account/stats`
- `GET /api/v3/account/snapshots?limit=200`
- `GET /api/v3/strategies/` (with stats)
- `GET /api/v2/mt5/connection` (or v3 equivalent)
- `GET /api/v2/engine/status`
- `GET /api/v2/engine-controls/logs?tail=200`

**JavaScript Functions:**
- `init()` → `loadAll()`
- `loadStats()`, `loadStrategies()`, `refreshEquity()`, `updateSystemHealth()`
- `initEquityChart()`, `renderEquityChart()`, `filterSnapshots(range)`
- `computeSharpe()`, `computeMaxDrawdown()`
- `renderStrategyGrid()`, `renderStrategyList()`
- `openLogDrawer()`, `closeLogDrawer()`

**Polling:** Default 5000ms (from config)

**Checkpoints:**
- [ ] Page extends `_base.html`
- [ ] 4 KPI tiles display with correct values
- [ ] Equity chart renders with two datasets (equity fill, drawdown line)
- [ ] Range buttons update chart data correctly
- [ ] System health cards show status (green/red) and latency
- [ ] Grid/List toggle switches view; localStorage preference saved
- [ ] Strategy cards display name, symbol, timeframe, metrics
- [ ] Log drawer opens/closes; auto-refreshes every 5s when open
- [ ] All API calls successful, errors handled gracefully
- [ ] Charts responsive on window resize

---

## PHASE 3: TRADE OPERATIONS

**Reference:** `page_trade_ops.html` (DASHBOARD_DOCUMENTATION pages 577-722)

**Files:**
- `dashboard/templates/v3/pages/trade_operations.html`
- `dashboard/static/v3/pages/trade_operations.js`

**Layout:**
1. Fixed Top Bar (h-12):
   - Search input, Filters button, Account selector, Regime button, Connection status, Notifications, Profile
2. Main Grid (12 cols):
   - **Panel 1-3**: Live Executions & Pending Orders (col-span-8, sticky header table)
   - **Panel 4**: Execution Quality (col-span-4, 4 metric boxes + progress bars)
   - **Panel 5**: Historical Trade Log (col-span-7)
   - **Panel 6**: Journal & Annotations (col-span-5)
3. Fixed Bottom Bar (h-6): Port label, sync timestamp, engine status, ticker clock

**Sub-components:**
- Execution quality modals (stub)
- Journal annotation cards with delete
- Tag chips selection

**API Endpoints:**
- `GET /api/mt5/positions`
- `GET /api/mt5/orders`
- `GET /api/trades/recent?limit=50`
- `GET /api/v2/accounts/summary`
- `GET /api/v2/engine/status`
- `GET /api/v2/mt5/connection`
- `GET /api/journal/annotations?trade_id=`
- `POST /api/journal/annotations`
- `DELETE /api/journal/annotations/{id}`

**JavaScript Functions:**
- `loadExecutions()`, `loadExecQuality()`, `loadHistoricalLog()`, `updatePort()`, `updateEngineStatus()`, `updateTicker()`, `reloadAll()`
- `computeExecQuality()`
- `populateJournalFromTrade()`, `loadAnnotations()`, `addObservation()`, `commitObservation()`
- `flash(msg)`

**Polling:** 8000ms (configurable)

**Checkpoints:**
- [ ] Executions table shows open positions + pending orders
- [ ] Close position button on each row (confirmation)
- [ ] Execution quality metrics display with progress bars (slippage, latency, fill rate, rejections)
- [ ] Historical trade log clickable; selection populates journal panel
- [ ] Alpha factor tags toggle visual state
- [ ] Journal notes can be saved; annotation list updates
- [ ] Bottom bar updates port label, engine status, ticker clock
- [ ] All columns correctly sized; sticky headers work

---

## PHASE 4: STRATEGY LIBRARY

**Reference:** `strategy_library/code.html` (V3 plan adaptation section)

**Files:**
- `dashboard/templates/v3/pages/strategy_library.html`
- `dashboard/static/v3/pages/strategy_library.js`

**Layout:**
1. Top Actions Bar: "+ New Strategy", Refresh, View toggles (Table/Grid/Evidence)
2. Stats Bar (4 cols): Total, Active, Inactive, Deploying
3. Main Grid Layout (3-column):
   - Left (240px): Filters (search, asset class, status), Strategy list (if table view shows table)
   - Center (1fr): Strategy cards (grid view) or table (table view)
   - Right (340px): Detail panel (slide-up bottom when strategy selected)
4. Detail Panel contents:
   - Header: Name, label, active badge, regime filter dropdown, ML override toggle, Export, Copy
   - Charts row: Equity curve (Chart.js line with fill), Monte Carlo (multiple light lines), Monthly returns bar chart
   - Performance Metrics (7-col KPI grid): Trades, Win Rate, Net PnL (R), PF, Sharpe, Max DD, Avg R
   - Trade History Table (full width, 8 cols)
   - Backtest Results Summary (expandable accordion)
   - Version History list
5. Modals:
   - Edit Params Modal: JSON textarea with validation
   - Copy/New Strategy Modal
   - Backtest Results Modal (expandable rows)

**API Endpoints:**
- `GET /api/v3/strategies/`
- `GET /api/v3/strategies/{name}`
- `GET /api/v3/strategies/{name}/equity`
- `GET /api/v3/strategies/{name}/monte-carlo`
- `GET /api/v3/strategies/{name}/performance`
- `GET /api/v3/strategies/{name}/trades`
- `GET /api/v3/strategies/{name}/backtests`
- `GET /api/v3/strategies/{name}/versions`
- `GET /api/v3/strategies/evidence`
- `POST /api/v3/strategies/{name}/toggle`
- `PUT /api/v3/strategies/{name}/params`
- `POST /api/v3/strategies/{name}/copy`
- `PUT /api/v3/strategies/{name}/ml-override`
- `GET /api/v3/strategies/{name}/export`

**JavaScript Functions:**
- `init()`: `loadAll()`
- `loadAll()`: fetch strategies overview
- `loadStrategyDetail(name)`: fetch all detail endpoints
- `openDetailPanel(name)`, `closeDetailPanel()`
- `renderStrategyGrid()`, `renderStrategyList()`, `renderEvidence()`
- `renderEquityChart()`, `renderMonteCarloChart()`, `renderMonthlyChart()`
- `saveParams()` (Edit Params modal)
- `copyStrategy()`
- `toggleStrategyActive()`
- `exportStrategy()`
- `applyRegimeFilter()`, `applyMLOverride()`

**Polling:** 30000ms (30s) — if detail open, refresh detail only

**Checkpoints:**
- [ ] Table view shows full columns (Name, Label, Symbol, TF, Status, Version, Trades, WR, PF, Sharpe, Max DD, ML toggle, Actions)
- [ ] Grid view shows cards with metrics and mini sparkline (optional)
- [ ] Evidence view shows combined event log timeline
- [ ] Detail panel slides up when strategy clicked; displays all charts and metrics
- [ ] Equity curve chart fills under line, correct data
- [ ] Monte Carlo chart shows 50 light lines (opacity 0.3)
- [ ] Monthly returns heatmap renders 12 cols × years
- [ ] Trade history table paginated or limited to 30 rows
- [ ] Edit Params modal: JSON textarea validates on save; version history updates
- [ ] Copy Strategy modal: creates new strategy with unique name; success feedback
- [ ] ML override toggle sends PUT and updates UI state
- [ ] Export button downloads JSON config file
- [ ] View toggle preference saved to localStorage

**Sub-pages/Modals included:**
- Edit Params Modal
- Copy Strategy Modal
- Backtest Results Modal (if separate)

---

## PHASE 5: PORTFOLIO RISK MONITOR

**Reference:** `portfolio_risk_monitor/code.html` (DASHBOARD_DOCUMENTATION pages 355-464)

**Files:**
- `dashboard/templates/v3/pages/portfolio_risk.html`
- `dashboard/static/v3/pages/portfolio_risk.js`

**Layout:**
1. Top Row (5 KPI panels, grid-cols-5):
   - Daily DD %, Weekly DD %, Total Exposure USD, VaR 95% 1D USD, Margin Usage %
2. Main Content Grid:
   - Left Panel (9 cols): Open Positions Table
   - Right Sidebar (3 cols): Asset Allocation Donut (canvas), Strategy Exposure Bars (vertical stacked)
3. Bottom Row:
   - Left (8 cols): Correlation Matrix (6x6 CSS grid)
   - Right (4 cols): Risk Alerts list

**API Endpoint:**
- `GET /api/v3/risk/overview` (returns all needed data)

**JavaScript Functions:**
- `tick()` every 6000ms → `refreshAll()`
- `renderAlloc(d)`: manual Canvas donut (lineWidth 16, colors by asset class)
- `renderCorrelation(d)`: builds 6x6 grid, absolute correlations > 0.5 bold+colored, diagonal highlighted
- `renderAlerts(d)`: generates alerts for concentration >35%, daily DD < -2%, margin >80%, free margin <20%

**Helper:** `_asset(sym)` for asset class mapping; `_grp(name)` for strategy grouping

**Polling:** 6000ms

**Checkpoints:**
- [ ] All 5 KPI tiles display formatted values (percentages, USD)
- [ ] Open Positions table shows all columns with correct formatting (account, symbol, side, entry, price, size, SL/TP, PnL, risk %)
- [ ] Asset Allocation donut renders with correct slices and colors (crypto purple, fx cyan, equities amber, metals gold, fixed income emerald)
- [ ] Center label shows gross exposure
- [ ] Strategy exposure bars display tooltips on hover
- [ ] Correlation matrix 6x6 grid renders; diagonal cells highlighted; strong correlations emphasized
- [ ] Risk alerts list dynamically adds/removes items based on thresholds
- [ ] All data updates every 6 seconds without flicker
- [ ] Canvas charts resize correctly on window resize

---

## PHASE 6: RISK & COMPLIANCE

**Reference:** `risk_management_compliance/code.html` (V3 plan adaptation)

**Files:**
- `dashboard/templates/v3/pages/risk_compliance.html`
- `dashboard/static/v3/pages/risk_compliance.js`

**Layout:**
1. Top Telemetry Bar (h-16): 3-4 KPI tiles (VaR, Beta, Margin Usage, Net PnL) using `_kpi_tile.html`
2. Main Grid (3 columns):
   - Left Sidebar (240px): Risk navigation links (Risk Telemetry, Compliance, Stress Tests, Margin, Reports)
   - Center (1fr): Strategy risk metrics table using `_data_table.html`
   - Right Sidebar (340px): VaR breakdown donut chart (Chart.js), Active alerts list, Stress test results
3. Bottom Panel (h-64): Compliance event log (scrollable)

**API Endpoints:**
- `GET /api/v3/risk/overview`
- `GET /api/v3/risk/strategies`
- `GET /api/v3/risk/compliance/events`
- `GET /api/v3/risk/alerts`
- `GET /api/v3/risk/stress-tests`

**JavaScript Functions:**
- `init()`: load overview metrics, table data, compliance events
- `renderTable()`, `renderComplianceLog()`, `renderVaRDonut()`
- Start polling for compliance events (WebSocket or polling 10s)

**Charts:** Donut chart via `shared/charts.js` `createDonutChart()`

**Polling:** 10s for compliance feed

**Checkpoints:**
- [ ] Top telemetry bar displays KPI tiles with correct values
- [ ] Left sidebar navigation highlights active section
- [ ] Strategy risk table loads with columns: Strategy, Symbol, VaR, Margin, Stress Score, Max DD, Actions
- [ ] Table sorting enabled on numeric columns
- [ ] VaR breakdown donut renders with segments (colors from design system)
- [ ] Active alerts list items show severity icons and text
- [ ] Bottom compliance log scrollable; timestamps in `font-label-sm`
- [ ] New compliance events appear automatically

---

## PHASE 7: RESEARCH LAB

**Reference:** `research_lab/research_lab.md` (DASHBOARD_DOCUMENTATION pages 1247-1386)

**Files:**
- `dashboard/templates/v3/pages/research_lab.html`
- `dashboard/static/v3/pages/research_lab.js`

**Layout (3-panel workspace):**
1. Left Panel (w-64):
   - Dataset Explorer: categories (Metals, Crypto, Equities) with file list
   - Footer: "Import New Data" button, "LOADED" badge
2. Center Panel (flex-1, notebook):
   - Tabs bar: file tabs (scrollable), "Run All" button, Kernel status badge
   - Notebook body:
     - Code blocks with line numbers and run button
     - Output blocks (stdout, plots, charts)
     - Markdown blocks
   - Default blocks: Environment Setup, Hypothesis Generation, Visualization (Alpha Signal Intensity Map)
3. Right Panel (w-80):
   - Key Observations list (cards with type badge, timestamp, title, tags, confidence)
   - Inline entry form: Type selector, notes textarea, Add button
   - Workspace Stats: RAM, GPU, Jobs, Runtime
   - "Commit to Hypothesis" button

**Sub-pages/Modals:** None (but sends event to Hypotheses page)

**API Endpoints:**
- `POST /api/quant/hypotheses` (when commit button clicked)
- `POST /api/v2/ai/chat` (terminal queries)

**JavaScript Functions:**
- `renderDatasets()`, `activateDataset(name)`
- `addFileTab(filename)`
- `runBlock(blockId)` (simulated with 700ms delay, mock output)
- `outputBlock(blockId, text)`
- `renderViz()` (10×14 colored grid)
- `renderObservations()`
- `addObservation()`, `commitObservation()`
- `updateRuntimeStats()` (every 5s)

**Polling:** N/A (mostly static except runtime stats)

**Checkpoints:**
- [ ] Dataset explorer lists all categories and datasets with sizes
- [ ] Clicking dataset activates it, adds file tab, populates notebook code blocks with dataset name
- [ ] Code block run buttons generate mock stdout output after delay
- [ ] Visualization block renders colored grid (alpha signal intensity map)
- [ ] Observations list displays pre-loaded demo cards
- [ ] Add observation button creates new card with selected type and notes
- [ ] Commit to Hypothesis button POSTs to `/api/quant/hypotheses`, clears notes, dispatches event, navigates after 600ms
- [ ] Runtime stats update every 5s (mock increments)
- [ ] Terminal input sends to `/api/v2/ai/chat` and displays response

---

## PHASE 8: HYPOTHESES CENTER

**Reference:** `hypothesis_center/code.html` (DASHBOARD_DOCUMENTATION pages 1147-1245)

**Files:**
- `dashboard/templates/v3/pages/hypotheses.html`
- `dashboard/static/v3/pages/hypotheses.js`

**Layout:**
1. Top Bar: Refresh button, New Hypothesis button
2. Context Bar: View toggles (Kanban/Table), Status filter dropdown, Asset Class filter, Search input
3. Collapsible Summary Table (Active Hypothesis Registry)
4. Kanban Board (5 columns): DRAFT, RESEARCHING, BACKTESTING, VALIDATED, DEPLOYED (REJECTED hidden)
   - Each column contains draggable hypothesis cards
5. Hypothesis Card:
   - Header: ID, title, asset badge
   - Body: description (2 lines), timeframe symbol
   - Progress bar
   - Footer: "Advance to Next Stage", "Deploy Strategy" (only when VALIDATED), "Discard"
6. Floating Status Overlay (bottom-right): Engine Live dot, Latency, CPU %

**Sub-pages/Modals:**
- New Hypothesis Modal (fields: Title, Description, Symbol, Timeframe, Initial Status)

**API Endpoints:**
- `GET /api/quant/hypotheses`
- `POST /api/quant/hypotheses`
- `PATCH /api/quant/hypotheses/{id}`
- `DELETE /api/quant/hypotheses/{id}`

**JavaScript Functions:**
- `loadHypotheses()`, `renderKanban()`, `renderTable()`
- `applyFilters()`, `_assetClass(sym)` mapping
- `advanceHypothesis(id)`, `deployHypothesis(id)`, `discardHypothesis(id)`
- Drag-and-drop handling (if required)
- Event listener for `research.hypothesis.created` to refresh

**Polling:** 15s (auto-refresh)

**Checkpoints:**
- [ ] Kanban board displays 5 columns with correct status headers
- [ ] Hypothesis cards draggable between columns (if implemented)
- [ ] Card progress bar reflects stages passed (DRAFT→RESEARCHING→BACKTESTING→VALIDATED→DEPLOYED)
- [ ] "Advance to Next Stage" button updates status via PATCH
- [ ] "Deploy Strategy" button creates StrategyConfig from hypothesis params (stub or actual) and moves to DEPLOYED
- [ ] "Discard" button removes card after confirmation
- [ ] New Hypothesis modal validates required fields; creates new card with DRAFT status
- [ ] Filters (status, asset class, search) filter cards in real-time
- [ ] View toggle switches between Kanban and Table layouts; preference saved
- [ ] Summary table collapse/expand works

---

## PHASE 9: BACKTESTING CENTER

**Reference:** `backtesting_center/code.html` (V3 plan adaptation)

**Files:**
- `dashboard/templates/v3/pages/backtesting_center.html`
- `dashboard/static/v3/pages/backtesting_center.js`

**Layout:**
1. Left Sidebar (w-72):
   - Strategy select, Symbol input, Timeframe select, Execution mode (OHLC/Every Tick)
   - Date range pickers (start_date, end_date)
   - Parameter overrides table (dynamic from strategy.default_params)
   - Reset Defaults button
   - RUN BACKTEST button (with spinner)
   - Status message area
2. Main Content (flex-1):
   - Metrics Row (5 KPI tiles): Net Profit, Sharpe, Max DD, Profit Factor, Win Rate
   - Equity & Drawdown Chart (canvas, dual axis, scale toggle linear/log)
   - Bottom Row (2 cols):
     - Left: Trade Distribution Histogram (bar chart)
     - Right: Monthly Returns Heatmap (12 cols × years)
   - Run History Table (below, expandable rows)

**Modals:**
- Backtest Results Modal (optional, or inline expansion)

**API Endpoints:**
- `GET /api/v3/backtest/strategies`
- `GET /api/v3/backtest/symbols`
- `GET /api/v3/backtest/timeframes`
- `POST /api/v3/backtest/run`
- `GET /api/v3/backtest/runs`
- `GET /api/v3/backtest/run/{run_id}`
- `GET /api/v3/backtest/run/{run_id}/equity`
- `GET /api/v3/backtest/run/{run_id}/distribution?bins=30`
- `GET /api/v3/backtest/run/{run_id}/monthly`
- `DELETE /api/v3/backtest/run/{run_id}`

**JavaScript Functions:**
- `initBT()`: parallel fetch strategies, symbols, timeframes
- `onStrategyChange()`: build parameter overrides table
- `buildParamTable(cls)`: generate rows with inputs respecting param_bounds
- `runBacktest()`: validate, collect overrides, POST, start `pollRun(run_id)`
- `pollRun(run_id)`: every 2s GET run; update progress; on complete: render charts and metrics
- `renderEquityChart(data, scale)`, `renderDistChart(data)`, `renderHeatmap(data)`
- `renderHistory(runs)`, `loadRun(run_id)`

**Polling:** During run: 2000ms; after completion: none (manual refresh)

**Checkpoints:**
- [ ] Strategy select populated with names and labels
- [ ] Symbol dropdown grouped by asset class (optgroups)
- [ ] Timeframe select shows M1, M5, M15, H1, H4, D1
- [ ] Parameter overrides table shows each param with min/max/step validation
- [ ] Run button disabled until required fields filled
- [ ] Progress spinner shows during run; status message updates
- [ ] Metrics tiles display after run completes (Net Profit, Sharpe, Max DD, PF, Win Rate)
- [ ] Equity chart dual axis (equity line + drawdown red line) with fill
- [ ] Distribution histogram renders correctly with bin counts
- [ ] Monthly heatmap grid colors cells green/red with opacity proportional to magnitude
- [ ] Run history table lists recent runs; clicking row loads that run's results
- [ ] Parameter overrides correctly applied; different values produce different results
- [ ] Linear/Log scale toggle works on equity chart

---

## PHASE 10: OPTIMIZATION HUB

**Reference:** `optimization_hub/code.html` (DASHBOARD_DOCUMENTATION pages 1014-1145)

**Files:**
- `dashboard/templates/v3/pages/optimization.html`
- `dashboard/static/v3/pages/optimization.js`

**Layout:**
1. Left Sidebar (w-72):
   - Strategy Select dropdown
   - Parameter Bounds Builder (for each param: Min, Max, Step inputs)
   - Search Method radios: Grid, Random, Bayesian (GP)
   - Fitness Function radios: Sharpe, Calmar, Net Profit
   - Symbol/Timeframe info (hidden until strategy selected)
   - START OPTIMIZER button (disabled until strategy selected)
   - Progress bar (hidden), Status message
2. Main Content (flex-1):
   - Parameter Surface Heatmap (canvas, height 280px)
   - Top Parameter Sets Table (rank, params badges, fitness metrics, Sharpe, PF, Max DD, Trades, LOAD action)
   - Optimization History List (status dot, strategy, date, iterations, best Sharpe)

**Sub-pages/Modals:** None

**API Endpoints:**
- `GET /api/v3/backtest/strategies` (for param_bounds)
- `GET /api/v3/backtest/symbols`
- `GET /api/v3/backtest/timeframes`
- `POST /api/v3/quant/optimise`
- `GET /api/v3/quant/optimise`
- `GET /api/v3/quant/optimise/{run_id}`
- `PUT /api/v3/quant/optimise/{run_id}/deploy`

**JavaScript Functions:**
- `initOpt()`: load strategies, bind change handler
- `onStrategyChange()`: fetch strategy class, show symbol/timeframe, `buildParamTable()`
- `buildParamTable(default_params)`: create label + min/max/step inputs with validation
- `runOptimisation()`: collect form, POST, receive `run_id`, start `pollRun(run_id)`
- `pollRun(run_id)`: every 3s GET run; update progress; on complete: `renderHeatmap()`, `renderTopResults()`
- `renderHeatmap(heatmap_data)`: 2D gradient grid (slate→cyan→gold), hover scales cell, tooltip
- `renderTopResults(results)`: table rows with param badges; LOAD button deploys best_params
- `exportCSV()`: downloads all results

**Polling:** During run: 3000ms; after: none

**Checkpoints:**
- [ ] Strategy select populated; selecting strategy shows symbol/timeframe info
- [ ] Parameter bounds builder generates correct number of inputs with default ranges (bound.min/max or default*0.5/2)
- [ ] Validation ensures min < max, step > 0
- [ ] Search method and fitness function radios selectable
- [ ] START button disabled until strategy selected
- [ ] Heatmap renders with color gradient; axes labeled with first two parameter names
- [ ] Hovering over heatmap cell shows tooltip with coordinates and score (scaled cell 1.25×)
- [ ] Top 10 results table displays ranks and param badges; LOAD button functional
- [ ] Progress bar updates during run; status message informative
- [ ] LOAD button deploys best_params to StrategyConfig (PUT)
- [ ] Export CSV downloads file with columns: rank, params (JSON), fitness, sharpe, pf, max_dd, trades
- [ ] Optimization history list clickable: loads that run's results

---

## PHASE 11: ML CENTER (4 PAGES)

**Note:** ML Center is a separate section with sub-pages. Navigate via existing ML Center nav item.

### Page 1: ML Dashboard

**Reference:** `institutional_ml_center_rebuild/code.html`

**Files:**
- `dashboard/templates/v3/pages/ml_dashboard.html`
- `dashboard/static/v3/pages/ml_dashboard.js`

**Layout:**
- Top Stats Bar (4 metric cards): Trained Models, Active, Avg Accuracy, Models Deployed
- Model Status Grid (responsive): Cards showing model name, status badge (pending/training/ready/active/failed), metrics (Symbol, TF, Type, Accuracy, Precision, Recall, F1, Created, Last trained, Samples)
- Quick Actions: Train New Model (opens ML Training page), Deploy, Monitor
- Charts: Model performance comparison (bar chart), prediction volume over time (line)

**API Endpoints:**
- `GET /api/v3/ml/models`
- `GET /api/v3/ml/predictions` (feed)
- `GET /api/v3/ml/models/{id}/metrics`
- `GET /api/v3/ml/models/{id}/deploy`

**JavaScript:** `init()` loads models, renders grid, updates stats, draws charts

**Checkpoints:**
- [ ] Models grid displays all models with correct status badges
- [ ] Metrics shown for each model (accuracy, precision, recall, F1)
- [ ] Action buttons on each card functional (Deploy opens confirmation, Monitor navigates to Monitoring page)
- [ ] "Train New Model" button navigates to ML Training page
- [ ] Bar chart compares model accuracies; updates when models change
- [ ] Prediction volume line chart shows count over time (last 30 days)
- [ ] Stats bar aggregates correct counts

### Page 2: ML Training

**Reference:** `ml_strategy_builder_alpha_generation/code.html`

**Files:**
- `dashboard/templates/v3/pages/ml_training.html`
- `dashboard/static/v3/pages/ml_training.js`

**Layout:**
- Training Interface Form (grid-cols-6):
  - Symbol select, Timeframe select, Model Type select (RandomForest, GradientBoosting, Logistic), Model Name input, CV Folds input, Train button
- Pipeline Visualization (horizontal flow): Dataset → Feature Eng → Model → Validation
- Feature Importance Section:
  - Model select dropdown, Analyze button
  - Horizontal bar chart (top 15 features, amber bars)
- Training Progress Indicator (epochs, loss) — appears when training
- Artifact Management: Save model, Export configuration

**API Endpoints:**
- `POST /api/v3/ml/train`
- `GET /api/v3/ml/models`
- `GET /api/v3/ml/models/{id}/features`
- `POST /api/v3/ml/models/{id}/deploy`

**JavaScript Functions:**
- `trainModel()`: POST, receives `model_id`, starts `pollTrainStatus(model_id)`
- `pollTrainStatus(id)`: every 5s GET models; if ready shows metrics, if failed shows error
- `loadFi()`: GET features, draws horizontal bar chart
- `buildPipelineViz()`: static illustration (CSS/SVG)

**Polling:** 5s during training

**Checkpoints:**
- [ ] All form fields present; required validation (symbol, timeframe, model name)
- [ ] Train button disabled until fields valid
- [ ] On submit, POST sent; progress indicator appears; status updates
- [ ] Training completion updates model card (status becomes "ready")
- [ ] Feature importance chart appears after training; bars horizontal with labels
- [ ] Pipeline visualization renders with connected boxes and labels
- [ ] Deploy button after training creates StrategyConfig with model_id

### Page 3: Trade Classification

**Reference:** `trade_intelligence_ai_risk_filter/code.html`

**Files:**
- `dashboard/templates/v3/pages/ml_classification.html`
- `dashboard/static/v3/pages/ml_classification.js`

**Layout:**
- Live Feed Table (full width) of candidate signals awaiting classification:
  - Columns: Timestamp, Strategy, Symbol, Signal (BUY/SELL), ML Confidence, Classification (GOOD/BAD/UNCERTAIN), Action (executed/skipped)
  - Real-time: new rows prepend; color coding (GOOD green, BAD red, UNCERTAIN yellow)
- Filter Controls: Strategy dropdown, Classification outcome select, Confidence threshold slider
- Historical Classification Log (table) with outcome tracking (did trade win?)
- Summary Stats: accuracy % by model, profit factor for GOOD vs BAD, avg confidence

**API Endpoints:**
- `GET /api/v3/ml/predictions` (live feed)
- `GET /api/v3/ml/classification/history`
- `GET /api/v3/ml/strategy/{name}/ml-stats`
- `GET /api/v3/ml/models/{id}/metrics`

**JavaScript Functions:**
- `loadFeed()`: GET predictions; renders table rows with timestamp sorting
- `loadHistory()`: fetches historical classifications with outcomes
- `renderStats()`: aggregates accuracy, profit factor, confidence
- Filters apply to both feed and history

**Polling:** 10s (feed); history static unless refresh

**Checkpoints:**
- [ ] Live feed table updates automatically; newest rows at top
- [ ] Classification badges color-coded correctly
- [ ] Filters (strategy, classification, confidence) filter both feed and history tables
- [ ] Historical log shows final outcome (win/loss) for each classified signal
- [ ] Summary stats calculate correctly from data
- [ ] Confidence threshold slider excludes low-confidence rows from feed

### Page 4: ML Monitoring

**Reference:** Based on Institutional ML template table (new page)

**Files:**
- `dashboard/templates/v3/pages/ml_monitoring.html`
- `dashboard/static/v3/pages/ml_monitoring.js`

**Layout:**
- Filters: Date range, Strategy select, Classification select (GOOD/BAD/UNCERTAIN), Outcome select (Win/Loss/Open)
- Table (full width):
  - Columns: Date, Strategy, Symbol, Side, Lot, Entry, Exit, PnL, ML Confidence, Classification, Outcome
  - Sorting on all columns
- Export to CSV button
- Aggregate Stats Bar (3-4 tiles): Overall Accuracy, PF for GOOD, PF for BAD, Avg Confidence
- Charts:
  - Scatter: Confidence vs PnL (bubble size = lot)
  - Histogram: Classification distribution

**API Endpoints:**
- `GET /api/v3/ml/strategy/{name}/ml-stats` (or combined endpoint)
- `GET /api/v3/ml/models/{id}/metrics`
- `GET /api/v3/trades?source=ml&...` (filtered)

**JavaScript Functions:**
- `loadMonitoring()`: fetch ML trades with filters; render table
- `renderScatter()`: Chart.js scatter
- `renderHistogram()`: Chart.js bar
- `exportCSV()`: downloads filtered data

**Polling:** 15000ms (15s)

**Checkpoints:**
- [ ] All filters functional; changing them triggers data reload
- [ ] Table displays ML-enabled trades with correct columns
- [ ] Sorting on each column toggles asc/desc
- [ ] Scatter chart plots confidence vs PnL; positive PnL cluster in GOOD classification
- [ ] Histogram shows count of GOOD/BAD/UNCERTAIN
- [ ] Stats bar calculates: accuracy = GOOD wins / (GOOD total + BAD total?), PF ratios, avg confidence
- [ ] CSV export includes current filtered dataset

---

## PHASE 12: AI RESEARCH CENTER

**Reference:** `page_ai_research.html` (DASHBOARD_DOCUMENTATION pages 898-1012)

**Status:** Keep v2 implementation unchanged; verify compatibility with base template.

**Files:**
- `dashboard/templates/v3/pages/ai_research.html` (copy from v2, update styles)
- `dashboard/static/v3/pages/ai_research.js` (keep existing logic, ensure no internal top bar)

**Layout (3-column workspace):**
1. Left Column (col-span-3):
   - AI Configuration Panel: Confidence Threshold slider, Cooldown buttons (5m/15m/1h), Knowledge Bases checkboxes
   - Signal Heatmap grid (4×N) with color-coded cells, demo badge
2. Center Column (col-span-5):
   - Active AI Suggestions Table (searchable)
   - Automated Reasoning Panel (Market Context, Alpha Factor Alignment, Risk Assessment)
3. Right Column (col-span-4):
   - Quant Terminal (input + output log)
   - Confidence Distribution Chart (horizontal bar bins)
   - Stats Bar: Suggestion Accuracy, Avg Alpha
4. Footer Bar: status dot, latency, throughput, UTC clock

**API Endpoints (v2):**
- `GET /api/v2/ai/suggestions?limit=50`
- `GET /api/v2/ai/heatmap`
- `GET /api/v2/ai/reasoning/{symbol}`
- `POST /api/v2/ai/chat`
- `POST /api/v2/ai/toggle`
- `GET /api/v2/ai/config`
- `PUT /api/v2/ai/config`
- `POST /api/v2/ai/generate`

**JavaScript Functions:** Existing `init()`, `updateToggleUI()`, `loadHeatmap()`, `renderHeatmap()`, `loadSuggestions()`, `selectSuggestion()`, `updateConfidenceChart()`, `sendChat()`

**Polling:** 10s (heatmap + suggestions)

**Checkpoints:**
- [ ] Page extends `_base.html` (no internal top bar)
- [ ] Confidence slider updates display and PUTs to `/api/v2/ai/config`
- [ ] Cooldown buttons set cooldown_minutes
- [ ] Heatmap grid displays 12 assets with score and direction; demo badge shown if is_demo
- [ ] Suggestions table loads; search filters rows
- [ ] Clicking suggestion loads reasoning into right panel
- [ ] Confidence distribution chart bins suggestions correctly
- [ ] Quant terminal accepts input; POST to chat; response displays with optional SQL
- [ ] Footer bar stats update (latency, throughput, clock)
- [ ] All v2 API calls work despite base template changes

---

## PHASE 13: ACCOUNTS (Multi-Account Management)

**Reference:** `page_multi_account.html` (DASHBOARD_DOCUMENTATION pages 467-575)

**Files:**
- `dashboard/templates/v3/pages/multi_account.html`
- `dashboard/static/v3/pages/multi_account.js`

**Layout:**
1. Top KPI Cards (4 cols): Total Equity, Free Margin, Drawdown (worst), Profit (today)
2. MT5 Instance Matrix Table (full width, sticky):
   - Bulk actions bar (hidden until rows selected)
   - Columns: Checkbox, Account (with color swatch), Broker, Server, Status badge, Equity, Balance, Margin %, Positions, Weight, Actions (more_vert)
3. Recent Orders Table (fixed max-height 180px): Time, Symbol, Type, Size, Price, Status, PnL
4. Account Detail Drawer (slide-out right, off-canvas):
   - Header: swatch + account name + meta + status
   - KPIs: Balance, Equity, Free Margin (3-col)
   - Action buttons row: Connect, Disconnect, Pause, Close All Positions
   - Form: Weight input, Display Name, Notes
   - Footer actions
5. Add Account Modal (centered overlay):
   - Form: Account Name, Broker select, Account Type (Demo/Live), Server, MT5 Login, Weight, Password, Investor Password, Notes, Color swatch picker (10 colors)
6. Killswitch Modal (emergency overlay): warning text, CONFIRM input, Execute button

**API Endpoints:**
- `GET /api/v2/accounts/`
- `GET /api/v2/accounts/summary`
- `GET /api/trades/recent?limit=10`
- `POST /api/v2/accounts/`
- `PATCH /api/v2/accounts/{id}`
- `DELETE /api/v2/accounts/{id}`
- `POST /api/v2/accounts/{id}/action`
- `POST /api/v2/accounts/bulk/disconnect-all`
- `POST /api/v2/accounts/bulk/close-all`

**JavaScript Functions:**
- `loadAll()`: parallel GET accounts + recent trades
- `openDrawer(account_id)`, `closeDrawer()`
- Drawer action POSTs to `/action`
- `pickColour(hex)`, `openAddModal()`, `closeAddModal()`, `submitAdd()`
- Bulk selection handling; bulk action buttons
- Killswitch logic

**Polling:** 8000ms

**Checkpoints:**
- [ ] KPI cards sum across all accounts correctly
- [ ] Matrix table shows all accounts with checkboxes, color swatches, status badges
- [ ] Weight column numeric; >=1 highlighted in primary container color
- [ ] Actions menu (more_vert) opens drawer with correct account data
- [ ] Drawer fields editable; PATCH updates account; success feedback
- [ ] Drawer action buttons (Connect, Disconnect, Pause, Close All) functional
- [ ] Add Account modal validates required fields; color swatch picker highlights selection
- [ ] POST `/api/v2/accounts/` creates new account; table refreshes
- [ ] Killswitch modal requires typing "CONFIRM" exactly before button enables
- [ ] Bulk selection enables bulk action bar; bulk disconnect/close all work
- [ ] Recent orders table updates every 8s

---

## PHASE 14: SETTINGS

**Reference:** `page_settings.html` (DASHBOARD_DOCUMENTATION pages 1704-1783)

**Status:** Standalone page (no base template, no top bar)

**Files:**
- `dashboard/templates/v3/pages/settings.html` (update form styles to design system)
- `dashboard/static/v3/pages/settings.js`

**Layout:**
- Settings Form organized in fieldsets:
  1. Dashboard: poll_interval_ms, recent_trades_count, heartbeat_stale_seconds
  2. Risk Management: risk_per_trade, max_daily_drawdown, max_total_drawdown, max_open_trades, max_lot_size
  3. SL/TP Model: atr_period, sl_atr_mult_trending, sl_atr_mult_ranging, tp1_rr_trending, tp2_rr_trending
  4. AI Advisor: enabled (Yes/No), min_confidence_to_show, cooldown_minutes, model
- Save All Settings button
- Status message area

**API Endpoints:**
- `GET /api/settings`
- `POST /api/settings`
- `PUT /api/v2/ai/config` (if AI settings changed, to update runtime)

**JavaScript Functions:**
- `loadSettings()`: GET, populate inputs by matching id suffix to config key path
- `saveSettings()`: collect values, coerce numbers, AI enabled bool conversion, POST full object
- Show success/error message
- Optionally notify other pages via localStorage event or WebSocket

**Polling:** None (manual save)

**Checkpoints:**
- [ ] Page renders outside base template (standalone)
- [ ] All input fields present with correct default values from backend
- [ ] Number inputs have proper step, min, max attributes
- [ ] Save button sends full settings payload; backend responds 200
- [ ] Success message displays (green); error displays (red)
- [ ] After save, AI config update call sent if AI section changed
- [ ] Form layout matches design system: colors, spacing, typography
- [ ] Required fields marked (if any)

---

## PHASE 15: NOTIFICATIONS

**Reference:** To be defined (likely new page or modal). Since not in DASHBOARD_DOCUMENTATION, infer from top bar notification icon.

**Assumption:** Notifications page is a dedicated page showing list of system alerts, trade executions, engine events.

**Files:**
- `dashboard/templates/v3/pages/notifications.html`
- `dashboard/static/v3/pages/notifications.js`

**Layout:**
- Header: "Notifications" with mark all read button
- Filter tabs: All, System, Trades, Alerts, Errors
- List groups (scrollable):
  - Each item: icon ( bell/warning/error ), timestamp, title, description, unread dot
  - Click to mark read and expand details
- Pagination or infinite scroll

**API Endpoints (expected):**
- `GET /api/v3/notifications?limit=50&filter=`
- `POST /api/v3/notifications/{id}/read`
- `POST /api/v3/notifications/read-all`

**JavaScript Functions:**
- `loadNotifications()`: fetch with filter
- `markRead(id)`, `markAllRead()`
- `renderList()`
- Polling for new notifications

**Polling:** 30s

**Checkpoints:**
- [ ] Notifications list displays with correct icons and timestamps
- [ ] Filter tabs filter list without page reload
- [ ] Mark read removes unread dot; detail expansion works
- [ ] Mark all read button clears all unread states
- [ ] New notifications appear automatically during polling
- [ ] Empty state shows when no notifications match filter

---

## PHASE 16: PROFILE

**Reference:** Not in DASHBOARD_DOCUMENTATION; likely user profile page with account info, preferences, logout.

**Files:**
- `dashboard/templates/v3/pages/profile.html`
- `dashboard/static/v3/pages/profile.js`

**Layout:**
- Standalone page (no base top bar? Or maybe base with profile section)
- Profile card: avatar, username, role, email
- Preferences form: timezone, date format, number format, theme override
- Security section: Change password (current, new, confirm)
- Sessions list (active logins) with revoke buttons
- API tokens management (list, create new, revoke)
- Save button

**API Endpoints (expected):**
- `GET /api/v3/profile`
- `POST /api/v3/profile/update`
- `POST /api/v3/profile/change-password`
- `GET /api/v3/profile/sessions`
- `POST /api/v3/profile/sessions/{id}/revoke`
- `POST /api/v3/profile/tokens` (create)
- `DELETE /api/v3/profile/tokens/{id}`

**JavaScript Functions:**
- `loadProfile()`: GET, populate fields
- `saveProfile()`: POST updates
- `changePassword()`: POST with current/new/confirm
- `loadSessions()`, `revokeSession(id)`
- `createToken()`, `revokeToken(id)`

**Polling:** None

**Checkpoints:**
- [ ] Profile data loads: avatar, username, email, preferences
- [ ] Preferences form saves via POST; success feedback
- [ ] Change password validates current password; new password meets complexity; confirmation matches
- [ ] Sessions list shows active devices with IP, last active, revoke button
- [ ] Revoke session removes entry after confirmation
- [ ] API tokens list shows tokens with scopes; create token generates new token displayed once; revoke removes
- [ ] All forms use design system styling

---

## BUILD SEQUENCE SUMMARY

| Phase | Page/Component | Files | Key Dependencies | Checkpoint Count |
|-------|----------------|-------|------------------|------------------|
| 0 | Foundation | 19 files | None | 9 |
| 1 | Sidebar & Top Bar | 3 components | Foundation | 10 |
| 2 | Mission Control | 2 files | Phase 1 | 10 |
| 3 | Trade Ops | 2 files | Phase 1 | 11 |
| 4 | Strategy Library | 2 files | Phase 1-2 | 20 |
| 5 | Portfolio Risk | 2 files | Phase 1 | 9 |
| 6 | Risk & Compliance | 2 files | Phase 1 | 9 |
| 7 | Research Lab | 2 files | Phase 1 | 11 |
| 8 | Hypotheses | 2 files | Phase 1, 7 | 13 |
| 9 | Backtesting Center | 2 files | Phase 1, 4 | 14 |
| 10 | Optimization Hub | 2 files | Phase 1, 9 | 12 |
| 11 | ML Center | 8 files (4 pages) | Phase 1 | 4 pages × 12 = 48 |
| 12 | AI Research | 2 files | Phase 1 | 11 |
| 13 | Accounts | 2 files | Phase 1 | 14 |
| 14 | Settings | 2 files | Phase 1 | 8 |
| 15 | Notifications | 2 files | Phase 1 | 7 |
| 16 | Profile | 2 files | Phase 1 | 10 |

**Total Estimated Checkpoints:** ~220

---

## COMPLETION CRITERIA FOR ENTIRE BUILD

- [ ] All 16 phases completed (checklists green)
- [ ] No console errors in browser (all JS loads, no 404s on API)
- [ ] All charts render with mock or real data
- [ ] API mock layer functional if v3 backend not ready (`?mock=1`)
- [ ] Responsive layout tested on mobile (sidebar drawer), tablet, desktop
- [ ] Accessibility: keyboard navigation works, ARIA labels present
- [ ] All modals/drawers open/close correctly; backdrop dismissal optional
- [ ] Polling intervals update data without race conditions
- [ ] Error handling displays user-friendly messages (toast or inline)
- [ ] Design system colors/typography consistent across all pages
- [ ] Sidebar collapse state persists across page reloads
- [ ] Theme toggle persists across page reloads

---

## NOTES FOR IMPLEMENTATION

1. **API Versioning:** Use `/api/v3/` endpoints as defined in V3_FRONTEND_REDESIGN_PLAN.md Section 4.2. If not ready, enable mock mode via `?mock=1` query param.
2. **Chart.js:** Use helper functions from `static/v3/shared/charts.js` for consistent styling. Always destroy chart before re-creating.
3. **Modals:** Use `_modal.html` partial for consistent header/body/footer structure.
4. **Tables:** Use `_data_table.html` with sorting/pagination where appropriate.
5. **KPI Tiles:** Use `_kpi_tile.html` for uniform cards.
6. **Polling:** Respect `config.dashboard.poll_interval_ms` if available; default per page as documented.
7. **Error Handling:** All `apiFetch` calls should catch errors, display toast, and optionally retry.
8. **Loading States:** Show spinner or skeleton while data loads; disable buttons during actions.
9. **Sub-pages:** Modals and slide-out panels are considered part of the parent page's checklist; test open/close/submit.
10. **ML Center integration:** Strategies must have `ml_enabled` and `ml_model_id` fields; engine will POST to `/api/v3/ml/classify` before execution.

---

**End of Plan**
