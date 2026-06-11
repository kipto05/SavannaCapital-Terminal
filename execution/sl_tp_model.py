""" execution/sl_tp_model.py — DynamicSLTPModel.

Sole source of SL/TP values for all strategies. Never compute SL/TP inside
a strategy or order_manager directly. Call sltp.compute(df, side, entry).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import config

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SLTPResult:
    """Immutable SL/TP bundle returned by DynamicSLTPModel.compute()."""
    sl: float
    tp1: float
    tp2: float
    tp: float  # primary TP (== tp2) — present so strategies can use result.tp
    regime: str
    atr_value: float
    rr1: float
    rr2: float


class DynamicSLTPModel:
    """ATR-scaled, regime-aware SL/TP model.

    Steps:
    1. Compute ATR → classify tf regime (trending / ranging / volatile)
    2. Pick SL multiplier per regime from config.sltp
    3. Add TP1 / TP2 from risk-reward multipliers
    4. Enforce minimum RR gate (config.sltp.min_rr)
    5. Return None if the trade would breach the RR gate (strategy skips it)
    """

    def __init__(self) -> None:
        self.cfg = config.sltp

    # ── Public API ────────────────────────────────────────────────────────────

    def compute(
        self,
        df: pd.DataFrame,
        side: str,
        entry: float,
        atr_override: float | None = None,
    ) -> SLTPResult | None:
        """Compute SL, TP1, TP2 for a given entry price.

        Parameters
        ----------
        df : pd.DataFrame OHLCV data covering the signal timeframe.
        side : str "BUY" or "SELL".
        entry : float Intended entry price.
        atr_override : float | None Pre-computed ATR (from caller if already
            available). Computed from df when None.

        Returns
        -------
        SLTPResult or None
        None if the trade does not pass the RR gate.
        """
        try:
            if len(df) < self.cfg.atr_period + 1:
                log.debug("SLTPModel: insufficient bars for ATR %d", self.cfg.atr_period)
                return None

            atr_val = atr_override if atr_override is not None else self._atr(df)
            if atr_val <= 0:
                log.debug(
                    "SLTPModel: ATR=%.5f — non-positive, blocking trade", atr_val
                )
                return None

            regime = self._detect_regime(df, atr_val)
            sl_mult = self._sl_multiplier(regime)
            tp1_rr, tp2_rr = self._tp_rr(regime)

            sl_dist = atr_val * sl_mult

            if side.upper() == "BUY":
                sl = entry - sl_dist
                tp1 = entry + sl_dist * tp1_rr
                tp2 = entry + sl_dist * tp2_rr
            else:
                sl = entry + sl_dist
                tp1 = entry - sl_dist * tp1_rr
                tp2 = entry - sl_dist * tp2_rr

            rr1 = tp1_rr
            rr2 = tp2_rr
            tp = tp2  # primary TP == tp2 (strategies reference result.tp)

            # RR gate
            if rr2 < self.cfg.min_rr:
                log.debug(
                    "SLTPModel: blocked by RR gate — rr2=%.2f < min=%.2f",
                    rr2,
                    self.cfg.min_rr,
                )
                return None

            return SLTPResult(
                sl=round(sl, 6),
                tp1=round(tp1, 6),
                tp2=round(tp2, 6),
                tp=round(tp, 6),
                regime=regime,
                atr_value=round(atr_val, 6),
                rr1=round(rr1, 2),
                rr2=round(rr2, 2),
            )
        except Exception as exc:
            log.exception("SLTPModel.compute failed: %s", exc)
            return None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _atr(self, df: pd.DataFrame) -> float:
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        period = self.cfg.atr_period
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                abs(highs[1:] - closes[:-1]),
                abs(lows[1:] - closes[:-1]),
            ),
        )
        atr_val = pd.Series(tr).rolling(period).mean().iloc[-1]
        return float(atr_val) if not np.isnan(atr_val) else 0.0

    def _atr_pct(self, df: pd.DataFrame, atr: float) -> float:
        """ATR as a fraction of current close price."""
        if len(df) == 0 or df["close"].iloc[-1] == 0:
            return 0.0
        return atr / float(df["close"].iloc[-1])

    def _detect_regime(self, df: pd.DataFrame, atr: float) -> str:
        atr_pct = self._atr_pct(df, atr)
        if atr_pct < self.cfg.atr_pct_ranging_thresh:
            return "ranging"
        if atr_pct > self.cfg.atr_pct_volatile_thresh:
            return "volatile"
        return "trending"

    def _sl_multiplier(self, regime: str) -> float:
        if regime == "ranging":
            return self.cfg.sl_atr_mult_ranging
        if regime == "volatile":
            return self.cfg.sl_atr_mult_volatile
        return self.cfg.sl_atr_mult_trending

    def _tp_rr(self, regime: str) -> tuple[float, float]:
        if regime == "ranging":
            return self.cfg.tp1_rr_ranging, self.cfg.tp2_rr_ranging
        if regime == "volatile":
            return self.cfg.tp1_rr_volatile, self.cfg.tp2_rr_volatile
        return self.cfg.tp1_rr_trending, self.cfg.tp2_rr_trending
