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

import pandas as pd
from sqlalchemy.orm import Session

from config.settings import config
from data.repository import fetch_ohlcv
from db.models import BacktestRun, Trade
from db.session import SessionLocal
from quant.backtest_engine import BacktestEngine, BacktestResult

log = logging.getLogger(__name__)


def run_backtest_job(
    run_id: int,
    *,
    # Provided by caller — all resolved before this function is invoked
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
    """Execute a backtest job and persist results.

    This function is designed to be called in a background thread / task
    (e.g. FastAPI BackgroundTasks or a Celery worker). It updates the
    BacktestRun status in the DB as it progresses.

    Parameters
    ----------
    run_id : int
        Primary key of the BacktestRun record to update.
    symbol, timeframe, strategy_class, params : see BacktestEngine.run()
    start_date, end_date : str | None
        ISO dates for MT5 fetch (e.g. "2025-01-01", "2026-01-01").
        If both are None, n_bars is passed instead.
    n_bars : int
        Fallback bar count when dates are not specified.
    initial_equity, risk_per_trade, warmup_bars, execution : see BacktestEngine
    """
    db: Session | None = None
    try:
        db = SessionLocal()

        # ── Mark as running ──────────────────────────────────────────────
        run = db.query(BacktestRun).filter(BacktestRun.id == run_id).first()
        if run is None:
            log.error("run_backtest_job: BacktestRun %d not found", run_id)
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        db.flush()
        log.info("Backtest %d started: %s %s %s", run_id, symbol, timeframe, run.strategy_name)

        # ── Resolve dates ────────────────────────────────────────────────
        start_dt: datetime | None = None
        end_dt: datetime | None = None
        if start_date:
            start_dt = pd.Timestamp(start_date, tz="UTC").to_pydatetime()
        if end_date:
            end_dt = pd.Timestamp(end_date, tz="UTC").to_pydatetime()

        # ── Fetch MT5 data ───────────────────────────────────────────────
        log.info("Backtest %d: fetching %s %s (%s → %s)", run_id, symbol, timeframe, start_date, end_date)
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

        # ── Run engine ──────────────────────────────────────────────────
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

        # ── Persist summary to BacktestRun ──────────────────────────────
        run.symbol = symbol
        run.timeframe = timeframe
        run.strategy_name = strategy_class.__name__
        run.initial_equity = result.initial_equity
        run.final_equity = result.final_equity
        run.net_pnl_r = result.net_pnl_r
        run.max_drawdown = result.max_drawdown
        run.n_bars = n_bars_fetched
        run.n_trades = len(result.trades)
        run.win_rate = result.win_rate
        run.profit_factor = result.profit_factor
        run.sharpe_approx = result.sharpe_approx
        run.p_value = result.p_value
        run.is_significant = result.is_significant
        run.equity_curve = _safe_json(result.equity_curve)
        run.drawdown_curve = _safe_json(result.drawdown_curve)
        run.monthly_returns = _safe_json(result.monthly_returns)
        run.params_snapshot = params
        run.completed_at = datetime.now(timezone.utc)
        run.status = "complete"
        db.flush()
        log.info(
            "Backtest %d complete: %d trades, PF=%s, net_r=%.2f",
            run_id, run.n_trades, run.profit_factor, run.net_pnl_r,
        )

        # ── Persist trades ───────────────────────────────────────────────
        for t in result.trades:
            trade = Trade(
                strategy_name=strategy_class.__name__,
                symbol=symbol,
                side=t.side,
                entry_time=t.entry_time,
                exit_time=t.exit_time,
                entry_price=t.entry,
                exit_price=t.close_price,
                sl=t.sl,
                tp=t.tp2,
                lot_size=t.lot_size,
                pnl_r=t.pnl_r,
                pnl_dollars=t.pnl_dollars,
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_json(value: Any) -> Any:
    """Convert values that might not be JSON-serialisable."""
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json(v) for v in value]
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
