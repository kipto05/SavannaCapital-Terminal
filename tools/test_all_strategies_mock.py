#!/usr/bin/env python3
"""Mock-data test for all strategies (strategies + strategies_2).

Generates synthetic M1 data and resamples to required timeframes, runs
walk-forward for each strategy, and reports signals produced.
Also tests ML gate filtering for a couple of strategies.
"""
import sys, logging, time
from pathlib import Path
import numpy as np, pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("test_all")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all strategy classes
from strategies.registry import StrategyRegistry as OldReg
old_reg = OldReg()
old_classes = list(old_reg.classes.values())

from strategies_2 import GoldScalp, VolatilityBreakout, MomentumFlip, BTCEmaCross
new_classes = [GoldScalp, VolatilityBreakout, MomentumFlip, BTCEmaCross]

# Combine, dedup by class name
all_strat_map = {cls.__name__: cls for cls in old_classes + new_classes}
all_strategies = list(all_strat_map.values())

# Stub predictor for ML gate tests
class StubPredictor:
    def __init__(self, prob, version="stub"):
        self.prob = float(prob)
        self.version = version
        self.is_ready = True
    def predict_proba(self, X):
        n = X.shape[0]
        return np.tile([1.0-self.prob, self.prob], (n,1))

# Access to the global ML gate
from strategies_2.ml_gate import default_ml_gate

# Symbol -> typical price scale and volatility
SYMBOL_INFO = {
    "XAUUSD": {"price": 2000.0, "vol": 0.0005},
    "BTCUSD": {"price": 28000.0, "vol": 0.002},
    "EURUSD": {"price": 1.08, "vol": 0.0005},
    "GBPUSD": {"price": 1.27, "vol": 0.0006},
    "AAPL":   {"price": 170.0, "vol": 0.002},
    "TSLA":   {"price": 250.0, "vol": 0.003},
    "XAGUSD": {"price": 25.0, "vol": 0.001},
    "DEFAULT": {"price": 100.0, "vol": 0.001},
}

def get_symbol_scale(symbol):
    info = SYMBOL_INFO.get(symbol, SYMBOL_INFO["DEFAULT"])
    return info["price"], info["vol"]

# Generate base M1 data (deterministic per symbol)
def generate_m1_data(symbol, n_bars=2000, seed_offset=0):
    start_price, vol = get_symbol_scale(symbol)
    rng = np.random.default_rng(seed=abs(hash(symbol)+seed_offset) % (2**32))
    rets = rng.normal(0.0, vol, n_bars)
    close = start_price * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.0005, n_bars)))
    low = close * (1 - np.abs(rng.normal(0, 0.0005, n_bars)))
    open = np.roll(close, 1); open[0] = close[0]
    volume = rng.integers(50, 500, n_bars).astype(float)
    start_date = "2024-01-01 00:00:00"
    idx = pd.date_range(start=start_date, periods=n_bars, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "open": open,
        "high": high,
        "low": low,
        "close": close,
        "tick_volume": volume,
    }, index=idx)
    return df

# Resample to higher timeframe
def resample(df, timeframe):
    if timeframe == "M1":
        return df.copy()
    rule = {"M5":"5min","M15":"15min","H1":"60min"}[timeframe]
    df_resampled = df.resample(rule, label='left', closed='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum',
    }).dropna()
    return df_resampled

# Estimate minimal bars required for a strategy
def required_bars(strat):
    p = strat.default_params
    periods = [v for k,v in p.items() if 'period' in k.lower() and isinstance(v, int)]
    return max(periods) + 50 if periods else 100

# Walk-forward runner with proper multi-tf alignment by timestamp
def walk_forward(strat, data_dict, warmup=None):
    if warmup is None:
        warmup = required_bars(strat)
    tf = strat.timeframe
    df_tf = data_dict.get(tf)
    if df_tf is None or len(df_tf) < warmup:
        return [], 0
    signals = []
    blocked = 0
    for i in range(warmup, len(df_tf)+1):
        current_ts = df_tf.index[i-1]
        sub_data = {}
        needed_tfs = [tf] + (strat.meta.required_timeframes or [])
        for needed_tf in needed_tfs:
            df_needed = data_dict.get(needed_tf)
            if df_needed is None:
                sub_data = None
                break
            sub = df_needed[df_needed.index <= current_ts]
            if len(sub) < 2:
                sub_data = None
                break
            sub_data[needed_tf] = sub
        if sub_data is None:
            continue
        try:
            sig = strat.generate_signal(sub_data)
        except Exception as exc:
            log.warning("Strategy %s error at bar %d: %s", strat.meta.name, i, exc)
            continue
        if sig is not None:
            signals.append((i, sig))
        else:
            if strat.params.get("ml_enabled", False):
                blocked += 1
    return signals, blocked

# Main test
def main():
    print("\n" + "="*80)
    print(" Testing all strategies with synthetic M1 data")
    print("="*80)
    # Group strategies by symbol
    symbol_to_strats = {}
    for strat in all_strategies:
        sym = strat.meta.default_symbol or ""
        symbol_to_strats.setdefault(sym, []).append(strat)

    # Generate base M1 data per symbol
    symbol_data_m1 = {}
    for sym in symbol_to_strats.keys():
        df_m1 = generate_m1_data(sym, n_bars=20000, seed_offset=0)
        symbol_data_m1[sym] = df_m1

    summary = []
    for strat in all_strategies:
        meta = strat.meta
        sym = meta.default_symbol
        df_m1 = symbol_data_m1.get(sym)
        if df_m1 is None:
            log.warning("No M1 data for %s, skipping %s", sym, meta.name)
            continue
        # Determine needed timeframes
        tfs_needed = set()
        if meta.typical_timeframes:
            tfs_needed.add(meta.typical_timeframes[0])
        if hasattr(strat, 'timeframe') and strat.timeframe:
            tfs_needed.add(strat.timeframe)
        tfs_needed.update(meta.required_timeframes or [])
        if not tfs_needed:
            tfs_needed = {"M1"}
        # Build data_dict
        data_dict = {}
        for tf in tfs_needed:
            if tf == "M1":
                data_dict[tf] = df_m1.copy()
            else:
                data_dict[tf] = resample(df_m1, tf)
        # Instantiate strategy
        tf_primary = next(iter(tfs_needed))
        instance = strat(symbol=sym, timeframe=tf_primary)
        warmup = required_bars(instance)
        if warmup >= len(data_dict[tf_primary]):
            log.warning("Insufficient data for %s: need >= %d bars, have %d", meta.name, warmup, len(data_dict[tf_primary]))
            continue
        signals, blocked = walk_forward(instance, data_dict, warmup=warmup)
        longs = sum(1 for _, s in signals if s.side.value == "BUY")
        shorts = len(signals) - longs
        print(f"\nStrategy: {meta.name} ({meta.label})")
        print(f"  Symbol: {sym}, Primary TF: {tf_primary}")
        print(f"  Bars processed: {len(data_dict[tf_primary])}, warmup={warmup}")
        print(f"  Signals: {len(signals)} ({longs} long / {shorts} short), ML-blocks: {blocked}")
        if signals:
            print("  Sample signals (first 3):")
            for bar_idx, sig in signals[:3]:
                ts = df_m1.index[bar_idx-1] if bar_idx-1 < len(df_m1) else "?"
                print(f"    bar {bar_idx} ({ts}): {sig.side.value} entry={sig.entry:.4f} sl={sig.sl:.4f} tp={sig.tp:.4f} conf={sig.confidence:.2f}")
        else:
            print("  No signals generated.")
        summary.append({
            "strategy": meta.name,
            "symbol": sym,
            "timeframe": tf_primary,
            "bars": len(data_dict[tf_primary]),
            "signals": len(signals),
            "blocked": blocked,
        })

    # ML gate filtering tests
    print("\n" + "="*80)
    print(" ML Gate Filtering Tests")
    print("="*80)
    test_cases = [
        ("BTCEmaCross", BTCEmaCross, {"ml_enabled": True, "ml_min_probability": 0.55}),
        ("GoldScalp", GoldScalp, {"ml_enabled": True, "ml_min_probability": 0.55}),
    ]
    gate = default_ml_gate()
    for name, cls, overrides in test_cases:
        meta = cls.meta
        sym = meta.default_symbol
        df_m1 = symbol_data_m1.get(sym)
        if df_m1 is None:
            continue
        tfs_needed = set([meta.typical_timeframes[0]])
        if hasattr(cls, 'timeframe') and cls.timeframe:
            tfs_needed.add(cls.timeframe)
        tfs_needed.update(meta.required_timeframes or [])
        data_dict = {}
        for tf in tfs_needed:
            if tf == "M1": data_dict[tf] = df_m1.copy()
            else: data_dict[tf] = resample(df_m1, tf)
        always_allow = StubPredictor(0.95, "allow-0.95")
        gate.bind(always_allow, model_version="allow-0.95")
        instance = cls(symbol=sym, timeframe=next(iter(tfs_needed)), params=overrides)
        signals_pass, _ = walk_forward(instance, data_dict, warmup=required_bars(instance))
        print(f"\n{name} with ML gate (prob=0.95) -> signals = {len(signals_pass)} (expected all passes)")
        always_deny = StubPredictor(0.05, "deny-0.05")
        gate.bind(always_deny, model_version="deny-0.05")
        signals_deny, _ = walk_forward(instance, data_dict, warmup=required_bars(instance))
        print(f"{name} with ML gate (prob=0.05) -> signals = {len(signals_deny)} (expected blocked)")
        gate.unbind()

    # Summary
    print("\n" + "="*80)
    print(" Summary")
    print("="*80)
    for s in summary:
        print(f"{s['strategy']:25s} symbol={s['symbol']:8s} tf={s['timeframe']:3s} bars={s['bars']:6d} signals={s['signals']:4d} blocked={s['blocked']:4d}")

    # Continuous training pipeline description
    print("\n" + "="*80)
    print(" Continuous Training Pipeline (text summary)")
    print("="*80)
    print("""
Live data flow:
  1. Strategy emits Signal                -> engine queues an order
  2. Order fills                          -> Trade row created
  3. At fill time                         -> engine snapshots features into
                                              db.ml_prediction_history.features_snapshot
                                              with side, confidence, model_version
  4. During signal emission (gate reject case):
                                            -> a negative-outcome row logged (was_correct=False)
                                              so the trainer has both classes
  5. On trade close (sl/tp/timeout)        -> engine back-fills
                                              ml_prediction_history.was_correct
                                              linking prediction -> outcome
  6. Periodic trainer (every N closes or every T minutes):
                                            -> reads new rows since last fit
                                            -> joins with oldest kept history
                                                (rolling window, e.g. 5k samples)
                                            -> refits LogisticRegression / LGBM
                                            -> saves artifact to ml_models/<name>.joblib
                                            -> INSERTs db.ml_models row with is_active=False
  7. On save + validation pass             -> updates db.ml_models.is_active=True
                                            -> engine's Predictor picks up the new
                                                active model on its next _load()
                                            -> hot-swap: default_ml_gate().bind(
                                                   predictor, model_version=...)
                                            -> from next bar, every strategy's gate
                                                uses the new model

Cadence recommendation:
  - Cold start (n_trades < 200):           gate stays UNBOUND (NullPredictor),
                                            signals flow unfiltered
  - Warm (n_trades >= 200):                refit every 100 closes or every 6h
  - Drift guard:                           track rolling 200-trade accuracy on
                                            MLPredictionHistory.was_correct; if
                                            it drops > 5pp vs training accuracy
                                            for 3 consecutive refit cycles, force
                                            a more aggressive refit (drop old data,
                                            shorten window) and emit a notification
""")

    print("\nDone.")

if __name__ == "__main__":
    main()
