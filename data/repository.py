"""
data/repository.py — OHLCV data fetching from MT5, with broker-aware symbol resolution.
All external data flows through here so validation is applied consistently.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config.settings import config, resolve_broker_symbol
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
    """Convert a human timeframe string to the MT5 constant."""
    tf = _MT5_TF_MAP.get(timeframe.upper())
    if tf is None:
        raise ValueError(
            "Unsupported timeframe: %r. Supported: %s"
            % (timeframe, list(_MT5_TF_MAP))
        )
    return tf


def _mt5_init() -> bool:
    """Initialise MT5 connection.

    Priority
    --------
    1. Attach to a running terminal (``mt5.initialize()`` no-args).  This is
       the preferred path when the user has the JustMarkets terminal open —
       it's reliable, requires no credentials, and picks up live state.
    2. Credential-based init (``login=, password=, server=``) as a headless
       fallback when the terminal is NOT running but credentials are available.

    Both paths are logged so failures are actionable.
    """
    try:
        import MetaTrader5 as mt5  # noqa: F811 — re-bound locally
    except ImportError:
        log.error("metatrader5 package not installed — cannot fetch live data")
        return False

    # ── Attempt 1: attach to a running terminal (most common case) ─────
    log.info("MT5: attempting attach mode (mt5.initialize() no-args)")
    ok = mt5.initialize()
    if ok:
        info = mt5.terminal_info()
        log.info(
            "MT5 attach OK: terminal=%s connected=%s",
            info.name if info else "?",
            info.connected if info else "?",
        )
        return True
    err = mt5.last_error()
    log.warning("MT5 attach failed: %s", err)

    # ── Attempt 2: credential-based init (headless / automated) ─────────
    if config.mt5.login and config.mt5.server:
        log.info(
            "MT5: trying credential init login=%s server=%s",
            config.mt5.login,
            config.mt5.server,
        )
        ok = mt5.initialize(
            login=config.mt5.login,
            password="[REDACTED]",  # never log raw passwords (Rule: never log credentials)
            server=config.mt5.server,
            timeout=config.mt5.timeout,
        )
        if ok:
            log.info("MT5 credential init succeeded")
            return True
        err = mt5.last_error()
        log.error("MT5 credential init failed: %s", err)

    log.error("MT5 initialise failed — both attach and credential modes exhausted")
    return False


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    n_bars: int = 5000,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from the MT5 terminal.

    Parameters
    ----------
    symbol : str
        Canonical ticker (e.g. "XAUUSD", "EURUSD").  Resolved to the
        broker-specific terminal name via ``resolve_broker_symbol()``.
    timeframe : str
        One of M1, M5, M15, M30, H1, H4, D1.
    start / end : datetime | None
        Boundaries for the fetch.  If ``None``, defaults are set by MT5.
    n_bars : int
        Fallback bar count when no start/end supplied.

    Returns
    -------
    pd.DataFrame or None
        Columns: open, high, low, close, (volume, tick_volume, spread).
        Index: pd.DatetimeIndex, tz-aware UTC.
    """
    try:
        import MetaTrader5 as mt5  # noqa: F811
    except ImportError:
        log.error("metatrader5 package not installed — cannot fetch live data")
        return None

    tf = timeframe_to_mt5(timeframe)

    # ── Initialise connection ─────────────────────────────────────────
    if not _mt5_init():
        return None

    # ── Resolve canonical symbol → broker-specific terminal name ──────
    # Strategy Layer                → ASSET_POOL uses canonical names (no suffix)
    # repository._mt5_init()       → broker-agnostic, just connects
    # THIS LINE (below)             → converts canonical→MT5 terminal name
    # MT5 copy_rates_range()       → receives broker-specific name
    #
    # Put the broker-suffix logic HERE (one place), not scattered.
    # e.g. "US500" + JustMarkets = "US500.std"
    #       "EURUSD" + JustMarkets = "EURUSD.m"
    #       "BRENT"  + JustMarkets = "BRENT.m"  (explicit override in BROKER_MAP)
    broker_sym = resolve_broker_symbol(symbol, config.mt5.server)
    log.info(
        "MT5 resolved symbol: %s (canonical=%s, server=%s)",
        broker_sym, symbol, config.mt5.server,
    )

    # ── Build time window ─────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    if start is None:
        tf_minutes = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440,
        }.get(timeframe.upper(), 1)
        start = datetime.fromtimestamp(
            now.timestamp() - n_bars * tf_minutes * 60, tz=timezone.utc
        )
    else:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    if end is None:
        end = now
    else:
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

    log.info(
        "MT5 copy_rates_range: symbol=%s timeframe=%s %s -> %s",
        broker_sym, timeframe, start.isoformat(), end.isoformat(),
    )

    rates = mt5.copy_rates_range(broker_sym, tf, start, end)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        log.warning(
            "No MT5 data: symbol=%s timeframe=%s error=%s",
            broker_sym, timeframe, mt5.last_error(),
        )
        return None

    log.info("MT5 returned %d bars for %s", len(rates), broker_sym)

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
    opt_cols = {"volume", "tick_volume", "spread"}
    keep = ["open", "high", "low", "close"] + [c for c in df.columns if c in opt_cols]
    df = df[keep].copy()

    # Sort ascending, drop duplicate timestamps keeping last
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]

    # Validate — log but do not raise; caller checks is_valid flag
    report = validate(df, symbol=symbol, timeframe=timeframe)
    if not report.is_valid:
        log.warning(
            "Repository returning invalidated data: symbol=%s timeframe=%s issues=%s",
            symbol, timeframe, report.issues,
        )
        # Return the frame so the caller can decide; issues are in the logs.

    return df


def _try_database_cache(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Attempt to load cached OHLCV data from the DB (future implementation)."""
    return None
