# Optimization Hub — Build Plan

## Source of truth
- UI reference: `dashscreens/stitch_savanna_quant_os/optimization_hub/code.html`
- Existing backend: `db/models.py` (`BacktestRun`, `StrategyConfig`, `Trade`)
- Existing page scaffold: `dashboard/templates/pages/page_optimization.html`
- Existing API: `dashboard/app.py` → `/api/quant/backtests` (list/create)

## What the reference HTML shows (4 user-visible sections)

### Section A — Left Sidebar (Optimization Settings)
1. **Strategy select** — pick from `StrategyConfig` rows in DB
2. **Parameter bounds grid** — min / max / step for each tunable parameter of the selected strategy
   - currently shows 2 params (Lookback Period, Entry Threshold) as static examples
   - in production, bounds come from `StrategyConfig.param_bounds` column
3. **Fitness function radio** — choose optimisation objective (Sharpe / Calmar / Net Profit)
4. **Start Optimiser button** — dispatches to backend

### Section B — Main Top (Parameter Surface Heatmap)
1. 2-D heatmap grid showing fitness metric across two parameters
2. Currently hard-coded placeholder cells
3. Legend with min→best gradient
4. Axis labels (param X vs param Y)

### Section C — Main Bottom Left (Top Parameter Sets)
1. Ranked table of best parameter combinations found
2. Columns: Rank, Params (as badge chips), Sharpe, Profit Factor, Max DD, Action (Load)
3. "Export CSV" button at top

### Section D — Main Bottom Right (Optimization History)
1. Scrollable list of previous optimisation runs
2. Each item: status icon, strategy name, date, iteration count / search method, best Sharpe, chevron
3. Click drills into detail (future)

---

## Data model — new table: `OptimisationRun`

Add to `db/models.py`. Columns:

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | auto-increment |
| label | String(128) | user-supplied name |
| strategy_name | String(64) | FK to `StrategyConfig.name` |
| symbol | String(32) | |
| timeframe | String(8) | |
| search_method | String(32) | "grid", "random", "bayesian" |
| fitness_metric | String(32) | "sharpe", "calmar", "net_profit" |
| status | String(16) | pending → running → complete / failed |
| n_iterations | Integer | |
| best_params | JSON | winning param dict |
| best_score | Float | fitness value |
| heatmap_data | JSON | list of `{x,y,score}` for heatmap |
| top_n_results | JSON | top-N ranked results for table |
| error_message | Text | when status=failed |
| created_at | DateTime | |
| started_at | DateTime | nullable |
| completed_at | DateTime | nullable |

Alembic migration required.

---

## Backend API endpoints

All new endpoints appended to `dashboard/app.py` after the existing `/api/quant/backtests` block.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/quant/optimise` | JWT | Submit an optimisation job. Returns run ID immediately. Runs in background thread. |
| GET  | `/api/quant/optimise` | JWT | List all optimisation runs (most recent first). |
| GET  | `/api/quant/optimise/{run_id}` | JWT | Get one run by ID (includes heatmap + top results). |
| PATCH | `/api/quant/optimise/{run_id}/deploy` | JWT | Load winning params into `StrategyConfig` (update row). |

### POST `/api/quant/optimise` request body

```json
{
  "strategy_name": "momentum_reversion",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "search_method": "grid",
  "fitness_metric": "sharpe",
  "param_overrides": { "lookback_min": 10, "lookback_max": 50, "lookback_step": 5 }
}
```

If `param_overrides` is omitted, server reads `StrategyConfig.param_bounds`.

### Background thread behaviour

1. Create `OptimisationRun` with `status=pending`.
2. Update `status=running`, set `started_at`.
3. Call `quant.optimiser.run(...)` (new module, see below).
4. On completion, write `best_params`, `best_score`, `heatmap_data`, `top_n_results`, `status=complete`, `completed_at`.
5. On failure, `status=failed`, populate `error_message`.

---

## New module: `quant/optimiser.py`

### Public API

```python
def run(
    strategy_name: str,
    symbol: str,
    timeframe: str,
    param_bounds: dict[str, dict],  # {param: {min,max,step}}
    search_method: str,            # "grid" | "random" | "bayesian"
    fitness_metric: str,           # "sharpe" | "calmar" | "net_profit"
    n_iterations: int = 200,
    db_session: Session | None = None,
) -> dict:
    """
    Run optimisation. Returns:
    {
        "best_params": dict,
        "best_score": float,
        "heatmap_data": [{"p1":val,"p2":val,"score":val}, ...],
        "top_n_results": [{"params":dict,"score":float}, ...],
        "n_iterations": int,
    }
    """
```

### Algorithm selection

| Method | When used | Notes |
|--------|-----------|-------|
| Grid | `n_params <= 2` | Cartesian product of all min/max/step combos — exhaustive |
| Random | `n_params > 2` | Random sample of `n_iterations` points |
| Bayesian | opt-in | scikit-optimize `gp_minimize`; fall back to random if skopt missing |

### Fitness computation — delegates to the backtest engine

```python
from quant.backtest_engine import BacktestEngine
engine = BacktestEngine(...)
result = engine.run(strategy_name, symbol, timeframe, params)
score = _score(result, fitness_metric)
```

Scoring:

| Metric | Formula |
|--------|---------|
| sharpe | `equity_curve` annualised Sharpe (assume 365 days, risk-free = 0) |
| calmar | `final_equity / max_drawdown` (if max_dd > 0 else 0) |
| net_profit | `final_equity - initial_equity` |

### Heatmap generation

Only meaningful when exactly 2 params are being optimised. For each combination of (paramA, paramB) with fixed step, run mini-backtest (or reuse cached result if search_method=grid) and record score → surface array. Return flat list of `{p1, p2, score}` rows.

For >2 params, return `heatmap_data: []` (surface not available).

---

## Frontend wiring: `dashboard/templates/pages/page_optimization.html`

### State machine

```
[LOAD PAGE]
  → GET /api/strategies              // populate strategy dropdown
  → GET /api/quant/optimise         // populate history table
  → for each run with heatmap_data  → call drawHeatmap(run)
```

### User flows

#### 1. Start Optimiser
- User fills in strategy, optionally overrides bounds, picks fitness metric, clicks **Start Optimiser**
- JS: POST `/api/quant/optimise` → stores returned `run_id` → polls GET `/api/quant/optimise/{run_id}` every 3 s
- On status change to `running`: show progress (iterations so far = length of heatmap_data)
- On status `complete`: update heatmap, populate Top Parameter Sets table, add to history list
- On status `failed`: show error_message inline

#### 2. Heatmap rendering
- Uses `heatmap_data` array from the most recent completed run
- Rendered as a canvas heatmap using Chart.js or as an HTML grid (matching reference style)
- Clicking a cell shows: param values at that point + exact score (tooltip)

#### 3. Top Parameter Sets table
- Rendered from `top_n_results` (top 20 by score)
- Rank, param badges, score columns, action buttons
- **Load** → POST `/api/quant/optimise/{run_id}/deploy` with `{params: winning_params}` → updates `StrategyConfig.params` row in DB → live engine picks it up on next tick

#### 4. History list
- Clickable row → expands or navigates to detail (stretch: modal with full results)
- Color-coded status icon (green check = complete, red X = failed, spinner = running)

---

## CSS / Design tokens

Reuse from `_base.html` — same Material-inspired token system already used by `page_ml.html`. The reference screenshot's custom colours (slate, primary container, secondary) are the same tokens — no new CSS variables needed.

Components to include:
- `.heatmap-cell` from reference (hover scale, cursor) — move into `static/app.css` or inline `<style>` in the page
- `.terminal-grid` subtle background — keep in page styles if not already global

---

## Files touched / created

| Action | File |
|--------|------|
| EDIT | `db/models.py` — add `OptimisationRun` model |
| CREATE | `alembic/versions/XXXX_add_optimisation_run.py` — auto-generated |
| CREATE | `quant/optimiser.py` — grid / random / bayesian search + fitness scorer |
| EDIT | `dashboard/app.py` — add 3 new `/api/quant/optimise*` endpoints |
| REWRITE | `dashboard/templates/pages/page_optimization.html` — full page |

## What gets reused (no new code)

- `BacktestEngine` from `quant/backtest_engine.py` — the optimiser calls this per-param-set
- `apiFetch` from existing `app.js` — all API calls use this helper
- `_render_page` + JWT passthrough from `app.py` — page renders same way
- `StrategyConfig.param_bounds` from DB — source of parameter ranges
- `_get_current_user` auth dependency from `auth.router`

## Not in scope for first build

- Walk-forward analysis (separate module, mentioned in Claude docs)
- Bayesian optimiser (skopt dependency optional; random fallback for now)
- Export CSV button
- History-detail drill-in modal
- Multi-objective optimisation

---

## Sequence (once plan approved)

1. DB model + migration
2. `quant/optimiser.py` (unit-tested in isolation)
3. API endpoints in `app.py`
4. Page template rewrite (`page_optimization.html`)
5. Smoke test: start server, hit `/optimization`, submit a real optimisation
