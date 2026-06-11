"""engine/routes.py — HTTP endpoints for engine monitoring.

Mount at /api/v2/engine in main.py (already done).

All endpoints are public (no auth required) because they only expose
operational state, not sensitive data. The engine heartbeat and MT5
connection status are visible to anyone who can reach the server, so
firewall exposure rules should be followed as per config.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from engine.state import snapshot

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
def engine_status() -> JSONResponse:
    """Return current engine state snapshot.

    Fields
    ------
    running : bool
        True while the engine loop is alive.
    started_at_iso : str | None
        ISO timestamp when the engine thread was created.
    last_iteration_iso : str | None
        ISO timestamp of the most recent successful loop iteration.
    circuit_breaker_tripped : bool
        True if the daily loss limit was breached.
    today_date : str
        YYYY-MM-DD of the current trading day (UTC).
    daily_pnl : float
        Net realised PnL for today (live trades only, in account currency).
    mt5_connected : bool
        True if MT5 reported a live connection in the last iteration.
    last_scan_signals_generated : int
        Signals produced in the most recent scan pass.
    last_scan_trades_executed : int
        Orders successfully submitted in the most recent pass.
    """
    return JSONResponse(snapshot())


@router.get("/health")
def engine_health() -> JSONResponse:
    """Lightweight health check used by infrastructure monitors.

    Returns 200 with {"ok": true} if the engine thread was started at
    some point in the last 5 minutes.
    Returns 503 with {"ok": false, "reason": "..."} if no heartbeat
    has been received within that window.
    """
    import time
    data = snapshot()
    last_iter = data.get("last_iteration_ts") or data.get("started_at", 0)
    try:
        # snapshot() returns iso strings — the state module has raw floats
        # accessible via a different path. Fall back gracefully.
        last_iter = max(
            _ts_from_iso(data.get("last_iteration_iso")),
            _ts_from_iso(data.get("started_at_iso")),
        )
    except Exception:
        last_iter = 0
    age_s = time.time() - last_iter if last_iter else 9999
    if age_s > 300:
        return JSONResponse(
            {"ok": False, "reason": f"stale heartbeat ({age_s:.0f}s)"},
            status_code=503,
        )
    return JSONResponse({"ok": True})


def _ts_from_iso(val: str | None) -> float:
    if not val:
        return 0.0
    from datetime import datetime, timezone
    try:
        return datetime.fromisoformat(val).timestamp()
    except Exception:
        return 0.0
