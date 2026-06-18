"""Pytest fixtures for notification subsystem tests.

Provides:
- In-memory SQLite database with all tables created
- FastAPI TestClient with dependency overrides for test DB
- Test users (regular and admin)
- NotificationService fixture
- SMTP mock (automatically applied)
- Seeded NotificationSettings for test user
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.session import Base, get_db
from auth.service import hash_password
from config.settings import config as app_config
from dashboard.app import app as original_app

# Override SMTP config for tests to avoid real sends
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "25"
os.environ["SMTP_USERNAME"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["SMTP_USE_TLS"] = "false"
os.environ["SMTP_FROM_EMAIL"] = "test@example.com"


@pytest.fixture(scope="session")
def engine():
    """Create SQLite in-memory engine and create all tables."""
    engine = create_engine("sqlite:///:memory:")

    # Import all models to ensure they're registered with Base
    from db.models import (
        User,
        Notification,
        NotificationRecipient,
        NotificationSettings,
    )

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def connection(engine):
    """Create a new connection for each test with transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db(connection) -> Generator[Session, None, None]:
    """Provide a Session bound to the test transaction."""
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def app(db) -> FastAPI:
    """Create FastAPI app with get_db override for testing."""

    # Override the get_db dependency
    def override_get_db():
        try:
            yield db
        finally:
            pass  # db cleanup handled by fixture

    original_app.dependency_overrides[get_db] = override_get_db
    yield original_app
    original_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app) -> TestClient:
    """Create TestClient for the test app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def test_user(db: Session) -> User:
    """Create a regular test user."""
    from db.models import User

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpass"),
        role="trader",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture(scope="function")
def admin_user(db: Session) -> User:
    """Create an admin test user."""
    from db.models import User

    admin = User(
        username="adminuser",
        email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    return admin


@pytest.fixture(scope="function")
def notification_service(db: Session) -> "NotificationService":
    """Create NotificationService instance bound to test DB."""
    from execution.notification_service import NotificationService

    service = NotificationService(db)
    return service


@pytest.fixture(scope="session", autouse=True)
def mock_smtp():
    """Automatically mock SMTP for all tests."""
    with patch("smtplib.SMTP") as mock_smtp_class:
        # Create mock instance with necessary methods
        mock_smtp = MagicMock()
        mock_smtp.starttls = MagicMock()
        mock_smtp.login = MagicMock()
        mock_smtp.send_message = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        mock_smtp_class.return_value = mock_smtp
        yield mock_smtp_class


@pytest.fixture(scope="function")
def seeded_settings(db: Session, test_user: User):
    """Seed notification settings for test user."""
    from db.models import NotificationSettings

    settings = [
        NotificationSettings(
            user_id=test_user.id,
            event_type="strategy_signal",
            in_app_enabled=True,
            email_enabled=False,
        ),
        NotificationSettings(
            user_id=test_user.id,
            event_type="order_placed",
            in_app_enabled=True,
            email_enabled=True,
        ),
    ]
    db.add_all(settings)
    db.flush()
    return settings


# Helper to override _get_current_user dependency for API tests

def override_get_current_user(test_user: User):
    """Create a dependency override for _get_current_user."""
    async def _override():
        return test_user
    return _override


@pytest.fixture(scope="function")
def override_current_user(app, test_user):
    """Override _get_current_user to return test_user for API tests."""
    from auth.router import _get_current_user

    app.dependency_overrides[_get_current_user] = override_get_current_user(test_user)
    yield
    # Cleanup happens in app fixture teardown


@pytest.fixture(scope="function")
def override_admin_user(app, admin_user):
    """Override _get_current_user to return admin_user for admin tests."""
    from auth.router import _get_current_user

    app.dependency_overrides[_get_current_user] = override_get_current_user(admin_user)
    yield
    # Cleanup happens in app fixture teardown
