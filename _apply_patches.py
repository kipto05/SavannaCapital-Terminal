from pathlib import Path
import re

# ─── Fix 2a: insert _resample helper before _eq_helper in backtest_engine.py ──
engine_p = Path("quant/backtest_engine.py")
et = engine_p.read_text(encoding="utf-8")

anchor = "# ── Module-level helpers ────────────────────────────────────────────"

resample_block = '''

_TF_TO_PANDAS_RULE: dict[str, str] = {
    "M1": "1T", "M5": "5T", "M15": "15T", "M30": "30T",
    "H1": "1H", "H4": "4H", "D1": "1D",
}


def _resample(df: pd.DataFrame, target_tf: str) -> pd.DataFrame | None:
    """Resample a lower-TF DataFrame up to target_tf OHLCV bars."""
    rule = _TF_TO_PANDAS_RULE.get(target_tf.upper())
    if rule is None:
        log.warning("_resample: unknown target TF %r", target_tf)
        return None
    needed = {
        "M1": 10, "M5": 10, "M15": 10, "M30": 15,
        "H1": 30, "H4": 30, "D1": 60,
    }.get(target_tf.upper(), 30)
    if len(df) < needed:
        log.debug(
            "_resample: only %d source bars for %s (need %d)",
            len(df), target_tf, needed,
        )
        return None
    try:
        out = df.resample(rule).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            tick_volume=("tick_volume", "sum"),
            volume=("volume", "sum"),
            spread=("spread", "mean"),
        ).dropna(subset=["close"])
        return out if not out.empty else None
    except Exception as exc:
        log.warning("_resample failed %s: %s", target_tf, exc)
        return None

'''

if anchor in et:
    et = et.replace(anchor, resample_block + anchor, 1)
    engine_p.write_text(et, encoding="utf-8")
    print("Fix 2a OK: _resample helper inserted")
else:
    # Try alternate approach: find line by content
    lines = et.split('\n')
    for i, l in enumerate(lines):
        if 'Module-level helpers' in l:
            print(f"Found marker at line {i+1}: {repr(l)}")
            lines.insert(i, resample_block.rstrip('\n'))
            et = '\n'.join(lines)
            engine_p.write_text(et, encoding="utf-8")
            print("Fix 2a OK (inserted at marker line)")
            break
    else:
        print("FAIL Fix 2a: Module-level helpers marker not found")

# ─── Fix 2b: multi-TF data builder in BacktestEngine.run() ────────────────────
et2 = engine_p.read_text(encoding="utf-8")

# The current block (with exact em-dashes from the file):
old_block = (
    '# ── Generate signal — ONLY past data visible ─────────────────────────────────────────\n'
    '# CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}\n'
    '            slice_data = {timeframe: df.iloc[: i + 1].copy()}\n'
    '\n'
    '            signal = None'
)

new_block = (
    '# -- Build multi-TF data dict (primary + any required trend TFs)\n'
    '            # MomentumReversion needs H1 alongside M15, etc.\n'
    '            slice_data: dict[str, pd.DataFrame] = {timeframe: df.iloc[: i + 1].copy()}\n'
    '            req_tfs = getattr(getattr(strategy, "meta", None), "required_timeframes", []) or []\n'
    '            for req_tf in req_tfs:\n'
    '                if req_tf == timeframe:\n'
    '                    continue  # already have primary TF\n'
    '                if req_tf in slice_data:\n'
    '                    continue  # already added by prior iteration\n'
    '                resampled = _resample(df.iloc[: i + 1], req_tf)\n'
    '                if resampled is not None:\n'
    '                    slice_data[req_tf] = resampled\n'
    '                    log.debug(\n'
    '                        "BacktestEngine: added %s (%d bars) for %s",\n'
    '                        req_tf, len(resampled), strategy_class.__name__,\n'
    '                    )\n'
    '                else:\n'
    '                    log.debug(\n'
    '                        "BacktestEngine: could not build %s for %s at bar %d",\n'
    '                        req_tf, strategy_class.__name__, i,\n'
    '                    )\n'
    '\n'
    '            # - Generate signal — ONLY past data visible\n'
    '            # CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}\n'
    '            slice_data = {timeframe: df.iloc[: i + 1].copy()}\n'
    '\n'
    '            signal = None'
)

if old_block in et2:
    et2 = et2.replace(old_block, new_block, 1)
    engine_p.write_text(et2, encoding="utf-8")
    print("Fix 2b OK: multi-TF data builder added")
else:
    print("FAIL Fix 2b: sig block not found in engine")
    # Show actual content around line 192
    lines = et2.split('\n')
    for j in range(190, 200):
        print(f"  Line {j+1}: {repr(lines[j])}")

# ─── Fix 3: MomentumReversion required_timeframes ───────────────────────────────
mr_p = Path("strategies/momentum_reversion.py")
mr_t = mr_p.read_text(encoding="utf-8")

old_mr = '''    version: str = "1.0.0"
    typical_timeframes: list[str] = field(default_factory=list)
    default_symbol: str = ""'''

new_mr = '''    version: str = "1.0.0"
    typical_timeframes: list[str] = field(default_factory=list)
    required_timeframes: list[str] = field(default_factory=lambda: ["H1"])
    default_symbol: str = ""'''

if old_mr in mr_t:
    mr_t = mr_t.replace(old_mr, new_mr, 1)
    mr_p.write_text(mr_t, encoding="utf-8")
    print("Fix 3 OK: MomentumReversion.required_timeframes=[H1]")
else:
    print("FAIL Fix 3: MR meta block not found")
    # Show actual content
    lines = mr_t.split('\n')
    for j in range(26, 36):
        print(f"  Line {j+1}: {repr(lines[j])}")

# ─── Fix 4: Live engine _phase_scan — bundle multi-TF data ──────────────────────
loop_p = Path("engine/engine_loop.py")
lt = loop_p.read_text(encoding="utf-8")

old_scan = (
    '        instance = cls(default_symbol=symbol, params=params)\n'
    '        try:\n'
    '            signal = instance.generate_signal({timeframe: df})'
)

new_scan = (
    '        instance = cls(default_symbol=symbol, params=params)\n'
    '        # Build multi-TF data bundle (primary + any required secondary TFs)\n'
    '        tf_data: dict[str, pd.DataFrame] = {timeframe: df}\n'
    '        req = getattr(getattr(instance, "meta", None), "required_timeframes", []) or []\n'
    '        for extra_tf in req:\n'
    '            if extra_tf == timeframe or extra_tf in tf_data:\n'
    '                continue\n'
    '            extra_df = _fetch_ohlcv_mt5(symbol, extra_tf, strat.name)\n'
    '            if extra_df is not None and not extra_df.empty:\n'
    '                tf_data[extra_tf] = extra_df\n'
    '                log.debug(\n'
    '                    "Engine: loaded %d bars for %s %s (%s)",\n'
    '                    len(extra_df), symbol, extra_tf, strat.name,\n'
    '                )\n'
    '        try:\n'
    '            signal = instance.generate_signal(tf_data)'
)

if old_scan in lt:
    lt = lt.replace(old_scan, new_scan, 1)
    loop_p.write_text(lt, encoding="utf-8")
    print("Fix 4 OK: Live engine _phase_scan multi-TF data bundle")
else:
    print("FAIL Fix 4: _phase_scan call block not found")
    lines = lt.split('\n')
    for j in range(286, 295):
        print(f"  Line {j+1}: {repr(lines[j])}")

print("\nDone.")
