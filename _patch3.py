from pathlib import Path


def find_exact_line(filepath, keyword, context=6):
    """Find a line containing keyword, return surrounding lines with exact bytes."""
    lines = Path(filepath).read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if keyword in line:
            start = max(0, i - 2)
            end = min(len(lines), i + context)
            print(f"  -> Found at line {i+1}:")
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                print(f"    {marker} L{j+1}: {repr(lines[j])}")
            return lines, i
    return lines, -1

# ── Fix 2a: backtest_engine.py _resample helper ────────────────────────────────
print("\n=== Fix 2a: quant/backtest_engine.py ===")
engine_lines, marker_idx = find_exact_line("quant/backtest_engine.py", "Module-level helpers")
if marker_idx == -1:
    print("FAIL: Cannot find 'Module-level helpers' marker")
else:
    marker_line = engine_lines[marker_idx]
    print(f"\n  Marker line: {repr(marker_line[:70])}")

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
    # Insert the resample block BEFORE the marker line
    engine_lines.insert(marker_idx, resample_block.rstrip('\n'))
    new_text = "\n".join(engine_lines)
    Path("quant/backtest_engine.py").write_text(new_text, encoding="utf-8")

    # Verify
    verify = Path("quant/backtest_engine.py").read_text(encoding="utf-8")
    if "def _resample(df: pd.DataFrame, target_tf: str)" in verify:
        print("Fix 2a OK: _resample helper inserted")
    else:
        print("FAIL Fix 2a: _resample not found after write")

# ── Fix 2b: backtest_engine.py multi-TF builder ────────────────────────────────
print("\n=== Fix 2b: quant/backtest_engine.py ===")
engine_text = Path("quant/backtest_engine.py").read_text(encoding="utf-8")

lines = engine_text.split('\n')
# Find the sig block by searching for "CLAUDE.md rule: slice_data"
for i, l in enumerate(lines):
    if 'CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}' in l:
        print(f"  Found sig comment at line {i+1}: {repr(l)}")
        # Show surrounding context
        for j in range(i-1, min(len(lines), i+8)):
            print(f"  L{j+1}: {repr(lines[j])}")
        break

# ── Fix 3: momentum_reversion.py ───────────────────────────────────────────────
print("\n=== Fix 3: strategies/momentum_reversion.py ===")
mr_lines, mr_idx = find_exact_line(
    "strategies/momentum_reversion.py", "required_timeframes"
)
if mr_idx != -1:
    print(f"Fix 3 SKIP: already contains required_timeframes at line {mr_idx+1}")
else:
    mr_lines2, t_idx = find_exact_line(
        "strategies/momentum_reversion.py", "typical_timeframes: list"
    )
    if t_idx == -1:
        print("FAIL Fix 3: cannot find typical_timeframes line")
    else:
        # Insert required_timeframes on the line AFTER typical_timeframes
        insert_pos = t_idx + 2  # after typical_timeframes line
        mr_lines2.insert(
            insert_pos,
            '    required_timeframes: list[str] = field(default_factory=lambda: ["H1"])'
        )
        Path("strategies/momentum_reversion.py").write_text(
            "\n".join(mr_lines2), encoding="utf-8"
        )
        verify = Path("strategies/momentum_reversion.py").read_text(encoding="utf-8")
        print(f"Fix 3 {'OK' if 'required_timeframes' in verify else 'FAIL'}: MomentumReversion.meta updated")

# ── Fix 4: engine_loop.py _phase_scan multi-TF bundle ──────────────────────────
print("\n=== Fix 4: engine/engine_loop.py ===")
loop_lines, loop_idx = find_exact_line(
    "engine/engine_loop.py", "instance = cls(default_symbol=symbol, params=params)"
)
if loop_idx == -1:
    print("FAIL Fix 4: cannot find instance = cls")
else:
    # Show the 4-line block: instance/try/signal/except
    for j in range(loop_idx, min(len(loop_lines), loop_idx + 4)):
        print(f"  L{j+1}: {repr(loop_lines[j])}")

    print("\n  NOTE: Fix 4 will need manual byte-level replacement")
    print("  because the file contains em-dash chars that cannot be")
    print("  written reliably from a Python string literal in this encoding.")

print("\nDone.")
