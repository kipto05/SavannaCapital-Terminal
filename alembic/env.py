"""Alembic environment — wired to the Savanna Capital Quant OS project."""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Bootstrap project path ─────────────────────────────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ── Load .env if python-dotenv is available ───────────────────────────────────
try:
    from dotenv import load_dotenv  # noqa: E402
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Wire target_metadata to the project's declared Base ───────────────────────
from db.session import Base  # noqa: E402
from db.models import (  # noqa: E402 — import every model for autogenerate
    User,
    Trade,
    AccountSnapshot,
    OHLCVBar,
    StrategyConfig,
    StrategyParamVersion,
    BacktestRun,
    Hypothesis,
    MLModel,
    AIAdvisorSuggestion,
    TradeAnnotation,
    PlatformSetting,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
