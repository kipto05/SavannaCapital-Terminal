# -*- coding: utf-8 -*-
"""Apply the multi-TF fixes to base.py, backtest_engine.py, momentum_reversion.py, engine_loop.py."""
from pathlib import Path

assert_no_change = lambda f: Path(f).read_text()

# ── Fix 1: Add required_timeframes to StrategyMeta ────────────────────────────
base_p = Path("strategies/base.py")
base_t = base_p.read_text(encoding="utf-8")

old_meta = """    typical_timeframes: list[str] = field(default_factory=list)
    default_symbol: str = ""


@dataclass
class Signal:"""

new_meta = """    typical_timeframes: list[str] = field(default_factory=list)
    default_symbol: str = ""
    required_timeframes: list[str] = field(default_factory=list)  # additional TFs beyond self.timeframe


@dataclass
class Signal:"""

assert old_meta in base_t, "FAIL: StrategyMeta block not found — showing actual:"
print(repr(base_t[base_t.index("default_symbol"):base_t.index("@dataclass")+20]))
base_t = base_t.replace(old_meta, new_meta, 1)
base_p.write_text(base_t, encoding="utf-8")
print("Fix 1 OK: StrategyMeta.required_timeframes added to base.py")

# ── Fix 2: BacktestEngine — resample helper + multi-TF data builder ─────────────
engine_p = Path("quant/backtest_engine.py")
et = engine_p.read_text(encoding="utf-8")

helper_block = '''

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
        log.debug("_resample: only %d source bars for %s (need %d)", len(df), target_tf, needed)
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

marker = '# -- Module-level helpers ------------------------------------------------------'
assert marker in et, f"Module-level helper marker not found in engine"
et = et.replace(marker, helper_block + "\n" + marker, 1)

old_sig = """            # - Generate signal — ONLY past data visible
            # CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}
            slice_data = {timeframe: df.iloc[: i + 1].copy()}

            signal = None"""

new_sig = """            # -- Build multi-TF data dict (primary + any required trend TFs)
            # MomentumReversion needs H1, StochasticTrend needs M5, etc.
            slice_data: dict[str, pd.DataFrame] = {timeframe: df.iloc[: i + 1].copy()}
            req_tfs = getattr(getattr(strategy, 'meta', None), 'required_timeframes', []) or []
            for req_tf in req_tfs:
                if req_tf == timeframe:
                    continue  # already have primary TF
                if req_tf in slice_data:
                    continue  # already added
                resampled = _resample(df.iloc[: i + 1], req_tf)
                if resampled is not None:
                    slice_data[req_tf] = resampled
                    log.debug(
                        "BacktestEngine: added %s data (%d bars) for %s",
                        req_tf, len(resampled), strategy_class.__name__,
                    )
                else:
                    log.debug(
                        "BacktestEngine: could not build %s for %s at bar %d",
                        req_tf, strategy_class.__name__, i,
                    )

            # - Generate signal — ONLY past data visible
            # CLAUDE.md rule: slice_data = {tf: df.iloc[:i+1]}
            signal = None"""

assert old_sig in et, "FAIL: sig block not found in engine"
et = et.replace(old_sig, new_sig, 1)
engine_p.write_text(et, encoding="utf-8")
print("Fix 2 OK: BacktestEngine multi-TF and resample helper added")

# ── Fix 3: MomentumReversion required_timeframes ───────────────────────────────
mr_p = Path("strategies/momentum_reversion.py")
mr_t = mr_p.read_text(encoding="utf-8")

old_mr = """    version: str = "1.0.0"
    typical_timeframes: list[str] = field(default_factory=list)
    default_symbol: str = """""

new_mr = """    version: str = "1.0.0"
    typical_timeframes: list[str] = field(default_factory=list)
    required_timeframes: list[str] = field(default_factory=lambda: ["H1"])
    default_symbol: str = """""

assert old_mr in mr_t, "FAIL: MR meta block not found"
mr_t = mr_t.replace(old_mr, new_mr, 1)
mr_p.write_text(mr_t, encoding="utf-8")
print("Fix 3 OK: MomentumReversion meta required_timeframes=['H1']")

# ── Fix 4: Live engine _phase_scan — bundle multi-TF data ──────────────────────
loop_p = Path("engine/engine_loop.py")
lt = loop_p.read_text(encoding="utf-8")

old_scan = """        instance = cls(default_symbol=symbol, params=params)
        try:
            signal = instance.generate_signal({timeframe: df})"""

new_scan = """        instance = cls(default_symbol=symbol, params=params)
        # Build multi-TF data bundle (primary + any required secondary TFs)
        tf_data: dict[str, pd.DataFrame] = {timeframe: df}
        req = getattr(getattr(instance, 'meta', None), 'required_timeframes', []) or []
        for extra_tf in req:
            if extra_tf == timeframe or extra_tf in tf_data:
                continue
            extra_df = _fetch_ohlcv_mt5(symbol, extra_tf, strat.name)
            if extra_df is not None and not extra_df.empty:
                tf_data[extra_tf] = extra_df
                log.debug(
                    "Engine: loaded %s bars for %s %s (%s)",
                    len(extra_df), symbol, extra_tf, strat.name,
                )
        try:
            signal = instance.generate_signal(tf_data)"""

assert old_scan in lt, "FAIL: _phase_scan call block not found in engine_loop.py"
lt = lt.replace(old_scan, new_scan, 1)
loop_p.write_text(lt, encoding="utf-8")
print("Fix 4 OK: Live engine _phase_scan bundles multi-TF data")

print("\nAll 4 fixes applied.")
