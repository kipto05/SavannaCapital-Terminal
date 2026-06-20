"""
strategies_2/gold_scalp.py — GoldScalp.

Fast 9/21 EMA crossover with RSI(14) confirmation, 24/7 (no session gate),
ATR-scaled tight SL/TP. Designed for XAUUSD on M1/M5.

Param summary (all editable from the Strategy Library UI):
    timeframe            : str   — "M1", "M5", ...
    ema_fast_period      : int   (default 9)
    ema_slow_period      : int   (default 21)
    rsi_period           : int   (default 14)
    rsi_long_min/max     : float (default 45 / 70)
    rsi_short_min/max    : float (default 30 / 55)
    atr_period           : int   (default 14)
    min_atr_threshold    : float (default 0.5 — gold price units)
    sl_atr_multiple      : float (default 1.2 ∈ [1.0, 1.5])
    tp_atr_multiple      : float (default 2.2 ∈ [2.0, 2.5])
    tp1_atr_multiple     : float (default 1.0 — partial exit level)
    cooldown_bars        : int   (bars to wait after a signal before re-entry)
    lot_size             : float (default 0.01)
    ml_enabled           : bool  (default False)
    ml_min_probability   : float (default 0.55)
    ml_model_name        : str   (default "gold_scalp_v1")
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr, ema, rsi
from strategies_2.ml_gate import build_hft_features, default_ml_gate

log = logging.getLogger(__name__)


_DEFAULT_TIMEFRAMES = ("M1", "M5")


class GoldScalp(BaseStrategy):
    """EMA-fast/slow cross in trend direction, RSI band filter, ATR-sized risk."""

    meta = StrategyMeta(
        name="gold_scalp",
        label="Gold Scalp",
        description=(
            "9/21 EMA crossover with RSI(14) confirmation on XAUUSD. Trades "
            "24/7. Tight ATR-scaled SL/TP. Optional ML win-probability gate."
        ),
        asset_class="commodity",
        typical_timeframes=list(_DEFAULT_TIMEFRAMES),
        default_symbol="XAUUSD",
    )

    default_params: dict[str, Any] = {
        "ema_fast_period": 9,
        "ema_slow_period": 21,
        "rsi_period": 14,
        "rsi_long_min": 45,
        "rsi_long_max": 70,
        "rsi_short_min": 30,
        "rsi_short_max": 55,
        "atr_period": 14,
        "min_atr_threshold": 0.5,
        "sl_atr_multiple": 1.2,
        "tp_atr_multiple": 2.2,
        "tp1_atr_multiple": 1.0,
        "cooldown_bars": 3,
        "lot_size": 0.01,
        "ml_enabled": False,
        "ml_min_probability": 0.55,
        "ml_model_name": "gold_scalp_v1",
    }

    # names MUST match default_params exactly (BaseStrategy guard).
    param_bounds: dict[str, tuple[float, float, float]] = {
        "ema_fast_period": (3, 30, 1),
        "ema_slow_period": (10, 80, 1),
        "rsi_period": (5, 30, 1),
        "rsi_long_min": (20, 60, 1),
        "rsi_long_max": (55, 90, 1),
        "rsi_short_min": (10, 45, 1),
        "rsi_short_max": (40, 80, 1),
        "atr_period": (5, 30, 1),
        "min_atr_threshold": (0.0, 10.0, 0.1),
        "sl_atr_multiple": (1.0, 1.5, 0.05),
        "tp_atr_multiple": (2.0, 2.5, 0.1),
        "tp1_atr_multiple": (0.5, 1.5, 0.1),
        "cooldown_bars": (0, 30, 1),
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
        # ``_last_signal_bar`` is an internal anti-spam guard used only when
        # the engine forwards a bar index; we don't depend on it being set,
        # so leave it None unless caller provided one.
        self._last_signal_bar = -10_000

    # Helpers ----------------------------------------------------------
    def _cooldown_clear(self, curr_bar_index: int) -> bool:
        return (curr_bar_index - self._last_signal_bar) >= self.params["cooldown_bars"]

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        return build_hft_features(df)

    def _ml_prob(self, df: pd.DataFrame) -> tuple[bool, float | None]:
        if not self.params["ml_enabled"]:
            return True, None
        feats = self._features(df)
        gate = default_ml_gate()
        return gate.allow(feats, self.params["ml_min_probability"])

    def _conf(self, prob: float | None) -> float:
        if prob is None:
            return 0.5
        # Map probability to [0,1] confidence with slight floor.
        return float(min(1.0, max(0.0, prob)))

    # Indicator scaffolding -------------------------------------------
    def _series(self, df: pd.DataFrame):
        p = self.params
        close = df["close"]
        fast = ema(close, p["ema_fast_period"])
        slow = ema(close, p["ema_slow_period"])
        rsi_v = rsi(close, p["rsi_period"])
        atr_v = atr(df, p["atr_period"])
        return close, fast, slow, rsi_v, atr_v

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        try:
            tf = self.timeframe
            df = data.get(tf)
            if df is None or len(df) < self.params["ema_slow_period"] + 2:
                log.debug(
                    "%s: insufficient bars=%d",
                    self.meta.name,
                    len(df) if df is not None else 0,
                )
                return None

            p = self.params
            close, fast, slow, rsi_v, atr_v = self._series(df)
            if pd.isna(fast.iloc[-1]) or pd.isna(slow.iloc[-1]):
                return None
            if pd.isna(rsi_v.iloc[-1]) or pd.isna(atr_v.iloc[-1]):
                return None

            # Hard ATR floor — HFT on quiet markets just churns the account.
            if float(atr_v.iloc[-1]) < float(p["min_atr_threshold"]):
                return None

            # ML gate (cheap no-op when unbound or ml_enabled=False).
            passes, prob = self._ml_prob(df)
            if not passes:
                log.debug(
                    "%s: blocked by ML gate (prob=%s)", self.meta.name, prob
                )
                return None

            curr_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            fast_now, fast_prev = float(fast.iloc[-1]), float(fast.iloc[-2])
            slow_now, slow_prev = float(slow.iloc[-1]), float(slow.iloc[-2])
            curr_rsi = float(rsi_v.iloc[-1])
            curr_atr = float(atr_v.iloc[-1])

            cross_up = fast_prev <= slow_prev and fast_now > slow_now
            cross_dn = fast_prev >= slow_prev and fast_now < slow_now

            side_v: Side | None = None
            if cross_up and p["rsi_long_min"] < curr_rsi < p["rsi_long_max"]:
                side_v = Side.BUY
            elif cross_dn and p["rsi_short_min"] < curr_rsi < p["rsi_short_max"]:
                side_v = Side.SELL

            if side_v is None:
                return None

            sl_dist = curr_atr * p["sl_atr_multiple"]
            tp_dist = curr_atr * p["tp_atr_multiple"]
            tp1_dist = curr_atr * p["tp1_atr_multiple"]
            if side_v is Side.BUY:
                entry = curr_close
                sl = entry - sl_dist
                tp = entry + tp_dist
                tp1 = entry + tp1_dist
            else:
                entry = curr_close
                sl = entry + sl_dist
                tp = entry - tp_dist
                tp1 = entry - tp1_dist

            # Cooldown bookkeeping (only meaningful if caller provides a
            # monotonic bar index via df.index; we use the integer position
            # so it's session-stable even on a DatetimeIndex).
            self._last_signal_bar = len(close) - 1

            regime = "trending" if (fast_now - slow_now) > 0 else "ranging"
            metadata: dict[str, Any] = {
                "ema_fast": fast_now,
                "ema_slow": slow_now,
                "rsi": curr_rsi,
                "atr": curr_atr,
                "strategy_family": "ema_cross",
                "ml_probability": prob,
                "ml_model_version": (
                    default_ml_gate().model_version if p["ml_enabled"] else None
                ),
            }
            # Track whichever mode produced the entry so the engine can audit.
            return Signal(
                side=side_v,
                entry=entry,
                sl=sl,
                tp=tp,
                tp1=tp1,
                tp2=tp,
                lot_size=p["lot_size"],
                tag=f"{self.meta.name}.{'long' if side_v is Side.BUY else 'short'}",
                regime=regime,
                confidence=self._conf(prob),
                metadata=metadata,
            )
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
