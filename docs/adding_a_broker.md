# Adding a New Broker

All broker-specific knowledge lives in **one place**: `BROKER_MAP` inside
`config/settings.py`. Strategies, ML, DB, and the dashboard never touch broker
names directly — they all use the canonical symbols in `ASSET_POOL`.

Changing broker therefore means: populate one dict entry, verify the symbol
resolution, done.

---

## 1. Start from the actual terminal

Open the broker's MetaTrader 5 terminal, log in, and run:

```powershell
.\venv\Scripts\python.exe scripts\list_mt5_symbols.py
```

This prints every symbol visible to that terminal along with its description.
Save the output — it is the source of truth for step 3.

You need to know:

| Question | Where to find it |
|---|---|
| Does every symbol have a suffix? (`.m`, `.pro`, none …) | The symbol names from `symbols_get()` |
| Are some symbols named differently? (e.g. `GOLD` instead of `XAUUSD`) | The description column alongside the name |
| Do index CFDs use a different suffix class? (e.g. `.std` on JustMarkets) | Look for patterns in the symbol class / description |
| Does the server allow `mt5.initialize()` (attach mode) without credentials? | Try it — see § 5 below |

---

## 2. Decide the active server string

`resolve_broker_symbol()` keys off `config.mt5.server` (read from `.env` key
`MT5_SERVER`). The value must match exactly what the MT5 terminal reports as
the server name.

Example JustMarkets entries already in the map:

```python
"JustMarkets-Demo3":  { ... }
"JustMarkets-Live":   { ... }
```

Add your new broker under whatever `MT5_SERVER` you will put in `.env`:

```python
"YourBroker-ServerName": { ... }
```

If you are not sure yet, use a placeholder — the map has a `"default"` fallback
(empty suffix, no overrides) that passes symbols through unchanged.

---

## 3. Build the broker entry

Add one dict to `BROKER_MAP` in `config/settings.py`:

```python
BROKER_MAP: dict[str, dict] = {
    # ... existing entries ...

    "YourBroker-ServerName": {
        # Suffix appended to every symbol NOT listed in `overrides`.
        # Empty string "" = no suffix (most non-JustMarkets brokers).
        "default_suffix": ".m",          # or "pro", "", etc.

        # Suffixes that should be stripped before `default_suffix` is
        # re-applied.  Makes the resolution idempotent — calling resolve
        # twice on the same symbol is a no-op, not a double-append.
        "strip_suffix": {".m", ".pro"},   # adjust to match your broker

        # Exact overrides for symbols that don't follow the pattern.
        # Keys are CANONICAL names (from ASSET_POOL), values are what the
        # broker's MT5 terminal actually calls them.
        "overrides": {
            # Indices with a different suffix class
            "US30":  "US30.std",
            "US500": "US500.std",
            # Commodity CFDs with non-standard names
            "WTI":   "WTI.m",
            "BRENT": "BRENT.m",
        },
    },
}
```

### Field reference

| Field | Purpose | Required |
|---|---|---|
| `default_suffix` | Appended to canonical names not in `overrides`. Use `""` for brokers with no suffix. | yes |
| `strip_suffix` | Strip these before re-applying `default_suffix`. Prevents double-suffix when a symbol is already qualified. | no (default `set()`) |
| `overrides` | Exact broker name for symbols that break the pattern (different suffix, renamed, exotic). | no (often empty) |

---

## 4. Update ASSET_POOL (if needed)

If the new broker offers **different symbols** than what is already in
`ASSET_POOL`, add them under the appropriate asset class:

```python
ASSET_POOL: dict[str, list[str]] = {
    "crypto": [...],        # canonical names, NO suffix
    "forex": [...],
    "commodity": [...],
    "equity": [...],
    "index":  [...],
}
```

> Rule: **ASSET_POOL is always canonical**. No `.m`, no `.std`, no broker
> decoration of any kind.

---

## 5. Verify MT5 init mode

`data/repository.py::_mt5_init()` tries two modes **in this order**:

1. **Attach mode** — `mt5.initialize()` with no arguments. Picks up the
   already-running terminal. This is the preferred path when the terminal is
   open on your desktop.
2. **Credential mode** — `mt5.initialize(login=…, password=…, server=…)`.
   For headless / automated runs when the terminal UI is not running.

Test both (or whichever applies):

```powershell
# Attach mode (terminal must be open)
.\venv\Scripts\python.exe -c "
import MetaTrader5 as mt5
ok = mt5.initialize()
print('attach ok:', ok)
if ok: print('terminal:', mt5.terminal_info().name)
mt5.shutdown()
"

# Credential mode (terminal can be closed)
.\venv\Scripts\python.exe -c "
import MetaTrader5 as mt5, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))
ok = mt5.initialize(
    login=int(os.environ['MT5_LOGIN']),
    password=os.environ['MT5_PASSWORD'],
    server=os.environ['MT5_SERVER'],
)
print('cred ok:', ok, mt5.last_error())
mt5.shutdown()
"
```

If credential mode fails but attach works (JustMarkets behaviour), the existing
fallback in `_mt5_init()` already handles it — no changes needed.

---

## 6. Verify symbol resolution

Run the following with your new `MT5_SERVER` in `.env`:

```powershell
.\venv\Scripts\python.exe -c "
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL','')
from config.settings import resolve_broker_symbol

server = os.environ['MT5_SERVER']
tests = ['EURUSD', 'XAUUSD', 'US500', 'BTCUSD']  # add broker-specific ones
for sym in tests:
    print(f'{sym:<12} -> {resolve_broker_symbol(sym, server)}')
"
```

Every output must be a real terminal name visible in the broker's MT5. Cross
check against the `list_mt5_symbols.py` output from step 1.

---

## 7. Fetch a test batch

```powershell
.\venv\Scripts\python.exe scripts\fetch_gold_5m_to_db.py
```

Confirm:

- No `No MT5 data` warnings in the log
- Row count in `ohlcv_bars` increases
- `SELECT symbol, timeframe, COUNT(*), MIN(timestamp), MAX(timestamp)
  FROM ohlcv_bars GROUP BY symbol, timeframe;` shows the expected range

---

## 8. Checklist of things NOT to change

| File / area | Change required? |
|---|---|
| `strategies/*.py` | **No** — strategies reference canonical names from `ASSET_POOL` |
| `ml/feature_engineer.py` | **No** — features are price-based, broker-agnostic |
| `ml/trainer.py` | **No** — same |
| `db/models.py` | **No** — DB stores canonical symbols |
| `db/session.py` | **No** |
| `dashboard/routes/*.py` | **Check** — if new routes need new symbols they should still use canonical names |
| `data/repository.py` | **No** — `resolve_broker_symbol()` handles it |
| `config/settings.py` | **Yes** — `BROKER_MAP`, possibly `ASSET_POOL` and `.env` values |

---

## 9. Common pitfalls

| Symptom | Likely cause |
|---|---|
| `copy_rates_range` returns 0 bars | Wrong broker symbol. Check the terminal name with `list_mt5_symbols.py` and update the `overrides` entry. |
| Symbol name has double suffix (e.g. `EURUSD.m.m`) | `strip_suffix` does not include `.m`. Add it. |
| `_sym()` bug (stripping last 2 chars blindly) | You are reading old docs. `_sym()` was removed in favour of `resolve_broker_symbol()`. Delete any remaining references. |
| `mt5.initialize()` returns `False` in attach mode | Terminal not running, or a different MT5 instance is already initialised in the same Python process. Call `mt5.shutdown()` first, or use a fresh process. |
| Credentials init fails but attach works | This is expected on JustMarkets. The fallback handles it — no action needed unless you need headless mode. |
| `.env` values not picked up | `config/settings.py` loads `.env` at import time via `python-dotenv`. Ensure `python-dotenv` is installed and the `.env` is in the project root. |

---

## 10. Example: adding Interactive Brokers (hypothetical)

```python
# 1. Add to .env
MT5_SERVER=YourBroker-Demo
# (or leave blank and use the "default" BROKER_MAP entry with empty suffix)

# 2. Add to BROKER_MAP in config/settings.py
"YourBroker-Demo": {
    "default_suffix": "",       # no suffix on IBKR
    "strip_suffix": set(),      # nothing to strip
    "overrides": {
        # IBKR names gold "GOLD" not "XAUUSD"
        "XAUUSD": "GOLD",
        # IBKR uses .CFD for some indices
        "US500":  "US500.CFD",
    },
},

# 3. Test
.\venv\Scripts\python.exe scripts\fetch_gold_5m_to_db.py
```

Everything else — strategies trading `XAUUSD`, ML features, DB schema — is
unchanged.
