from __future__ import annotations

import logging
import threading
import time
import smtplib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader

from config.settings import config
from db.session import SessionLocal
from db.models import Notification, NotificationRecipient, NotificationSettings, User

log = logging.getLogger(__name__)

# Email rate limiting: max emails per user per rolling window
_email_timestamps: dict[int, list[float]] = {}
_email_lock = threading.Lock()


def _can_send_email(user_id: int) -> bool:
    now = time.time()
    window = config.notification.rate_limit_window_seconds
    limit = config.notification.max_emails_per_hour
    cutoff = now - window
    with _email_lock:
        timestamps = _email_timestamps.setdefault(user_id, [])
        timestamps[:] = [ts for ts in timestamps if ts >= cutoff]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def _send_emails_async(self, notification_id: int, recipient_user_ids: list[int]):
        def worker():
            db = SessionLocal()
            try:
                notification = db.query(Notification).get(notification_id)
                if not notification:
                    log.warning("Email worker: notification not found: %s", notification_id)
                    return
                for uid in recipient_user_ids:
                    try:
                        setting = db.query(NotificationSettings).filter_by(user_id=uid, event_type=notification.type).first()
                        if not setting or not setting.email_enabled:
                            continue
                        user = db.query(User).get(uid)
                        if not user or not user.username:
                            continue
                        if not _can_send_email(uid):
                            log.warning("Email rate limit exceeded for user=%s", uid)
                            continue
                        env = Environment(loader=FileSystemLoader('dashboard/templates'))
                        template = env.get_template('emails/notification.html')
                        link = getattr(config.dashboard, 'base_url', None) or "/notifications"
                        html = template.render(notification=notification, user=user, link=link)
                        msg = MIMEText(html, 'html', 'utf-8')
                        msg['Subject'] = f"Savanna Capital: {notification.title}"
                        msg['From'] = config.smtp.from_email
                        msg['To'] = user.username
                        with smtplib.SMTP(config.smtp.host, config.smtp.port) as server:
                            if config.smtp.use_tls:
                                server.starttls()
                            if config.smtp.username and config.smtp.password:
                                server.login(config.smtp.username, config.smtp.password)
                            server.send_message(msg)
                        log.info("Email sent: notification=%s to=%s", notification_id, user.username)
                    except Exception:
                        log.exception("Email send failed for user=%s notification=%s", uid, notification_id)
            finally:
                db.close()
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def publish(
        self,
        event_type: str,
        title: str,
        message: str,
        data: Optional[dict] = None,
        recipient_ids: List[int] = None,
    ) -> Optional[Notification]:
        try:
            notification = Notification(
                type=event_type,
                title=title,
                message=message,
                data=data,
                created_at=datetime.utcnow(),
            )
            self.db.add(notification)
            self.db.flush()  # get ID

            if recipient_ids is None:
                settings = self.db.query(NotificationSettings).filter_by(event_type=event_type, in_app_enabled=True).all()
                recipient_user_ids = [s.user_id for s in settings]
            else:
                recipient_user_ids = recipient_ids

            for uid in recipient_user_ids:
                recipient = NotificationRecipient(
                    notification_id=notification.id,
                    user_id=uid,
                    is_read=False,
                )
                self.db.add(recipient)

            self.db.commit()
            log.info("Notification published: id=%s type=%s recipients=%d", notification.id, event_type, len(recipient_user_ids))
            # Trigger async emails if SMTP configured
            if config.smtp.host:
                try:
                    self._send_emails_async(notification.id, recipient_user_ids)
                except Exception as exc:
                    log.exception("Failed to start email thread: %s", exc)
            return notification
        except Exception as exc:
            log.exception("NotificationService.publish failed: type=%s", event_type)
            self.db.rollback()
            return None

    def get_user_notifications(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            query = self.db.query(NotificationRecipient).join(Notification).filter(NotificationRecipient.user_id == user_id)
            if is_read is not None:
                query = query.filter(NotificationRecipient.is_read == is_read)
            if type is not None:
                query = query.filter(Notification.type == type)
            rows = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
            result = []
            for row in rows:
                n = row.notification
                result.append({
                    'id': str(n.id),
                    'type': n.type,
                    'title': n.title,
                    'message': n.message,
                    'data': n.data,
                    'created_at': n.created_at,
                    'read_at': row.read_at,
                    'is_read': row.is_read,
                })
            return result
        except Exception as exc:
            log.exception("NotificationService.get_user_notifications failed: user=%s", user_id)
            return []

    def get_notification_count(
        self,
        user_id: int,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
    ) -> int:
        try:
            query = self.db.query(NotificationRecipient).join(Notification).filter(NotificationRecipient.user_id == user_id)
            if is_read is not None:
                query = query.filter(NotificationRecipient.is_read == is_read)
            if type is not None:
                query = query.filter(Notification.type == type)
            return query.count()
        except Exception as exc:
            log.exception("NotificationService.get_notification_count failed: user=%s", user_id)
            return 0

    def mark_as_read(self, notification_id: str, user_id: int) -> bool:
        try:
            notif_uuid = UUID(notification_id)
            recipient = self.db.query(NotificationRecipient).filter_by(notification_id=notif_uuid, user_id=user_id).first()
            if recipient is None or recipient.is_read:
                return False
            recipient.is_read = True
            recipient.read_at = datetime.utcnow()
            self.db.commit()
            log.info("Notification marked read: user=%s notification_id=%s", user_id, notification_id)
            return True
        except Exception as exc:
            log.exception("NotificationService.mark_as_read failed: notification_id=%s user=%s", notification_id, user_id)
            self.db.rollback()
            return False

    def mark_all_read(self, user_id: int) -> int:
        try:
            count = self.db.query(NotificationRecipient).filter_by(user_id=user_id, is_read=False).update(
                {'is_read': True, 'read_at': datetime.utcnow()}, synchronize_session=False
            )
            self.db.commit()
            log.info("All notifications marked read for user=%s count=%d", user_id, count)
            return count
        except Exception as exc:
            log.exception("NotificationService.mark_all_read failed: user=%s", user_id)
            self.db.rollback()
            return 0

    def delete_notification(self, notification_id: str, requesting_user_id: int) -> bool:
        try:
            requester = self.db.query(User).filter_by(id=requesting_user_id).first()
            if requester is None:
                log.warning('Delete notification: requester not found: user=%s', requesting_user_id)
                return False

            notif_uuid = UUID(notification_id)

            # Admin can delete the entire notification globally
            if requester.is_admin:
                # Delete all recipient rows first
                self.db.query(NotificationRecipient).filter_by(notification_id=notif_uuid).delete(synchronize_session=False)
                # Then delete the notification itself
                notification = self.db.query(Notification).filter_by(id=notif_uuid).first()
                if notification:
                    self.db.delete(notification)
                self.db.commit()
                log.info('Notification deleted globally by admin: id=%s by=%s', notification_id, requesting_user_id)
                return True

            # Non-admin: user must be a recipient; delete their single recipient record
            recipient = self.db.query(NotificationRecipient).filter_by(notification_id=notif_uuid, user_id=requesting_user_id).first()
            if recipient is None:
                log.warning('Delete notification: not authorized (not a recipient): user=%s notification=%s', requesting_user_id, notification_id)
                return False

            self.db.delete(recipient)
            # Conditionally delete notification if no recipients remain
            remaining = self.db.query(NotificationRecipient).filter_by(notification_id=notif_uuid).count()
            if remaining == 0:
                notification = self.db.query(Notification).filter_by(id=notif_uuid).first()
                if notification:
                    self.db.delete(notification)
            self.db.commit()
            log.info('Notification deleted (user recipient): id=%s by=%s', notification_id, requesting_user_id)
            return True
        except Exception as exc:
            log.exception('NotificationService.delete_notification failed: notification=%s user=%s', notification_id, requesting_user_id)
            self.db.rollback()
            return False

    def cleanup_old_notifications(self, days: int) -> int:
        """Delete notifications older than the specified number of days.

        Args:
            days: Retention period in days. Notifications older than this are deleted.

        Returns:
            Number of notifications deleted.
        """
        if days <= 0:
            log.warning("cleanup_old_notifications: invalid days=%d, skipping", days)
            return 0
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            # Find IDs of old notifications
            old_ids = [n.id for n in self.db.query(Notification.id).filter(Notification.created_at < cutoff).all()]
            if not old_ids:
                return 0
            # Delete recipient rows first (FK constraint)
            self.db.query(NotificationRecipient).filter(NotificationRecipient.notification_id.in_(old_ids)).delete(synchronize_session=False)
            # Delete notifications
            count = self.db.query(Notification).filter(Notification.id.in_(old_ids)).delete(synchronize_session=False)
            self.db.commit()
            log.info("Notification cleanup: deleted %d notifications (older than %d days)", count, days)
            return count
        except Exception as exc:
            log.exception("Notification cleanup failed: %s", exc)
            self.db.rollback()
            return 0
