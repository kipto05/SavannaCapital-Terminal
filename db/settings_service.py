"""
db/settings_service.py — DB-backed config overrides.

Everything the dashboard changes is persisted in the platform_settings table.
The config/settings.py values are defaults; this service reads the DB first and
falls back to config defaults for anything not overridden.

Key format: "category.field_name"
Examples: "risk.risk_per_trade", "dashboard.recent_trades_count"
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from config.settings import config
from db.models import PlatformSetting

log = logging.getLogger(__name__)


class SettingsService:
    """
    Central access point for all platform settings.

    Reads from DB first, falls back to config defaults.
    Dashboard writes come here. Engine reads come here.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Single key operations ────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        Look up a single setting by key. Returns DB value if present,
        otherwise returns the provided default.
        """
        row = self.db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if row is None:
            return default
        return self._coerce(row.value, row.value_type)

    def set(
        self,
        key: str,
        value: Any,
        description: str = "",
        value_type: str = "str",
        updated_by: str = "user",
    ) -> None:
        """
        Upsert a single key=value pair into platform_settings.
        """
        row = self.db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if row is None:
            row = PlatformSetting(key=key, value=self._serialize(value, value_type),
                                   value_type=value_type, description=description,
                                   updated_by=updated_by)
            self.db.add(row)
        else:
            row.value = self._serialize(value, value_type)
            row.value_type = value_type
            if description:
                row.description = description
            row.updated_by = updated_by
        self.db.flush()
        log.info("Setting updated: key=%s by=%s", key, updated_by)

    # ── Bulk operations ──────────────────────────────────────────────────────

    def get_category(self, category: str) -> dict[str, Any]:
        """
        Return all settings whose key starts with "category." as a flat dict.
        Example: get_category("risk") → {"risk_per_trade": 0.01, "max_daily_drawdown": 0.03, ...}
        """
        prefix = f"{category}."
        rows = (
            self.db.query(PlatformSetting)
            .filter(PlatformSetting.key.startswith(prefix))
            .all()
        )
        result: dict[str, Any] = {}
        for row in rows:
            field = row.key[len(prefix):]
            result[field] = self._coerce(row.value, row.value_type)
        return result

    def set_category(
        self, category: str, values: dict[str, Any], updated_by: str = "user"
    ) -> None:
        """
        Bulk upsert all keys in "category.*" format.
        """
        for field, value in values.items():
            key = f"{category}.{field}"
            value_type = self._infer_type(value)
            self.set(key, value, value_type=value_type, updated_by=updated_by)

    # ── Effective config helpers ─────────────────────────────────────────────

    def get_effective_risk_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.risk defaults."""
        defaults = {
            "risk_per_trade": config.risk.risk_per_trade,
            "max_daily_drawdown": config.risk.max_daily_drawdown,
            "max_total_drawdown": config.risk.max_total_drawdown,
            "max_open_trades": config.risk.max_open_trades,
            "max_lot_size": config.risk.max_lot_size,
            "min_lot_size": config.risk.min_lot_size,
            "lot_step": config.risk.lot_step,
        }
        db_overrides = self.get_category("risk")
        defaults.update(db_overrides)
        return defaults

    def get_effective_sltp_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.sltp defaults."""
        defaults = {
            "atr_period": config.sltp.atr_period,
            "sl_atr_mult_trending": config.sltp.sl_atr_mult_trending,
            "sl_atr_mult_ranging": config.sltp.sl_atr_mult_ranging,
            "sl_atr_mult_volatile": config.sltp.sl_atr_mult_volatile,
            "tp1_rr_trending": config.sltp.tp1_rr_trending,
            "tp2_rr_trending": config.sltp.tp2_rr_trending,
            "tp1_rr_ranging": config.sltp.tp1_rr_ranging,
            "tp2_rr_ranging": config.sltp.tp2_rr_ranging,
            "tp1_rr_volatile": config.sltp.tp1_rr_volatile,
            "tp2_rr_volatile": config.sltp.tp2_rr_volatile,
            "tp1_close_pct": config.sltp.tp1_close_pct,
            "trail_activate_rr": config.sltp.trail_activate_rr,
            "trail_atr_mult": config.sltp.trail_atr_mult,
            "min_rr": config.sltp.min_rr,
            "atr_pct_ranging_thresh": config.sltp.atr_pct_ranging_thresh,
            "atr_pct_volatile_thresh": config.sltp.atr_pct_volatile_thresh,
        }
        db_overrides = self.get_category("sltp")
        defaults.update(db_overrides)
        return defaults

    def get_effective_dashboard_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.dashboard defaults."""
        defaults = {
            "host": config.dashboard.host,
            "port": config.dashboard.port,
            "recent_trades_count": config.dashboard.recent_trades_count,
            "equity_curve_max_points": config.dashboard.equity_curve_max_points,
            "heartbeat_stale_seconds": config.dashboard.heartbeat_stale_seconds,
            "poll_interval_ms": config.dashboard.poll_interval_ms,
            "session_cookie_name": config.dashboard.session_cookie_name,
            "cors_origins": config.dashboard.cors_origins,
        }
        db_overrides = self.get_category("dashboard")
        defaults.update(db_overrides)
        return defaults

    def get_effective_engine_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.engine defaults."""
        defaults = {
            "poll_interval_seconds": config.engine.poll_interval_seconds,
            "mode": config.engine.mode,
            "snapshot_interval_seconds": config.engine.snapshot_interval_seconds,
        }
        db_overrides = self.get_category("engine")
        defaults.update(db_overrides)
        return defaults

    def get_effective_ml_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.ml defaults."""
        defaults = {
            "feature_window": config.ml.feature_window,
            "train_test_split": config.ml.train_test_split,
            "cv_folds": config.ml.cv_folds,
            "default_model_type": config.ml.default_model_type,
            "n_estimators": config.ml.n_estimators,
            "max_depth": config.ml.max_depth,
            "min_samples_split": config.ml.min_samples_split,
            "prediction_threshold": config.ml.prediction_threshold,
            "retrain_after_n_trades": config.ml.retrain_after_n_trades,
        }
        db_overrides = self.get_category("ml")
        defaults.update(db_overrides)
        return defaults

    def get_effective_backtest_config(self) -> dict[str, Any]:
        """Merge DB overrides onto config.backtest defaults."""
        defaults = {
            "default_initial_equity": config.backtest.default_initial_equity,
            "default_risk_per_trade": config.backtest.default_risk_per_trade,
            "min_trades_for_validity": config.backtest.min_trades_for_validity,
            "warmup_bars": config.backtest.warmup_bars,
            "significance_threshold": config.backtest.significance_threshold,
            "max_jobs_concurrent": config.backtest.max_jobs_concurrent,
        }
        db_overrides = self.get_category("backtest")
        defaults.update(db_overrides)
        return defaults

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _coerce(value: str, value_type: str) -> Any:
        """Convert stored string value back to its Python type."""
        if value is None:
            return None
        try:
            if value_type == "int":
                return int(value)
            if value_type == "float":
                return float(value)
            if value_type == "bool":
                return value.lower() in ("true", "1", "yes")
            if value_type == "json":
                import json
                return json.loads(value)
            return value  # str default
        except (ValueError, TypeError) as exc:
            log.warning("Setting coerce failed: type=%s value=%r error=%s", value_type, value, exc)
            return value

    @staticmethod
    def _serialize(value: Any, value_type: str) -> str:
        """Convert Python value to string for storage."""
        if value is None:
            return ""
        if value_type == "json":
            import json
            return json.dumps(value)
        return str(value)

    @staticmethod
    def _infer_type(value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, (dict, list)):
            return "json"
        return "str"
