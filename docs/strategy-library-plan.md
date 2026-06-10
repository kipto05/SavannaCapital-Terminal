# Strategy Library — Implementation Plan

## Reference: Stitch Screenshot (`strategy_library/screen.png`)

## Current State

| Exists | Missing |
|---|---|
| `/strategies` page → `page_strategies.html` | Stats bar (4 metrics at top) |
| `/api/strategies` → list all `StrategyConfig` | Tab switcher (Table / Grid / Evidence) |
| `/api/strategies/library` → enriched list | Copy Strategy button + endpoint |
| `/api/strategies/{name}/toggle` → **HAS BUG** | Edit Params modal + endpoint |
| `strategies/registry.py` → DB-backed registry | View Backtests eye icon → link |
| 7 strategy classes registered | Duplicate strategy endpoint |
| Version badge shown as string | Save as New / Commit Changes / Discard buttons |
| | Export strategy config endpoint |
| | Monte Carlo chart + endpoint |
| | Equity curve chart + endpoint |
| | Regime filter slider + endpoint |
| | ML signals toggle + endpoint |
| | Execution behaviour dropdown + endpoint |
| | Trade history table + endpoint |
| | Evidence log (deploy, performance, regime) + endpoint |
| | Backtest results bar (Profit Factor, Sharpe, Max DD) |

---

## Button / Feature Map

| UI Element | Current State | Required Action |
|---|---|---|
| Stats bar (4 metrics) | None | New endpoint + JS |
| Tab switcher (Table / Grid / Evidence) | None | Frontend (show/hide) |
| "Copy Strategy" button | None | New endpoint |
| Strategy table columns | Partial | Enrich with stats, add sort |
| Toggle Active/Inactive | Has endpoint, **broken** | Fix bug + frontend |
| "New Strategy" button | None | New endpoint + modal |
| "Edit Params" pencil icon | None | New endpoint + modal |
| "View Backtests" eye icon | None | Link to /backtest pre-filtered |
| "Duplicate" copy icon | None | New endpoint |
| Version badge | Partial (string) | Add versioning endpoints |
| Backtest results bar | None | New endpoints |
| Monte Carlo chart | None | New endpoint + chart |
| Regime filter slider | None | New endpoint + frontend |
| ML signals toggle | None | New endpoint + frontend |
| Execution behaviour dropdown | None | New endpoint |
| Trade history table | None | New endpoint |
| Equity curve | None | New endpoint + chart |
| Evidence log | None | New endpoint |
| "Save as New" button | None | New endpoint |
| "Commit Changes" / "Discard" | None | Frontend only |
| Export strategy config | None | New endpoint |

---

## Implementation Phases

### Phase 1: Fix Critical Toggle Bug ⚠️ PRE-REQUISITE
- **File**: `dashboard/app.py`
- **Change**: Line 272 — `rec.is_enabled` → `rec.is_active`
- **Time**: 2 minutes

### Phase 2: New v2 Strategy Routes
- **File**: `dashboard/v2/routes/strategies.py` (CREATE)
- **Register**: in `dashboard/v2/app.py`

Endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v2/strategies` | GET | Enriched list (existing + regime + ml flags) |
| `/api/v2/strategies/stats/overview` | GET | 4-metric stats bar |
| `/api/v2/strategies/{name}/toggle` | POST | Fix + return full state |
| `/api/v2/strategies/{name}/params` | PUT | Update parameters |
| `/api/v2/strategies/{name}/copy` | POST | Duplicate strategy config |
| `/api/v2/strategies/{name}/versions` | GET | Version history |
| `/api/v2/strategies/{name}/backtests` | GET | Backtest results for this strategy |
| `/api/v2/strategies/{name}/performance` | GET | Win rate, profit factor, Sharpe, max DD |
| `/api/v2/strategies/{name}/monte-carlo` | GET | Simulated equity curves (JSON) |
| `/api/v2/strategies/{name}/trades` | GET | Trade history (paginated) |
| `/api/v2/strategies/{name}/equity` | GET | Equity curve data for chart |
| `/api/v2/strategies/{name}/evidence` | GET | Event log (deploys, param changes) |
| `/api/v2/strategies/{name}/regime-filter` | PUT | Set regime filter |
| `/api/v2/strategies/{name}/ml-override` | PUT | Toggle ML signal override |
| `/api/v2/strategies/{name}/export` | GET | Export config as JSON |
| `/api/v2/strategies/new` | POST | Create new strategy record |

### Phase 3: Frontend Enhancements
- **File**: `dashboard/templates/pages/page_strategies.html` (REWRITE)

Features:
1. Stats bar — 4 metric cards, poll v2 overview endpoint
2. Tab switcher — Table / Grid / Evidence
3. Table enhancements — Regime, ML Override, Version columns; wire all buttons
4. Modal forms — Edit Params, Copy Strategy, New Strategy
5. Charts — Monte Carlo (Chart.js line), Equity Curve (Chart.js line)
6. Sliders/toggles — Regime filter, ML override
7. Evidence log — Collapsible event panel
8. All buttons wired via `window.apiFetch`

---

## Files Changed

| File | Action |
|---|---|
| `dashboard/app.py` | Fix 1-line bug |
| `dashboard/v2/routes/strategies.py` | CREATE — all new endpoints |
| `dashboard/v2/app.py` | Add strategies router |
| `dashboard/templates/pages/page_strategies.html` | REWRITE with full UI |

---

## Timing Estimate

| Phase | Time |
|---|---|
| Phase 1 — Bug fix | 2 min |
| Phase 2 — v2 routes | ~30 min |
| Phase 3 — Frontend | ~40 min |
| **Total** | **~1 hour** |
