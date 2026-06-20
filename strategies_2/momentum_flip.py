"""
strategies_2/momentum_flip.py — MomentumFlip.

Fast RSI-extreme reversal strategy designed for high-frequency scalp on
BTCUSD M1/M5.

Logic
-----
1. Compute RSI(rsi_period, default 5) on close.
2. Detect an "extreme flip":
      LONG  : prev_k <= rsi_oversold_flip and curr_k > rsi_oversold_flip
      SHORT : prev_k >= rsi_overbought_flip and curr_k < rsi_overbought_flip
3. Require momentum confirmation: the close-pct-change over
   ``momentum_period`` bars must exceed ``momentum_threshold_pct`` in the
   direction of the trade. This filters out micro-oscillations that would
   otherwise over-trigger.
4. Risk: SL = sl_atr_multiple x ATR, TP = rr_ratio x SL distance.
5. ``max_hold_bars`` is published in metadata so the exit manager can
   force-close the position if it stalls.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr, rsi
from strategies_2.ml_gate import build_hft_features, default_ml_gate

log = logging.getLogger(__name__)


_DEFAULT_TIMEFRAMES = ("M1", "M5")


class MomentumFlip(BaseStrategy):
    """RSI extreme flips with momentum confirmation for fast BTCUSD scalps."""

    meta = StrategyMeta(
        name="momentum_flip",
        label="Momentum Flip",
        description=(
            "RSI(5) extreme flips (30/70) with momentum confirmation. "
            "Fixed 1:2 RR with optional 2-bar max hold."
        ),
        asset_class="crypto",
        typical_timeframes=list(_DEFAULT_TIMEFRAMES),
        default_symbol="BTCUSD",
    )

    default_params: dict[str, Any] = {
        "rsi_period": 5,
        "rsi_oversold_flip": 30,
        "rsi_overbought_flip": 70,
        "momentum_period": 3,
        "momentum_threshold_pct": 0.001,    # 0.1 % over the lookback
        "atr_period": 14,
        "sl_atr_multiple": 1.0,
        "rr_ratio": 2.0,
        "max_hold_bars": 2,
        "lot_size": 0.01,
        "ml_enabled": False,
        "ml_min_probability": 0.55,
        "ml_model_name": "momentum_flip_v1",
    }

    param_bounds: dict[str, tuple[float, float, float]] = {
        "rsi_period": (3, 14, 1),
        "rsi_oversold_flip": (10, 45, 1),
        "rsi_overbought_flip": (55, 90, 1),
        "momentum_period": (1, 20, 1),
        "momentum_threshold_pct": (0.0, 0.05, 0.0005),
        "atr_period": (5, 30, 1),
        "sl_atr_multiple": (0.5, 3.0, 0.05),
        "rr_ratio": (1.0, 4.0, 0.1),
        "max_hold_bars": (1, 10, 1),
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
            timeframe=timeframe or "M1",
            params=params,
        )

    # Helpers ----------------------------------------------------------
    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        return build_hft_features(df)

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < self.params["rsi_period"] + self.params["momentum_period"] + 5:
                log.debug(
                    "%s: insufficient bars=%d",
                    self.meta.name,
                    len(df) if df is not None else 0,
                )
                return None

            p = self.params
            close = df["close"]
            rsi_v = rsi(close, p["rsi_period"])
            atr_v = atr(df, p["atr_period"])
            if len(rsi_v) < 2 or pd.isna(rsi_v.iloc[-1]) or pd.isna(rsi_v.iloc[-2]):
                return None
            if pd.isna(atr_v.iloc[-1]):
                return None

            curr_k = float(rsi_v.iloc[-1])
            prev_k = float(rsi_v.iloc[-2])

            cross_up = prev_k <= p["rsi_oversold_flip"] and curr_k > p["rsi_oversold_flip"]
            cross_dn = prev_k >= p["rsi_overbought_flip"] and curr_k < p["rsi_overbought_flip"]
            if not (cross_up or cross_dn):
                return None

            # Momentum confirmation
            momentum = close.pct_change(periods=p["momentum_period"]).iloc[-1]
            if pd.isna(momentum):
                return None
            momentum = float(momentum)
            if abs(momentum) < p["momentum_threshold_pct"]:
                log.debug("%s: momentum %.5f < threshold %.5f", self.meta.name,
                          momentum, p["momentum_threshold_pct"])
                return None

            if cross_up and momentum <= 0:
                return None
            if cross_dn and momentum >= 0:
                return None

            curr_atr = float(atr_v.iloc[-1])
            sl_dist = curr_atr * p["sl_atr_multiple"]
            tp_dist = sl_dist * p["rr_ratio"]

            entry = float(close.iloc[-1])
            side_v: Side
            if cross_up:
                side_v = Side.BUY
                sl = entry - sl_dist
                tp = entry + tp_dist
            else:
                side_v = Side.SELL
                sl = entry + sl_dist
                tp = entry - tp_dist

            # ML gate (no-op when disabled or unbound).
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

            rr = p["rr_ratio"]
            metadata: dict[str, Any] = {
                "rsi": curr_k,
                "rsi_prev": prev_k,
                "momentum": momentum,
                "atr": curr_atr,
                "rr_ratio": rr,
                "max_hold_bars": p["max_hold_bars"],
                "exit_policy": "fixed_rr_or_max_hold",
                "strategy_family": "rsi_extreme_flip",
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
                regime="ranging",
                confidence=float(prob) if prob is not None else 0.5,
                metadata=metadata,
            )
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
