# Savanna Capital Dashboard — Comprehensive Technical Documentation

## Overview
This document provides exhaustive documentation of the Savanna Capital quantum terminal dashboard, covering every page, UI element, API endpoint, calculation, parameter, and interaction. The system is built on Python 3.11+, FastAPI, SQLAlchemy ORM, PostgreSQL, with a frontend using Jinja2 templates, vanilla JavaScript, Chart.js, and Tailwind CSS via CDN.

---

## Table of Contents
1. [Login Page](#login-page)
2. [Mission Control](#mission-control)
3. [Executive Analytics](#executive-analytics)
4. [Portfolio Risk Monitor](#portfolio-risk-monitor)
5. [Multi-Account Management](#multi-account-management)
6. [Trade Operations & Journaling](#trade-operations-journaling)
7. [Risk & Compliance](#risk-compliance)
8. [ML Center](#ml-center)
9. [AI Research](#ai-research)
10. [Optimization Hub](#optimization-hub)
11. [Hypotheses Center](#hypotheses-center)
12. [Research Lab](#research-lab)
13. [Strategy Library](#strategy-library)
14. [Backtesting Center](#backtesting-center)
15. [Settings](#settings)
16. [API Reference — V1 Endpoints](#api-reference---v1-endpoints)
17. [API Reference — V2 Endpoints](#api-reference---v2-endpoints)

---

## Login Page

**Route:** `GET /login`  
**Template:** `dashboard/templates/login.html`

### Purpose
Authentication gateway for institutional trading terminal with hardware token requirement.

### UI Layout & Elements

**Top Section (Fixed Background)**
- Scanner line: Vertical sinusoidal animation moving from 0% to 100% top position
- Grid background pattern: 40px grid with rgba(48, 54, 61, 0.2) lines
- Ambient glow: Radial gradient circle at center with primary color (rgba(0, 229, 255, 0.05))

**Main Panel (glass-panel, max-w-420px)**
- Header:
  - Icon: Material Symbols "terminal" (filled, primary-fixed-dim color)
  - Title: "SAVANNA CAPITAL" (font-headline-md, tighter tracking, primary color)
  - Subtitle: "QUANTUM TERMINAL V4.2.0" (label-sm, uppercase, tracking-widest, on-surface-variant)
  - Bottom border: outline-variant/30

**Form Fields**
1. **TERMINAL_ID** (`#username-input`)
   - Type: text
   - Placeholder: "SC-QNT-XXXX" (typed character-by-character after 1s delay via JS)
   - Autocomplete: username
   - Right icon: fingerprint (on-surface-variant)
   - Label includes "REQUIRED" badge (text-[9px], opacity-40, primary-fixed-dim, hover:underline)

2. **ENCRYPTION_KEY** (`#password-input`)
   - Type: password (toggleable)
   - Placeholder: "••••••••••••"
   - Autocomplete: current-password
   - Right button: visibility icon (toggle between password/text)
   - Label includes "FORGOT?" link (primary-fixed-dim, hover:underline, shows alert on click)

**Hardware Token Toggle**
- Container: surface-container-low with outline-variant/50 border, p-3
- Left: key_visualizer icon (filled, primary-fixed-dim) + column: "HARDWARE TOKEN" (label-sm, on-surface) + "YubiKey or RSA SecurID Required" (text-[9px], data-md, on-surface-variant)
- Right: Checkbox toggle (default checked) - Tailwind peer-styled custom switch

**Submit Button** (`#connect-btn`)
- Full width, h-10, bg-primary-container, text-on-primary-fixed
- Icon: power_settings_new (filled)
- Text: "CONNECT TERMINAL"
- Border: b-2 border-black/20
- States: hover:opacity-90, active:scale-[0.98]
- On submit: disabled, spinner animation + "CONNECTING..."

**Error Display** (`#login-error`)
- Hidden by default
- Text: error color, label-sm, centered, mt-1

**Footer Bar (Fixed Bottom, z-50)**
- Background: surface-container-lowest with top border
- Links: Network Status, Compliance Desk, System Logs (label-sm, secondary → primary hover)

### JavaScript Functions
- `toggle-pw`: Switches password input type, updates icon (visibility/visibility_off)
- `anim()`: Scanner vertical bounce animation via requestAnimationFrame (pos += 0.4*dir, toggles at 0/100)
- `ty()`: Username placeholder typing effect (100ms per char, starts after 1s)
- `forgot-link`: Alert "Contact security administrator for LD4 access resets."
- `login-form submit` handler:
  - Prevents default
  - Disables button, shows spinner
  - POST `/auth/login` with JSON `{username, password}`
  - On success: stores `access_token` in `window.authToken`, `window.__JWT__`, `sessionStorage` (both access_token and refresh_token); redirects to `/`
  - On error: displays `err.detail` or `err.error` or `err.message`; re-enables button
  - Console logs for debugging

### Security Features
- Password never logged (only length)
- Access token stored in memory only (`window.authToken`)
- Refresh token stored in `sessionStorage` (cleared on tab close)
- CSRF protection not explicitly shown (relies on same-origin + auth headers)

### Styling & Colors
- Dark mode via `class="dark"` on HTML
- Tailwind config defines Material Design 3 color palette
- Primary fixed: #9cf0ff, primary container: #00e5ff
- Background: #101419, surface: #101419, surface-container: #1c2025
- Custom scrollbars: 4px width, track #101419, thumb #3b494c

---

## Mission Control

**Route:** `GET /`  
**Template:** `dashboard/templates/pages/page_mission_control.html`

### Purpose
Real-time overview of trading system status, strategy performance, and recent activity.

### Layout Structure

**Top Navigation Bar (h-14, border-b, bg-surface-container)**
- Left: Search bar (stub, no functionality), domain links: Research, Execution, Operations, Analytics
- Right: Connect Terminal button, notifications icon (notifications), terminal toggle, profile avatar

**Summary Bar (4 KPI Tiles, grid col-span-12)**
- Total Equity: latest account balance
- Daily PnL: realized + unrealized (color: green if positive, red if negative)
- Open Positions: count
- Active Strategies: count

**Equity Curve Section (8 columns)**
- Canvas-based line chart (`#equity-chart`)
- X-axis: time labels (HH:MM format)
- Y-axis (left): normalized equity (linear scale)
- Y-axis (right): drawdown percentage (line, red)
- Range buttons: 1H (3600000ms), 4H (14400000ms), 1D (86400000ms), MAX (all data)
- Legend: colors shown in small swatches

**System Health (4 columns, stat-cards)**
- MT5 Connection: status dot (green/red) + latency ms
- DataFeed: health status
- RiskEngine: status
- Backup: status

**Strategy Grid/List Toggle**
- View switch: Grid icon / List icon
- Grid: responsive card layout showing strategy cards
- List: compact table rows

**Strategy Card Metrics**
- 7D Return: percentage (colorized)
- Sharpe: value
- Max DD: percentage
- Trades: count

**Log Drawer (Slide-up Bottom Panel)**
- Toggle button: "Live Logs"
- Content area: scrollable log lines (`#log-entries`)
- Auto-refresh every 5 seconds when open
- Endpoint: `GET /api/v2/engine-controls/logs?tail=200`

### JavaScript Functions

**Data Loading**
- `loadAll()`: orchestrates calls to `loadStats()`, `loadStrategies()`, `refreshEquity()`, `updateSystemHealth()`
- `loadStats()`: GET `/api/account/stats` → updates KPI tiles
- `loadStrategies()`: GET `/api/strategies` → renders grid/list
- `refreshEquity()`: GET `/api/account/stats` + `/api/account/snapshots?limit=200` → updates equity chart
- `updateSystemHealth()`: GET `/api/v2/mt5/connection` + `/api/v2/engine/status`

**Equity Chart Rendering**
- `initEquityChart()`: creates Chart.js line chart with two datasets (equity fill, drawdown line)
- `filterSnapshots(range)`: filters `snapshots` array by timestamp window
- `renderEquityChart()`: updates chart data with filtered snapshots
- `computeSharpe()`:
  ```
  returns = daily equity differences
  ratio = returns per day sum / returns count
  sharpe = sqrt(ratio * 252) * mean(returns) / std(returns)
  ```
- `computeMaxDrawdown()`: peak tracking algorithm through equity series

**Strategy Views**
- `renderStrategyGrid()`: generates card HTML for each strategy with metrics
- `renderStrategyList()`: generates compact table rows

**Log Drawer**
- `openLogDrawer()` / `closeLogDrawer()`: toggle visibility
- Polling interval: 5 seconds

**Polling**
- Main refresh interval: `pollIntervalMs` from config (default 5000ms)
- `setInterval(loadAll, pollIntervalMs)`

### API Calls
- `GET /api/account/stats` → `AccountSnapshot` (latest equity, balance, margin, etc.)
- `GET /api/account/snapshots?limit=200` → list of snapshots for equity curve
- `GET /api/trades/recent?limit=50` → recent trades (used for some stats)
- `GET /api/strategies` → all `StrategyConfig` records
- `GET /api/strategies/library` → enriched with trade metrics (win_rate, Sharpe, max_drawdown, total_trades, avg_pnl_r)
- `GET /api/v2/mt5/connection` → `{connected, login, server, latency_ms}`
- `GET /api/v2/engine/status` → `{running, regime, uptime_seconds}`
- `GET /api/v2/engine-controls/logs?tail=200` → `{logs: string[]}`

### Calculations (Client-Side)
- Daily PnL: from latest account snapshot (realized_pnl + unrealized_pnl)
- Equity curve normalization: `normalized = equity / equity[0]`
- Drawdown: `(peak - current) / peak * 100`
- Sharpe ratio: see `computeSharpe()` above
- Max drawdown: see `computeMaxDrawdown()` above

---

## Executive Analytics

**Route:** `GET /executive`  
**Template:** `dashboard/templates/pages/page_executive.html`

### Purpose
Institutional performance reporting with tear sheet generation for investor reviews.

### Layout Structure

**Top Bar**
- Refresh button (clockwise arrows icon)
- Generate New Report button (primary, runs optimization and updates charts)

**Row 1: 4 KPI Tiles**
1. Cumulative Return
2. Sharpe Ratio
3. Alpha vs Risk-Free
4. Calmar Ratio

**Row 2 (2 columns)**
- Left (8 cols): NAV Growth Chart (`#exec-nav-chart`) with range buttons (1H/4H/1D/MAX)
- Right (4 cols): Capital Allocation Donut (`#exec-alloc-chart`)

**Row 3 (3 columns)**
- Left (4 cols): Risk/Return Scatter (`#exec-scatter-chart`)
- Middle (5 cols): Drawdown Profile (`#exec-dd-chart`)
- Right (3 cols): Report Panel (buttons: Export PDF, Save to Cloud, Email)

### Data Source
`GET /api/account/snapshots` (optional query: `?limit=365` for annual metrics)

### Calculations (Client-Side)

From equity snapshots array (sorted by timestamp ascending):

**Helper Functions**
```
spanMs = last_ts - first_ts
spanYears = spanMs / (365.25 * 864e5)  // 864e5 = ms per day
start_eq = snapshots[0].equity
end_eq = snapshots[-1].equity

cumReturn = (end_eq - start_eq) / start_eq

dailyReturns = []
for i in 1..len-1:
  r = (snapshots[i].equity - snapshots[i-1].equity) / snapshots[i-1].equity
  dailyReturns.append(r)

dailyVol = std(dailyReturns) * sqrt(252)  // annualized

meanReturn = mean(dailyReturns)
sharpe = (meanReturn * 252 - riskFreeRate) / dailyVol  // assuming riskFreeRate = 0.02

cagr = pow(end_eq / start_eq, 1/spanYears) - 1

// Max drawdown
peak = start_eq
maxDD = 0
for snap in snapshots:
  if snap.equity > peak: peak = snap.equity
  dd = (peak - snap.equity) / peak
  if dd > maxDD: maxDD = dd

calmar = cagr / maxDD if maxDD > 0 else None

// Underwater curve for drawdown profile
underwater = [(peak - snap.equity) / peak * 100 for snap in snapshots]  // percentage
```

### Chart Configurations

**NAV Chart (Chart.js Line)**
- Datasets:
  1. Normalized NAV: line, fill: true, backgroundColor: primary with 0.2 alpha, borderColor: primary
  2. Risk-Free benchmark: line, borderColor: grey, borderDash: [5, 5]
- X-axis: time (HH:MM)
- Y-axis (left): NAV normalized to 1.0
- Range buttons: same windows as Mission Control (1H, 4H, 1D, MAX)

**Allocation Donut (Chart.js Doughnut)**
- Data: sum of `net_pnl_r` per strategy from `/api/strategies/library`
- Group strategies beyond top 7 into "Other" category
- `cutout: "62%"` for thin ring
- Center overlay: count of segments displayed as text
- Legend: color swatch + strategy name + percentage

**Risk/Return Scatter (Chart.js Scatter)**
- Each point represents a strategy with at least one trade
- X: `max_drawdown * 100` (percentage)
- Y: `net_pnl_r * 100` (percentage)
- Point radius: `min(8, max(4, sqrt(total_trades) * 1.2))`
- X-axis label: "Max Drawdown (%)"
- Y-axis label: "Net PnL (%)"
- Legend: shown only if ≤7 strategies, positioned at bottom

**Drawdown Profile (Chart.js Bar)**
- Underwater series sampled to ~60 bars maximum: `step = floor(len(underwater)/60)`
- Bar colors:
  - Green: dd >= -4%
  - Amber: -8% <= dd < -4%
  - Red: dd < -8%
- Recovery annotation: shows trading days since last recovery to -0.1% level
- Average depth line: horizontal line at mean of negative underwater values

### Tear Sheet Modal
- Triggered by "Generate New Report" or "Export PDF"
- Full-screen overlay with `backdrop-blur`
- Content structure:
  - Header: "Executive Tear Sheet" + Today's date + performance period
  - 8 KPI tiles grid
  - Trade Statistics section: total trades, win rate, profit factor, best/worst trade
  - Monthly Returns table: 12 columns (Jan-Dec), rows = years
  - Strategy Performance table: each strategy's key metrics
- PDF export: injects `@media print` CSS (hides everything except modal, black text on white), calls `window.print()`

**Trigger Flow**
- "Generate New Report" button POSTs to `/api/quant/optimise` with body:
  ```
  {
    "strategy": "MultiStrategy",  // special aggregate
    "symbol": "PORTFOLIO",
    "timeframe": "D",
    "param_bounds": {},  // defaults
    "search_method": "grid",
    "fitness_metric": "sharpe",
    "n_iterations": 1
  }
  ```
  and polls until complete, then populates modal (demo implementation in template)

### Polling
- Manual refresh only (no auto-poll) — user clicks Refresh button

---

## Portfolio Risk Monitor

**Route:** `GET /portfolio-risk`  
**Template:** `dashboard/templates/pages/page_portfolio_risk.html`

### Purpose
Real-time risk metrics and position concentration monitoring.

### Layout Structure

**Top Row: 5 KPI Panels (grid-cols-5)**
1. Daily DD % — current day drawdown percentage (colorized)
2. Weekly DD % — rolling 7-day drawdown
3. Total Exposure USD — gross long + short exposure
4. VaR 95% 1D USD — Value at Risk (1.645 * sqrt(variance))
5. Margin Usage % — margin / equity

**Main Content (grid)**

**Left Panel (9 cols): Open Positions Table**
Full-width table with columns:
- Account (font-mono, text-[12px])
- Symbol (font-medium primary)
- Direction: Long/Short badge (green/red tint)
- Entry price (right-aligned)
- Current price (right-aligned, 5 decimals)
- Size (lots, right, format "X.XX")
- SL / TP (right, outline variant)
- PnL (right, colorized green/red/gray)
- Risk % (right, computed as `|price - sl| / price * size * contract_size / equity * 100`)

Data source: `GET /api/risk/overview.positions`

**Right Sidebar (3 cols)**
- Asset Allocation Donut (`#alloc-chart`) — Canvas 128x128, stroke chart with `lineWidth=16` (manual rendering)
- Strategy Exposure Bars (`#strat-bars`) — vertical stacked bars, tooltips show USD amounts

**Bottom Row**
- Left (8 cols): Correlation Matrix (`#corr-grid`) — 6x6 grid of asset class correlations
- Right (4 cols): Risk Alerts (`#alerts-list`) — bulleted list with severity icons

### JavaScript Functions

**Main Loop**
- `tick()`: `setInterval` every 6000ms → `refreshAll()`
- `refreshAll()`: parallel fetch `GET /api/risk/overview`, then `renderAll()` + `scheduleNextRefresh()`

**Rendering**
- `renderAlloc(d)`: manual Canvas donut
  - `ctx.arc()` with `lineWidth=16` for each asset class slice
  - Colors by `_asset(symbol)` mapping: crypto (purple), fx (cyan), equities (amber), metals (gold), fixed income (emerald)
  - Center label shows gross exposure (formatted USD)
- `renderCorrelation(d)`: builds CSS grid 6x6
  - Labels: ["trend", "mean_reversion", "hft_scalp", "macroscopic_event", "swing_divergence", "other"]
  - Diagonal cells: highlighted (primary-color text)
  - Absolute correlation > 0.5: bold + colored
- `renderAlerts(d)`: populates alert list
  - Alerts generated if:
    - Asset concentration > 35%: show symbol with warning icon
    - Daily DD < -2%: show percentage with error icon
    - Margin usage > 80%: show usage with warning
    - Free margin ratio < 20%: critical error

**Helper Functions**
- `_asset(sym)`: asset class by symbol prefix (BTC/ETH → crypto, EUR/GBP → fx, XAU/XAG → metals, AAPL/TSLA → equities, US10Y → fixed income, else "other")
- `_grp(name)`: strategy group by name keywords ("trend" → "trend", "revert" → "mean_reversion", etc.)

### API Endpoint
- `GET /api/risk/overview` returns:
  ```json
  {
    "daily_dd_pct": 1.23,
    "weekly_dd_pct": 2.45,
    "total_exposure_usd": 125000,
    "var_95_1d_usd": 8421,
    "margin_usage_pct": 45.2,
    "positions": [
      {
        "account": "LD4-PRIME",
        "symbol": "BTCUSD",
        "side": "BUY",
        "entry": 42500.0,
        "price": 42850.0,
        "size": 0.5,
        "sl": 42200.0,
        "tp": 43100.0,
        "pnl": 175.0,
        "risk_pct": 1.2
      }
    ],
    "asset_allocation": {
      "crypto": 45000,
      "fx": 32000,
      "equities": 28000,
      "metals": 15000,
      "fixed_income": 5000
    },
    "strategy_exposure_usd": {
      "trend": 60000,
      "mean_reversion": 35000,
      "swing_divergence": 30000
    },
    "correlation_matrix": [[1.0, 0.12, -0.08, ...], ...],
    "alerts": ["High concentration in BTC (42%)", "Daily DD approaching 2% limit"]
  }
  ```

### Polling Interval
- 6000ms (6 seconds)

---

## Multi-Account Management

**Route:** `GET /multi-account`  
**Template:** `dashboard/templates/pages/page_multi_account.html`

### Purpose
Manage multiple MT5 accounts from a unified interface with bulk operations.

### Layout Structure

**Top KPI Cards (4 cols)**
- Total Equity (sum across accounts)
- Free Margin (aggregate)
- Drawdown (worst across accounts)
- Profit (sum of today's PnL)

**MT5 Instance Matrix Table (full width, sticky)**
- Bulk actions bar (hidden until rows selected)
- Columns:
  - Checkbox (for bulk selection)
  - Account: name with color swatch (circle)
  - Broker: broker name
  - Server: MT5 server
  - Status: badge (Connected/Inactive/Paused) with text
  - Equity: formatted USD
  - Balance: formatted USD
  - Margin %: percentage
  - Positions: count
  - Weight: numeric weight for capital allocation (colored: >=1 primary container, >0 outline, 0 error)
  - Actions: more_vert icon button → opens drawer

**Recent Orders Table** (fixed max-height 180px)
- Columns: Time, Symbol, Type (BUY/SELL), Size, Price, Status (FILLED/PENDING/CANCELLED), PnL

**Account Detail Drawer** (slide-out right panel, off-canvas by default)
- Header: color swatch + account name + meta line + status badge
- KPIs: Balance, Equity, Free Margin (3-col grid)
- Action buttons row: Connect, Disconnect, Pause Trading, Close All Positions
- Form:
  - Weight: number input step 0.05, min 0, max 10
  - Display Name: text input
  - Notes: textarea
- Footer action buttons depending on state

**Add Account Modal** (centered overlay, hidden)
- Form fields:
  - Account Name (*required)
  - Broker: select dropdown (options: "JustMarkets", "IC Markets", "Pepperstone", "OANDA", "Interactive Brokers")
  - Account Type: radio (Demo / Live)
  - Server: text
  - MT5 Login: number
  - Weight: number (default 1.0)
  - Password: password (required)
  - Investor Password: password (optional)
  - Notes: textarea
  - Color: hidden field (stores selected swatch hex)
- Color swatch picker: 10 predefined colors in circular buttons
- Validation: required fields must be filled; shows error message otherwise

**Killswitch Modal** (emergency overlay, hidden)
- Warning text: "This will disconnect ALL accounts and stop all trading. Type CONFIRM to execute."
- Input: text (must equal "CONFIRM" for button to enable)
- Execute button: disabled until typed correctly

### JavaScript Functions

**Loading**
- `loadAll()`: parallel GET `/api/v2/accounts/` + `/api/trades/recent?limit=10`
- Matrix table rendering: loops accounts, creates table rows with checkbox, swatch, status badge, weight
- Recent orders table: loads from trades

**Drawer Logic**
- `openDrawer(account_id)`: finds account in `_accounts`, populates drawer fields, shows drawer
- `closeDrawer()`: hides drawer
- Drawer actions POST to `/api/v2/accounts/{id}/action`:
  - `{action: "connect"}` → connects MT5
  - `{action: "disconnect"}` → disconnects
  - `{action: "pause"}` → pauses trading
  - `{action: "set_weight", value: number}` → updates weight
  - `{action: "rename", value: string}` → updates display name
  - `{action: "close_all_positions"}` → bulk close
  - `{action: "test_connection"}` → health check

**Add Account Modal**
- `pickColour(hex)`: updates hidden input and swatch border highlight
- `openAddModal()` / `closeAddModal()`
- `submitAdd()`: validates required fields, POST `/api/v2/accounts/`, on success closes modal and `loadAll()`

**Bulk Actions**
- Checkbox selection updates `_selected` Set
- `_selected.size` shown in bulk bar
- Bulk disconnect: `POST /api/v2/accounts/bulk/disconnect-all`
- Bulk close all: `POST /api/v2/accounts/bulk/close-all`

**Polling**
- Interval: 8000ms (8 seconds)
- `setInterval(reloadAll, 8000)`

### API Endpoints Used
- `GET /api/v2/accounts/` → list of accounts with runtime fields
- `GET /api/trades/recent?limit=10` → recent orders
- `POST /api/v2/accounts/` → create account
- `PATCH /api/v2/accounts/{id}` → update (weight, display_name, notes)
- `DELETE /api/v2/accounts/{id}` → delete
- `POST /api/v2/accounts/{id}/action` → action endpoint
- `POST /api/v2/accounts/bulk/disconnect-all`
- `POST /api/v2/accounts/bulk/close-all`

---

## Trade Operations & Journaling

**Route:** `GET /trade-ops`  
**Template:** `dashboard/templates/pages/page_trade_ops.html`

### Purpose
Real-time trade execution monitoring, quality metrics, and journal annotation interface.

### Layout Structure

**Fixed Top Bar (h-12, bg-surface-container, border-b)**
- Search input (left, placeholder "Search trades...")
- Filters button (filter_list icon)
- Account selector dropdown (`#to-account`)
- Regime button (`#to-regime-btn`) — shows current market regime (Trending/Ranging)
- Connection status dot (green pulse / red)
- Notifications icon (badge count)
- Profile avatar (right)

**Main Grid (12 columns)**

**Panel 2: Live Executions & Pending Orders (col-span-8, flex-1)**
- Sticky header table (`#to-exec-table`)
- Table columns:
  - Account (font-mono, text-[12px])
  - Symbol (font-medium)
  - Type: side badge (BUY: bg-emerald/15 text-emerald-700, SELL: bg-red/15 text-red-700)
  - Status: badge (FILLED: bg-primary-container text-on-primary-fixed, PENDING: bg-tertiary-container text-on-tertiary-fixed, CANCELLED: bg-surface-variant text-on-surface-variant)
  - Price: right-aligned, 5 decimals
  - Size: right-aligned, format "X.XX Lot"
  - TP / SL: right, outline variant text
  - U.PnL: right, colorized (green/red/gray)
  - Action: center, close icon button (x to close position)
- Row attributes: `data-ticket`, `data-symbol`
- Close button: confirms and shows alert stub (production hooks to MT5Adapter.close_position)

**Panel 3: Execution Quality (col-span-4, 4 metric boxes)**
- Slippage (bps)
- Latency (ms)
- Fill Rate (%)
- Rejections (%)
Each box: label + value (`#to-*_val`) + progress bar (`#to-*_bar`) width reflects metric

**Panel 4: Historical Trade Log (col-span-7)**
- Columns: Time (UTC HH:MM:SS), Symbol, Side (color badge), Profit (signed +$X.XX colorized), R:R (RR ratio), Strategy
- Row click → populates journal panel
- CSV export button at bottom

**Panel 5: Journal & Annotations (col-span-5)**
- Trade selector dropdown (`#to-trade-select`) — options built from historical log rows
- Alpha factor tags (chips): clickable to toggle selection:
  - Mean Reversion
  - Volatility Spike
  - HFT Front-run
  - Liquidity Gap
  - Order Block
  - Trending
  - Ranging
- Notes textarea (`#to-journal-notes`) — full height, monospace
- Recent Annotations list (`#to-ann-list`) — each with delete button (trash icon)
- Chart attach placeholder (dashed border, "Attach Chart" text, click handler stub)
- Footer: "Potential Alpha Leakage" with red progress bar

**Fixed Bottom Bar (h-6, border-t, bg-surface-container-lowest)**
- Left: Port label (`#to-port-label`, from config or 8000)
- Sync timestamp (`#to-sync-ts`, shows "Updated 3s ago")
- Engine status (`#to-engine-status`, "RUNNING" green or "IDLE" outline)
- Right: Ticker clock (`#to-ticker-clk`, EST HH:MM:SS updating every second)

### JavaScript Functions

**Executions Loading**
- `loadExecutions()`:
  - GET `/api/mt5/positions` (for open positions)
  - GET `/api/mt5/orders` (for pending orders)
  - Filters by `selectedAccount` (from `#to-account`)
  - Renders rows in `#to-exec-table`
  - Row data: ticket, symbol, side, volume, price_open, sl, tp, profit

**Execution Quality**
- `computeExecQuality(deals)`: mock values (slippage 0.42 bps, latency 3.2ms, fill 99.8%, reject 0.02%)
- `loadExecQuality()`:
  - Caches for 30 seconds
  - Updates `#to-slippage_val`, `#to-latency_val`, `#to-fill_val`, `#to-reject_val`
  - Sets progress bar widths:
    - Slippage: `slippage_bps / 2`% (capped at 100)
    - Latency: `100 - latency_ms * 5`% (inverse, capped)
    - Fill: `fill_rate_pct`%
    - Reject: `rejections_pct * 500`%

**Historical Log**
- `loadHistoricalLog()`: GET `/api/trades/recent?limit=50`; populates table; rows clickable
- `populateJournalFromTrade(row)`: sets `#to-trade-select` to trade ID, fills notes with context "Trade {id}: {symbol} {side}", calls `loadAnnotations(tradeId)`

**Annotations**
- `loadAnnotations(tradeId)`: GET `/api/journal/annotations?trade_id={tradeId}`; renders list in `#to-ann-list`
- Each annotation item: note text + delete button (trash icon)
- Delete: `apiDel('/journal/annotations/{id}')` then `loadAnnotations(tradeId)`
- Save new annotation: POST `/api/journal/annotations` with `{trade_id, note, tag}`; on success clears notes, flashes overlay

**Tag System**
- `selectedTags` Set tracks selected alpha factor chips
- Click chip → toggles border-primary/text-primary vs outline state

**Flash Overlay**
- `flash(msg)`: fades in overlay div covering journal panel, shows message, fades out after 1s

**Bottom Bar Updates**
- `updatePort()`: GET `/api/v2/accounts/summary` to compute total equity; updates `#to-port-label`
- `updateEngineStatus()`: GET `/api/v2/engine/status` → sets `#to-engine-status` text and color
- `updateTicker()`: EST time clock updating every second

**Reload Cycle**
- `reloadAll()`: calls `loadExecutions()`, `loadExecQuality()`, `loadHistoricalLog()`, `updatePort()`, `updateEngineStatus()`
- Interval: `pollIntervalMs` from config (default 8000ms)
- `setInterval(reloadAll, pollIntervalMs)`

**CSV Export**
- Export button in historical log: gathers all table rows, builds CSV string with headers, triggers blob download

**Connection Status**
- `updateConnectionStatus()`: GET `/api/v2/mt5/connection`; sets dot color (emerald/red) and label

**Regime Display**
- `updateRegime()`: GET `/api/v2/engine/status`; shows `eng.regime` or "Running"/"Idle"

### API Endpoints Used
- `GET /api/mt5/positions` → list of open positions (MT5 positions)
- `GET /api/mt5/orders` → list of pending orders
- `GET /api/trades/recent?limit=50` → historical trades
- `GET /api/v2/accounts/summary` → total equity across accounts
- `GET /api/v2/engine/status` → engine state
- `GET /api/v2/mt5/connection` → connection health
- `GET /api/journal/annotations?trade_id=` → list annotations
- `POST /api/journal/annotations` → create annotation
- `DELETE /api/journal/annotations/{id}` → delete annotation

### Calculations
- Execution quality metrics (mocked in template)
- R:R ratio for historical trades: `abs(entry - exit) / abs(entry - sl)` (assuming sl present)
- PnL colorization: positive green, negative red, zero gray

### Polling Interval
- 8000ms (8 seconds)

---

## Risk & Compliance

**Route:** `GET /risk-compliance`  
**Template:** `dashboard/templates/pages/page_risk_compliance.html`

### Purpose
Regulatory compliance monitoring and strategy risk metrics dashboard.

### Layout Structure

**Two Tables (Full Width)**

**Table 1: Strategy Risk Metrics**
Columns:
- Name: strategy name (font-mono)
- Win Rate: percentage (right-aligned)
- Sharpe: ratio (right-aligned)
- Max DD: percentage (right-aligned)
- Exposure ($K): USD thousands (right)
- VaR %: Value at Risk percentage (right)
- Status: badge (Active/Inactive/Paused)

**Table 2: Compliance Event Log**
Columns:
- Time: HH:MM:SS UTC
- Event: event description
- Status: OK (green), Warning (amber), Breach (red)

### JavaScript Functions

**`loadRisk()`**
Parallel GET:
- `GET /api/strategies/library` → strategy list with metrics
- `GET /api/account/stats` → latest equity snapshot

For each strategy, computes:
```
wr_pct = (win_rate * 100).toFixed(1) + '%'
sharpe = if avg_pnl_r > 0 then (avg_pnl_r * sqrt(min(total_trades, 30))).toFixed(2) else "—"
maxDD = (abs(avg_pnl_r) * (1 - win_rate) * 100).toFixed(1) + '%'
exposure_K = if equity then (total_trades * equity * 0.001).toFixed(1) + 'K' else "—"
varPct = (abs(avg_pnl_r) * 1.65 * 100).toFixed(2) + '%'
```

**`loadCompliance()`**
- GET `/api/trades/recent?limit=30`
- For each trade:
  - pnl_r < -1: "Loss threshold exceeded" → Breach (red)
  - pnl_r < 0: "Trade closed at loss" → Warning (amber)
  - else: "Trade executed" → OK (green)
- Adds row to compliance table with timestamp

**Polling**
- `setInterval(loadAll, 30000)` (30 seconds)

### API Endpoints
- `GET /api/strategies/library` → `[{name, label, symbol, timeframe, is_active, version, trades, win_rate, avg_pnl_r, max_drawdown, sharpe}, ...]`
- `GET /api/account/stats` → latest snapshot
- `GET /api/trades/recent?limit=30` → recent trades for compliance events

### Notes
- Sharpe, Max DD, Exposure, VaR are *heuristic approximations* (not backtest accurate)
- Uses `min(total_trades, 30)` to cap Sharpe multiplier
- Exposure heuristic: `total_trades * equity * 0.001` (assumes avg 0.1% risk per trade)
- VaR: `abs(avg_pnl_r) * 1.65 * 100` (1.645 ≈ 95% z-score)

---

## ML Center

**Route:** `GET /ml`  
**Template:** `dashboard/templates/pages/page_ml.html`

### Purpose
Machine learning model lifecycle management: training, evaluation, feature analysis, and deployment as strategies.

### Layout Structure

**Top Stats Bar (4 metric cards)**
- Trained Models: count of all models
- Active: count of `is_active=True`
- Avg Accuracy: mean of test accuracy across models
- Models Deployed: count of `StrategyConfig` names starting with `ml_`

**Train New Model Form (grid-cols-6)**
- Symbol select (`#ml-train-symbol`) — populated from `/api/v2/backtest/symbols`
- Timeframe select (`#ml-train-timeframe`) — from `/api/v2/backtest/timeframes`
- Model Type select (`#ml-train-type`):
  - RandomForest
  - GradientBoosting
  - LogisticRegression
  - XGBoost (if available)
- Model Name input (`#ml-train-name`) — text, e.g., "btc_momentum_v1"
- CV Folds input (`#ml-train-folds`) — number 3-10 default 5
- Train button (`#ml-train-btn`) — POSTs to `/api/v2/ml/train`

**Model Registry (Responsive Grid: 1/2/3 cols)**
- Each model card (`#ml-models-grid`) shows:
  - Header: name + status badge (pending/training/ready/active/failed)
  - 2×2 metric grid: Symbol, Timeframe, Type, Accuracy, Precision, Recall, F1, Created, Last trained, Training Samples
  - Action buttons:
    - Deploy as Strategy (emerald)
    - Retrain (accent)
    - Live Predict (primary)
  - On "Live Predict": POST `/api/v2/ml/predict` appends row to Live Prediction Stream

**Feature Analysis Section**
- Model select dropdown (`#fi-model-select`)
- Analyze button (`#fi-load-btn`)
- Horizontal bar chart canvas (`#fi-chart`) showing top 15 features by importance

**Deployed ML Strategies Table**
- Columns: Strategy Name, Symbol, TF, Model ID, Active (toggle), Latest Prediction side/confidence

**Live Prediction Stream Table**
- Columns: Time (HH:MM:SS), Symbol, TF, Direction (BUY/SELL color), Confidence %, Model
- Auto-refresh: every 30s, loops active models, POSTs predict

### JavaScript Functions

**Model Training**
- `trainModel()`: collects form values, POST `/api/v2/ml/train` with body:
  ```json
  {
    "symbol": "...",
    "timeframe": "...",
    "model_type": "...",
    "model_name": "...",
    "cv_folds": 5
  }
  ```
  returns `{model_id, status}`; starts `pollTrainStatus(model_id)`
- `pollTrainStatus(id)`: every 5s GET `/api/v2/ml/models` → finds model by id; if status "ready" shows metrics; if "failed" shows error

**Feature Importance**
- `refreshFiSelect()`: populates dropdown from `ALL_MODELS` array (cached) with models having `feature_importance`
- `loadFi()`: GET `/api/v2/ml/models/{id}/features` → `{features: [{name, importance}]}`; sorts descending; `drawFeatureChart()`
- `drawFeatureChart()`: Chart.js horizontal bar chart (`indexAxis: 'y'`), amber bars, labels = feature names

**Deployed Table**
- `loadDeployedStrategies()`: GET `/api/v2/strategies/` filters `name.startsWith('ml_')`; shows params.model_id, side, active badge

**Live Prediction Stream**
- `loadPredStream()`: GET `/api/v2/ml/models` → filters active; for each, POST `/api/v2/ml/predict` with `{model_id}`; appends row with timestamp
- Auto-refresh: `setInterval(loadPredStream, 30000)` (30s)

**Populating Selects**
- On page load: GET `/api/v2/backtest/symbols` and `/api/v2/backtest/timeframes` to populate train selects

**Model Cards**
- Shows `status` from model record (pending, training, ready, active, failed)
- Deploy button POSTs `/api/v2/ml/models/{id}/deploy` (creates StrategyConfig for model, updates is_active)
- Retrain button POSTs `/api/v2/ml/retrain/{id}` (resets status to pending, starts training)

### API Endpoints
- `POST /api/v2/ml/train` — queue training; returns `{model_id, status}`
- `GET /api/v2/ml/models` — list models (optional `?symbol=&timeframe=` filters)
- `GET /api/v2/ml/models/{model_id}` — model detail (params, metrics)
- `DELETE /api/v2/ml/models/{model_id}` — delete model and artifact file
- `POST /api/v2/ml/models/{model_id}/deploy` — toggle is_active, creates StrategyConfig
- `POST /api/v2/ml/predict` — run inference; body `{model_id}`; returns `{symbol, timeframe, model_name, prediction: {direction, confidence, probability}}`
- `GET /api/v2/ml/models/{id}/features` — `{features: [{name, importance}]}`
- `POST /api/v2/ml/retrain/{model_id}` — retrain from existing params
- `GET /api/v2/ml/history?symbol=&model_id=&limit=100` — prediction history

### Background Training
`dashboard/v2/routes/ml.py` `_train_worker()` uses sklearn if available, else mocks with random metrics. Artifacts saved to `ml_models/` directory.

### Polling
- Model status: 5s during training
- Prediction stream: 30s

---

## AI Research

**Route:** `GET /ai-research`  
**Template:** `dashboard/templates/pages/page_ai_research.html`

### Purpose
AI advisor configuration, signal monitoring, and quant research terminal interface.

### Layout Structure (3-column workspace)

**Left Column (col-span-3)**

**AI Configuration Panel**
- Confidence Threshold slider (`#ai-confidence-slider`): range 0-100, display updates, on change PUT `/api/v2/ai/config` with `{min_confidence_to_show: value/100}`
- Cooldown buttons: 5m, 15m, 1h (PUT `/api/v2/ai/config` with `{cooldown_minutes}`)
- Knowledge Bases: checkboxes (Market Microstructure, Central Bank Speeches, Retail Sentiment) — visual only, no network

**Signal Heatmap** (`#heatmap-grid`)
- Grid: 4 columns, auto rows
- Each cell: symbol name + score badge + direction arrow
- Color coding:
  - Bullish: primary/20 border + primary text
  - Bearish: error/20 border + error text
  - Neutral: surface-variant border
- Legend below: color swatches + labels
- Demo badge (`#heatmap-demo-badge`) shown when `is_demo=true`

**Center Column (col-span-5)**

**Active AI Suggestions Table** (`#ai-suggestions-table`)
- Columns: Symbol, Direction (BUY/SELL color), Conf %, Entry Zone, SL Zone, TP Zone
- Search input above table filters rows
- Row click: loads reasoning into right panel, highlights row

**Automated Reasoning Panel** (grid 3 cols)
- Market Context (`#reason-context`): text paragraph
- Alpha Factor Alignment (`#reason-alpha`): list of factors with values
- Risk Assessment (`#reason-risk`): bulleted list with icon

**Right Column (col-span-4)**

**Quant Terminal** (`#terminal-*`)
- Output div (`#terminal-output`): scrollable log of chat + SQL
- Input (`#terminal-input`): text field
- Send icon (`#terminal-send`) → click or Enter triggers `sendChat()`
- POST `/api/v2/ai/chat` with `{query, context}`; response includes `{answer, sql?}`

**Confidence Distribution Chart** (`#confidence-chart`)
- Horizontal bar chart: 4 bins (30–50%, 50–70%, 70–90%, 90%+)
- Shows count of suggestions per bin

**Stats Bar** (`#stat-accuracy`, `#stat-alpha`)
- Suggestion Accuracy: win rate of AI trades %
- Avg Alpha: mean pnl_r of AI trades

**Footer Bar (Fixed Bottom)**
- Status dot (green pulse if connected)
- Latency: ms
- Throughput: suggestions/sec
- UTC clock updating every second

### JavaScript Functions

**Initialization**
- `init()`: GET `/api/v2/ai/config`; sets slider, display, cooldown button state; starts 10s poll interval

**Config Toggle**
- `updateToggleUI()`: reads `_aiEnabled` (from suggestions presence or config), updates toggle switch; button toggles via POST `/api/v2/ai/toggle`

**Heatmap**
- `loadHeatmap()`: GET `/api/v2/ai/heatmap`; renders grid cells; shows demo badge if `is_demo`
- `renderHeatmap(assets)`: loops 12 cells (fixed asset list), calculates score, direction, cell color

**Suggestions**
- `loadSuggestions()`: GET `/api/v2/ai/suggestions?limit=50`; `renderSuggestions()` builds table rows
- `selectSuggestion(id, symbol)`: GET `/api/v2/ai/reasoning/{symbol}`; fills reasoning panels; highlights selected row

**Confidence Chart**
- `updateConfidenceChart(suggestions)`: bins by confidence, draws Chart.js horizontal bar

**Terminal**
- `sendChat()`: POST `/api/v2/ai/chat` with `{query}`; appends user query and AI answer to `#terminal-output`; if `sql` key present, displays in code block

**Cooldown & Confidence**
- Cooldown buttons: set `cooldown_minutes` (5/15/60) via PUT `/api/v2/ai/config`
- Slider: on change PUTs new `min_confidence_to_show`

**Polling**
- `setInterval(() => { loadHeatmap(); loadSuggestions(); }, 10000)` (10s)

### API Endpoints
- `GET /api/v2/ai/suggestions?limit=50` → `{suggestions: [{id, symbol, timeframe, side, confidence, reasoning, market_context, entry, sl, tp1, tp2, created_at}], total_signals, accuracy_pct, avg_alpha, stats}`
- `GET /api/v2/ai/heatmap` → `{assets: [{symbol, score, signal_count, direction, is_demo}], is_demo, note?}`
- `GET /api/v2/ai/reasoning/{symbol}` → `{symbol, direction, confidence, market_context, alpha_factors: [{name, value}], risk_bullets: [{icon, text}], model_version, is_demo}`
- `POST /api/v2/ai/chat` → `{answer: "...", sql?: "..."}`
- `POST /api/v2/ai/toggle` → `{name: "ai_trading", is_active: bool}`
- `GET /api/v2/ai/config` → `{is_enabled, provider, model, min_confidence_to_show, cooldown_minutes, max_tokens, strategy_active, strategy_params}`
- `PUT /api/v2/ai/config` → updates cooldown_minutes, min_confidence_to_show, symbols, timeframe, min_confidence
- `POST /api/v2/ai/generate` → `{generated, symbols, timeframe}` (for manual trigger)

### Mock Data
Heatmap returns demo data when no suggestions exist:
```json
{
  "assets": [
    {"symbol": "XAUUSD", "score": 0.85, "signal_count": 3, "direction": "LONG", "is_demo": true},
    {"symbol": "BTCUSD", "score": -0.62, "signal_count": 2, "direction": "SHORT", "is_demo": true},
    ...
  ],
  "is_demo": true,
  "note": "No live suggestions yet — showing demo data."
}
```

---

## Optimization Hub

**Route:** `GET /optimization`  
**Template:** `dashboard/templates/pages/page_optimization.html`

### Purpose
Parameter optimization for strategies using grid, random, or Bayesian search.

### Layout Structure

**Left Sidebar (w-72, border-r, overflow-y-auto)**

- Strategy Select dropdown (`#opt-strategy-select`) — populated from `/api/v2/backtest/strategies`
- **Parameter Bounds Builder** (`#opt-params-area`):
  - Generated after strategy selection
  - For each param in strategy.default_params:
    - Label: param name
    - Min input (number)
    - Max input (number)
    - Step input (number)
- **Search Method** (`#opt-search-method`): Radio buttons
  - Grid Search (option)
  - Random Search
  - Bayesian (GP)
- **Fitness Function** (`#opt-fitness`): Radio buttons with visual select
  - Sharpe Ratio (radio)
  - Calmar Ratio
  - Net Profit
- **Symbol / Timeframe Info** (hidden until strategy selected): shows default symbol/timeframe from strategy class
- **START OPTIMIZER** button (`#opt-start-btn`) — disabled until strategy selected
- **Progress Bar** (`#opt-progress`, hidden): shows completion %
- **Status Message** (`#opt-status`): colored text

**Main Content (flex-1, p-6)**

**Parameter Surface Heatmap** (canvas `#opt-heatmap`, height 280px)
- Grid of colored cells representing fitness across 2D parameter space
- Color gradient: slate (#475569) → cyan (#06b6d4) → gold (#fbbf24)
- Cell size: `cellW = max(24, min(48, 600 / p1Arr.length))`
- Hover: scales to 1.25, shows tooltip with coordinates and score
- X-axis: first parameter (label at bottom)
- Y-axis: second parameter (label rotated vertical on left)

**Top Parameter Sets Table** (`#opt-top-table`)
- Columns:
  - Rank (1-10)
  - Parameters: badges per param (bg-surface-container-high, px-2 py-1 rounded)
  - Fitness (metric value, right-aligned)
  - Sharpe, PF, Max DD, Trades (right columns)
  - Action: LOAD button → loads params into strategy (PUT `/api/quant/optimise/{run_id}/deploy`)

**Optimization History List** (`#opt-history-list`)
- Each entry: status dot (green/amber/red), strategy name, date, iterations, best Sharpe
- Click entry loads that run's results

### JavaScript Functions

**Initialization**
- `initOpt()`: loads strategies list → populates `#opt-strategy-select`; binds change handler

**Strategy Selection**
- `onStrategyChange()`: fetches strategy class via GET `/api/v2/backtest/strategies` (or from cached); shows symbol/timeframe; builds parameter inputs from `default_params`

**Parameter Bounds Builder**
- `buildParamTable(default_params)`: for each param key, creates:
  - Label: text-capitalize
  - Min input: value = bound.min or default * 0.5
  - Max input: value = bound.max or default * 2
  - Step input: default = (max-min)/20 or 1 for integers
  - Validation: min < max, step > 0

**Running Optimisation**
- `runOptimisation()`: collects form:
  ```json
  {
    "strategy_name": select.value,
    "symbol": strategy.default_symbol,
    "timeframe": strategy.default_timeframe,
    "param_bounds": {param: {min, max, step} for each param},
    "search_method": radio value,
    "fitness_metric": radio value,
    "n_iterations": 200 (hardcoded default)
  }
  ```
  POST `/api/quant/optimise`; receives `{run_id}`; starts `pollRun(run_id)`
- `pollRun(run_id)`: every 3s GET `/api/quant/optimise/{run_id}`; on status "complete":
  - Hides progress, shows results
  - `renderHeatmap(heatmap_data)`
  - `renderTopResults(top_n_results)`

**Heatmap Rendering**
- `renderHeatmap(heatmap_data)`:
  - Extracts unique values for p1 and p2 axes (first two params)
  - Canvas context: `createLinearGradient` from slate to cyan to gold
  - Loop p2 rows (top to bottom), p1 cols (left to right): fillRect with color = gradient(score normalized)
  - Draw axis labels; p2 rotated -90°
  - Hover: track mouse, find cell, scale via `ctx.scale(1.25, 1.25)` centered on cell

**Top Results Table**
- `renderTopResults(results)`: each row has param badges: `<span class="badge">{key}={value}</span>`
- LOAD button: PUT `/api/quant/optimise/{run_id}/deploy` with `{}` (uses best_params stored on run)

**Export CSV**
- Export button triggers download of all results as CSV: columns rank, params (JSON-stringified), score, sharpe, profit_factor, max_drawdown, n_trades

**Polling**
- During run: every 3000ms (3s)
- Status updates to progress bar (computing percent from current iteration / n_iterations)

### API Endpoints
- `GET /api/v2/backtest/strategies` → `[{name, label, symbol, timeframe, default_params, param_bounds}]`
- `GET /api/v2/backtest/symbols` → `{groups: {asset_class: [symbols]}, pool: {symbol: metadata}}`
- `GET /api/v2/backtest/timeframes` → `{timeframes: ["M1","M5",...], mt5_minutes: {M1:1, M5:5, ...}}`
- `POST /api/quant/optimise` → `{run_id}`
- `GET /api/quant/optimise` → list of recent runs
- `GET /api/quant/optimise/{run_id}` → full run with `status, param_bounds, best_params, best_score, heatmap_data, top_n_results, n_iterations, ...`
- `PUT /api/quant/optimise/{run_id}/deploy` → applies `best_params` to StrategyConfig via `StrategyRegistry.update_params()`

### Backend Process (`quant/optimiser.py`)
- Search strategies:
  - Grid: iterates all combinations within bounds (step increments)
  - Random: samples `n_iterations` uniformly from bounds
  - Bayesian: uses scikit-optimize `gp_minimize` if available, else falls back to random
- For each parameter set: runs backtest via `BacktestEngine`, computes fitness metric from result
- Returns:
  - `best_params`: dict
  - `best_score`: float
  - `heatmap_data`: for first two params, list of `{p1, p2, score}` (used for 2D heatmap)
  - `top_n_results`: top 10 parameter sets with full metrics
  - `n_iterations`: total evaluated

---

## Hypotheses Center

**Route:** `GET /hypotheses`  
**Template:** `dashboard/templates/pages/page_hypotheses.html`

### Purpose
Quantitative research hypothesis tracking from idea through validation to deployment.

### Layout Structure

**Top Bar**
- Refresh button (`#hyp-refresh-btn`)
- New Hypothesis button (`#hyp-new-btn`) — opens modal

**Context Bar**
- View toggles: Kanban ( Kanban icon ) / Table ( table icon )
- Status filter dropdown (`#hyp-status-filter`): options: DRAFT, RESEARCHING, BACKTESTING, VALIDATED, DEPLOYED, (REJECTED hidden)
- Asset Class filter dropdown (`#hyp-asset-filter`): FX, Crypto, Equities, Metals, Fixed Income, All
- Search input (`#hyp-search`) — filters by title/description

**Collapsible Summary Table** (Active Hypothesis Registry)
- Shows active hypotheses in compact table: ID, Title, Asset Class, Status, Progress % (computed from stage), Last Updated
- Toggle collapse/expand

**Kanban Board (5 pipeline columns + hidden REJECTED)**
Columns (left to right):
1. DRAFT
2. RESEARCHING
3. BACKTESTING
4. VALIDATED
5. DEPLOYED
6. REJECTED (hidden by CSS, shown if filter selected)

Each column contains draggable cards (hypothesis items).

**Hypothesis Card**
- Header: ID (mono), title (truncated), asset badge (small, color by class)
- Body: description (2 lines max), timeframe symbol
- Progress bar: shows stages passed / total stages
- Footer: action buttons:
  - "Advance to [Next Stage]" (if not at max)
  - "Deploy Strategy" (only when status=VALIDATED)
  - "Discard" (✕ icon)
- Overlay on hover: shadow, border-primary

**Hypothesis Detail (right-side panel when card clicked, optional — may be stub)**

**Floating Status Overlay (Bottom-Right)**
- Engine Live dot (pulsing green)
- Latency ms
- CPU %

### JavaScript Functions

**Loading**
- `loadHypotheses()`: GET `/api/quant/hypotheses`; renders current view (kanban/table)
- `renderKanban()`: clears column containers, appends cards to appropriate columns
- `renderTable()`: populates summary table rows

**Filtering**
- `applyFilters()`: on status/asset/search change → filters `_hypotheses` array and re-renders
- Asset class detection: `_assetClass(symbol)` by prefix mapping (FX: EUR/GBP/USD/JPY/AUD/NZD/CAD/CHF; Crypto: BTC/ETH/SOL/BNB/XRP; Equities: AAPL/TSLA/NVDA/MSFT/GOOGL/AMZN; Metals: XAU/XAG/GOLD/SILVER; Fixed Income: US10Y/US02Y/DXY)

**Card Actions**
- `advanceHypothesis(id)`: PATCH `/api/quant/hypotheses/{id}` with `{status: next_stage}`; refresh
- `deployHypothesis(id)`: creates StrategyConfig from hypothesis params (stub, may POST to `/api/v2/strategies/new`); then PATCH status to DEPLOYED
- `discardHypothesis(id)`: DELETE `/api/quant/hypotheses/{id}` with confirmation

**New Hypothesis Modal**
- Opens on button click
- Fields: Title (text, required), Description (textarea), Symbol (text), Timeframe (text), Initial Status (select: Draft, Researching, Backtesting, Validated)
- Submit: POST `/api/quant/hypotheses` with body; on success closes modal, `loadHypotheses()`

**View Switching**
- Toggle buttons switch between kanban and table layouts; saves preference in localStorage

**Event System**
- Custom event `research.hypothesis.created` dispatched; Research Lab page listens to refresh list

### API Endpoints
- `GET /api/quant/hypotheses` → list `[{id, title, description, symbol, timeframe, status, asset_class, created_at, updated_at, progress}]`
- `POST /api/quant/hypotheses` → create, returns created object
- `PATCH /api/quant/hypotheses/{id}` → update fields (status, params, etc.)
- `DELETE /api/quant/hypotheses/{id}` → discard

### Asset Class Mapping
```javascript
function _assetClass(sym) {
  const s = sym.toUpperCase();
  if (/^((E|G|A|N|C|CHF|JPY|NZD|CAD)...)/.test(s)) return "FX";
  if (/^(BTC|ETH|SOL|BNB|XRP)/.test(s)) return "Crypto";
  if (/^(AAPL|TSLA|NVDA|MSFT|GOOGL|AMZN)/.test(s)) return "Equities";
  if (/^(XAU|XAG|GOLD|SILVER)/.test(s)) return "Metals";
  if (/^(US10Y|US02Y|DXY)/.test(s)) return "Fixed Income";
  return "Other";
}
```

---

## Research Lab

**Route:** `GET /research`  
**Template:** `dashboard/templates/pages/page_research.html`

### Purpose
Interactive research notebook for hypothesis development with code execution and observation logging.

### Layout Structure (3-panel workspace, flex-1)

**Left Panel (w-64, border-r, flex-col)**
- Panel header: "Dataset Explorer" + filter icon
- Dataset list grouped by category:
  - Metals
    - XAUUSD (M15) [2.3 MB]
    - XAGUSD (M15) [1.8 MB]
  - Crypto (L2)
    - BTCUSD (M15) [4.1 MB]
    - ETHUSD (M15) [3.9 MB]
  - Equities
    - AAPL (M5) [2.0 MB]
    - TSLA (M5) [1.7 MB]
- Footer: "Import New Data" button (stub), "LOADED" badge

**Center Panel (flex-1, Notebook)**
- Tabs bar:
  - File tabs (left scrollable): dataset file names (e.g., "BTCUSD_M15_2024.csv")
  - Run All button (right)
  - Kernel status: "Python 3.11" badge
- Notebook body:
  - Code blocks with line numbers, run button (play icon) per block
  - Output blocks (stdout, matplotlib plots, Chart.js charts)
  - Markdown blocks (rendered)
- Default welcome state before dataset load
- After activating dataset: shows code blocks and outputs

**Default Notebook Content** (after selecting dataset)

**Code Block 01** — Environment Setup
```python
import numpy as np
import pandas as pd
from scipy import stats

df = sc.load_dataset("<dataset_name>", start="2023-10-01")
print(f"Loaded {len(df)} bars")
df.head()
```

**Code Block 02** — Hypothesis Generation
```python
# Compute rolling Z-score of returns
df['returns'] = df['close'].pct_change()
df['zscore'] = (df['returns'] - df['returns'].rolling(50).mean()) / df['returns'].rolling(50).std()

# Identify anomalies
anomalies = df[abs(df['zscore']) > 2.4]
print(f"Found {len(anomalies)} potential alpha signals")
```

**Markdown Block**: Pre-filled markdown template for observations

**Visualization Block**: Alpha Signal Intensity Map (12×10 grid rendered via `.renderViz()`)

**Right Panel (w-80, border-l, flex-col)**
- Header: "Key Observations"
- Observation cards list (`#obs-list`):
  - Each card: type badge (STAT_SIG, ANOMALY, etc.), timestamp, title/content, tags, confidence
- Inline entry form:
  - Type selector (`#obs-type`): STAT_SIG, ANOMALY, DATA_GAP, VOLATILITY, REGIME_SHIFT, MODEL_ALERT, CORRELATION, RISK
  - Add button (`#obs-add-btn`)
  - Notes textarea (`#obs-notes`)
- Workspace Stats (grid 2×2):
  - RAM Usage: "2.4 GB"
  - GPU Load: "0%" (mock)
  - Running Jobs: "0"
  - Notebook Runtime: "00:14:23"
- "Commit to Hypothesis" button (`#obs-commit-btn`) — creates hypothesis from observations

### JavaScript Functions

**Dataset Explorer**
- `renderDatasets()`: hardcoded `datasetMeta` object with category → array of {name, size, timeframe} entries
- `activateDataset(name)`: sets active dataset, shows notebook, adds file tab, populates code blocks with dataset-specific placeholders

**File Tabs**
- `addFileTab(filename, active=false)`: creates tab element; click switches active dataset

**Notebook Execution (Simulated)**
- Code block run buttons: `runBlock(blockEl)`; 700ms timeout, then mock output (fixed text like "stdout: Loaded 4320 bars\nmean=1.234, std=0.056")
- `outputBlock(blockId, text)`: inserts output div after code block

**Visualization**
- `renderViz()`: creates 10×14 grid of colored cells (Canvas or div grid); colors pseudo-random based on dataset name seed
- Shows "Alpha Signal Intensity Map" title above

**Observations**
- `renderObservations()`: from `mockObs` demo data; creates card elements
- `addObservation()`: POST `/api/v2/ai/chat`? (actually not implemented in snippet — likely stub or stores to local state then commits)
- `commitObservation()`: POST `/api/quant/hypotheses` with body:
  ```json
  {
    "title": dataset name,
    "description": note text from STAT_SIG observations,
    "symbol": from dataset (parsed),
    "timeframe": from dataset,
    "status": "DRAFT"
  }
  ```
  On success: dispatches `research.hypothesis.created` event, navigates to `/hypotheses` after 600ms

**Runtime Stats**
- `updateRuntimeStats()`: every 5s updates RAM/GPU/jobs/runtime (mocked values incrementing)

**Terminal Integration**
- `sendChat()`: POST `/api/v2/ai/chat`; appends to output; displays SQL if returned

### API Endpoints Used
- None directly in template for datasets (mock data used)
- Commit triggers `/api/quant/hypotheses`
- Quant Terminal chat uses `/api/v2/ai/chat`

### Dataset Metadata Structure (hardcoded in JS)
```javascript
const datasetMeta = {
  "Metals": [
    { name: "XAUUSD_M15_2024.csv", size: "2.3 MB", timeframe: "M15" },
    { name: "XAGUSD_M15_2024.csv", size: "1.8 MB", timeframe: "M15" }
  ],
  "Crypto (L2)": [
    { name: "BTCUSD_M15_2024.csv", size: "4.1 MB", timeframe: "M15" },
    { name: "ETHUSD_M15_2024.csv", size: "3.9 MB", timeframe: "M15" }
  ],
  "Equities": [
    { name: "AAPL_M5_2024.csv", size: "2.0 MB", timeframe: "M5" },
    { name: "TSLA_M5_2024.csv", size: "1.7 MB", timeframe: "M5" }
  ]
};
```

---

## Strategy Library

**Route:** `GET /strategies`  
**Template:** `dashboard/templates/pages/page_strategies.html`

### Purpose
Strategy management: view, toggle, edit parameters, copy, backtest, view evidence and performance.

### Layout Structure

**Top Actions Bar**
- "+ New Strategy" button (opens Create Strategy modal)
- Refresh button
- View toggles: Table (icon), Grid (icon), Evidence (icon)

**Stats Bar (4 columns)**
- Total: count of all strategies
- Active: `is_active=True`
- Inactive: `is_active=False`
- Deploying: status="deploying"

**Views**

### Table View (default)
Full-width responsive table with columns:
- Name (font-mono, clickable to open detail panel)
- Label (display label)
- Symbol
- Timeframe
- Status: badge (Active green, Inactive gray, Deploying amber)
- Version (integer)
- Trades (right-aligned, formatted)
- Win Rate (right, percentage)
- PF (Profit Factor, right)
- Sharpe (right)
- Max DD (right, red if >10%)
- ML: On/Off toggle
- Actions: icons (toggle, edit, copy, backtest)

### Grid View
- Cards in CSS `trading-grid` layout
- Each card shows: Name, Symbol, TF, Status badge
- Metrics row: WR, Trades, PF (3-col grid)
- Compact chart placeholder (mini equity sparkline if data available)
- Action buttons: same as table but smaller

### Evidence View
- Filter dropdown: All Strategies / My Strategies / Recently Modified
- Event log list (vertical timeline) showing backtest runs, param changes, trade executions

**Strategy Detail Panel (Slide-up Bottom)**
- Opens when strategy name clicked in table/grid
- Header: strategy name, label, active badge, twitch to regime filter dropdown, ML override toggle, Export button, Copy button
- Charts row (2 cols):
  - Equity Curve (canvas) — cumulative PnL
  - Monte Carlo (canvas) — up to 50 simulation paths (light opacity)
  - (Optional third: Monthly Returns bar chart)
- Performance Metrics (7 cols):
  - Trades count
  - Win Rate %
  - Net PnL (R) — total R multiples
  - Profit Factor
  - Sharpe Ratio
  - Max Drawdown %
  - Avg R per trade
- Trade History Table (full width, 8 cols):
  - Time (UTC), Side (color), Symbol, Entry, Exit, SL, TP, PnL (R, color)
- Backtest Results Summary (expandable accordion):
  - List of recent runs: ID, status, symbol/TF, date, metrics
- Version History (list):
  - Each entry: version number, datetime, params diff (JSON), backtest_id reference

### Modals

**Edit Params Modal**
- Shows current params in `<pre>` block (formatted JSON)
- Editable textarea: paste edited JSON
- "Save as New Version" button → `PUT /api/v2/strategies/{name}/params`
- Validation: JSON.parse() check; if invalid shows error

**Copy / New Strategy Modal**
- Name input (lowercase, underscores validated)
- Display Label input
- Create button:
  - If copying: `POST /api/v2/strategies/{name}/copy` with `{new_name, label?}`
  - If new: `POST /api/v2/strategies/new` with full strategy definition

**Backtest Results Modal**
- Lists recent backtest runs with status, symbol/TF, date
- Each expandable (details) shows params JSON snippet and equity curve JSON
- "Load" button loads that run into Backtesting Center

### JavaScript Functions

**Data Loading**
- `loadAll()`: parallel GET `/api/v2/strategies/` + `/api/v2/strategies/stats/overview`
- `loadStrategyDetail(name)`: when row clicked, fetches:
  - `GET /api/v2/strategies/{name}` (full metadata)
  - `GET /api/v2/strategies/{name}/equity` (equity curve points)
  - `GET /api/v2/strategies/{name}/monte-carlo?simulations=50` (MC curves)
  - `GET /api/v2/strategies/{name}/performance` (monthly returns + stats)
  - `GET /api/v2/strategies/{name}/trades?limit=30` (recent trades)
  - `GET /api/v2/strategies/{name}/backtests?limit=10` (run history)
  - `GET /api/v2/strategies/{name}/versions` (param version history)
  - `GET /api/v2/strategies/{name}/evidence?limit=50` (event log)

**View Switching**
- Toggle buttons: `setView('table'|'grid'|'evidence')`, re-renders main content
- Stores preference in localStorage

**Detail Panel Rendering**
- `openDetailPanel(name)`: fetches above data, populates panel, slides up (CSS transform translateY)
- `closeDetailPanel()`: hides panel
- Charts via Chart.js:
  - Equity: line chart with fill
  - Monte Carlo: multiple light lines on single chart (opacity 0.3)
  - Monthly Returns: bar chart grouped by month/year

**Actions**
- Toggle active: `POST /api/v2/strategies/{name}/toggle` → returns new `is_active`; refreshes row
- Edit Params: opens modal, pre-fills textarea with `JSON.stringify(params, null, 2)`
- Copy: opens copy modal, suggests new default name (copy of X)
- Backtest: opens modal with run history; "New Backtest" button navigates to `/backtesting-center` with strategy pre-filled

**Regime Filter & ML Override**
- Regime filter dropdown: `PUT /api/v2/strategies/{name}/regime_filter` with `{enabled, trending_threshold, ranging_threshold}`
- ML override toggle: `PUT /api/v2/strategies/{name}/ml-override` with `{enabled: bool}`

**Export**
- Export button: `GET /api/v2/strategies/{name}/export` → downloads JSON file

**Evidence View**
- `GET /api/v2/strategies/evidence?limit=50` → combined event log across all strategies
- Renders timeline: icon + timestamp + description + badge

**Auto-Refresh**
- Interval: 30000ms (30s)
- `setInterval(() => { if (detailOpen) refreshDetail(); else loadAll(); }, 30000)`

### API Endpoints (Strategy V2)
- `GET /api/v2/strategies/` → `[{name, label, symbol, timeframe, is_active, version, stats: {...}}]`
- `GET /api/v2/strategies/stats/overview` → `{total, active, inactive, deploying}`
- `GET /api/v2/strategies/{name}` → `{name, label, symbol, timeframe, params, param_bounds, is_active, version, created_at, updated_at}`
- `POST /api/v2/strategies/{name}/toggle` → `{name, is_active: bool}`
- `PUT /api/v2/strategies/{name}/params` → `{status: "ok"}`
- `POST /api/v2/strategies/{name}/copy` → `{name, label, params}` (new copy)
- `GET /api/v2/strategies/{name}/versions` → version history list
- `GET /api/v2/strategies/{name}/backtests?limit=20` → backtest runs
- `GET /api/v2/strategies/{name}/performance` → `{monthly_returns, sharpe, max_drawdown, ...}`
- `GET /api/v2/strategies/{name}/monte-carlo?simulations=50` → `{simulations, curves}`
- `GET /api/v2/strategies/{name}/trades?limit=50&offset=0` → paginated trades
- `GET /api/v2/strategies/{name}/equity` → equity curve
- `GET /api/v2/strategies/{name}/evidence?limit=50` → event log
- `PUT /api/v2/strategies/{name}/regime-filter` → `{enabled, trending_threshold, ranging_threshold}`
- `PUT /api/v2/strategies/{name}/ml-override` → `{enabled: bool}`
- `GET /api/v2/strategies/{name}/export` → JSON config download
- `POST /api/v2/strategies/new` → create new strategy
- `GET /api/v2/strategies/evidence` → combined evidence (all strategies)

### Calculations (Client-Side)
- Win Rate: `wins / total`
- Profit Factor: `gross_win / gross_loss` (if gross_loss > 0 else null)
- Sharpe and Max DD are computed server-side and returned in stats

---

## Backtesting Center

**Route:** `GET /backtesting-center` (or as documented)  
**Template:** `dashboard/templates/pages/page_backtesting_center.html`

### Purpose
Configure and run strategy backtests with parameter overrides; visualize results with charts and metrics.

### Layout Structure

**Configuration Panel (Left Sidebar, w-72, border-r, p-4)**

- Strategy Template dropdown (`#bt-strategy`) — populated from `/api/v2/backtest/strategies`
- Selected Symbol dropdown (`#bt-symbol`) — populated from `/api/v2/backtest/symbols` grouped by asset
- Timeframe select (`#bt-timeframe`): M1, M5, M15, H1, H4, D
- Execution mode select (`#bt-execution`): OHLC (default) / Every Tick
- Date Range:
  - Start date input (`#bt-start`) type=date
  - End date input (`#bt-end`) type=date
- Parameter Overrides table (`#bt-params-table`):
  - Header: Parameter, Override Value
  - Rows for each param from selected strategy's `default_params`
  - Input cell: number field bound to param key
- Reset Defaults button — clears all overrides
- RUN BACKTEST button (`#bt-run-btn`) — primary, disabled until required fields filled
- Status message area (`#bt-status`) — dynamic feedback

**Main Content (Right, flex-1, p-6)**

**Summary Metrics Row (5 tiles)**
1. Net Profit (currency)
2. Sharpe Ratio
3. Max Drawdown (percentage)
4. Profit Factor
5. Win Rate (percentage)

**Equity & Drawdown Curve** (canvas `#bt-equity-chart`, height 280px)
- Dual axis: equity (left), drawdown % (right)
- Linear/Log scale toggle buttons above chart

**Bottom Row (2 cols)**

- Left: Trade Distribution Histogram (canvas `#bt-dist-chart`, height 180px) — PnL distribution
- Right: Monthly Returns Heatmap (grid `#bt-monthly-grid`) — 12 month columns per year, colored red/green

**Run History Table** (below bottom row, full width)
- Columns: ID, Symbol, TF, Strategy, Status (badge), Trades, Win Rate, Net PnL (R), Created
- Click row → `loadRun(run_id)` to populate charts

### JavaScript Functions

**Initialization (`initBT()`)**
- Parallel GET:
  - `/api/v2/backtest/strategies`
  - `/api/v2/backtest/symbols`
  - `/api/v2/backtest/timeframes`
- Populates selects, binds change handlers

**Strategy Selection**
- `onStrategyChange()`: stores selected strategy class, sets default symbol/timeframe in form, calls `buildParamTable(cls)`
- `buildParamTable(cls)`: clears table, for each key in `cls.default_params`:
  - Row with label (humanized) + input (`type=number`, step from `param_bounds[key].step`, min/max from bounds)
  - If param is boolean, checkbox instead

**Symbol Selection**
- Populates symbol dropdown grouped by asset class (renders `<optgroup>`)

**Run Backtest**
- `runBacktest()`:
  - Validates required fields
  - Collects overrides: from each param input where value differs from default
  - POST `/api/v2/backtest/run` with body:
    ```json
    {
      "strategy": strategy_name,
      "symbol": symbol,
      "timeframe": timeframe,
      "execution": "OHLC"|"Every Tick",
      "start_date": "2024-01-01",
      "end_date": "2025-01-01",
      "params_overrides": {param: value, ...},
      "n_bars": 5000,
      "initial_equity": 10000,
      "risk_per_trade": 0.01
    }
    ```
  - Returns `{run_id, status}`
  - Starts `pollRun(run_id)`

**Polling**
- `pollRun(run_id)`: every 2s GET `/api/v2/backtest/run/{run_id}`
- While status = "running": updates progress spinner/message
- On "complete": calls `renderRunResult(run)`, adds to history table
- On "failed": shows error message

**Charts**

**Equity Chart**
- `renderEquityChart(data, scale='linear'|'log')`:
  - `data = GET /run/{id}/equity` → `{equity_curve: [equity1, ...], drawdown_curve: [dd1, ...]}`
  - Line dataset: equity curve (filled, primary color)
  - Line dataset: drawdown curve (red, right axis)
  - X-axis: bar index or date if available

**Distribution Chart**
- `renderDistChart(data)`: GET `/run/{id}/distribution?bins=30` → `{bins[], counts[], labels[]}`
- Bar chart: labels = bin labels, counts

**Monthly Heatmap**
- `renderHeatmap(data)`: GET `/run/{id}/monthly` → `{monthly: {year: {month: pnl_r}}}`
- Grid: rows = years, cols = 12 (Jan-Dec)
- Cell background: green if pnl_r > 0, red if < 0; opacity proportional to magnitude
- Tooltip: shows exact value

**History Table**
- `renderHistory(runs)`: GET `/api/v2/backtest/runs` or from poll; populates table
- Row click: `loadRun(run_id)` fetches full run + charts

**Export CSV**
- Export button downloads all results as CSV file with columns: rank, params (JSON), fitness, sharpe, pf, max_dd, trades

### API Endpoints (Backtest V2)
- `GET /api/v2/backtest/strategies` → `[{name, label, symbol, timeframe, default_params, param_bounds}]`
- `GET /api/v2/backtest/symbols` → `{groups: {asset_class: [symbols]}, pool: {symbol: {description, currency, ...}}}`
- `GET /api/v2/backtest/timeframes` → `{timeframes: ["M1","M5",...], mt5_minutes: {M1:1, M5:5, ...}}`
- `POST /api/v2/backtest/run` → `{run_id, status}`; enqueues background job
- `GET /api/v2/backtest/runs` → list of recent runs (filters: `strategy`, `status`, `limit`)
- `GET /api/v2/backtest/run/{run_id}` → full run with trades
- `GET /api/v2/backtest/run/{run_id}/equity` → `{equity_curve[], drawdown_curve[], initial_equity, final_equity, net_pnl_r}`
- `GET /api/v2/backtest/run/{run_id}/distribution?bins=30` → `{bins, counts, labels}`
- `GET /api/v2/backtest/run/{run_id}/monthly` → `{monthly: {year: {month: pnl_r}}}`
- `DELETE /api/v2/backtest/run/{run_id}` → deletes run and associated Trade records

### Backend Backtest Flow (`dashboard/v2/routes/backtest.py`)
- POST `/run` creates `BacktestRun` record (status="pending")
- Enqueues `_job(run_id)` in background (via `quant.runner.run_backtest_job`)
- Job:
  1. Sets status="running"
  2. Runs `BacktestEngine` with provided parameters
  3. Saves trades to DB with `backtest_run_id`
  4. Updates `BacktestRun` with results (`equity_curve`, `drawdown_curve`, `monthly_returns`, `final_equity`, `net_pnl_r`, etc.)
  5. Sets status="complete" or "failed"

### Notes
- Parameter overrides only include fields where user enters a value ≠ default
- Execution mode "OHLC" uses close prices only; "Every Tick" uses tick simulation (more CPU)

---

## Settings

**Route:** `GET /settings`  
**Template:** `dashboard/templates/pages/page_settings.html`

### Purpose
Platform configuration with live reloading of settings across dashboard and engine.

### Layout Structure

**Settings Form** (`#settings-form`) organized in fieldset groups:

1. **Dashboard**
   - Poll interval (ms): `<input type="number" id="cfg-dashboard-poll_interval_ms" min="1000" step="500" value="5000">`
   - Recent trades count: `<input type="number" id="cfg-dashboard-recent_trades_count" min="1" max="500" value="50">`
   - Heartbeat stale (s): `<input type="number" id="cfg-dashboard-heartbeat_stale_seconds" min="30" value="120">`

2. **Risk Management**
   - Risk per trade (fraction): `<input type="number" step="0.001" min="0.001" max="0.1" value="0.01">`
   - Max daily drawdown: `<input type="number" step="0.01" min="0.01" max="0.5" value="0.03">`
   - Max total drawdown: `<input type="number" step="0.01" min="0.05" max="0.5" value="0.10">`
   - Max open trades: `<input type="number" min="1" max="50" value="5">`
   - Max lot size: `<input type="number" step="0.1" min="0.01" value="1.0">`

3. **SL/TP Model**
   - ATR period: `<input type="number" min="1" max="200" value="14">`
   - SL mult (trending): `<input type="number" step="0.1" min="0.1" value="1.2">`
   - SL mult (ranging): `<input type="number" step="0.1" min="0.1" value="1.8">`
   - TP1 RR (trending): `<input type="number" step="0.1" min="0.1" value="1.0">`
   - TP2 RR (trending): `<input type="number" step="0.1" min="0.1" value="2.5">`

4. **AI Advisor**
   - Enabled: `<select id="cfg-ai-enabled"><option>Yes</option><option>No</option></select>`
   - Min confidence to show: `<input type="number" step="0.05" min="0" max="1" value="0.7">`
   - Cooldown (minutes): `<input type="number" min="1" max="1440" value="15">`
   - Model: `<input type="text" id="cfg-ai-model" value="claude-sonnet-4-20250514">`

**Save Button**
- "Save All Settings" — primary button at bottom
- Status message: shows "Settings saved" (success) or error

### JavaScript Functions

**Loading**
- `loadSettings()`: GET `/api/settings` on page load
- Populates each input from response by matching `id` suffix to config key path
  - Example: response `{"dashboard": {"poll_interval_ms": 5000}}` → `cfg-dashboard-poll_interval_ms` value = 5000

**Saving**
- `saveSettings()` triggered by Save button:
  - Collects all input values
  - Coerces numbers: for `type=number` inputs, uses `parseFloat` or `parseInt` based on `step` attribute
  - AI enabled: converts "Yes"/"No" to boolean
  - POST `/api/settings` with full settings object (all fields, not just changed ones)
  - On success: shows green status message "Settings saved"
  - On error: shows red error message

**Realtime Updates**
- After save, POSTs to `/api/v2/ai/config` if AI settings changed (cooldown, confidence) to update runtime
- Dashboard poll interval updates immediately in other pages if they read from `window.config`

### API Endpoints
- `GET /api/settings` → effective settings dict:
  ```json
  {
    "dashboard": {"poll_interval_ms": 5000, "recent_trades_count": 50, "heartbeat_stale_seconds": 120},
    "risk": {"risk_per_trade": 0.01, "max_daily_drawdown": 0.03, "max_total_drawdown": 0.10, "max_open_trades": 5, "max_lot_size": 1.0},
    "sltp": {"atr_period": 14, "sl_atr_mult_trending": 1.2, "sl_atr_mult_ranging": 1.8, "tp1_rr_trending": 1.0, "tp2_rr_trending": 2.5},
    "ai": {"enabled": true, "min_confidence_to_show": 0.7, "cooldown_minutes": 15, "model": "claude-sonnet-4-20250514"}
  }
  ```
- `POST /api/settings` — expects full settings object; updates `PlatformSetting` table (or env vars for non-overrideable). Returns `{"status": "saved"}` or error.

### Settings Override Chain
1. Defaults in `config/settings.py`
2. Environment variables (loaded at startup via `PlatformConfig.from_env()`)
3. DB `platform_settings` table (queried by `SettingsService.get_effective_*()`)
4. Settings page writes to DB; takes effect immediately across all pages after save (next API call uses new values)

---

## API Reference — V1 Endpoints

**Base path:** `/api/*` (from `dashboard/app.py` and `dashboard/routes/*.py`)

### Authentication
All V1 endpoints require JWT except:
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /login` (HTML page)

Header: `Authorization: Bearer {access_token}`

### Account
- `GET /api/account/stats`
  - Returns: latest `AccountSnapshot` dict (equity, balance, margin, realized_pnl, unrealized_pnl, timestamps)
- `GET /api/account/snapshots?limit=200`
  - Returns: array of `AccountSnapshot` sorted descending (newest first)
  - Query: `limit` (default 200)
- `GET /api/mt5/account`
  - Returns: MT5 account info dict (login, server, balance, equity, margin, etc.) or 404 on disconnect
- `GET /api/mt5/positions`
  - Returns: list of open positions
- `GET /api/mt5/orders`
  - Returns: list of pending orders

### Trades
- `GET /api/trades/recent?limit=50`
  - Returns: list[Trade] most recent trades (ordered by `opened_at` desc)
  - Query: `limit` (int, default 50)

### Strategies
- `GET /api/strategies`
  - Returns: list[`StrategyConfig`] (name, label, symbol, timeframe, is_active, params, version)
- `GET /api/strategies/library`
  - Returns: enriched strategy list with trade metrics computed from `Trade` table
  - Fields added: `win_rate`, `avg_pnl_r`, `net_pnl_r`, `profit_factor`, `max_drawdown`, `sharpe`, `total_trades`
- `POST /api/strategies/{name}/toggle`
  - Toggles `StrategyConfig.is_active` via `StrategyRegistry.toggle()`
  - Returns: `{name, is_active: bool}`
- `POST /api/strategies/{name}/deploy`
  - Queues strategy deployment to engine (sets `needs_deploy=True` flag)
  - Returns: `{status: "deploying"}`

### Quant
- `GET /api/quant/hypotheses`
  - Returns: list[Hypothesis] with fields `id, title, description, symbol, timeframe, status, asset_class, created_at, updated_at, progress`
- `POST /api/quant/hypotheses`
  - Body: `{title, description?, symbol?, timeframe?, status?}`
  - Returns: created Hypothesis object
- `PATCH /api/quant/hypotheses/{id}`
  - Body: partial fields to update (e.g., `{status: "BACKTESTING"}`)
- `DELETE /api/quant/hypotheses/{id}`
  - Discards hypothesis
- `POST /api/quant/backtests`
  - Creates `BacktestRun` with status="pending"
  - Body: `{strategy, symbol, timeframe, start_date?, end_date?, params_overrides?}`
  - Returns: `{run_id}`
- `GET /api/quant/backtests`
  - Returns: list of all backtest runs (recent first)
- `POST /api/quant/optimise`
  - Creates `OptimisationRun` and spawns background thread
  - Body: `{strategy, symbol, timeframe, param_bounds, search_method, fitness_metric, n_iterations}`
  - Returns: `{run_id}`
- `GET /api/quant/optimise`
  - Returns: list of optimisation runs (limited)
- `GET /api/quant/optimise/{run_id}`
  - Returns: full run with `best_params`, `best_score`, `heatmap_data`, `top_n_results`
- `PUT /api/quant/optimise/{run_id}/deploy`
  - Applies `best_params` to `StrategyConfig` for that strategy

### Data
- `GET /api/data/datasets`
  - Returns: `{assets: {asset_class: [symbols]}, bar_counts: {symbol|timeframe: count}}`
- `GET /api/data/datasets/{symbol}/ohlcv?timeframe=M15&limit=300`
  - Returns: OHLCV data for symbol + timeframe

### Transcription (Journal)
- `GET /api/transcription/history`
  - Returns: list of `TradeAnnotation` with `{id, trade_id, note, tag, created_at}`

### Settings
- `GET /api/settings` → effective settings (config + DB overrides)
- `POST /api/settings` → update settings (body: full settings dict)

### MT5 (Legacy)
- `GET /api/mt5/connection` → `{connected: bool, login?, server?, latency_ms?}`

### Engine Controls
- `GET /api/v2/engine-controls/logs?tail=200`
  - Returns: `{logs: ["line1", "line2", ...]}`
- `GET /api/v2/engine-controls/history?limit=200`
  - Returns: recent `AccountSnapshot` list
- `GET /api/v2/engine-controls/active-strategies`
  - Returns: list of active strategy names (`StrategyConfig.is_active=True`)

---

## API Reference — V2 Endpoints

**Base path:** `/api/v2/`

### Health & Config
- `GET /health` → `{"status": "ok", "version": "2.0.0"}`
- `GET /config/public` → non-sensitive config for frontend (engine, dashboard, mt5, risk sections)

### AI (`/api/v2/ai/`)
- `GET /suggestions?limit=50` → `{suggestions: [{id, symbol, timeframe, side, confidence, reasoning, market_context, entry, sl, tp1, tp2, created_at}], total_signals, accuracy_pct, avg_alpha, stats}`
- `GET /heatmap` → `{assets: [{symbol, score, signal_count, direction, is_demo}], is_demo, note?}`
- `GET /reasoning/{symbol}` → `{symbol, direction, confidence, market_context, alpha_factors: [{name, value}], risk_bullets: [{icon, text}], model_version, is_demo}`
- `POST /chat` → body `{query, context?}` → `{answer, sql?}`
- `POST /toggle` → `{name: "ai_trading", is_active: bool}` (creates strategy if missing)
- `GET /config` → `{is_enabled, provider, model, min_confidence_to_show, cooldown_minutes, max_tokens, strategy_active, strategy_params}`
- `PUT /config` → body partial AI config (cooldown_minutes, min_confidence_to_show, symbols, timeframe, min_confidence)
- `POST /generate` → body `{symbols[], timeframe}` → `{generated, symbols, timeframe}`

### Accounts (`/api/v2/accounts/`)
- `GET /` → list `[{account_id, broker, server, status, equity, balance, margin, positions, weight, ...}]`
- `GET /summary` → `{total_equity, total_balance, total_free_margin, total_positions}`
- `GET /health` → per-account health items dict
- `GET /{account_id}` → single account detail
- `GET /{account_id}/positions` → positions for account
- `POST /` → create account (body: account_name, broker, account_type, server, mt5_login, password_enc, investor_password_enc?, weight?, notes?, colour?)
- `PATCH /{account_id}` → update mutable fields (display_name?, weight?, notes?, colour?)
- `DELETE /{account_id}` → delete
- `POST /{account_id}/action` → body `{action, value?}` where action ∈ {connect, disconnect, pause, set_weight, rename, close_all_positions, test_connection}
- `POST /bulk/disconnect-all` → disconnect all
- `POST /bulk/close-all` → queue close-all for all connected

### Backtest (`/api/v2/backtest/`)
- `GET /strategies` → `[{name, label, symbol, timeframe, default_params, param_bounds}]`
- `GET /symbols` → `{groups: {}, pool: {}}`
- `GET /timeframes` → `{timeframes: [], mt5_minutes: {}}`
- `POST /run` → `{run_id, status}`; body includes strategy, symbol, timeframe, execution, start_date, end_date, params_overrides, n_bars, initial_equity, risk_per_trade, warmup_bars
- `GET /runs?strategy=&status=&limit=` → list
- `GET /run/{run_id}` → full run with trades
- `GET /run/{run_id}/equity` → `{equity_curve[], drawdown_curve[], initial_equity, final_equity, net_pnl_r}`
- `GET /run/{run_id}/distribution?bins=30` → histogram data
- `GET /run/{run_id}/monthly` → `{monthly: {year: {month: pnl_r}}}`
- `DELETE /run/{run_id}` → delete

### Strategies (`/api/v2/strategies/`)
- `GET /` → enriched list with stats
- `GET /stats/overview` → `{total, active, inactive, deploying}`
- `GET /{name}` → detail
- `POST /{name}/toggle` → `{name, is_active}`
- `PUT /{name}/params` → body `{params: {...}}`
- `POST /{name}/copy` → body `{new_name, label?}` → `{name, label, params}`
- `GET /{name}/versions` → version history
- `GET /{name}/backtests?limit=20` → backtest runs
- `GET /{name}/performance` → `{monthly_returns, sharpe, max_drawdown, ...}`
- `GET /{name}/monte-carlo?simulations=50` → `{simulations, curves}`
- `GET /{name}/trades?limit=50&offset=0` → paginated trades
- `GET /{name}/equity` → equity curve
- `GET /{name}/evidence?limit=50` → event log
- `PUT /{name}/regime-filter` → body dict (enabled, thresholds)
- `PUT /{name}/ml-override` → body `{enabled: bool}`
- `GET /{name}/export` → JSON config download
- `POST /new` → body `{name, label?, symbol?, timeframe?, params?}`
- `GET /evidence?limit=50` → combined evidence

### ML (`/api/v2/ml/`)
- `GET /models?symbol=&timeframe=` → list
- `POST /train` → body `{symbol, timeframe, model_type, model_name, params?}` → `{status, model_id}`
- `GET /models/{model_id}` → detail
- `DELETE /models/{model_id}` → delete model + artifact
- `POST /models/{model_id}/deploy` → toggles `is_active`, creates StrategyConfig if needed
- `POST /predict` → body `{model_id}` → `{symbol, timeframe, model_name, prediction: {direction, confidence, probability}}`
- `GET /models/{model_id}/features` → `{features: [{name, importance}]}`
- `POST /retrain/{model_id}` → creates new model from existing params
- `GET /history?symbol=&model_id=&limit=100` → prediction history

### Monitoring (MT5) (`/api/v2/`)
Enhanced MT5 endpoints:
- `GET /mt5/account` → account info or error
- `GET /mt5/accounts` → configured accounts list
- `GET /mt5/positions?symbol=` → open positions
- `GET /mt5/orders?symbol=` → pending orders
- `GET /mt5/connection` → `{connected, login, server}`

### Journal (`/api/v2/journal/`)
- `GET /annotations?trade_id=` → list (filter by trade_id if provided)
- `GET /annotations/{annotation_id}` → single
- `POST /annotations` → body `{note, trade_id?, tag?}`
- `PUT /annotations/{annotation_id}` → body `{note?, tag?, trade_id?}`
- `DELETE /annotations/{annotation_id}` → delete

---

## Appendix: Database Models Referenced

### Trade
Fields: id, symbol, side (BUY/SELL), entry, exit, sl, tp, volume, profit, pnl_r, commission, swap, opened_at, closed_at, strategy_name, backtest_run_id, source ("live"|"backtest"|"ai"), tags[], notes

### AccountSnapshot
Fields: id, timestamp, equity, balance, margin, realized_pnl, unrealized_pnl, floating_pnl, margin_level, free_margin

### StrategyConfig
Fields: name, label, symbol, timeframe, is_active, params (JSON), version, created_at, updated_at, deployed_at

### AIAdvisorSuggestion
Fields: id, symbol, timeframe, side, confidence, reasoning, market_context (JSON: entry, sl, tp1, tp2), created_at

### OptimisationRun
Fields: id, strategy, symbol, timeframe, param_bounds (JSON), search_method, fitness_metric, n_iterations, status, created_at, started_at, completed_at, best_params (JSON), best_score, heatmap_data (JSON), top_n_results (JSON), error_message

### BacktestRun
Fields: id, strategy, symbol, timeframe, start_date, end_date, params_overrides (JSON), status, created_at, completed_at, initial_equity, final_equity, net_pnl_r, equity_curve (JSON array), drawdown_curve (JSON array), monthly_returns (JSON), trades (relationship)

---

## End of Documentation

Document compiled from all source files as of 2025-06-15.
Total pages documented: 15
Total API endpoints documented: 100+