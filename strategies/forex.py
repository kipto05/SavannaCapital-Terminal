"""
strategies/forex.py — forex asset-class strategies.

BandReversion — EURUSD  H1/M15 (mean reversion in London + NY sessions)
StochasticTrend — GBPUSD  H1/M15 (stochastic cross in EMA trend direction)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from execution.sl_tp_model import DynamicSLTPModel, SLTPResult
from strategies.base import (
    BaseStrategy,
    Signal,
    Side,
    StrategyMeta,
    atr,
    bollinger,
    ema,
    rsi,
    stochastic,
)

log = logging.getLogger(__name__)

_ASSET_CLASS = "forex"
_DEFAULT_TFS = ["H1", "M15"]


# ── BandReversion ─────────────────────────────────────────────────────────────

class BandReversion(BaseStrategy):
    """
    Bollinger band mean reversion during London + NY session windows.
    RSI confirms the extremum. SL/TP from DynamicSLTPModel.
    """

    meta = StrategyMeta(
        name="band_reversion",
        label="Band Reversion",
        description="Mean reversion from Bollinger extremes during active sessions",
        asset_class=_ASSET_CLASS,
        typical_timeframes=_DEFAULT_TFS,
        default_symbol="EURUSD",
    )

    default_params: dict[str, Any] = {
        "bb_period": 20,
        "bb_std_dev": 2.0,
        "rsi_period": 14,
        "rsi_overbought": 68,
        "rsi_oversold": 32,
        "atr_period": 14,
        "min_atr_pips": 5,
        "pip_value": 0.0001,
        "london_start_hr": 7,
        "london_end_hr": 12,
        "ny_start_hr": 13,
        "ny_end_hr": 17,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "bb_period": (10, 40, 1),
        "bb_std_dev": (1.5, 3.0, 0.1),
        "rsi_period": (7, 21, 1),
        "rsi_overbought": (62, 80, 1),
        "rsi_oversold": (20, 38, 1),
        "atr_period": (7, 21, 1),
        "min_atr_pips": (3, 15, 1),
        "pip_value": (0.00001, 0.001, 0.00001),
        "london_start_hr": (6, 9, 1),
        "london_end_hr": (10, 13, 1),
        "ny_start_hr": (12, 15, 1),
        "ny_end_hr": (16, 20, 1),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "EURUSD", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    def _in_session(self, idx: pd.Timestamp) -> bool:
        p = self.params
        hr = idx.hour  # UTC hour — data must be UTC-indexed
        in_london = p["london_start_hr"] <= hr < p["london_end_hr"]
        in_ny = p["ny_start_hr"] <= hr < p["ny_end_hr"]
        return in_london or in_ny

    def generate_signal(
        self, data: dict[str, pd.DataFrame]
    ) -> Signal | None:
        try:
            tf = self.timeframe
            m15 = data.get(tf)
            if m15 is None or len(m15) < max(self.params["bb_period"], self.params["atr_period"]) + 1:
                log.debug("%s: insufficient %s bars", self.meta.name, tf)
                return None

            p = self.params
            close = m15["close"].iloc[-1]
            curr_ts: pd.Timestamp = m15.index[-1]

            # Session gate
            if not self._in_session(curr_ts):
                log.debug("%s: outside session window at %s", self.meta.name, curr_ts)
                return None

            upper, mid, lower = bollinger(
                m15["close"], period=p["bb_period"], std_dev=p["bb_std_dev"]
            )
            rsi_vals = rsi(m15["close"], p["rsi_period"])
            atr_vals = atr(m15, p["atr_period"])

            if pd.isna(upper.iloc[-1]) or pd.isna(rsi_vals.iloc[-1]):
                return None

            atr_pips = atr_vals.iloc[-1] / p["pip_value"]
            if atr_pips < p["min_atr_pips"]:
                return None

            # LONG: prev close <= lower[-2] AND curr close > lower[-1]  AND rsi was oversold
            if (
                m15["close"].iloc[-2] <= lower.iloc[-2]
                and close > lower.iloc[-1]
                and rsi_vals.iloc[-2] < p["rsi_oversold"]
            ):
                side_v = Side.BUY
                result = self.sltp.compute(df=m15, side=side_v.value, entry=close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long",
                    regime=result.regime,
                )

            # SHORT: prev close >= upper[-2] AND curr close < upper[-1] AND rsi was overbought
            if (
                m15["close"].iloc[-2] >= upper.iloc[-2]
                and close < upper.iloc[-1]
                and rsi_vals.iloc[-2] > p["rsi_overbought"]
            ):
                side_v = Side.SELL
                result = self.sltp.compute(df=m15, side=side_v.value, entry=close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.short",
                    regime=result.regime,
                )

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None


# ── StochasticTrend ───────────────────────────────────────────────────────────

class StochasticTrend(BaseStrategy):
    """
    Stochastic oversold/overbought cross, only in the direction of the H1 EMA trend.
    """

    meta = StrategyMeta(
        name="stochastic_trend",
        label="Stochastic Trend",
        description="Stochastic cross in direction of H1 EMA trend with micro EMA filter",
        asset_class=_ASSET_CLASS,
        typical_timeframes=_DEFAULT_TFS,
        default_symbol="GBPUSD",
    )

    default_params: dict[str, Any] = {
        "trend_ema_period": 50,
        "slope_lookback_bars": 5,
        "stoch_k_period": 14,
        "stoch_d_period": 3,
        "stoch_oversold_level": 35,
        "stoch_overbought_level": 65,
        "micro_ema_period": 8,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "trend_ema_period": (20, 100, 5),
        "slope_lookback_bars": (3, 10, 1),
        "stoch_k_period": (5, 21, 1),
        "stoch_d_period": (2, 5, 1),
        "stoch_oversold_level": (15, 45, 5),
        "stoch_overbought_level": (55, 85, 5),
        "micro_ema_period": (5, 21, 1),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "GBPUSD", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    def generate_signal(
        self, data: dict[str, pd.DataFrame]
    ) -> Signal | None:
        try:
            tf_sig = self.timeframe
            tf_trend = "H1"

            m15 = data.get(tf_sig)
            h1 = data.get(tf_trend)
            if (
                m15 is None
                or h1 is None
                or len(m15) < max(self.params["stoch_k_period"] + 2, self.params["micro_ema_period"] + 2)
                or len(h1) < self.params["trend_ema_period"] + self.params["slope_lookback_bars"] + 2
            ):
                log.debug("%s: insufficient data bars=%d", self.meta.name, len(m15) if m15 is not None else 0)
                return None

            p = self.params
            h1_close = h1["close"]
            trend_ema = ema(h1_close, p["trend_ema_period"])
            if len(trend_ema) < p["slope_lookback_bars"] + 1:
                return None

            curr_close_h1 = h1_close.iloc[-1]
            trend_ema_last = trend_ema.iloc[-1]
            ema_slope = trend_ema_last - trend_ema.iloc[-p["slope_lookback_bars"]]
            bullish = curr_close_h1 > trend_ema_last and ema_slope > 0
            bearish = curr_close_h1 < trend_ema_last and ema_slope < 0

            m15_close = m15["close"]
            k_vals, d_vals = stochastic(
                m15["high"], m15["low"], m15_close,
                p["stoch_k_period"], p["stoch_d_period"],
            )
            micro_ema = ema(m15_close, p["micro_ema_period"])

            if len(k_vals) < 2 or pd.isna(k_vals.iloc[-1]):
                return None

            curr_k = k_vals.iloc[-1]
            prev_k = k_vals.iloc[-2]
            curr_d = d_vals.iloc[-1]
            curr_close = m15_close.iloc[-1]

            # ── LONG ────────────────────────────────────────────────────────
            if bullish and prev_k < d_vals.iloc[-2] and curr_k >= curr_d:
                if curr_k >= p["stoch_oversold_level"]:
                    log.debug("%s: LONG stoch %.1f ≥ oversold %.1f", self.meta.name, curr_k, p["stoch_oversold_level"])
                    return None
                if curr_close <= micro_ema.iloc[-1]:
                    return None
                side_v = Side.BUY
                result = self.sltp.compute(df=m15, side=side_v.value, entry=curr_close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=curr_close,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long",
                    regime=result.regime,
                )

            # ── SHORT ───────────────────────────────────────────────────────
            if bearish and prev_k > d_vals.iloc[-2] and curr_k <= curr_d:
                if curr_k <= p["stoch_overbought_level"]:
                    log.debug("%s: SHORT stoch %.1f ≤ overbought %.1f", self.meta.name, curr_k, p["stoch_overbought_level"])
                    return None
                if curr_close >= micro_ema.iloc[-1]:
                    return None
                side_v = Side.SELL
                result = self.sltp.compute(df=m15, side=side_v.value, entry=curr_close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=curr_close,
                    sl=result.sl,
                    tp=result.tp2,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.short",
                    regime=result.regime,
                )

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
