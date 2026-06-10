"""dashboard/v2/routes/accounts.py — Multi-Account MT5 management endpoints.

All routes mount under /api/v2/accounts/ via dashboard/v2/app.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from auth.service import hash_password
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import config
from db.models import Account, Trade
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()

_ACCOUNTS_AVAILABLE: bool | None = None


def _check_accounts_table(db: Session) -> bool:
    """Return True once the accounts table is confirmed to exist."""
    global _ACCOUNTS_AVAILABLE
    if _ACCOUNTS_AVAILABLE is not None:
        return _ACCOUNTS_AVAILABLE
    try:
        db.execute(text("SELECT 1 FROM accounts LIMIT 1"))
        _ACCOUNTS_AVAILABLE = True
    except Exception:
        _ACCOUNTS_AVAILABLE = False
    return _ACCOUNTS_AVAILABLE


_ACCOUNT_COLOUR_PALETTE = [
    "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6",
    "#EF4444", "#06B6D4", "#EC4899", "#84CC16",
    "#F97316", "#6366F1",
]


def _assign_colour(db: Session, preferred: str | None) -> str:
    if preferred and preferred in _ACCOUNT_COLOUR_PALETTE:
        return preferred
    used = {row[0] for row in db.query(Account.colour).filter(Account.colour.isnot(None)).all()}
    for c in _ACCOUNT_COLOUR_PALETTE:
        if c not in used:
            return c
    return _ACCOUNT_COLOUR_PALETTE[len(used) % len(_ACCOUNT_COLOUR_PALETTE)]


# ── Lists ────────────────────────────────────────────────────────────────────
@router.get("/")
def list_accounts(request: Request, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        return {
            "accounts": [], "total": 0, "summary": {},
            "accounts_available": False,
            "note": "accounts table not yet migrated — run: .\\venv\\Scripts\\python.exe -m alembic upgrade head",
        }
    rows = db.query(Account).order_by(Account.created_at.desc()).all()
    accounts = [r.to_dict(include_runtime=True) for r in rows]
    te = sum(r._equity or 0 for r in rows)
    tb = sum(r._balance or 0 for r in rows)
    ac = sum(1 for r in rows if r.is_active and r.is_connected)
    return {
        "accounts": accounts, "total": len(accounts),
        "summary": {"total_equity": round(te, 2), "total_balance": round(tb, 2), "active_count": ac},
        "accounts_available": True,
    }


@router.get("/summary")
def accounts_summary(db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        return {
            "total_equity": 0, "total_balance": 0,
            "combined_free_margin": 0, "aggregated_drawdown": 0,
            "global_profit": 0, "accounts_available": False,
        }
    rows = db.query(Account).filter(Account.is_active.is_(True)).all()
    te = sum(r._equity or 0 for r in rows)
    tb = sum(r._balance or 0 for r in rows)
    cfm = sum(r._free_margin or 0 for r in rows)
    gp = sum((r._equity or 0) - (r._balance or 0) for r in rows)
    return {
        "total_equity": round(te, 2), "total_balance": round(tb, 2),
        "combined_free_margin": round(cfm, 2), "aggregated_drawdown": 0.0,
        "global_profit": round(gp, 2), "accounts_available": True,
    }


@router.get("/health")
def accounts_health(db: Session = Depends(get_db)) -> dict:
    rows = db.query(Account).all()
    items = []
    for r in rows:
        items.append({
            "account": r.account_name, "login": r.mt5_login, "broker": r.broker,
            "colour": r.colour, "is_connected": r.is_connected, "is_active": r.is_active,
            "last_heartbeat": r._last_heartbeat.isoformat() if r._last_heartbeat else None,
        })
    return {"items": items, "count": len(items)}


# ── Single account ───────────────────────────────────────────────────────────
@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    row = db.query(Account).filter(Account.id == account_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account": row.to_dict(include_runtime=True)}


@router.get("/{account_id}/positions")
def account_positions(account_id: int, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")
    trades = (
        db.query(Trade)
        .filter(Trade.is_active == True)
        .order_by(Trade.opened_at.desc())
        .limit(200)
        .all()
    )
    return {
        "account": acc.to_dict(include_runtime=True),
        "positions": [t.to_dict() for t in trades],
    }


# ── Create ───────────────────────────────────────────────────────────────────
_CREATE_FIELDS = {"account_name", "broker", "server", "mt5_login", "password_enc",
                  "investor_password_enc", "account_type", "weight", "colour", "notes"}


@router.post("/")
def create_account(body: dict, request: Request, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")

    required = ("account_name", "broker", "server", "mt5_login", "password_enc")
    missing = [k for k in required if not body.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail={"error": f"missing fields: {missing}"})

    try:
        login_val = int(body["mt5_login"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"error": "mt5_login must be a number"})

    if db.query(Account).filter(Account.mt5_login == login_val).first():
        raise HTTPException(status_code=409, detail={"error": "mt5_login already exists"})

    colour = _assign_colour(db, body.get("colour"))
    acct_type_raw = (body.get("account_type") or "demo").lower()
    acct_type = "live" if acct_type_raw == "live" else "demo"


    # Store raw MT5 password in raw_password, hash in password_enc
    raw_pw = str(body.get("password_enc") or "")
    # BCrypt hashing will be done in a follow-up step — for now store raw
    # in raw_password column (never exposed via API) and keep password_enc
    # as-is for backward compat. The create endpoint sends plaintext which
    # we stash in raw_password; password_enc is the bcrypt layer.

    acc = Account(
        account_name=body["account_name"],
        broker=body["broker"],
        server=body["server"],
        mt5_login=login_val,
        raw_password=raw_pw,
        password_enc=hash_password(raw_pw),  # bcrypt for future platform auth
        investor_password_enc=body.get("investor_password_enc"),
        account_type=acct_type,
        weight=float(body.get("weight") or 1.0),
        colour=colour,
        is_active=bool(body.get("is_active", True)),
        notes=body.get("notes"),
    )
    db.add(acc)
    db.flush()
    log.info("Account created: id=%d name=%s login=%s", acc.id, acc.account_name, acc.mt5_login)
    return {"account": acc.to_dict(include_runtime=True), "created": True}


# ── Update ───────────────────────────────────────────────────────────────────
_MUTABLE = {"account_name", "broker", "server", "mt5_login",
            "investor_password_enc", "account_type", "weight", "colour",
            "is_active", "notes"}


@router.patch("/{account_id}")
def update_account(account_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = {k: v for k, v in body.items() if k in _MUTABLE}
    if "mt5_login" in updates:
        try:
            new_login = int(updates["mt5_login"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="mt5_login must be a number")
        dup = db.query(Account).filter(Account.mt5_login == new_login, Account.id != account_id).first()
        if dup:
            raise HTTPException(status_code=409, detail="mt5_login already in use")
        updates["mt5_login"] = new_login

    if "account_type" in updates:
        raw = str(updates["account_type"]).lower()
        updates["account_type"] = "live" if raw == "live" else "demo"

    if "colour" in updates:
        updates["colour"] = _assign_colour(db, updates["colour"])

    for k, v in updates.items():
        setattr(acc, k, v)

    db.flush()
    return {"account": acc.to_dict(include_runtime=True), "updated": True}


# ── Delete ───────────────────────────────────────────────────────────────────
@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    log.info("Account deleted: id=%d name=%s", account_id, acc.account_name)
    return {"deleted": account_id}


# ── Per-account actions ──────────────────────────────────────────────────────
def _resolve_password(acc: Account) -> str:
    """Return the raw MT5 plaintext password for this account.

    Preferred: raw_password column (stores plaintext for MT5 init).
    Fallback:  password_enc column (may contain plaintext for legacy accounts
               created before the raw_password column was added).
    """
    pw = acc.raw_password or ""
    if pw:
        return pw
    # Legacy fallback: pre-migration accounts stored plaintext in password_enc
    # We still pass it to MT5 directly; the bcrypt hash was only applied after
    # migration so password_enc may hold the raw value for old records.
    return acc.password_enc or ""


def _connect_mt5_account(acc: Account) -> dict:
    """Attempt a real MT5 connection for this specific account.

    Uses the account's own stored credentials (mt5_login, raw_password, server).
    On success populates the runtime fields (balance, equity, margin, free_margin,
    open_positions, last_heartbeat) from the live MT5 terminal.

    Returns a result dict with keys: success (bool), detail (str), runtime (dict|None).
    """
    try:
        import MetaTrader5 as mt5  # noqa: F811
    except ImportError:
        return {
            "success": False,
            "detail": "MetaTrader5 package is not installed in the Python environment",
            "runtime": None,
        }

    login_val = int(acc.mt5_login)
    password = _resolve_password(acc)
    server = acc.server or config.mt5.server or ""
    path = config.mt5.path or ""

    log.info(
        "MT5 connect: account=%s id=%d login=%s server=%s",
        acc.account_name, acc.id, login_val, server,
    )

    # Always shutdown first to clear stale IPC state
    mt5.shutdown()

    ok = False
    # Strategy 1: full init with terminal path + credentials (clean cold start)
    if path:
        log.info("  attempt 1: path=%s", path[:80])
        ok = mt5.initialize(
            path=path,
            login=login_val,
            password=password,
            server=server,
            timeout=15_000,
        )

    # Strategy 2: no path — attach to already-running terminal
    if not ok:
        log.info("  attempt 2: no path (attach to running terminal)")
        ok = mt5.initialize(
            login=login_val,
            password=password,
            server=server,
            timeout=15_000,
        )

    if not ok:
        err = mt5.last_error()
        log.error(
            "MT5 init FAILED account=%s id=%d: %s",
            acc.account_name, acc.id, err,
        )
        return {"success": False, "detail": f"MT5 init failed: {err}", "runtime": None}

    info = mt5.account_info()
    if info is None:
        err = mt5.last_error()
        log.error("MT5 account_info FAILED account=%s id=%d: %s", acc.account_name, acc.id, err)
        mt5.shutdown()
        return {"success": False, "detail": f"MT5 account_info failed: {err}", "runtime": None}

    acc.update_runtime(
        balance=float(info.balance),
        equity=float(info.equity),
        margin=float(info.margin),
        free_margin=float(info.margin_free),
        open_positions=info.margin,
        is_connected=True,
    )
    positions = mt5.positions_get()
    acc._open_positions = len(positions) if positions is not None else 0

    log.info(
        "MT5 connected: %s id=%d balance=%.2f equity=%.2f positions=%d",
        acc.account_name, acc.id, acc._balance, acc._equity, acc._open_positions,
    )
    result = acc.to_dict(include_runtime=True)
    return {
        "success": True,
        "detail": f"Connected to {acc.server} as {acc.account_name}",
        "runtime": {
            "balance": result.get("balance"),
            "equity": result.get("equity"),
            "margin": result.get("margin"),
            "free_margin": result.get("free_margin"),
            "open_positions": result.get("open_positions"),
            "margin_level": result.get("margin_level"),
            "last_heartbeat": result.get("last_heartbeat"),
        },
    }


@router.post("/{account_id}/action")
def account_action(account_id: int, body: dict, db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")

    action = str(body.get("action", "")).lower().strip()
    value = body.get("value")
    log.info("Account action: account=%s id=%d action=%s", acc.account_name, account_id, action)

    if action == "connect":
        conn = _connect_mt5_account(acc)
        if not conn["success"]:
            raise HTTPException(status_code=502, detail={"error": conn["detail"]})
        acc.is_connected = True
        db.flush()
        return {
            "account": acc.to_dict(include_runtime=True),
            "action": "connect",
            "mt5_result": conn,
        }

    elif action == "disconnect":
        try:
            import MetaTrader5 as _mt5_disc
            _mt5_disc.shutdown()
            log.info("MT5 shutdown: %s id=%d", acc.account_name, acc.id)
        except Exception as exc:
            log.warning("MT5 shutdown warning: %s: %s", acc.account_name, exc)
        acc.is_connected = False
        acc._balance = None
        acc._equity = None
        acc._margin = None
        acc._free_margin = None
        acc._open_positions = None
        acc._last_heartbeat = None
        db.flush()
        return {"account": acc.to_dict(include_runtime=True), "action": "disconnect"}

    elif action == "pause":
        acc.is_active = False
        db.flush()
        return {"account": acc.to_dict(include_runtime=True), "action": "pause"}

    elif action == "set_weight":
        try:
            w = float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="weight must be a number")
        if not (0.0 <= w <= 2.0):
            raise HTTPException(status_code=400, detail="weight must be 0.0 - 2.0")
        acc.weight = w
        db.flush()
        return {"account": acc.to_dict(include_runtime=True), "action": "set_weight"}

    elif action == "rename":
        name = str(value or "").strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="name must have at least 2 characters")
        acc.account_name = name
        db.flush()
        return {"account": acc.to_dict(include_runtime=True), "action": "rename"}

    elif action == "close_all_positions":
        log.warning("close_all_positions: %s id=%d", acc.account_name, acc.id)
        return {
            "action": "close_all_positions", "queued": True,
            "account": acc.to_dict(include_runtime=True),
            "note": "Engine MT5 order manager will execute close",
        }

    elif action == "test_connection":
        log.info("test_connection: %s id=%d", acc.account_name, acc.id)
        try:
            import MetaTrader5 as _mt5_test
            login_v = int(acc.mt5_login)
            mt5_pw = _resolve_password(acc)
            mt5_srv = acc.server or config.mt5.server or ""
            test_path = config.mt5.path or ""
            _mt5_test.shutdown()
            test_ok = _mt5_test.initialize(
                path=test_path, login=login_v,
                password=mt5_pw, server=mt5_srv, timeout=15_000,
            )
            if test_ok:
                _mt5_test.shutdown()
                return {
                    "action": "test_connection", "status": "ok",
                    "account": acc.to_dict(include_runtime=True),
                    "detail": f"Login {acc.mt5_login} on {acc.server} — credentials valid",
                }
            err = _mt5_test.last_error()
            return {
                "action": "test_connection", "status": "failed",
                "account": acc.to_dict(include_runtime=True),
                "detail": f"Login failed: {err}",
            }
        except Exception as exc:
            return {
                "action": "test_connection", "status": "error",
                "account": acc.to_dict(include_runtime=True),
                "detail": str(exc),
            }

    raise HTTPException(
        status_code=400,
        detail={"error": f"unknown action '{action}'. Allowed: connect, disconnect, pause, set_weight, rename, close_all_positions, test_connection"},
    )


# ── Bulk ─────────────────────────────────────────────────────────────────────
@router.post("/bulk/disconnect-all")
def bulk_disconnect(db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    n = (
        db.query(Account)
        .filter(Account.is_connected.is_(True))
        .update({"is_connected": False}, synchronize_session=False)
    )
    for acc in db.query(Account).all():
        acc._balance = None
        acc._equity = None
        acc._margin = None
        acc._free_margin = None
        acc._open_positions = None
        acc._last_heartbeat = None
    try:
        import MetaTrader5 as _mt5_disc
        _mt5_disc.shutdown()
    except Exception:
        pass
    db.flush()
    log.info("Bulk disconnect: %d accounts", n)
    return {"disconnected": n, "action": "disconnect-all"}


@router.post("/bulk/close-all")
def bulk_close_all(db: Session = Depends(get_db)) -> dict:
    if not _check_accounts_table(db):
        raise HTTPException(status_code=503, detail="accounts table not yet migrated")
    accounts = db.query(Account).filter(Account.is_connected.is_(True)).all()
    log.warning("Bulk close-all: %d connected accounts", len(accounts))
    return {
        "action": "close-all", "queued": True, "account_count": len(accounts),
        "accounts": [a.to_dict(include_runtime=True) for a in accounts],
        "note": "Engine must close positions per account",
    }
