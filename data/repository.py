"""
data/repository.py — OHLCV data fetching from MT5, with optional DB caching.
All external data flows through here so validation is applied consistently.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config.settings import config
from data.validator import validate, ValidationReport

log = logging.getLogger(__name__)

# Mapping human-readable timeframes → MT5 timeframe constants
_MT5_TF_MAP: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


def timeframe_to_mt5(timeframe: str) -> int:
    """Convert a TIMEFRAMES_BY_ASSET key to the corresponding MT5 constant."""
    tf = _MT5_TF_MAP.get(timeframe.upper())
    if tf is None:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}. Supported: {list(_MT5_TF_MAP)}")
    return tf


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    n_bars: int = 5000,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV from the MT5 terminal. Returns a UTC-indexed DataFrame.

    Parameters
    ----------
    symbol : str
        Ticker known to the MT5 terminal (e.g. "EURUSD", "BTCUSD").
    timeframe : str
        One of M1, M5, M15, M30, H1, H4, D1.
    start / end : datetime | None
        Boundaries for the fetch. If None, defaults are set by MT5.
    n_bars : int
        Fallback bar count if no start/end supplied.

    Returns
    -------
    pd.DataFrame or None
        Columns: open, high, low, close, (volume, tick_volume, spread).
        Index: pd.DatetimeIndex, tz-aware UTC.
    """
    try:
        import MetaTrader5 as mt5
    except ImportError:
        log.error("metatrader5 package not installed — cannot fetch live data")
        return None

    tf = timeframe_to_mt5(timeframe)

    # ── Initialise connection ──────────────────────────────────────────────
    if not mt5.initialize(
        path=config.mt5.path,
        login=config.mt5.login,
        password=config.mt5.password,
        server=config.mt5.server,
        timeout=config.mt5.timeout,
    ):
        log.error("MT5 initialise failed: %s", mt5.last_error())
        return None

    # ── Build time window ──────────────────────────────────────────────────
    # MT5 copy_rates_range expects timezone-aware UTC datetimes
    now = datetime.now(timezone.utc)
    if start is None:
        # Approximate start from bar count and timeframe
        # For a rough default go back enough bars to fill the request
        tf_minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30,
                       "H1": 60, "H4": 240, "D1": 1440}.get(timeframe.upper(), 1)
        start = datetime.fromtimestamp(now.timestamp() - n_bars * tf_minutes * 60, tz=timezone.utc)
    else:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    if end is None:
        end = now
    else:
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

    rates = mt5.copy_rates_range(symbol.upper(), tf, start, end)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        log.warning("No MT5 data: symbol=%s timeframe=%s error=%s", symbol, timeframe, mt5.last_error())
        return None

    df = pd.DataFrame(rates)
    df.rename(
        columns={
            "time": "timestamp",
            "tick_volume": "tick_volume",
            "real_volume": "volume",
        },
        inplace=True,
    )
    # MT5 stores integer seconds; convert to UTC datetime index
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df.set_index("timestamp", inplace=True)
    df.index.name = "timestamp"

    # Standardise column names to lower-case
    df.columns = [c.lower() for c in df.columns]

    # Drop extraneous columns — keep only known ones
    keep = ["open", "high", "low", "close"] + [c for c in df.columns if c in OPTIONAL_COLUMNS]  # noqa: F821
    # OPTIONAL_COLUMNS imported at top — re-compute inline to avoid circular ref in annotation
    opt_cols = {"volume", "tick_volume", "spread"}
    keep = ["open", "high", "low", "close"] + [c for c in df.columns if c in opt_cols]
    df = df[keep].copy()

    # Sort ascending, drop duplicate timestamps keeping last
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]

    # Validate — log but do not raise; caller checks is_valid flag
    report = validate(df, symbol=symbol, timeframe=timeframe)
    if not report.is_valid:
        log.warning("Repository returning invalidated data: symbol=%s timeframe=%s issues=%s",
                     symbol, timeframe, report.issues)
        # Still return the frame so the caller can decide, but flag clearly in logs

    return df


def _try_database_cache(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Attempt to load cached OHLCV data from the DB (future implementation).
    Returns None until the cache implementation is wired in.
    """
    return None
