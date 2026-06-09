"""
execution/position_sizer.py — PositionSizer.

Sole source of lot sizes. Strategies must never compute lot_size directly.
Always route through PositionSizer.compute().
"""
from __future__ import annotations

import logging
from typing import Optional

from config.settings import config

log = logging.getLogger(__name__)


class PositionSizer:
    """
    Fixed-fractional position sizing from account equity.

    Lot size = risk_per_trade × account_equity / sl_distance_in_points

    Returns None if the computed lot size breaches min/max constraints or
    if risk_per_trade is zero / not configured.
    """

    def __init__(self) -> None:
        self.risk_cfg = config.risk

    def compute(
        self,
        account_equity: float,
        entry: float,
        sl: float,
        symbol: str,
        point_size: float | None = None,
        lot_step: float | None = None,
    ) -> float | None:
        """
        Return lot size in standard broker units (0.01 lots = 1 micro-lot).

        Parameters
        ----------
        account_equity : float
            Current account equity (from MT5 or balance snapshot).
        entry : float
            Intended entry price.
        sl : float
            Stop-loss price from DynamicSLTPModel.
        symbol : str
            Ticker symbol (used for point_size lookup).
        point_size : float | None
            Per-symbol point size. Falls back to config.risk.point_sizes.
        lot_step : float | None
            Broker lot granularity. Falls back to config.risk.lot_step.
        """
        try:
            risk_amount = account_equity * self.risk_cfg.risk_per_trade
            if risk_amount <= 0:
                log.warning("PositionSizer: risk_amount=%.2f ≤ 0", risk_amount)
                return None

            pt = point_size or self.risk_cfg.point_sizes.get(symbol.upper(), 0.00001)
            step = lot_step or self.risk_cfg.lot_step

            sl_points = abs(entry - sl) / pt
            if sl_points <= 0:
                log.warning("PositionSizer: sl_points=%.2f — zero distance", sl_points)
                return None

            # Standard lot = 100,000 units; 1 point = 0.00001 price units
            lot_size_raw = risk_amount / (sl_points * 1.0)

            # Align to broker lot step
            lot_size = round(lot_size_raw / step) * step
            lot_size = max(lot_size, self.risk_cfg.min_lot_size)
            lot_size = min(lot_size, self.risk_cfg.max_lot_size)

            if lot_size <= 0:
                log.warning("PositionSizer: computed lot_size=%.5f — non-positive", lot_size)
                return None

            log.debug(
                "PositionSizer: equity=%.2f symbol=%s sl_pts=%.1f → lots=%.2f",
                account_equity,
                symbol,
                sl_points,
                lot_size,
            )
            return round(lot_size, 2)

        except Exception as exc:
            log.exception("PositionSizer.compute failed: %s", exc)
            return None
