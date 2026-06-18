from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Load .env file immediately so os.environ picks up settings before any imports
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(Path(__file__).resolve().parent.parent, ".env"))
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


# ── Asset pools and timeframe lists ───────────────────────────────────────────
# Extend these dicts to add new symbols or timeframes. No strategy code changes needed.

# ─────────────────────────────────────────────────────────────────────────────
# Broker-neutral canonical symbol names (no suffix).
# resolution to broker-specific names (e.g. XAUUSD.m, US30.std) lives in
# data/repository.py via BrokerAdapter. Add a new broker → add a new entry
# in BROKER_SYMBOL_MAP; everything else (strategies, ML, DB) is untouched.
# ─────────────────────────────────────────────────────────────────────────────
ASSET_POOL: dict[str, list[str]] = {
# ── Crypto (JustMarkets uses <TICKER>USD.m or <TICKER>EUR.m for BTC) ─
"crypto": [
"BTCUSD", "ETHUSD", "BNBUSD", "XRPUSD", "SOLUSD",
"ADAUSD", "DOGEUSD", "AVAXUSD", "DOTUSD", "LINKUSD",
"LTCUSD", "MATICUSD","SHIBUSD", "TRXUSD", "UNIUSD",
"XLMUSD", "BCHUSD", "KSMUSD",
],
# ── Forex majors ────────────────────────────────────────────────────────
"forex": [
"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD", "USDCAD",
],
# ── Forex crosses & exotics (active JustMarkets pairs) ──────────────────
"forex_cross": [
"EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "GBPAUD",
"EURCHF", "GBPCHF", "AUDCAD", "AUDNZD", "NZDCAD", "NZDCHF",
"CADCHF", "CADJPY", "CHFJPY", "EURCAD", "EURNZD", "GBPNZD",
"EURSEK", "USDSEK", "EURHUF", "USDHUF", "USDPLN", "USDZAR",
"EURDKK", "USDNOK", "NOKSEK", "NOKJPY", "SEKJPY",
"CHFPLN", "CHFSGD", "EURCNH", "USDDKK", "USDHKD", "USDTHB",
"EURHKD", "EURPLN", "EURNOK", "GBPSEK", "GBPSGD", "NZDSGD",
"AUDSGD", "USDCNH", "USDMXN", "USDZAR", "USDMXN", "EURZAR",
"AUDCHF", "GBPNOK", "GBPUSD",
],
# ── Commodities & Metals ────────────────────────────────────────────────
# JustMarkets: XAU/USD, XAG/USD pairings plus WTI, Brent, NatGas
# Precious metals also quoted in EUR/GBP/AUD/JPY (XAUEUR.m, XAUGBP.m …)
"commodity": [
"XAUUSD", "XAGUSD", "XAUAUD", "XAUEUR", "XAUGBP", "XAUJPY", "XAGEUR",
"WTI", "BRENT", "XNGUSD",
"XPDUSD", "XPTUSD", # Palladium, Platinum
],
# ── Equity CFDs (US/EU names – JustMarkets .m suffix) ──────────────────
"equity": [
"AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL",
"META", "NFLX", "AMD", "INTC", "BABA", "BA",
"BAC", "C", "CRM", "DIS", "F", "GS",
"JPM", "KO", "MA", "MS", "NKE", "ORCL",
"PFE", "PG", "PYPL", "SHOP", "V", "VZ",
"WMT", "XOM", "ZM", "HOOD", "COIN", "UBER",
"ABNB", "DELL", "LMT", "RACE", "WFC", "CSCO",
"CVX", "SBUX", "QCOM", "BA", "MRVL",
],
# ── Index CFDs (JustMarkets uses .std suffix, NOT .m) ───────────────────
"index": [
"US30", "US500", "US100", "UK100", "DE40",
"FR40", "JP225", "AU200", "EU50", "ES35",
"SG20", "CH50", "SHA50", "HK50", "A50",
],
}

TIMEFRAMES_BY_ASSET: dict[str, list[str]] = {
"crypto": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
"forex": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
"commodity": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
"equity": ["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
}


# ── Broker symbol resolution ───────────────────────────────────────────────────
# Every canonical symbol in ASSET_POOL is resolved to its broker-specific
# terminal name through this map. When you add a new broker / account:
# 1. Add its entry here (suffix rules + explicit overrides for odd names)
# 2. Ensure MT5_SERVER in .env matches the key below
# 3. Nothing else changes — strategies, ML, DB all use canonical names.
#
# Strategy:
# - `default_suffix` → appended for every symbol not explicitly overridden
# - `overrides` → exact broker-specific name for the few instruments
#   that don't follow the pattern (e.g. BRENT, WTI,
#   BTCXAU, XNGUSD have no standard suffix variant)
# - `strip_suffix` → strip these known suffixes before re-applying
#   (idempotent — safe if symbol is already canonical)

BROKER_MAP: dict[str, dict] = {
# ── JustMarkets (current broker) ─────────────────────────────────────────
"JustMarkets-Demo3": {
"default_suffix": ".m",
"strip_suffix": {".m"},
"overrides": {
# Indices use .std not .m
"US30": "US30.std", "US500": "US500.std", "US100": "US100.std",
"UK100": "UK100.std", "DE40": "DE40.std", "FR40": "FR40.std",
"JP225": "JP225.std", "AU200": "AU200.std", "EU50": "EU50.std",
"ES35": "ES35.std", "SG20": "SG20.std", "CH50": "CH50.std",
"SHA50": "SHA50.std", "HK50": "SHA50.std", "A50": "A50.std",
# Commodity CFDs keep their broker names
"WTI": "WTI.m", "BRENT": "BRENT.m",
"XNGUSD": "XNGUSD.m", "XPDUSD": "XPDUSD.m", "XPTUSD": "XPTUSD.m",
# Crypto-Crypto cross
"BTCXAU": "BTCXAU.m",
},
},
# ── JustMarkets Live (same terminal, different server) ───────────────────
"JustMarkets-Live": {
"default_suffix": ".m",
"strip_suffix": {".m"},
"overrides": {
"US30": "US30.std", "US500": "US500.std", "US100": "US100.std",
"UK100": "UK100.std", "DE40": "DE40.std", "FR40": "FR40.std",
"JP225": "JP225.std", "AU200": "AU200.std",
"WTI": "WTI.m", "BRENT": "BRENT.m",
"XNGUSD": "XNGUSD.m", "XPDUSD": "XPDUSD.m", "XPTUSD": "XPTUSD.m",
"BTCXAU": "BTCXAU.m",
},
},
# ── Generic fallback (any non-JustMarkets MT5 broker) ───────────────────
# Most non-JustMarkets brokers use no suffix or their own convention.
# Add entries here as you test them.
"default": {
"default_suffix": "",
"strip_suffix": set(),
"overrides": {},
},
}


def resolve_broker_symbol(canonical: str, server: str = "") -> str:
    """Return the broker-specific terminal name for a canonical symbol.

    Example
    -------
    resolve_broker_symbol("EURUSD", "JustMarkets-Demo3") → "EURUSD.m"
    resolve_broker_symbol("US500", "JustMarkets-Demo3") → "US500.std"
    resolve_broker_symbol("BRENT", "JustMarkets-Demo3") → "BRENT.m"
    resolve_broker_symbol("EURUSD", "") → "EURUSD"
    """
    entry = BROKER_MAP.get(server) or BROKER_MAP.get("default", {"default_suffix": ""})
    # Check explicit override first
    upper = canonical.upper()
    if upper in entry.get("overrides", {}):
        return entry["overrides"][upper]
    # Strip any existing suffix, re-apply the default
    base = canonical
    for sfx in entry.get("strip_suffix", set()):
        if base.endswith(sfx):
            base = base[: -len(sfx)]
    default_sfx = entry.get("default_suffix", "")
    return base + default_sfx if default_sfx else base


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
    access_token_expire_minutes: int = 480
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
class SMTPConfig:
    """Email notification configuration."""
    host: str = "localhost"
    port: int = 25
    username: str = ""
    password: str = ""
    use_tls: bool = False
    from_email: str = "noreply@example.com"


@dataclass
class NotificationConfig:
    """Notification cleanup and retention configuration."""
    retention_days: int = 30


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
        "XAUUSD": 0.01, "XAGUSD": 0.001, "BTCUSD": 0.01, "ETHUSD": 0.01,
        "AAPL": 0.01, "TSLA": 0.01, "NVDA": 0.01,
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
class CircuitBreakerConfig:
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    halt_hours_after_trip: float = 1.0


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
    provider: str = "anthropic"        # anthropic | nvidia | gemini | openrouter
    # ── Global defaults (used when no per-use-case override is set) ──
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 500
    min_confidence_to_show: float = 0.7
    lookback_bars: int = 50
    cooldown_minutes: int = 15
    # NVIDIA-specific
    stream: bool = False               # stream responses token-by-token (NVIDIA only)
    reasoning_budget: int = 0          # extended thinking tokens for reasoning models (0=off)
    # ── Per-use-case overrides (set in .env, fall back to global above) ──
    suggest_model: str = ""            # model for trade suggestions (empty = use global model)
    suggest_max_tokens: int = 0       # 0 = use global max_tokens
    suggest_reasoning_budget: int = -1 # -1 = use global reasoning_budget
    chat_model: str = ""               # model for research terminal (empty = use global)
    chat_max_tokens: int = 0           # 0 = use global
    chat_reasoning_budget: int = -1    # -1 = use global
    chat_stream: bool = ""             # empty = use global stream setting
    # Provider API keys — only fill the one(s) you use
    anthropic_api_key: str = ""
    nvidia_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    def effective_model(self, use_case: str = "suggest") -> str:
        """Return the model for a given use case."""
        if use_case == "chat":
            return self.chat_model or self.model
        return self.suggest_model or self.model

    def effective_max_tokens(self, use_case: str = "suggest") -> int:
        """Return max_tokens for a given use case."""
        val = self.chat_max_tokens if use_case == "chat" else self.suggest_max_tokens
        return val if val > 0 else self.max_tokens

    def effective_reasoning_budget(self, use_case: str = "suggest") -> int:
        """Return reasoning_budget for a given use case."""
        val = self.chat_reasoning_budget if use_case == "chat" else self.suggest_reasoning_budget
        return val if val >= 0 else self.reasoning_budget

    def effective_stream(self, use_case: str = "suggest") -> bool:
        """Return stream setting for a given use case."""
        if use_case == "chat":
            if self.chat_stream != "":
                return str(self.chat_stream).lower() in ("1", "true", "yes")
        return self.stream


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
    min_bars_required: int = 50
    reconnect_delay_seconds: int = 5
    max_reconnect_attempts: int = 3
    quant_trigger_interval_seconds: int = 604800  # once per week
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


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
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
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
        cfg.mt5.path = os.environ.get("MT5_PATH", cfg.mt5.path)

        # ── AI provider config ────────────────────────────────────────────
        cfg.ai.provider = os.environ.get("AI_PROVIDER", cfg.ai.provider).lower()
        # Global model settings
        cfg.ai.model = os.environ.get("AI_MODEL", cfg.ai.model)
        cfg.ai.stream = os.environ.get("AI_STREAM", "false").lower() in ("1", "true", "yes")
        cfg.ai.reasoning_budget = int(os.environ.get("AI_REASONING_BUDGET", "0"))
        cfg.ai.max_tokens = int(os.environ.get("AI_MAX_TOKENS", str(cfg.ai.max_tokens)))
        # Per-use-case overrides
        cfg.ai.suggest_model = os.environ.get("AI_SUGGEST_MODEL", cfg.ai.suggest_model)
        cfg.ai.chat_model = os.environ.get("AI_CHAT_MODEL", cfg.ai.chat_model)
        cfg.ai.suggest_max_tokens = int(os.environ.get("AI_SUGGEST_MAX_TOKENS", str(cfg.ai.suggest_max_tokens)))
        cfg.ai.chat_max_tokens = int(os.environ.get("AI_CHAT_MAX_TOKENS", str(cfg.ai.chat_max_tokens)))
        cfg.ai.suggest_reasoning_budget = int(os.environ.get("AI_SUGGEST_REASONING_BUDGET", str(cfg.ai.suggest_reasoning_budget)))
        cfg.ai.chat_reasoning_budget = int(os.environ.get("AI_CHAT_REASONING_BUDGET", str(cfg.ai.chat_reasoning_budget)))
        cfg.ai.chat_stream = os.environ.get("AI_CHAT_STREAM", cfg.ai.chat_stream)
        # Provider API keys
        cfg.ai.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", cfg.ai.anthropic_api_key)
        cfg.ai.nvidia_api_key = os.environ.get("NVIDIA_API_KEY", cfg.ai.nvidia_api_key)
        cfg.ai.gemini_api_key = os.environ.get("GEMINI_API_KEY", cfg.ai.gemini_api_key)
        cfg.ai.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", cfg.ai.openrouter_api_key)

        # Enabled if ANY provider key is present
        has_key = any([
            cfg.ai.anthropic_api_key,
            cfg.ai.nvidia_api_key,
            cfg.ai.gemini_api_key,
            cfg.ai.openrouter_api_key,
        ])
        cfg.ai.enabled = has_key

        # ── SMTP config ─────────────────────────────────────────────────────
        cfg.smtp.host = os.environ.get("SMTP_HOST", cfg.smtp.host)
        cfg.smtp.port = int(os.environ.get("SMTP_PORT", str(cfg.smtp.port)))
        cfg.smtp.username = os.environ.get("SMTP_USERNAME", cfg.smtp.username)
        cfg.smtp.password = os.environ.get("SMTP_PASSWORD", cfg.smtp.password)
        cfg.smtp.use_tls = os.environ.get("SMTP_USE_TLS", str(cfg.smtp.use_tls)).lower() in ("1", "true", "yes")
        cfg.smtp.from_email = os.environ.get("SMTP_FROM_EMAIL", cfg.smtp.from_email)

        # ── Notification cleanup config ─────────────────────────────────────
        notification_retention = os.environ.get("NOTIFICATION_RETENTION_DAYS", str(cfg.notification.retention_days))
        cfg.notification.retention_days = int(notification_retention)

        return cfg


config = PlatformConfig.from_env()
