"""
strategies/base.py — BaseStrategy, Signal, StrategyMeta, Side, and all indicator helpers.

Key enforcement: `__init_subclass__` raises ValueError if any subclass has
param_bounds keys that don't exactly match default_params keys.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class StrategyMeta:
    """Non-param strategy metadata."""
    name: str = ""
    label: str = ""
    description: str = ""
    asset_class: str = ""
    version: str = "1.0.0"
    typical_timeframes: list[str] = field(default_factory=list)
    default_symbol: str = ""


@dataclass
class Signal:
    """Immutable signal produced by a strategy."""
    side: Side
    entry: float
    sl: float | None = None
    tp: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tag: str = ""
    confidence: float = 0.5
    lot_size: float = 0.01
    regime: str = "trending"
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Indicator helpers ─────────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highs, lows, closes = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    stoch_d = stoch_k.rolling(d_period).mean()
    return stoch_k, stoch_d


def vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vol = df.get("tick_volume", pd.Series(1, index=tp.index))
    cum_tp_vol = (tp * vol).cumsum()
    cum_vol = vol.cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def pivot_high(high: pd.Series, left: int = 3, right: int = 3) -> pd.Series:
    """Return a boolean Series — True where a pivot high is confirmed."""
    result = pd.Series(False, index=high.index)
    for i in range(left, len(high) - right):
        window = high.iloc[i - left : i + right + 1]
        if high.iloc[i] == window.max():
            result.iloc[i] = True
    return result


def pivot_low(low: pd.Series, left: int = 3, right: int = 3) -> pd.Series:
    """Return a boolean Series — True where a pivot low is confirmed."""
    result = pd.Series(False, index=low.index)
    for i in range(left, len(low) - right):
        window = low.iloc[i - left : i + right + 1]
        if low.iloc[i] == window.min():
            result.iloc[i] = True
    return result


# ── BaseStrategy ─────────────────────────────────────────────────────────────

class BaseStrategy:
    """
    Abstract base for all strategies.

    Subclasses MUST define:
        default_params: dict[str, Any]
        param_bounds: dict[str, tuple[float, float, float]]  — keys must match default_params
        meta: StrategyMeta
        generate_signal(data: dict[str, pd.DataFrame]) -> Signal | None

    The metaclass enforces param_bounds.keys() == default_params.keys() at import time.
    """

    default_params: dict[str, Any] = {}
    param_bounds: dict[str, tuple[float, float, float]] = {}
    meta: StrategyMeta = StrategyMeta("base", "Base", "", "general")

    def __init__(
        self,
        symbol: str = "",
        timeframe: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.params = {**self.default_params}
        if params:
            self.params.update(params)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "default_params") and hasattr(cls, "param_bounds"):
            dp_keys = set(cls.default_params.keys())
            pb_keys = set(cls.param_bounds.keys())
            if dp_keys != pb_keys:
                missing = dp_keys - pb_keys
                extra = pb_keys - dp_keys
                raise ValueError(
                    f"{cls.__name__}: param_bounds mismatch. "
                    f"Missing from bounds: {missing}. Extra in bounds: {extra}"
                )

    def generate_signal(
        self, data: dict[str, pd.DataFrame]
    ) -> Signal | None:
        """
        Produce a Signal or None.  Never raises — log and return None on error.
        Implemented by each subclass.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.generate_signal() not implemented"
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"symbol={self.symbol!r} timeframe={self.timeframe!r}>"
        )
