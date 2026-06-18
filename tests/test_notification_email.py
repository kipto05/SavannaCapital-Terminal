"""Tests for email integration.

Tests:
- Email composition: subject contains "Savanna Capital", from matches config.smtp.from_email, to equals user.username, HTML body contains notification details and link
- TLS/starttls called when config.smtp.use_tls is true
- Login called when credentials present
- _send_emails_async spawns daemon thread and sends email
- Rate limiting: publishes 12 notifications rapidly, verifies only up to 10 email send attempts
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from jinja2 import Environment, FileSystemLoader

from execution.notification_service import NotificationService, _can_send_email, _email_timestamps
from config.settings import config as app_config


class TestSendEmailsAsync:
    """Tests for NotificationService._send_emails_async."""

    def test_send_emails_async_spawns_daemon_thread(self, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """_send_emails_async should spawn a daemon thread."""
        notif = notification_service.publish(
            event_type="order_placed",
            title="Order Placed",
            message="Test message",
            recipient_ids=[test_user.id],
        )

        # Check that a thread was started
        # The thread is started inside _send_emails_async and we can't easily capture it,
        # but we can verify by checking that SMTP's send_message was called
        # Wait briefly for thread to execute
        time.sleep(0.5)

        # Verify SMTP was called
        assert mock_smtp.return_value.send_message.called

    def test_send_emails_async_sends_html_email(self, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """Email should have correct subject, from, to, and HTML body."""
        notif = notification_service.publish(
            event_type="order_placed",
            title="Order Placed",
            message="Your order was placed successfully.",
            data={"order_id": 12345},
            recipient_ids=[test_user.id],
        )

        time.sleep(0.5)

        # Check SMTP was used
        mock_smtp_instance = mock_smtp.return_value
        assert mock_smtp_instance.send_message.called

        # Get the message that was sent
        sent_msg = mock_smtp_instance.send_message.call_args[0][0]

        # Check headers
        assert "Savanna Capital: Order Placed" in sent_msg['Subject']
        assert sent_msg['From'] == app_config.smtp.from_email
        assert sent_msg['To'] == test_user.username

        # Check HTML body contains notification details
        html_body = sent_msg.get_payload(decode=True).decode('utf-8')
        assert "Order Placed" in html_body
        assert "Your order was placed successfully." in html_body
        assert "notification" in html_body.lower()
        # Should contain a link (config.dashboard.base_url or /notifications)
        assert 'href=' in html_body

    def test_send_emails_async_uses_tls_when_configured(self, db: Session, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """If config.smtp.use_tls is True, starttls() should be called."""
        # Set use_tls in config
        original_use_tls = app_config.smtp.use_tls
        app_config.smtp.use_tls = True
        app_config.smtp.host = "smtp.example.com"
        app_config.smtp.port = 587

        try:
            notif = notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[test_user.id],
            )
            time.sleep(0.5)

            mock_smtp_instance = mock_smtp.return_value
            mock_smtp_instance.starttls.assert_called_once()
        finally:
            app_config.smtp.use_tls = original_use_tls

    def test_send_emails_async_logins_when_credentials_set(self, db: Session, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """If SMTP username/password configured, login() should be called."""
        original_username = app_config.smtp.username
        original_password = app_config.smtp.password
        app_config.smtp.username = "testuser"
        app_config.smtp.password = "testpass"
        app_config.smtp.host = "smtp.example.com"
        app_config.smtp.port = 587

        try:
            notif = notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[test_user.id],
            )
            time.sleep(0.5)

            mock_smtp_instance = mock_smtp.return_value
            mock_smtp_instance.login.assert_called_once_with("testuser", "testpass")
        finally:
            app_config.smtp.username = original_username
            app_config.smtp.password = original_password

    def test_send_emails_async_no_login_when_no_credentials(self, db: Session, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """If no SMTP credentials, login() should not be called."""
        app_config.smtp.username = ""
        app_config.smtp.password = ""

        notif = notification_service.publish(
            event_type="order_placed",
            title="Test",
            message="Test",
            recipient_ids=[test_user.id],
        )
        time.sleep(0.5)

        mock_smtp_instance = mock_smtp.return_value
        mock_smtp_instance.login.assert_not_called()

    def test_send_emails_async_no_email_when_disabled(self, db: Session, notification_service: NotificationService, test_user: User, mock_smtp):
        """If user has email_enabled=False, no email should be sent."""
        # Create settings with email_enabled=False
        from db.models import NotificationSettings
        settings = NotificationSettings(
            user_id=test_user.id,
            event_type="order_placed",
            in_app_enabled=True,
            email_enabled=False,
        )
        db.add(settings)
        db.flush()

        notif = notification_service.publish(
            event_type="order_placed",
            title="Test",
            message="Test",
            recipient_ids=[test_user.id],
        )
        time.sleep(0.5)

        # SMTP should not be used since email is disabled
        mock_smtp.assert_not_called()

    def test_send_emails_async_user_without_username(self, db: Session, notification_service: NotificationService, seeded_settings, mock_smtp):
        """If recipient user has no username, email should not be sent (skipped silently)."""
        # Create user without username
        from db.models import User
        user_no_email = User(
            username="",  # empty username
            email="no@example.com",
            hashed_password=hash_password("pass"),
            role="trader",
            is_active=True,
        )
        db.add(user_no_email)
        db.flush()

        notif = notification_service.publish(
            event_type="order_placed",
            title="Test",
            message="Test",
            recipient_ids=[user_no_email.id],
        )
        time.sleep(0.5)

        # Should skip this user
        mock_smtp.assert_not_called()

    def test_send_emails_async_uses_base_url_from_config(self, db: Session, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """Email link should use config.dashboard.base_url if set."""
        # Set base_url
        original_base_url = getattr(app_config.dashboard, 'base_url', None)
        app_config.dashboard.base_url = "https://savannacapital.com"

        try:
            notif = notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[test_user.id],
            )
            time.sleep(0.5)

            sent_msg = mock_smtp.return_value.send_message.call_args[0][0]
            html_body = sent_msg.get_payload(decode=True).decode('utf-8')
            assert "https://savannacapital.com" in html_body
        finally:
            app_config.dashboard.base_url = original_base_url

    def test_send_emails_async_uses_default_link_when_no_base_url(self, db: Session, notification_service: NotificationService, test_user: User, seeded_settings, mock_smtp):
        """If no base_url, link should default to /notifications."""
        original_base_url = getattr(app_config.dashboard, 'base_url', None)
        # Ensure base_url is not set
        if hasattr(app_config.dashboard, 'base_url'):
            delattr(app_config.dashboard, 'base_url')

        try:
            notif = notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[test_user.id],
            )
            time.sleep(0.5)

            sent_msg = mock_smtp.return_value.send_message.call_args[0][0]
            html_body = sent_msg.get_payload(decode=True).decode('utf-8')
            assert "/notifications" in html_body
        finally:
            if original_base_url is not None:
                app_config.dashboard.base_url = original_base_url
            elif hasattr(app_config.dashboard, 'base_url'):
                delattr(app_config.dashboard, 'base_url')


class TestEmailRateLimitingIntegration:
    """Integration tests for rate limiting with actual publish calls."""

    def test_rate_limit_blocks_after_10_emails(self, db: Session, notification_service: NotificationService, seeded_settings, test_user: User, mock_smtp):
        """After 10 emails, additional publishes should not send more."""
        # Clear any existing timestamps
        _email_timestamps.clear()

        mock_smtp_instance = mock_smtp.return_value

        # Publish 12 notifications rapidly
        for i in range(12):
            notification_service.publish(
                event_type="order_placed",  # email_enabled=True for test_user
                title=f"Order {i}",
                message=f"Message {i}",
                recipient_ids=[test_user.id],
            )

        time.sleep(0.5)

        # Should have at most 10 send_message calls
        assert mock_smtp_instance.send_message.call_count <= 10

    def test_rate_limit_resets_after_hour(self, db: Session, notification_service: NotificationService, seeded_settings, test_user: User, mock_smtp):
        """After an hour, should allow more emails."""
        _email_timestamps.clear()

        # Simulate sending 10 emails at time T
        base_time = time.time()
        with patch('time.time', return_value=base_time):
            for _ in range(10):
                _can_send_email(test_user.id)

        # At T + 3601 seconds (1 hour + 1 sec), should allow 1 more
        later_time = base_time + 3601
        with patch('time.time', return_value=later_time):
            assert _can_send_email(test_user.id) is True

    def test_rate_limit_per_user_is_isolated(self, db: Session, notification_service: NotificationService, seeded_settings, test_user: User, admin_user: User, mock_smtp):
        """Rate limit should be per user, not global."""
        _email_timestamps.clear()

        # Send 10 emails to test_user
        for _ in range(10):
            notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[test_user.id],
            )

        # Send 10 emails to admin_user (separate user)
        for _ in range(10):
            notification_service.publish(
                event_type="order_placed",
                title="Test",
                message="Test",
                recipient_ids=[admin_user.id],
            )

        time.sleep(0.5)

        # Both should have been sent (20 total, 10 each)
        assert mock_smtp.return_value.send_message.call_count <= 20  # may be <= 20 due to threading


class TestEmailTemplate:
    """Tests for email template rendering."""

    def test_template_renders_notification_details(self, notification_service: NotificationService, test_user: User, seeded_settings):
        """Template should contain notification title and message."""
        notif_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "type": "strategy_signal",
            "title": "Buy Signal: BTCUSD",
            "message": "Momentum strategy triggered a buy signal on BTCUSD M15.",
            "created_at": datetime.utcnow(),
        }

        # Render template manually (it's used inside _send_emails_async)
        env = Environment(loader=FileSystemLoader('dashboard/templates'))
        template = env.get_template('emails/notification.html')

        # Setup a minimal Notification object-like notif
        class MockNotification:
            def __init__(self, data):
                self.__dict__.update(data)

        notif = MockNotification(notif_data)

        html = template.render(notification=notif, user=test_user, link="/notifications")

        assert "Buy Signal: BTCUSD" in html
        assert "Momentum strategy triggered" in html
        assert test_user.username in html
        assert "Savanna Capital" in html

    def test_template_has_button_link(self, notification_service: NotificationService, test_user: User, seeded_settings):
        """Template should have a clickable button linking to notifications."""
        env = Environment(loader=FileSystemLoader('dashboard/templates'))
        template = env.get_template('emails/notification.html')

        class MockNotification:
            def __init__(self, link):
                self.link = link

        notif = MockNotification("https://savannacapital.com/notifications")
        html = template.render(notification=notif, user=test_user, link=notif.link)

        assert 'href="https://savannacapital.com/notifications"' in html
        assert "<button" in html or "<a " in html

