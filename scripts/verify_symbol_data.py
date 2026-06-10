"""scripts/verify_symbol_data.py — check which JustMarkets symbols have real M1/M5 data
so we can curate the symbol pool precisely. Reads from .env for MT5 credentials.
"""
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8")

import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone

# -- bootstrap path so we can use config (which now loads .env) --
root = __import__("pathlib").Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# Load .env so MT5 creds are in os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(root / ".env")
except ImportError:
    pass

# -- init MT5 (attach to running terminal, no credentials = attach mode) --
if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    sys.exit(1)

try:
    import os
    login = int(os.environ.get("MT5_LOGIN", 0))
    server = os.environ.get("MT5_SERVER", "")
    if login and server:
        mt5.initialize(login=login, password=os.environ.get("MT5_PASSWORD", ""),
                       server=server)
except Exception:
    pass

# Candidate lists pulled from the full listing
SYMBOLS_TO_CHECK = [
    # ── Commodities / Metals ─────────────────────────────────────────────
    "XAUUSD.m", "XAGEUR.m", "XAUAUD.m", "XAUEUR.m",
    "WTI.m", "BRENT.m", "XNGUSD.m",
    "XPDUSD.m", "XPTUSD.m",
    # ── Crypto (USD pairs — JustMarkets full list) ──────────────────────
    "ADAUSD.m", "AVAXUSD.m", "BCHUSD.m",
    "BTCUSD.m", "DOGEUSD.m", "DOTUSD.m", "ETHUSD.m",
    "LINKUSD.m", "LTCUSD.m", "MATICUSD.m", "SOLUSD.m",
    "TRXUSD.m", "UNIUSD.m", "XLMUSD.m", "XRPUSD.m",
    "BTCEUR.m", "BTCGBP.m",
    # ── Forex majors ───────────────────────────────────────────────────
    "EURUSD.m", "GBPUSD.m", "USDJPY.m", "AUDUSD.m", "USDCHF.m",
    "NZDUSD.m",
    # ── Forex crosses ──────────────────────────────────────────────────
    "EURGBP.m", "EURJPY.m", "GBPJPY.m", "AUDJPY.m",
    "EURAUD.m", "GBPAUD.m", "EURCHF.m", "GBPCHF.m",
    "AUDCAD.m", "AUDNZD.m", "NZDCAD.m", "NZDCHF.m",
    "CADCHF.m", "CADJPY.m", "CHFJPY.m",
    "EURCAD.m", "EURNZD.m", "GBPNZD.m",
    "EURSEK.m", "USDSEK.m", "EURHUF.m", "USDHUF.m",
    "USDMXN.m", "USDPLN.m", "USDZAR.m",
    # ── CFDs / Indices (JustMarkets uses .std) ──────────────────────────
    "US30.std", "US500.std", "US100.std", "UK100.std",
    "DE40.std", "FR40.std", "JP225.std", "AU200.std",
    "SHA50.std", "EU50.std", "ES35.std", "SG20.std", "CH50.std",
]

now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=6)  # must have ≥6h of M1 data

print(f"Forex window check: {cutoff.isoformat()} → {now.isoformat()}")
print()
print(f"{'Symbol':<20} {'Description':<50} {'M1 bars':>8} {'Last bar':>25}  Data")
print("-" * 110)

no_data = []
for sym in SYMBOLS_TO_CHECK:
    si = mt5.symbol_info(sym)
    if si is None:
        print(f"{sym:<20} {'[not found in terminal]':<50}")
        no_data.append(sym)
        continue
    desc = (si.description or "").strip()[:49]
    try:
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, cutoff, now)
    except Exception as exc:
        print(f"{sym:<20} {desc:<50}  error: {exc}")
        no_data.append(sym)
        continue
    if rates is None or len(rates) == 0:
        print(f"{sym:<20} {desc:<50} {'0':>8} {'-':>25}  ✗ NO DATA")
        no_data.append(sym)
    else:
        last_ts = datetime.fromtimestamp(rates[-1][0], tz=timezone.utc)
        print(f"{sym:<20} {desc:<50} {len(rates):>8} {last_ts.isoformat():>25}  ✓")

print()
print(f"--- Summary ---")
ok = [s for s in SYMBOLS_TO_CHECK if s not in no_data]
bad = [s for s in SYMBOLS_TO_CHECK if s in no_data]
print(f"DATA OK:   {len(ok)}")
print(f"NO DATA:   {len(bad)} → {bad}")

mt5.shutdown()
