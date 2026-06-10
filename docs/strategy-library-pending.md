# Strategy Library — Pending Work (vs Stitch Screenshot)

> Reference: `dashscreens/stitch_savanna_quant_os/strategy_library/screen.png`
>
> This file lists every feature visible in the stitch reference that is **missing or incomplete** in the current implementation (`dashboard/templates/pages/page_strategies.html` + `dashboard/v2/routes/strategies.py`).
>
> Items are ordered as they appear top-to-bottom in the screenshot.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ❌ | Missing — no HTML element, no JS handler, no backend endpoint |
| ⚠️ | Partial — element exists but incomplete / not wired |
| 🔌 | Backend endpoint exists but frontend does not call it |

---

## 1. Top Action Bar

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1.1 | **"Deploy Strategy" button** | ❌ | Screenshot shows a "Deploy Strategy" button left of "+ New Strategy". Current top bar only has "+ New Strategy" + "Refresh". No deploy button, no deploy modal. |
| 1.2 | **"+ New Strategy" button** | ✅ | Present and wired to `openNewModal()` → `POST /api/v2/strategies/new`. |
| 1.3 | **Tab switcher (Table / Grid / Evidence)** | ✅ | Present and functional. |

---

## 2. Stats Bar

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 2.1 | **Total count** | ✅ | Card present, polls `/api/v2/strategies/stats/overview`. |
| 2.2 | **Active count** | ✅ | Card present, green coloured. |
| 2.3 | **Inactive count** | ✅ | Card present. |
| 2.4 | **Deploying count** | ✅ | Card present (amber), counts `BacktestRun.status="running"`. Note: this is a heuristic — no real deploy pipeline exists yet. |

---

## 3. Main Table

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 3.1 | **Name column** | ✅ | Clickable, opens detail panel. |
| 3.2 | **Symbol column** | ✅ | Populated from `cls.meta.default_symbol`. |
| 3.3 | **Timeframe column** | ✅ | Populated from `cls.meta.typical_timeframes[0]`. |
| 3.4 | **Status column (Active/Inactive badge)** | ✅ | Badge styled, toggle button in Actions. |
| 3.5 | **Version column** | ✅ | Shows `v{N}`, increments on param update. |
| 3.6 | **"Deploy" button per row** | ❌ | Screenshot shows a "Deploy" button in each row (in the Version column area or adjacent). Current table has Activate/Deactivate/Edit/Copy/BT — no Deploy button. v1 has `POST /api/strategies/{name}/deploy` but it is not called from the strategies page. |
| 3.7 | **"Actions" dropdown (not flat buttons)** | ❌ | Screenshot shows a single "Actions" dropdown per row containing: Edit, Clone (duplicate), View Backtests, **Delete**. Current implementation shows 4 flat buttons (Activate/Deactivate, Edit, Copy, BT) — not a dropdown. No Delete option anywhere. |
| 3.8 | **Column sorting** | ❌ | No click-to-sort on any column header. All columns are fixed-order. |
| 3.9 | **Search / filter input** | ❌ | No search box above the table to filter by name, symbol, or status. |
| 3.10 | **Execution Behaviour column/dropdown** | ❌ | Screenshot shows an "Execution Behaviour" selector (Market / Limit / Stop). Not present in table or detail panel. 🔌 No backend endpoint stores this. |
| 3.11 | **Backtest results bar (PF / Sharpe / Max DD) per row** | ❌ | Screenshot shows a result bar under each strategy row showing Profit Factor, Sharpe, Max DD as inline metrics. Currently these are only visible inside the detail panel, not in the table. |

---

## 4. Detail Panel (extends from bottom)

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 4.1 | **Strategy name + label + badge** | ✅ | Sticky top bar shows name, label, Active/Inactive badge. |
| 4.2 | **Close button** | ✅ | × button closes panel. |
| 4.3 | **Regime filter section (collapsible)** | ⚠️ | Dropdown exists (All/Trending/Ranging/Volatile) and saves to DB via `PUT /regime-filter`. **Not collapsible** — it's always visible as a flat control bar. Screenshot shows it as a titled, collapsible section "Regime Filter: Ranging" with a slider/indicator. |
| 4.4 | **ML Signals section (collapsible)** | ⚠️ | Toggle button exists (On/Off) and saves via `PUT /ml-override`. **Not collapsible** — always visible as flat button. Screenshot shows a titled section "ML Signals: Disabled" with a dropdown (Disabled / Filter / Override). Current implementation only has binary On/Off, no three-state selector. |
| 4.5 | **Execution Behaviour section (collapsible)** | ❌ | Not present in detail panel at all. Screenshot shows "Execution Behaviour: Market" with a dropdown (Market / Limit / Stop). 🔌 No backend endpoint. |
| 4.6 | **Performance section (collapsible)** | ⚠️ | Metrics strip (7 cards) and Monthly Returns chart exist. **Not collapsible** — always visible. Screenshot shows this as a titled collapsible section. |
| 4.7 | **Equity Curve chart** | ✅ | Present, loads from `/equity`. |
| 4.8 | **Monte Carlo chart** | ✅ | Present, loads from `/monte-carlo`. |
| 4.9 | **Profit Factor display** | ⚠️ | Shown as a metric card in the detail panel. Screenshot shows a dedicated **"Profit Factor: 1.86"** section. |
| 4.10 | **Sharpe Ratio display** | ⚠️ | Shown as a metric card. Screenshot shows **"Sharpe: 1.55"** as a distinct section element. |
| 4.11 | **Max Drawdown display** | ⚠️ | Shown as a metric card. Screenshot shows **"Max Drawdown: -24.37%"** as a distinct section. |
| 4.12 | **Trade History section (collapsible)** | ⚠️ | Table of 30 trades present. **Not collapsible** — always visible. Screenshot shows this as a titled, collapsible section with a table of Time, Side, Entry, Exit, SL, TP, PnL. |
| 4.13 | **Backtest Results section (collapsible)** | ⚠️ | Runs list + modal present. **Not collapsible** — always visible. |
| 4.14 | **Version History section (collapsible)** | ⚠️ | Versions list present. **Not collapsible** — always visible. |

---

## 5. Collapsible Section Pattern

The screenshot shows every section in the detail panel as a **collapsible accordion item** with:
- A header bar showing the section title + current value (e.g. "Regime Filter: Ranging", "ML Signals: Disabled", "Performance", "Trade History")
- A chevron/arrow icon indicating expand/collapse state
- Content hidden when collapsed

**Current state:** All sections are always-expanded divs with border separators. No collapse/expand logic exists.

This is a structural change affecting sections 4.3 through 4.14. Every "⚠️ Not collapsible" item above shares this root cause.

---

## 6. Table Row Expansion

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 6.1 | **Inline row expansion** | ❌ | Screenshot shows clicking a strategy row expands it in-place to reveal the backtest results bar (PF / Sharpe / Max DD) directly under that row, without opening a separate detail panel overlay. Current implementation opens a full-screen detail panel overlay instead. |

---

## 7. Modals

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 7.1 | **Edit Params modal** | ✅ | Present, loads params, saves via `PUT /params`. |
| 7.2 | **Copy / New Strategy modal** | ✅ | Present, creates via `POST /copy` or `POST /new`. |
| 7.3 | **Backtest Results modal** | ✅ | Present, loads runs from `/backtests`. |
| 7.4 | **"Save as New" / "Commit Changes" / "Discard" workflow** | ❌ | Screenshot shows a param editing workflow with three buttons: "Save as New" (creates a new version), "Commit Changes" (applies to active), "Discard" (reverts). Current modal only has "Save as New Version" — no Commit or Discard. No drafts/preview system. |
| 7.5 | **Delete confirmation modal** | ❌ | No delete functionality anywhere. |

---

## 8. Evidence / History Log (Evidence Tab)

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 8.1 | **Evidence tab with log** | ✅ | Present, shows events from `/evidence`. |
| 8.2 | **Per-strategy filter dropdown** | ✅ | Present, populates from strategy list. |
| 8.3 | **Event icons (backtest / trade)** | ✅ | Material icons, coloured by type. |
| 8.4 | **PnL display on trade events** | ✅ | Green/red coloured R-multiple. |
| 8.5 | **Status badges on backtest events** | ✅ | Coloured by status. |
| 8.6 | **Timestamp display** | ✅ | Formatted date+time. |

---

## 9. Chart Layout

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 9.1 | **Equity Curve chart** | ✅ | Chart.js line chart, blue fill. |
| 9.2 | **Monte Carlo chart** | ✅ | 20 simulation lines, multi-coloured. |
| 9.3 | **Monthly Returns bar chart** | ✅ | Bar chart, green/red per month. |
| 9.4 | **Drawdown-over-time chart** | ❌ | No dedicated drawdown chart. Max DD is shown as a single number only. |
| 9.5 | **Chart sizing** | ⚠️ | Equity and MC charts are 180px tall, monthly is 100px. Screenshot shows larger chart areas (probably ~250-300px). |

---

## 10. Backend Endpoints Not Yet Called From Frontend

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/v2/strategies/{name}/export` | GET | 🔌 | Endpoint exists, frontend calls it for download. |
| `/api/v2/strategies/{name}/equity` | GET | 🔌 | Called by detail panel. |
| `/api/v2/strategies/{name}/monte-carlo` | GET | 🔌 | Called by detail panel. |
| `/api/v2/strategies/{name}/performance` | GET | 🔌 | Called by detail panel (monthly). |
| `/api/v2/strategies/{name}/trades` | GET | 🔌 | Called by detail panel. |
| `/api/v2/strategies/{name}/versions` | GET | 🔌 | Called by detail panel. |
| `/api/v2/strategies/{name}/backtests` | GET | 🔌 | Called by detail panel + modal. |
| `/api/v2/strategies/{name}/regime-filter` | PUT | 🔌 | Called by regime dropdown. |
| `/api/v2/strategies/{name}/ml-override` | PUT | 🔌 | Called by ML toggle. |
| `/api/v2/strategies/{name}/copy` | POST | 🔌 | Called by copy modal. |
| `/api/v2/strategies/{name}/params` | PUT | 🔌 | Called by edit modal. |
| `/api/v2/strategies/{name}/toggle` | POST | 🔌 | Called by activate/deactivate. |
| `/api/v2/strategies/new` | POST | 🔌 | Called by new strategy modal. |
| `/api/v2/strategies/evidence` | GET | 🔌 | Called by evidence tab. |
| `/api/v2/strategies/stats/overview` | GET | 🔌 | Called by stats bar. |
| `/api/v2/strategies/` | GET | 🔌 | Called on page load. |
| `/api/v2/strategies/{name}/deploy` | *(not used)* | ❌ | No frontend calls this. v1 endpoint exists at `/api/strategies/{name}/deploy` but nothing on the page triggers it. |

---

## 11. Summary — Prioritised Gap List

### Critical (visible in screenshot, core UX)

1. **Deploy Strategy button** (1.1) — top bar button + per-row Deploy button (3.6)
2. **Actions dropdown** (3.7) — replace flat buttons with dropdown containing Edit / Clone / View Backtests / Delete
3. **Collapsible sections in detail panel** (4.3–4.14, 5) — refactor all detail sections to accordion pattern
4. **Execution Behaviour selector** (3.10, 4.5) — dropdown in table + detail panel
5. **Commit Changes / Discard workflow** (7.4) — replace "Save as New Version" with full param lifecycle

### Important (visible in screenshot, secondary UX)

6. **Inline row expansion** (6.1) — expand strategy row in-place to show PF/Sharpe/Max DD bar
7. **Search / filter** (3.9) — text input above table
8. **Column sorting** (3.8) — click column headers to sort
9. **Delete strategy** (3.7, 7.5) — add to Actions dropdown + confirm modal + `DELETE` endpoint
10. **ML Signals three-state selector** (4.4) — Disabled / Filter / Override instead of binary On/Off

### Nice to have (enhancement)

11. **Larger chart heights** (9.5) — match screenshot proportions
12. **Drawdown-over-time chart** (9.4) — dedicated drawdown chart in detail panel
13. **Backtest results bar in table row** (3.11) — inline PF/Sharpe/Max DD under each strategy row (before inline expansion)

### Backend gaps

14. **Execution Behaviour storage** — no DB column or endpoint for Market/Limit/Stop per strategy
15. **Delete endpoint** — `DELETE /api/v2/strategies/{name}` does not exist
16. **Real deploy pipeline** — "Deploying" count is a heuristic; no actual deploy queue

---

## File References

| File | Current state |
|------|--------------|
| `dashboard/templates/pages/page_strategies.html` | 819 lines — table, grid, evidence views; detail panel overlay; 3 modals |
| `dashboard/v2/routes/strategies.py` | 498 lines — 17 endpoints (16 strategy + 1 evidence-all) |
| `dashboard/v2/app.py` | Strategies router registered |
| `dashboard/app.py` | Toggle bug fixed (`is_active`) |
| `docs/strategy-library-plan.md` | Original implementation plan |
