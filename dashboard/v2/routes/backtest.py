"""dashboard/v2/routes/backtest.py - placeholders for backtesting endpoints.

Feature stub - returns stub response until backtesting engine is wired up.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session

from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/backtest/runs")
def list_backtest_runs(db: Session = Depends(get_db)):
    """List all backtest runs from DB."""
    from db.models import BacktestRun
    runs = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(50).all()
    return [r.to_dict() for r in runs]


@router.post("/backtest/run")
def run_backtest(body: dict[str, Any], db: Session = Depends(get_db)):
    """Queue a new backtest run."""
    from db.models import BacktestRun
    run = BacktestRun(
        strategy_name=body.get("strategy_name", ""),
        symbol=body.get("symbol", ""),
        timeframe=body.get("timeframe", ""),
        status="pending",
        params=body.get("params", {}),
    )
    db.add(run)
    db.flush()
    return {"run_id": str(run.id), "status": "queued"}


@router.get("/backtest/runs/{run_id}")
def get_backtest_run(run_id: str, db: Session = Depends(get_db)):
    """Get status and results of a specific backtest run."""
    from db.models import BacktestRun
    from db.models import Trade
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if not run:
        return {"error": "run not found"}
    trades = (
        db.query(Trade)
        .filter(Trade.backtest_run_id == run_id)
        .order_by(Trade.id.desc())
        .limit(200)
        .all()
    )
    return {
        **run.to_dict(),
        "trades": [t.to_dict() for t in trades],
    }
