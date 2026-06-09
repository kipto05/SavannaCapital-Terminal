"""
strategies — ICT-ML trading strategies.

4-file group layout:
  crypto.py    → MomentumReversion, DivergenceSwing
  forex.py     → BandReversion
  commodities.py  → SessionBreakout
  equities.py  → VWAPReversion, MACDImpulse, StochasticTrend
"""
from strategies.base import BaseStrategy, Signal, StrategyMeta, Side
from strategies.registry import StrategyRegistry
