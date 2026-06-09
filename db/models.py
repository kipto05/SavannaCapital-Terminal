"""
db/models.py — all SQLAlchemy ORM models.
13 tables covering auth, trades, strategies, backtesting, ML, AI advisor, and settings.

Import pattern (never import from anywhere else):
    from db.models import Trade, User, OHLCVBar, StrategyConfig, BacktestRun
"""
from __future__ import annotations

import enum
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

from db.session import Base

log = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────

class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class StrategyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    ACCEPTED = "ACCEPTED"
    DEPLOYED = "DEPLOYED"
    REJECTED = "REJECTED"


class HypothesisStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ModelType(str, enum.Enum):
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    LOGISTIC = "logistic"


class AISide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), nullable=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="trader", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover — never log hashes
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Trade ────────────────────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_symbol_opened", "symbol", "opened_at"),
        Index("ix_trades_strategy", "strategy_name", "symbol", "timeframe"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket = Column(String(64), nullable=True, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False)
    side = Column(Enum(Side), nullable=False)
    strategy_name = Column(String(64), nullable=False, index=True)

    entry = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    tp1 = Column(Float, nullable=True)
    tp2 = Column(Float, nullable=True)

    lot_size = Column(Float, nullable=True)
    open_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_r = Column(Float, nullable=True)

    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Source tracking — backtest / live / ai_advisor
    source = Column(String(32), default="live", nullable=False, index=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=True, index=True)
    ai_suggestion_id = Column(Integer, ForeignKey("ai_advisor_suggestions.id"), nullable=True, index=True)

    account_snapshot_id = Column(Integer, ForeignKey("account_snapshots.id"), nullable=True)

    # Meta
    is_active = Column(Boolean, default=True, nullable=False)
    closed_reason = Column(String(64), nullable=True)
    tag = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Back-relations
    backtest_run = relationship("BacktestRun", back_populates="trades", lazy="noload")
    ai_suggestion = relationship("AIAdvisorSuggestion", back_populates="trades", lazy="noload")
    account_snapshot = relationship("AccountSnapshot", back_populates="trades", lazy="noload")
    annotations = relationship("TradeAnnotation", back_populates="trade", cascade="all, delete-orphan", lazy="noload")

    __table_args__ = (
        Index("ix_trades_symbol_opened", "symbol", "opened_at"),
        Index("ix_trades_strategy", "strategy_name", "symbol", "timeframe"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket": self.ticket,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "side": self.side.value if isinstance(self.side, Side) else self.side,
            "strategy_name": self.strategy_name,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "lot_size": self.lot_size,
            "open_price": self.open_price,
            "close_price": self.close_price,
            "pnl": self.pnl,
            "pnl_r": self.pnl_r,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "source": self.source,
            "backtest_run_id": self.backtest_run_id,
            "ai_suggestion_id": self.ai_suggestion_id,
            "is_active": self.is_active,
            "closed_reason": self.closed_reason,
            "tag": self.tag,
            "notes": self.notes,
        }


# ── AccountSnapshot ───────────────────────────────────────────────────────────

class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    margin = Column(Float, nullable=True)
    free_margin = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)

    trades = relationship("Trade", back_populates="account_snapshot", lazy="noload")


# ── OHLCVBar ──────────────────────────────────────────────────────────────────

class OHLCVBar(Base):
    __tablename__ = "ohlcv_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_ohlcv_symbol_tf_ts"),
        Index("ix_ohlcv_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=True)
    tick_volume = Column(Integer, nullable=True)
    spread = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<OHLCVBar {self.symbol} {self.timeframe} {self.timestamp}>"


# ── StrategyConfig ────────────────────────────────────────────────────────────

class StrategyConfig(Base):
    __tablename__ = "strategy_configs"
    __table_args__ = (
        UniqueConstraint("name", "symbol", "timeframe", name="uq_strategy_symbol_tf"),
        Index("ix_strategy_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)  # e.g. "momentum_reversion"
    label = Column(String(128), nullable=False)  # e.g. "Momentum Reversion"
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False, index=True)
    is_active = Column(Boolean, default=False, nullable=False)

    params = Column(JSON, nullable=False, default=dict)
    param_bounds = Column(JSON, nullable=True)

    version = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    param_versions = relationship(
        "StrategyParamVersion",
        back_populates="strategy_config",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="desc(StrategyParamVersion.created_at)",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "is_active": self.is_active,
            "params": self.params,
            "param_bounds": self.param_bounds,
            "version": self.version,
        }


# ── StrategyParamVersion ──────────────────────────────────────────────────────

class StrategyParamVersion(Base):
    __tablename__ = "strategy_param_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_config_id = Column(Integer, ForeignKey("strategy_configs.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    params = Column(JSON, nullable=False)
    changed_by = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    strategy_config = relationship("StrategyConfig", back_populates="param_versions", lazy="noload")


# ── BacktestRun ───────────────────────────────────────────────────────────────

class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(128), nullable=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False)
    strategy_name = Column(String(64), nullable=False, index=True)

    initial_equity = Column(Float, nullable=False)
    final_equity = Column(Float, nullable=True)
    net_pnl_r = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)

    n_bars = Column(Integer, nullable=True)
    n_trades = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    sharpe_approx = Column(Float, nullable=True)

    p_value = Column(Float, nullable=True)  # binomial significance
    is_significant = Column(Boolean, nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)

    equity_curve = Column(JSON, nullable=True)
    drawdown_curve = Column(JSON, nullable=True)
    monthly_returns = Column(JSON, nullable=True)

    params_snapshot = Column(JSON, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    trades = relationship("Trade", back_populates="backtest_run", lazy="noload")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "initial_equity": self.initial_equity,
            "net_pnl_r": self.net_pnl_r,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "n_trades": self.n_trades,
            "status": self.status,
            "is_significant": self.is_significant,
            "p_value": self.p_value,
        }


# ── Hypothesis ────────────────────────────────────────────────────────────────

class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(HypothesisStatus), default=HypothesisStatus.DRAFT, nullable=False, index=True)
    symbol = Column(String(32), nullable=True, index=True)
    timeframe = Column(String(8), nullable=True)

    hypothesis_text = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    test_result = Column(Text, nullable=True)

    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value if isinstance(self.status, HypothesisStatus) else self.status,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "hypothesis_text": self.hypothesis_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── MLModel ───────────────────────────────────────────────────────────────────

class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    model_type = Column(Enum(ModelType), nullable=False)
    symbol = Column(String(32), nullable=True, index=True)
    timeframe = Column(String(8), nullable=True)

    artifact_path = Column(String(512), nullable=True)
    feature_columns = Column(JSON, nullable=True)
    hyperparams = Column(JSON, nullable=True)

    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1 = Column(Float, nullable=True)

    n_train_samples = Column(Integer, nullable=True)
    last_trained_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model_type": self.model_type.value if isinstance(self.model_type, ModelType) else self.model_type,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "is_active": self.is_active,
            "accuracy": self.accuracy,
            "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
        }


# ── AIAdvisorSuggestion ────────────────────────────────────────────────────────

class AIAdvisorSuggestion(Base):
    __tablename__ = "ai_advisor_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False)
    side = Column(Enum(AISide), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    market_context = Column(JSON, nullable=True)
    raw_response = Column(Text, nullable=True)

    trades = relationship("Trade", back_populates="ai_suggestion", lazy="noload")

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "side": self.side.value if isinstance(self.side, AISide) else self.side,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── TradeAnnotation ───────────────────────────────────────────────────────────

class TradeAnnotation(Base):
    __tablename__ = "trade_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    tag = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    trade = relationship("Trade", back_populates="annotations", lazy="noload")


# ── PlatformSetting ───────────────────────────────────────────────────────────

class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(32), default="str", nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<PlatformSetting key={self.key!r} value={self.value!r}>"
