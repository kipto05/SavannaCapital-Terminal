"""engine/engine_loop.py - main trading engine loop extracted from main.py.

Design
------
Phased loop so each concern is independently testable and replaceable.

Phase 0 : Pre-flight - connection, DB, daily sync, circuit breakers
Phase 1 : Account snapshot (periodic, configurable cadence)
Phase 2 : Strategy scan - one strategy at a time, one bar at a time
Phase 3 : Risk gate - per-candidate, before any order submission
Phase 4 : Order submission - submit, log, persist trades
Phase 5 : Open position management - TP1/BE, trailing stop, partial close
Phase 6 : AI advisor - fire & forget, non-blocking
Phase 7 : ML prediction layer - non-blocking, do not interrupt order flow
Phase 8 : Quant research trigger - periodic backtest refresh (weekly+)
Phase 9 : Shutdown check + sleep

Usage
-----
Loop is run as a daemon thread by main.py:
    loop = EngineLoop(cfg, adapter)
    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    loop.stop()  # on shutdown
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


# -- Helpers --------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _utcnow().date()


# -- Circuit breaker state -------------------------------------------------------


class _CircuitBreakerState:
    """Mutable state held by the engine loop across iterations."""

    def __init__(self) -> None:
        self.shutdown: bool = False
        self.last_snapshot_ts: float = 0.0
        self.today_date: date = _today()
        self.daily_pnl: float = 0.0
        self.last_ai_suggestion_ts: dict[str, float] = {}
        self.last_ml_retrain_trade_count: int = 0
        self.last_quant_run_ts: float = 0.0
        # Scan stats - reset each iteration, published to state at end
        self.last_scan_symbols: list[str] = []
        self.last_scan_signals_generated: int = 0
        self.last_scan_trades_executed: int = 0
        self.mt5_connected: bool = False
        self.circuit_breaker_tripped: bool = False
        self.breaker_tripped_at: float = 0.0

    def sync_day(self) -> None:
        now = _today()
        if now != self.today_date:
            self.today_date = now
            self.daily_pnl = 0.0


# -- Engine loop ----------------------------------------------------------------


class EngineLoop:
    """Orchestrates all engine phases in a background thread."""

    def __init__(self, cfg: Any, adapter: Any) -> None:
        self.cfg = cfg
        self.adapter = adapter
        self.state = _CircuitBreakerState()
        self._stop_event = threading.Event()
        self._started_ts = time.time()

    # ══════════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Main loop - call from a daemon thread."""
        log.info(
            "Engine loop started - polling every %ds",
            self.cfg.engine.poll_interval_seconds,
        )
        while not self._stop_event.is_set():
            iteration_start = time.monotonic()
            try:
                self._run_one_iteration()
            except Exception:
                log.exception("Engine loop iteration error")
            self._sleep_until_next(iteration_start)

        self._on_stop()
        log.info("Engine loop stopped")

    def stop(self) -> None:
        """Signal the loop to halt after the current iteration."""
        log.info("Engine loop stop requested")
        self._stop_event.set()

    # ══════════════════════════════════════════════════════════════════════════
    # One iteration - calls each phase in sequence
    # ══════════════════════════════════════════════════════════════════════════

    def _run_one_iteration(self) -> None:
        with _db_session() as db:
            if not self._phase_preflight(db):
                return

            self._phase_snapshot(db)

            if self._is_tripped(db):
                self._phase_circuit_breached(db)
                return

            enabled = _get_enabled_strategies(db)
            account_info = self.adapter.account_info()
            equity = self._safe_equity(account_info)

            self._phase_scan(db, enabled, equity)

            self._phase_position_mgmt(db, equity)

            # Non-blocking hooks - log failures silently
            self._phase_ai_advisor(db, equity)
            self._phase_ml_prediction(db, equity)
            self._phase_quant_trigger(db)

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 0 - Pre-flight
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_preflight(self, db: Any) -> bool:
        """Return True if the loop should continue, False to skip the iteration."""
        if not self.adapter.is_connected():
            log.warning("MT5 disconnected - attempting reconnect")
            if not self._attempt_reconnect():
                log.error("Reconnect failed - skipping iteration")
                return False

        self.state.mt5_connected = self.adapter.is_connected()
        self.state.sync_day()
        return True

    def _attempt_reconnect(self, max_attempts: int = 3) -> bool:
        delay = self.cfg.engine.reconnect_delay_seconds
        for attempt in range(1, max_attempts + 1):
            try:
                if self.adapter.connect():
                    log.info("MT5 reconnected on attempt %d", attempt)
                    return True
            except Exception as exc:
                log.warning("Reconnect attempt %d/%d failed: %s", attempt, max_attempts, exc)
            time.sleep(delay)
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 1 - Account snapshot
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_snapshot(self, db: Any) -> None:
        now_ts = time.time()
        interval = self.cfg.engine.snapshot_interval_seconds
        if interval <= 0 or (now_ts - self.state.last_snapshot_ts) < interval:
            return

        info = self.adapter.account_info()
        if info is None:
            return

        try:
            from db.models import AccountSnapshot
            snap = AccountSnapshot(
                balance=float(info.get("balance", 0)),
                equity=float(info.get("equity", 0)),
                margin=float(info.get("margin", 0)),
                free_margin=float(info.get("margin_free", 0)),
                profit=float(info.get("profit", 0)),
                created_at=_utcnow(),
            )
            db.add(snap)
            db.flush()
            log.info(
                "Account snapshot: bal=%.2f eq=%.2f margin=%.2f pnl=%.2f",
                snap.balance, snap.equity, snap.margin, snap.profit,
            )
            self.state.last_snapshot_ts = now_ts
        except Exception:
            log.exception("Account snapshot failed")

        self._publish_state()

    # ══════════════════════════════════════════════════════════════════════════
    # Circuit breaker
    # ══════════════════════════════════════════════════════════════════════════

    def _is_tripped(self, db: Any) -> bool:
        today_str = self.state.today_date.isoformat()
        from sqlalchemy import func
        from db.models import Trade
        todays_pnl = (
            db.query(func.coalesce(func.sum(Trade.pnl), 0.0))
            .filter(Trade.source == "live")
            .filter(func.date(Trade.created_at) == today_str)
            .scalar()
        )
        self.state.daily_pnl = float(todays_pnl)

        equity = self._safe_equity(self.adapter.account_info())
        risk_cfg = self.cfg.engine.circuit_breaker

        if equity <= 0:
            equity = 10_000.0

        daily_loss_pct = abs(self.state.daily_pnl) / equity
        if daily_loss_pct >= risk_cfg.max_daily_loss_pct:
            log.critical(
                "CIRCUIT BREAKER TRIPPED - daily loss %.2f%% exceeds %.2f%%",
                daily_loss_pct * 100, risk_cfg.max_daily_loss_pct * 100,
            )
            return True

        return False

    def _phase_circuit_breached(self, db: Any) -> None:
        """When tripped - halt new orders but keep loop alive for monitoring."""
        log.warning("Circuit breaker active - no new orders this iteration")

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 2 - Strategy scan
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_scan(self, db: Any, enabled: list[Any], equity: float) -> None:
        from execution.position_sizer import PositionSizer
        from execution.risk_manager import RiskManager
        from execution.sl_tp_model import DynamicSLTPModel
        from execution.mt5_adapter import MT5Adapter
        from strategies.registry import StrategyRegistry
        import pandas as pd
        import MetaTrader5 as mt5

        risk_mgr = RiskManager()
        sizer = PositionSizer()
        sltp = DynamicSLTPModel()
        reg = StrategyRegistry(db)
        reg._seed_if_needed(db)

        # Pre-load all enabled class references once
        class_map = reg.classes

        scanned_symbols: list[str] = []
        self.state.last_scan_signals_generated = 0
        self.state.last_scan_trades_executed = 0
        for strat in enabled:
            cls = class_map.get(strat.name)
            if cls is None:
                log.debug("Engine: class not registered for %s", strat.name)
                continue

            symbol = _resolve_symbol(strat, self.cfg.mt5.server)
            timeframe = _resolve_timeframe(strat)
            params = strat.params or {}

            # Fetch data
            df = _fetch_ohlcv_mt5(symbol, timeframe, strat.name)
            if df is None or len(df) < self.cfg.engine.min_bars_required:
                log.debug(
                    "Engine: %s %s - insufficient bars (%d)",
                    strat.name, symbol, len(df) if df is not None else 0,
                )
                continue

            instance = cls(default_symbol=symbol, params=params)
            # Build multi-TF data bundle (primary + any required secondary TFs)
            tf_data: dict[str, pd.DataFrame] = {timeframe: df}
            req = getattr(getattr(instance, "meta", None), "required_timeframes", []) or []
            for extra_tf in req:
                if extra_tf == timeframe or extra_tf in tf_data:
                    continue
                extra_df = _fetch_ohlcv_mt5(symbol, extra_tf, strat.name)
                if extra_df is not None and not extra_df.empty:
                    tf_data[extra_tf] = extra_df
                    log.debug(
                        "Engine: loaded %d bars for %s %s (%s)",
                        len(extra_df), symbol, extra_tf, strat.name,
                    )
            try:
                signal = instance.generate_signal(tf_data)
            except Exception:
                log.exception("Engine: %s generate_signal error", strat.name)
                continue

            if signal is None:
                continue

            # SL/TP
            sltp_result = sltp.compute(
                df=df, side=signal.side.value, entry=signal.entry
            )
            if sltp_result is None:
                log.debug("Engine: %s - RR gate blocked", strat.name)
                continue

            lot_size = sizer.compute(
                account_equity=equity,
                entry=signal.entry,
                sl=sltp_result.sl,
                symbol=symbol,
            )
            if lot_size is None or lot_size <= 0:
                log.debug(
                    "Engine: %s - position sizing returned %.5f",
                    strat.name, lot_size if lot_size is not None else 0,
                )
                continue

            # Build candidate
            candidate = {
                "symbol": symbol,
                "side": signal.side.value,
                "entry": signal.entry,
                "sl": sltp_result.sl,
                "tp": sltp_result.tp2,
                "tp1": sltp_result.tp1,
                "tp2": sltp_result.tp2,
                "lot_size": lot_size,
                "strategy_name": strat.name,
                "tag": signal.tag,
                "timeframe": timeframe,
                "sltp_result": sltp_result,
            }

            # Risk gate
            block_reason = risk_mgr.check_before_order(
                symbol=symbol,
                account_equity=equity,
            )
            if block_reason:
                log.warning("Engine: order blocked - %s", block_reason)
                continue

            # Safety guard
            if candidate["sl"] is None or candidate["tp"] is None:
                log.error(
                    "Engine: order blocked - missing SL/TP for %s %s",
                    strat.name, symbol,
                )
                continue

            if not (self.cfg.risk.min_lot_size <= lot_size <= self.cfg.risk.max_lot_size):
                log.error(
                    "Engine: order blocked - lot %.5f outside [%.2f-%.2f] for %s",
                    lot_size, self.cfg.risk.min_lot_size,
                    self.cfg.risk.max_lot_size, strat.name,
                )
                continue

            # Submit
            from execution.order_manager import OrderManager
            order_mgr = OrderManager(self.adapter)
            trade = order_mgr.submit(
                candidate, df={timeframe: df}, account_equity=equity
            )
            if trade is not None:
                log.info(
                    "Engine: trade executed - %s %s lots=%.2f ticket=%s",
                    trade.symbol, trade.side.value, trade.lot_size,
                    getattr(trade, "ticket", "?"),
                )

        self.state.last_scan_symbols = scanned_symbols

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 5 - Open position management
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_position_mgmt(self, db: Any, equity: float) -> None:
        """Manage all open MT5 positions: BE stop, trailing stop, partial close."""
        positions = self.adapter.get_open_positions()
        if not positions:
            return

        from execution.mt5_adapter import MT5Adapter
        from execution.sl_tp_model import DynamicSLTPModel

        sltp = DynamicSLTPModel()

        for pos in positions:
            ticket = pos.get("ticket")
            symbol = pos.get("symbol", "")
            side = pos.get("type", "buy")
            entry = float(pos.get("price_open", 0))
            sl = float(pos.get("sl", 0))
            tp = float(pos.get("tp", 0))
            volume = float(pos.get("volume", 0))

            if entry <= 0:
                continue

            # Fetch fresh prices
            tick = self.adapter.get_symbol_info(symbol)
            if tick is None:
                continue
            current = float(tick.get("bid" if side == "buy" else "ask", 0))
            if current <= 0:
                continue

            pnl_r = sltp.pnl_in_r(
                entry=entry, sl=sl, current=current, side=side
            )
            if pnl_r is None:
                continue

            # TP1 hit → move SL to breakeven
            if pnl_r >= 1.0 and sl > 0 and sl < entry:
                log.info("Engine: position %s hit TP1 - moving SL to breakeven", ticket)
                self.adapter.modify_position(
                    ticket=ticket, sl=entry, tp=tp
                )

            # Trail SL beyond BE
            if pnl_r >= self.cfg.sltp.trail_activate_rr and sl > entry:
                new_sl = sltp.compute_trailing_sl(
                    side=side, entry=entry, atr_mult=self.cfg.sltp.trail_atr_mult,
                    current_price=current,
                )
                if new_sl is not None and new_sl > sl:
                    log.info(
                        "Engine: position %s trailing SL to %.5f (RR=%.1f)",
                        ticket, new_sl, pnl_r,
                    )
                    self.adapter.modify_position(
                        ticket=ticket, sl=new_sl, tp=tp
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 6 - AI advisor (non-blocking)
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_ai_advisor(self, db: Any, equity: float) -> None:
        try:
            from ai_advisor.advisor import AIAdvisor
            advisor = AIAdvisor(cfg=self.cfg)
            enabled = _get_enabled_strategies(db)
            for strat in enabled:
                symbol = _resolve_symbol(strat, self.cfg.mt5.server)
                tf = _resolve_timeframe(strat)
                cooldown = self.cfg.ai.cooldown_minutes * 60
                last = self.state.last_ai_suggestion_ts.get(symbol, 0)
                if time.monotonic() - last < cooldown:
                    continue
                df = _fetch_ohlcv_mt5(symbol, tf, f"ai_advisor_{symbol}")
                if df is None or len(df) < 20:
                    continue
                trades = _recent_trades(db, symbol=symbol, limit=20)
                suggestion = advisor.suggest(
                    symbol=symbol, timeframe=tf, df=df,
                    stats={}, trades=trades,
                )
                if suggestion is None:
                    continue
                if suggestion.get("confidence", 0) < self.cfg.ai.min_confidence_to_show:
                    continue
                from db.models import AIAdvisorSuggestion
                db.add(AIAdvisorSuggestion(
                    symbol=symbol,
                    timeframe=tf,
                    side=suggestion["side"],
                    confidence=suggestion["confidence"],
                    reasoning=suggestion.get("reasoning", ""),
                    source="ai_advisor",
                    status="pending",
                ))
                db.flush()
                self.state.last_ai_suggestion_ts[symbol] = time.monotonic()
                log.info(
                    "AIAdvisor: %s %s conf=%.2f",
                    symbol, suggestion["side"], suggestion["confidence"],
                )
        except Exception:
            log.debug("AIAdvisor phase skipped: %s", __import__("traceback").format_exc())

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 7 - ML prediction (non-blocking)
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_ml_prediction(self, db: Any, equity: float) -> None:
        try:
            from ml.predictor import Predictor
            from ml.feature_engineer import build_features
            predictor = Predictor()
            symbols = _active_ml_symbols(db)
            for symbol in symbols:
                df = _fetch_ohlcv_mt5(symbol, "H1", f"ml_{symbol}")
                if df is None or len(df) < 40:
                    continue
                try:
                    X, _y, _names = build_features(df)
                except (ValueError, Exception) as exc:
                    log.debug("ML %s feature build failed: %s", symbol, exc)
                    continue
                if X is None or len(X) == 0:
                    continue
                prediction = predictor.predict(X)
                if prediction is None:
                    continue
                confidence = float(prediction.get("confidence", 0))
                if confidence < self.cfg.ml.prediction_threshold:
                    log.debug(
                        "ML %s confidence %.2f below threshold %.2f",
                        symbol, confidence, self.cfg.ml.prediction_threshold,
                    )
                    continue
                from db.models import MLPredictionHistory
                db.add(MLPredictionHistory(
                    symbol=symbol,
                    timeframe="H1",
                    side=str(prediction.get("side", "HOLD")),
                    confidence=confidence,
                    model_version=predictor.current_version(),
                    features_snapshot={},
                ))
                db.flush()
                log.info(
                    "ML %s %s conf=%.2f model=%s",
                    symbol, prediction.get("side"), confidence,
                    predictor.current_version(),
                )
        except Exception:
            log.debug("ML prediction phase skipped")

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 8 - Quant research trigger
    # ══════════════════════════════════════════════════════════════════════════

    def _phase_quant_trigger(self, db: Any) -> None:
        """Run backtest refresh if new data is available (weekly cadence)."""
        now_ts = time.time()
        interval = self.cfg.engine.quant_trigger_interval_seconds
        if interval <= 0 or (now_ts - self.state.last_quant_run_ts) < interval:
            return

        self.state.last_quant_run_ts = now_ts
        log.info("Quant research trigger - scheduling backtest refresh")

    # ══════════════════════════════════════════════════════════════════════════
    # Shutdown
    # ══════════════════════════════════════════════════════════════════════════

    def _on_stop(self) -> None:
        self._publish_state()
        try:
            self.adapter.disconnect()
        except Exception:
            pass

    def _sleep_until_next(self, iteration_start: float) -> None:
        elapsed = time.monotonic() - iteration_start
        remaining = self.cfg.engine.poll_interval_seconds - elapsed
        if remaining <= 0:
            return
        # Sleep in small ticks so stop() responds fast
        ticks = int(remaining * 10)
        for _ in range(ticks):
            if self._stop_event.is_set():
                return
            time.sleep(0.1)

    # ══════════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _publish_state(self) -> None:
        """Push current state to the shared EngineState for API routes."""
        try:
            from engine.state import update
            update(
                running=True,
                started_at=self._started_ts,
                last_iteration_ts=time.time(),
                last_snapshot_ts=self.state.last_snapshot_ts,
                last_quant_trigger_ts=self.state.last_quant_run_ts,
                circuit_breaker_tripped=self.state.circuit_breaker_tripped,
                breaker_tripped_at=self.state.breaker_tripped_at,
                today_date=self.state.today_date.isoformat(),
                daily_pnl=self.state.daily_pnl,
                last_scan_symbols=self.state.last_scan_symbols,
                last_scan_signals_generated=self.state.last_scan_signals_generated,
                last_scan_trades_executed=self.state.last_scan_trades_executed,
                mt5_connected=self.state.mt5_connected,
            )
        except Exception:
            log.debug("Engine: state publish failed")

    def _safe_equity(self, info: Optional[dict]) -> float:
        if info is None:
            return 10_000.0
        return float(info.get("equity", 0)) or 10_000.0


# -- Free helpers used across phases -------------------------------------------


def _db_session():
    """Context manager yielding a SQLAlchemy session."""
    from contextlib import contextmanager
    from db.session import SessionLocal

    @contextmanager
    def _ctx():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _ctx()


def _get_enabled_strategies(db: Any) -> list[Any]:
    from strategies.registry import StrategyRegistry
    reg = StrategyRegistry(db)
    reg._seed_if_needed(db)
    return reg.get_enabled()


def _resolve_symbol(strat: Any, server: str) -> str:
    from config.settings import resolve_broker_symbol
    symbol = strat.params.get("symbol") or strat.name.replace("_", " ").title()
    return resolve_broker_symbol(symbol, server)


def _resolve_timeframe(strat: Any) -> str:
    tf = strat.params.get("timeframe")
    if tf:
        return tf
    return "M15"


def _fetch_ohlcv_mt5(symbol: str, timeframe: str, ctx: str) -> Any:
    import pandas as pd
    import MetaTrader5 as mt5

    mt5tf = getattr(mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_M15)
    bars_raw = mt5.copy_rates_from_pos(symbol, mt5tf, 0, 300)
    if bars_raw is None or len(bars_raw) < 50:
        return None
    df = pd.DataFrame(bars_raw)
    df.rename(
        columns={
            "time": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "volume",
        },
        inplace=True,
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


def _recent_trades(db: Any, symbol: str, limit: int = 20) -> list[Any]:
    from db.models import Trade
    return (
        db.query(Trade)
        .filter(Trade.symbol == symbol)
        .order_by(Trade.created_at.desc())
        .limit(limit)
        .all()
    )


def _active_ml_symbols(db: Any) -> list[str]:
    from db.models import MLModel
    return [row.symbol for row in db.query(MLModel.symbol).distinct().all() if row.symbol]
