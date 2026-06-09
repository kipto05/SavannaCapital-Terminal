"""
execution/risk_manager.py — real-time risk gating.

Blocks orders when limits are breached. Runs in the engine loop before
any order hits the broker. All limits read from SettingsService.
"""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

from config.settings import config
from db.session import SessionLocal
from db.models import Trade
from db.settings_service import SettingsService

log = logging.getLogger(__name__)


class RiskManager:
    """
    Hard risk limits for the engine loop.

    Checked before every order submission. Returns a blocking reason string
    on violation; empty string means the order may proceed.
    """

    def __init__(self) -> None:
        self._daily_pnl: float = 0.0
        self._today: Optional[date] = None
        self._session: Optional[SessionLocal] = None

    def _ensure_session(self) -> None:
        if self._session is None:
            self._session = SessionLocal()

    def _sync_day(self) -> None:
        today = datetime.utcnow().date()
        if today != self._today:
            self._daily_pnl = 0.0
            self._today = today

    def check_before_order(
        self,
        symbol: str,
        account_equity: float,
        initial_equity: float = 10_000.0,
    ) -> str:
        """
        Evaluate current risk exposure against configured limits.

        Returns "" if OK, non-empty blocking reason if not.
        """
        blocking = ""
        try:
            self._sync_day()
            cfg = self._effective_config()

            # ── Max open trades ──────────────────────────────────────────────
            open_count = self._open_trade_count()
            if open_count >= cfg["max_open_trades"]:
                blocking = f"max open trades reached ({open_count}/{cfg['max_open_trades']})"
                log.warning("Order blocked: %s", blocking)

            # ── Daily drawdown ───────────────────────────────────────────────
            daily_dd = self._compute_daily_drawdown(initial_equity)
            if daily_dd >= cfg["max_daily_drawdown"]:
                blocking = (
                    f"daily drawdown {daily_dd:.2%} ≥ "
                    f"max {cfg['max_daily_drawdown']:.2%}"
                )
                log.warning("Order blocked: %s", blocking)

            # ── Total drawdown ───────────────────────────────────────────────
            total_dd = self._compute_total_drawdown(initial_equity)
            if total_dd >= cfg["max_total_drawdown"]:
                blocking = (
                    f"total drawdown {total_dd:.2%} ≥ "
                    f"max {cfg['max_total_drawdown']:.2%}"
                )
                log.warning("Order blocked: %s", blocking)

        except Exception as exc:
            log.exception("RiskManager.check_before_order failed: %s", exc)

        if blocking:
            log.warning("Risk limit hit: %s", blocking)
        return blocking

    def _effective_config(self) -> dict:
        with SessionLocal() as db:
            svc = SettingsService(db)
            return svc.get_effective_risk_config()

    def _open_trade_count(self) -> int:
        with SessionLocal() as db:
            return db.query(Trade).filter(Trade.is_active.is_(True)).count()

    def _compute_daily_drawdown(self, initial_equity: float) -> float:
        if initial_equity <= 0:
            return 0.0
        return abs(self._daily_pnl) / initial_equity if self._daily_pnl < 0 else 0.0

    def _compute_total_drawdown(self, initial_equity: float) -> float:
        # A true total DD should use the peak equity; simplified here:
        # uses the sum of all PnLs from closed trades
        with SessionLocal() as db:
            closed_pnl = (
                db.query(Trade)
                .filter(Trade.is_active.is_(False), Trade.pnl.isnot(None))
                .all()
            )
        total_pnl = sum(t.pnl for t in closed_pnl if t.pnl is not None)
        if initial_equity + total_pnl <= 0:
            return 1.0
        drawdown_from_peak = max(0.0, -(total_pnl / (initial_equity + total_pnl)))
        return min(drawdown_from_peak, 1.0)
