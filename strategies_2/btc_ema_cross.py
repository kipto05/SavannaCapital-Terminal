"""
strategies_2/btc_ema_cross.py — BTCEmaCross.

Crypto-flavoured EMA crossover tuned for BTCUSD on M5. Same EMA-cross
skeleton as GoldScalp, with slightly looser RSI bands and a broader ATR
floor suited to BTC's volatility profile. Defaults to the ML gate being
ENABLED so the model built off ml/feature_engineer.py output can be
applied without extra dashboard configuration.

Why a separate class from GoldScalp?
-----------------------------------
  * Different default paper (BTC's typical pip decimalisation, larger ATR
    in absolute units).
  * Different default RSI bands — BTC trends aggressively, so we don't
    want to refuse entries when RSI is already at 65.
  * BTC has by far the most trainer-friendly data flow; this is the
    strategy we expect ML models to be most accurate on.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from strategies.base import BaseStrategy, Signal, Side, StrategyMeta, atr, ema, rsi
from strategies_2.ml_gate import build_hft_features, default_ml_gate

log = logging.getLogger(__name__)


_DEFAULT_TIMEFRAMES = ("M5", "M15", "M1")


class BTCEmaCross(BaseStrategy):
    """9/21 EMA cross with RSI confirmation, ATR risk, ML-gated by default."""

    meta = StrategyMeta(
        name="btc_ema_cross",
        label="BTC EMA Cross",
        description=(
            "9/21 EMA crossover on BTCUSD/M5 with RSI filter and default "
            "ML win-probability gate. ATR-scaled SL/TP."
        ),
        asset_class="crypto",
        typical_timeframes=list(_DEFAULT_TIMEFRAMES),
        default_symbol="BTCUSD",
    )

    default_params: dict[str, Any] = {
        "ema_fast_period": 9,
        "ema_slow_period": 21,
        "rsi_period": 14,
        "rsi_long_min": 40,
        "rsi_long_max": 80,
        "rsi_short_min": 20,
        "rsi_short_max": 60,
        "atr_period": 14,
        "min_atr_threshold": 30.0,         # BTC price units (~ $30 on M5)
        "sl_atr_multiple": 1.5,
        "tp_atr_multiple": 3.0,
        "tp1_atr_multiple": 1.5,
        "cooldown_bars": 5,
        "lot_size": 0.01,
        "ml_enabled": True,                # ML on by default for BTC
        "ml_min_probability": 0.55,
        "ml_model_name": "btc_ema_cross_v1",
    }

    # names MUST match default_params exactly (BaseStrategy guard).
    param_bounds: dict[str, tuple[float, float, float]] = {
        "ema_fast_period": (3, 50, 1),
        "ema_slow_period": (10, 100, 1),
        "rsi_period": (5, 30, 1),
        "rsi_long_min": (20, 60, 1),
        "rsi_long_max": (55, 90, 1),
        "rsi_short_min": (10, 45, 1),
        "rsi_short_max": (40, 80, 1),
        "atr_period": (5, 30, 1),
        "min_atr_threshold": (0.0, 500.0, 1.0),
        "sl_atr_multiple": (0.5, 3.0, 0.05),
        "tp_atr_multiple": (1.0, 6.0, 0.1),
        "tp1_atr_multiple": (0.5, 3.0, 0.1),
        "cooldown_bars": (0, 50, 1),
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
        self._last_signal_bar = -10_000

    # Helpers ----------------------------------------------------------
    def _cooldown_clear(self, curr_bar_index: int) -> bool:
        return (curr_bar_index - self._last_signal_bar) >= self.params["cooldown_bars"]

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        return build_hft_features(df)

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
            close = df["close"]
            fast = ema(close, p["ema_fast_period"])
            slow = ema(close, p["ema_slow_period"])
            rsi_v = rsi(close, p["rsi_period"])
            atr_v = atr(df, p["atr_period"])
            if pd.isna(fast.iloc[-1]) or pd.isna(slow.iloc[-1]):
                return None
            if pd.isna(rsi_v.iloc[-1]) or pd.isna(atr_v.iloc[-1]):
                return None

            if float(atr_v.iloc[-1]) < float(p["min_atr_threshold"]):
                return None

            # Cooldown
            curr_bar = len(close) - 1
            if not self._cooldown_clear(curr_bar):
                return None

            # ML gate (default ON — see default_params)
            if p["ml_enabled"]:
                feats = self._features(df)
                gate = default_ml_gate()
                passes, prob = gate.allow(feats, p["ml_min_probability"])
                if not passes:
                    log.debug(
                        "%s: blocked by ML gate (prob=%s)",
                        self.meta.name,
                        prob,
                    )
                    return None
            else:
                prob = None

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

            self._last_signal_bar = curr_bar

            regime = "trending" if (fast_now - slow_now) > 0 else "ranging"
            metadata: dict[str, Any] = {
                "ema_fast": fast_now,
                "ema_slow": slow_now,
                "rsi": curr_rsi,
                "atr": curr_atr,
                "strategy_family": "btc_ema_cross",
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
                tp1=tp1,
                tp2=tp,
                lot_size=p["lot_size"],
                tag=f"{self.meta.name}.{'long' if side_v is Side.BUY else 'short'}",
                regime=regime,
                confidence=float(prob) if prob is not None else 0.5,
                metadata=metadata,
            )
        except Exception as exc:
            log.exception("%s: generate_signal error: %s", self.meta.name, exc)
            return None
