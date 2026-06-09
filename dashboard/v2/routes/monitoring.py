"""dashboard/v2/routes/monitoring.py - MT5 monitoring endpoints.

Enhanced versions of the existing /api/mt5/* endpoints, living in v2
so the original endpoints are never touched.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.settings import config
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()


def _get_adapter():
    """Lazy-load the MT5 adapter - returns None if MT5 is not installed."""
    try:
        from execution.mt5_adapter import MT5Adapter
        return MT5Adapter()
    except Exception:
        return None


@router.get("/mt5/account")
def get_mt5_account():
    """Return live MT5 account info."""
    adapter = _get_adapter()
    if not adapter:
        return {"error": "MT5 adapter unavailable", "connected": False}
    try:
        info = adapter.account_info()
        if info is None:
            return {"error": "No account info available", "connected": False}
        info.setdefault("login", config.mt5.login)
        info["connected"] = True
        return info
    except Exception as exc:
        log.warning("MT5 account fetch failed: %s", exc)
        return {"error": str(exc), "connected": False}


@router.get("/mt5/positions")
def get_mt5_positions(symbol: str = ""):
    """Return open MT5 positions, optionally filtered by symbol."""
    adapter = _get_adapter()
    if not adapter:
        return []
    try:
        positions = adapter.positions_get(symbol) or []
        for p in positions:
            p["account"] = str(config.mt5.login) if config.mt5.login else "default"
        return positions
    except Exception as exc:
        log.warning("MT5 positions fetch failed: %s", exc)
        return []


@router.get("/mt5/orders")
def get_mt5_orders(symbol: str = ""):
    """Return pending MT5 orders."""
    adapter = _get_adapter()
    if not adapter:
        return []
    try:
        orders = adapter.orders_get(symbol) or []
        for o in orders:
            o["account"] = str(config.mt5.login) if config.mt5.login else "default"
        return orders
    except Exception as exc:
        log.warning("MT5 orders fetch failed: %s", exc)
        return []


@router.get("/mt5/connection")
def get_mt5_connection():
    """Quick health check - is MT5 connected right now?"""
    adapter = _get_adapter()
    if not adapter:
        return {"connected": False, "reason": "adapter unavailable"}
    return {
        "connected": adapter._connected,
        "login": config.mt5.login,
        "server": config.mt5.server,
    }
