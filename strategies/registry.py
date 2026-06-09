"""strategies/registry.py — DB-backed strategy registry.

Discovers all BaseStrategy subclasses via the strategies package.
Seeds config.default_params into strategy_configs on first run so the
dashboard can read and toggle any installed strategy.

Usage:
from strategies.registry import StrategyRegistry
reg = StrategyRegistry(db)
enabled = reg.get_enabled()
rec = reg.get_by_name("momentum_reversion")
reg.toggle("momentum_reversion")
"""
from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any

from config.settings import config
from db.models import StrategyConfig
from db.session import SessionLocal
from strategies.base import BaseStrategy

log = logging.getLogger(__name__)

# ── Package discovery ───────────────────────────────────────────────────────────

_STRATEGY_PACKAGE = "strategies"
_KNOWN_MODULES: list[str] = [
    "strategies.momentum_reversion",
    "strategies.band_reversion",
    "strategies.stochastic_trend",
    "strategies.session_breakout",
    "strategies.divergence_swing",
    "strategies.vwap_reversion",
    "strategies.macd_impulse",
    "strategies.crypto",
    "strategies.forex",
    "strategies.commodities",
    "strategies.equities",
]


def _discover() -> dict[str, type[BaseStrategy]]:
    """Import all strategy modules and return {name: class}."""
    found: dict[str, type[BaseStrategy]] = {}
    for mod_name in _KNOWN_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError as exc:
            log.debug("Strategy module skip: %s (%s)", mod_name, exc)
            continue
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
                and hasattr(obj, "meta")
                and hasattr(obj, "default_params")
            ):
                key = obj.meta.name
                if key:
                    found[key] = obj
    return found


# ── Registry ────────────────────────────────────────────────────────────────────


class StrategyRecord:
    """In-memory representation of a strategy_config row."""

    def __init__(
        self,
        name: str,
        is_enabled: bool,
        params: dict[str, Any],
        version: str = "1.0.0",
    ) -> None:
        self.name = name
        self.is_enabled = is_enabled
        self.params = params
        self.version = version

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.name.replace("_", " ").title(),
            "is_active": self.is_enabled,
            "version": self.version,
            "params": self.params,
        }


class StrategyRegistry:
    """DB-backed strategy lifecycle manager.

    Guarantees:
    - Every discovered strategy has a row in strategy_configs (seeded on first call).
    - get_enabled() returns only strategies with is_active=True.
    - toggle() flips is_active and persists.
    """

    def __init__(self, db=None) -> None:
        self._db = db
        self._classes: dict[str, type[BaseStrategy]] | None = None

    # ── Discovery ───────────────────────────────────────────────────────────

    @property
    def classes(self) -> dict[str, type[BaseStrategy]]:
        if self._classes is None:
            self._classes = _discover()
        return self._classes

    # ── Internal DB session management ───────────────────────────────────────

    def _session(self):
        """Return the existing db session or open a new one."""
        if self._db is not None:
            return self._db
        return SessionLocal()

    # ── Seed & load ──────────────────────────────────────────────────────────

    def _seed_if_needed(self, db) -> None:
        """Insert rows for any strategy not yet in strategy_configs.

        Populates ALL NOT NULL columns: name, label, symbol, timeframe,
        is_active, params, version.  Without these the INSERT fails and
        no rows are created at all.
        """
        existing = {
            row.name for row in db.query(StrategyConfig.name).all()
        }
        for name, cls in self.classes.items():
            if name not in existing:
                meta = cls.meta
                rec = StrategyConfig(
                    name=name,
                    label=meta.label or name.replace("_", " ").title(),
                    symbol=meta.default_symbol or "",
                    timeframe=meta.typical_timeframes[0] if meta.typical_timeframes else "",
                    is_active=False,
                    params=cls.default_params,
                    version=1,
                )
                db.add(rec)
                log.info(
                    "Strategy seeded: name=%s label=%s",
                    name,
                    rec.label,
                )
        db.flush()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_enabled(self) -> list[StrategyRecord]:
        """Return all currently active strategies."""
        db = self._session()
        try:
            self._seed_if_needed(db)
            rows = (
                db.query(StrategyConfig)
                .filter(StrategyConfig.is_active.is_(True))
                .all()
            )
            return [
                StrategyRecord(
                    name=r.name,
                    is_enabled=r.is_active,
                    params=dict(r.params) if r.params else {},
                    version=str(r.version),
                )
                for r in rows
            ]
        finally:
            if self._db is None:
                db.close()

    def get_all(self) -> list[StrategyRecord]:
        """Return every registered strategy, enabled or not."""
        db = self._session()
        try:
            self._seed_if_needed(db)
            rows = (
                db.query(StrategyConfig).order_by(StrategyConfig.name).all()
            )
            return [
                StrategyRecord(
                    name=r.name,
                    is_enabled=r.is_active,
                    params=dict(r.params) if r.params else {},
                    version=str(r.version),
                )
                for r in rows
            ]
        finally:
            if self._db is None:
                db.close()

    def get_by_name(self, name: str) -> StrategyRecord | None:
        """Return a single strategy record by name key."""
        db = self._session()
        try:
            self._seed_if_needed(db)
            row = (
                db.query(StrategyConfig)
                .filter(StrategyConfig.name == name)
                .first()
            )
            if row is None:
                return None
            cls = self.classes.get(name)
            return StrategyRecord(
                name=row.name,
                is_enabled=row.is_active,
                params=dict(row.params) if row.params else {},
                version=str(row.version),
            )
        finally:
            if self._db is None:
                db.close()

    def toggle(self, name: str) -> StrategyRecord:
        """Flip is_active for *name* and return the updated record."""
        db = self._session()
        try:
            self._seed_if_needed(db)
            row = (
                db.query(StrategyConfig)
                .filter(StrategyConfig.name == name)
                .first()
            )
            if row is None:
                raise ValueError(
                    f"Strategy '{name}' not found — has it been registered?"
                )
            row.is_active = not row.is_active
            db.flush()
            log.info(
                "Strategy toggled: name=%s enabled=%s",
                name,
                row.is_active,
            )
            return StrategyRecord(
                name=row.name,
                is_enabled=row.is_active,
                params=dict(row.params) if row.params else {},
                version=str(row.version),
            )
        finally:
            if self._db is None:
                db.close()

    def update_params(
        self, name: str, params: dict[str, Any]
    ) -> StrategyRecord:
        """Merge *params* into the stored config and return the updated record."""
        db = self._session()
        try:
            self._seed_if_needed(db)
            row = (
                db.query(StrategyConfig)
                .filter(StrategyConfig.name == name)
                .first()
            )
            if row is None:
                raise ValueError(f"Strategy '{name}' not found")
            current = dict(row.params) if row.params else {}
            current.update(params)
            row.params = current
            db.flush()
            log.info(
                "Strategy params updated: name=%s keys=%s",
                name,
                list(params),
            )
            return StrategyRecord(
                name=row.name,
                is_enabled=row.is_active,
                params=dict(row.params) if row.params else {},
                version=str(row.version),
            )
        finally:
            if self._db is None:
                db.close()
