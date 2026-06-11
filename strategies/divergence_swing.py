"""strategies/divergence_swing.py — DivergenceSwing — XAGUSD M15.

Detects bullish/bearish regular divergence between price RSI and momentum,
filters by ADX regime, and trades the breakout from the divergence bar.
SL/TP from DynamicSLTPModel.
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
    ema,
    rsi,
)

log = logging.getLogger(__name__)

_ASSET_CLASS = "commodity"
_DEFAULT_TFS = ["M15", "H1"]


class DivergenceSwing(BaseStrategy):
    """Regular RSI divergence swing on XAGUSD M15.

    Bullish divergence: price makes lower low but RSI makes higher low.
    Bearish divergence: price makes higher high but RSI makes lower high.
    ADX gate avoids choppy markets. Breakout confirmation from divergence bar.
    """

    meta = StrategyMeta(
        name="divergence_swing",
        label="Divergence Swing",
        description="Regular RSI divergence with ADX regime filter on XAGUSD",
        asset_class=_ASSET_CLASS,
        typical_timeframes=_DEFAULT_TFS,
        default_symbol="XAGUSD",
    )

    default_params: dict[str, Any] = {
        "rsi_period": 14,
        "lookback_bars": 5,
        "adx_period": 14,
        "adx_threshold": 20.0,
        "pip_value": 0.001,
        "min_rr": 1.5,
        "lot_size": 0.01,
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "rsi_period": (7, 21, 1),
        "lookback_bars": (3, 10, 1),
        "adx_period": (10, 25, 1),
        "adx_threshold": (15.0, 35.0, 1.0),
        "pip_value": (0.0001, 0.01, 0.0001),
        "min_rr": (1.0, 3.0, 0.1),
        "lot_size": (0.01, 1.0, 0.01),
    }

    def __init__(self, symbol: str = "", timeframe: str = "", params: dict | None = None):
        super().__init__(symbol=symbol or "XAGUSD", timeframe=timeframe or "M15", params=params)
        self.sltp = DynamicSLTPModel()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Simplified ADX computation."""
        high, low, close = df["high"], df["low"], df["close"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0.0
        minus_dm[minus_dm < 0] = 0.0

        tr = pd.concat(
            [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
            axis=1,
        ).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * plus_dm.rolling(period).mean() / atr.replace(0, np.nan)
        minus_di = 100 * minus_dm.rolling(period).mean() / atr.replace(0, np.nan)
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        return dx.rolling(period).mean()

    @staticmethod
    def _find_lower_lows(series: pd.Series, n: int = 2) -> list[int]:
        """Return indices where a local minimum of width *n* occurs."""
        indices: list[int] = []
        for i in range(n, len(series) - n):
            window = series.iloc[i - n : i + n + 1]
            if series.iloc[i] == window.min():
                indices.append(i)
        return indices

    @staticmethod
    def _find_higher_highs(series: pd.Series, n: int = 2) -> list[int]:
        """Return indices where a local maximum of width *n* occurs."""
        indices: list[int] = []
        for i in range(n, len(series) - n):
            window = series.iloc[i - n : i + n + 1]
            if series.iloc[i] == window.max():
                indices.append(i)
        return indices

    def _bullish_divergence(self, price: pd.Series, rsi_vals: pd.Series, lookback: int) -> bool:
        """Price lower low + RSI higher low within lookback window."""
        if len(price) < lookback * 2 + 2:
            return False
        p_now = price.iloc[-1]
        p_prev = price.iloc[-lookback - 1]
        r_now = rsi_vals.iloc[-1]
        r_prev = rsi_vals.iloc[-lookback - 1]
        return bool(p_now < p_prev and r_now > r_prev and r_now < 50)

    def _bearish_divergence(self, price: pd.Series, rsi_vals: pd.Series, lookback: int) -> bool:
        """Price higher high + RSI lower high within lookback window."""
        if len(price) < lookback * 2 + 2:
            return False
        p_now = price.iloc[-1]
        p_prev = price.iloc[-lookback - 1]
        r_now = rsi_vals.iloc[-1]
        r_prev = rsi_vals.iloc[-lookback - 1]
        return bool(p_now > p_prev and r_now < r_prev and r_now > 50)

    # ── Signal generation ─────────────────────────────────────────────────────

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < self.params["adx_period"] + self.params["lookback_bars"] + 5:
                log.debug("%s: insufficient bars=%d", self.meta.name, len(df) if df is not None else 0)
                return None

            p = self.params
            close = df["close"].iloc[-1]
            # ── ADX regime gate ──────────────────────────────────────────────
            adx = self._adx(df, p["adx_period"])
            if len(adx) < 2 or adx.iloc[-1] < p["adx_threshold"]:
                log.debug("%s: ADX %.1f < threshold %.1f — choppy market", self.meta.name,
                          adx.iloc[-1] if len(adx) else 0, p["adx_threshold"])
                return None

            rsi_vals = rsi(df["close"], p["rsi_period"])

            # ── Bullish divergence ───────────────────────────────────────────
            if self._bullish_divergence(df["close"], rsi_vals, p["lookback_bars"]):
                side_v = Side.BUY
                result = self.sltp.compute(df=df, side=side_v.value, entry=close)
                if result is None:
                    return None
                if result.rr1 < p["min_rr"]:
                    log.debug("%s: RR %.2f < min %.2f — skip", self.meta.name, result.rr1, p["min_rr"])
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
                    regime="ranging",
                )

            # ── Bearish divergence ───────────────────────────────────────────
            if self._bearish_divergence(df["close"], rsi_vals, p["lookback_bars"]):
                side_v = Side.SELL
                result = self.sltp.compute(df=df, side=side_v.value, entry=close)
                if result is None:
                    return None
                if result.rr1 < p["min_rr"]:
                    log.debug("%s: RR %.2f < min %.2f — skip", self.meta.name, result.rr1, p["min_rr"])
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
                    regime="ranging",
                )

            return None
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
