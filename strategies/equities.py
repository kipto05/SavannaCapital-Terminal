"""
strategies/equities.py — equity asset-class strategies.

VWAPReversion   — AAPL   M5   (VWAP band reversion during US session)
MACDImpulse     — TSLA   M15  (MACD histogram cross in H1 EMA trend direction)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from execution.sl_tp_model import DynamicSLTPModel as SLTP
from strategies.base import (
    BaseStrategy,
    Signal,
    Side,
    StrategyMeta,
    atr,
    ema,
    macd,
    rsi,
    vwap as _vwap,
)

log = logging.getLogger(__name__)

_ASSET_CLASS = "equity"
_DEFAULT_TFS = ["M5", "M15"]


# ── VWAPReversion ─────────────────────────────────────────────────────────────

class VWAPReversion(BaseStrategy):
    """
    Intraday VWAP standard deviation reversion during US equity session.
    TP moves to VWAP midline when closer than model TP2.
    """

    meta = StrategyMeta(
        name="vwap_reversion",
        label="VWAP Reversion",
        description="Intraday VWAP std deviation mean reversion during US session",
        asset_class=_ASSET_CLASS,
        typical_timeframes=["M5"],
        default_symbol="AAPL",
    )

    default_params: dict[str, Any] = {
        "vwap_band_multiple": 2.0,
        "rsi_period": 9,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "session_start_hr": 14,
        "session_start_min": 30,
        "session_end_hr": 21,
        "session_end_min": 0,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "vwap_band_multiple": (1.0, 3.5, 0.25),
        "rsi_period": (5, 14, 1),
        "rsi_overbought": (62, 82, 1),
        "rsi_oversold": (18, 38, 1),
        "session_start_hr": (13, 15, 1),
        "session_start_min": (0, 59, 5),
        "session_end_hr": (19, 22, 1),
        "session_end_min": (0, 59, 5),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "AAPL", timeframe=timeframe or "M5", params=params)
        self.sltp = DynamicSLTPModel()

    def _in_session(self, ts: pd.Timestamp) -> bool:
        p = self.params
        start = p["session_start_hr"] * 60 + p["session_start_min"]
        end = p["session_end_hr"] * 60 + p["session_end_min"]
        curr = ts.hour * 60 + ts.minute
        return start <= curr < end

    def generate_signal(
        self, data: dict[str, pd.DataFrame]
    ) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < 20:
                log.debug("%s: insufficient bars=%d", self.meta.name, len(df) if df is not None else 0)
                return None
            if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
                return None

            p = self.params
            curr = df.iloc[-1]
            curr_ts = df.index[-1]

            if not self._in_session(curr_ts):
                return None

            vwap_ser = _vwap(df)
            sigma = np.sqrt(
                (
                    ((df["close"] - vwap_ser) ** 2) * df.get("tick_volume", 1.0)
                ).cumsum()
                / df.get("tick_volume", 1.0).cumsum()
            )
            upper = vwap_ser + p["vwap_band_multiple"] * sigma
            lower = vwap_ser - p["vwap_band_multiple"] * sigma

            if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]):
                return None

            rsi_vals = rsi(df["close"], p["rsi_period"])
            close = float(curr["close"])

            # ── LONG: close < lower ────────────────────────────────────────
            if (
                close < lower.iloc[-1]
                and df["close"].iloc[-2] < lower.iloc[-2].iloc[-1]
                if isinstance(lower.iloc[-2], pd.Series)
                else df["close"].iloc[-2] < lower.iloc[-2]
            ):
                side_v = Side.BUY
                result = self.sltp.compute(df=df, side=side_v.value, entry=close)
                if result is None:
                    return None
                tp1 = result.tp1
                tp2 = result.tp2
                vwap_mid = float(vwap_ser.iloc[-1])
                if abs(vwap_mid - close) < abs(result.tp2 - close):
                    tp2 = vwap_mid
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp,
                    tp1=tp1,
                    tp2=tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long",
                    regime=result.regime,
                )

            # ── SHORT: close > upper ───────────────────────────────────────
            if (
                close > upper.iloc[-1]
                and df["close"].iloc[-2] > upper.iloc[-2].iloc[-1]
                if isinstance(upper.iloc[-2], pd.Series)
                else df["close"].iloc[-2] > upper.iloc[-2]
            ):
                side_v = Side.SELL
                result = self.sltp.compute(df=df, side=side_v.value, entry=close)
                if result is None:
                    return None
                tp1 = result.tp1
                tp2 = result.tp2
                vwap_mid = float(vwap_ser.iloc[-1])
                if abs(vwap_mid - close) < abs(result.tp2 - close):
                    tp2 = vwap_mid
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp,
                    tp1=tp1,
                    tp2=tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.short",
                    regime=result.regime,
                )

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None


# ── MACDImpulse ───────────────────────────────────────────────────────────────

class MACDImpulse(BaseStrategy):
    """
    MACD histogram cross, only in direction of H1 EMA trend, during US session.
    """

    meta = StrategyMeta(
        name="macd_impulse",
        label="MACD Impulse",
        description="MACD histogram cross in direction of H1 EMA trend during US session",
        asset_class=_ASSET_CLASS,
        typical_timeframes=["H1", "M15"],
        default_symbol="TSLA",
    )

    default_params: dict[str, Any] = {
        "trend_ema_period": 21,
        "trend_confirm_bar_count": 3,
        "macd_fast_period": 12,
        "macd_slow_period": 26,
        "macd_signal_period": 9,
        "rsi_period": 14,
        "rsi_long_floor": 45,
        "rsi_long_ceiling": 70,
        "rsi_short_floor": 30,
        "rsi_short_ceiling": 55,
        "session_start_hr": 14,
        "session_end_hr": 20,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "trend_ema_period": (8, 50, 1),
        "trend_confirm_bar_count": (1, 5, 1),
        "macd_fast_period": (6, 20, 1),
        "macd_slow_period": (18, 40, 1),
        "macd_signal_period": (5, 15, 1),
        "rsi_period": (7, 21, 1),
        "rsi_long_floor": (35, 55, 2),
        "rsi_long_ceiling": (60, 80, 2),
        "rsi_short_floor": (20, 40, 2),
        "rsi_short_ceiling": (45, 65, 2),
        "session_start_hr": (13, 16, 1),
        "session_end_hr": (18, 22, 1),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "TSLA", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    def _in_session(self, ts: pd.Timestamp) -> bool:
        p = self.params
        return p["session_start_hr"] <= ts.hour < p["session_end_hr"]

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
                or len(m15) < max(self.params["macd_slow_period"] + 2, self.params["trend_confirm_bar_count"] + 1)
                or len(h1) < self.params["trend_ema_period"] + self.params["trend_confirm_bar_count"] + 1
            ):
                log.debug("%s: insufficient data bars=%d", self.meta.name, len(m15) if m15 is not None else 0)
                return None

            p = self.params
            curr_ts = m15.index[-1]
            if not isinstance(curr_ts, pd.Timestamp):
                return None
            if not self._in_session(curr_ts):
                log.debug("%s: outside US session window", self.meta.name)
                return None

            h1_close = h1["close"]
            trend_ema = ema(h1_close, p["trend_ema_period"])
            if len(trend_ema) < p["trend_confirm_bar_count"]:
                return None

            curr_close_h1 = h1_close.iloc[-1]
            last_n_ema = trend_ema.iloc[-p["trend_confirm_bar_count"]:]
            last_n_close = h1_close.iloc[-p["trend_confirm_bar_count"]:]
            bullish = (last_n_close > last_n_ema).all()
            bearish = (last_n_close < last_n_ema).all()

            m15_close = m15["close"]
            macd_line, signal_line, hist = macd(
                m15_close, p["macd_fast_period"], p["macd_slow_period"], p["macd_signal_period"]
            )
            rsi_vals = rsi(m15_close, p["rsi_period"])

            if len(hist) < 2 or pd.isna(hist.iloc[-1]):
                return None

            curr_rsi = rsi_vals.iloc[-1]
            close = float(m15_close.iloc[-1])

            # ── LONG ────────────────────────────────────────────────────────
            if bullish and hist.iloc[-2] < 0 and hist.iloc[-1] >= 0 and macd_line.iloc[-1] > 0:
                if not (p["rsi_long_floor"] < curr_rsi < p["rsi_long_ceiling"]):
                    log.debug("%s: LONG RSI gate %.1f", self.meta.name, curr_rsi)
                    return None
                side_v = Side.BUY
                result = self.sltp.compute(df=m15, side=side_v.value, entry=close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp,
                    tp1=result.tp1,
                    tp2=result.tp2,
                    lot_size=p["lot_size"],
                    tag=f"{self.meta.name}.long",
                    regime=result.regime,
                )

            # ── SHORT ───────────────────────────────────────────────────────
            if bearish and hist.iloc[-2] > 0 and hist.iloc[-1] <= 0 and macd_line.iloc[-1] < 0:
                if not (p["rsi_short_floor"] < curr_rsi < p["rsi_short_ceiling"]):
                    log.debug("%s: SHORT RSI gate %.1f", self.meta.name, curr_rsi)
                    return None
                side_v = Side.SELL
                result = self.sltp.compute(df=m15, side=side_v.value, entry=close)
                if result is None:
                    return None
                return Signal(
                    side=side_v,
                    entry=close,
                    sl=result.sl,
                    tp=result.tp,
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
