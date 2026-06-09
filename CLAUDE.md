
# CLAUDE.md — Trading Workflow Automation
## Agent Memory & Project Instructions

> This file is read at the start of every session by every agent.
> It is the single source of truth for how this project works.
> Nothing in this file is optional. Everything here has been decided.

---

## SESSION STARTUP PROTOCOL

Before doing anything else at the start of every session:

1. Read this file completely
2. Read `SESSION_STATE.md` for in-progress work
3. Report to the user:
   - Active branch
   - Last completed feature
   - Any in-progress tasks not yet committed
4. Ask: "Resume in-progress work, or start fresh?"

Do not write a single line of code until this protocol is complete.

# Required Reading Order

Before implementing any task:

1. Read CLAUDE.md
2. Read TWFA1.md
3. Read quant-build.md (if strategy-related)
4. Identify affected technologies
5. Load required skills
6. Create implementation plan
7. Begin implementation

---

# Skill Loading Rules

Before modifying code, load all relevant skills.

## Backend

Required skills:

* .claude/skills/fastapi.md
* .claude/skills/sqlalchemy.md
* .claude/skills/postgres.md

## Database

Required skills:

* .claude/skills/alembic.md
* .claude/skills/sqlalchemy.md
* .claude/skills/postgres.md

## Frontend

Required skills:

* .claude/skills/react.md

---

# Mandatory Planning Phase

Before writing code:

1. Understand requirements.
2. Identify affected modules.
3. Identify risks.
4. Produce implementation plan.
5. Validate architecture.
6. Then implement.

Never immediately begin coding.

---

# Architecture Rules

Maintain separation of concerns.

## Backend

Separate:

* Routers
* Services
* Repositories
* Models
* Schemas

Business logic belongs in services.

Database access belongs in repositories.

---

## Frontend

Separate:

* Pages
* Components
* Hooks
* Services
* State

Avoid business logic in UI components.

---

# Database Rules

Schema changes require migrations.

Never:

* modify schema manually
* bypass Alembic
* create schema drift

Whenever models change:

1. Generate migration
2. Review migration
3. Upgrade database
4. Test application
5. Test downgrade

No exceptions.

---

# API Rules

Every endpoint requires:

* request schema
* response schema
* validation
* error handling

Routers must remain thin.

Business logic belongs in services.

---

# React Rules

Every feature must support:

* loading state
* success state
* error state
* empty state

Every screen must be responsive.

Target:

* mobile
* tablet
* desktop

---

# Trading System Rules

For all trading functionality:

Prioritize:

1. Correctness
2. Risk management
3. Reliability
4. Performance

Never prioritize speed of development over correctness.

---

# Risk Management Requirements

Every strategy implementation must define:

* entry conditions
* exit conditions
* stop conditions
* failure conditions

No strategy is complete without risk controls.

---

# Quality Gates

Before marking work complete:

## Backend

* [ ] Type checks pass
* [ ] Lint passes
* [ ] Tests pass
* [ ] API validation verified

## Database

* [ ] Migration created
* [ ] Migration reviewed
* [ ] Upgrade tested
* [ ] Downgrade tested

## Frontend

* [ ] Mobile verified
* [ ] Tablet verified
* [ ] Desktop verified
* [ ] Error states verified

---

# Git Workflow

For every feature:

1. Create feature branch
2. Implement feature
3. Run validation
4. Run tests
5. Review changes
6. Commit changes
7. Push branch

Never commit broken code.

---

# Completion Checklist

Before declaring a task complete:

* [ ] Requirements satisfied
* [ ] Architecture respected
* [ ] Skills followed
* [ ] Tests pass
* [ ] Migrations validated
* [ ] Documentation updated
* [ ] No known defects introduced

If any checklist item fails, continue working until resolved.

---

# Agent Behavior

When uncertain:

* inspect existing code
* inspect project documents
* inspect skills
* ask for clarification

Never invent requirements.

Never assume behavior.

Never fabricate successful tests.

Never claim code works unless validated.

Evidence-based implementation only.


## ENVIRONMENT

```
OS:               Windows 10, PowerShell terminal
Python:           .\venv\Scripts\python.exe  — NEVER bare python or python3
Venv location:    .\venv\ in project root
Working dir:      ~\TWFA
Database:         PostgreSQL (local) — connection via DATABASE_URL env var
MT5 terminal:     JustMarkets MetaTrader 5 — metatrader5 pkg in venv only
Dashboard:        FastAPI + Jinja2, runs at http://127.0.0.1:8000
Auth:             JWT — access token in memory, refresh token in sessionStorage
```

**Environment variables (never hardcode these):**
```
DATABASE_URL        postgresql://trading:trading@localhost:5432/tradingwf
JWT_SECRET_KEY      [long random string — set before first run]
MT5_LOGIN           [broker login number]
MT5_PASSWORD        [broker password]
MT5_SERVER          [broker server name]
ANTHROPIC_API_KEY   [for AI advisor — optional]
```

---

## FILE EDITING RULES — CRITICAL — READ BEFORE TOUCHING ANY FILE

PowerShell corrupts file content when the Edit/Update tool uses str_replace.
This is a known Windows encoding bug that affects both Python and HTML files.

### Rule 1 — Never use Edit or Update on any .py or .html file
Always use the Write tool to write the complete file in a single call.

### Rule 2 — One Write per file per turn
Do not chain multiple Write calls to the same file. Write the complete content once.

### Rule 3 — Verify every .py file immediately after writing
```powershell
.\venv\Scripts\python.exe -c "import py_compile; py_compile.compile('path/to/file.py', doraise=True); print('OK')"
```
If syntax fails: rewrite the full file. Do not patch with Edit.

### Rule 4 — Verify every .html file immediately after writing
```powershell
.\venv\Scripts\python.exe -c "
content = open('dashboard/templates/file.html', encoding='utf-8').read()
assert '<html' in content and '</html>' in content, 'FAIL: broken HTML structure'
print('HTML OK, length=', len(content))
"
```

### Rule 5 — If Write fails, use Python to write the file
```powershell
.\venv\Scripts\python.exe -c "
with open('path/to/file.py', 'w', encoding='utf-8') as f:
    f.write('''<full file content here>''')
print('written')
"
```

### Rule 6 — Never create fix scripts
Do not create fix_indent.py, fix_main.py, patch_*.py, temp_*.py.
Fix the actual source file directly and immediately.
Delete any leftover fix scripts found in the project root.

### Rule 7 — Always use UTF-8 encoding
Every `open()` call must specify `encoding='utf-8'`.
Every file Write must produce UTF-8 output. No BOM characters.

---

## PYTHON RULES

### Indentation
- 4 spaces everywhere. No tabs. No 2-space. No 1-space.
- Verify with tokenize if uncertain:
```powershell
.\venv\Scripts\python.exe -c "
import tokenize
with open('file.py', 'rb') as f:
    tokens = list(tokenize.tokenize(f.readline))
tabs = [t for t in tokens if t.type == tokenize.INDENT and '\t' in t.string]
print('FAIL: tabs found' if tabs else 'OK: no tabs')
"
```

### Imports
- All imports at top of file
- Standard library first, then third-party, then local
- Never `import *`
- Never circular imports — check import order against project structure

### Type annotations
- All function signatures have type annotations
- Return type always annotated including `-> None`
- Use `from __future__ import annotations` at top of every file

### main.py structure — correct tail every time
```python
if __name__ == "__main__":
    args = parse_args()
    cfg  = PlatformConfig.from_env()

    engine = TradingEngine(cfg)
    if not args.dashboard_only:
        try:
            engine.init_mt5(login=args.login, password=args.password, server=args.server)
        except Exception as exc:
            log.error("MT5 init failed (%s) — dashboard will still start", exc)
        try:
            engine.start()
        except Exception as exc:
            log.error("Engine start failed (%s)", exc)
    else:
        log.info("Dashboard-only mode — skipping MT5 init")

    import uvicorn
    uvicorn.run(
        "dashboard.app:app",
        host=cfg.dashboard.host,
        port=cfg.dashboard.port,
        log_level="info",
    )
```

`uvicorn.run()` is always the last statement. Always inside `if __name__ == "__main__":`.
Never inside the `else:` branch. Never outside the `if __name__` block.

---

## PROJECT ARCHITECTURE

```
tradingwf/
├── alembic/                    # DB migrations — never skip these
│   ├── env.py
│   └── versions/
├── config/
│   ├── __init__.py
│   └── settings.py             # PlatformConfig — single source of all config
├── db/
│   ├── __init__.py
│   ├── models.py               # All SQLAlchemy ORM models
│   ├── session.py              # engine, SessionLocal, get_db()
│   └── settings_service.py    # DB-backed config overrides
├── auth/
│   ├── __init__.py
│   ├── service.py              # JWT, bcrypt
│   └── router.py               # /auth/* endpoints
├── data/
│   ├── __init__.py
│   ├── validator.py            # OHLCV integrity checks
│   └── repository.py           # OHLCV fetch + DB cache
├── strategies/
│   ├── __init__.py
│   ├── base.py                 # BaseStrategy, Signal, StrategyMeta, Side
│   ├── registry.py             # DB-backed registry: toggle, versioning
│   ├── momentum_reversion.py   # MomentumReversion  — BTCUSD  M15
│   ├── band_reversion.py       # BandReversion      — EURUSD  M15
│   ├── stochastic_trend.py     # StochasticTrend    — GBPUSD  M15
│   ├── session_breakout.py     # SessionBreakout    — XAUUSD  M15
│   ├── divergence_swing.py     # DivergenceSwing    — XAGUSD  M15
│   ├── vwap_reversion.py       # VWAPReversion      — AAPL    M5
│   └── macd_impulse.py         # MACDImpulse        — TSLA    M15
├── execution/
│   ├── __init__.py
│   ├── mt5_adapter.py
│   ├── mock_mt5.py
│   ├── sl_tp_model.py          # DynamicSLTPModel — sole source of SL/TP
│   ├── position_sizer.py       # PositionSizer — sole source of lot sizes
│   ├── order_manager.py
│   └── risk_manager.py
├── quant/
│   ├── __init__.py
│   ├── hypothesis.py
│   ├── backtest_engine.py
│   ├── walk_forward.py
│   └── optimiser.py
├── ml/
│   ├── __init__.py
│   ├── feature_engineer.py
│   ├── trainer.py
│   ├── predictor.py
│   └── model_store.py
├── ai_advisor/
│   ├── __init__.py
│   └── advisor.py
├── transcription/
│   ├── __init__.py
│   └── parser.py
├── journal/
│   ├── __init__.py
│   └── store.py
├── dashboard/
│   ├── app.py
│   ├── routes/
│   │   ├── account.py
│   │   ├── trades.py
│   │   ├── strategies.py
│   │   ├── quant.py
│   │   ├── ml.py
│   │   ├── ai_advisor.py
│   │   ├── transcription.py
│   │   └── settings.py
│   ├── templates/
│   │   ├── login.html
│   │   └── index.html
│   └── static/
│       ├── app.js
│       └── login.js
├── uploads/                    # Uploaded CSV/PDF files (temp storage)
├── ml_models/                  # Trained model artifacts (.joblib files)
├── logs/
│   ├── engine.log
│   └── engine_heartbeat
├── alembic.ini
└── main.py
```

---

## DATABASE RULES

### ORM only — never raw SQL
```python
# WRONG
db.execute("SELECT * FROM trades WHERE symbol = 'EURUSD'")

# CORRECT
db.query(Trade).filter(Trade.symbol == "EURUSD").all()
```

### Session management
```python
# Always use get_db() dependency in FastAPI routes
from db.session import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@router.get("/endpoint")
def endpoint(db: Session = Depends(get_db)):
    ...
```

### Migration discipline
- Every schema change requires a new Alembic migration
- Never call `Base.metadata.create_all()` after initial setup
- `create_all()` is only used in first-run startup and tests
- Generate migration: `.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "description"`
- Apply migration: `.\venv\Scripts\python.exe -m alembic upgrade head`

### Database models location
All ORM models are in `db/models.py`. Never define models elsewhere.
Import pattern: `from db.models import Trade, User, OHLCVBar, StrategyConfig`

### Key tables and their purpose
```
users                   — auth only. Never store trading data here.
trades                  — every executed trade (live + backtest + ai_advisor)
                          source of truth. trades.csv is DEPRECATED in v3.
account_snapshots       — periodic balance snapshots for equity curve
ohlcv_bars              — cached market data from MT5
strategy_configs        — persisted strategy params and toggle state
strategy_param_versions — param change history for rollback
backtest_runs           — backtest results with equity curves stored as JSON
hypotheses              — quant research hypothesis lifecycle
ml_models               — trained model metadata + artifact paths
ai_advisor_suggestions  — AI trade suggestions with full reasoning
trade_annotations       — user journal notes on trades
platform_settings       — dashboard-configurable overrides for all config
```

---

## CONFIGURATION RULES

### Single config singleton
```python
# Every module that needs config:
from config.settings import config

# Access:
config.risk.risk_per_trade
config.sltp.min_rr
config.dashboard.recent_trades_count
config.ai.enabled
```

### No hardcoded values anywhere
```python
# WRONG
if atr_pct < 0.003:
    regime = "ranging"

# CORRECT
if atr_pct < config.sltp.atr_pct_ranging_thresh:
    regime = "ranging"
```

### Settings override chain
Runtime order (later overrides earlier):
1. `config/settings.py` dataclass defaults
2. Environment variables (loaded in `PlatformConfig.from_env()`)
3. `platform_settings` DB table (read by `SettingsService`)

Dashboard changes always go to DB via `SettingsService`.
Engine reads effective config via `SettingsService.get_effective_risk_config()`.

### Environment variables
Load via `os.environ.get("VAR_NAME", default)` in `PlatformConfig.from_env()` only.
Never call `os.environ` anywhere else in the codebase.

---

## AUTHENTICATION RULES

### Every API endpoint requires JWT — no exceptions
```python
from auth.service import get_current_user
from db.models import User
from fastapi import Depends

@router.get("/protected")
def protected_endpoint(current_user: User = Depends(get_current_user)):
    ...
```

Only these endpoints are public (no auth):
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /login` (HTML page)

### Password handling
```python
# Store: always bcrypt
from auth.service import hash_password
user.hashed_password = hash_password(plain_password)

# Verify: always bcrypt
from auth.service import verify_password
if not verify_password(plain_password, user.hashed_password):
    raise HTTPException(401)
```

Never log passwords. Never return `hashed_password` in any API response.
Never store passwords in plaintext anywhere including logs.

### Token handling rules
- Access token: created by `auth.service.create_access_token()` — short-lived (30 min)
- Refresh token: created by `auth.service.create_refresh_token()` — long-lived (7 days)
- Frontend stores access token in `window.authToken` (memory only — lost on tab close)
- Frontend stores refresh token in `sessionStorage` (cleared on tab close)
- Never store access token in localStorage
- Never store access token in a cookie that is readable by JavaScript

### Login security
- Rate limit: track failed attempts in memory dict `{ip: [timestamps]}`
- Block after 5 failures in 15 minutes — return HTTP 429
- Log every attempt: `log.warning("Failed login: username=%s ip=%s", username, ip)`
- On success: `log.info("Login: username=%s ip=%s", username, ip)` + update `last_login`

---

## SECURITY RULES

### Input validation — use Pydantic models everywhere
```python
# WRONG — raw dict from request
def endpoint(body: dict):
    db.add(Trade(symbol=body["symbol"]))

# CORRECT — Pydantic model validates and sanitises
from pydantic import BaseModel, validator
class TradeCreate(BaseModel):
    symbol: str
    side:   str
    @validator("side")
    def validate_side(cls, v):
        if v not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        return v
```

### API security headers
Every response must include (set in FastAPI middleware):
```python
response.headers["X-Content-Type-Options"]  = "nosniff"
response.headers["X-Frame-Options"]         = "DENY"
response.headers["X-XSS-Protection"]        = "1; mode=block"
```

### CORS
Only allow `config.dashboard.cors_origins` — default is `["http://127.0.0.1:8000"]`.
Never use `allow_origins=["*"]` in production.

### Swagger UI
Disabled in production: `FastAPI(docs_url=None, redoc_url=None)`.

---

## STRATEGY RULES

### Naming convention
Strategies are named by behaviour, not by asset.
```
Class name         Display name          File
MomentumReversion  Momentum Reversion    momentum_reversion.py
BandReversion      Band Reversion        band_reversion.py
StochasticTrend    Stochastic Trend      stochastic_trend.py
SessionBreakout    Session Breakout      session_breakout.py
DivergenceSwing    Divergence Swing      divergence_swing.py
VWAPReversion      VWAP Reversion        vwap_reversion.py
MACDImpulse        MACD Impulse          macd_impulse.py
```

### param_bounds must exactly match default_params
This is enforced at import time by `BaseStrategy.__init_subclass__`.
If you add a param to `default_params`, add it to `param_bounds` in the same edit.
If keys mismatch, the class raises `ValueError` at import — fix before proceeding.

### No hardcoded values in strategy logic
```python
# WRONG
if rsi[-1] < 30:

# CORRECT
if rsi[-1] < self.params["rsi_oversold"]:
```

Every threshold is a param. Every period is a param. Every session hour is a param.

### generate_signal must never raise
```python
def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
    try:
        m15 = data.get("M15")
        if m15 is None or len(m15) < self.params["min_bars_required"]:
            log.debug("%s: insufficient data bars=%s", self.meta.name, len(m15) if m15 is not None else 0)
            return None
        # ... signal logic ...
    except Exception as exc:
        log.exception("%s: generate_signal error: %s", self.meta.name, exc)
        return None
```

### SL/TP always from DynamicSLTPModel
```python
# WRONG — strategy computes its own SL/TP
sl = close - atr * 1.5
tp = close + atr * 3.0

# CORRECT — model computes it
from execution.sl_tp_model import DynamicSLTPModel
sltp = DynamicSLTPModel()
result = sltp.compute(df=m15, side=side.value, entry=close)
if result is None:
    return None  # trade blocked by RR gate
signal.sl   = result.sl
signal.tp   = result.tp2
signal.tp1  = result.tp1
```

### Signal tag format
```python
signal.tag = f"{self.meta.name}.{'long' if side == Side.BUY else 'short'}"
```

### Strategy registry reads from DB
```python
# WRONG — hardcoded dict
REGISTRY = {"momentum_reversion": MomentumReversion, ...}

# CORRECT — DB-backed
from strategies.registry import StrategyRegistry
registry = StrategyRegistry(db)
enabled = registry.get_enabled()
```

The registry is seeded from class defaults on first run.
Subsequent runs read params from DB — preserving user changes across restarts.

---

## BACKTESTING RULES

### No look-ahead — this rule is absolute
```python
# WRONG — passes full dataframe to strategy
signal = strategy.generate_signal({"M15": full_m15_df})

# CORRECT — slices to current bar only
for i in range(warmup, n_bars):
    slice_data = {tf: df.iloc[:i+1] for tf, df in data.items()}
    signal = strategy.generate_signal(slice_data)
```

No exceptions. No "it's just for validation". No "the indicator is already computed".
If data after bar i is accessible during signal generation, it is look-ahead.

### Equity curve normalisation
```python
equity_curve = [1.0]  # always starts at 1.0
# After each trade:
equity += pnl_r * (equity * risk_per_trade)
equity_curve.append(equity / initial_equity)
```

### Partial close P&L
```python
# When both TP1 and TP2 are hit:
sl_dist  = abs(entry - original_sl)
tp1_rr   = abs(tp1 - entry) / sl_dist
tp2_rr   = abs(tp2 - entry) / sl_dist
net_r    = 0.5 * tp1_rr + 0.5 * tp2_rr   # 50% closed at each level

# When only SL hit after TP1 (BE stop):
net_r = 0.0   # breakeven — SL moved to entry after TP1

# When SL hit before TP1:
net_r = -1.0
```

### Data validation before every backtest
```python
from data.validator import validate
report = validate(df, symbol, timeframe)
if not report.is_valid:
    log.error("Backtest blocked: data validation failed: %s", report.issues)
    return empty_report
```

### scipy binomial test — use new API
```python
try:
    from scipy.stats import binomtest
    p_val = binomtest(n_wins, n_trades, 0.5, alternative="greater").pvalue
except ImportError:
    from scipy.stats import binom_test
    p_val = binom_test(n_wins, n_trades, 0.5, alternative="greater")
```

### BacktestRun persistence
Every backtest saves a `BacktestRun` record to DB with status "pending" before starting.
Status updates to "running", then "complete" or "failed".
equity_curve, drawdown_curve, monthly_returns stored as JSON columns.
Trades saved to `trades` table with `source="backtest"` and `backtest_run_id=run.id`.

---

## ML RULES

### TimeSeriesSplit — never shuffle time series
```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=config.ml.cv_folds)
# Never use: train_test_split(shuffle=True) on time series
```

### Feature engineering — no leakage
Features at bar[i] may only use data from bars 0..i.
Target at bar[i] uses bar[i + target_bars_forward].
Feature matrix and target series must be aligned and trimmed of NaN before training.

### CSV upload validation
```python
required_columns = {"open", "high", "low", "close"}
# Also accept: "datetime", "timestamp", "date", "time" for the index
# Rename to standard on load
# Run data.validator.validate() before using for training
```

### Model artifacts
Trained models saved as `.joblib` files in `ml_models/` directory.
Path stored in `MLModel.artifact_path` in DB.
On load: verify file exists before returning model.
If file missing: log error, return None — never crash the predictor.

### Prediction threshold
```python
if confidence < config.ml.prediction_threshold:
    log.debug("ML prediction below threshold: conf=%.3f threshold=%.3f", confidence, config.ml.prediction_threshold)
    return None
```

---

## AI ADVISOR RULES

### Never block the engine loop
AI advisor calls are async. Failures return None silently.
```python
try:
    suggestion = await advisor.suggest(symbol, timeframe, df, stats, trades)
except Exception as exc:
    log.error("AIAdvisor.suggest failed: %s", exc)
    suggestion = None
```

### Cooldown enforcement
```python
last_time = self._last_suggestion_time.get(symbol)
if last_time and (datetime.utcnow() - last_time).seconds < config.ai.cooldown_minutes * 60:
    log.debug("AIAdvisor: cooldown active for symbol=%s", symbol)
    return None
```

### Response parsing — always safe
```python
def _parse_response(self, text: str) -> dict | None:
    try:
        clean = text.replace("```json", "").replace("```", "").strip()
        data  = json.loads(clean)
        required = {"side", "confidence", "reasoning"}
        if not required.issubset(data.keys()):
            log.warning("AIAdvisor: response missing required keys: %s", required - data.keys())
            return None
        return data
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("AIAdvisor: parse failed: %s", exc)
        return None
```

### Confidence gate
```python
if data.get("confidence", 0) < config.ai.min_confidence_to_show:
    return None
```

---

## FRONTEND RULES

### No localStorage or sessionStorage for auth tokens
```javascript
// WRONG
localStorage.setItem('access_token', token);

// CORRECT
window.authToken = token;  // memory only — lost on refresh, re-fetched via refresh token
sessionStorage.setItem('refresh_token', refreshToken);  // OK for refresh token only
```

### All API calls use apiFetch (not raw fetch)
`apiFetch` is defined in `index.html` auth guard and attaches the JWT automatically.
```javascript
// WRONG
const res = await fetch('/api/account/stats');

// CORRECT
const res = await window.apiFetch('/api/account/stats');
```

### Chart.js lifecycle
Always destroy chart before recreating:
```javascript
if (chartRef.current) {
    chartRef.current.destroy();
}
chartRef.current = new Chart(canvas, config);
```

### No JSX without Babel CDN
Either use `React.createElement()` directly, or include Babel standalone CDN
and use `type="text/babel"` on script tags.

### Colour palette — use consistently across all charts
```javascript
const COLORS = {
    equity:     '#3B82F6',   // blue
    benchmark:  '#9CA3AF',   // grey
    drawdown:   'rgba(239,68,68,0.2)',  // red transparent
    win:        '#10B981',   // green
    loss:       '#EF4444',   // red
    neutral:    '#6B7280',   // grey
    accent:     '#8B5CF6',   // purple (ML predictions)
    ai:         '#F59E0B',   // amber (AI advisor)
};
```

### Poll interval
All auto-refresh intervals use `config.dashboard.poll_interval_ms` (from API settings).
Clean up intervals on component unmount:
```javascript
useEffect(() => {
    const id = setInterval(fetchData, pollInterval);
    return () => clearInterval(id);
}, [pollInterval]);
```

---

## LOGGING RULES

### One logger per module
```python
import logging
log = logging.getLogger(__name__)
# Resolves to e.g. "strategies.momentum_reversion"
```

Never use `logging.info(...)` directly. Always `log.info(...)`.
Never call `logging.basicConfig(...)` inside modules — only `main.py` configures handlers.

### Log levels
```
DEBUG     — internal state, variable values, loop counters (high volume, off by default)
INFO      — normal milestones: connected, signal generated, trade executed, strategy toggled
WARNING   — expected recoverable failures: no data, skipped session, retry attempt
ERROR     — unexpected failure blocking an action — does not crash the process
EXCEPTION — inside except blocks — includes full traceback (use log.exception not log.error)
CRITICAL  — process-level failure requiring immediate attention
```

### Required log events — always present
```
Engine start/stop                   log.info
MT5 connect/disconnect/reconnect    log.info
Strategy toggled active/inactive    log.info  (registry)
Signal generated                    log.info  symbol, side, entry, SL, TP
Trade executed                      log.info  symbol, side, lot, ticket
Trade blocked                       log.warning  reason
Risk limit hit                      log.warning  which limit, current value
Retry attempt                       log.warning  attempt N of M
Backtest started/completed/failed   log.info
ML training started/completed       log.info
AI suggestion generated             log.info  symbol, side, confidence
Failed login attempt                log.warning  username, ip
```

### Never log sensitive data
```python
# WRONG
log.info("Connecting: login=%d password=%s", login, password)

# CORRECT
log.info("Connecting: login=%d server=%s", login, server)
```

---

## ERROR HANDLING RULES

### Never bare except
```python
# WRONG
except:
    pass

# WRONG
except Exception:
    pass  # silent swallow

# CORRECT
except Exception as exc:
    log.exception("Context description failed: %s", exc)
    raise  # or return sentinel — never silently continue
```

### Every loop needs a retry limit
```python
MAX_RETRIES = config.engine.max_reconnect_attempts  # not a magic number
for attempt in range(1, MAX_RETRIES + 1):
    try:
        self.adapter.connect()
        log.info("Connected on attempt %d", attempt)
        break
    except ConnectionError as exc:
        log.warning("Connect attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
        if attempt == MAX_RETRIES:
            log.error("All %d connect attempts exhausted", MAX_RETRIES)
            raise
        time.sleep(config.engine.reconnect_delay_seconds)
```

### Trading-critical safety guards — never remove
Before any order is sent to MT5:
```python
if signal.sl is None or signal.tp is None:
    log.error("Order blocked: missing SL or TP for %s %s", strategy_name, signal.symbol)
    return None
if signal.lot_size <= 0:
    log.error("Order blocked: lot_size=%.5f for %s", signal.lot_size, strategy_name)
    return None
if signal.lot_size > config.risk.max_lot_size:
    log.error("Order blocked: lot_size=%.5f > max=%.5f", signal.lot_size, config.risk.max_lot_size)
    return None
```

### FastAPI error responses
```python
# All endpoints return structured errors — never raw exceptions
from fastapi import HTTPException
raise HTTPException(status_code=400, detail={"error": "specific description"})

# All endpoint handlers wrapped:
try:
    result = do_thing()
    return result
except SpecificError as exc:
    log.error("Endpoint /path failed: %s", exc)
    raise HTTPException(status_code=400, detail={"error": str(exc)})
except Exception as exc:
    log.exception("Unexpected error in /path: %s", exc)
    raise HTTPException(status_code=500, detail={"error": "Internal server error"})
```

---

## RUNNING THE PLATFORM

### First run setup
```powershell
# 1. Install dependencies
.\venv\Scripts\pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary passlib[bcrypt] python-jose[cryptography] python-multipart pandas numpy scipy scikit-learn scikit-optimize joblib pdfplumber python-docx aiofiles jinja2 anthropic httpx

# 2. Set environment variables
$env:DATABASE_URL = "postgresql://trading:trading@localhost:5432/tradingwf"
$env:JWT_SECRET_KEY = "your-long-random-secret-here"

# 3. Run migrations
.\venv\Scripts\python.exe -m alembic upgrade head

# 4. Start dashboard only (no MT5 needed)
.\venv\Scripts\python.exe main.py --dashboard-only

# 5. Open browser: http://127.0.0.1:8000/login
# Default credentials: admin / changeme123 — CHANGE IMMEDIATELY
```

### Full engine + dashboard
```powershell
.\venv\Scripts\python.exe main.py --login 12345678 --password yourpass --server JustMarkets-Live
```

### Session-aware mode
```powershell
.\venv\Scripts\python.exe main.py --mode session_aware --login 12345678 --password yourpass --server JustMarkets-Live
```

---

## DEBUGGING CHECKLIST

Run these before making any code changes:

```powershell
# 1. Syntax check all recently modified files
.\venv\Scripts\python.exe -m py_compile main.py config/settings.py db/models.py

# 2. All imports resolve
.\venv\Scripts\python.exe -c "
from config.settings import config
from db.session import engine
from db.models import Trade, User
from auth.service import hash_password
from strategies.registry import StrategyRegistry
from execution.sl_tp_model import DynamicSLTPModel
from quant.backtest_engine import BacktestEngine
print('All core imports OK')
"

# 3. DB connection
.\venv\Scripts\python.exe -c "
from db.session import engine
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('DB OK')
"

# 4. Dashboard smoke test
.\venv\Scripts\python.exe main.py --dashboard-only &
Start-Sleep 5
(Invoke-WebRequest http://127.0.0.1:8000/login -UseBasicParsing).StatusCode  # should be 200
(Invoke-WebRequest http://127.0.0.1:8000/api/account/stats -UseBasicParsing).StatusCode  # should be 401
Stop-Process -Name python -ErrorAction SilentlyContinue

# 5. Check engine.log for recent errors
Get-Content logs\engine.log -Tail 30

# 6. Check heartbeat freshness
$ts = [float](Get-Content logs\engine_heartbeat)
$age = [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $ts)
Write-Host "Heartbeat age: ${age}s (stale if > 120s)"
```

---

## KEY INVARIANTS — NEVER VIOLATE

These have been decided. Do not re-debate them.

```
1.  Never use Edit/Update tool on .py or .html — always Write full file
2.  Always .\venv\Scripts\python.exe — never bare python
3.  No look-ahead in backtester: slice_data = {tf: df.iloc[:i+1] ...}
4.  Config singleton: from config.settings import config everywhere
5.  No hardcoded values: every threshold/period/multiplier is a named param
6.  All DB writes via SQLAlchemy ORM — no raw SQL strings
7.  All API endpoints require JWT except /auth/login and /auth/refresh
8.  Passwords bcrypt only — never logged, never in API responses
9.  param_bounds.keys() == default_params.keys() — enforced at class load time
10. DynamicSLTPModel is the only source of SL/TP values
11. PositionSizer is the only source of lot sizes
12. Trade table is source of truth — trades.csv is deprecated
13. Registry reads from DB — strategy params and toggles persist across restarts
14. Equity curves start at 1.0: value[i] = cumulative_equity / initial_equity
15. All datetimes UTC — pd.to_datetime(index, utc=True) before every time filter
16. AI advisor never blocks engine loop — async, failures return None
17. Background tasks for backtest/optimise/ML train — never block FastAPI event loop
18. Platform settings in DB override config defaults — use SettingsService
19. uvicorn.run() is always last statement inside if __name__ == "__main__"
20. Never create fix_*.py scripts — fix the actual file
```

---

## WHAT NEVER TO DO

```
× Never use Edit/Update tool on any .py or .html file
× Never use bare python or python3
× Never create fix_*.py, patch_*.py, temp_*.py scripts
× Never hardcode a number, threshold, or string that belongs in config
× Never write raw SQL — use SQLAlchemy ORM
× Never store passwords in plaintext
× Never return hashed_password in any API response
× Never log passwords, MT5 credentials, or JWT tokens
× Never use shuffle=True on time series data in ML training
× Never use localStorage for tokens
× Never call logging.basicConfig() inside modules (only main.py)
× Never pass full df to generate_signal inside backtest loop (look-ahead)
× Never compute SL/TP inside a strategy — use DynamicSLTPModel
× Never compute lot size inside a strategy — use PositionSizer
× Never skip Alembic migration for schema changes
× Never allow a GET endpoint to modify database state
× Never place uvicorn.run() inside the else: branch of dashboard-only check
× Never move uvicorn.run() outside if __name__ == "__main__":
× Never skip py_compile verification after writing a .py file
× Never skip Jinja2 verification after writing a .html template
× Never remove an existing try/except block — improve it, never delete it
× Never remove an existing log call — improve it, never delete it
× Never commit trades.csv, engine_heartbeat, or any file in logs/
× Never commit .env files or files containing credentials
× Never commit directly to main or master branch
```

---

## DECISIONS MADE — DO NOT REVISIT

```
Language:         Python 3.11+
Database:         PostgreSQL via SQLAlchemy ORM + Alembic
Auth:             JWT (python-jose) + bcrypt (passlib)
Web framework:    FastAPI + Jinja2 + uvicorn
Frontend:         React via CDN (no build step) + Chart.js + Tailwind CDN
SL/TP:            DynamicSLTPModel — ATR-scaled, regime-aware, tiered TP
Position sizing:  PositionSizer — fixed-fractional from account equity
Backtesting:      Bar-by-bar event loop, no vectorised look-ahead
Optimisation:     Grid search (≤3 params) or Bayesian (4+ params, scikit-optimize)
ML models:        scikit-learn (RandomForest, GradientBoosting, Logistic)
AI advisor:       Anthropic Claude API (claude-sonnet-4-20250514)
Strategy naming:  By behaviour (MomentumReversion) not by asset (BTCStrategy)
Trade storage:    Trade DB table — trades.csv deprecated
Config override:  platform_settings DB table overrides config.py defaults
File editing:     Write tool only — Edit tool banned on .py and .html
```