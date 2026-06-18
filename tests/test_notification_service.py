"""Tests for NotificationService.

Coverage:
- publish(): notification & recipient creation, email thread start
- get_user_notifications(): pagination, filters, ordering
- get_notification_count(): filters
- mark_as_read(): valid, already read, invalid ID
- mark_all_read(): count of updated rows
- delete_notification(): admin global delete, user self delete, unauthorized, conditional deletion
- cleanup_old_notifications(): delete old only, edge cases
- Email rate limiting: 10 per user per rolling hour
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from execution.notification_service import NotificationService, _can_send_email
from db.models import NotificationRecipient


class TestNotificationServicePublish:
    """Tests for NotificationService.publish."""

    def test_publish_creates_notification_and_recipients(self, notification_service: NotificationService, test_user: User):
        """publish should create Notification and NotificationRecipient rows."""
        notif = notification_service.publish(
            event_type="strategy_signal",
            title="Test Signal",
            message="Test message body",
            data={"key": "value"},
            recipient_ids=[test_user.id],
        )

        assert notif is not None
        assert notif.type == "strategy_signal"
        assert notif.title == "Test Signal"
        assert notif.message == "Test message body"
        assert notif.data == {"key": "value"}
        assert notif.id is not None

        # Check recipients
        recipients = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id).all()
        assert len(recipients) == 1
        assert recipients[0].user_id == test_user.id
        assert recipients[0].is_read is False

    def test_publish_without_recipient_ids_uses_settings(self, notification_service: NotificationService, seeded_settings, test_user: User):
        """publish with recipient_ids=None should create recipients for users with in_app_enabled for that event_type."""
        # seeded_settings includes strategy_signal (in_app_enabled=True, email_enabled=False) for test_user
        notif = notification_service.publish(
            event_type="strategy_signal",
            title="Broadcast",
            message="To all with in_app enabled",
        )

        assert notif is not None
        recipients = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id).all()
        assert len(recipients) == 1
        assert recipients[0].user_id == test_user.id

    def test_publish_starts_email_thread_when_smtp_configured(self, notification_service: NotificationService, test_user: User, seeded_settings):
        """If SMTP host is configured, _send_emails_async should spawn a daemon thread."""
        # Patch time to control rate limit check
        with patch.object(notification_service, '_send_emails_async') as mock_send:
            notif = notification_service.publish(
                event_type="order_placed",  # email_enabled=True in seeded_settings
                title="Order Placed",
                message="Your order was placed",
                recipient_ids=[test_user.id],
            )

            assert notif is not None
            mock_send.assert_called_once_with(notif.id, [test_user.id])

    def test_publish_handles_exception_and_returns_none(self, notification_service: NotificationService, test_user: User):
        """publish should catch exceptions, rollback, and return None."""
        with patch.object(notification_service.db, 'add', side_effect=Exception("DB error")):
            result = notification_service.publish(
                event_type="error",
                title="Should Fail",
                message="This will raise",
            )
            assert result is None


class TestNotificationServiceGetUserNotifications:
    """Tests for get_user_notifications."""

    def test_get_user_notifications_returns_ordered_by_created_at_desc(self, notification_service: NotificationService, test_user: User):
        """Notifications should be returned in reverse chronological order."""
        # Create multiple notifications with different times
        now = datetime.utcnow()
        n1 = notification_service.publish("type1", "Title 1", "Msg 1", recipient_ids=[test_user.id])
        # Simulate earlier created_at by manually updating (requires flush)
        notification_service.db.query(Notification).filter_by(id=n1.id).update({"created_at": now - timedelta(minutes=5)})
        notification_service.db.flush()

        n2 = notification_service.publish("type2", "Title 2", "Msg 2", recipient_ids=[test_user.id])
        notification_service.db.query(Notification).filter_by(id=n2.id).update({"created_at": now - timedelta(minutes=3)})
        notification_service.db.flush()

        n3 = notification_service.publish("type3", "Title 3", "Msg 3", recipient_ids=[test_user.id])
        notification_service.db.query(Notification).filter_by(id=n3.id).update({"created_at": now - timedelta(minutes=1)})
        notification_service.db.flush()

        results = notification_service.get_user_notifications(user_id=test_user.id)
        assert len(results) == 3
        # Most recent first
        assert results[0]['id'] == str(n3.id)
        assert results[1]['id'] == str(n2.id)
        assert results[2]['id'] == str(n1.id)

    def test_get_user_notifications_pagination(self, notification_service: NotificationService, test_user: User):
        """Pagination should work correctly with limit and offset."""
        # Create 5 notifications
        for i in range(5):
            notification_service.publish(f"type{i}", f"Title {i}", f"Msg {i}", recipient_ids=[test_user.id])

        page1 = notification_service.get_user_notifications(user_id=test_user.id, limit=2, offset=0)
        assert len(page1) == 2

        page2 = notification_service.get_user_notifications(user_id=test_user.id, limit=2, offset=2)
        assert len(page2) == 2

        page3 = notification_service.get_user_notifications(user_id=test_user.id, limit=2, offset=4)
        assert len(page3) == 1

    def test_get_user_notifications_filter_is_read(self, notification_service: NotificationService, test_user: User):
        """Filter by is_read should return only matching notifications."""
        n_unread = notification_service.publish("type", "Unread", "Msg", recipient_ids=[test_user.id])
        n_read = notification_service.publish("type", "Read", "Msg", recipient_ids=[test_user.id])
        # Mark one as read
        notification_service.mark_as_read(str(n_read.id), test_user.id)

        unread_only = notification_service.get_user_notifications(user_id=test_user.id, is_read=True)
        assert len(unread_only) == 1
        assert unread_only[0]['id'] == str(n_unread.id)

        read_only = notification_service.get_user_notifications(user_id=test_user.id, is_read=False)
        assert len(read_only) == 1
        assert read_only[0]['id'] == str(n_read.id)

    def test_get_user_notifications_filter_type(self, notification_service: NotificationService, test_user: User):
        """Filter by type should return only matching notifications."""
        n_type_a = notification_service.publish("type_a", "A", "Msg", recipient_ids=[test_user.id])
        n_type_b = notification_service.publish("type_b", "B", "Msg", recipient_ids=[test_user.id])

        results_a = notification_service.get_user_notifications(user_id=test_user.id, type="type_a")
        assert len(results_a) == 1
        assert results_a[0]['type'] == "type_a"
        assert results_a[0]['id'] == str(n_type_a.id)

        results_b = notification_service.get_user_notifications(user_id=test_user.id, type="type_b")
        assert len(results_b) == 1
        assert results_b[0]['id'] == str(n_type_b.id)

    def test_get_user_notifications_returns_empty_on_no_notifications(self, notification_service: NotificationService):
        """Should return empty list if user has no notifications."""
        results = notification_service.get_user_notifications(user_id=99999)
        assert results == []

    def test_get_user_notifications_handles_exception(self, notification_service: NotificationService):
        """On exception, should return empty list."""
        with patch.object(notification_service.db, 'query', side_effect=Exception("DB error")):
            results = notification_service.get_user_notifications(user_id=1)
            assert results == []


class TestNotificationServiceGetNotificationCount:
    """Tests for get_notification_count."""

    def test_get_notification_count_counts_correctly(self, notification_service: NotificationService, test_user: User):
        """Should return total count matching filters."""
        notification_service.publish("type1", "T1", "M1", recipient_ids=[test_user.id])
        notification_service.publish("type2", "T2", "M2", recipient_ids=[test_user.id])
        notification_service.publish("type1", "T3", "M3", recipient_ids=[test_user.id])

        total = notification_service.get_notification_count(user_id=test_user.id)
        assert total == 3

        type1_count = notification_service.get_notification_count(user_id=test_user.id, type="type1")
        assert type1_count == 2

        unread_count = notification_service.get_notification_count(user_id=test_user.id, is_read=False)
        assert unread_count == 3

    def test_get_notification_count_returns_zero_on_no_matches(self, notification_service: NotificationService):
        """Should return 0 if no notifications match."""
        count = notification_service.get_notification_count(user_id=99999)
        assert count == 0

    def test_get_notification_count_handles_exception(self, notification_service: NotificationService):
        """On exception, should return 0."""
        with patch.object(notification_service.db, 'query', side_effect=Exception("DB error")):
            count = notification_service.get_notification_count(user_id=1)
            assert count == 0


class TestNotificationServiceMarkAsRead:
    """Tests for mark_as_read."""

    def test_mark_as_read_valid(self, notification_service: NotificationService, test_user: User):
        """Should mark notification as read and return True."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])
        result = notification_service.mark_as_read(str(notif.id), test_user.id)
        assert result is True

        # Verify in DB
        recipient = notification_service.db.query(NotificationRecipient).filter_by(
            notification_id=notif.id, user_id=test_user.id
        ).first()
        assert recipient.is_read is True
        assert recipient.read_at is not None

    def test_mark_as_read_already_read_returns_false(self, notification_service: NotificationService, test_user: User):
        """Should return False if already read."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])
        # Mark as read twice
        notification_service.mark_as_read(str(notif.id), test_user.id)
        result = notification_service.mark_as_read(str(notif.id), test_user.id)
        assert result is False

    def test_mark_as_read_invalid_id_returns_false(self, notification_service: NotificationService, test_user: User):
        """Should return False if notification not found."""
        result = notification_service.mark_as_read("99999999", test_user.id)
        assert result is False

    def test_mark_as_read_wrong_user_returns_false(self, notification_service: NotificationService, test_user: User, admin_user: User):
        """Should return False if user is not a recipient."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])
        result = notification_service.mark_as_read(str(notif.id), admin_user.id)
        assert result is False


class TestNotificationServiceMarkAllRead:
    """Tests for mark_all_read."""

    def test_mark_all_read_counts_updated_rows(self, notification_service: NotificationService, test_user: User):
        """Should return count of updated notifications."""
        notification_service.publish("type1", "T1", "M1", recipient_ids=[test_user.id])
        notification_service.publish("type2", "T2", "M2", recipient_ids=[test_user.id])
        notification_service.publish("type3", "T3", "M3", recipient_ids=[test_user.id])

        count = notification_service.mark_all_read(test_user.id)
        assert count == 3

        # Verify all are read
        unread = notification_service.get_notification_count(user_id=test_user.id, is_read=False)
        assert unread == 0

    def test_mark_all_read_with_some_already_read(self, notification_service: NotificationService, test_user: User):
        """Should only count and update unread notifications."""
        n1 = notification_service.publish("type", "T1", "M1", recipient_ids=[test_user.id])
        n2 = notification_service.publish("type", "T2", "M2", recipient_ids=[test_user.id])
        notification_service.mark_as_read(str(n1.id), test_user.id)

        count = notification_service.mark_all_read(test_user.id)
        assert count == 1  # Only n2

        remaining_unread = notification_service.get_notification_count(user_id=test_user.id, is_read=False)
        assert remaining_unread == 0


class TestNotificationServiceDeleteNotification:
    """Tests for delete_notification."""

    def test_delete_user_self_deletes_recipient_only(self, notification_service: NotificationService, test_user: User):
        """Non-admin user should delete only their recipient row; notification deleted if no recipients remain."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])
        result = notification_service.delete_notification(str(notif.id), test_user.id)
        assert result is True

        # Recipient should be deleted
        recipient = notification_service.db.query(NotificationRecipient).filter_by(
            notification_id=notif.id, user_id=test_user.id
        ).first()
        assert recipient is None

        # Notification should also be deleted (no recipients remain)
        from db.models import Notification
        notif_db = notification_service.db.query(Notification).filter_by(id=notif.id).first()
        assert notif_db is None

    def test_delete_user_recipient_only_not_deleted_globally(self, notification_service: NotificationService, test_user: User, admin_user: User):
        """If notification has multiple recipients, deleting one user's recipient should not delete notification."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id, admin_user.id])

        # test_user deletes their recipient
        result = notification_service.delete_notification(str(notif.id), test_user.id)
        assert result is True

        # test_user's recipient gone
        recipient1 = notification_service.db.query(NotificationRecipient).filter_by(user_id=test_user.id).first()
        assert recipient1 is None

        # admin's recipient still exists
        recipient2 = notification_service.db.query(NotificationRecipient).filter_by(user_id=admin_user.id).first()
        assert recipient2 is not None

        # Notification still exists
        from db.models import Notification
        notif_db = notification_service.db.query(Notification).filter_by(id=notif.id).first()
        assert notif_db is not None

    def test_delete_admin_global_delete(self, notification_service: NotificationService, admin_user: User, test_user: User):
        """Admin should delete all recipients and the notification itself."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id, admin_user.id])

        result = notification_service.delete_notification(str(notif.id), admin_user.id)
        assert result is True

        # All recipients should be deleted
        recipients = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id).all()
        assert len(recipients) == 0

        # Notification should be deleted
        from db.models import Notification
        notif_db = notification_service.db.query(Notification).filter_by(id=notif.id).first()
        assert notif_db is None

    def test_delete_unauthorized_returns_false(self, notification_service: NotificationService, test_user: User, admin_user: User):
        """Non-recipient user should return False."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])

        result = notification_service.delete_notification(str(notif.id), admin_user.id)
        assert result is False

    def test_delete_invalid_id_returns_false(self, notification_service: NotificationService, test_user: User):
        """Should return False for non-existent notification."""
        result = notification_service.delete_notification("99999999", test_user.id)
        assert result is False

    def test_delete_handles_exception(self, notification_service: NotificationService, test_user: User):
        """Should catch exception, rollback, and return False."""
        with patch.object(notification_service.db, 'delete', side_effect=Exception("DB error")):
            result = notification_service.delete_notification("some_id", test_user.id)
            assert result is False


class TestNotificationServiceCleanupOldNotifications:
    """Tests for cleanup_old_notifications."""

    def test_cleanup_deletes_only_old_notifications(self, notification_service: NotificationService, test_user: User):
        """Should delete notifications older than cutoff, keep recent ones."""
        now = datetime.utcnow()
        old_notif = notification_service.publish("type", "Old", "Msg", recipient_ids=[test_user.id])
        recent_notif = notification_service.publish("type", "Recent", "Msg", recipient_ids=[test_user.id])

        # Manually adjust created_at times
        notification_service.db.query(Notification).filter_by(id=old_notif.id).update(
            {"created_at": now - timedelta(days=40)}
        )
        notification_service.db.query(Notification).filter_by(id=recent_notif.id).update(
            {"created_at": now - timedelta(days=10)}
        )
        notification_service.db.flush()

        deleted = notification_service.cleanup_old_notifications(days=30)
        assert deleted == 1

        # Old notification gone
        from db.models import Notification
        assert notification_service.db.query(Notification).filter_by(id=old_notif.id).first() is None
        # Recent remains
        assert notification_service.db.query(Notification).filter_by(id=recent_notif.id).first() is not None

    def test_cleanup_deletes_all_when_all_old(self, notification_service: NotificationService, test_user: User):
        """Should delete all notifications if all older than cutoff."""
        now = datetime.utcnow()
        for i in range(3):
            n = notification_service.publish("type", f"Old {i}", "Msg", recipient_ids=[test_user.id])
            notification_service.db.query(Notification).filter_by(id=n.id).update(
                {"created_at": now - timedelta(days=60)}
            )
        notification_service.db.flush()

        deleted = notification_service.cleanup_old_notifications(days=30)
        assert deleted == 3

    def test_cleanup_returns_zero_when_no_old(self, notification_service: NotificationService, test_user: User):
        """Should return 0 if all notifications are recent."""
        # Create recent notification
        notification_service.publish("type", "Recent", "Msg", recipient_ids=[test_user.id])

        deleted = notification_service.cleanup_old_notifications(days=30)
        assert deleted == 0

    def test_cleanup_handles_exception(self, notification_service: NotificationService):
        """Should catch exception, rollback, and return 0."""
        with patch.object(notification_service.db, 'query', side_effect=Exception("DB error")):
            deleted = notification_service.cleanup_old_notifications(days=30)
            assert deleted == 0


class TestEmailRateLimiting:
    """Tests for email rate limiting (10 per user per rolling hour)."""

    def test_can_send_email_under_limit(self):
        """_can_send_email should return True for first 9 emails."""
        _email_timestamps.clear()
        user_id = 123
        now = time.time()

        # Simulate 9 sends
        for i in range(9):
            with patch('time.time', return_value=now):
                assert _can_send_email(user_id) is True

    def test_can_send_email_blocks_over_limit(self):
        """_can_send_email should return False after 10 emails in rolling hour."""
        _email_timestamps.clear()
        user_id = 123
        now = time.time()

        # Send 10 emails
        for i in range(10):
            with patch('time.time', return_value=now):
                assert _can_send_email(user_id) is True

        # 11th should be blocked
        with patch('time.time', return_value=now):
            assert _can_send_email(user_id) is False

    def test_can_send_email_allows_after_hour_passes(self):
        """_can_send_email should allow email after an hour from first send."""
        _email_timestamps.clear()
        user_id = 123
        now = time.time()

        # Send 10 emails at t=0
        for i in range(10):
            with patch('time.time', return_value=now):
                _can_send_email(user_id)

        # At t=3601 (1 hour + 1 sec later), first email falls out of window, should allow
        later = now + 3601
        with patch('time.time', return_value=later):
            assert _can_send_email(user_id) is True

    def test_can_send_email_rolls_window_forward(self):
        """_can_send_email should keep window rolling as time advances."""
        _email_timestamps.clear()
        user_id = 123
        base = time.time()

        # Send 5 emails
        for i in range(5):
            with patch('time.time', return_value=base + i * 10):
                _can_send_email(user_id)

        # After 1 hour, earliest should fall out, allowing new send
        with patch('time.time', return_value=base + 3600):
            assert _can_send_email(user_id) is True
