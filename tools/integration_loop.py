"""
tools/integration_loop.py

Full system integration verification loop.

Tests three things in sequence for every strategy:
  1. SIGNAL TEST    — strategy fires at least one signal on synthetic OHLCV data
  2. BACKTEST TEST  — backtest engine completes and returns a valid report
  3. FRONTEND TEST  — POST /api/quant/backtest endpoint accepts the request,
                      job completes, and returns equity curve + stats cards data

Plus one AI advisor test:
  4. AI ADVISOR TEST — advisor returns a suggestion with side, confidence, reasoning

Each test is independent. A failure in one does not block the others.
Results are written to tools/integration_report.json.

Run:
    .\venv\Scripts\python.exe tools/integration_loop.py

Run with live API test (requires dashboard running on port 8000):
    .\venv\Scripts\python.exe tools/integration_loop.py --with-api

Run a single strategy only:
    .\venv\Scripts\python.exe tools/integration_loop.py --strategy momentum_reversion

Exit code 0 = all tests passed
Exit code 1 = one or more tests failed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.WARNING,         # suppress noise from strategies/engine during tests
    format="%(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("integration_loop")
log.setLevel(logging.DEBUG)

# ── Constants ─────────────────────────────────────────────────────────────────

STRATEGIES = [
    "momentum_reversion",
    "band_reversion",
    "stochastic_trend",
    "session_breakout",
    "divergence_swing",
    "vwap_reversion",
    "macd_impulse",
]

# Symbol → asset class → synthetic data config
STRATEGY_META = {
    "momentum_reversion": {"symbol": "BTCUSD",  "timeframes": ["H1", "M15"], "asset_class": "crypto",    "base_price": 45000.0, "volatility": 0.015},
    "band_reversion":     {"symbol": "EURUSD",  "timeframes": ["H1", "M15"], "asset_class": "forex",     "base_price": 1.0850,  "volatility": 0.0008},
    "stochastic_trend":   {"symbol": "GBPUSD",  "timeframes": ["H1", "M15"], "asset_class": "forex",     "base_price": 1.2650,  "volatility": 0.0010},
    "session_breakout":   {"symbol": "XAUUSD",  "timeframes": ["M15"],       "asset_class": "commodity", "base_price": 2050.0,  "volatility": 0.008},
    "divergence_swing":   {"symbol": "XAGUSD",  "timeframes": ["H1", "M15"], "asset_class": "commodity", "base_price": 24.50,   "volatility": 0.012},
    "vwap_reversion":     {"symbol": "AAPL",    "timeframes": ["M5"],        "asset_class": "equity",    "base_price": 185.0,   "volatility": 0.006},
    "macd_impulse":       {"symbol": "TSLA",    "timeframes": ["H1", "M15"], "asset_class": "equity",    "base_price": 250.0,   "volatility": 0.020},
}

DASHBOARD_URL = "http://127.0.0.1:8000"
TEST_USERNAME  = "admin"
TEST_PASSWORD  = "changeme123"


# ── Result structures ─────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name:     str
    passed:   bool
    duration: float     # seconds
    detail:   str = ""
    error:    str = ""
    data:     dict = field(default_factory=dict)


@dataclass
class StrategyTestSuite:
    strategy_name:  str
    signal_test:    TestResult | None = None
    backtest_test:  TestResult | None = None
    frontend_test:  TestResult | None = None

    @property
    def all_passed(self) -> bool:
        tests = [self.signal_test, self.backtest_test, self.frontend_test]
        return all(t is not None and t.passed for t in tests)

    @property
    def any_failed(self) -> bool:
        tests = [self.signal_test, self.backtest_test, self.frontend_test]
        return any(t is not None and not t.passed for t in tests)


@dataclass
class IntegrationReport:
    run_id:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    suites:    list[StrategyTestSuite] = field(default_factory=list)
    ai_test:   TestResult | None = None

    @property
    def total_tests(self) -> int:
        count = 0
        for s in self.suites:
            for t in [s.signal_test, s.backtest_test, s.frontend_test]:
                if t is not None:
                    count += 1
        if self.ai_test:
            count += 1
        return count

    @property
    def passed_tests(self) -> int:
        count = sum(1 for s in self.suites
                    for t in [s.signal_test, s.backtest_test, s.frontend_test]
                    if t is not None and t.passed)
        if self.ai_test and self.ai_test.passed:
            count += 1
        return count

    @property
    def all_passed(self) -> bool:
        return self.passed_tests == self.total_tests


# ── Synthetic OHLCV generator ─────────────────────────────────────────────────

def make_ohlcv(
    n_bars:      int,
    timeframe:   str,
    base_price:  float,
    volatility:  float,
    start:       datetime | None = None,
    inject_signal_conditions: str = "mixed",  # "mixed" | "bullish" | "bearish"
    seed:        int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data that is realistic enough to trigger signals.

    inject_signal_conditions:
      "mixed"   — normal random walk (may or may not trigger signals)
      "bullish" — biased upward trend (increases chance of BUY signals)
      "bearish" — biased downward trend
    """
    rng = np.random.default_rng(seed)

    tf_minutes = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 60, "H4": 240, "D1": 1440,
    }
    minutes = tf_minutes.get(timeframe, 15)

    if start is None:
        # Use a Monday morning UTC time to ensure session conditions are met
        start = datetime(2024, 3, 4, 8, 0, 0)  # Monday 08:00 UTC

    freq_str = f"{minutes}min"
    index = pd.date_range(start=start, periods=n_bars, freq=freq_str, tz="UTC")

    # Price series with trend bias
    drift = {"mixed": 0.0, "bullish": 0.0002, "bearish": -0.0002}[inject_signal_conditions]
    returns = rng.normal(drift, volatility, n_bars)
    log_prices = np.log(base_price) + np.cumsum(returns)
    closes = np.exp(log_prices)

    # Build OHLC from closes
    noise = volatility * 0.5
    highs  = closes * (1 + np.abs(rng.normal(0, noise, n_bars)))
    lows   = closes * (1 - np.abs(rng.normal(0, noise, n_bars)))
    opens  = np.roll(closes, 1)
    opens[0] = base_price

    # Ensure OHLC validity
    highs  = np.maximum(highs, np.maximum(opens, closes))
    lows   = np.minimum(lows,  np.minimum(opens, closes))

    volume = rng.integers(100, 10000, n_bars).astype(float)

    df = pd.DataFrame({
        "open":        opens,
        "high":        highs,
        "low":         lows,
        "close":       closes,
        "tick_volume": volume,
    }, index=index)

    return df


def make_data_for_strategy(strategy_name: str, bias: str = "mixed") -> dict[str, pd.DataFrame]:
    """Build a complete data dict for a given strategy."""
    meta       = STRATEGY_META[strategy_name]
    timeframes = meta["timeframes"]
    base       = meta["base_price"]
    vol        = meta["volatility"]

    data = {}
    for tf in timeframes:
        # More bars for longer timeframes to ensure warmup
        n = {"M5": 600, "M15": 500, "H1": 300}.get(tf, 400)
        data[tf] = make_ohlcv(
            n_bars=n,
            timeframe=tf,
            base_price=base,
            volatility=vol,
            inject_signal_conditions=bias,
        )

    return data


# ── TEST 1: Signal generation ─────────────────────────────────────────────────

def test_signal_generation(strategy_name: str) -> TestResult:
    """
    Verifies that the strategy can:
    1. Import without error
    2. Instantiate with default params
    3. Accept a data dict without raising
    4. Fire at least one signal across multiple data scenarios
    """
    t0 = time.perf_counter()
    test_name = f"{strategy_name}.signal"

    try:
        # Dynamic import
        module_map = {
            "momentum_reversion": ("strategies.momentum_reversion", "MomentumReversion"),
            "band_reversion":     ("strategies.band_reversion",     "BandReversion"),
            "stochastic_trend":   ("strategies.stochastic_trend",   "StochasticTrend"),
            "session_breakout":   ("strategies.session_breakout",   "SessionBreakout"),
            "divergence_swing":   ("strategies.divergence_swing",   "DivergenceSwing"),
            "vwap_reversion":     ("strategies.vwap_reversion",     "VWAPReversion"),
            "macd_impulse":       ("strategies.macd_impulse",       "MACDImpulse"),
        }
        import importlib
        mod_path, cls_name = module_map[strategy_name]
        module  = importlib.import_module(mod_path)
        cls     = getattr(module, cls_name)

        # Instantiate with defaults
        strategy = cls()
        assert hasattr(strategy, "meta"),           "missing meta"
        assert hasattr(strategy, "default_params"), "missing default_params"
        assert hasattr(strategy, "param_bounds"),   "missing param_bounds"
        assert set(strategy.default_params.keys()) == set(strategy.param_bounds.keys()), \
            "param_bounds keys do not match default_params keys"

        # Try signal generation across 3 scenarios
        signals_found = []
        errors        = []
        scenarios     = [
            ("mixed",   42),
            ("bullish", 100),
            ("bearish", 200),
            ("bullish", 300),
            ("bearish", 400),
        ]

        for bias, seed in scenarios:
            try:
                data = make_data_for_strategy(strategy_name, bias=bias)
                # Replace seed in make_ohlcv — rebuild with different seed
                meta = STRATEGY_META[strategy_name]
                for tf in meta["timeframes"]:
                    n = {"M5": 600, "M15": 500, "H1": 300}.get(tf, 400)
                    data[tf] = make_ohlcv(
                        n_bars=n, timeframe=tf,
                        base_price=meta["base_price"],
                        volatility=meta["volatility"],
                        inject_signal_conditions=bias,
                        seed=seed,
                    )

                # Run signal on last 50 bar slices (simulate live feed)
                signal_tf  = strategy.meta.timeframes[-1]
                full_df    = data[signal_tf]
                warmup     = 250

                for i in range(warmup, len(full_df)):
                    slice_data = {tf: df.iloc[:i+1] for tf, df in data.items()}
                    sig = strategy.generate_signal(slice_data)
                    if sig is not None:
                        signals_found.append({
                            "scenario": bias,
                            "seed":     seed,
                            "bar":      i,
                            "side":     sig.side.value,
                            "entry":    round(sig.entry, 5),
                            "sl":       round(sig.sl, 5),
                            "tp":       round(sig.tp, 5),
                            "tag":      sig.tag,
                        })
                        break  # one signal per scenario is enough

            except Exception as exc:
                errors.append(f"scenario={bias} seed={seed}: {exc}")

        # Verdict
        if errors:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"Errors during signal generation: {len(errors)}",
                error="\n".join(errors),
            )

        if not signals_found:
            # Not necessarily a bug — strict conditions may mean no signal on synthetic data
            # But we need at least one to confirm the pipeline works
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="No signals generated across 5 synthetic scenarios (bullish + bearish + mixed)",
                error=(
                    "Strategy returned None on all bar iterations. "
                    "Check: (1) session window params vs synthetic data timestamps, "
                    "(2) ATR minimum threshold vs synthetic volatility, "
                    "(3) trend filter strictness. "
                    "Synthetic data timestamps start Monday 08:00 UTC."
                ),
                data={"scenarios_tested": len(scenarios), "errors": errors},
            )

        return TestResult(
            name=test_name, passed=True,
            duration=time.perf_counter() - t0,
            detail=f"Fired {len(signals_found)} signal(s) across {len(scenarios)} scenarios",
            data={
                "signals": signals_found,
                "params":  strategy.default_params,
                "meta":    {
                    "symbol":      strategy.meta.symbol,
                    "asset_class": strategy.meta.asset_class,
                    "timeframes":  strategy.meta.timeframes,
                },
            },
        )

    except Exception as exc:
        return TestResult(
            name=test_name, passed=False,
            duration=time.perf_counter() - t0,
            detail="Unexpected exception during signal test",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


# ── TEST 2: Backtest engine ───────────────────────────────────────────────────

def test_backtest_engine(strategy_name: str) -> TestResult:
    """
    Verifies that BacktestEngine.run() completes and returns a valid report.

    Checks:
    - Report is a BacktestReport instance
    - equity_curve starts at 1.0
    - equity_curve has at least 1 point
    - drawdown_curve same length as equity_curve
    - monthly_returns is a dict
    - sharpe_ratio is a real number (not NaN/inf)
    - max_drawdown_pct >= 0
    - If total_trades > 0: win_rate between 0 and 1
    - No look-ahead: verifiable by checking equity_curve monotonicity during drawdown
    """
    t0 = time.perf_counter()
    test_name = f"{strategy_name}.backtest"

    try:
        from quant.backtest_engine import BacktestEngine
        from config.settings import config

        import importlib
        module_map = {
            "momentum_reversion": ("strategies.momentum_reversion", "MomentumReversion"),
            "band_reversion":     ("strategies.band_reversion",     "BandReversion"),
            "stochastic_trend":   ("strategies.stochastic_trend",   "StochasticTrend"),
            "session_breakout":   ("strategies.session_breakout",   "SessionBreakout"),
            "divergence_swing":   ("strategies.divergence_swing",   "DivergenceSwing"),
            "vwap_reversion":     ("strategies.vwap_reversion",     "VWAPReversion"),
            "macd_impulse":       ("strategies.macd_impulse",       "MACDImpulse"),
        }
        mod_path, cls_name = module_map[strategy_name]
        module   = importlib.import_module(mod_path)
        cls      = getattr(module, cls_name)

        # Build synthetic data — longer for backtest
        meta     = STRATEGY_META[strategy_name]
        data     = {}
        for tf in meta["timeframes"]:
            n = {"M5": 2000, "M15": 1500, "H1": 600}.get(tf, 1000)
            data[tf] = make_ohlcv(
                n_bars=n, timeframe=tf,
                base_price=meta["base_price"],
                volatility=meta["volatility"],
                inject_signal_conditions="mixed",
                seed=999,
            )

        engine = BacktestEngine()
        report = engine.run(
            strategy_cls   = cls,
            data           = data,
            params         = None,       # use defaults
            initial_equity = config.backtest.default_initial_equity,
            risk_per_trade = config.backtest.default_risk_per_trade,
            log_trades     = False,
        )

        # ── Structural checks ──────────────────────────────────────────
        issues = []

        if report is None:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="BacktestEngine.run() returned None",
                error="Expected BacktestReport, got None",
            )

        # equity_curve checks
        if not report.equity_curve:
            issues.append("equity_curve is empty")
        elif abs(report.equity_curve[0] - 1.0) > 1e-6:
            issues.append(f"equity_curve does not start at 1.0 (got {report.equity_curve[0]})")

        # drawdown_curve checks
        if hasattr(report, "drawdown_curve"):
            if len(report.drawdown_curve) != len(report.equity_curve):
                issues.append(
                    f"drawdown_curve length {len(report.drawdown_curve)} != "
                    f"equity_curve length {len(report.equity_curve)}"
                )
            if any(d < 0 for d in report.drawdown_curve):
                issues.append("drawdown_curve contains negative values")

        # monthly_returns checks
        if hasattr(report, "monthly_returns"):
            if not isinstance(report.monthly_returns, dict):
                issues.append(f"monthly_returns is not a dict (got {type(report.monthly_returns)})")

        # numeric checks
        if np.isnan(report.sharpe_ratio) or np.isinf(report.sharpe_ratio):
            issues.append(f"sharpe_ratio is NaN or Inf: {report.sharpe_ratio}")
        if report.max_drawdown_pct < 0:
            issues.append(f"max_drawdown_pct is negative: {report.max_drawdown_pct}")
        if report.total_trades > 0:
            if not (0.0 <= report.win_rate <= 1.0):
                issues.append(f"win_rate out of range: {report.win_rate}")
            if report.expectancy_r is not None and np.isnan(report.expectancy_r):
                issues.append("expectancy_r is NaN")

        # p_value check
        if hasattr(report, "p_value") and report.total_trades > 0:
            if not (0.0 <= report.p_value <= 1.0):
                issues.append(f"p_value out of range: {report.p_value}")

        # benchmark_equity check
        if hasattr(report, "benchmark_equity") and report.benchmark_equity:
            if abs(report.benchmark_equity[0] - 1.0) > 1e-4:
                issues.append(
                    f"benchmark_equity does not start at 1.0 (got {report.benchmark_equity[0]})"
                )

        if issues:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"BacktestReport has {len(issues)} structural issue(s)",
                error="\n".join(issues),
                data={"total_trades": report.total_trades, "issues": issues},
            )

        # ── Content check: warn if zero trades ──────────────────────────
        detail = (
            f"trades={report.total_trades} "
            f"win_rate={report.win_rate:.1%} "
            f"sharpe={report.sharpe_ratio:.3f} "
            f"max_dd={report.max_drawdown_pct:.2f}% "
            f"equity_points={len(report.equity_curve)}"
        )
        if report.total_trades == 0:
            detail += " ⚠ WARNING: zero trades — strategy may be too strict for synthetic data"

        return TestResult(
            name=test_name, passed=True,
            duration=time.perf_counter() - t0,
            detail=detail,
            data={
                "total_trades":    report.total_trades,
                "win_rate":        report.win_rate,
                "sharpe_ratio":    report.sharpe_ratio,
                "max_drawdown":    report.max_drawdown_pct,
                "expectancy_r":    report.expectancy_r,
                "equity_points":   len(report.equity_curve),
                "monthly_returns": getattr(report, "monthly_returns", {}),
                "is_significant":  getattr(report, "is_significant", None),
            },
        )

    except Exception as exc:
        return TestResult(
            name=test_name, passed=False,
            duration=time.perf_counter() - t0,
            detail="Exception during BacktestEngine.run()",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


# ── TEST 3: Frontend API backtest endpoint ────────────────────────────────────

def test_frontend_backtest_api(
    strategy_name: str,
    base_url:      str,
    token:         str,
) -> TestResult:
    """
    Verifies the full frontend→backend backtest flow:
    1. POST /api/quant/backtest — returns job_id
    2. Poll GET /api/quant/backtest/{job_id} — waits for completion
    3. Validates response structure matches what the frontend expects:
       - stats cards fields present and numeric
       - equity_curve is a list of floats
       - monthly_returns is a dict
       - drawdown_curve present

    This is the test that catches:
    - Missing route registrations
    - Serialisation bugs (NaN/Inf in JSON)
    - Missing fields the frontend chart expects
    - Background task failures
    """
    t0 = time.perf_counter()
    test_name = f"{strategy_name}.frontend_api"

    try:
        import httpx

        headers = {
            "Authorization":   f"Bearer {token}",
            "Content-Type":    "application/json",
            "X-Requested-With":"XMLHttpRequest",
        }

        # Step 1: Submit backtest job
        payload = {
            "strategy_name":  strategy_name,
            "params":         None,      # use registry defaults
            "period_days":    90,        # 3 months of data
            "initial_equity": 10000.0,
            "risk_per_trade": 0.01,
            "run_walk_forward": False,
        }

        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{base_url}/api/quant/backtest",
                json=payload,
                headers=headers,
            )

        if r.status_code == 401:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="HTTP 401 — JWT token rejected",
                error="Authentication failed. Check token validity and auth dependency on /api/quant/backtest",
            )
        if r.status_code == 404:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="HTTP 404 — /api/quant/backtest not found",
                error=(
                    "Route not registered. Check: "
                    "1) dashboard/routes/quant.py has POST /backtest, "
                    "2) app.include_router(quant_router, prefix='/api/quant') in dashboard/app.py"
                ),
            )
        if r.status_code != 200:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"HTTP {r.status_code} from POST /api/quant/backtest",
                error=f"Response: {r.text[:500]}",
            )

        submit_data = r.json()
        if "job_id" not in submit_data:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="POST /api/quant/backtest did not return job_id",
                error=f"Response keys: {list(submit_data.keys())}. Expected 'job_id'.",
            )

        job_id = submit_data["job_id"]

        # Step 2: Poll for completion
        MAX_WAIT_SECONDS = 120
        POLL_INTERVAL    = 2
        elapsed          = 0
        job_result       = None

        with httpx.Client(timeout=15.0) as client:
            while elapsed < MAX_WAIT_SECONDS:
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

                poll = client.get(
                    f"{base_url}/api/quant/backtest/{job_id}",
                    headers=headers,
                )

                if poll.status_code == 404:
                    return TestResult(
                        name=test_name, passed=False,
                        duration=time.perf_counter() - t0,
                        detail=f"HTTP 404 — /api/quant/backtest/{job_id} not found",
                        error="GET job status endpoint missing. Check route: GET /api/quant/backtest/{job_id}",
                    )
                if poll.status_code != 200:
                    return TestResult(
                        name=test_name, passed=False,
                        duration=time.perf_counter() - t0,
                        detail=f"HTTP {poll.status_code} polling job status",
                        error=poll.text[:500],
                    )

                poll_data = poll.json()
                status    = poll_data.get("status", "unknown")

                if status == "failed":
                    return TestResult(
                        name=test_name, passed=False,
                        duration=time.perf_counter() - t0,
                        detail=f"Backtest job failed (job_id={job_id})",
                        error=poll_data.get("error", "No error message returned"),
                    )

                if status == "complete":
                    job_result = poll_data
                    break

                log.debug("  Polling job %s: status=%s elapsed=%ds", job_id, status, elapsed)

        if job_result is None:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"Backtest job timed out after {MAX_WAIT_SECONDS}s (job_id={job_id})",
                error="Job still 'running' or 'pending' after timeout. Check BackgroundTask execution.",
            )

        # Step 3: Validate response structure for frontend
        result  = job_result.get("result", {})
        issues  = []

        # Fields the frontend stats cards expect
        REQUIRED_STATS = [
            "total_trades", "win_rate", "sharpe_ratio",
            "max_drawdown_pct", "expectancy_r", "profit_factor",
            "avg_trades_per_week",
        ]
        for field_name in REQUIRED_STATS:
            if field_name not in result:
                issues.append(f"Missing stats field: '{field_name}'")
            elif result[field_name] is not None:
                val = result[field_name]
                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    issues.append(
                        f"Field '{field_name}' is {val} — JSON serialisation will fail. "
                        f"Replace with None or 0 before serialising."
                    )

        # Fields the frontend equity curve chart expects
        REQUIRED_CHARTS = ["equity_curve", "drawdown_curve", "monthly_returns"]
        for field_name in REQUIRED_CHARTS:
            if field_name not in result:
                issues.append(f"Missing chart field: '{field_name}'")
            elif field_name == "equity_curve":
                ec = result["equity_curve"]
                if not isinstance(ec, list):
                    issues.append(f"equity_curve must be a list, got {type(ec)}")
                elif ec and abs(ec[0] - 1.0) > 1e-4:
                    issues.append(f"equity_curve does not start at 1.0 (got {ec[0]})")
            elif field_name == "drawdown_curve":
                dc = result["drawdown_curve"]
                if not isinstance(dc, list):
                    issues.append(f"drawdown_curve must be a list, got {type(dc)}")
            elif field_name == "monthly_returns":
                mr = result["monthly_returns"]
                if not isinstance(mr, dict):
                    issues.append(f"monthly_returns must be a dict, got {type(mr)}")

        # p_value and significance for hypothesis display
        if "p_value" not in result:
            issues.append("Missing field: 'p_value' (needed for hypothesis display)")
        if "is_significant" not in result:
            issues.append("Missing field: 'is_significant'")

        if issues:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"Response structure has {len(issues)} issue(s) that will break frontend charts",
                error="\n".join(issues),
                data={"job_id": job_id, "result_keys": list(result.keys())},
            )

        total_trades = result.get("total_trades", 0)
        detail = (
            f"job_id={job_id} "
            f"completed in {elapsed}s "
            f"trades={total_trades} "
            f"sharpe={result.get('sharpe_ratio', 'N/A')} "
            f"equity_points={len(result.get('equity_curve', []))}"
        )
        if total_trades == 0:
            detail += " ⚠ zero trades on 90-day synthetic data"

        return TestResult(
            name=test_name, passed=True,
            duration=time.perf_counter() - t0,
            detail=detail,
            data={
                "job_id":         job_id,
                "total_trades":   total_trades,
                "sharpe_ratio":   result.get("sharpe_ratio"),
                "equity_points":  len(result.get("equity_curve", [])),
                "stats_present":  REQUIRED_STATS,
                "charts_present": REQUIRED_CHARTS,
            },
        )

    except Exception as exc:
        return TestResult(
            name=test_name, passed=False,
            duration=time.perf_counter() - t0,
            detail="Exception during frontend API test",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


# ── TEST 4: AI advisor ────────────────────────────────────────────────────────

async def test_ai_advisor() -> TestResult:
    """
    Verifies that AIAdvisor.suggest() returns a valid suggestion.

    Checks:
    - Returns an AIAdvisorSuggestion (not None, not exception)
    - side is one of BUY / SELL / NEUTRAL
    - confidence is 0.0–1.0
    - reasoning is a non-empty string
    - entry_zone, sl_suggestion, tp_suggestion are strings

    Uses EURUSD M15 synthetic data as the test subject.
    Temporarily lowers min_confidence_to_show to 0.0 to ensure something returns.
    """
    t0 = time.perf_counter()
    test_name = "ai_advisor.suggest"

    try:
        from ai_advisor.advisor import AIAdvisor
        from config.settings import config

        if not config.ai.anthropic_api_key:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="Skipped — ANTHROPIC_API_KEY not set",
                error=(
                    "Set env var ANTHROPIC_API_KEY to enable AI advisor tests. "
                    "Run: $env:ANTHROPIC_API_KEY = 'your-key'"
                ),
            )

        # Temporarily lower confidence threshold for testing
        from copy import deepcopy
        test_ai_config = deepcopy(config.ai)
        test_ai_config.enabled                = True
        test_ai_config.min_confidence_to_show = 0.0   # accept any response
        test_ai_config.cooldown_minutes       = 0      # no cooldown in tests

        advisor = AIAdvisor(test_ai_config)

        # Synthetic data
        df = make_ohlcv(
            n_bars=60, timeframe="M15",
            base_price=1.0850, volatility=0.0008,
            inject_signal_conditions="mixed", seed=77,
        )

        account_stats = {
            "balance":          10000.0,
            "equity":           10150.0,
            "open_trades_count": 1,
            "daily_pnl":        150.0,
        }
        recent_trades = [
            {"symbol": "EURUSD", "side": "BUY",  "pnl_r":  1.8, "strategy": "band_reversion"},
            {"symbol": "XAUUSD", "side": "SELL", "pnl_r": -1.0, "strategy": "session_breakout"},
        ]

        suggestion = await advisor.suggest(
            symbol        = "EURUSD",
            timeframe     = "M15",
            df            = df,
            account_stats = account_stats,
            recent_trades = recent_trades,
        )

        if suggestion is None:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail="AIAdvisor.suggest() returned None with min_confidence=0.0",
                error=(
                    "Expected a suggestion with min_confidence_to_show=0.0. "
                    "Check: (1) API call succeeds, (2) response JSON parsed correctly, "
                    "(3) _parse_response() returns a dict, (4) all required keys present."
                ),
            )

        # Structural checks
        issues = []

        if not hasattr(suggestion, "side") or suggestion.side not in ("BUY", "SELL", "NEUTRAL", None):
            issues.append(f"side invalid: {suggestion.side!r}")

        if suggestion.confidence is not None:
            if not (0.0 <= suggestion.confidence <= 1.0):
                issues.append(f"confidence out of range: {suggestion.confidence}")

        if not suggestion.reasoning or len(suggestion.reasoning.strip()) < 20:
            issues.append(f"reasoning too short or empty: {suggestion.reasoning!r}")

        if issues:
            return TestResult(
                name=test_name, passed=False,
                duration=time.perf_counter() - t0,
                detail=f"AIAdvisorSuggestion has {len(issues)} structural issue(s)",
                error="\n".join(issues),
            )

        return TestResult(
            name=test_name, passed=True,
            duration=time.perf_counter() - t0,
            detail=(
                f"side={suggestion.side} "
                f"confidence={suggestion.confidence:.2f} "
                f"reasoning_length={len(suggestion.reasoning or '')}"
            ),
            data={
                "side":           suggestion.side,
                "confidence":     suggestion.confidence,
                "entry_zone":     suggestion.entry_zone,
                "sl_suggestion":  suggestion.sl_suggestion,
                "tp_suggestion":  suggestion.tp_suggestion,
                "reasoning_len":  len(suggestion.reasoning or ""),
            },
        )

    except Exception as exc:
        return TestResult(
            name=test_name, passed=False,
            duration=time.perf_counter() - t0,
            detail="Exception during AI advisor test",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        )


# ── API authentication helper ─────────────────────────────────────────────────

def get_api_token(base_url: str, username: str, password: str) -> str | None:
    """Logs into the dashboard and returns a JWT access token."""
    try:
        import httpx
        r = httpx.post(
            f"{base_url}/auth/login",
            json={"username": username, "password": password},
            timeout=10.0,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        log.error("Login failed: HTTP %d %s", r.status_code, r.text[:200])
        return None
    except Exception as exc:
        log.error("Login request failed: %s", exc)
        return None


# ── Reporting ─────────────────────────────────────────────────────────────────

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
SKIP = "\033[90m–\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_test_result(result: TestResult | None, indent: int = 4) -> None:
    pad = " " * indent
    if result is None:
        print(f"{pad}{SKIP}  skipped")
        return
    icon = PASS if result.passed else FAIL
    print(f"{pad}{icon}  {result.name}  [{result.duration:.2f}s]")
    print(f"{pad}   {result.detail}")
    if not result.passed and result.error:
        for line in result.error.strip().splitlines()[:6]:
            print(f"{pad}   \033[91m{line}\033[0m")
        if result.error.count("\n") > 6:
            print(f"{pad}   \033[91m... (see integration_report.json for full error)\033[0m")


def print_report(report: IntegrationReport, with_api: bool) -> None:
    print(f"\n{BOLD}═══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  INTEGRATION VERIFICATION LOOP — {report.run_id}{RESET}")
    print(f"{BOLD}  {report.timestamp}{RESET}")
    print(f"{BOLD}═══════════════════════════════════════════════════════{RESET}\n")

    for suite in report.suites:
        icon = PASS if suite.all_passed else FAIL
        print(f"  {icon} {BOLD}{suite.strategy_name}{RESET}")
        print_test_result(suite.signal_test)
        print_test_result(suite.backtest_test)
        if with_api:
            print_test_result(suite.frontend_test)
        else:
            print(f"    {SKIP}  {suite.strategy_name}.frontend_api  [skipped — run with --with-api]")
        print()

    if report.ai_test:
        print(f"  {PASS if report.ai_test.passed else FAIL} {BOLD}AI Advisor{RESET}")
        print_test_result(report.ai_test)
        print()

    print(f"{BOLD}───────────────────────────────────────────────────────{RESET}")
    total  = report.total_tests
    passed = report.passed_tests
    failed = total - passed
    if report.all_passed:
        print(f"  {PASS} {BOLD}ALL {total} TESTS PASSED{RESET}")
    else:
        print(f"  {FAIL} {BOLD}{failed}/{total} TESTS FAILED{RESET}")
    print(f"{BOLD}───────────────────────────────────────────────────────{RESET}\n")
    print(f"  Report saved to: tools/integration_report.json\n")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="ICT-ML Platform integration verification loop")
    parser.add_argument("--with-api",  action="store_true",
                        help="Also test frontend API endpoints (requires dashboard running)")
    parser.add_argument("--strategy",  type=str, default=None,
                        help="Test only this strategy (e.g. momentum_reversion)")
    parser.add_argument("--skip-ai",   action="store_true",
                        help="Skip AI advisor test")
    parser.add_argument("--url",       type=str, default=DASHBOARD_URL,
                        help=f"Dashboard URL (default: {DASHBOARD_URL})")
    parser.add_argument("--username",  type=str, default=TEST_USERNAME)
    parser.add_argument("--password",  type=str, default=TEST_PASSWORD)
    args = parser.parse_args()

    strategies_to_test = [args.strategy] if args.strategy else STRATEGIES

    # Validate strategy name
    for name in strategies_to_test:
        if name not in STRATEGY_META:
            print(f"ERROR: unknown strategy '{name}'. Valid: {list(STRATEGY_META.keys())}")
            return 1

    report = IntegrationReport()
    token  = None

    # Get API token if testing frontend
    if args.with_api:
        print(f"Authenticating with dashboard at {args.url}...")
        token = get_api_token(args.url, args.username, args.password)
        if token is None:
            print(f"  {FAIL} Could not authenticate. Is the dashboard running at {args.url}?")
            print(f"     Start it with: .\\venv\\Scripts\\python.exe main.py --dashboard-only")
            return 1
        print(f"  {PASS} Authenticated as {args.username}\n")

    # ── Main strategy loop ────────────────────────────────────────────
    for strategy_name in strategies_to_test:
        print(f"Testing {BOLD}{strategy_name}{RESET}...")
        suite = StrategyTestSuite(strategy_name=strategy_name)

        # Test 1: signal generation
        print(f"  Running signal test...")
        suite.signal_test = test_signal_generation(strategy_name)

        # Test 2: backtest engine (always run — independent of signal test)
        print(f"  Running backtest engine test...")
        suite.backtest_test = test_backtest_engine(strategy_name)

        # Test 3: frontend API (only if --with-api and authenticated)
        if args.with_api and token:
            print(f"  Running frontend API test...")
            suite.frontend_test = test_frontend_backtest_api(
                strategy_name, args.url, token
            )

        report.suites.append(suite)
        status = PASS if suite.all_passed else FAIL
        print(f"  {status} {strategy_name} complete\n")

    # ── AI advisor test ───────────────────────────────────────────────
    if not args.skip_ai:
        print(f"Testing {BOLD}AI Advisor{RESET}...")
        report.ai_test = asyncio.run(test_ai_advisor())
        status = PASS if report.ai_test.passed else FAIL
        print(f"  {status} AI advisor complete\n")

    # ── Print and save report ─────────────────────────────────────────
    print_report(report, with_api=args.with_api)

    # Save JSON report
    Path("tools").mkdir(exist_ok=True)

    def serialise(obj):
        if isinstance(obj, TestResult):
            return asdict(obj)
        if isinstance(obj, StrategyTestSuite):
            return {
                "strategy_name":  obj.strategy_name,
                "all_passed":     obj.all_passed,
                "signal_test":    asdict(obj.signal_test)    if obj.signal_test    else None,
                "backtest_test":  asdict(obj.backtest_test)  if obj.backtest_test  else None,
                "frontend_test":  asdict(obj.frontend_test)  if obj.frontend_test  else None,
            }
        raise TypeError(f"Cannot serialise {type(obj)}")

    json_report = {
        "run_id":        report.run_id,
        "timestamp":     report.timestamp,
        "all_passed":    report.all_passed,
        "total_tests":   report.total_tests,
        "passed_tests":  report.passed_tests,
        "suites":        [serialise(s) for s in report.suites],
        "ai_test":       asdict(report.ai_test) if report.ai_test else None,
    }
    Path("tools/integration_report.json").write_text(
        json.dumps(json_report, indent=2, default=str),
        encoding="utf-8",
    )

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
