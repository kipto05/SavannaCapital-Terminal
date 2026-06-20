"""
strategies_2/volatility_breakout.py — VolatilityBreakout.

Bollinger Band squeeze → breakout continuation. Designed primarily for
XAUUSD and BTCUSD on M5.

Logic
-----
1. Compute BB(N, k) and BB width as a fraction of the middle band.
2. If BB width was below ``squeeze_threshold_pct`` for at least
   ``squeeze_min_bars`` of the last ``squeeze_lookback`` bars, the market
   is "compressed" and primed for expansion.
3. On the next bar, enter in the direction of the close if it pierces the
   upper (long) / lower (short) band. The previous close must still be
   inside the bands so this is a fresh break, not a continuation chase.
4. Optional volume confirmation: tick_volume > volume_spike_multiple x
   volume_ma. Volume data is missing on some synthetic feeds — the gate
   degrades gracefully and ignores the check when no volume is present.

Exit guidance
-------------
The exit manager is responsible for trailing the stop once price reaches
``profit_rr_to_trail`` RR in profit; at that point the SL should be moved
behind price by ``trail_atr_multiple`` ATR units. The strategy just
publishes these numbers in ``Signal.metadata`` so the executor doesn't
need to know about the strategy internals.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr, bollinger
from strategies_2.ml_gate import build_hft_features, default_ml_gate

log = logging.getLogger(__name__)


_DEFAULT_TIMEFRAMES = ("M5",)


class VolatilityBreakout(BaseStrategy):
    """BB squeeze release with volume spike confirmation and trail metadata."""

    meta = StrategyMeta(
        name="volatility_breakout",
        label="Volatility Breakout",
        description=(
            "Bollinger Band squeeze release with optional volume spike. "
            "Designed for XAUUSD and BTCUSD on M5."
        ),
        asset_class="multi",
        typical_timeframes=list(_DEFAULT_TIMEFRAMES),
        default_symbol="XAUUSD",
    )

    default_params: dict[str, Any] = {
        "bb_period": 20,
        "bb_std_dev": 2.0,
        "squeeze_threshold_pct": 0.002,   # 0.2 % of mid-band
        "squeeze_lookback": 20,
        "squeeze_min_bars": 5,
        "volume_ma_period": 20,
        "volume_spike_multiple": 1.5,
        "atr_period": 14,
        "sl_atr_multiple": 1.5,
        "tp_atr_multiple": 3.0,
        "trail_atr_multiple": 0.5,
        "profit_rr_to_trail": 1.0,
        "require_volume_confirmation": True,
        "lot_size": 0.01,
        "ml_enabled": False,
        "ml_min_probability": 0.55,
        "ml_model_name": "volatility_breakout_v1",
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "bb_period": (10, 60, 1),
        "bb_std_dev": (1.0, 3.5, 0.1),
        "squeeze_threshold_pct": (0.0005, 0.02, 0.0005),
        "squeeze_lookback": (5, 100, 1),
        "squeeze_min_bars": (1, 50, 1),
        "volume_ma_period": (5, 100, 1),
        "volume_spike_multiple": (0.5, 5.0, 0.1),
        "atr_period": (5, 30, 1),
        "sl_atr_multiple": (0.5, 3.0, 0.1),
        "tp_atr_multiple": (1.0, 6.0, 0.1),
        "trail_atr_multiple": (0.1, 2.0, 0.05),
        "profit_rr_to_trail": (0.5, 3.0, 0.1),
        "require_volume_confirmation": (False, True, 1),
        "lot_size": (0.01, 1.0, 0.01),
        "ml_enabled": (False, True, 1),
        "ml_min_probability": (0.0, 1.0, 0.01),
        "ml_model_name": ("a", "z"*32, 1),
    }

    def __init__(
        self,
        symbol: str = "",
        timeframe: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            symbol=symbol or self.meta.default_symbol,
            timeframe=timeframe or "M5",
            params=params,
        )

    # Helpers ----------------------------------------------------------
    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        return build_hft_features(df)

    def _volume_col(self, df: pd.DataFrame) -> str | None:
        if "tick_volume" in df.columns:
            return "tick_volume"
        if "volume" in df.columns:
            return "volume"
        return None

    def _bb_width_pct(self, df: pd.DataFrame, period: int, std_dev: float) -> pd.Series:
        upper, mid, lower = bollinger(df["close"], period=period, std_dev=std_dev)
        # (upper - lower) / mid in absolute units; for XAUUSD on M5 a width
        # of 0.002 means the bands span 0.2 % of mid-price.
        return (upper - lower) / mid.replace(0, np.nan)

    def _squeeze_recent(self, width: pd.Series, lookback: int, min_bars: int, thresh: float) -> bool:
        if len(width) < lookback + 1:
            return False
        window = width.iloc[-lookback - 1:-1]   # bars strictly before current
        valid = window.dropna()
        if len(valid) < min_bars:
            return False
        # Use rolling count of bars within the threshold.
        return int((valid < thresh).sum()) >= int(min_bars)

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < self.params["bb_period"] + self.params["squeeze_lookback"] + 2:
                log.debug(
                    "%s: insufficient bars=%d",
                    self.meta.name,
                    len(df) if df is not None else 0,
                )
                return None

            p = self.params
            close = df["close"]
            upper, mid, lower = bollinger(close, period=p["bb_period"], std_dev=p["bb_std_dev"])
            width = self._bb_width_pct(df, p["bb_period"], p["bb_std_dev"])
            atr_v = atr(df, p["atr_period"])
            if (
                pd.isna(upper.iloc[-1])
                or pd.isna(lower.iloc[-1])
                or pd.isna(width.iloc[-1])
                or pd.isna(atr_v.iloc[-1])
            ):
                return None

            squeezed = self._squeeze_recent(
                width,
                lookback=p["squeeze_lookback"],
                min_bars=p["squeeze_min_bars"],
                thresh=p["squeeze_threshold_pct"],
            )
            if not squeezed:
                return None

            curr_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            curr_upper = float(upper.iloc[-1])
            prev_upper = float(upper.iloc[-2])
            curr_lower = float(lower.iloc[-1])
            prev_lower = float(lower.iloc[-2])
            curr_atr = float(atr_v.iloc[-1])

            # Fresh break: previous close was inside, this close is outside.
            long_break = prev_close <= prev_upper and curr_close > curr_upper
            short_break = prev_close >= prev_lower and curr_close < curr_lower
            if not (long_break or short_break):
                return None

            # Optional volume confirmation.
            if p["require_volume_confirmation"]:
                vol_col = self._volume_col(df)
                if vol_col is not None:
                    vol = df[vol_col].astype(float)
                    vol_ma = vol.rolling(p["volume_ma_period"], min_periods=1).mean()
                    if pd.notna(vol_ma.iloc[-1]) and float(vol.iloc[-1]) < float(vol_ma.iloc[-1]) * p["volume_spike_multiple"]:
                        log.debug("%s: volume spike missing", self.meta.name)
                        return None
                else:
                    log.debug("%s: require_volume_confirmation=True but no volume column — skipping trade", self.meta.name)
                    return None

            # ML gate (no-op when unbound or ml_enabled=False).
            if p["ml_enabled"]:
                feats = self._features(df)
                gate = default_ml_gate()
                passes, prob = gate.allow(feats, p["ml_min_probability"])
                if not passes:
                    log.debug("%s: ML gate block prob=%s", self.meta.name, prob)
                    return None
            else:
                prob = None
                passes = True

            sl_dist = curr_atr * p["sl_atr_multiple"]
            tp_dist = curr_atr * p["tp_atr_multiple"]
            side_v = Side.BUY if long_break else Side.SELL
            entry = curr_close
            if side_v is Side.BUY:
                sl = entry - sl_dist
                tp = entry + tp_dist
            else:
                sl = entry + sl_dist
                tp = entry - tp_dist

            metadata: dict[str, Any] = {
                "bb_width_pct": float(width.iloc[-1]),
                "atr": curr_atr,
                "trail_atr_multiple": p["trail_atr_multiple"],
                "trail_after_rr": p["profit_rr_to_trail"],
                "strategy_family": "bb_squeeze_breakout",
                "ml_probability": prob,
                "ml_model_version": (
                    default_ml_gate().model_version if p["ml_enabled"] else None
                ),
            }
            return Signal(
                side=side_v,
                entry=entry,
                sl=sl,
                tp=tp,
                tp1=tp,
                tp2=tp,
                lot_size=p["lot_size"],
                tag=f"{self.meta.name}.{'long' if side_v is Side.BUY else 'short'}",
                regime="volatile",
                confidence=float(prob) if prob is not None else 0.5,
                metadata=metadata,
            )
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
