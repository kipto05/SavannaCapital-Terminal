# -*- coding: utf-8 -*-
"""
Apply remaining fixes to backtest_engine.py, momentum_reversion.py, engine_loop.py.
"""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

# ── Fix 2b: backtest_engine.py multi-TF builder ────────────────────────────────
print("\n=== Fix 2b: quant/backtest_engine.py ===")
engine_text = Path("quant/backtest_engine.py").read_text(encoding="utf-8")

# Find the sig block - we know it's at line 192-196
old_sig = (
    "# — Generate signal — ONLY past data visible ————————————————————————————————————————\n"
    "# CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}\n"
    "            slice_data = {timeframe: df.iloc[: i + 1].copy()}\n"
    "\n"
    "            signal = None"
)

new_sig = (
    "# -- Build multi-TF data dict (primary + any required trend TFs)\n"
    "            # MomentumReversion needs H1 alongside M15, etc.\n"
    "            slice_data: dict[str, pd.DataFrame] = {timeframe: df.iloc[: i + 1].copy()}\n"
    "            req_tfs = getattr(getattr(strategy, 'meta', None), 'required_timeframes', []) or []\n"
    "            for req_tf in req_tfs:\n"
    "                if req_tf == timeframe:\n"
    "                    continue  # already have primary TF\n"
    "                if req_tf in slice_data:\n"
    "                    continue  # already added by prior iteration\n"
    "                resampled = _resample(df.iloc[: i + 1], req_tf)\n"
    "                if resampled is not None:\n"
    "                    slice_data[req_tf] = resampled\n"
    '                    log.debug(\n'
    '                        "BacktestEngine: added %s (%d bars) for %s",\n'
    '                        req_tf, len(resampled), strategy_class.__name__,\n'
    "                    )\n"
    "                else:\n"
    '                    log.debug(\n'
    '                        "BacktestEngine: could not build %s for %s at bar %d",\n'
    '                        req_tf, strategy_class.__name__, i,\n'
    "                    )\n"
    "\n"
    "            # - Generate signal — ONLY past data visible ——————————————————————————————————\n"
    "            # CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}\n"
    "            slice_data = {timeframe: df.iloc[: i + 1].copy()}\n"
    "\n"
    "            signal = None"
)

if old_sig in engine_text:
    engine_text = engine_text.replace(old_sig, new_sig, 1)
    Path("quant/backtest_engine.py").write_text(engine_text, encoding="utf-8")
    print("Fix 2b OK: multi-TF data builder inserted")
else:
    print("FAIL Fix 2b: old sig block not found")
    # Show what's actually in the file around line 192
    lines = engine_text.split('\n')
    for j in range(190, 200):
        print(f"  L{j+1}: {repr(lines[j])}")

# ── Fix 3: momentum_reversion.py ───────────────────────────────────────────────
print("\n=== Fix 3: strategies/momentum_reversion.py ===")
mr_text = Path("strategies/momentum_reversion.py").read_text(encoding="utf-8")

old_mr = (
    "    version: str = \"1.0.0\"\n"
    "    typical_timeframes: list[str] = field(default_factory=list)\n"
    "    default_symbol: str = \"\""
)

new_mr = (
    "    version: str = \"1.0.0\"\n"
    "    typical_timeframes: list[str] = field(default_factory=list)\n"
    "    required_timeframes: list[str] = field(default_factory=lambda: [\"H1\"])\n"
    "    default_symbol: str = \"\""
)

if old_mr in mr_text:
    mr_text = mr_text.replace(old_mr, new_mr, 1)
    Path("strategies/momentum_reversion.py").write_text(mr_text, encoding="utf-8")
    print("Fix 3 OK: required_timeframes=[H1] added")
else:
    print("FAIL Fix 3: old MR meta block not found")
    lines = mr_text.split('\n')
    for j in range(27, 36):
        print(f"  L{j+1}: {repr(lines[j])}")

# ── Fix 4: engine_loop.py _phase_scan multi-TF bundle ──────────────────────────
print("\n=== Fix 4: engine/engine_loop.py ===")
loop_text = Path("engine/engine_loop.py").read_text(encoding="utf-8")

old_scan = (
    "        instance = cls(default_symbol=symbol, params=params)\n"
    "        try:\n"
    "            signal = instance.generate_signal({timeframe: df})"
)

new_scan = (
    "        instance = cls(default_symbol=symbol, params=params)\n"
    "        # Build multi-TF data bundle (primary + any required secondary TFs)\n"
    "        tf_data: dict[str, pd.DataFrame] = {timeframe: df}\n"
    '        req = getattr(getattr(instance, "meta", None), "required_timeframes", []) or []\n'
    "        for extra_tf in req:\n"
    "            if extra_tf == timeframe or extra_tf in tf_data:\n"
    "                continue\n"
    "            extra_df = _fetch_ohlcv_mt5(symbol, extra_tf, strat.name)\n"
    "            if extra_df is not None and not extra_df.empty:\n"
    "                tf_data[extra_tf] = extra_df\n"
    '                log.debug(\n'
    '                    "Engine: loaded %d bars for %s %s (%s)",\n'
    "                    len(extra_df), symbol, extra_tf, strat.name,\n"
    "                )\n"
    "        try:\n"
    "            signal = instance.generate_signal(tf_data)"
)

if old_scan in loop_text:
    loop_text = loop_text.replace(old_scan, new_scan, 1)
    Path("engine/engine_loop.py").write_text(loop_text, encoding="utf-8")
    print("Fix 4 OK: _phase_scan bundles multi-TF data")
else:
    print("FAIL Fix 4: old scan block not found")
    lines = loop_text.split('\n')
    for j in range(286, 294):
        print(f"  L{j+1}: {repr(lines[j])}")

# ── Verify all fixes ────────────────────────────────────────────────────────────
print("\n=== Verification ===")
patches = [
    ("backtest_engine: req_tfs builder", "req_tfs = getattr(getattr(strategy", "quant/backtest_engine.py"),
    ("momentum: required_timeframes", "required_timeframes: list", "strategies/momentum_reversion.py"),
    ("engine: tf_data bundle", "tf_data: dict[str, pd.DataFrame]", "engine/engine_loop.py"),
]
for label, needle, fpath in patches:
    try:
        present = needle in Path(fpath).read_text(encoding="utf-8")
        print(f"  [{'OK  ' if present else 'MISS'}] {label}")
    except Exception as exc:
        print(f"  [ERR ] {label}: {exc}")

print("\nDone.")
