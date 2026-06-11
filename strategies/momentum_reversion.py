"""strategies/momentum_reversion.py — MomentumReversion — BTCUSD M15.

Pullback-to-fast-EMA in the direction of the H1 EMA trend.
SL/TP from DynamicSLTPModel.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from execution.sl_tp_model import DynamicSLTPModel
from strategies.base import (
    BaseStrategy,
    Signal,
    Side,
    StrategyMeta,
    atr,
    ema,
    rsi,
)

log = logging.getLogger(__name__)


class MomentumReversion(BaseStrategy):
    meta = StrategyMeta(
        name="momentum_reversion",
        label="Momentum Reversion",
        description="Pullback to fast EMA in direction of H1 EMA trend",
        asset_class="crypto",
        typical_timeframes=["H1", "M15"],
            required_timeframes=["H1"],
        default_symbol="BTCUSD",
    )

    default_params: dict[str, Any] = {
        "trend_fast_period": 50,
        "trend_slow_period": 200,
        "entry_ema_period": 21,
        "rsi_period": 14,
        "rsi_long_min": 40,
        "rsi_long_max": 65,
        "rsi_short_min": 35,
        "rsi_short_max": 60,
        "atr_period": 14,
        "min_atr_threshold": 50.0,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "trend_fast_period": (20, 100, 5),
        "trend_slow_period": (100, 300, 10),
        "entry_ema_period": (8, 50, 1),
        "rsi_period": (7, 21, 1),
        "rsi_long_min": (30, 50, 2),
        "rsi_long_max": (55, 75, 2),
        "rsi_short_min": (25, 45, 2),
        "rsi_short_max": (50, 70, 2),
        "atr_period": (7, 21, 1),
        "min_atr_threshold": (20.0, 200.0, 10.0),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "BTCUSD", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        try:
            tf_signal = self.timeframe
            tf_trend = "H1"

            df_sig = data.get(tf_signal)
            df_trend = data.get(tf_trend)
            if (
                df_sig is None
                or df_trend is None
                or len(df_sig) < self.params["trend_slow_period"] + 2
                or len(df_trend) < self.params["trend_slow_period"] + 2
            ):
                log.debug(
                    "%s: insufficient data (sig=%d trend=%d)",
                    self.meta.name,
                    len(df_sig) if df_sig is not None else 0,
                    len(df_trend) if df_trend is not None else 0,
                )
                return None

            p = self.params
            tf_close_sig = df_sig["close"]
            tf_close_trend = df_trend["close"]

            fast_ema = ema(tf_close_trend, p["trend_fast_period"])
            slow_ema = ema(tf_close_trend, p["trend_slow_period"])
            bullish = fast_ema.iloc[-1] > slow_ema.iloc[-1]
            bearish = fast_ema.iloc[-1] < slow_ema.iloc[-1]

            entry_ema_vals = ema(tf_close_sig, p["entry_ema_period"])
            rsi_vals = rsi(tf_close_sig, p["rsi_period"])
            atr_vals = atr(df_sig, p["atr_period"])

            if len(entry_ema_vals) < 2 or pd.isna(entry_ema_vals.iloc[-1]):
                return None

            curr_close = tf_close_sig.iloc[-1]
            prev_close = tf_close_sig.iloc[-2]
            curr_entry_ema = entry_ema_vals.iloc[-1]
            prev_entry_ema = entry_ema_vals.iloc[-2]
            curr_rsi = rsi_vals.iloc[-1]
            curr_atr = atr_vals.iloc[-1]

            # LONG
            if bullish and prev_close < prev_entry_ema and curr_close >= curr_entry_ema:
                if not (p["rsi_long_min"] < curr_rsi < p["rsi_long_max"]):
                    return None
                if curr_atr < p["min_atr_threshold"]:
                    return None

                side_v = Side.BUY
                entry = curr_close
                result = self.sltp.compute(df=df_sig, side=side_v.value, entry=entry)
                if result is None:
                    return None
                return Signal(
                    side=side_v, entry=entry, sl=result.sl, tp=result.tp2,
                    tp1=result.tp1, tp2=result.tp2, lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long", regime=result.regime,
                )

            # SHORT
            if bearish and prev_close > prev_entry_ema and curr_close <= curr_entry_ema:
                if not (p["rsi_short_min"] < curr_rsi < p["rsi_short_max"]):
                    return None
                if curr_atr < p["min_atr_threshold"]:
                    return None

                side_v = Side.SELL
                entry = curr_close
                result = self.sltp.compute(df=df_sig, side=side_v.value, entry=entry)
                if result is None:
                    return None
                return Signal(
                    side=side_v, entry=entry, sl=result.sl, tp=result.tp2,
                    tp1=result.tp1, tp2=result.tp2, lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.short", regime=result.regime,
                )

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
