"""dashboard/v2/routes/monitoring.py - MT5 monitoring endpoints.

Enhanced versions of the existing /api/mt5/* endpoints, living in v2
so the original endpoints are never touched.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.settings import config
from db.session import get_db

try:
    import MetaTrader5 as _mt5_pkg
except ImportError:
    _mt5_pkg = None  # type: ignore[assignment]

log = logging.getLogger(__name__)
router = APIRouter()


def _try_initialize() -> bool:
    """Attempt a best-effort MT5 initialise if not already connected.

    Returns True if connected (or initialise succeeded), False otherwise.
    """
    if _mt5_pkg is None:
        return False
    try:
        info = _mt5_pkg.account_info()
        if info is not None:
            return True
        _mt5_pkg.initialize(
            path=config.mt5.path,
            login=config.mt5.login,
            password=config.mt5.password,
            server=config.mt5.server,
            timeout=config.mt5.timeout,
        )
        return _mt5_pkg.account_info() is not None
    except Exception:
        return False


def _connected() -> bool:
    """Return True if the MT5 package reports an active connection."""
    if _mt5_pkg is None:
        return False
    try:
        return _mt5_pkg.account_info() is not None
    except Exception:
        return False


@router.get("/mt5/account")
def get_mt5_account():
    """Return live MT5 account info."""
    if not _try_initialize():
        return {"error": "MT5 adapter unavailable", "connected": False}
    try:
        if _mt5_pkg is None:
            return {"error": "MT5 package not available", "connected": False}
        info = _mt5_pkg.account_info()
        if info is None:
            return {"error": "No account info available", "connected": False}
        data: dict[str, Any] = info._asdict()
        data.setdefault("login", config.mt5.login)
        data["connected"] = True
        return data
    except Exception as exc:
        log.warning("MT5 account fetch failed: %s", exc)
        return {"error": str(exc), "connected": False}


@router.get("/mt5/accounts")
def get_mt5_accounts():
    """List configured MT5 accounts for the account selector dropdown.

    V1 returns a single account (the one configured in .env).
    Future: multiple accounts -> returns list of all registered accounts.
    """
    if not _try_initialize():
        return []
    try:
        if _mt5_pkg is None:
            return []
        info = _mt5_pkg.account_info()
        if info is None:
            return []
        d = info._asdict()
        login = d.get("login") or config.mt5.login
        server = d.get("server") or config.mt5.server
        return [{
            "login": login,
            "server": server,
            "name": d.get("name", f"Account {login}"),
            "balance": d.get("balance", 0),
            "equity": d.get("equity", 0),
            "currency": d.get("currency", "USD"),
        }]
    except Exception as exc:
        log.warning("MT5 accounts fetch failed: %s", exc)
        return []


@router.get("/mt5/positions")
def get_mt5_positions(symbol: str = ""):
    """Return open MT5 positions, optionally filtered by symbol."""
    if not _connected():
        return []
    try:
        if _mt5_pkg is None:
            return []
        positions = _mt5_pkg.positions_get(symbol=symbol or None) or []
        for p in positions:
            p["account"] = str(config.mt5.login) if config.mt5.login else "default"
            if hasattr(p, "_asdict"):
                p = p._asdict()
        return [p if isinstance(p, dict) else p._asdict() for p in positions]
    except Exception as exc:
        log.warning("MT5 positions fetch failed: %s", exc)
        return []


@router.get("/mt5/orders")
def get_mt5_orders(symbol: str = ""):
    """Return pending MT5 orders."""
    if not _connected():
        return []
    try:
        if _mt5_pkg is None:
            return []
        orders = _mt5_pkg.orders_get(symbol=symbol or None) or []
        for o in orders:
            o["account"] = str(config.mt5.login) if config.mt5.login else "default"
            if hasattr(o, "_asdict"):
                o = o._asdict()
        return [o if isinstance(o, dict) else o._asdict() for o in orders]
    except Exception as exc:
        log.warning("MT5 orders fetch failed: %s", exc)
        return []
