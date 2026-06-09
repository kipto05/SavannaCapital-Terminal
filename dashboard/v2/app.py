"""dashboard/v2/app.py - isolated FastAPI app for new features.

Mount point: /api/v2/
All routes are prefixed with /api/v2/ by the caller (main.py).

Never import from dashboard/app.py here - it creates a circular dependency.
All shared state (DB, config) comes from config.settings and db.session.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from config.settings import config
from dashboard.v2.routes import backtest, engine, monitoring

log = logging.getLogger(__name__)

app = FastAPI(
    title="Savanna Capital Quant OS v2",
    description="New features — isolated from dashboard v1",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount routers — each module defines its own APIRouter
app.include_router(engine.router)
app.include_router(monitoring.router)
app.include_router(backtest.router)


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
            "max_open_positions": config.risk.max_open_positions,
            "max_daily_loss_pct": config.risk.max_daily_loss_pct,
            "max_lot_size": config.risk.max_lot_size,
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("v2 unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
