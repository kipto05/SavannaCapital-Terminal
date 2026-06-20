"""Test all 7 strategies with EURUSD M15 data.

Fetches EURUSD M15 from MT5, runs each strategy through BacktestEngine,
and reports trade counts and errors.
"""
import sys
import logging

sys.stdout.reconfigure(encoding="utf-8")

# Must set env before importing anything that reads it
import os
os.environ["DATABASE_URL"] = "postgresql://trading:trading@localhost:5432/tradingwf"

# Suppress noisy per-bar strategy logs during the test
logging.basicConfig(
    level=logging.CRITICAL,
    format="%(levelname)s %(name)s: %(message)s",
)

from quant.backtest_engine import BacktestEngine
from strategies.crypto import MomentumReversion
from strategies.divergence_swing import DivergenceSwing
from strategies.forex import BandReversion, StochasticTrend
from strategies.commodities import SessionBreakout
from strategies.equities import VWAPReversion, MACDImpulse
from db.session import SessionLocal
from data.repository import fetch_ohlcv

STRATEGIES = [
    ("momentum_reversion", MomentumReversion),
    ("band_reversion", BandReversion),
    ("stochastic_trend", StochasticTrend),
    ("session_breakout", SessionBreakout),
    ("divergence_swing", DivergenceSwing),
    ("vwap_reversion", VWAPReversion),
    ("macd_impulse", MACDImpulse),
]

print("=" * 60)
print("EURUSD M15 Strategy Smoke Test")
print("=" * 60)

# --- Step 1: Fetch data ---
print("\n[Step 1] Fetching EURUSD M15 from MT5 (5000 bars)...")
df = fetch_ohlcv("EURUSD", "M15", n_bars=5000)

if df is None or df.empty:
    print("ERROR: fetch_ohlcv returned None or empty DataFrame. Cannot proceed.")
    print("  Possible reasons:")
    print("  - MT5 is not running and not configured in env")
    print("  - EURUSD not available on this broker server")
    sys.exit(1)

print(f"  Got {len(df)} bars: {df.index[0]} -> {df.index[-1]}")

# Check data quality
from data.validator import validate
report = validate(df, symbol="EURUSD", timeframe="M15")
if not report.is_valid:
    print(f"  WARNING: data validation issues: {report.issues}")
else:
    print(f"  Data validation: OK")

# --- Step 2: Run backtests ---
print("\n[Step 2] Running backtests for each strategy...")
print("-" * 60)

be = BacktestEngine()
results = {}

for name, cls in STRATEGIES:
    params = dict(cls.default_params)
    print(f"\n--- {name} ({cls.__name__}) ---")
    print(f"  default_symbol={cls.meta.default_symbol}")
    print(f"  asset_class={cls.meta.asset_class}")
    print(f"  required_timeframes={cls.meta.required_timeframes}")
    print(f"  params keys: {sorted(params.keys())}")

    try:
        r = be.run(df, cls, params, timeframe="M15", symbol="EURUSD")
        results[name] = {
            "class": cls.__name__,
            "num_trades": len(r.trades),
            "win_rate": r.win_rate,
            "error": None,
        }
        if r.trades:
            win_reasons = {}
            for t in r.trades:
                win_reasons[t.exit_reason] = win_reasons.get(t.exit_reason, 0) + 1
            print(f"  RESULT: {len(r.trades)} trades, win_rate={r.win_rate:.1%}")
            print(f"  Exits: {win_reasons}")
        else:
            print(f"  RESULT: 0 trades (no signals generated)")
    except Exception as exc:
        results[name] = {
            "class": cls.__name__,
            "num_trades": None,
            "win_rate": None,
            "error": str(exc),
        }
        print(f"  ERROR: {type(exc).__name__}: {exc}")

# --- Summary ---
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"{'Strategy':<25} {'Class':<22} {'Trades':>7} {'Win%':>7} {'Status'}")
print("-" * 60)

success = 0
fail = 0
for name, info in results.items():
    if info["error"]:
        print(f"{name:<25} {info['class']:<22} {'---':>7} {'---':>7} FAIL: {info['error'][:60]}")
        fail += 1
    else:
        wr = f"{info['win_rate']:.1%}" if info["win_rate"] is not None else "---"
        trades = str(info["num_trades"]) if info["num_trades"] is not None else "---"
        print(f"{name:<25} {info['class']:<22} {trades:>7} {wr:>7} OK")
        success += 1

print("-" * 60)
print(f"Total: {success + fail}  Succeeded: {success}  Failed: {fail}")
if fail:
    sys.exit(1)
