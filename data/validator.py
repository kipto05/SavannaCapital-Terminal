"""
data/validator.py — OHLCV data integrity checks.
Rejects bad data before it reaches strategies, backtester, or ML pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


REQUIRED_COLUMNS = {"open", "high", "low", "close"}
OPTIONAL_COLUMNS = {"volume", "tick_volume", "spread"}


@dataclass
class ValidationReport:
    is_valid: bool
    issues: list[str] = field(default_factory=list)
    n_bars: int = 0
    symbol: str = ""
    timeframe: str = ""


def validate(
    df: pd.DataFrame,
    symbol: str = "",
    timeframe: str = "",
) -> ValidationReport:
    """
    Run all integrity checks on an OHLCV DataFrame.
    Returns ValidationReport — check is_valid before using the data.
    """
    issues: list[str] = []

    if df is None or df.empty:
        issues.append("DataFrame is None or empty")
        return ValidationReport(is_valid=False, issues=issues, symbol=symbol, timeframe=timeframe)

    # --- Column check ---
    cols = set(df.columns.str.lower())
    missing = REQUIRED_COLUMNS - cols
    if missing:
        issues.append(f"Missing required columns: {missing}")

    # --- Index check ---
    if not isinstance(df.index, pd.DatetimeIndex):
        issues.append("Index is not DatetimeIndex")
    else:
        if df.index.tz is None:
            issues.append("Index is timezone-naive — all data must be UTC")

    # --- OHLC logic ---
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            if (df[col] < 0).any():
                issues.append(f"{col} has negative values")
            if df[col].isna().any():
                issues.append(f"{col} has NaN values")

    if all(c in df.columns for c in ["high", "low", "open", "close"]):
        bad_high = (df["high"] < df[["open", "close"]].max(axis=1)).any()
        bad_low = (df["low"] > df[["open", "close"]].min(axis=1)).any()
        if bad_high:
            issues.append("high < max(open, close) on some bars")
        if bad_low:
            issues.append("low < min(open, close) on some bars")

    # --- Duplicate timestamps ---
    if isinstance(df.index, pd.DatetimeIndex):
        dupes = df.index.duplicated().sum()
        n_bars = len(df)

    report = ValidationReport(
        is_valid=len(issues) == 0,
        issues=issues,
        n_bars=len(df),
        symbol=symbol,
        timeframe=timeframe,
    )

    if report.is_valid:
        log.info("Data validated: symbol=%s timeframe=%s bars=%d", symbol, timeframe, n_bars)
    else:
        log.warning("Data validation FAILED: symbol=%s timeframe=%s issues=%s", symbol, timeframe, issues)

    return report
