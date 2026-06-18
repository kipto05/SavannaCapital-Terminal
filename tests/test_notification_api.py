"""Tests for notification API endpoints.

Endpoints tested:
- GET /api/v3/notifications (list with pagination, filters)
- POST /api/v3/notifications (admin create)
- PATCH /api/v3/notifications/{notification_id}/read
- POST /api/v3/notifications/mark-all-read
- DELETE /api/v3/notifications/{notification_id}
- GET /api/v3/notifications/settings
- PATCH /api/v3/notifications/settings
- POST /api/v3/notifications/send-test

Also tests:
- Unauthenticated access returns 401
- Admin-only endpoints return 403 for regular users
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from db.models import NotificationSettings


class TestListNotifications:
    """Tests for GET /api/v3/notifications."""

    def test_list_notifications_requires_auth(self, client: TestClient, db: Session, test_user: User):
        """Unauthenticated request should return 401."""
        response = client.get("/api/v3/notifications")
        assert response.status_code == 401

    def test_list_notifications_returns_paginated_results(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should return paginated list of notifications."""
        # Create 5 notifications
        for i in range(5):
            notification_service.publish(f"type{i}", f"Title {i}", f"Msg {i}", recipient_ids=[test_user.id])

        response = client.get("/api/v3/notifications?page=1&limit=3")
        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 1
        assert data["size"] == 3
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["unread_count"] == 5

        # Items should be ordered by created_at desc
        for item in data["items"]:
            assert "id" in item
            assert "type" in item
            assert "title" in item
            assert "message" in item
            assert "created_at" in item
            assert "is_read" in item
            assert "read_at" in item

    def test_list_notifications_pagination_page2(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Page 2 should return correct subset."""
        for i in range(4):
            notification_service.publish("type", f"Title {i}", "Msg", recipient_ids=[test_user.id])

        response = client.get("/api/v3/notifications?page=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["size"] == 2
        assert data["total"] == 4
        assert len(data["items"]) == 2

    def test_list_notifications_filter_is_read(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Filter by is_read should work."""
        n1 = notification_service.publish("type", "Unread", "Msg", recipient_ids=[test_user.id])
        n2 = notification_service.publish("type", "Read", "Msg", recipient_ids=[test_user.id])
        notification_service.mark_as_read(str(n2.id), test_user.id)

        # Get unread only
        response = client.get("/api/v3/notifications?is_read=false")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Unread"

        # Get read only
        response = client.get("/api/v3/notifications?is_read=true")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Read"

    def test_list_notifications_filter_type(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Filter by type should work."""
        notification_service.publish("type_a", "A", "Msg", recipient_ids=[test_user.id])
        notification_service.publish("type_b", "B", "Msg", recipient_ids=[test_user.id])

        response = client.get("/api/v3/notifications?type=type_a")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "type_a"

    def test_list_notifications_empty(self, client: TestClient, override_current_user):
        """Should return empty list when user has no notifications."""
        response = client.get("/api/v3/notifications")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_notifications_invalid_pagination_params(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Invalid page/limit should be validated by FastAPI."""
        response = client.get("/api/v3/notifications?page=0")
        assert response.status_code == 422  # validation error


class TestCreateNotification:
    """Tests for POST /api/v3/notifications (admin only)."""

    def test_create_notification_requires_admin(self, client: TestClient, test_user: User, override_current_user):
        """Regular user should get 403."""
        payload = {
            "user_id": test_user.id,
            "type": "test",
            "title": "Test",
            "message": "Test message"
        }
        response = client.post("/api/v3/notifications", json=payload)
        assert response.status_code == 403

    def test_create_notification_admin_success(self, client: TestClient, admin_user: User, test_user: User, notification_service: NotificationService, override_admin_user):
        """Admin should be able to create notification for another user."""
        payload = {
            "user_id": test_user.id,
            "type": "order_placed",
            "title": "Order Placed",
            "message": "Your order was placed",
            "data": {"order_id": 123}
        }
        response = client.post("/api/v3/notifications", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "id" in data

        # Verify notification created
        notif = notification_service.db.query(Notification).get(uuid.UUID(data["id"]))
        assert notif is not None
        assert notif.type == "order_placed"
        assert notif.title == "Order Placed"

    def test_create_notification_invalid_payload(self, client: TestClient, admin_user: User, override_admin_user):
        """Invalid payload should return 422 (validation error)."""
        payload = {
            "user_id": 1,
            "type": "",  # empty not allowed
            "title": "Test",
            "message": "Test"
        }
        response = client.post("/api/v3/notifications", json=payload)
        assert response.status_code == 422

    def test_create_notification_fails_on_service_error(self, client: TestClient, admin_user: User, override_admin_user, notification_service: NotificationService):
        """If service returns None, should return 500."""
        with patch.object(notification_service, 'publish', return_value=None):
            payload = {
                "user_id": 1,
                "type": "test",
                "title": "Test",
                "message": "Test"
            }
            response = client.post("/api/v3/notifications", json=payload)
            assert response.status_code == 500


class TestMarkNotificationRead:
    """Tests for PATCH /api/v3/notifications/{notification_id}/read."""

    def test_mark_notification_read_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.patch("/api/v3/notifications/123/read", json={"is_read": True})
        assert response.status_code == 401

    def test_mark_notification_read_valid(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should mark notification as read and return success."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])

        response = client.patch(f"/api/v3/notifications/{notif.id}/read", json={"is_read": True})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify in service
        is_read = notification_service.mark_as_read(str(notif.id), test_user.id)
        # The operation already succeeded, so can't call again to verify; query directly
        recipient = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id).first()
        assert recipient.is_read is True

    def test_mark_notification_read_false_rejected(self, client: TestClient, test_user: User, override_current_user):
        """is_read=false should return 400."""
        response = client.patch("/api/v3/notifications/123/read", json={"is_read": False})
        assert response.status_code == 400
        assert "is_read must be true" in response.json()["detail"]

    def test_mark_notification_read_not_found(self, client: TestClient, test_user: User, override_current_user):
        """Non-existent notification should return 404."""
        response = client.patch("/api/v3/notifications/999/read", json={"is_read": True})
        assert response.status_code == 404

    def test_mark_notification_read_already_read(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Marking already read notification should return 404."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])
        notification_service.mark_as_read(str(notif.id), test_user.id)

        response = client.patch(f"/api/v3/notifications/{notif.id}/read", json={"is_read": True})
        assert response.status_code == 404


class TestMarkAllRead:
    """Tests for POST /api/v3/notifications/mark-all-read."""

    def test_mark_all_read_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.post("/api/v3/notifications/mark-all-read")
        assert response.status_code == 401

    def test_mark_all_read_success(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should mark all user's notifications as read and return count."""
        notification_service.publish("type", "T1", "M1", recipient_ids=[test_user.id])
        notification_service.publish("type", "T2", "M2", recipient_ids=[test_user.id])
        notification_service.publish("type", "T3", "M3", recipient_ids=[test_user.id])

        response = client.post("/api/v3/notifications/mark-all-read")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 3

    def test_mark_all_read_with_some_already_read(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should only update unread notifications."""
        n1 = notification_service.publish("type", "T1", "M1", recipient_ids=[test_user.id])
        n2 = notification_service.publish("type", "T2", "M2", recipient_ids=[test_user.id])
        notification_service.mark_as_read(str(n1.id), test_user.id)

        response = client.post("/api/v3/notifications/mark-all-read")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1

    def test_mark_all_read_empty(self, client: TestClient, override_current_user):
        """Should return count 0 if no notifications."""
        response = client.post("/api/v3/notifications/mark-all-read")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


class TestDeleteNotification:
    """Tests for DELETE /api/v3/notifications/{notification_id}."""

    def test_delete_notification_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.delete("/api/v3/notifications/123")
        assert response.status_code == 401

    def test_delete_own_notification_success(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """User should be able to delete own notification."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])

        response = client.delete(f"/api/v3/notifications/{notif.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Recipient and notification should be deleted
        recipient = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id).first()
        assert recipient is None

    def test_delete_notification_not_authorized(self, client: TestClient, notification_service: NotificationService, test_user: User, admin_user: User, override_admin_user):
        """Non-recipient should return 404."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])

        response = client.delete(f"/api/v3/notifications/{notif.id}")
        assert response.status_code == 404

    def test_delete_notification_not_found(self, client: TestClient, test_user: User, override_current_user):
        """Non-existent notification should return 404."""
        response = client.delete("/api/v3/notifications/999999")
        assert response.status_code == 404

    def test_admin_can_delete_any_notification(self, client: TestClient, notification_service: NotificationService, admin_user: User, test_user: User, override_admin_user):
        """Admin should be able to delete any notification."""
        notif = notification_service.publish("type", "Title", "Msg", recipient_ids=[test_user.id])

        response = client.delete(f"/api/v3/notifications/{notif.id}")
        assert response.status_code == 200

        # Notification should be fully deleted
        from db.models import Notification
        notif_db = notification_service.db.query(Notification).filter_by(id=notif.id).first()
        assert notif_db is None


class TestGetNotificationSettings:
    """Tests for GET /api/v3/notifications/settings."""

    def test_get_settings_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.get("/api/v3/notifications/settings")
        assert response.status_code == 401

    def test_get_settings_returns_list(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user, seeded_settings):
        """Should return list of notification settings."""
        response = client.get("/api/v3/notifications/settings")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2  # from seeded_settings

        for setting in data:
            assert "user_id" in setting
            assert "event_type" in setting
            assert "in_app_enabled" in setting
            assert "email_enabled" in setting

    def test_get_settings_empty(self, client: TestClient, db: Session, test_user: User, override_current_user):
        """Should return empty list if no settings."""
        # Delete any existing settings
        db.query(NotificationSettings).delete()
        db.commit()

        response = client.get("/api/v3/notifications/settings")
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestUpdateNotificationSettings:
    """Tests for PATCH /api/v3/notifications/settings."""

    def test_update_settings_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.patch("/api/v3/notifications/settings", json={"settings": []})
        assert response.status_code == 401

    def test_update_settings_valid(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should update settings for user."""
        payload = {
            "settings": [
                {"event_type": "strategy_signal", "in_app_enabled": True, "email_enabled": False},
                {"event_type": "order_placed", "in_app_enabled": True, "email_enabled": True},
            ]
        }

        response = client.patch("/api/v3/notifications/settings", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Verify in DB
        settings = notification_service.db.query(NotificationSettings).filter_by(user_id=test_user.id).all()
        assert len(settings) == 2
        event_types = {s.event_type for s in settings}
        assert "strategy_signal" in event_types
        assert "order_placed" in event_types

    def test_update_settings_duplicate_event_types_rejected(self, client: TestClient, test_user: User, override_current_user):
        """Duplicate event_type should return 400."""
        payload = {
            "settings": [
                {"event_type": "strategy_signal", "in_app_enabled": True, "email_enabled": False},
                {"event_type": "strategy_signal", "in_app_enabled": False, "email_enabled": True},
            ]
        }
        response = client.patch("/api/v3/notifications/settings", json=payload)
        assert response.status_code == 400
        assert "Duplicate event types" in response.json()["detail"]

    def test_update_settings_clears_existing(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user, seeded_settings):
        """Patch should replace all settings for user."""
        # Initially have 2 settings (from seeded_settings)
        assert len(seeded_settings) == 2

        # Update with 1 setting
        payload = {
            "settings": [
                {"event_type": "new_event", "in_app_enabled": False, "email_enabled": False},
            ]
        }
        response = client.patch("/api/v3/notifications/settings", json=payload)
        assert response.status_code == 200

        # Should have only 1 setting now
        settings = notification_service.db.query(NotificationSettings).filter_by(user_id=test_user.id).all()
        assert len(settings) == 1
        assert settings[0].event_type == "new_event"

    def test_update_settings_invalid_types(self, client: TestClient, test_user: User, override_current_user):
        """Non-boolean values for in_app_enabled/email_enabled should be rejected by pydantic."""
        payload = {
            "settings": [
                {"event_type": "test", "in_app_enabled": "yes", "email_enabled": False},  # string instead of bool
            ]
        }
        response = client.patch("/api/v3/notifications/settings", json=payload)
        assert response.status_code == 422  # Validation error


class TestSendTestNotification:
    """Tests for POST /api/v3/notifications/send-test."""

    def test_send_test_requires_auth(self, client: TestClient):
        """Unauthenticated should return 401."""
        response = client.post("/api/v3/notifications/send-test")
        assert response.status_code == 401

    def test_send_test_creates_notification(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should create a test notification."""
        response = client.post("/api/v3/notifications/send-test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify notification created
        notif = notification_service.db.query(Notification).order_by(Notification.created_at.desc()).first()
        assert notif is not None
        assert notif.type == "test"
        assert "Test Notification" in notif.title
        assert notif.message == "This is a test notification."

        # Verify recipient exists
        from db.models import NotificationRecipient
        recipient = notification_service.db.query(NotificationRecipient).filter_by(notification_id=notif.id, user_id=test_user.id).first()
        assert recipient is not None

    def test_send_test_triggers_email_thread(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """Should start async email thread."""
        with patch.object(notification_service, '_send_emails_async') as mock_send:
            response = client.post("/api/v3/notifications/send-test")
            assert response.status_code == 200

            # Verify _send_emails_async was called with notification id and recipient
            assert mock_send.called
            args = mock_send.call_args[0]
            assert isinstance(args[0], int)  # notification_id
            assert args[1] == [test_user.id]

    def test_send_test_fails_on_service_error(self, client: TestClient, notification_service: NotificationService, test_user: User, override_current_user):
        """If publish returns None, should return 500."""
        with patch.object(notification_service, 'publish', return_value=None):
            response = client.post("/api/v3/notifications/send-test")
            assert response.status_code == 500
