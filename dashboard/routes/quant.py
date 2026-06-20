"""dashboard/routes/quant.py — parameter optimisation endpoints.

Mount: app.include_router(router) -> /api/quant/optimise
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from config.settings import config
from db.models import OptimisationRun
from db.session import get_db
from quant.optimiser import run as run_optimiser
from strategies.registry import StrategyRegistry

log = logging.getLogger(__name__)
router = APIRouter()


def _resolve_strategy_class(name: str):
    reg = StrategyRegistry(None)
    cls = reg.classes.get(name)
    if cls is None:
        raise ValueError(f"Strategy not found in registry: {name!r}")
    return cls


@router.post("/optimise")
def create_optimisation(
    body: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """POST /api/quant/optimise — start a parameter optimisation.

    Expected body:
    {
        "strategy": "MomentumReversion",
        "symbol": "BTCUSD",
        "timeframe": "M15",
        "param_bounds": {"trend_fast_period": {"min": 20, "max": 100, "step": 5}, ...},
        "search_method": "grid|random|bayesian",
        "fitness_metric": "sharpe|calmar|net_profit",
        "n_iterations": 200
    }
    """
    strategy = body.get("strategy")
    symbol = body.get("symbol")
    timeframe = body.get("timeframe")
    param_bounds = body.get("param_bounds")
    if not all([strategy, symbol, timeframe, param_bounds]):
        raise HTTPException(400, "Missing required fields: strategy, symbol, timeframe, param_bounds")

    search_method = body.get("search_method", "grid")
    fitness_metric = body.get("fitness_metric", "sharpe")
    n_iterations = int(body.get("n_iterations", 200))

    # Create OptimisationRun record (pending)
    run = OptimisationRun(
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        param_bounds=param_bounds,
        search_method=search_method,
        fitness_metric=fitness_metric,
        n_iterations=n_iterations,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Enqueue background job
    background_tasks.add_task(
        _run_optimisation_job,
        run_id=run.id,
        strategy_name=strategy,
        symbol=symbol,
        timeframe=timeframe,
        param_bounds=param_bounds,
        search_method=search_method,
        fitness_metric=fitness_metric,
        n_iterations=n_iterations,
    )
    log.info("Optimisation queued: run_id=%d %s %s %s", run.id, symbol, timeframe, strategy)
    return {"run_id": run.id}


def _run_optimisation_job(
    run_id: int,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    param_bounds: dict,
    search_method: str,
    fitness_metric: str,
    n_iterations: int,
) -> None:
    """Background job wrapper."""
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        # Mark running
        run = db.query(OptimisationRun).filter(OptimisationRun.id == run_id).first()
        if run is None:
            log.error("OptimisationRun %d not found", run_id)
            return
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        # Run optimisation
        result = run_optimiser(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            param_bounds=param_bounds,
            search_method=search_method,
            fitness_metric=fitness_metric,
            n_iterations=n_iterations,
            db_session=db,
        )

        # Update run with results
        run.best_params = result.get("best_params")
        run.best_score = result.get("best_score")
        run.heatmap_data = result.get("heatmap_data")
        run.top_n_results = result.get("top_n_results")
        run.n_iterations = result.get("n_iterations", n_iterations)
        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        log.info("Optimisation %d complete: best_score=%.4f", run_id, run.best_score)
    except Exception as exc:
        log.exception("Optimisation %d FAILED: %s", run_id, exc)
        if db is not None:
            try:
                db.rollback()
                run = db.query(OptimisationRun).filter(OptimisationRun.id == run_id).first()
                if run is not None:
                    run.status = "failed"
                    run.error_message = str(exc)
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                log.exception("Failed to mark OptimisationRun %d as failed", run_id)
    finally:
        db.close()


@router.get("/optimise")
def list_optimisations(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """GET /api/quant/optimise — recent optimisation runs."""
    runs = (
        db.query(OptimisationRun)
        .order_by(OptimisationRun.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in runs:
        result.append({
            "id": r.id,
            "strategy": r.strategy,
            "symbol": r.symbol,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "best_score": r.best_score,
        })
    return result


@router.get("/optimise/{run_id}")
def get_optimisation(run_id: int, db: Session = Depends(get_db)):
    """GET /api/quant/optimise/{run_id} — full optimisation result."""
    run = db.query(OptimisationRun).filter(OptimisationRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Optimisation {run_id} not found")
    return {
        "id": run.id,
        "strategy": run.strategy,
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "param_bounds": run.param_bounds,
        "search_method": run.search_method,
        "fitness_metric": run.fitness_metric,
        "n_iterations": run.n_iterations,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message,
        "best_params": run.best_params,
        "best_score": run.best_score,
        "heatmap_data": run.heatmap_data,
        "top_n_results": run.top_n_results,
    }


@router.put("/optimise/{run_id}/deploy")
def deploy_optimisation(run_id: int, db: Session = Depends(get_db)):
    """PUT /api/quant/optimise/{run_id}/deploy — apply best_params to strategy."""
    run = db.query(OptimisationRun).filter(OptimisationRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Optimisation {run_id} not found")
    if run.status != "complete":
        raise HTTPException(400, f"Optimisation {run_id} not completed")
    if not run.best_params:
        raise HTTPException(400, "No best_params to deploy")
    reg = StrategyRegistry(db)
    try:
        reg.update_params(run.strategy, run.best_params)
        db.commit()
        log.info("Optimisation %d deployed best_params to strategy %s", run_id, run.strategy)
        return {"status": "deployed", "strategy": run.strategy, "params": run.best_params}
    except Exception as exc:
        db.rollback()
        log.exception("Deploy optimisation %d failed: %s", run_id, exc)
        raise HTTPException(500, "Deploy failed")
