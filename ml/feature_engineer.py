"""ml/feature_engineer.py — Build ML feature matrix from OHLCV DataFrame.

Produces a (n_samples, n_features) X array and a (n_samples,) y target,
together with the ordered feature names.

Features
--------
RSI-14, ATR-20 (as % of close), VWAP deviation, EMA-12/26 cross (normalised),
tick_volume delta, bar body ratio, London/NY/overlap session dummies (UTC),
20-bar rolling vol of returns.

Target
------
1-bar-forward binary: 1 if close[t+1] > close[t] else 0.
"""
from __future__ import annotations

import logging
from typing import cast

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def build_features(
    df: pd.DataFrame,
    target_bars: int = 1,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Return X, y, feature_names.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV bars with columns: open, high, low, close, (tick_volume, volume).
        Index must be a DatetimeIndex (UTC).
    target_bars : int
        Lookahead for the binary target.

    Returns
    -------
    X : np.ndarray, shape (n_samples, n_features)
    y : np.ndarray, shape (n_samples,)
    feature_names : list[str]
    """
    if df is None or len(df) < 40:
        raise ValueError("Insufficient data: need at least 40 bars")

    df = df.copy()

    # ── Intermediate columns (not features) ─────────────────────────
    # range used in body_ratio; clip to avoid division by zero
    df["range"] = (df["high"] - df["low"]).clip(lower=1e-9)
    df["return_"] = df["close"].pct_change()

    # ── RSI-14 ──────────────────────────────────────────────────────
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100.0 - 100.0 / (1.0 + rs)

    # ── ATR-20 ──────────────────────────────────────────────────────
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr_20"] = tr.rolling(20, min_periods=20).mean()
    # ATR as percentage of close — avoid div-by-zero
    df["atr_pct"] = df["atr_20"] / df["close"].replace(0, np.nan)

    # ── VWAP deviation (session-based or cumulative) ────────────────
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df.get("tick_volume", df.get("volume", pd.Series(1, index=df.index))).fillna(1)
    # Replace zero-volume bars with 1 to avoid div-by-zero in cumsum
    vol = vol.replace(0, 1)
    vwap = (tp * vol).cumsum() / vol.cumsum()
    # Normalise by ATR; if ATR is nan use the close itself (first bars)
    denom = df["atr_20"].replace(0, np.nan)
    df["vwap_dev"] = (df["close"] - vwap) / denom
    # Backfill nan vwap_dev from first valid bar
    df["vwap_dev"] = df["vwap_dev"].bfill()

    # ── EMA cross (12 vs 26) normalised by ATR ──────────────────────
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["ema_cross"] = (ema12 - ema26) / df["atr_20"].replace(0, np.nan)
    df["ema_cross"] = df["ema_cross"].bfill()

    # ── Volume delta ────────────────────────────────────────────────
    if "tick_volume" in df.columns:
        df["vol_delta"] = df["tick_volume"].diff().fillna(0)
    elif "volume" in df.columns:
        df["vol_delta"] = df["volume"].diff().fillna(0)
    else:
        df["vol_delta"] = 0.0

    # ── Bar body ratio ──────────────────────────────────────────────
    df["body_ratio"] = (df["close"] - df["open"]).abs() / df["range"]
    # Clip to [0, 1] — a bar body larger than range means wicks are
    # negative (data quality issue); cap it to keep the feature bounded.
    df["body_ratio"] = df["body_ratio"].clip(0, 1)

    # ── Session dummies (UTC hours) ─────────────────────────────────
    dt_idx = df.index
    hours = dt_idx.hour
    df["session_london"]  = ((hours >= 8)  & (hours < 16)).astype(float)
    df["session_ny"]      = ((hours >= 13) & (hours < 21)).astype(float)
    df["session_overlap"] = ((hours >= 13) & (hours < 16)).astype(float)

    # ── Rolling vol of returns ──────────────────────────────────────
    df["rolling_vol"] = df["return_"].rolling(20, min_periods=20).std()

    # ── Feature list (ordered — must match param_bounds order) ──────
    feature_names: list[str] = [
        "rsi_14",
        "atr_pct",
        "vwap_dev",
        "ema_cross",
        "vol_delta",
        "body_ratio",
        "session_london",
        "session_ny",
        "session_overlap",
        "rolling_vol",
    ]

    # ── Target: binary next-bar direction ───────────────────────────
    # shift(-target_bars): at bar t, target = direction at t + target_bars
    df["target"] = (df["close"].shift(-target_bars) > df["close"]).astype(int)

    # ── Drop NaN / inf AFTER all features + target are built ────────
    subset = feature_names + ["target"]
    clean = df[subset].replace([np.inf, -np.inf], np.nan).dropna()

    if len(clean) < 10:
        raise ValueError(
            f"Too few samples after dropna: {len(clean)} "
            f"(needed >= 10, have {len(df)} raw bars)"
        )

    X = cast(np.ndarray, clean[feature_names].to_numpy(dtype=np.float64))
    y = cast(np.ndarray, clean["target"].to_numpy(dtype=np.int64))

    log.info(
        "Feature matrix: %d samples x %d features, positive_rate=%.2f",
        len(X), len(feature_names), float(y.mean()),
    )
    return X, y, feature_names
