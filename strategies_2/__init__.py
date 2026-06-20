"""
strategies_2 â€” HFT-flavored strategies that build on top of the existing
strategies package (BaseStrategy, Signal, StrategyMeta, Side, indicators).

Layout:
    ml_gate.py             â†’ MLGate wrapper around ml.Predictor
    gold_scalp.py          â†’ GoldScalp        (XAUUSD M1/M5 EMA-cross/RSI)
    volatility_breakout.py â†’ VolatilityBreakout (XAUUSD/BTCUSD M5 BB squeeze)
    momentum_flip.py       â†’ MomentumFlip     (BTCUSD M1/M5 RSI extreme flip)
    btc_ema_cross.py       â†’ BTCEmaCross      (BTCUSD M5 EMA cross, ML-gated)

All four strategies:
  * inherit strategies.base.BaseStrategy so the registry can discover them
  * default_symbol is only a default; symbol + timeframe are overridable at
    instantiation, which the Strategy Library UI does on each user edit
  * every numeric threshold lives in default_params with param_bounds so the
    dashboard's Strategy Library can render a slider/input for it
  * defer the final GATE to MLGate.allow(...) when params["ml_enabled"] is True
    and a predictor is bound; otherwise the signal flows through unfiltered
"""
from __future__ import annotations

from strategies.base import BaseStrategy, Side, Signal, StrategyMeta
from strategies.registry import StrategyRecord, StrategyRegistry

from strategies_2.btc_ema_cross import BTCEmaCross
from strategies_2.gold_scalp import GoldScalp
from strategies_2.ml_gate import (
    FEATURE_NAMES,
    MLGate,
    MLPredictorProtocol,
    NullPredictor,
    build_hft_features,
    default_ml_gate,
)
from strategies_2.momentum_flip import MomentumFlip
from strategies_2.volatility_breakout import VolatilityBreakout

__all__ = [
    "BaseStrategy",
    "Signal",
    "Side",
    "StrategyMeta",
    "StrategyRecord",
    "StrategyRegistry",
    "FEATURE_NAMES",
    "MLGate",
    "MLPredictorProtocol",
    "NullPredictor",
    "build_hft_features",
    "default_ml_gate",
    "GoldScalp",
    "VolatilityBreakout",
    "MomentumFlip",
    "BTCEmaCross",
]
