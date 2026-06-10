"""dashboard/v2/routes/strategies.py — v2 strategy endpoints.

All routes mount under /api/v2/strategies/ via dashboard/v2/app.py.

Endpoints
----------
GET /strategies — list available strategy classes with metadata
GET /strategies/stats/overview — 4-metric stats bar
GET /strategies/{name} — single strategy detail (for edit modal)
POST /strategies/{name}/toggle — flip is_active
PUT /strategies/{name}/params — update strategy parameters
POST /strategies/{name}/copy — duplicate a strategy config
GET /strategies/{name}/versions — version history
GET /strategies/{name}/backtests — recent backtest runs
GET /strategies/{name}/performance — full performance metrics
GET /strategies/{name}/monte-carlo — simulated equity curves
GET /strategies/{name}/trades — paginated trade history
GET /strategies/{name}/equity — equity curve data
GET /strategies/{name}/evidence — event log
PUT /strategies/{name}/regime-filter — set regime filter params
PUT /strategies/{name}/ml-override — toggle ML signal override
GET /strategies/{name}/export — export config as JSON
POST /strategies/new — create a new strategy record
GET /strategies/evidence — combined event log across all strategies
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from sqlalchemy.sql import desc

from config.settings import config
from db.models import BacktestRun, StrategyConfig, Trade, TradeAnnotation
from db.session import get_db, SessionLocal
from strategies.registry import StrategyRegistry

log = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _registry(db: Session | None = None) -> StrategyRegistry:
    """Return a StrategyRegistry, using provided session or opening a new one."""
    if db is not None:
        return StrategyRegistry(db)
    with SessionLocal() as sdb:
        return StrategyRegistry(sdb)


def _strategy_stats(db: Session, name: str) -> dict[str, Any]:
    """Compute per-strategy stats from Trade table."""
    trades = (
        db.query(Trade)
        .filter(Trade.strategy_name == name)
        .order_by(Trade.id.desc())
        .limit(500)
        .all()
    )
    total = len(trades)
    wins = sum(1 for t in trades if t.pnl_r is not None and t.pnl_r > 0)
    losses = sum(1 for t in trades if t.pnl_r is not None and t.pnl_r < 0)
    win_rate = wins / total if total else 0.0
    pnl_r_list = [t.pnl_r for t in trades if t.pnl_r is not None]
    net_pnl_r = sum(pnl_r_list) if pnl_r_list else 0.0
    avg_pnl_r = net_pnl_r / total if total else 0.0
    # Profit factor
    gross_win = sum(r for r in pnl_r_list if r > 0)
    gross_loss = abs(sum(r for r in pnl_r_list if r < 0))
    profit_factor = gross_win / gross_loss if gross_loss else None
    # Max drawdown (simple from R-multiple sequence)
    max_dd = None
    if pnl_r_list:
        equity = 1.0
        peak = 1.0
        max_dd_val = 0.0
        for r in pnl_r_list:
            equity += r * config.risk.risk_per_trade
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd_val:
                max_dd_val = dd
        max_dd = round(max_dd_val, 4)
    # Sharpe (simplified, assumes mean/std of R-multiples)
    sharpe = None
    if len(pnl_r_list) > 1:
        mean_r = sum(pnl_r_list) / len(pnl_r_list)
        var_r = sum((r - mean_r) ** 2 for r in pnl_r_list) / (len(pnl_r_list) - 1)
        std_r = var_r ** 0.5
        if std_r > 0:
            sharpe = round(mean_r / std_r, 4)
    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "net_pnl_r": round(net_pnl_r, 4),
        "avg_pnl_r": round(avg_pnl_r, 4),
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
    }


def _strategy_detail(db: Session, name: str) -> dict[str, Any]:
    """Build full strategy detail dict."""
    reg = _registry(db)
    reg._seed_if_needed(db)
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if row is None:
        raise HTTPException(404, f"Strategy {name} not found")
    cls = reg.classes.get(name)
    label = cls.meta.label if cls else row.name.replace("_", " ").title()
    symbol = cls.meta.default_symbol if cls else ""
    tf = cls.meta.typical_timeframes[0] if cls and cls.meta.typical_timeframes else ""
    stats = _strategy_stats(db, name)
    return {
        "name": row.name,
        "label": label,
        "symbol": symbol,
        "timeframe": tf,
        "is_active": row.is_active,
        "version": row.version or 1,
        "params": dict(row.params) if row.params else {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        **stats,
    }


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@router.get("/")
def list_strategies(db: Session = Depends(get_db)):
    """GET /strategies — enriched list of all strategies."""
    from strategies.registry import StrategyRegistry as _Reg
    reg = _Reg(db)
    reg._seed_if_needed(db)
    rows = db.query(StrategyConfig).order_by(StrategyConfig.name).all()
    results = []
    for row in rows:
        cls = reg.classes.get(row.name)
        label = cls.meta.label if cls else row.name.replace("_", " ").title()
        symbol = cls.meta.default_symbol if cls else ""
        tf = cls.meta.typical_timeframes[0] if cls and cls.meta.typical_timeframes else ""
        stats = _strategy_stats(db, row.name)
        results.append({
            "name": row.name,
            "label": label,
            "symbol": symbol,
            "timeframe": tf,
            "is_active": row.is_active,
            "version": row.version or 1,
            **stats,
        })
    return results


@router.get("/stats/overview")
def stats_overview(db: Session = Depends(get_db)):
    """GET /strategies/stats/overview — 4-metric stats bar."""
    from strategies.registry import StrategyRegistry as _Reg
    reg = _Reg(db)
    reg._seed_if_needed(db)
    all_rows = db.query(StrategyConfig).all()
    total = len(all_rows)
    active = sum(1 for r in all_rows if r.is_active)
    inactive = total - active
    # Any with recent backtest runs = "deploying" heuristic
    from db.models import BacktestRun as _BR
    recent_deploy_count = (
        db.query(_BR.strategy_name)
        .filter(_BR.status == "running")
        .distinct()
        .count()
    )
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "deploying": recent_deploy_count,
    }


@router.get("/{name}")
def get_strategy_detail(name: str, db: Session = Depends(get_db)):
    """GET /strategies/{name} — single strategy detail for edit modal."""
    reg = _registry(db)
    rec = reg.get_by_name(name)
    if rec is None:
        raise HTTPException(404, f"Strategy '{name}' not found")
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    cls = reg.classes.get(name)
    result = rec.to_dict()
    if row:
        result["label"] = row.label
        result["version"] = row.version or 1
    return result


@router.post("/{name}/toggle")
def toggle_strategy(name: str, db: Session = Depends(get_db)):
    """POST /strategies/{name}/toggle — flip is_active."""
    try:
        rec = _registry(db).toggle(name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"name": rec.name, "is_active": rec.is_active}


@router.put("/{name}/params")
def update_params(name: str, body: dict[str, Any], db: Session = Depends(get_db)):
    """PUT /strategies/{name}/params — update strategy parameters."""
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if row is None:
        raise HTTPException(404, f"Strategy {name} not found")
    if "params" not in body or not isinstance(body["params"], dict):
        raise HTTPException(400, "body.params must be a dict")
    row.params = body["params"]
    row.version = (row.version or 1) + 1
    db.flush()
    log.info("Strategy params updated: name=%s version=%d", name, row.version)
    return {"name": row.name, "version": row.version, "params": dict(row.params)}


@router.post("/{name}/copy")
def copy_strategy(name: str, body: dict | None = None, db: Session = Depends(get_db)):
    """POST /strategies/{name}/copy — duplicate a strategy config."""
    source = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if source is None:
        raise HTTPException(404, f"Strategy {name} not found")
    new_name = (body or {}).get("new_name", f"{name}_copy")
    existing = db.query(StrategyConfig).filter(StrategyConfig.name == new_name).first()
    if existing:
        raise HTTPException(409, f"Strategy {new_name} already exists")
    import copy as _copy
    clone = StrategyConfig(
        name=new_name,
        label=(body or {}).get("label", source.label),
        symbol=source.symbol,
        timeframe=source.timeframe,
        is_active=False,
        params=_copy.deepcopy(source.params) if source.params else {},
        version=1,
    )
    db.add(clone)
    db.flush()
    log.info("Strategy copied: %s → %s", name, new_name)
    return {"name": new_name, "label": clone.label, "version": 1}


@router.get("/{name}/versions")
def strategy_versions(name: str, db: Session = Depends(get_db)):
    """GET /strategies/{name}/versions — version history."""
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if row is None:
        raise HTTPException(404, f"Strategy {name} not found")
    # Current version as latest entry
    entries = [{
        "version": row.version or 1,
        "params": dict(row.params) if row.params else {},
        "is_active": row.is_active,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else row.created_at.isoformat() if row.created_at else None,
    }]
    # Also pull related backtests as historical snapshots
    runs = (
        db.query(BacktestRun)
        .filter(BacktestRun.strategy_name == name)
        .order_by(BacktestRun.created_at.desc())
        .limit(20)
        .all()
    )
    for run in runs:
        entries.append({
            "version": run.id,
            "params": run.params or {},
            "is_active": row.is_active,
            "updated_at": run.created_at.isoformat() if run.created_at else None,
            "backtest_status": run.status,
        })
    return entries


@router.get("/{name}/backtests")
def strategy_backtests(name: str, limit: int = 20, db: Session = Depends(get_db)):
    """GET /strategies/{name}/backtests — recent backtest runs."""
    runs = (
        db.query(BacktestRun)
        .filter(BacktestRun.strategy_name == name)
        .order_by(BacktestRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in runs]


@router.get("/{name}/performance")
def strategy_performance(name: str, db: Session = Depends(get_db)):
    """GET /strategies/{name}/performance — full performance metrics."""
    stats = _strategy_stats(db, name)
    # Monthly returns
    trades = (
        db.query(Trade)
        .filter(Trade.strategy_name == name)
        .order_by(Trade.entry_time.asc())
        .all()
    )
    monthly: dict[str, float] = {}
    for t in trades:
        if t.entry_time is None or t.pnl_r is None:
            continue
        key = t.entry_time.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0.0) + t.pnl_r
    stats["monthly_returns"] = [{"month": k, "pnl_r": round(v, 4)} for k, v in sorted(monthly.items())]
    return stats


@router.get("/{name}/monte-carlo")
def strategy_monte_carlo(name: str, simulations: int = 50, db: Session = Depends(get_db)):
    """GET /strategies/{name}/monte-carlo — simulated equity curves."""
    import random
    random.seed(42)
    pnl_r_list = [
        t.pnl_r for t in
        db.query(Trade)
        .filter(Trade.strategy_name == name, Trade.pnl_r.isnot(None))
        .all()
    ]
    if not pnl_r_list:
        return {"simulations": 0, "curves": []}
    risk_pct = config.risk.risk_per_trade
    curves = []
    for _ in range(min(simulations, 200)):
        equity = 1.0
        curve = [1.0]
        shuffled = random.sample(pnl_r_list, len(pnl_r_list))
        for r in shuffled:
            equity += r * risk_pct
            curve.append(round(equity, 6))
        curves.append(curve)
    return {"simulations": len(curves), "curves": curves}


@router.get("/{name}/trades")
def strategy_trades(name: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """GET /strategies/{name}/trades — paginated trade history."""
    q = (
        db.query(Trade)
        .filter(Trade.strategy_name == name)
        .order_by(Trade.entry_time.desc())
        .limit(limit)
        .offset(offset)
    )
    trades = q.all()
    total = (
        db.query(func.count(Trade.id))
        .filter(Trade.strategy_name == name)
        .scalar()
    )
    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "trades": [t.to_dict() for t in trades],
    }


@router.get("/{name}/equity")
def strategy_equity(name: str, db: Session = Depends(get_db)):
    """GET /strategies/{name}/equity — equity curve data."""
    trades = (
        db.query(Trade)
        .filter(Trade.strategy_name == name, Trade.pnl_r.isnot(None))
        .order_by(Trade.entry_time.asc())
        .all()
    )
    equity = 1.0
    points = [{"index": 0, "equity": 1.0, "timestamp": None}]
    for i, t in enumerate(trades, 1):
        equity += t.pnl_r * config.risk.risk_per_trade
        points.append({
            "index": i,
            "equity": round(equity, 6),
            "timestamp": t.entry_time.isoformat() if t.entry_time else None,
            "pnl_r": round(t.pnl_r, 4),
        })
    return {"points": points, "final_equity": round(equity, 6)}


@router.get("/{name}/evidence")
def strategy_evidence(name: str, limit: int = 50, db: Session = Depends(get_db)):
    """GET /strategies/{name}/evidence — event log."""
    events: list[dict[str, Any]] = []
    # Param changes from backtest runs
    runs = (
        db.query(BacktestRun)
        .filter(BacktestRun.strategy_name == name)
        .order_by(BacktestRun.created_at.desc())
        .limit(limit // 2)
        .all()
    )
    for r in runs:
        events.append({
            "type": "backtest",
            "status": r.status,
            "params": r.params or {},
            "timestamp": r.created_at.isoformat() if r.created_at else None,
        })
    # Recent trades as deploy/execution events
    trades = (
        db.query(Trade)
        .filter(Trade.strategy_name == name)
        .order_by(Trade.entry_time.desc())
        .limit(limit // 2)
        .all()
    )
    for t in trades:
        events.append({
            "type": "trade",
            "side": t.side.value if hasattr(t.side, "value") else str(t.side),
            "symbol": t.symbol,
            "pnl_r": t.pnl_r,
            "timestamp": t.entry_time.isoformat() if t.entry_time else None,
        })
    # Sort by timestamp descending
    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return events[:limit]


@router.put("/{name}/regime-filter")
def regime_filter(name: str, body: dict[str, Any], db: Session = Depends(get_db)):
    """PUT /strategies/{name}/regime-filter — set regime filter params."""
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if row is None:
        raise HTTPException(404, f"Strategy {name} not found")
    if not isinstance(body, dict):
        raise HTTPException(400, "body must be a dict")
    params = dict(row.params) if row.params else {}
    params["regime_filter"] = body
    row.params = params
    row.version = (row.version or 1) + 1
    db.flush()
    log.info("Regime filter updated: name=%s", name)
    return {"name": row.name, "version": row.version, "regime_filter": body}


@router.put("/{name}/ml-override")
def ml_override(name: str, body: dict[str, Any], db: Session = Depends(get_db)):
    """PUT /strategies/{name}/ml-override — toggle ML signal override."""
    row = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if row is None:
        raise HTTPException(404, f"Strategy {name} not found")
    if "enabled" not in body:
        raise HTTPException(400, "body.enabled (bool) required")
    params = dict(row.params) if row.params else {}
    params["ml_override"] = {"enabled": bool(body["enabled"])}
    row.params = params
    row.version = (row.version or 1) + 1
    db.flush()
    log.info("ML override updated: name=%s enabled=%s", name, body["enabled"])
    return {"name": row.name, "ml_override": {"enabled": bool(body["enabled"])}}


@router.get("/{name}/export")
def export_strategy(name: str, db: Session = Depends(get_db)):
    """GET /strategies/{name}/export — export config as JSON."""
    detail = _strategy_detail(db, name)
    return detail


@router.post("/new")
def create_strategy(body: dict[str, Any], db: Session = Depends(get_db)):
    """POST /strategies/new — create a new strategy record."""
    name = body.get("name", "").strip().lower().replace(" ", "_")
    if not name:
        raise HTTPException(400, "body.name is required")
    existing = db.query(StrategyConfig).filter(StrategyConfig.name == name).first()
    if existing:
        raise HTTPException(409, f"Strategy {name} already exists")
    rec = StrategyConfig(
        name=name,
        label=body.get("label", name.replace("_", " ").title()),
        symbol=body.get("symbol", ""),
        timeframe=body.get("timeframe", ""),
        is_active=False,
        params=body.get("params", {}),
        version=1,
    )
    db.add(rec)
    db.flush()
    log.info("New strategy created: name=%s", name)
    return {"name": rec.name, "label": rec.label, "version": 1}


@router.get("/evidence")
def all_evidence(limit: int = 50, db: Session = Depends(get_db)):
    """GET /strategies/evidence — combined event log across all strategies."""
    from db.models import BacktestRun as _BR
    events = []
    # Fetch recent backtests from all strategies
    runs = db.query(_BR).order_by(_BR.created_at.desc()).limit(limit // 2).all()
    for r in runs:
        events.append({
            "strategy_name": r.strategy_name,
            "type": "backtest",
            "status": r.status,
            "params": r.params or {},
            "timestamp": r.created_at.isoformat() if r.created_at else None,
        })
    # Fetch recent trades from all strategies
    trades = db.query(Trade).order_by(Trade.entry_time.desc()).limit(limit // 2).all()
    for t in trades:
        events.append({
            "strategy_name": t.strategy_name,
            "type": "trade",
            "side": t.side.value if hasattr(t.side, "value") else str(t.side),
            "symbol": t.symbol,
            "pnl_r": t.pnl_r,
            "timestamp": t.entry_time.isoformat() if t.entry_time else None,
        })
    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return events[:limit]
