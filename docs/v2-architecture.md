# v2 Backend Architecture

## Why v2 exists

All new API endpoints must live in `dashboard/v2/`. The existing
`dashboard/app.py` (v1) is frozen — never edit it. Mounting a separate
FastAPI instance under `/api/v2/` means new features can be added,
tested, and rolled back without risking the production dashboard.

## Directory layout

```
dashboard/
├── app.py                          # v1 — FROZEN, never edit
├── templates/                      # v1 Jinja2 templates (frozen)
├── static/                         # v1 static assets (frozen)
└── v2/                             # ← all new code goes here
    ├── __init__.py                 # package marker
    ├── app.py                      # FastAPI instance — the only file that
    │                               # creates routes/mounts
    └── routes/
        ├── __init__.py             # package marker
        ├── engine.py               # engine status, logs, heartbeat
        ├── monitoring.py            # MT5 account, positions, orders
        ├── backtest.py              # backtest runs, results
        └── <feature>.py             # one file per feature domain
```

## How v2 is wired into main.py

`main.py` mounts v2 onto v1:

```python
v1_app = __import__("dashboard.app", fromlist=["app"]).app
v2_app = __import__("dashboard.v2.app", fromlist=["app"]).app
v1_app.mount("/api/v2", v2_app)
```

All v2 routes are therefore accessible under `/api/v2/...`.

## Adding a new v2 route

1. Create a new file in `dashboard/v2/routes/`:

   ```python
   # dashboard/v2/routes/my_feature.py
   from fastapi import APIRouter, Depends
   from sqlalchemy.orm import Session
   from db.session import get_db

   router = APIRouter()

   @router.get("/my-feature/list")
   def list_items(db: Session = Depends(get_db)):
       return {"items": []}
   ```

2. Register it in `dashboard/v2/app.py`:

   ```python
   from dashboard.v2.routes import engine, monitoring, backtest, my_feature

   app.include_router(engine.router)
   app.include_router(monitoring.router)
   app.include_router(backtest.router)
   app.include_router(my_feature.router)
   ```

3. Done — the endpoint is live at `/api/v2/my-feature/list`.

## Import rules — never break these

- **Never import from `dashboard.app`** into v2 code — it creates
  circular dependency.
- **Never import from v2 into `dashboard.app`**.
- Shared dependencies (DB session, config) come from:
  - `config.settings` — the `config` singleton
  - `db.session` — `engine`, `SessionLocal`, `get_db()`
  - `db.models` — ORM models

## Error handling

`dashboard/v2/app.py` has a global exception handler that catches
unhandled exceptions and returns JSON:

```python
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    log.exception("v2 unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc)})
```

Individual routes should still use try/except for expected errors
and raise `HTTPException` for client-facing failures.

## MT5 adapter in v2 routes

Use the lazy-loading pattern from `monitoring.py`:

```python
def _get_adapter():
    try:
        from execution.mt5_adapter import MT5Adapter
        return MT5Adapter()
    except Exception:
        return None
```

This avoids importing MetaTrader5 at module load time (which fails
outside an MT5 terminal). The adapter is only instantiated when
a request hits the endpoint.

## Config access

```python
from config.settings import config

# read-only — never mutate config at runtime
config.risk.max_open_positions
config.engine.poll_interval_seconds
config.dashboard.recent_trades_count
```

## Frontend integration

v2 endpoints are called by the v1 frontend (same domain, no CORS issues).
Use the existing `window.apiFetch()` helper in `index.html` which
auto-attaches the JWT token and handles 401 refresh flows.

Example frontend call:

```javascript
const res = await window.apiFetch('/api/v2/engine/status');
const data = await res.json();
```

## Security

- All v2 endpoints inherit JWT auth from the v1 middleware — no
  additional auth decorators needed unless you want per-route exclusions.
- For public endpoints (no auth), add a dedicated route outside the
  protected router, or handle `HTTPException` 401 gracefully in the
  frontend.

## Checklist before committing v2 changes

- [ ] Route handler imports `get_db` or `_get_adapter`, never bare
- [ ] No imports from `dashboard.app` anywhere in v2/
- [ ] All DB queries use SQLAlchemy ORM (no raw SQL)
- [ ] New route registered in `dashboard/v2/app.py`
- [ ] `py_compile` passes on modified files
- [ ] Commit to a feature branch — never directly to main
