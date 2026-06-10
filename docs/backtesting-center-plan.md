# Backtesting Center — Implementation Plan

## Reference Files
- `dashscreens/stitch_savanna_quant_os/backtesting_center/code.html` — full stitch HTML reference
- `dashscreens/stitch_savanna_quant_os/backtesting_center/screen.png` — visual reference
- `dashboard/templates/pages/page_backtesting_center.html` — current frontend (stub, 137 lines)
- `dashboard/v2/routes/backtest.py` — current backend (stub, 62 lines)
- `quant/hypothesis.py` — existing quant research module
- `data/repository.py` — `fetch_ohlcv()` already fetches from MT5
- `strategies/registry.py` — `StrategyRegistry` loads strategies, `get_by_name()` returns class
- `db/models.py` — `BacktestRun`, `Trade` models with full column set
- `config/settings.py` — `BacktestConfig` with initial_equity, risk_per_trade, warmup_bars

---

## 1. Stitch Screen Layout → UI Element Inventory

The stitch reference shows a 12-column CSS grid layout (`grid-cols-12`):

```
┌─────────────┬────────────────────────────────┬───────────┐
│  Config     │  Summary Metrics (5 cards)    │  Recent   │
│  Panel      │  Equity & Drawdown Curve       │  Runs     │
│  col-3      │  Trade Distribution / Heatmap  │  col-2    │
│             │  Run History Table             │           │
└─────────────┴────────────────────────────────┴───────────┘
```

### 1.1 Configuration Panel (col-span-3)
| # | Element | Type | Notes |
|---|---------|------|-------|
| C1 | Strategy Template | `<select>` | Populated from registry |
| C2 | Selected Symbols | Multi-select tag list | XAUUSD, XAGUSD, etc. with × to remove |
| C3 | Timeframe | `<select>` | 5m / 15m / 1h / 4h |
| C4 | Execution | `<select>` | OHLC / Every Tick |
| C5 | Date Range | Two date inputs | "Jan 2023 → Oct 2024" |
| C6 | Parameter Overrides | Editable table | Variable / Value columns, "Reset Defaults" link |
| C7 | Run Backtest | `<button>` | Primary action, bottom of panel |

### 1.2 Summary Metrics (col-span-7, row 1)
| # | Element | Notes |
|---|---------|-------|
| M1 | Net Profit | `$142,830`, border-l-primary, +14.2% trend |
| M2 | Sharpe Ratio | `2.41`, "High Performance" |
| M3 | Max Drawdown | `-4.2%`, border-l-error |
| M4 | Profit Factor | `1.88`, "Skewed Positive" |
| M5 | Win Rate | `62%`, "384 Trades" |

### 1.3 Equity & Drawdown Curve (col-span-7, row 2)
| # | Element | Notes |
|---|---------|-------|
| E1 | Title bar | "Equity & Drawdown Curve" + Linear/Log toggle |
| E2 | Chart area | SVG line chart (equity = cyan #00E5FF, drawdown = red area) |
| E3 | Tooltip on hover | Shows date, equity value, drawdown % |

### 1.4 Bottom Row — Split 2 ways (col-span-7)
| # | Element | Notes |
|---|---------|-------|
| D1 | Trade Distribution | Histogram (8 bars, green=win, red=loss) |
| D2 | Returns Heatmap | 12×2 grid (months × years), green=positive, red=negative |

### 1.5 Recent Runs Panel (col-span-2)
| # | Element | Notes |
|---|---------|-------|
| R1 | Job card — Running | #BT-0492, RUNNING badge, progress bar, ETA |
| R2 | Job card — Completed | #BT-0491, COMPLETED badge, Sharpe, timestamp |
| R3 | Job card — Queued | #BT-0490, QUEUED badge, batch ID |
| R4 | Clear History button | Bottom of panel |

### 1.6 Run History Table (col-span-7, below charts)
| # | Column | Notes |
|---|--------|-------|
| T1 | ID | Run identifier |
| T2 | Symbol | Traded symbol |
| T3 | TF | Timeframe |
| T4 | Strategy | Strategy name |
| T5 | Status | pending / running / complete / failed |
| T6 | Trades | Count |
| T7 | Win Rate | Percentage |
| T8 | Net PnL | R-multiple |
| T9 | Created | Timestamp |

---

## 2. Backend Endpoint Table

| # | Endpoint | Method | Auth | Purpose | Request Body | Response |
|---|----------|--------|------|---------|-------------|----------|
| E1 | `/api/v2/backtest/strategies` | GET | Yes | List all available strategy templates | — | `[{name, label, default_symbol, typical_timeframes}]` |
| E2 | `/api/v2/backtest/symbols` | GET | Yes | List all tradeable symbols grouped by asset class | — | `{crypto: [...], forex: [...], commodity: [...], equity: [...]}` |
| E3 | `/api/v2/backtest/timeframes` | GET | Yes | List all supported timeframes | — | `["M1","M5","M15","M30","H1","H4","D1"]` |
| E4 | `/api/v2/backtest/runs` | GET | Yes | List recent backtest runs (paginated) | — | `{items: [...], total, page, page_size}` |
| E5 | `/api/v2/backtest/run` | POST | Yes | **Queue a new backtest** | `{strategy_name, symbol, timeframe, execution, start_date, end_date, params_overrides}` | `{run_id, status, message}` |
| E6 | `/api/v2/backtest/runs/{run_id}` | GET | Yes | Get single run status + summary | — | Full `BacktestRun` dict + `progress_pct`, `eta_seconds` |
| E7 | `/api/v2/backtest/runs/{run_id}/equity` | GET | Yes | Get equity + drawdown curve data | — | `{equity_curve: [{t, equity}], drawdown_curve: [{t, dd}]}` |
| E8 | `/api/v2/backtest/runs/{run_id}/distribution` | GET | Yes | Get trade PnL distribution buckets | — | `{bins: [{label, count, is_win}]}` |
| E9 | `/api/v2/backtest/runs/{run_id}/monthly` | GET | Yes | Get monthly returns for heatmap | — | `{months: [{year, month, pnl_r}]}` |

**Total: 9 endpoints** (E1–E9)

---

## 3. Data Flow

### 3.1 Running a Backtest (E5 → E6 → E7/E8/E9)

```
Frontend                Backend (FastAPI)           Backtest Engine         MT5
   │                         │                          │                    │
   │  POST /backtest/run     │                          │                    │
   │  {strategy, symbol,    │                          │                    │
   │   tf, start, end,      │                          │                    │
   │   params}              │                          │                    │
   │───────────────────────>│                          │                    │
   │                         │  1. Create BacktestRun   │                    │
   │                         │     status=pending       │                    │
   │                         │  2. Background task:     │                    │
   │                         │     run_backtest_job()   │                    │
   │                         │                          │                    │
   │  ← {run_id, status}   │  3. Update status=running │                    │
   │                         │                          │                    │
   │                         │     ┌──────────────────┐ │                    │
   │                         │     │ Engine loop:     │ │                    │
   │                         │     │ a. fetch_ohlcv() │──────────────────────>│
   │                         │     │    from MT5      │ │   copy_rates_range  │
   │                         │     │ b. bar-by-bar    │ │<──────────────────────│
   │                         │     │    loop          │ │   DataFrame         │
   │                         │     │ c. strategy.     │ │                    │
   │                         │     │    generate_signal│ │                    │
   │                         │     │ d. SL/TP +       │ │                    │
   │                         │     │    position size │ │                    │
   │                         │     │ e. save trades   │ │                    │
   │                         │     └──────────────────┘ │                    │
   │                         │                          │                    │
   │  Poll: GET /runs/{id}  │  4. Return progress +    │                    │
   │  ─────────────────────>│     partial results      │                    │
   │  ← {progress, eta, ...}│                          │                    │
   │                         │                          │                    │
   │                         │  5. On complete:         │                    │
   │                         │     status=complete      │                    │
   │                         │     compute metrics      │                    │
   │                         │     save to BacktestRun  │                    │
   │                         │                          │                    │
   │  GET /runs/{id}/equity │  6. Return stored curves  │                    │
   │  GET /runs/{id}/monthly│  7. Return monthly data   │                    │
   │  GET /runs/{id}/dist   │  8. Return distribution   │                    │
```

### 3.2 MT5 Data Fetch → Backtest

```
fetch_ohlcv(symbol, timeframe, start, end)
    │
    ├── mt5.initialize(path, login, password, server)
    ├── mt5.copy_rates_range(symbol, tf, start, end)
    ├── Convert to DataFrame (UTC index, OHLCV columns)
    ├── Validate via data.validator.validate()
    └── Return DataFrame OR None on failure
```

### 3.3 Strategy Selection → Signal Generation

```
StrategyRegistry.get_by_name(strategy_name)
    │
    ├── Returns strategy class (e.g. MomentumReversion)
    ├── Instantiates with user params_overrides
    └── strategy.generate_signal({timeframe: df_slice})
            │
            ├── Uses DynamicSLTPModel for SL/TP
            ├── Uses PositionSizer for lot size
            └── Returns Signal | None
```

---

## 4. Implementation Tasks

### Phase A: Backend Engine (Python)

| Task | File | Description |
|------|------|-------------|
| A1 | `quant/__init__.py` | Package init |
| A2 | `quant/backtest_engine.py` | Core bar-by-bar engine — **no look-ahead** |
| A3 | `quant/runner.py` | Background job wrapper: fetch MT5 data → run engine → save results |
| A4 | `dashboard/v2/routes/backtest.py` | Replace stubs with 9 real endpoints |

### Phase B: Data Layer (MT5 integration)

Already exists:
- `data/repository.py` → `fetch_ohlcv(symbol, tf, start, end)` — fetches from MT5

Needs:
- Accept any symbol/timeframe from MT5 terminal (not limited to asset pools in config)
- Date range from frontend translates directly to `start`/`end` params
- Validation via `data.validator.validate()` before backtest starts

### Phase C: Frontend (HTML + JS)

| Task | File | Description |
|------|------|-------------|
| C1 | `dashboard/templates/pages/page_backtesting_center.html` | Full rewrite matching stitch layout |
| C2 | Chart.js rendering | Equity + drawdown, distribution histogram, monthly heatmap |
| C3 | Polling logic | Update progress on running jobs |
| C4 | apiFetch wiring | All AJAX calls use `window.apiFetch` |

---

## 5. Detailed Endpoint Specifications

### E1: `GET /api/v2/backtest/strategies`
```json
[
  {"name": "momentum_reversion", "label": "Momentum Reversion", "default_symbol": "BTCUSD", "typical_timeframes": ["M15", "H1"]},
  {"name": "band_reversion", "label": "Band Reversion", "default_symbol": "EURUSD", "typical_timeframes": ["M15"]},
  ...
]
```
Implementation: iterate `StrategyRegistry.get_all()`, extract `cls.meta` fields.

### E2: `GET /api/v2/backtest/symbols`
```json
{
  "crypto": ["BTCUSD", "ETHUSD", "BNBUSD"],
  "forex": ["EURUSD", "GBPUSD", "USDJPY"],
  "commodity": ["XAUUSD", "XAGUSD"],
  "equity": ["AAPL", "TSLA", "NVDA"]
}
```
Implementation: return `config.ASSET_POOL` dict.

### E3: `GET /api/v2/backtest/timeframes`
```json
["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
```
Implementation: static list or from config.

### E4: `GET /api/v2/backtest/runs`
```json
{
  "items": [
    {
      "id": 492, "label": null, "symbol": "XAUUSD", "timeframe": "M15",
      "strategy_name": "Mean_Rev_XAU_V42", "status": "running",
      "n_trades": 384, "win_rate": 0.62, "net_pnl_r": 1.42,
      "profit_factor": 1.88, "max_drawdown": -0.042, "sharpe_approx": 2.41,
      "created_at": "2024-10-15T08:30:00Z", "started_at": "...", "completed_at": null
    }
  ],
  "total": 150, "page": 1, "page_size": 20
}
```
Implementation: `db.query(BacktestRun).order_by(desc(created_at)).limit(page_size).all()`

### E5: `POST /api/v2/backtest/run`
```json
// Request
{
  "strategy_name": "momentum_reversion",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "execution": "OHLC",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "params_overrides": {"bb_period": 20, "rsi_limit": 30}
}

// Response
{"run_id": 492, "status": "queued", "message": "Backtest queued"}
```
Implementation:
1. Validate strategy exists in registry
2. Create `BacktestRun` record (status=pending)
3. Launch background task `run_backtest_job(run_id, ...)`
4. Return run_id immediately

### E6: `GET /api/v2/backtest/runs/{run_id}`
```json
{
  "id": 492, "symbol": "XAUUSD", "timeframe": "M15",
  "strategy_name": "momentum_reversion", "status": "running",
  "progress_pct": 65, "eta_seconds": 42,
  "n_bars": 12500, "n_trades": 248,
  ...
}
```
Implementation: query BacktestRun, compute progress from `n_bars_processed / total_bars`.

### E7: `GET /api/v2/backtest/runs/{run_id}/equity`
```json
{
  "equity_curve": [
    {"t": "2024-01-01T00:00:00Z", "equity": 1.0},
    {"t": "2024-01-01T00:15:00Z", "equity": 1.002},
    ...
  ],
  "drawdown_curve": [
    {"t": "2024-01-01T00:00:00Z", "dd": 0.0},
    {"t": "2024-01-01T00:15:00Z", "dd": -0.001},
    ...
  ]
}
```
Implementation: read `BacktestRun.equity_curve` and `BacktestRun.drawdown_curve` JSON columns.

### E8: `GET /api/v2/backtest/runs/{run_id}/distribution`
```json
{
  "bins": [
    {"label": "-5%", "count": 2, "is_win": false},
    {"label": "-4%", "count": 5, "is_win": false},
    ...
    {"label": "+5%", "count": 3, "is_win": true}
  ]
}
```
Implementation: query `Trade` rows for this `backtest_run_id`, bucket by `pnl_r`, group into 8 bins.

### E9: `GET /api/v2/backtest/runs/{run_id}/monthly`
```json
{
  "months": [
    {"year": 2024, "month": 1, "pnl_r": 0.08},
    {"year": 2024, "month": 2, "pnl_r": 0.12},
    ...
  ]
}
```
Implementation: read `BacktestRun.monthly_returns` JSON column.

---

## 6. Backtest Engine Design (`quant/backtest_engine.py`)

### Core Loop (NO look-ahead)

```python
def run_backtest(
    strategy_class: type[BaseStrategy],
    df: pd.DataFrame,           # full OHLCV DataFrame
    params: dict,
    timeframe: str,
    execution: str = "OHLC",    # OHLC or Every Tick
    initial_equity: float = 10_000,
    risk_per_trade: float = 0.01,
    warmup_bars: int = 210,
) -> BacktestResult:
    """
    Bar-by-bar event loop. No look-ahead.

    For each bar i from warmup to len(df)-1:
        slice = df.iloc[:i+1]   # only bars 0..i visible
        signal = strategy.generate_signal({tf: slice})
        if signal:
            compute SL/TP via DynamicSLTPModel
            compute lot via PositionSizer
            simulate entry at bar i close
            track until SL/TP hit or bar exit
            record trade
        update equity curve

    Returns BacktestResult with all metrics + curves.
    """
```

### Key Constraints (from CLAUDE.md)
- **No look-ahead**: `slice_data = {tf: df.iloc[:i+1] ...}` — never pass `df` directly
- **SL/TP always from DynamicSLTPModel**: never compute in strategy
- **Equity starts at 1.0**: `equity_curve = [1.0]`
- **Partial close P&L**: 50% at TP1, 50% at TP2, BE stop after TP1
- **Data validation**: `validate(df, symbol, timeframe)` before loop
- **Binomial significance test**: `binomtest(n_wins, n_trades, 0.5)`

### Execution Modes
- **OHLC**: enter on bar close, check SL/TP on next bar open
- **Every Tick**: enter on signal bar, use intrabar high/low for SL/TP (simulated with bar-level data)

---

## 7. File Structure (New/Modified)

```
quant/
├── __init__.py              # NEW — package init
├── backtest_engine.py       # NEW — core engine
├── runner.py                # NEW — background job wrapper
├── hypothesis.py            # EXISTS — unchanged for now
└── walk_forward.py          # EXISTS — unchanged

dashboard/v2/routes/
├── backtest.py              # REWRITE — 9 real endpoints replacing 3 stubs

dashboard/templates/pages/
├── page_backtesting_center.html  # REWRITE — full stitch layout
```

---

## 8. Frontend Architecture

### HTML Structure (12-col grid)
```
<div class="grid grid-cols-12 gap-6">
  <!-- Left: Configuration (col-3) -->
  <section class="col-span-3">...</section>

  <!-- Center: Charts + Results (col-7) -->
  <section class="col-span-7 flex flex-col gap-4">
    <!-- Summary metrics row (5 cards) -->
    <div class="grid grid-cols-5 gap-3">...</div>

    <!-- Equity + Drawdown (large chart) -->
    <div class="glass-panel p-5">
      <canvas id="btEquityChart"></canvas>
    </div>

    <!-- Bottom row: Distribution + Heatmap -->
    <div class="grid grid-cols-2 gap-4">
      <div class="glass-panel p-4">
        <canvas id="btDistChart"></canvas>
      </div>
      <div class="glass-panel p-4">
        <div id="btHeatmap" class="grid grid-cols-12 gap-1"></div>
      </div>
    </div>

    <!-- Run History Table -->
    <div class="glass-panel p-4">
      <table>...</table>
    </div>
  </section>

  <!-- Right: Recent Runs (col-2) -->
  <section class="col-span-2">...</section>
</div>
```

### JS Data Flow
```
Page load:
  1. fetch('/api/v2/backtest/strategies') → populate strategy dropdown
  2. fetch('/api/v2/backtest/symbols') → populate symbol selector
  3. fetch('/api/v2/backtest/runs?page_size=20') → render run table + recent panel
  4. Start polling interval for running jobs

On "Run Backtest" click:
  1. Gather form values
  2. POST /api/v2/backtest/run
  3. On success: poll GET /runs/{id} every 2s
  4. When complete: fetch equity, distribution, monthly → render charts

On run table row click:
  1. GET /runs/{id}/equity → render equity chart
  2. GET /runs/{id}/distribution → render histogram
  3. GET /runs/{id}/monthly → render heatmap
```

---

## 9. MT5 Integration Details

### Data Flow for "Run Backtest with M5 data"

```
User selects: Strategy=MomentumReversion, Symbol=BTCUSD, TF=M5,
              Start=Jan 2023, End=Oct 2024

Frontend:
  POST /api/v2/backtest/run {
    strategy_name: "momentum_reversion",
    symbol: "BTCUSD",
    timeframe: "M5",
    start_date: "2023-01-01",
    end_date: "2024-10-31",
    params_overrides: {bb_period: 20, rsi_limit: 30}
  }

Backend:
  run_backtest_job():
    1. Convert start_date/end_date → UTC datetime objects
    2. Call fetch_ohlcv("BTCUSD", "M5", start=2023-01-01, end=2024-10-31)
       → data/repository.py:
         a. mt5.initialize() (if not already connected)
         b. mt5.copy_rates_range("BTCUSD", MT5_TF_M5, datetime(2023,1,1), datetime(2024,10,31))
         c. Convert to DataFrame, validate
    3. If data is None or invalid → mark run failed, return
    4. Instantiate MomentumReversion with params_overrides
    5. Call backtest_engine.run_backtest(strategy, df, ...)
    6. Save trades to DB (source="backtest", backtest_run_id=run.id)
    7. Compute equity_curve, drawdown_curve, monthly_returns
    8. Update BacktestRun: status=complete, save all metrics + curves
```

### MT5 Timeframe Mapping
```python
# Already in data/repository.py
_MT5_TF_MAP = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}
```
User picks any timeframe from the dropdown → mapped to MT5 constant → `copy_rates_range()`.

### Date Range Handling
- Frontend sends ISO dates: `start_date: "2024-01-01"`, `end_date: "2024-10-31"`
- Backend converts to UTC datetime: `datetime(2024, 1, 1, tzinfo=timezone.utc)`
- Passed to `fetch_ohlcv(symbol, tf, start, end)`
- If `end` is None, defaults to `datetime.now(timezone.utc)`

---

## 10. Implementation Order

1. **`quant/__init__.py`** — trivial package init
2. **`quant/backtest_engine.py`** — core engine (depends on: strategies, data, config)
3. **`dashboard/v2/routes/backtest.py`** — rewrite with 9 endpoints
4. **`dashboard/templates/pages/page_backtesting_center.html`** — full frontend rewrite
5. **Verification** — smoke test backend, verify HTML, end-to-end with dashboard
