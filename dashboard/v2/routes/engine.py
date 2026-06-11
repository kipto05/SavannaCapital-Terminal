"""dashboard/v2/routes/engine.py - engine log and control endpoints.

/status and /heartbeat now live at /api/v2/engine/ (engine/routes.py)
and are backed by the shared thread-safe state (no file I/O).
This router handles log reading and history queries.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config.settings import config
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/engine-controls/logs")
def get_engine_logs(tail: int = 200) -> dict[str, Any]:
    """Return the last N lines of the engine log file."""
    log_path = Path(__file__).resolve().parent.parent.parent.parent / "logs" / "engine.log"
    if not log_path.exists():
        return {"lines": [], "path": str(log_path), "found": False}
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "lines": lines[-tail:],
        "path": str(log_path),
        "found": True,
        "total_lines": len(lines),
    }


@router.get("/engine-controls/history")
def get_pnl_history(limit: int = 200, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return recent account snapshot history for the equity curve."""
    from db.models import AccountSnapshot
    snaps = (
        db.query(AccountSnapshot)
        .order_by(AccountSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"history": [s.to_dict() for s in reversed(snaps)]}


@router.get("/engine-controls/active-strategies")
def get_active_strategies(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return list of strategies currently enabled in the registry."""
    from db.models import StrategyConfig
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    reg._seed_if_needed(db)
    rows = db.query(StrategyConfig).filter(StrategyConfig.is_active.is_(True)).all()
    return {
        "active": [
            {
                "name": r.name,
                "symbol": r.params.get("symbol", "") if r.params else "",
                "version": r.version,
            }
            for r in rows
        ]
    }
