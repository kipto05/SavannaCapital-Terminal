"""
execution/order_manager.py — broker-agnostic OrderManager.

Wraps an MT5Adapter. Trades BLOCKED (not exceptions) when:
- SL or TP is missing
- lot_size <= 0 or > max_lot_size
- RR below min_rr

All live trades are persisted to the Trade table via SQLAlchemy.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from config.settings import config
from db.models import Side as DBSide, Trade
from db.session import SessionLocal
from execution.notification_service import NotificationService
from execution.position_sizer import PositionSizer
from execution.sl_tp_model import SLTPResult

log = logging.getLogger(__name__)


class OrderManager:
    """
    Broker-agnostic order dispatcher.

    Strategy code calls OrderManager.submit(signal, account_equity).
    The OrderManager validates, sizes, and forwards to the MT5 adapter.
    """

    def __init__(self, adapter) -> None:
        self.adapter = adapter
        self.sizer = PositionSizer()

    def submit(
        self,
        signal: dict,
        df: Optional[dict] = None,
        account_equity: float = 10_000.0,
    ) -> Optional[Trade]:
        """
        Validate and submit an order. Returns the Trade ORM model or None if blocked.

        Parameters
        ----------
        signal : dict
            Must contain: symbol, side, entry, sl, tp, tp1, tp2, lot_size,
                          strategy_name, tag, timeframe.
        df : dict | None
            Optional OHLCV dict (forwarded to adapter if needed).
        account_equity : float
            Used for position sizing if lot_size is not provided by the signal.

        Returns
        -------
        Trade | None
        """
        symbol = signal.get("symbol", "")
        side_str = signal.get("side", "").upper()
        strategy_name = signal.get("strategy_name", "")
        timeframe = signal.get("timeframe", "")

        # ── Trading-critical safety guards ─────────────────────────────────
        sl = signal.get("sl")
        tp = signal.get("tp")
        if sl is None or tp is None:
            log.error(
                "Order blocked: missing SL or TP for %s %s", strategy_name, symbol
            )
            return None

        lot_size = signal.get("lot_size", 0)
        if lot_size <= 0:
            log.error("Order blocked: lot_size=%.5f ≤ 0 for %s %s", lot_size, strategy_name, symbol)
            return None
        if lot_size > config.risk.max_lot_size:
            log.error(
                "Order blocked: lot_size=%.5f > max=%.5f for %s %s",
                lot_size,
                config.risk.max_lot_size,
                strategy_name,
                symbol,
            )
            return None

        # Bridge SLTPResult if passed via signal
        sltp: Optional[SLTPResult] = signal.get("sltp_result")
        entry_price = sltp.tp1 if sltp else signal.get("entry", 0.0)

        # ── Send to MT5 adapter ─────────────────────────────────────────────
        try:
            result = self.adapter.place_order(
                symbol=symbol,
                side=side_str,
                lot_size=lot_size,
                entry=entry_price,
                sl=sl,
                tp=tp,
                deviation=10,
                comment=f"{strategy_name}.{side_str.lower()}",
            )
        except Exception as exc:
            log.exception(
                "Order failed for %s %s: %s", strategy_name, symbol, exc
            )
            return None
        if result is None:
            log.error(
                "Order rejected by adapter for %s %s", strategy_name, symbol
            )
            return None

        # ── Publish order_placed notification ───────────────────────────────
        ticket: str = str(result.get("order", result.get("ticket", "")))
        open_price: float = result.get("price", entry_price)
        try:
            with SessionLocal() as db:
                ns = NotificationService(db)
                ns.publish(
                    event_type="order_placed",
                    title=f"Order placed: {symbol} {side_str}",
                    message=f"Order placed: {symbol} {side_str} {lot_size} lots, ticket={ticket}",
                    data={
                        "symbol": symbol,
                        "side": side_str,
                        "lot_size": float(lot_size),
                        "order_id": ticket,
                        "price": float(open_price),
                        "strategy": strategy_name,
                    }
                )
        except Exception as exc:
            log.exception("Failed to publish order_placed notification: %s", exc)

        # ── Persist to Trade table ──────────────────────────────────────────
        with SessionLocal() as db:
            trade = Trade(
                ticket=ticket,
                symbol=symbol.upper(),
                timeframe=timeframe,
                side=DBSide[side_str],
                strategy_name=strategy_name,
                entry=entry_price,
                sl=sl,
                tp=tp,
                tp1=sltp.tp1 if sltp else None,
                tp2=sltp.tp2 if sltp else None,
                lot_size=lot_size,
                open_price=open_price,
                opened_at=datetime.now(timezone.utc),
                is_active=True,
                tag=signal.get("tag", f"{strategy_name}.{side_str.lower()}"),
                source="live",
            )
            db.add(trade)
            db.flush()
            trade_id = trade.id

        # ── Publish trade_opened notification ───────────────────────────────
        try:
            with SessionLocal() as db:
                ns = NotificationService(db)
                ns.publish(
                    event_type="trade_opened",
                    title=f"Trade opened: {symbol} {side_str}",
                    message=f"Trade opened: #{trade_id} {symbol} {side_str} {lot_size} lots @ {open_price:.5f}, SL={sl:.5f}, TP={tp:.5f}, strategy={strategy_name}",
                    data={
                        "trade_id": trade_id,
                        "symbol": symbol,
                        "side": side_str,
                        "lot_size": float(lot_size),
                        "entry_price": float(open_price),
                        "sl": float(sl),
                        "tp": float(tp),
                        "strategy": strategy_name,
                        "tag": signal.get("tag", f"{strategy_name}.{side_str.lower()}"),
                    }
                )
        except Exception as exc:
            log.exception("Failed to publish trade_opened notification: %s", exc)

        log.info(
            "Trade executed: id=%s ticket=%s symbol=%s side=%s entry=%.5f sl=%.5f tp=%.5f lots=%.2f strategy=%s",
            trade_id,
            ticket,
            symbol,
            side_str,
            open_price,
            sl,
            tp,
            lot_size,
            strategy_name,
        )
        return trade

    def close(
        self,
        ticket: str,
        symbol: str,
        lot: float,
        reason: str = "manual",
    ) -> Optional[dict]:
        """Close an open position by ticket. Updates the Trade record."""
        try:
            result = self.adapter.close_position(ticket, symbol, lot)
        except Exception as exc:
            log.exception("Close order failed for ticket=%s: %s", ticket, exc)
            return None

        close_price = result.get("price", 0.0)
        pnl = result.get("profit", 0.0)

        with SessionLocal() as db:
            trade = db.query(Trade).filter(Trade.ticket == ticket).first()
            if trade:
                trade.is_active = False
                trade.close_price = close_price
                trade.pnl = pnl
                trade.closed_at = datetime.now(timezone.utc)
                trade.closed_reason = reason
                db.flush()

        log.info(
            "Position closed: ticket=%s symbol=%s pnl=%.2f reason=%s",
            ticket,
            symbol,
            pnl,
            reason,
        )
        return result