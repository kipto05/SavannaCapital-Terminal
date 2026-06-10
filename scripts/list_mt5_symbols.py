"""scripts/list_mt5_symbols.py — enumerate all symbols available in the JustMarkets terminal
and show which have recent tick/bar data, so we can sync ASSET_POOL with reality.
"""
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
from collections import defaultdict

root = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    sys.exit(1)

print(f"=== Connected to: {mt5.terminal_info().name if mt5.terminal_info() else '?'} ===")

all_syms = mt5.symbols_get()
print(f"Total symbols visible: {len(all_syms)}")
print()

# Raw dump (full names so we can copy/paste)
print("=== FULL SYMBOL LIST ===")
for s in sorted(all_syms, key=lambda x: x.name):
    desc = (s.description or "").strip()
    print(f"  {s.name:20s}  |  {desc[:60]}")
print()

mt5.shutdown()
