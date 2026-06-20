"""strategies/ai_trading.py — AI Trading strategy.

Wraps AIAgent as a first-class BaseStrategy so it appears in the Strategy
Library, generates trades via engine loop, and shows full stats.

generate_signal() is a no-op — actual signals are produced by AIAgent
and stored as Trade rows with strategy_name='ai_trading'.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from config.settings import config
from strategies.base import BaseStrategy, Signal, StrategyMeta

log = logging.getLogger(__name__)

# ── Default params (must match param_bounds exactly) ────────────────────────
# Stored in strategy_configs, editable from Strategy Library.

default_params: dict[str, Any] = {
    "enabled": False,
    "symbols": ["XAUUSD", "BTCUSD", "EURUSD", "NVDA"],
    "timeframe": "M15",
    "cooldown_minutes": 15,
    "min_confidence": 0.60,
}

param_bounds: dict[str, tuple[Any, Any]] = {
    "enabled": (False, True),
    "symbols": ([], ["XAUUSD", "BTCUSD", "EURUSD", "NVDA", "GBPUSD", "ETHUSD"]),
    "timeframe": ("M1", "H4"),
    "cooldown_minutes": (1, 1440),
    "min_confidence": (0.0, 1.0),
}

meta = StrategyMeta(
    name="ai_trading",
    label="AI Trading",
    description="LLM-backed trade suggestions using Anthropic Claude. Produces signal entries with computed SL/TP via ATR-scaled model. All suggestions stored as pseudo-trades.",
    asset_class="multi",
    version="1.0.0",
    typical_timeframes=["M15"],
    default_symbol="XAUUSD",
)


# ── Strategy class ──────────────────────────────────────────────────────────

class AITrading(BaseStrategy):
    """AI Trading strategy adapter.

    generate_signal() always returns None — signals are produced externally
    by the AIAgent and stored as Trade rows (strategy_name='ai_trading').

    This class exists solely so the Strategy Library can:
      - Toggle AI on/off (is_active flag)
      - Display full stats (trades, win rate, Sharpe, etc.)
      - Manage config (symbols, timeframe, cooldown)

    The engine loop also calls generate_signal() for consistency, but this
    implementation is a no-op — actual signal production lives in
    ai_advisor.agent.
    """

    def generate_signal(self, data: dict[str, pd.DataFrame]) -> Signal | None:
        """No-op for AI Trading — suggestions flow through AIAgent directly.

        The engine loop still calls this as part of the unified strategy
        interface, but AI signals are produced asynchronously and stored
        as Trade rows.
        """
        log.debug(
            "AITrading: generate_signal called (no-op — signals via AIAgent)"
        )
        return None
