# Portfolio Risk Monitor — v3 API Contract

**Endpoint:** `GET /api/v3/risk/overview`  
**Authentication:** JWT required via `_get_current_user` dependency  
**Response Type:** `application/json`  
**Cache Policy:** No-cache (real-time risk data)

---

## Overview

The Portfolio Risk Monitor provides a comprehensive view of current portfolio risk metrics, open positions, asset allocation, strategy exposure, correlation matrix, and risk alerts. This endpoint aggregates data from account snapshots and active trades.

---

## Request

### Parameters
None.

### Headers
```
Authorization: Bearer <jwt_token>
```

---

## Response Schema

```json
{
  "kpis": {
    "daily_dd_pct": number,         // Daily drawdown percentage (e.g., -2.35 for -2.35%)
    "weekly_dd_pct": number,        // Weekly drawdown percentage
    "total_exposure_usd": number,   // Total gross exposure in USD (float)
    "var_95_1d_usd": number,        // 95% Value at Risk for 1 day (Parametric, normal distribution)
    "margin_usage_pct": number,     // Margin utilization percentage (0-100)
    "positions_count": number       // Number of active positions (optional but recommended)
  },
  "positions": [
    {
      "account": string,            // Always "Quant-A1" in v3
      "symbol": string,             // Trading symbol (e.g., "BTCUSD", "EURUSD")
      "dir": "Long" | "Short",      // Direction based on trade side
      "entry": number,              // Entry price (float)
      "price": number,              // Current price (same as entry in v2, may be updated in v3)
      "size": number,               // Lot size (float, in standard lot units)
      "sl": number | null,          // Stop loss price (null if not set)
      "tp": number | null,          // Take profit price (null if not set)
      "tp1": number | null,         // Optional: first TP level for tiered exits
      "pnl": number,                // Current P&L in USD (float)
      "pnl_r": number | null,       // Optional: P&L in risk multiples (R)
      "risk_pct": number,           // Risk as percentage of current equity (0-100)
      "asset_class": string,        // "crypto" | "equities" | "fx" | "metals" | "other"
      "strategy": string            // Strategy name that generated this trade
    }
  ],
  "asset_allocation": {
    "crypto": number,               // Percentage (0-100, float, 1 decimal)
    "equities": number,
    "fx": number,
    "metals": number,
    "other": number
  },
  "strategy_exposure_usd": {
    "trend": number,                // Exposure in USD by strategy group
    "mean_reversion": number,
    "hft_scalp": number,
    "macroscopic_event": number,
    "swing_divergence": number,
    "other": number
  },
  "correlation": {
    "labels": [string],             // Strategy group names (same keys as strategy_exposure_usd)
    "matrix": [[number]],           // Square matrix (n x n) of Pearson correlations (-1 to 1)
    "period_days": number          // Optional: lookback period used (e.g., 30)
  },
  "alerts": [
    {
      "severity": "error" | "warning" | "info",
      "account": string,            // Usually "System"
      "symbol": string,             // Asset/symbol that triggered alert (e.g., "BTC", "PORTFOLIO", "MARGIN")
      "message": string,            // Human-readable description
      "ts": string                  // ISO 8601 UTC timestamp (e.g., "2025-06-19T14:32:45.123Z")
    }
  ],
  "metadata": {
    "generated_at": string,         // ISO 8601 UTC timestamp when response was generated
    "snapshot_id": number | null,  // ID of latest AccountSnapshot used
    "equity_currency": string      // Currency code, always "USD" in v3
  }
}
```

---

## Computation Methods

### KPIs

**daily_dd_pct**
```
eq_now = latest_account_snapshot.equity
eq_prev = previous_account_snapshot.equity
daily_dd_pct = ((eq_now - eq_prev) / eq_prev) * 100
```
- Uses two most recent snapshots ordered by `created_at`
- If previous snapshot doesn't exist: `0.0`

**weekly_dd_pct**
```
week_ago = now_utc - 7 days
week_snapshots = all snapshots with created_at >= week_ago, ordered asc
if week_snapshots and eq_prev > 0:
    min_equity_week = min(snapshot.equity for snapshot in week_snapshots)
    weekly_dd_pct = ((eq_now - min_equity_week) / eq_prev) * 100
else:
    weekly_dd_pct = 0.0
```

**total_exposure_usd**
```
total_exposure = sum(position.notional_value for all active positions)
where notional_value = size * entry_price * contract_multiplier
```
- Contract multiplier: 100,000 for forex/crypto (standard lot), asset-specific for others
- In v3, use `ContractSpec` or config to determine multiplier per symbol

**var_95_1d_usd** (Parametric VaR, normal distribution)
```
all_snapshots = last 365 daily snapshots (ordered asc)
if len(all_snapshots) >= 5:
    equity_values = [float(s.equity) for s in all_snapshots]
    returns = [(equity_values[i] - equity_values[i-1]) / equity_values[i-1]
               for i in range(1, len(equity_values))
               if equity_values[i-1] != 0]
    if len(returns) >= 2:
        mu = mean(returns)
        variance = sum((r - mu)^2 for r in returns) / (len(returns) - 1)
        daily_vol = sqrt(variance)
        var_95 = 1.645 * daily_vol * eq_now
else:
    var_95 = 0.0
```
- Uses 1.645 as z-score for 95% one-tailed normal distribution
- Assumes mean = 0 for small samples (can subtract mu in formula)
- Returns USD amount (negative, representing potential loss)

**margin_usage_pct**
```
margin_pct = (latest_account_snapshot.margin / eq_now) * 100 if eq_now > 0 else 0.0
```

**positions_count**
```
count = number of active positions (Trade.is_active == True)
```

### Positions

For each active trade (`Trade.is_active == True`):

**notional_value** (used for exposure aggregation):
```
entry = trade.entry or trade.open_price or 0.0
size = trade.lot_size or 0.0
notional = size * entry * contract_multiplier
```

**risk_pct** (per-position risk as % of equity):
```
if entry > 0 and sl > 0 and eq_now > 0:
    sl_distance = abs(entry - sl)
    risk_amount = size * sl_distance * contract_multiplier
    risk_pct = (risk_amount / eq_now) * 100
else:
    risk_pct = 0.0
```

**asset_class** determination:
```python
def _asset(sym: str) -> str:
    s = sym.upper()
    if any(s.startswith(p) for p in ("XAU", "XAG", "GOLD", "SILVER", "GC", "SI")):
        return "metals"
    if any(s.startswith(p) for p in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA")):
        return "crypto"
    if any(s.startswith(p) for p in ("AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "META", "AMZN", "ES", "NQ")):
        return "equities"
    if len(s) >= 6 and s[:3] in ("EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF") and s[3:6] in same_tuple:
        return "fx"
    return "other"
```

**strategy_exposure_usd** aggregation:
```
by_strat = defaultdict(float)
for position in positions:
    group = _grp(position.strategy_name)
    by_strat[group] += position.notional_value

def _grp(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("trend", "ema", "macd", "momentum")):
        return "trend"
    if any(k in n for k in ("reversion", "mean", "band", "vwap", "stoch")):
        return "mean_reversion"
    if any(k in n for k in ("scalp", "hf", "hft")):
        return "hft_scalp"
    if any(k in n for k in ("breakout", "session", "macro")):
        return "macroscopic_event"
    if any(k in n for k in ("divergence", "swing")):
        return "swing_divergence"
    return "other"
```

**asset_allocation**:
```
by_asset = defaultdict(float)
for position in positions:
    by_asset[position.asset_class] += position.notional_value
total = sum(by_asset.values())
alloc = {k: round(v / total * 100, 1) if total > 0 else 0.0 for k, v in by_asset.items()}
# Ensure all 5 keys exist with 0.0 defaults
```

### Correlation Matrix

Pearson correlation on strategy group returns:

```python
def _pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a2, b2 = a[:n], b[:n]
    ma = sum(a2) / n
    mb = sum(b2) / n
    num = sum((a2[i] - ma) * (b2[i] - mb) for i in range(n))
    da = sqrt(sum((x - ma) ** 2 for x in a2))
    db = sqrt(sum((x - mb) ** 2 for x in b2))
    if da < 1e-12 or db2 < 1e-12:
        return 0.0
    return num / (da * db2)
```

**collect returns by group**:
```
strat_ret = defaultdict(list)
for trade in active_trades:
    if trade.pnl_r is not None:
        group = _grp(trade.strategy_name)
        strat_ret[group].append(float(trade.pnl_r))
```

**build matrix**:
```
groups = sorted(set(_grp(trade.strategy_name) for trade in trades if trade.strategy_name))
n = len(groups)
corr_matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
for i in range(n):
    for j in range(i+1, n):
        r = _pearson(strat_ret.get(groups[i], []), strat_ret.get(groups[j], []))
        corr_matrix[i][j] = round(r, 2)
        corr_matrix[j][i] = round(r, 2)
```

**lookback period**: v2 used all available trade history. For v3, consider limiting to last 30-90 days to ensure relevance.

### Alerts

Generated at endpoint execution time with thresholds:

| Condition | Threshold | Severity | Symbol | Message Pattern |
|-----------|-----------|----------|--------|-----------------|
| Asset concentration | > 35% of total exposure | error | asset class uppercase (e.g., "CRYPTO") | "High concentration: {asset} at {pct:.1f}% of portfolio" |
| Daily drawdown | < -2.0% | warning | "PORTFOLIO" | "Daily drawdown {dd:.2f}% breached -2.0% threshold" |
| Margin usage | > 80% | error | "MARGIN" | "Margin usage {pct:.1f}% above 80% threshold" |
| Free margin ratio | < 20% | equity | warning | "FREE_MARGIN" | "Free margin ratio {pct:.1f}% below 20% floor" |

**Alert timestamp**: `datetime.now(timezone.utc).isoformat()`

---

## Frontend Integration Specs

### Polling Frequency
- 6000ms (6 seconds) between data refreshes

### KPI Display Rules

| KPI | Element ID | Format | Color Logic |
|-----|------------|--------|-------------|
| Daily Drawdown | `kpi-daily-dd` | `"{value:.2f}%"` | text-error if < 0, text-primary-fixed-dim otherwise |
| Weekly Drawdown | `kpi-weekly-dd` | `"{value:.2f}%"` | text-error if < 0, text-primary-fixed-dim otherwise |
| Total Exposure | `kpi-exposure` | `fmtUSD(value)` | text-primary-fixed-dim |
| VaR 95% 1D | `kpi-var` | `fmtUSD(value)` + secondary `"{pct:.2f}% NAV"` | text-on-surface |
| Margin Usage | `kpi-margin` | `"{value:.1f}%"` | text-error if > 70%, text-tertiary otherwise |

**Margin bar** (`#bar-margin`): width = `min(margin_usage_pct, 100)%`

### Asset Allocation Donut

- Canvas: `#alloc-canvas` (128x128)
- Center: (64, 64)
- Radius: 54
- Line width: 16
- Start angle: -π/2 (top)
- Colors:
  ```javascript
  {
    fx: '#00daf3',
    crypto: '#e9c400',
    equities: '#bcc7de',
    metals: '#ffecad',
    other: '#849396'
  }
  ```
- Legend: displays each non-zero allocation with color dot and `"{value:.1f}%"`

### Strategy Exposure Bars

- Container: `#strat-bars`
- Horizontal bar for each strategy group, displayed in descending order by exposure
- Bar width normalized to max exposure in current data: `pct = value / max * 100`
- Color: primary-fixed-dim

### Correlation Matrix

- Container: `#corr-grid` (CSS Grid, columns = rows = number of groups)
- Diagonal cells: background `rgba(primary, 0.25)`, bold text
- Off-diagonal correlation >= 0.5 absolute: background error/30 + error text, bold
- Otherwise: background surface-container-highest
- Format: always 2 decimal places

### Alerts

- Container: `#alerts-list`
- Count display: `#alerts-count`
- Each alert: severity icon + symbol (uppercase bold in severity color) + timestamp (HH:MM:SS) + message
- Icon mapping:
  - error: `warning` (Material icon)
  - warning: `priority_high`
  - info: `info`

---

## Error Handling

**Empty Data Scenario**:
- If no AccountSnapshot exists: all KPIs = 0 or null
- If no active trades: positions = [], asset_allocation = all 0.0%, strategy_exposure = empty object, correlation = {labels: [], matrix: []}
- Always return valid JSON structure (no null for required fields, use 0 or [] instead)

**Exception Handling**:
- Endpoint should catch database exceptions and return HTTP 500 with structured error
- Return empty structure with error flag if data retrieval fails partially
- Log errors with context (user ID, query parameters)

---

## Performance Requirements

- Target query time: < 500ms (P95)
- Optimizations:
  - Single query to fetch latest + previous AccountSnapshot
  - Single query to fetch active trades with proper indexes
  - Correlation calculation may be expensive; consider caching per-session if needed
  - Limit active trades query to reasonable number (v2 uses limit 500; consider if pagination needed)

---

## Sample Response

```json
{
  "kpis": {
    "daily_dd_pct": -1.42,
    "weekly_dd_pct": -3.87,
    "total_exposure_usd": 1250000,
    "var_95_1d_usd": 32850,
    "margin_usage_pct": 45.2,
    "positions_count": 12
  },
  "positions": [
    {
      "account": "Quant-A1",
      "symbol": "BTCUSD",
      "dir": "Long",
      "entry": 67250.50,
      "price": 67830.25,
      "size": 2.5,
      "sl": 65800.00,
      "tp": 69500.00,
      "tp1": null,
      "pnl": 1495.00,
      "pnl_r": 0.42,
      "risk_pct": 1.85,
      "asset_class": "crypto",
      "strategy": "MomentumReversion"
    }
  ],
  "asset_allocation": {
    "crypto": 45.2,
    "equities": 28.5,
    "fx": 18.3,
    "metals": 8.0,
    "other": 0.0
  },
  "strategy_exposure_usd": {
    "trend": 450000,
    "mean_reversion": 520000,
    "hft_scalp": 0,
    "macroscopic_event": 180000,
    "swing_divergence": 100000,
    "other": 0
  },
  "correlation": {
    "labels": ["mean_reversion", "trend", "swing_divergence", "macroscopic_event"],
    "matrix": [
      [1.00, 0.23, -0.15, 0.08],
      [0.23, 1.00, 0.12, -0.05],
      [-0.15, 0.12, 1.00, 0.34],
      [0.08, -0.05, 0.34, 1.00]
    ],
    "period_days": 30
  },
  "alerts": [
    {
      "severity": "warning",
      "account": "System",
      "symbol": "PORTFOLIO",
      "message": "Daily drawdown -2.35% breached -2.0% threshold",
      "ts": "2025-06-19T14:32:45.123Z"
    }
  ],
  "metadata": {
    "generated_at": "2025-06-19T14:35:10.456Z",
    "snapshot_id": 15234,
    "equity_currency": "USD"
  }
}
```

---

## Implementation Notes

### Database Models Required

**AccountSnapshot** (or equivalent):
- `id` (int)
- `equity` (float)
- `margin` (float)
- `free_margin` (float)
- `created_at` (datetime, UTC)

**Trade**:
- `id` (int)
- `symbol` (str)
- `side` (Enum: BUY/SELL)
- `lot_size` (float)
- `entry` (float, nullable)
- `open_price` (float, nullable)
- `sl` (float, nullable)
- `tp` (float, nullable)
- `pnl` (float)
- `pnl_r` (float, nullable)
- `strategy_name` (str)
- `opened_at` (datetime)
- `is_active` (bool)

### Contract Multiplier Strategy

For v3, define a "ContractSpec" registry that maps symbols to multiplier:
- Forex pairs (EURUSD, GBPUSD, etc.): 100,000
- Gold/Silver (XAUUSD, XAGUSD): 100
- Crypto (BTCUSD, ETHUSD): 1 (already in USD terms)
- Indices (ES, NQ, etc.): vary by contract
- Stocks: shares directly (multiplier = 1)

Alternative: store contract size in `Trade` or have `symbol_metadata` table.

---

## Version History

- **v2** (current): `/api/risk/overview` (unversioned)
- **v3** (proposed): `/api/v3/risk/overview`

Changes from v2:
- Add `positions_count` to KPIs
- Add `metadata` block with `generated_at`, `snapshot_id`, `equity_currency`
- Add `tp1` field to positions (optional, for tiered TP tracking)
- Add `period_days` to correlation metadata
- Standardize `account` field as "Quant-A1" (instead of potentially variable)
- All fields consistently typed (no mixed null/0 handling in required fields)
- More explicit about contract multiplier calculation

---

## Testing Scenarios

1. **Empty database** (no snapshots, no trades): return all KPIs as 0 or null, empty arrays
2. **Single snapshot only**: daily_dd_pct = 0, weekly_dd_pct = 0, VaR = 0
3. **Margin usage > 100%**: still show value (could indicate over-leverage)
4. **Negative equity**: allow KPIs to be negative (drawdowns), but handle division by zero safely
5. **Large portfolio (500+ positions)**: ensure performance remains < 500ms
6. **Correlation with insufficient data**: return all zeros and empty labels
7. **Asset with unknown prefix**: falls back to "other" class and triggers alert if >35%

---

## Frontend Mapping Reference

| v2 HTML Element | v3 Expected Field |
|-----------------|-------------------|
| `kpi-daily-dd` | `kpis.daily_dd_pct` |
| `kpi-weekly-dd` | `kpis.weekly_dd_pct` |
| `kpi-exposure` | `kpis.total_exposure_usd` |
| `kpi-var` | `kpis.var_95_1d_usd` |
| `kpi-var-pct` | computed: `var_95_1d_usd / total_exposure_usd * 100` |
| `kpi-margin` | `kpis.margin_usage_pct` |
| `bar-margin` | width = `margin_usage_pct` (clamped to 100%) |
| `positions-tbl` | `positions[]` array |
| `positions-count` | `kpis.positions_count` |
| `alloc-canvas` | `asset_allocation` object |
| `alloc-gross` | `kpis.total_exposure_usd` |
| `alloc-legend` | rendered from `asset_allocation` keys/values |
| `strat-bars` | `strategy_exposure_usd` object |
| `corr-grid` | `correlation.labels` + `correlation.matrix` |
| `alerts-list` | `alerts[]` array |
| `alerts-count` | `alerts.length` |

---

## Backend Implementation Checklist

- [ ] Endpoint at `/api/v3/risk/overview` with JWT dependency
- [ ] Query latest AccountSnapshot (order by created_at desc, limit 1)
- [ ] Query previous AccountSnapshot (created_at < latest.created_at, order desc, limit 1)
- [ ] Query last 7 days of AccountSnapshots for weekly DD
- [ ] Query last 365 days of AccountSnapshots for VaR
- [ ] Query active trades (`is_active=True`) with limit (default 500)
- [ ] Compute correlation on strategy group returns from trade.pnl_r values
- [ ] Apply alert threshold rules
- [ ] Format all numbers as float, percentages as 0-100 range
- [ ] Return JSON with top-level keys: kpis, positions, asset_allocation, strategy_exposure_usd, correlation, alerts, metadata
- [ ] Add proper error handling (log exceptions, return 500 on failure)
- [ ] Add response headers: `Cache-Control: no-cache, no-store, must-revalidate`
- [ ] Document average response time in logs (use middleware timing if available)

---

## Appendix: Constants

**Asset Class Prefixes**:
```python
CRYPTO_PREFIXES = ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA")
EQUITY_PREFIXES = ("AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "META", "AMZN", "ES", "NQ")
METAL_PREFIXES = ("XAU", "XAG", "GOLD", "SILVER", "GC", "SI")
FX_PREFIXES = ("EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF")
```

**Strategy Group Keywords**:
```python
TREND_KWS = ("trend", "ema", "macd", "momentum")
MEAN_REVERSION_KWS = ("reversion", "mean", "band", "vwap", "stoch")
HFT_SCALP_KWS = ("scalp", "hf", "hft")
MACROSCOPIC_KWS = ("breakout", "session", "macro")
SWING_DIVERGENCE_KWS = ("divergence", "swing")
```

**Alert Thresholds**:
```python
ASSET_CONCENTRATION_THRESHOLD = 0.35    # 35%
DAILY_DD_THRESHOLD = -2.0              # -2%
MARGIN_USAGE_THRESHOLD = 80.0          # 80%
FREE_MARGIN_RATIO_THRESHOLD = 0.20     # 20%
MARGIN_COLOR_THRESHOLD = 70.0          # for KPI display
```

**Statistical Constants**:
```python
VAR_CONFIDENCE_LEVEL = 0.95
VAR_Z_SCORE = 1.645  # Normal distribution one-tailed
MIN_RETURNS_FOR_VAR = 2
MIN_POINTS_FOR_CORRELATION = 3
```

**Canvas Constants**:
```python
DONUT_CENTER = (64, 64)
DONUT_RADIUS = 54
DONUT_LINEWIDTH = 16
DONUT_START_ANGLE = -math.pi / 2
```
