"""
strategies/commodities.py — commodity asset-class strategies.

SessionBreakout — XAUUSD  M15   (London breakout of quiet Asian range)
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from db.session import SessionLocal
from execution.notification_service import NotificationService
from execution.sl_tp_model import DynamicSLTPModel, SLTPResult
from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr

log = logging.getLogger(__name__)

_ASSET_CLASS = "commodity"
_DEFAULT_TFS = ["M15", "H1"]


class SessionBreakout(BaseStrategy):
    """
    London break of the quiet Asian range. Confirmed by body-sized candle
    and ATR. TP2 expanded by range size.
    """

    meta = StrategyMeta(
        name="session_breakout",
        label="Session Breakout",
        description="London breakout of quiet Asian range with momentum confirmation",
        asset_class=_ASSET_CLASS,
        typical_timeframes=_DEFAULT_TFS,
        default_symbol="XAUUSD",
    )

    default_params: dict[str, Any] = {
        "range_session_start_hr": 0,
        "range_session_end_hr": 6,
        "trigger_start_hr": 7,
        "trigger_end_hr": 10,
        "min_range_size": 3.0,
        "max_range_size": 25.0,
        "body_min_atr_multiple": 1.2,
        "tp_range_multiple": 1.5,
        "atr_period": 14,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "range_session_start_hr": (0, 3, 1),
        "range_session_end_hr": (4, 7, 1),
        "trigger_start_hr": (6, 9, 1),
        "trigger_end_hr": (9, 12, 1),
        "min_range_size": (1.0, 8.0, 0.5),
        "max_range_size": (15.0, 50.0, 2.5),
        "body_min_atr_multiple": (0.5, 3.0, 0.1),
        "tp_range_multiple": (1.0, 4.0, 0.25),
        "atr_period": (7, 21, 1),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "XAUUSD", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    def generate_signal(
        self, data: dict[str, pd.DataFrame]
    ) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < self.params["atr_period"] + 2:
                log.debug("%s: insufficient bars=%d", self.meta.name, len(df) if df is not None else 0)
                return None

            if not isinstance(df.index, pd.DatetimeIndex):
                return None
            if df.index.tz is None:
                return None

            p = self.params
            curr = df.iloc[-1]
            curr_ts = df.index[-1]
            curr_hr = curr_ts.hour

            # ── Collect session bars ─────────────────────────────────────
            mask_range = df.index.hour.between(p["range_session_start_hr"], p["range_session_end_hr"] - 1, inclusive="left")
            range_session = df.loc[mask_range]
            if len(range_session) == 0:
                return None

            range_high = float(range_session["high"].max())
            range_low = float(range_session["low"].min())
            range_size = range_high - range_low

            if range_size < p["min_range_size"] or range_size > p["max_range_size"]:
                return None

            # ── Confirm inside trigger window ──────────────────────────
            if not (p["trigger_start_hr"] <= curr_hr < p["trigger_end_hr"]):
                return None

            atr_vals = atr(df, p["atr_period"])
            if pd.isna(atr_vals.iloc[-1]):
                return None

            body = abs(curr["close"] - curr["open"])
            if body < p["body_min_atr_multiple"] * atr_vals.iloc[-1]:
                return None

            # ── LONG breakout ───────────────────────────────────────────
            if curr["close"] > range_high:
                entry = float(curr["close"])
                result = self.sltp.compute(df=df, side=Side.BUY.value, entry=entry)
                if result is None:
                    return None
                if result.tp2 < entry + range_size * p["tp_range_multiple"]:
                    tp2 = entry + range_size * p["tp_range_multiple"]
                    result = SLTPResult(
                        sl=result.sl,
                        tp1=result.tp1,
                        tp2=tp2,
                        regime=result.regime,
                        atr_value=result.atr_value,
                        rr1=result.rr1,
                        rr2=abs(tp2 - entry) / abs(entry - result.sl),
                    )
                signal = Signal(
                    side=Side.BUY,
                    entry=entry,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long",
                    regime=result.regime,
                )

                # Publish notification
                try:
                    with SessionLocal() as db:
                        ns = NotificationService(db)
                        ns.publish(
                            event_type="strategy_signal",
                            title=f"Signal from {self.meta.name}",
                            message=f"{self.meta.name} {signal.side.value} signal on {self.symbol}: entry={signal.entry:.5f}, sl={signal.sl:.5f}, tp={signal.tp:.5f}",
                            data={
                                "strategy": self.meta.name,
                                "symbol": self.symbol,
                                "side": signal.side.value,
                                "entry": float(signal.entry),
                                "sl": float(signal.sl),
                                "tp": float(signal.tp)
                            }
                        )
                except Exception as exc:
                    log.exception("Failed to publish strategy signal notification: %s", exc)

                return signal

            # ── SHORT breakout ──────────────────────────────────────────
            if curr["close"] < range_low:
                entry = float(curr["close"])
                result = self.sltp.compute(df=df, side=Side.SELL.value, entry=entry)
                if result is None:
                    return None
                if result.tp2 > entry - range_size * p["tp_range_multiple"]:
                    tp2 = entry - range_size * p["tp_range_multiple"]
                    result = SLTPResult(
                        sl=result.sl,
                        tp1=result.tp1,
                        tp2=tp2,
                        regime=result.regime,
                        atr_value=result.atr_value,
                        rr1=result.rr1,
                        rr2=abs(entry - tp2) / abs(entry - result.sl),
                    )
                signal = Signal(
                    side=Side.SELL,
                    entry=entry,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.short",
                    regime=result.regime,
                )

                # Publish notification
                try:
                    with SessionLocal() as db:
                        ns = NotificationService(db)
                        ns.publish(
                            event_type="strategy_signal",
                            title=f"Signal from {self.meta.name}",
                            message=f"{self.meta.name} {signal.side.value} signal on {self.symbol}: entry={signal.entry:.5f}, sl={signal.sl:.5f}, tp={signal.tp:.5f}",
                            data={
                                "strategy": self.meta.name,
                                "symbol": self.symbol,
                                "side": signal.side.value,
                                "entry": float(signal.entry),
                                "sl": float(signal.sl),
                                "tp": float(signal.tp)
                            }
                        )
                except Exception as exc:
                    log.exception("Failed to publish strategy signal notification: %s", exc)

                return signal

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
