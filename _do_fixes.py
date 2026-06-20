from pathlib import Path
import re


def rd(f):
    return Path(f).read_text(encoding="utf-8")


def wr(f, t):
    py_compile(f, t)  # safety — but we actually just write first
    Path(f).write_text(t, encoding="utf-8")


def py_compile(f, t):
    """Strip incomplete lines that depend on py_compile, just return."""
    return t


def verify(f):
    """Verify syntax after writes."""
    import py_compile
    try:
        py_compile.compile(f, doraise=True)
        return True, "OK"
    except py_compile.PyCompileError as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────
# 2b  Multi-TF builder in backtest_engine.py run()
# ─────────────────────────────────────────────────────────────────
# Read the 5-line sig block from the file
text_be = rd("quant/backtest_engine.py")
lines_be = text_be.split("\n")

# Locate line with "CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}"
sig_comment_idx = None
for i, line in enumerate(lines_be):
    if "CLAUDE.md rule: slice_data" in line:
        sig_comment_idx = i - 1  # the comment above it
        break

if sig_comment_idx is None:
    for i, line in enumerate(lines_be):
        if "CLAUDE.md rule" in line:
            sig_comment_idx = i
            break

print(f"sig_comment_idx={sig_comment_idx}")
if sig_comment_idx is None:
    print("FAIL 2b: cannot find sig comment")
else:
    # old 5-line block: lines[sig_comment_idx] .. lines[sig_comment_idx+4]
    old5 = "\n".join(lines_be[sig_comment_idx: sig_comment_idx + 5])

    # new 15-line block:
    # line 1 — actual em-dashes from file:
    actual_line = lines_be[sig_comment_idx]  # "# — Generate signal — ONLY past..."
    # build the full new block using Unicode reads from the file
    new15 = actual_line + "\n" + \
        "            # Build multi-TF data dict (primary + any required trend TFs)\n" + \
        "            # MomentumReversion needs H1 alongside M15, etc.\n" + \
        "            slice_data: dict[str, pd.DataFrame] = {timeframe: df.iloc[: i + 1].copy()}\n" + \
        "            req_tfs = getattr(getattr(strategy, 'meta', None), 'required_timeframes', []) or []\n" + \
        "            for req_tf in req_tfs:\n" + \
        "                if req_tf == timeframe:\n" + \
        "                    continue  # already have primary TF\n" + \
        "                if req_tf in slice_data:\n" + \
        "                    continue  # already added by prior iteration\n" + \
        "                resampled = _resample(df.iloc[: i + 1], req_tf)\n" + \
        "                if resampled is not None:\n" + \
        "                    slice_data[req_tf] = resampled\n" + \
        '                    log.debug(\n' + \
        '                        "BacktestEngine: added %s (%d bars) for %s",\n' + \
        '                        req_tf, len(resampled), strategy_class.__name__,\n' + \
        "                    )\n" + \
        "                else:\n" + \
        '                    log.debug(\n' + \
        '                        "BacktestEngine: could not build %s for %s at bar %d",\n' + \
        '                        req_tf, strategy_class.__name__, i,\n' + \
        "                    )\n" + \
        "\n" + \
        "            slice_data = {timeframe: df.iloc[: i + 1].copy()}\n" + \
        "\n" + \
        "            signal = None"

    if old5 in text_be:
        new_text = text_be.replace(old5, new15, 1)
        Path("quant/backtest_engine.py").write_text(new_text, encoding="utf-8")
        ok, msg = verify("quant/backtest_engine.py")
        print(f"2b {'OK' if ok else 'SYN ERR: ' + msg}")
        print(f"   _resample inserted: {'def _resample' in new_text}")
        print(f"   req_tfs inserted: {'req_tfs = getattr' in new_text}")
    else:
        print("FAIL 2b: old 5-line block not in file")
        for j in range(sig_comment_idx, sig_comment_idx + 6):
            print(f"  L{j+1}: {repr(lines_be[j])}")

# ─────────────────────────────────────────────────────────────────
# 3  MomentumReversion required_timeframes
# ─────────────────────────────────────────────────────────────────
text_mr = rd("strategies/momentum_reversion.py")
lines_mr = text_mr.split("\n")

ds_idx = None
for i, line in enumerate(lines_mr):
    if 'default_symbol: str = ""' in line:
        ds_idx = i
        break

print(f"\nds_idx={ds_idx}")
if ds_idx is None:
    print("FAIL 3: default_symbol line not found")
else:
    insert = '    required_timeframes: list[str] = field(default_factory=lambda: ["H1"])'
    new_lines_mr = lines_mr[:ds_idx] + [insert] + lines_mr[ds_idx:]
    Path("strategies/momentum_reversion.py").write_text("\n".join(new_lines_mr), encoding="utf-8")
    ok, msg = verify("strategies/momentum_reversion.py")
    print(f"3 {'OK' if ok else 'SYN ERR: ' + msg}")
    v = rd("strategies/momentum_reversion.py")
    print(f"   H1 present: {'H1' in v}")

# ─────────────────────────────────────────────────────────────────
# 4  Live engine _phase_scan multi-TF bundle
# ─────────────────────────────────────────────────────────────────
text_loop = rd("engine/engine_loop.py")
lines_loop = text_loop.split("\n")

inst_idx = None
for i, line in enumerate(lines_loop):
    if "instance = cls(default_symbol" in line:
        inst_idx = i
        break

print(f"\ninst_idx={inst_idx}")
if inst_idx is None:
    print("FAIL 4: instance = cls line not found")
else:
    # the 3-line block: instance/try/signal
    old3 = "\n".join(lines_loop[inst_idx: inst_idx + 3])
    new_multi = (
        lines_loop[inst_idx] + "\n" +
        "        # Build multi-TF data bundle (primary + any required secondary TFs)\n" +
        "        tf_data: dict[str, pd.DataFrame] = {timeframe: df}\n" +
        '        req = getattr(getattr(instance, "meta", None), "required_timeframes", []) or []\n' +
        "        for extra_tf in req:\n" +
        "            if extra_tf == timeframe or extra_tf in tf_data:\n" +
        "                continue\n" +
        "            extra_df = _fetch_ohlcv_mt5(symbol, extra_tf, strat.name)\n" +
        "            if extra_df is not None and not extra_df.empty:\n" +
        "                tf_data[extra_tf] = extra_df\n" +
        '                log.debug(\n' +
        '                    "Engine: loaded %d bars for %s %s (%s)",\n' +
        "                    len(extra_df), symbol, extra_tf, strat.name,\n" +
        "                )\n" +
        "        try:\n" +
        "            signal = instance.generate_signal(tf_data)"
    )
    if old3 in text_loop:
        new_loop = text_loop.replace(old3, new_multi, 1)
        Path("engine/engine_loop.py").write_text(new_loop, encoding="utf-8")
        ok, msg = verify("engine/engine_loop.py")
        print(f"4 {'OK' if ok else 'SYN ERR: ' + msg}")
        v = rd("engine/engine_loop.py")
        print(f"   tf_data present: {'tf_data' in v}")
    else:
        print("FAIL 4: old 3-line block not in file")
        for j in range(inst_idx, inst_idx + 4):
            print(f"  L{j+1}: {repr(lines_loop[j])}")

# ─────────────────────────────────────────────────────────────────
# 5  Verification summary
# ─────────────────────────────────────────────────────────────────
print("\n=== Summary ===")
checks = [
    ("base: required_timeframes", "strategies/base.py", "required_timeframes"),
    ("be: _resample helper",     "quant/backtest_engine.py", "def _resample(df: pd.DataFrame, target_tf: str)"),
    ("be: req_tfs builder",      "quant/backtest_engine.py", "req_tfs = getattr(getattr(strategy"),
    ("mr: required_timeframes",  "strategies/momentum_reversion.py", "required_timeframes"),
    ("loop: tf_data bundle",     "engine/engine_loop.py", "tf_data: dict[str, pd.DataFrame]"),
]
import py_compile
all_ok = True
for label, fpath, needle in checks:
    t = rd(fpath)
    present = needle in t
    try:
        py_compile.compile(fpath, doraise=True)
        syn = "SYN OK"
    except Exception as e:
        syn = f"SYN ERR: {e}"
        all_ok = False
    status = f"{'[OK]' if present else '[MISS]'} {syn}"
    print(f"  {status}  {label}")
    if not present:
        all_ok = False

print(f"\n{'ALL OK' if all_ok else 'SOME FAILURES'}")
