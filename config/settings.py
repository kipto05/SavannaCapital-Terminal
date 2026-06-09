"""
config/settings.py — single source of truth for all platform configuration.
Every number, threshold, and path reads from here. Nothing is hardcoded elsewhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Asset pools and timeframe lists ───────────────────────────────────────────
# Extend these dicts to add new symbols or timeframes. No strategy code changes needed.

ASSET_POOL: dict[str, list[str]] = {
    "crypto": ["BTCUSD", "ETHUSD", "BNBUSD", "XRPUSD", "SOLUSD"],
    "forex": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"],
    "commodity": ["XAUUSD", "XAGUSD", "USOIL", "UKOIL"],
    "equity": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL"],
}

TIMEFRAMES_BY_ASSET: dict[str, list[str]] = {
    "crypto": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
    "forex": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
    "commodity": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
    "equity": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
}


# ── Config dataclasses ─────────────────────────────────────────────────────────

@dataclass
class DatabaseConfig:
    url: str = "sqlite:///./tradingwf.db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    echo_sql: bool = False


@dataclass
class AuthConfig:
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12
    default_admin_user: str = "admin"
    default_admin_password: str = "changeme123"


@dataclass
class MT5Config:
    path: str = r"C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe"
    login: int = 0
    password: str = ""
    server: str = ""
    timeout: int = 60000


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.01
    max_daily_drawdown: float = 0.03
    max_total_drawdown: float = 0.10
    max_open_trades: int = 5
    max_lot_size: float = 1.0
    min_lot_size: float = 0.01
    lot_step: float = 0.01
    point_sizes: dict = field(default_factory=lambda: {
        "EURUSD": 0.00001, "GBPUSD": 0.00001, "USDJPY": 0.001,
        "XAUUSD": 0.01, "XAGUSD": 0.001,
        "BTCUSD": 0.01, "ETHUSD": 0.01,
        "AAPL": 0.01, "TSLA": 0.01, "NVDA": 0.01,
        "USOIL": 0.01, "UKOIL": 0.01,
    })


@dataclass
class SLTPConfig:
    atr_period: int = 14
    sl_atr_mult_trending: float = 1.2
    sl_atr_mult_ranging: float = 1.8
    sl_atr_mult_volatile: float = 2.5
    tp1_rr_trending: float = 1.0
    tp2_rr_trending: float = 2.5
    tp1_rr_ranging: float = 0.8
    tp2_rr_ranging: float = 1.6
    tp1_rr_volatile: float = 1.0
    tp2_rr_volatile: float = 2.0
    tp1_close_pct: float = 0.5
    trail_activate_rr: float = 1.0
    trail_atr_mult: float = 0.8
    min_rr: float = 1.5
    atr_pct_ranging_thresh: float = 0.003
    atr_pct_volatile_thresh: float = 0.012


@dataclass
class BacktestConfig:
    default_initial_equity: float = 10_000.0
    default_risk_per_trade: float = 0.01
    min_trades_for_validity: int = 10
    warmup_bars: int = 210
    significance_threshold: float = 0.05
    max_jobs_concurrent: int = 2


@dataclass
class MLConfig:
    feature_window: int = 20
    train_test_split: float = 0.8
    cv_folds: int = 5
    default_model_type: str = "random_forest"
    n_estimators: int = 100
    max_depth: int = 5
    min_samples_split: int = 20
    prediction_threshold: float = 0.60
    retrain_after_n_trades: int = 50
    upload_dir: str = "uploads"
    model_artifact_dir: str = "ml_models"


@dataclass
class AIAdvisorConfig:
    enabled: bool = False
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 500
    min_confidence_to_show: float = 0.7
    lookback_bars: int = 50
    cooldown_minutes: int = 15
    anthropic_api_key: str = ""


@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    recent_trades_count: int = 50
    equity_curve_max_points: int = 500
    heartbeat_stale_seconds: int = 120
    poll_interval_ms: int = 5000
    session_cookie_name: str = "trading_session"
    cors_origins: list = field(default_factory=lambda: ["http://127.0.0.1:8000"])


@dataclass
class EngineConfig:
    poll_interval_seconds: int = 60
    mode: str = "continuous"
    snapshot_interval_seconds: int = 300


@dataclass
class PlatformConfig:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    mt5: MT5Config = field(default_factory=MT5Config)
    risk: RiskConfig = field(default_factory=RiskConfig)
    sltp: SLTPConfig = field(default_factory=SLTPConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    ai: AIAdvisorConfig = field(default_factory=AIAdvisorConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    base_dir: Path = BASE_DIR

    def __post_init__(self) -> None:
        (self.base_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "uploads").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "ml_models").mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        cfg = cls()
        cfg.db.url = os.environ.get("DATABASE_URL", cfg.db.url)
        cfg.auth.secret_key = os.environ.get("JWT_SECRET_KEY", cfg.auth.secret_key)
        cfg.mt5.login = int(os.environ.get("MT5_LOGIN", cfg.mt5.login or 0))
        cfg.mt5.password = os.environ.get("MT5_PASSWORD", cfg.mt5.password)
        cfg.mt5.server = os.environ.get("MT5_SERVER", cfg.mt5.server)
        cfg.ai.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", cfg.ai.anthropic_api_key)
        cfg.ai.enabled = bool(cfg.ai.anthropic_api_key)
        return cfg


config = PlatformConfig.from_env()
