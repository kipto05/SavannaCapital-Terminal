# -*- coding: utf-8 -*-
"""Verify the state of patches: base.py, backtest_engine.py, momentum_reversion.py, engine_loop.py."""
import pathlib

patches = [
    ("base.py required_timeframes", "required_timeframes", "strategies/base.py"),
    ("engine _resample helper", "_resample", "quant/backtest_engine.py"),
    ("engine multi-TF builder", "req_tfs = getattr", "quant/backtest_engine.py"),
    ("momentum H1 required", "required_timeframes", "strategies/momentum_reversion.py"),
    ("live engine multi-TF", 'req = getattr(getattr(instance', "engine/engine_loop.py"),
]

for label, needle, fpath in patches:
    with open(fpath, "r", encoding="utf-8") as f:
        present = needle in f.read()
    status = "OK" if present else "MISSING"
    print(f"[{status}] {label} ({fpath})")
