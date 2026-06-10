# Portfolio Risk Monitor — Build Plan

## Source of truth
`dashscreens/stitch_savanna_quant_os/portfolio_risk_monitor/code.html`
Layout: 1 page, sub-grids inside existing sidebar shell.


## UI sections (from code.html)

| Section | col-span | Content |
|---------|----------|---------|
| 5 KPI panels | grid-cols-5 top | DD (daily), DD (weekly), Exposure, VaR 95% 1D, Margin Usage |
| Open Positions | col-span-9 | Positions table (account, symbol, side, entry, price, size, SL/TP, PnL, risk%) |
| Exposure sidebar | col-span-3 | Asset Allocation donut + Asset class list + Strategy Exposure bars |
| Correlation | col-span-8 | Strategy correlation matrix 6×6 |
| Risk Alerts | col-span-4 | List of alert cards with severity levels |

## Rust (existing) → Risk Monitor mapping

| Data I need | Source |
----------|--------|
| today_dd, week_dd, margin_pct, total_exposure | `/api/account/stats` + `/api/account/snapshots` snapshot |
| Open positions with live profit | `/api/mt5/positions` + `/api/mt5/account` |
| Asset class breakdown | Derive symbol→asset class client-side (XAU=Crypto, EURUSD=FX, AAPL=Equities) |
| Strategy exposure | `/api/trades/recent?limit=500` sum lot_size*pair by strategy_name |
| Correlation matrix | returns matrix from recent trades/positions per strategy | 
| Risk alerts | Generated client-side from the above (concentration > 35% = High, pnl_r < -1 = Medium) |
| VaR 95% 1D | Parametric: 1.65×σ of recent daily returns from snapshots (Month/returns) or trade PnL |

API contract choice: single `GET /api/risk/overview` returns all sections at once. Keeps HTTP count low and matches reference's one-screen refresh.

Approach: derive everything client-side from existing endpoints. No backend risk engine changes needed — keeps surgical.

## Implementation

## Backend

Write `dashboard/routes/risk.py` as a tiny router with one route:

```python
router = APIRouter()
@router.get("/overview")
def overview(current_user, db):
    stats = db.query(AccountSnapshot)...
    # latest snapshot for equity + drawdown estimate
    return {...}
```

Add to `app.py`:
```python
from dashboard.routes.risk import router as risk_router
app.include_router(risk_router)
```

Because stats/snapshots/positions are already public JWT-protected, same rule here.

### data shape returned by `/api/risk/overview`

```json
{
  "kpis": {
    "daily_dd_pct": -1.24, // derived from latest vs previous snapshot equity
    "weekly_dd_pct": -2.45,
    "total_exposure_usd": 8421902,
    "var_95_1d_usd": 142500,
    "margin_usage_pct": 14.2
  },
  "positions": [...],
  "asset_allocation": {
    "equities": 42.4, "fx": 28.1, "crypto": 18.5, "metals": 11.0
  },
  "strategy_exposure": {
    "trend": 79, "mean_reversion": 52, ...
  },
  "correlation_matrix": [[1.0,0.3,...],...],
  "alerts": [
    {"severity":"error","account":"Quant-A1","symbol":"BTCUSDT","message":"Excessive Correlation Detected: BTC_Trend vs ETH_Momentum (0.84)","ts":...},
    ...
  ]
}
```

Compute details in risk.py — leverage `ing=AccountSnapshot + Trade`.

## Frontend

Rewrite `dashboard/templates/pages/page_portfolio_risk.html` following existing project conventions:
- Jinja2 extends `_base.html`
- Sidebar link is already in `_base.html` (Portfolio Risk)
- Tailwind classes matching the dark theme
- Single profile init block, sq: all data via `apiFetch('/api/risk/overview')`
- Render 5 KPI cards in top grid, positions table with hover inset, segments (col 9), allocation donut + pie (col 3), strategy exposure bars (col 3), correlation matrix (col 8), alerts list (col 4)

Algorithm for ai/client-side pieces:
- `asset_classes` = symbol→category mapping (approximate):
  - `XAU`, `XAG`, `GOLD`, `SIL` → metals (%)
  - `BTC`, `ETH`, `SOL`, crypto → crypto
  - `EUR`, `GBP`, `USD`, `JPY`, `AUD`, `NZD`, `CAD`, `CHF` → fx
  - `AAPL`, `TSLA`, `NVDA`, `ES`, equities / indices
  - everything else → `other`
- `total_exposure` — from positions + MT5 account info
- `dd_today` = equity - prev_day equity (from snapshots), else 0
- `weekly_dd` = equity - min(equity) over last 7 days  from snapshots
- `var_95` = 1.645 × σ of daily returns over last 252 snapshots (or balance returns)
- `correlation` = trade returns per strategy → pandas correlation()
- `alerts` = `generate_alerts()` based on computed values

## Files changed

1. `dashboard/routes/risk.py` (new)
2. `dashboard/app.py` (register new router)
3. `dashboard/templates/pages/page_portfolio_risk.html` (rewrite)
4. Optionally add synthetic alias `RiskOverview` if helpful, but not required.

## Risk analysis approach (won't require new DB schema)

Compute from existing data:
- VaR: parametric = 1.645 * std(log_returns of account balance over last N days)
- Correlation: trade_r per strategy per day → correlation matrix
- Asset allocation: infer from symbol string with a small symbolic mapper
- Alerts: static checks once loaded (high concentration, high drawdown, low margin)

If snapshots are empty: derive Vix from equity(now) - equity_latest snapshot — cheap approximation.

## Decision: don't add new DB schema changes for VaR
Live VaR stays in-memory computed on each requests. This keeps the runtime stats requirements simple (Stat calls on /api/snapshots), not schema changes.

## Caveats
- eager positions linkage: portfolio risk depends on live MT5 → Mock MT5 returns empty list, page should state "No connected". Plan: zero-fallback handled in JS (empty positions → show "MT5 disconnected").
- Client-side correlation builds on Trade rows with returns. If no trades, correlation is N/A.
- TODO: correlation matrix 6×6 col titles (Trend, Mean, Arb, HFT, Macro, Scalp) maps strategy names; if fewer than 6 groups, clamp grid-cols=X dynamically client-side.

## Acceptance

- Navigate to /portfolio-risk while dashboard running
- Shows 5 KPI panels with rounded values and sparkline logic (from live/account data)
- Positions table with live PnL colored green/red as before
- Exposure sidebar with donut and strategy bars
- Correlation matrix (all 1.0 on diagonal, off-diagonal if data available)
- Alerts list with color-coded severity
- Page polls every 5s (shorter than default 10s) for freshness
