from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth.router import _get_current_user
from db.models import User, NotificationSettings
from db.session import get_db
from execution.notification_service import NotificationService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v3/notifications")

class NotificationItemResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    is_read: bool

    model_config = ConfigDict(from_attributes=False)

class NotificationCreate(BaseModel):
    user_id: int
    type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    data: Optional[Dict[str, Any]] = None

class NotificationListResponse(BaseModel):
    items: List[NotificationItemResponse]
    total: int
    unread_count: int
    page: int
    size: int

class NotificationSettingItem(BaseModel):
    event_type: str
    in_app_enabled: bool = True
    email_enabled: bool = False

class NotificationSettingsResponse(BaseModel):
    user_id: int
    event_type: str
    in_app_enabled: bool
    email_enabled: bool

    model_config = ConfigDict(from_attributes=True)

class NotificationSettingsUpdate(BaseModel):
    settings: List[NotificationSettingItem]

class MarkReadRequest(BaseModel):
    is_read: bool

@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = Query(None),
    type: Optional[str] = Query(None),
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("List notifications: user=%s page=%s limit=%s is_read=%s type=%s", current_user.id, page, limit, is_read, type)
    service = NotificationService(db)
    offset = (page - 1) * limit
    items_data = service.get_user_notifications(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        is_read=is_read,
        type=type,
    )
    total = service.get_notification_count(user_id=current_user.id, is_read=is_read, type=type)
    unread_total = service.get_notification_count(user_id=current_user.id, is_read=False, type=type)
    return {
        "items": items_data,
        "total": total,
        "unread_count": unread_total,
        "page": page,
        "size": limit,
    }

@router.post("/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(
    body: NotificationCreate,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        log.warning("Notification create unauthorized: user=%s", current_user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    log.info("Create notification (admin): user=%s target_user=%s type=%s", current_user.id, body.user_id, body.type)
    service = NotificationService(db)
    notif = service.publish(
        event_type=body.type,
        title=body.title,
        message=body.message,
        data=body.data,
        recipient_ids=[body.user_id],
    )
    if not notif:
        raise HTTPException(status_code=500, detail="Failed to create notification")
    return {"success": True, "id": str(notif.id)}

@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    body: MarkReadRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    if not body.is_read:
        raise HTTPException(status_code=400, detail="is_read must be true")
    log.info("Mark notification read: user=%s notification_id=%s", current_user.id, notification_id)
    service = NotificationService(db)
    if not service.mark_as_read(notification_id, current_user.id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}

@router.post("/mark-all-read")
def mark_all_read(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("Mark all read: user=%s", current_user.id)
    service = NotificationService(db)
    count = service.mark_all_read(current_user.id)
    return {"success": True, "count": count}

@router.delete("/{notification_id}")
def delete_notification(
    notification_id: str,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("Delete notification: user=%s notification_id=%s", current_user.id, notification_id)
    service = NotificationService(db)
    if not service.delete_notification(notification_id, current_user.id):
        raise HTTPException(status_code=404, detail="Notification not found or unauthorized")
    return {"success": True}

@router.get("/settings", response_model=List[NotificationSettingsResponse])
def get_settings(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("Get notification settings: user=%s", current_user.id)
    settings = db.query(NotificationSettings).filter_by(user_id=current_user.id).all()
    return settings

@router.patch("/settings")
def update_settings(
    body: NotificationSettingsUpdate,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("Update notification settings: user=%s entries=%d", current_user.id, len(body.settings))

    # Check for duplicate event_type entries
    event_types = [s.event_type for s in body.settings]
    if len(set(event_types)) != len(event_types):
        raise HTTPException(status_code=400, detail="Duplicate event types not allowed")

    db.query(NotificationSettings).filter_by(user_id=current_user.id).delete()
    new_settings = []
    for item in body.settings:
        ns = NotificationSettings(
            user_id=current_user.id,
            event_type=item.event_type,
            in_app_enabled=item.in_app_enabled,
            email_enabled=item.email_enabled,
        )
        db.add(ns)
        new_settings.append(ns)
    db.commit()
    return new_settings

@router.post("/send-test")
def send_test(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
):
    log.info("Send test notification: user=%s", current_user.id)
    service = NotificationService(db)
    notif = service.publish(
        event_type="test",
        title="Test Notification",
        message="This is a test notification.",
        recipient_ids=[current_user.id],
    )
    if not notif:
        raise HTTPException(status_code=500, detail="Failed to create test notification")
    return {"success": True}
