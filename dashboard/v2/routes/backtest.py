"""dashboard/v2/routes/backtest.py — backtesting center endpoints.

Mounts under /api/v2/backtest/ via dashboard/v2/app.py.

Endpoints
---------
GET   /strategies        — list available strategy classes with metadata
GET   /symbols           — list available MT5 symbols by asset class
GET   /timeframes        — list available timeframes + MT5 minute mapping
POST  /run               — queue a backtest (returns run_id immediately)
GET   /runs              — recent backtest run history
GET   /run/{run_id}      — single run detail with trades
GET   /run/{run_id}/equity       — equity / drawdown curves
GET   /run/{run_id}/distribution— PnL distribution bins
GET   /run/{run_id}/monthly     — monthly returns heatmap grid
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config.settings import ASSET_POOL, TIMEFRAMES_BY_ASSET, config
from db.models import BacktestRun, Trade
from db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_strategy_class(name: str):
    """Import and return a strategy class by Python class name."""
    try:
        import importlib
        modules = {
            "MomentumReversion": "strategies.momentum_reversion",
            "BandReversion":    "strategies.band_reversion",
            "StochasticTrend":  "strategies.stochastic_trend",
            "SessionBreakout":  "strategies.session_breakout",
            "DivergenceSwing":  "strategies.divergence_swing",
            "VWAPReversion":    "strategies.vwap_reversion",
            "MACDImpulse":      "strategies.macd_impulse",
        }
        mod_path = modules.get(name)
        if mod_path is None:
            return None
        mod = importlib.import_module(mod_path)
        return getattr(mod, name, None)
    except Exception as exc:
        log.warning("_resolve_strategy_class(%s) failed: %s", name, exc)
        return None


def _job(run_id: int, symbol, timeframe, strategy_name, params, start_date, end_date, n_bars,
         initial_equity, risk_per_trade, warmup_bars, execution) -> None:
    """Background job wrapper — import runner lazily to avoid circular imports."""
    from quant.runner import run_backtest_job
    run_backtest_job(
        run_id=run_id,
        symbol=symbol,
        timeframe=timeframe,
        strategy_class=_resolve_strategy_class(strategy_name),
        params=params,
        start_date=start_date,
        end_date=end_date,
        n_bars=n_bars,
        initial_equity=initial_equity,
        risk_per_trade=risk_per_trade,
        warmup_bars=warmup_bars,
        execution=execution,
    )


# ─────────────────────────────────────────────────────────────────────────────
# E1 — List strategies
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/strategies")
def list_strategies(db: Session = Depends(get_db)):
    """GET /api/v2/backtest/strategies — available strategy classes."""
    from strategies.base import BaseStrategy
    import importlib

    entries: list[dict[str, Any]] = []
    module_paths = [
        ("MomentumReversion",  "strategies.momentum_reversion"),
        ("BandReversion",    "strategies.band_reversion"),
        ("StochasticTrend",  "strategies.stochastic_trend"),
        ("SessionBreakout",  "strategies.session_breakout"),
        ("DivergenceSwing",  "strategies.divergence_swing"),
        ("VWAPReversion",    "strategies.vwap_reversion"),
        ("MACDImpulse",      "strategies.macd_impulse"),
    ]

    for class_name, mod_path in module_paths:
        try:
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, class_name, None)
            if cls is None or not issubclass(cls, BaseStrategy):
                continue
            meta = cls.meta
            entries.append({
                "class_name": class_name,
                "name": meta.name,
                "label": meta.label,
                "description": meta.description or "",
                "version": meta.version,
                "default_symbol": meta.default_symbol,
                "typical_timeframes": meta.typical_timeframes,
                "default_params": cls.default_params,
                "param_bounds": cls.param_bounds,
            })
        except Exception as exc:
            log.debug("Skipping strategy %s: %s", class_name, exc)

    return entries


# ─────────────────────────────────────────────────────────────────────────────
# E2 — List symbols
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/symbols")
def list_symbols():
    """GET /api/v2/backtest/symbols — available MT5 symbols, grouped by asset class."""
    asset_pool = ASSET_POOL
    if isinstance(asset_pool, dict):
        return {"groups": list(asset_pool.keys()), "pool": asset_pool}
    symbols = list(asset_pool) if isinstance(asset_pool, list) else []
    return {"groups": ["all"], "pool": {"all": symbols}}


# ─────────────────────────────────────────────────────────────────────────────
# E3 — List timeframes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/timeframes")
def list_timeframes():
    """GET /api/v2/backtest/timeframes — available timeframes with MT5 minute values."""
    tf_by_asset = TIMEFRAMES_BY_ASSET
    seen: set[str] = set()
    ordered: list[str] = []
    canonical = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    for tf in canonical:
        if tf not in seen:
            seen.add(tf)
            ordered.append(tf)
    for tfs in tf_by_asset.values():
        for tf in tfs:
            if tf not in seen:
                seen.add(tf)
                ordered.append(tf)
    mt5_minutes = {tf: _mt5_minutes(tf) for tf in ordered}
    return {"timeframes": ordered, "mt5_minutes": mt5_minutes}


def _mt5_minutes(tf: str) -> int:
    mapping = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
    return mapping.get(tf, 0)


# ─────────────────────────────────────────────────────────────────────────────
# E4 — Run / queue a backtest
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run")
def create_run(body: dict[str, Any], background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """POST /api/v2/backtest/run — queue a new backtest.

    Returns run_id immediately; actual computation runs in the background.
    """
    # ── Validate inputs ──────────────────────────────────────────────────
    strategy_name: str = _require(body, "strategy", str)
    symbol: str = _require(body, "symbol", str)
    timeframe: str = _require(body, "timeframe", str)

    cls = _resolve_strategy_class(strategy_name)
    if cls is None:
        raise HTTPException(400, f"Unknown strategy: {strategy_name}")

    # ── Build params (defaults merged with user overrides) ───────────────
    user_params: dict = body.get("params", {})
    params = {**cls.default_params, **{k: v for k, v in user_params.items() if k in cls.default_params}}

    # ── Create DB record ─────────────────────────────────────────────────
    run = BacktestRun(
        strategy_name=strategy_name,
        label=body.get("label", f"{symbol} {timeframe}"),
        status="pending",
        params_snapshot=params,
        symbol=symbol,
        timeframe=timeframe,
    )
    db.add(run)
    db.flush()

    # ── Dispatch background job ──────────────────────────────────────────
    background_tasks.add_task(
        _job,
        run_id=run.id,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=strategy_name,
        params=params,
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        n_bars=int(body.get("n_bars", 5000)),
        initial_equity=float(body.get("initial_equity", config.backtest.default_initial_equity)),
        risk_per_trade=float(body.get("risk_per_trade", config.backtest.default_risk_per_trade)),
        warmup_bars=int(body.get("warmup_bars", config.backtest.warmup_bars)),
        execution=body.get("execution", "OHLC"),
    )

    db.commit()
    log.info("Backtest queued: run_id=%d %s %s %s", run.id, symbol, timeframe, strategy_name)
    return {"run_id": run.id, "status": "pending"}


# ─────────────────────────────────────────────────────────────────────────────
# E5 — List runs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs")
def recent_runs(
    strategy: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """GET /api/v2/backtest/runs — recent backtests."""
    q = db.query(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit)
    if strategy:
        q = q.filter(BacktestRun.strategy_name == strategy)
    if status:
        q = q.filter(BacktestRun.status == status)
    return [r.to_dict() for r in q.all()]


# ─────────────────────────────────────────────────────────────────────────────
# E6 — Single run detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/run/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    """GET /api/v2/backtest/run/{run_id} — full run with trades."""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Run {run_id} not found")
    result = run.to_dict()
    trades_q = db.query(Trade).filter(Trade.backtest_run_id == run_id).order_by(Trade.id)
    result["trades"] = [t.to_dict() for t in trades_q.all()]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# E7 — Equity curve
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/run/{run_id}/equity")
def run_equity(run_id: int, db: Session = Depends(get_db)):
    """GET /api/v2/backtest/run/{run_id}/equity — equity + drawdown arrays."""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Run {run_id} not found")
    return {
        "run_id": run_id,
        "equity_curve":  _as_list(run.equity_curve),
        "drawdown_curve": _as_list(run.drawdown_curve),
        "initial_equity": run.initial_equity,
        "final_equity": run.final_equity,
        "net_pnl_r": run.net_pnl_r,
    }


# ─────────────────────────────────────────────────────────────────────────────
# E8 — PnL distribution
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/run/{run_id}/distribution")
def run_distribution(run_id: int, bins: int = 30, db: Session = Depends(get_db)):
    """GET /api/v2/backtest/run/{run_id}/distribution — PnL histogram data."""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Run {run_id} not found")

    trades = (
        db.query(Trade)
        .filter(Trade.backtest_run_id == run_id, Trade.pnl_r.isnot(None))
        .all()
    )
    pnl_r = sorted(t.pnl_r for t in trades)
    if not pnl_r:
        return {"run_id": run_id, "bins": [], "counts": [], "labels": []}

    lo, hi = min(pnl_r), max(pnl_r)
    if lo == hi:
        return {
            "run_id": run_id,
            "bins": [round(lo, 4)],
            "counts": [len(pnl_r)],
            "labels": [f"{lo:.3f}"],
        }

    step = (hi - lo) / bins
    bucket_edges = [lo + i * step for i in range(bins + 1)]
    bucket_counts = [0] * bins
    for r in pnl_r:
        idx = min(int((r - lo) / step), bins - 1)
        bucket_counts[idx] += 1

    labels = [f"{bucket_edges[i]:.3f}" for i in range(bins)]
    return {
        "run_id": run_id,
        "bins": [round((bucket_edges[i] + bucket_edges[i + 1]) / 2, 4) for i in range(bins)],
        "counts": bucket_counts,
        "labels": labels,
    }


# ─────────────────────────────────────────────────────────────────────────────
# E9 — Monthly returns heatmap
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/run/{run_id}/monthly")
def run_monthly(run_id: int, db: Session = Depends(get_db)):
    """GET /api/v2/backtest/run/{run_id}/monthly — monthly PnL grid."""
    run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(404, f"Run {run_id} not found")

    monthly = run.monthly_returns or {}
    grid: dict[str, dict[str, float]] = {}
    for key, val in monthly.items():
        parts = key.split("-")
        if len(parts) != 2:
            continue
        year, month = parts
        grid.setdefault(year, {})[month] = round(val, 4)

    return {"run_id": run_id, "monthly": grid}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require(body: dict, key: str, expected_type: type) -> Any:
    val = body.get(key)
    if val is None:
        raise HTTPException(400, f"Missing required field: {key}")
    if not isinstance(val, expected_type):
        raise HTTPException(400, f"Field '{key}' must be {expected_type.__name__}")
    return val


def _as_list(value: Any) -> list[float]:
    """Normalise JSON-stored curve to a plain list of floats."""
    if value is None:
        return []
    if isinstance(value, list):
        return [float(v) for v in value]
    if isinstance(value, dict):
        try:
            return [float(v) for v in value.values()]
        except (TypeError, ValueError):
            pass
    return []
