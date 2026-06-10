"""
execution/mt5_adapter.py — MetaTrader 5 adapter for JustMarkets.

Bridges the broker-agnostic OrderManager to the live MT5 terminal.
All MT5 package calls are isolated here; nothing in the rest of the codebase
imports metatrader5 directly.

Broker note: JustMarkets appends .m (lowercase) to symbol names
(e.g. XAUUSD.m, EURUSD.m). The _symbol() helper always produces the
correct lowercase .m form, stripping any existing suffix first.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from config.settings import config

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


def _symbol(name: str) -> str:
    """Normalize a canonical symbol name for JustMarkets MT5.

    Strips any existing suffix and appends the lowercase .m that
    JustMarkets uses. Idempotent: passing "XAUUSD.m" returns "XAUUSD.m".
    Examples:
        XAUUSD -> XAUUSD.m
        xauusd -> XAUUSD.m
        XAUUSD.m -> XAUUSD.m
        xauusd.m -> XAUUSD.m
        EURUSD -> EURUSD.m
    """
    n = name.strip()
    base = n[:-2] if n.lower().endswith(".m") else n
    return base.upper() + ".m"


class MT5Adapter:
    """Thin wrapper around the MetaTrader5 Python package.

    Calling pattern:
        adapter = MT5Adapter()
        adapter.connect()
        result = adapter.place_order(symbol, side, lot_size, ...)
        adapter.disconnect()
    """

    def __init__(self) -> None:
        self.cfg = config.mt5
        self._connected = False

    def connect(self) -> bool:
        """Initialise MT5 connection. Returns True on success."""
        if mt5 is None:
            log.error("MT5 package not installed — cannot connect")
            return False

        ok = mt5.initialize(
            path=self.cfg.path,
            login=self.cfg.login,
            password=self.cfg.password,
            server=self.cfg.server,
            timeout=self.cfg.timeout,
        )
        if not ok:
            err = mt5.last_error() if mt5 else "unknown"
            log.error("MT5 initialise failed: %s", err)
            return False

        self._connected = True
        log.info(
            "MT5 connected: login=%d server=%s path=%s",
            self.cfg.login,
            self.cfg.server,
            self.cfg.path,
        )
        return True

    def disconnect(self) -> None:
        """Shut down the MT5 connection."""
        if mt5 is not None and self._connected:
            mt5.shutdown()
            self._connected = False
            log.info("MT5 disconnected")

    def broker_symbol(self, name: str) -> str:
        """Alias kept for backward compatibility."""
        return _symbol(name)

    def account_info(self) -> dict[str, Any] | None:
        """Return account snapshot dict or None on failure."""
        if not self._connected:
            log.warning("MT5 not connected — cannot fetch account info")
            return None
        info = mt5.account_info()
        if info is None:
            log.warning("MT5 account_info failed: %s", mt5.last_error())
            return None
        return info._asdict()

    def positions_get(
        self, symbol: str = ""
    ) -> list[dict[str, Any]] | None:
        """Return list of open position dicts for a symbol (all if empty)."""
        if not self._connected:
            return None
        positions = mt5.positions_get(symbol=_symbol(symbol) if symbol else "")
        if positions is None:
            log.warning(
                "MT5 positions_get failed for %s: %s",
                _symbol(symbol),
                mt5.last_error(),
            )
            return None
        return [p._asdict() for p in positions]

    def orders_get(
        self, symbol: str = ""
    ) -> list[dict[str, Any]] | None:
        """Return list of pending order dicts for a symbol (all if empty)."""
        if not self._connected:
            return None
        orders = mt5.orders_get(symbol=_symbol(symbol) if symbol else "")
        if orders is None:
            log.warning(
                "MT5 orders_get failed for %s: %s",
                _symbol(symbol),
                mt5.last_error(),
            )
            return None
        return [o._asdict() for o in orders]

    def history_deals_get(
        self,
        from_dt: datetime,
        to_dt: datetime,
        symbol: str = "",
    ) -> list[dict[str, Any]] | None:
        """Return deal history between two datetimes, optionally filtered by symbol.

        Parameters
        ----------
        from_dt, to_dt : datetime
            UTC datetime range.
        symbol : str
            Canonical symbol name (e.g. "XAUUSD"). Empty for all symbols.

        Returns
        -------
        list[dict] | None
            Deal dicts from MT5, or None if not connected / error.
        """
        if not self._connected or mt5 is None:
            return None
        deals = mt5.history_deals_get(from_dt, to_dt)
        if deals is None:
            log.warning("MT5 history_deals_get failed: %s", mt5.last_error())
            return []
        result = [d._asdict() for d in deals]
        if symbol:
            result = [
                d for d in result
                if d.get("symbol", "").lower() == symbol.lower()
            ]
        return result

    def history_orders_get(
        self,
        from_dt: datetime,
        to_dt: datetime,
        symbol: str = "",
    ) -> list[dict[str, Any]] | None:
        """Return order history between two datetimes, optionally filtered by symbol.

        Parameters
        ----------
        from_dt, to_dt : datetime
            UTC datetime range.
        symbol : str
            Canonical symbol name. Empty for all symbols.

        Returns
        -------
        list[dict] | None
            Order history dicts from MT5, or None on failure.
        """
        if not self._connected or mt5 is None:
            return None
        try:
            orders = mt5.history_orders_get(from_dt, to_dt)
        except AttributeError:
            log.debug("history_orders_get not available in this MT5 build")
            return []
        except Exception as exc:
            log.warning("MT5 history_orders_get failed: %s", exc)
            return None
        if orders is None:
            return []
        result = [o._asdict() for o in orders]
        if symbol:
            result = [
                o for o in result
                if o.get("symbol", "").lower() == symbol.lower()
            ]
        return result

    def place_order(
        self,
        symbol: str,
        side: str,
        lot_size: float,
        entry: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
        deviation: int = 10,
        comment: str = "",
    ) -> dict[str, Any] | None:
        """Send an order to MT5.

        Parameters
        ----------
        symbol : str
            Canonical broker ticker (e.g. "XAUUSD"). .m suffix added automatically.
        side : str
            "BUY" or "SELL".
        lot_size : float
            Standard lot size (0.01 = micro-lot).
        entry : float
            Limit price (0.0 for market order).
        sl, tp : float
            Stop-loss and take-profit prices (0.0 to omit).
        deviation : int
            Max slippage in points.
        comment : str
            MT5 order comment.

        Returns
        -------
        dict with keys: order (ticket), price, volume, deal, retcode
        or None on failure.
        """
        if not self._connected:
            log.error(
                "MT5 not connected — order not sent for %s %s", symbol, side
            )
            return None

        if mt5 is None:
            log.error("MT5 package not available")
            return None

        sym = _symbol(symbol)

        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": round(float(lot_size), 2),
            "type": (
                mt5.ORDER_TYPE_BUY
                if side.upper() == "BUY"
                else mt5.ORDER_TYPE_SELL
            ),
            "deviation": deviation,
            "magic": 0,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        if entry > 0:
            request["price"] = float(entry)
        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error()
            log.error(
                "Order failed for %s %s lots=%.2f: retcode=%s error=%s",
                sym,
                side,
                lot_size,
                result.retcode if result else "N/A",
                err,
            )
            return None

        log.info(
            "Order sent: %s %s lots=%.2f ticket=%d price=%.5f",
            sym,
            side,
            lot_size,
            result.order,
            result.price,
        )
        return {
            "order": result.order,
            "price": result.price,
            "volume": result.volume,
            "deal": result.deal,
            "retcode": result.retcode,
        }

    def close_position(
        self,
        ticket: int | str,
        symbol: str,
        lot: float = 0.0,
    ) -> dict[str, Any] | None:
        """Close an open position by ticket.

        lot = 0.0 closes the full position.
        """
        if not self._connected:
            log.error(
                "MT5 not connected — cannot close ticket=%s", ticket
            )
            return None

        if mt5 is None:
            return None

        sym = _symbol(symbol)
        positions = self.positions_get(symbol)
        if not positions:
            log.warning(
                "No open positions for %s — cannot close ticket=%s",
                sym,
                ticket,
            )
            return None

        pos = next(
            (p for p in positions if str(p.get("ticket")) == str(ticket)),
            None,
        )
        if pos is None:
            log.warning("Ticket %s not found — cannot close", ticket)
            return None

        close_lot = lot if lot > 0 else float(pos["volume"])
        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": round(close_lot, 2),
            "type": (
                mt5.ORDER_TYPE_SELL
                if pos["type"] == mt5.ORDER_TYPE_BUY
                else mt5.ORDER_TYPE_BUY
            ),
            "position": int(ticket),
            "deviation": 10,
            "magic": 0,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = mt5.last_error() if mt5 else None
            log.error(
                "Close failed for ticket=%s: retcode=%s error=%s",
                ticket,
                result.retcode if result else "N/A",
                err,
            )
            return None

        log.info("Position closed: ticket=%s price=%.5f", ticket, result.price)
        return {
            "price": result.price,
            "volume": result.volume,
            "profit": result.profit,
            "deal": result.deal,
        }

    def modify_position(
        self,
        ticket: int | str,
        new_sl: float = 0.0,
        new_tp: float = 0.0,
    ) -> bool:
        """Move SL/TP on an open position."""
        if not self._connected or mt5 is None:
            return False
        request: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "sl": float(new_sl) if new_sl else 0.0,
            "tp": float(new_tp) if new_tp else 0.0,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            log.info(
                "SL/TP modified: ticket=%s sl=%.5f tp=%.5f",
                ticket,
                new_sl,
                new_tp,
            )
        else:
            log.error("Modify failed for ticket=%s", ticket)
        return ok
