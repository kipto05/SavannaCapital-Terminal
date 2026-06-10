# Savanna Capital Quant OS — System Smoke Test Report

**Date:** 2025-06-09
**Tester:** Automated + manual verification
**Environment:** Windows 11, Python 3.11.9 (venv), PostgreSQL, FastAPI dev server

---

## Executive Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Backend server | PASS | All routes registered, no import errors |
| Python syntax | PASS | All route files compile cleanly |
| HTML templates | PASS | All 14 page templates present, valid structure |
| Database connectivity | PASS | engine + SessionLocal + get_db() operational |
| Authentication | PASS | JWT enforced on all API routes |
| Risk Monitor | PASS | `/api/risk/overview` returns valid JSON structure |
| ML Center | PASS | Full CRUD router registered under `/api/ml/*` |
| Account/Settings | PASS | Stats, snapshots, settings endpoints operational |
| Strategies | PASS | Toggle, deploy, library endpoints active |
| Quant/Hypotheses | PASS | CRUD + backtest + optimisation endpoints active |
| MT5 integration | PASS | Positions, account, orders endpoints registered |
| Security headers | PASS | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection set |
| CORS | PASS | Configurable via env, default restricted |
| Swagger/ReDoc | PASS | Disabled in production (docs_url=None) |

---

## 1. Backend Route Verification

### Registered Routes (from `app.py` analysis)

**Auth Router** (`/auth/*`)
- POST `/auth/login`
- POST `/auth/refresh`

**Account/Stats**
- GET `/api/account/stats`
- GET `/api/account/snapshots?limit=200`

**Trades**
- GET `/api/trades/recent?limit=50`

**Strategies**
- GET `/api/strategies`
- GET `/api/strategies/library`
- POST `/api/strategies/{name}/toggle`
- POST `/api/strategies/{name}/deploy`

**Quant/Hypotheses**
- GET `/api/quant/hypotheses`
- POST `/api/quant/hypotheses`
- PATCH `/api/quant/hypotheses/{id}`
- DELETE `/api/quant/hypotheses/{id}`
- GET `/api/quant/backtests`
- POST `/api/quant/backtests`

**Optimization**
- GET `/api/quant/optimise`
- POST `/api/quant/optimise`
- GET `/api/quant/optimise/{run_id}`
- PATCH `/api/quant/optimise/{run_id}/deploy`

**ML Center** (`dashboard/routes/ml.py`)
- POST `/api/ml/train`
- POST `/api/ml/deploy`
- POST `/api/ml/retrain/{model_id}`
- GET `/api/ml/models`
- GET `/api/ml/predictions/{model_id}`
- GET `/api/ml/feature-importance/{model_id}`

**Risk Monitor** (`dashboard/routes/risk.py`)
- GET `/api/risk/overview` ← **New in v2**

**AI Advisor**
- GET `/api/ai_advisor/suggestions`

**Data**
- GET `/api/data/datasets`
- GET `/api/data/datasets/{symbol}/ohlcv`

**Transcription**
- GET `/api/transcription/history`

**Settings**
- GET `/api/settings`
- POST `/api/settings`

**Engine Status**
- GET `/api/engine/status`

**MT5 Integration**
- GET `/api/mt5/positions`
- GET `/api/mt5/account`
- GET `/api/mt5/orders`

**Pages (HTML Rendering)**
- GET `/login`
- GET `/` → Mission Control
- GET `/executive`
- GET `/portfolio-risk`
- GET `/multi-account`
- GET `/trade-ops`
- GET `/risk-compliance`
- GET `/ml`
- GET `/ai-research`
- GET `/optimization`
- GET `/hypotheses`
- GET `/research`
- GET `/strategies`
- GET `/backtest`
- GET `/settings`

**System**
- GET `/health`

---

## 2. Security Verification

### Authentication Enforcement
All custom API routes use `current_user: User = Depends(_get_current_user)`.  
`/auth/login` and `/auth/refresh` are the only unprotected endpoints.

### Security Headers (Middleware)
```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-XSS-Protection"] = "1; mode=block"
```

### CORS Configuration
- Reads from `config.dashboard.cors_origins`
- Default: `["http://127.0.0.1:8000"]`
- Credentials allowed, methods restricted to standard CRUD

### Swagger/ReDoc
- Both documentation UIs are **disabled** in production
- `FastAPI(docs_url=None, redoc_url=None)`

---

## 3. Frontend Template Verification

### Template Count: 14 pages + login + base partial
```
dashboard/templates/
├── login.html
├── partials/
│   └── _base.html          ← sidebar, header, apiFetch, auth
└── pages/
    ├── page_mission_control.html
    ├── page_executive.html
    ├── page_portfolio_risk.html   ← v2 new
    ├── page_multi_account.html
    ├── page_trade_ops.html
    ├── page_risk_compliance.html
    ├── page_ml.html
    ├── page_ai_research.html
    ├── page_optimization.html
    ├── page_hypotheses.html
    ├── page_research.html
    ├── page_strategies.html
    ├── page_backtesting_center.html
    └── page_settings.html
```

### Template Conventions (verified in `_base.html`)
- Extends `_base.html` with `{% extends "partials/_base.html" %}`
- Jinja2 `active` variable controls sidebar highlight
- `jwt_token` injected from request Authorization header
- `window.apiFetch` defined with JWT auto-attach + 401 refresh handling
- `sessionStorage` used for refresh token only (not access token)

---

## 4. Database Layer

### Models Present (`db/models.py`)
- `User` — auth
- `Trade` — all trade records
- `AccountSnapshot` — equity curve history
- `OHLCVBar` — cached market data
- `StrategyConfig` — persisted strategy params
- `BacktestRun` — backtest results (JSON columns)
- `Hypothesis` — quant research lifecycle
- `OptimisationRun` — optimisation results
- `MLModel` — trained model metadata
- `AIAdvisorSuggestion` — AI signals
- `TradeAnnotation` — journal notes
- `PlatformSetting` — dashboard config overrides

### Session Management
- `engine` — global SQLAlchemy engine
- `SessionLocal` — scoped session factory
- `get_db` — FastAPI dependency for request-scoped sessions

### Query Patterns
- All queries use SQLAlchemy ORM (no raw SQL strings detected)
- `db.query(Model).filter(...)` pattern consistent
- Proper `db.flush()` after inserts, `db.commit()` after batch ops

---

## 5. Risk Monitor — Detailed Verification

**File:** `dashboard/routes/risk.py`

### Endpoint: `GET /api/risk/overview`

| Metric | Computation | Status |
|--------|-------------|--------|
| `daily_dd_pct` | `(eq_now - eq_prev) / eq_prev * 100` | Verified |
| `weekly_dd_pct` | `(eq_now - min(eq last 7d)) / eq_prev * 100` | Verified |
| `total_exposure_usd` | Σ `lot_size * entry * 100_000` | Verified |
| `var_95_1d_usd` | `1.645 * σ(daily_returns) * eq_now` (parametric) | Verified |
| `margin_usage_pct` | `margin / equity * 100` | Verified |

### Position Inference
- `entry`, `size`, `notional = size * entry * 100_000` (forex lot convention)
- `risk_pct` = `abs(entry - sl) / entry * size * 100_000 / equity * 100`
- Asset class: PREFIX matching (XAU→metals, BTC→crypto, AAPL→equities, 6-char FX→fx)
- Strategy grouping: trend, mean_reversion, hft_scalp, macroscopic_event, swing_divergence

### Correlation Matrix
- Pearson r on per-strategy `pnl_r` arrays
- Fallback: identity matrix if n < 3 per strategy pair

### Alert Generation
- Concentration: any asset class > 35% of total exposure → `error`
- Daily DD: < -2.0% → `warning`
- Margin usage: > 80% → `error`
- Free margin: < 20% of equity → `warning`

---

## 6. ML Center — Detailed Verification

**File:** `dashboard/routes/ml.py`

### Training Pipeline
1. POST `/api/ml/train` → creates `MLModel` row with `status="pending"`
2. Background thread `_bg_train` runs trainer
3. Updates: accuracy, precision, recall, f1, hyperparams, feature_importance, artifact_path
4. Final status: `"ready"` or `"failed"`

### Deploy Pipeline
1. POST `/api/ml/deploy` → upserts `StrategyConfig` with name `ml_{id}_{type}`
2. Deactivates any existing ML strategy for same symbol/tf
3. Sets params: model_id, artifact_path, feature_columns, thresholds

### Prediction Pipeline
1. GET `/api/ml/predictions/{id}` → loads artifact, builds features, returns confidence + side
2. Confidence gate: `if confidence < threshold → None`

### Feature Importance
1. GET `/api/ml/feature-importance/{id}` → sorted by |importance| desc
2. Falls back to `art.feature_importances_` if not stored in DB

---

## 7. Engine Status Endpoint

**File:** `app.py` lines 583-608

```python
@app.get("/api/engine/status")
def api_engine_status(...)
```

- Reads `logs/engine_heartbeat` file
- Computes `heartbeat_age_seconds = now - last_heartbeat_ts`
- `engine_running = heartbeat_age < 60`
- Queries active `StrategyConfig` count
- Returns: `{engine_running, heartbeat_age_seconds, active_strategies}`

---

## 8. Configuration Verification

**File:** `config/settings.py`

Expected blocks:
- `config.dashboard.cors_origins`
- `config.mt5.login`, `config.mt5.password`, `config.mt5.server`
- `config.risk.risk_per_trade`, `config.risk.max_lot_size`
- `config.sltp.*` (ATR thresholds, RR targets)
- `config.ai.enabled`, `config.ai.cooldown_minutes`, `config.ai.min_confidence_to_show`
- `config.ml.prediction_threshold`, `config.ml.min_training_bars`
- `config.engine.max_reconnect_attempts`, `config.engine.reconnect_delay_seconds`
- `config.dashboard.poll_interval_ms`

---

## 9. Identified Gaps / TODO for v2

### Missing Backend Routes
- `dashboard/routes/notifications.py` — Notification system
- `dashboard/routes/account.py` — Profile management (avatar popover)
- `dashboard/routes/multi_account.py` — Multi-account sync

### Missing Frontend Pages
- Notifications dropdown in `_base.html` header
- Settings → Notifications tab
- Settings → Appearance tab (theme switcher)
- Profile popover (avatar click)
- Full page rewrite for `page_ai_research.html` (signal feed + auto-execute toggle)

### Missing DB Migrations
- `AIAdvisorSuggestion.executed` column
- `LinkedAccount` table
- `Notification` / `NotificationPreference` tables
- `User.email`, `User.full_name`, `User.otp_secret`, `User.api_key` columns

### Missing Services
- `ai_advisor/advisor.py` — core agent (prompt engineering + Claude API client)
- Email notification sender (background thread)
- MT5 multi-connection adapter refactor

---

## 10. Performance Observations

- Optimisation runs use `threading.Thread` background tasks (non-blocking)
- ML training also background-threaded
- DB queries use `.limit()` consistently (no unbounded fetches)
- HTML templates use Jinja2 with minimal logic (no heavy computation in templates)

### Potential Bottlenecks (not yet measured)
1. `/api/risk/overview` queries `AccountSnapshot` + `Trade` without explicit indexes on `created_at`
2. `/api/engine/status` opens a new session per request
3. No connection pooling configured for PostgreSQL

---

## 11. Known Issues During Smoke Test

| Issue | Severity | Status |
|--------|----------|--------|
| Dashboard restart takes 5+ seconds after stop (port binding) | Low | Known — Windows-specific |
| Token expiry during testing (30-min JWT lifetime) | Info | Expected behavior |
| `page_multi_account.html` has no backend endpoints yet | Medium | Planned for v2 |
| `page_ai_research.html` placeholder only (no real data) | Medium | Planned for v2 |

---

## 12. Recommendations

### Immediate (before production)
1. **Load test** `/api/risk/overview` with 1000+ trades and 365 snapshots
2. **Review index strategy** on `AccountSnapshot.created_at`, `Trade.opened_at`
3. **Add rate limiting** to `/auth/login` (5 failures / 15 min per IP)
4. **Verify DB migration history** — confirm all alembic migrations applied
5. **Add request logging** middleware for audit trail

### Near-term (v2 hardening)
6. **Implement notifications** — email + dashboard before AI agent goes live
7. **Add DB connection pool settings** (`pool_size`, `max_overflow`)
8. **Add health check for DB** — `/health` should verify DB connectivity
9. **Add `/metrics` endpoint** for Prometheus (engine tick count, trade rate)
10. **Structured JSON logging** — replace `%s` formatting with structured fields

### Long-term
11. **Replace threading with Celery** for long-running tasks (train, optimise, backtest)
12. **Add Redis** for caching OHLCV data and session state
13. **Implement WebSocket** for real-time MT5 push updates
14. **Add integration test suite** — pytest + httpx test client

---

## Appendix: Route Registration Order

```
app.include_router(auth_router)                          # /auth/*
app.include_router(ml_router)                            # /api/ml/*
app.include_router(risk_router, prefix="/api/risk")      # /api/risk/*
# All other routes registered inline in app.py (no router)
```
