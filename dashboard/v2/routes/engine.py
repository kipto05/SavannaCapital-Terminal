"""dashboard/v2/routes/engine.py - engine control endpoints.

All new feature routes go here.  The v2 app mounts everything under
/api/v2/ automatically so this router's paths are relative.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.settings import config
from db.models import StrategyConfig
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/engine/status")
def get_engine_status(db: Session = Depends(get_db)):
    """Full engine status snapshot - heartbeat, MT5, active strategies."""
    heartbeat_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "logs"
        / "engine_heartbeat"
    )
    heartbeat_age: int | None = None
    engine_running = False
    try:
        if heartbeat_path.exists():
            ts = float(heartbeat_path.read_text(encoding="utf-8").strip())
            now = datetime.now(timezone.utc).timestamp()
            heartbeat_age = int(now - ts)
            engine_running = heartbeat_age < 120
    except Exception:
        pass

    active_count = (
        db.query(StrategyConfig)
        .filter(StrategyConfig.is_active.is_(True))
        .count()
    )

    return {
        "engine_running": engine_running,
        "heartbeat_age_seconds": heartbeat_age,
        "active_strategies": active_count,
        "poll_interval_seconds": config.engine.poll_interval_seconds,
        "snapshot_interval_seconds": config.engine.snapshot_interval_seconds,
    }


@router.get("/engine/logs")
def get_engine_logs(tail: int = 200):
    """Return the last N lines of the engine log file."""
    log_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "logs"
        / "engine.log"
    )
    if not log_path.exists():
        return {"lines": [], "path": str(log_path), "found": False}
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "lines": lines[-tail:],
        "path": str(log_path),
        "found": True,
        "total_lines": len(lines),
    }


@router.get("/engine/heartbeat")
def get_heartbeat():
    """Return raw heartbeat timestamp and age."""
    heartbeat_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "logs"
        / "engine_heartbeat"
    )
    if not heartbeat_path.exists():
        return {"timestamp": None, "age_seconds": None, "fresh": False}
    try:
        ts = float(heartbeat_path.read_text(encoding="utf-8").strip())
        now = datetime.now(timezone.utc).timestamp()
        age = int(now - ts)
        return {
            "timestamp": ts,
            "age_seconds": age,
            "fresh": age < 60,
            "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        }
    except Exception:
        return {"timestamp": None, "age_seconds": None, "fresh": False}
