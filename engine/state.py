"""engine/state.py — shared, read-only-ish state between the engine loop and the HTTP layer.

The engine loop (engine_loop.py) updates this on each iteration.
The dashboard routes (engine/routes.py) read from it.
All mutations happen in the engine thread only. Reads happen in the
FastAPI handler thread. We use a plain dict with a threading lock
because the data is small and the access pattern is single-writer,
many-reader.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import date


@dataclass
class EngineState:
    # Lifecycle
    running: bool = False
    started_at: float = field(default_factory=time.time)

    # Last iteration timestamps (unix seconds)
    last_iteration_ts: float = 0.0
    last_snapshot_ts: float = 0.0
    last_quant_trigger_ts: float = 0.0

    # Circuit breaker
    circuit_breaker_tripped: bool = False
    breaker_tripped_at: float = 0.0

    # Daily counters
    today_date: str = ""
    daily_pnl: float = 0.0

    # AI / ML
    last_ai_suggestion_count: int = 0
    last_ml_prediction_count: int = 0

    # Strategy scan stats (reset each iteration)
    last_scan_symbols: list[str] = field(default_factory=list)
    last_scan_signals_generated: int = 0
    last_scan_trades_executed: int = 0

    # MT5
    mt5_connected: bool = False

    def snapshot(self) -> dict:
        """Return a JSON-safe dict for the API."""
        return {
            "running": self.running,
            "started_at_iso": _iso(self.started_at),
            "last_iteration_iso": _iso(self.last_iteration_ts),
            "last_snapshot_iso": _iso(self.last_snapshot_ts),
            "last_quant_trigger_iso": _iso(self.last_quant_trigger_ts),
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "breaker_tripped_at_iso": _iso(self.breaker_tripped_at),
            "today_date": self.today_date,
            "daily_pnl": self.daily_pnl,
            "last_ai_suggestion_count": self.last_ai_suggestion_count,
            "last_ml_prediction_count": self.last_ml_prediction_count,
            "last_scan_symbols": self.last_scan_symbols,
            "last_scan_signals_generated": self.last_scan_signals_generated,
            "last_scan_trades_executed": self.last_scan_trades_executed,
            "mt5_connected": self.mt5_connected,
        }


_lock = threading.Lock()
_state = EngineState()


def get_state() -> EngineState:
    """Return the shared state. Caller must hold the lock for writes."""
    return _state


def update(**kwargs) -> None:
    """Update fields on the shared state from the engine thread."""
    with _lock:
        for k, v in kwargs.items():
            if hasattr(_state, k):
                setattr(_state, k, v)


def snapshot() -> dict:
    """Return a JSON-safe snapshot of the current state."""
    with _lock:
        return _state.snapshot()


def _iso(ts: float) -> str | None:
    if ts <= 0:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
