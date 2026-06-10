"""quant/optimiser.py — parameter search for trading strategies.

Supports three methods:

* Grid   — exhaustive Cartesian product; only practical when ≤2 params.
* Random — uniform random sample of ``n_iterations`` points.
* Bayesian — scikit-optimize ``gp_minimize``; falls back to random if
  ``skopt`` is not installed, if ``n == 0``, or if any step errors.

Fitness is computed by running the existing ``BacktestEngine`` and scoring
the resulting ``BacktestResult`` with the chosen metric.
"""
from __future__ import annotations

import itertools
import logging
import random
import time
from typing import Any

from config.settings import config
from quant.backtest_engine import BacktestEngine
from strategies.registry import StrategyRegistry

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Scoring                                                                     #
# --------------------------------------------------------------------------- #

_METRIC_ALIASES: dict[str, str] = {
    "sharpe": "sharpe",
    "sharpe_ratio": "sharpe",
    "calmar": "calmar",
    "calmar_ratio": "calmar",
    "net_profit": "net_profit",
    "netprofit": "net_profit",
    "profit": "net_profit",
}


def _score(result: Any, metric: str) -> float:
    """Map a BacktestResult → single float for comparison."""
    if result is None or not getattr(result, "trades", None):
        return -9999.0
    m = _METRIC_ALIASES.get(metric.lower(), "sharpe")
    if m == "sharpe":
        return float(result.sharpe_approx or 0.0)
    if m == "calmar":
        dd = abs(result.max_drawdown or 0.0)
        net = float((result.final_equity or 0.0) - (result.initial_equity or 0.0))
        return (net / dd) if dd > 1e-9 else 0.0
    # net_profit (default)
    return float((result.final_equity or 0.0) - (result.initial_equity or 0.0))


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _load_strategy_class(name: str) -> type:
    reg = StrategyRegistry(None)
    cls = reg.classes.get(name)
    if cls is None:
        raise ValueError(f"Strategy not found in registry: {name!r}")
    return cls


def _load_data(symbol: str, timeframe: str, db_session: Any = None):
    """Return a validated OHLCV DataFrame."""
    import pandas as pd
    if db_session is not None:
        from db.models import OHLCVBar
        rows = (
            db_session.query(OHLCVBar)
            .filter(OHLCVBar.symbol == symbol, OHLCVBar.timeframe == timeframe)
            .order_by(OHLCVBar.timestamp.asc())
            .all()
        )
        if not rows:
            raise ValueError(f"No OHLCV data for {symbol}/{timeframe}")
        df = pd.DataFrame(
            {
                "open": [r.open for r in rows],
                "high": [r.high for r in rows],
                "low": [r.low for r in rows],
                "close": [r.close for r in rows],
                "volume": [r.volume or 0 for r in rows],
                "tick_volume": [r.tick_volume or 0 for r in rows],
                "spread": [r.spread or 0 for r in rows],
            }
        )
        df.index = pd.to_datetime([r.timestamp for r in rows], utc=True)
    else:
        from data.repository import fetch_ohlcv
        df = fetch_ohlcv(symbol=symbol, timeframe=timeframe, n_bars=5000)
        if df is None or len(df) < 100:
            raise ValueError(f"Insufficient data for {symbol}/{timeframe}")
    return df


def _param_grid(bounds: dict[str, dict]) -> list[dict[str, Any]]:
    """Cartesian product of min/max/step specs → list of param dicts."""
    keys = sorted(bounds)
    ranges: list[list[float]] = []
    for k in keys:
        b = bounds[k]
        lo, hi, step = float(b["min"]), float(b["max"]), float(b.get("step", 1) or 1)
        vals: list[float] = []
        v = lo
        while v <= hi + 1e-9:
            vals.append(v)
            v += step
        ranges.append(vals)
    combos = list(itertools.product(*ranges))
    return [dict(zip(keys, c)) for c in combos]


def _random_points(
    bounds: dict[str, dict], n: int, rng: random.Random
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(n):
        pt: dict[str, Any] = {}
        for k, b in bounds.items():
            lo, hi = float(b["min"]), float(b["max"])
            step = float(b.get("step", 1) or 1)
            raw = rng.uniform(lo, hi)
            pt[k] = round(raw / step) * step if step > 0 else raw
        out.append(pt)
    return out


# --------------------------------------------------------------------------- #
#  Bayesian search (self-contained — no shared mutable cache)                  #
# --------------------------------------------------------------------------- #


def _bayesian_candidates(
    bounds: dict[str, dict],
    n: int,
    cls: type,
    df: Any,
    symbol: str,
    timeframe: str,
    metric: str,
) -> list[dict[str, Any]]:
    """Run gp_minimize and return the single best param dict.

    Falls back to random search if skopt is missing, if *n == 0*, or if
    any step in the process errors.
    """
    if n <= 0:
        return [{}]

    try:
        from skopt import gp_minimize
    except ImportError:
        log.warning(
            "scikit-optimize not installed — falling back to random search (n=%d)", n
        )
        rng = random.Random(42)
        return _random_points(bounds, n, rng)

    keys = sorted(bounds)
    sk_bounds = [
        (float(bounds[k]["min"]), float(bounds[k]["max"])) for k in keys
    ]
    steps = [float(bounds[k].get("step", 1) or 1) for k in keys]

    def _objective(x: list[float]) -> float:
        # skopt minimizes → return negative score so maximisation works
        params = {
            k: (round(x[i] / steps[i]) * steps[i] if steps[i] > 0 else x[i])
            for i, k in enumerate(keys)
        }
        try:
            engine = BacktestEngine()
            res = engine.run(df, cls, params, timeframe=timeframe, symbol=symbol)
            return -_score(res, metric)
        except Exception:
            return 1e9   # penalise candidates that error

    try:
        result = gp_minimize(
            func=_objective,
            dimensions=sk_bounds,
            n_calls=min(n, 100),
            n_random_starts=min(max(n // 4, 1), 25),
            random_state=42,
        )
        best = result.x
        return [
            {
                k: round(best[i] / steps[i]) * steps[i] if steps[i] > 0 else best[i]
                for i, k in enumerate(keys)
            }
        ]
    except Exception as exc:
        log.warning("Bayesian search failed (%s) — falling back to random", exc)
        rng = random.Random(42)
        return _random_points(bounds, n, rng)


# --------------------------------------------------------------------------- #
#  Public API                                                                  #
# --------------------------------------------------------------------------- #


def run(
    strategy_name: str,
    symbol: str,
    timeframe: str,
    param_bounds: dict[str, dict],
    search_method: str = "grid",
    fitness_metric: str = "sharpe",
    n_iterations: int = 200,
    db_session: Any = None,
) -> dict[str, Any]:
    """Run parameter search.

    Parameters
    ----------
    strategy_name : str
        Key in StrategyRegistry (e.g. ``"momentum_reversion"``).
    symbol, timeframe : str
        Instrument / timeframe to backtest on.
    param_bounds : dict[str, dict]
        ``{param_name: {"min": …, "max": …, "step": …}}``.
    search_method : str
        ``"grid"`` | ``"random"`` | ``"bayesian"``.
    fitness_metric : str
        ``"sharpe"`` | ``"calmar"`` | ``"net_profit"``.
    n_iterations : int
        Budget for random / bayesian search (ignored for grid).
    db_session : Session | None
        When provided OHLCV is loaded from the DB; otherwise
        :func:`data.repository.fetch_ohlcv` is used.

    Returns
    -------
    dict
        ``best_params``, ``best_score``, ``heatmap_data`` (grid only),
        ``top_n_results``, ``n_iterations``
    """
    t0 = time.monotonic()
    cls = _load_strategy_class(strategy_name)
    df = _load_data(symbol, timeframe, db_session=db_session)

    n_params = len(param_bounds)

    # Build candidate list
    if search_method == "grid" and n_params <= 2:
        candidates = _param_grid(param_bounds)
    elif search_method == "bayesian":
        candidates = _bayesian_candidates(
            param_bounds,
            n_iterations,
            cls=cls,
            df=df,
            symbol=symbol,
            timeframe=timeframe,
            metric=fitness_metric,
        )
    else:
        rng = random.Random(42)
        candidates = _random_points(param_bounds, n_iterations, rng)

    if not candidates:
        candidates = [{}]
        log.warning("Optimiser produced zero candidates; running single default combo")

    log.info(
        "Optimiser: strategy=%s symbol=%s tf=%s method=%s candidates=%d",
        strategy_name,
        symbol,
        timeframe,
        search_method,
        len(candidates),
    )

    # Score every candidate
    engine = BacktestEngine()
    scored: list[tuple[dict[str, Any], float, Any]] = []

    for params in candidates:
        try:
            res = engine.run(df, cls, params, timeframe=timeframe, symbol=symbol)
            score = _score(res, fitness_metric)
            scored.append((params, score, res))
        except Exception as exc:
            log.debug("Optimiser candidate failed: %s — %s", params, exc)

    if not scored:
        raise RuntimeError(
            "All parameter combinations failed — check strategy / data / param_bounds."
        )

    scored.sort(key=lambda t: t[1], reverse=True)
    best_params, best_score, best_result = scored[0]

    # Top-N for the UI table
    top_n = [
        {
            "params": p,
            "score": round(s, 6),
            "sharpe": round(float(getattr(r, "sharpe_approx", 0.0) or 0.0), 4),
            "profit_factor": round(float(getattr(r, "profit_factor", 0.0) or 0.0), 4),
            "max_drawdown": round(float(getattr(r, "max_drawdown", 0.0) or 0.0), 4),
            "n_trades": int(getattr(r, "n_trades", 0) or 0),
        }
        for p, s, r in scored[:20]
    ]

    # Heatmap data — only when exactly 2 params and grid search
    heatmap_data: list[dict[str, Any]] = []
    if n_params == 2 and search_method == "grid":
        p1_key, p2_key = sorted(param_bounds)
        b1, b2 = param_bounds[p1_key], param_bounds[p2_key]
        s1, s2 = float(b1.get("step", 1) or 1), float(b2.get("step", 1) or 1)
        lookup = {tuple(sorted(p.items())): s for p, s, _ in scored}
        for v1 in _frange(float(b1["min"]), float(b1["max"]), s1):
            for v2 in _frange(float(b2["min"]), float(b2["max"]), s2):
                key = tuple(sorted({p1_key: v1, p2_key: v2}.items()))
                score = lookup.get(key)
                if score is not None:
                    heatmap_data.append({"p1": v1, "p2": v2, "score": score})

    elapsed = round(time.monotonic() - t0, 2)
    log.info(
        "Optimiser done: best_score=%.4f best_params=%s elapsed=%ss",
        best_score,
        best_params,
        elapsed,
    )
    return {
        "best_params": best_params,
        "best_score": best_score,
        "heatmap_data": heatmap_data,
        "top_n_results": top_n,
        "n_iterations": len(candidates),
    }


# --------------------------------------------------------------------------- #
#  Internal helpers                                                            #
# --------------------------------------------------------------------------- #


def _frange(start: float, stop: float, step: float) -> list[float]:
    vals: list[float] = []
    v = start
    while v <= stop + 1e-9:
        vals.append(v)
        v += step
    return vals
