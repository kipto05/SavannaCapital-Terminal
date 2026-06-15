"""dashboard/v2/routes - feature routers for the v2 API.

Each feature gets its own file with an APIRouter, imported here so
v2/app.py can include everything in one call.

Add a new feature:
1. Create routes/<feature>.py with an APIRouter
2. Import it below and include_router()
3. Done - routes are live at /api/v2/<feature>/...
"""
from __future__ import annotations

from dashboard.v2.routes import accounts  # noqa: F401
from dashboard.v2.routes import ai  # noqa: F401
from dashboard.v2.routes import backtest  # noqa: F401
from dashboard.v2.routes import engine  # noqa: F401
from dashboard.v2.routes import journal  # noqa: F401
from dashboard.v2.routes import ml  # noqa: F401
from dashboard.v2.routes import monitoring  # noqa: F401
from dashboard.v2.routes import strategies  # noqa: F401

__all__ = [
    "accounts",
    "ai",
    "backtest",
    "engine",
    "journal",
    "ml",
    "monitoring",
    "strategies",
]
