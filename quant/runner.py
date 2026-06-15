"""quant/runner.py — background task that orchestrates a full backtest run.

Flow:
1. Fetch OHLCV data from MT5 via data.repository.fetch_ohlcv()
2. Run bar-by-bar backtest via BacktestEngine
3. Persist BacktestRun + trades to DB
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config.settings import config
from data.repository import fetch_ohlcv
from db.models import BacktestRun, Trade
from db.session import SessionLocal
from quant.backtest_engine import BacktestEngine, BacktestResult

log = logging.getLogger(__name__)


def _to_python(value: Any) -> Any:
    """Convert numpy scalars / arrays to native Python types for SQLAlchemy."""
    if value is None:
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _to_python_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert numpy scalars inside a dict (e.g. params snapshot)."""
    if not isinstance(d, dict):
        return d
    result: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _to_python_dict(v)
        elif isinstance(v, (np.integer, np.floating, np.bool_, np.ndarray)):
            result[k] = _to_python(v)
        elif isinstance(v, (list, tuple)):
            result[k] = [_to_python(x) for x in v]
        else:
            result[k] = v
    return result


def run_backtest_job(
    run_id: int,
    *,
    symbol: str,
    timeframe: str,
    strategy_class: type,
    params: dict[str, Any],
    start_date: str | None = None,
    end_date: str | None = None,
    n_bars: int = 5000,
    initial_equity: float | None = None,
    risk_per_trade: float | None = None,
    warmup_bars: int | None = None,
    execution: str = "OHLC",
) -> None:
    """Execute a backtest job and persist results."""
    db: Session | None = None
    try:
        db = SessionLocal()

        # Mark as running
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if run is None:
            log.error("run_backtest_job: BacktestRun %d not found", run_id)
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.flush()
        log.info(
            "Backtest %d started: %s %s %s",
            run_id, symbol, timeframe, run.strategy_name,
        )

        # Resolve dates
        start_dt: datetime | None = None
        end_dt: datetime | None = None
        if start_date:
            start_dt = pd.Timestamp(start_date, tz="UTC").to_pydatetime()
        if end_date:
            end_dt = pd.Timestamp(end_date, tz="UTC").to_pydatetime()

        # Fetch MT5 data
        log.info(
            "Backtest %d: fetching %s %s (%s -> %s)",
            run_id, symbol, timeframe, start_date, end_date,
        )
        df = fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt,
            n_bars=n_bars if start_dt is None and end_dt is None else 5000,
        )

        if df is None or df.empty:
            raise ValueError(f"No MT5 data returned for {symbol} {timeframe}")

        n_bars_fetched = len(df)
        log.info("Backtest %d: fetched %d bars", run_id, n_bars_fetched)

        # Run engine
        engine = BacktestEngine(
            initial_equity=initial_equity,
            risk_per_trade=risk_per_trade,
            warmup_bars=warmup_bars,
            execution=execution,
        )

        result: BacktestResult = engine.run(
            df=df,
            strategy_class=strategy_class,
            params=params,
            timeframe=timeframe,
            symbol=symbol,
        )

        # Persist summary to BacktestRun
        run.symbol = symbol
        run.timeframe = timeframe
        run.strategy_name = strategy_class.__name__
        run.initial_equity = _to_python(result.initial_equity)
        run.final_equity = _to_python(result.final_equity)
        run.net_pnl_r = _to_python(result.net_pnl_r)
        run.max_drawdown = _to_python(result.max_drawdown)
        run.n_bars = n_bars_fetched
        run.n_trades = len(result.trades)
        run.win_rate = _to_python(result.win_rate)
        run.profit_factor = _to_python(result.profit_factor)
        run.sharpe_approx = _to_python(result.sharpe_approx)
        run.p_value = _to_python(result.p_value)
        run.is_significant = _to_python(result.is_significant)
        run.equity_curve = _safe_json(result.equity_curve)
        run.drawdown_curve = _safe_json(result.drawdown_curve)
        run.monthly_returns = _safe_json(result.monthly_returns)
        run.params_snapshot = _to_python_dict(params)
        run.completed_at = datetime.now(timezone.utc)
        run.status = "complete"
        db.flush()
        log.info(
            "Backtest %d complete: %d trades, PF=%s, net_r=%.2f",
            run_id, run.n_trades, run.profit_factor, run.net_pnl_r,
        )

        # Persist trades
        for t in result.trades:
            trade = Trade(
                strategy_name=strategy_class.__name__,
                symbol=symbol,
                timeframe=timeframe,
                side=t.side,
                opened_at=t.entry_time,
                closed_at=t.exit_time,
                entry=_to_python(t.entry),
                open_price=_to_python(t.entry),
                close_price=_to_python(t.close_price),
                sl=_to_python(t.sl),
                tp=_to_python(t.tp2),
                tp1=_to_python(t.tp1),
                tp2=_to_python(t.tp2),
                lot_size=_to_python(t.lot_size),
                pnl=_to_python(t.pnl_dollars),
                pnl_r=_to_python(t.pnl_r),
                tag=t.tag,
                closed_reason=t.exit_reason,
                source="backtest",
                backtest_run_id=run_id,
            )
            db.add(trade)

        db.commit()
        log.info("Backtest %d: %d trades saved to DB", run_id, len(result.trades))

    except Exception as exc:
        log.exception("Backtest %d FAILED: %s", run_id, exc)
        if db is not None:
            try:
                # Rollback failed transaction so we can query + update the run
                run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
                if run is not None:
                    run.status = "failed"
                    run.error_message = str(exc)
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                log.exception("Failed to mark BacktestRun %d as failed", run_id)
    finally:
        if db is not None:
            db.close()


def _safe_json(value: Any) -> Any:
    """Convert values that might not be JSON-serialisable."""
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json(x) for x in value]
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    return str(value)


def list_runs(db: Session, limit: int = 50, strategy_name: str | None = None) -> list[BacktestRun]:
    """Return recent backtest runs, optionally filtered by strategy."""
    q = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
    if strategy_name:
        q = q.filter(BacktestRun.strategy_name == strategy_name)
    return q.all()


def get_run(db: Session, run_id: int) -> BacktestRun | None:
    """Return a single BacktestRun by id."""
    return db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
