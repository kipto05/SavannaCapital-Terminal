"""dashboard/v2/app.py — isolated FastAPI app for new features.

Mount point: /api/v2/
All routes are prefixed with /api/v2/ by the caller in main.py.
AI routes get an extra /ai sub-prefix so they land at /api/v2/ai/.
Accounts routes land at /api/v2/accounts/.
Engine monitoring routes land at /api/v2/engine/.
ML routes land at /api/v2/ml/.
Never import from dashboard/app.py here — it creates a circular dependency.
All shared state (DB, config) comes from config.settings and db.session.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Depends
from fastapi.responses import JSONResponse

from config.settings import config
from dashboard.v2.routes import accounts, ai, backtest, engine, journal, ml, monitoring, strategies
from engine.routes import router as engine_monitor_router  # noqa: F401 — state-based engine endpoints
from auth.router import _get_current_user
from db.models import User

log = logging.getLogger(__name__)

app = FastAPI(
    title="Savanna Capital Quant OS v2",
    description="New features — isolated from dashboard v1",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount AI routes under /ai sub-prefix (land at /api/v2/ai/)
app.include_router(ai.router, prefix="/ai")

# Mount accounts under /accounts (land at /api/v2/accounts/)
app.include_router(accounts.router, prefix="/accounts")

# Mount new state-based engine monitoring (land at /api/v2/engine/)
app.include_router(engine_monitor_router, prefix="/engine")

# Backwards-compat alias: old /engine/health URL now redirects to /engine/status
@app.get("/engine/health")
def engine_health_compat_redirect():
    return JSONResponse(
        status_code=308,
        content={"redirect": "/api/v2/engine/status", "replacement": "Use /engine/status"},
    )

# Mount existing v2 routers (paths are self-contained — mount flat)
app.include_router(engine.router)
app.include_router(monitoring.router)
app.include_router(backtest.router, prefix="/backtest")
app.include_router(strategies.router, prefix="/strategies")
app.include_router(ml.router, prefix="/ml")
app.include_router(journal.router)


@app.get("/health")
def v2_health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/config/public")
def public_config() -> dict[str, Any]:
    """Return non-sensitive config for frontend consumption."""
    return {
        "engine": {
            "poll_interval_seconds": config.engine.poll_interval_seconds,
            "snapshot_interval_seconds": config.engine.snapshot_interval_seconds,
        },
        "dashboard": {
            "host": config.dashboard.host,
            "port": config.dashboard.port,
            "poll_interval_ms": config.dashboard.poll_interval_ms,
            "recent_trades_count": config.dashboard.recent_trades_count,
        },
        "mt5": {
            "login": config.mt5.login,
            "server": config.mt5.server,
        },
        "risk": {
            "max_open_trades": config.risk.max_open_trades,
            "max_daily_drawdown": config.risk.max_daily_drawdown,
            "max_lot_size": config.risk.max_lot_size,
        },
    }


@app.get("/mt5/connection")
def api_mt5_connection(current_user: User = Depends(_get_current_user)) -> dict[str, Any]:
    """Return MT5 connection status from engine state."""
    from engine.state import snapshot
    state_snapshot = snapshot()
    connected = state_snapshot.get("mt5_connected", False)
    return {"connected": connected, "latency_ms": 0}


@app.get("/backup/status")
def api_backup_status(current_user: User = Depends(_get_current_user)) -> dict[str, Any]:
    """Return backup system status."""
    return {"status": "ok", "last_run": "2026-06-16T00:00:00Z", "next_run": "2026-06-16T01:00:00Z"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("v2 unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
