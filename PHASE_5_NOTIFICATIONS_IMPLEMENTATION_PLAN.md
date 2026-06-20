# Phase 5: Notifications System — Implementation Plan

**Generated:** 2025-06-17  
**Branch:** v3-dashboard  
**Reference:** V3_SEQUENTIAL_BUILD_PLAN.md, V3_FRONTEND_REDESIGN_PLAN.md, CLAUDE.md design tokens

---

## 1. Overview

Implement a comprehensive notification system that:
- Persists notifications in database with user-specific read/unread state
- Provides real-time in-app alerts via a top bar bell dropdown (resizable, filter toggle, localStorage)
- Offers a full notifications history page with filters, bulk actions, pagination
- Sends email digests for important notifications (configurable per event type)
- Integrates with Settings page for per-event-type preferences
- Supports retention and cleanup policies
- Is instrumented across all core modules (trading engine, backtest, ML, AI, strategy registry, platform errors)

The system must follow the existing architecture: FastAPI routes, SQLAlchemy ORM, Alembic migrations, JWT auth, Material Design 3 frontend tokens, and Chart.js where applicable.

---

## 2. Database Schema

### Table: `notifications`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `postgresql.UUID(as_uuid=True)`, server default `gen_random_uuid()` |
| type | VARCHAR(50) | NOT NULL, e.g., 'trade_executed', 'backtest_complete', 'ai_suggestion', 'ml_model_trained', 'strategy_toggled', 'error', 'custom' |
| title | VARCHAR(255) | NOT NULL |
| message | TEXT | NOT NULL |
| data | JSON | NULLABLE, extra context (trade_id, backtest_run_id, strategy_name, etc.) |
| created_at | TIMESTAMPTZ | NOT NULL, server default `NOW()` |
| expires_at | TIMESTAMPTZ | NULLABLE, determined by retention policy |

Indexes:
- `idx_notifications_created_at` on `notifications(created_at)` (for cleanup queries)

### Table: `notification_recipients`

| Column | Type | Constraints |
|--------|------|-------------|
| notification_id | UUID (PK, FK) | REFERENCES `notifications(id)` ON DELETE CASCADE |
| user_id | UUID (PK, FK) | REFERENCES `users(id)` ON DELETE CASCADE |
| is_read | BOOLEAN | NOT NULL DEFAULT FALSE |
| read_at | TIMESTAMPTZ | NULLABLE |
| delivered_at | TIMESTAMPTZ | NULLABLE (when in-app notification was shown) |
| email_sent_at | TIMESTAMPTZ | NULLABLE |

Composite primary key: `(notification_id, user_id)`

Indexes:
- `idx_notification_recipients_user_id_is_read` on `notification_recipients(user_id, is_read)` (for unread count queries)
- `idx_notification_recipients_notification_id` on `notification_recipients(notification_id)` (for cleanup joins)

### Table: `notification_settings`

| Column | Type | Constraints |
|--------|------|-------------|
| user_id | UUID (PK, FK) | REFERENCES `users(id)` ON DELETE CASCADE |
| event_type | VARCHAR(50) (PK) | NOT NULL, matches `notifications.type` |
| in_app_enabled | BOOLEAN | NOT NULL DEFAULT TRUE |
| email_enabled | BOOLEAN | NOT NULL DEFAULT FALSE |

Primary key: `(user_id, event_type)`

Indexes:
- `idx_notification_settings_user_id` on `notification_settings(user_id)`

---

## 3. Service Layer

### `NotificationService`

Location: `notifications/service.py` (new module)

```python
class NotificationService:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.user = current_user

    def publish(
        self,
        event_type: str,
        title: str,
        message: str,
        data: dict | None = None,
        recipient_ids: list[UUID] | None = None,
    ) -> Notification:
        """
        Create a notification and fan-out to recipients.
        If recipient_ids is None, broadcast to all active users.
        Returns the created Notification.
        """
        # create notification row
        # create NotificationRecipient rows for each recipient
        # respects user's in_app_enabled setting (skip if disabled)
        # return notification
```

Other methods:
- `mark_read(notification_id: UUID) -> None`
- `mark_all_read() -> int` (number marked)
- `get_unread_count() -> int`
- `get_page(filters: dict) -> tuple[list[NotificationRecipient], int]` (items + total)
- `delete(notification_id: UUID) -> None` (deletes recipient row; cascades to notification if no other recipients)
- `cleanup_expired(batch_size: int = 1000) -> int` (number deleted)

### `AsyncEmailService`

Location: `notifications/email.py` (new module)

- SMTP configuration from `config.settings.SMTP_*`
- Queue: `asyncio.Queue` of email dicts (to, subject, html_body)
- Background worker task running in FastAPI startup (or APScheduler)
- Rate limiting: per-user bucket (max emails per hour, config from env `NOTIFICATIONS_EMAIL_RATE_LIMIT=10`)
- Sends via `aiosmtplib`
- On failure: log error, retry once, then discard (avoid blocking)

---

## 4. API Endpoints (FastAPI, JWT protected)

All endpoints under `/api/v3/notifications` (new router). Use `Depends(get_current_user)`.

### GET `/api/v3/notifications`

Query parameters:
- `page` (int, default 1)
- `limit` (int, default 20)
- `is_read` (bool, optional filter)
- `type` (string, optional filter, one of known types)
- `sort` (string, default `-created_at` for descending)

Response:
```json
{
  "items": [
    {
      "id": "...",
      "type": "...",
      "title": "...",
      "message": "...",
      "data": {...},
      "created_at": "2025-06-17T12:34:56Z",
      "is_read": false
    }
  ],
  "total": 150,
  "unread_count": 5
}
```

### PATCH `/api/v3/notifications/{id}/read`

Body:
```json
{ "is_read": true }
```
Response: `{ "success": true }`

### POST `/api/v3/notifications/mark-all-read`

Response:
```json
{ "success": true, "count": 23 }
```

### DELETE `/api/v3/notifications/{id}`

Response:
```json
{ "success": true }
```

### GET `/api/v3/notifications/settings`

Response:
```json
{
  "settings": [
    { "event_type": "trade_executed", "in_app_enabled": true, "email_enabled": false },
    ...
  ]
}
```

### PUT `/api/v3/notifications/settings`

Body:
```json
{
  "settings": [
    { "event_type": "trade_executed", "in_app_enabled": true, "email_enabled": true },
    ...
  ]
}
```
Response: `{ "success": true }`

### POST `/api/v3/notifications/send-test`

Body (optional):
```json
{ "email": "user@example.com" }
```
Triggers a test notification and email (if email_enabled). Response: `{ "success": true }`

---

## 5. Frontend Components

### Top Bar Bell Dropdown

**Template:** Extend `dashboard/templates/v3/_topbar.html`:

- Add Material Symbol "notifications" icon with badge showing unread count.
- Badge: absolute positioned red circle with white number.
- Dropdown panel (absolute, top-full, right-0, mt-2) with:
  - Header: "Notifications" + "Mark all read" link
  - Toggle: "Show read" switch (persisted in localStorage key `notifications_show_read`)
  - List: `<ul>` of items, each with title, message snippet, timestamp, unread dot.
  - Footer: "View all" → `/v3/notifications`
- Drag handle at right edge to resize horizontally. Width persisted in localStorage key `notifications_dropdown_width` (default 380px).
- Polling: every `config.dashboard.poll_interval_ms` (30s) fetch unread count and latest notifications; update badge and list (prepend new items).
- Click outside to close; ESC to close.

**JavaScript:** Modify `dashboard/static/v3/components/topbar.js` or create `notifications.js` to manage dropdown state, resize, filtering, polling.

### Full Notifications Page

**Route:** `/v3/notifications` (or `/notifications`)

**Template:** `dashboard/templates/v3/pages/notifications.html`

- Header: Title, filter row (type select, read/unread toggle, date range picker), bulk actions (Mark all read, Delete selected)
- Main: container with infinite scroll or pagination controls (page numbers, next/prev)
- Each notification item: card-like, expands to show full message and data JSON (pretty print). Actions: toggle read, delete.
- Empty state: illustration + "No notifications"
- Responsive: full width on mobile, max-width-4xl centered on desktop.

**JavaScript:** `dashboard/static/v3/pages/notifications.js`:

- `init()`: load settings, bind filters, load first page
- `loadPage(page)`: fetch with current filters, render list, update pagination
- `renderItem(notif)`: create DOM element with classes
- `markRead(id, isRead)`: PATCH
- `delete(id)`: DELETE, remove from DOM
- `markAllRead()`: POST
- Polling for unread count in top bar should be coordinated; maybe a shared service.

---

## 6. Email Integration

**SMTP Config (.env):**
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM="Savanna Capital <noreply@savannacapital.com>"
SMTP_USE_TLS=true
NOTIFICATIONS_EMAIL_RATE_LIMIT=10
NOTIFICATIONS_EMAIL_ENABLED=true
```

**Config:** Add to `config/settings.py` under an `email` or `notifications` namespace.

**HTML Template:** `dashboard/templates/v3/emails/notification.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: 'Geist', sans-serif; color: #1F2937; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: #0D1B2A; color: white; padding: 20px; text-align: center; }
    .content { padding: 20px; }
    .footer { font-size: 12px; color: #6B7280; text-align: center; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>Savanna Capital</h1></div>
    <div class="content">
      <h2>{{title}}</h2>
      <p>{{message}}</p>
      <p><a href="{{action_url}}">View in app</a></p>
    </div>
    <div class="footer">
      <p>You received this email because you have in-app notifications enabled.</p>
      <p><a href="{{unsubscribe_url}}">Unsubscribe from email notifications</a></p>
    </div>
  </div>
</body>
</html>
```

**AsyncEmailService:**
- Initialize on startup: read SMTP config, create queue, spawn worker task.
- Worker: `while True: email = await queue.get(); send via aiosmtplib; handle errors`.
- Integration: When `NotificationService.publish` is called and any recipient has `email_enabled` for the event type, enqueue an email with appropriate template.

**Rate Limiting:** Track per-user email timestamps in memory dict (or Redis if available). If user exceeds limit, skip email and log.

---

## 7. Instrumentation Points

Call `NotificationService.publish` in the following modules (ensure failures are caught and logged, never block main flow):

| Module | Event | Type | Data payload |
|--------|-------|------|--------------|
| `execution/order_manager.py` | Position opened/closed, order filled/rejected, SL/TP hit | `trade_executed`, `order_filled`, `order_rejected` | `{ "trade_id": ..., "symbol": ..., "side": ..., "pnl": ... }` |
| `quant/backtest_engine.py` | Backtest completes or fails | `backtest_complete`, `backtest_failed` | `{ "run_id": ..., "equity_curve": [...], "metrics": {...} }` |
| `ml/trainer.py` | Model finished training/evaluation | `ml_model_trained`, `ml_model_evaluated` | `{ "model_id": ..., "accuracy": ... }` |
| `ai_advisor/advisor.py` | Suggestion generated or acted upon | `ai_suggestion`, `ai_suggestion_executed` | `{ "symbol": ..., "side": ..., "confidence": ... }` |
| `strategies/registry.py` | Strategy toggled active/inactive, params updated | `strategy_toggled`, `params_updated` | `{ "strategy_name": ..., "active": true/false }` |
| `dashboard/` routes (error handlers) | Unhandled exceptions (critical) | `error` | `{ "endpoint": ..., "error": "...", "traceback": "..." }` |
| `main.py` (heartbeat) | Missed heartbeat (engine unresponsive) | `heartbeat_missed` | `{ "last_heartbeat": "...", "gap_seconds": ... }` |

Implementation: import `NotificationService` (with dependency injection or `Depends(get_db)` and `Depends(get_current_user)`). Where no user context (e.g., background tasks), publish to all admins or a specific user based on config.

---

## 8. Settings Integration

Extend the existing Settings page (or create a new "Notifications" section):

- Table listing all known event types (from a constant list or from distinct values in notifications).
- Two toggle columns: "In-app" and "Email".
- Save button (or auto-save on toggle change) → `PUT /api/v3/notifications/settings`.

The page should fetch current settings on load and reflect them.

---

## 9. Retention and Cleanup

- Upon `publish`, set `expires_at = created_at + timedelta(days=config.notifications.retention_days)` (default 30). Configurable via env `NOTIFICATIONS_RETENTION_DAYS`.
- Background job (run hourly via `APScheduler` or FastAPI `BackgroundTasks` with loop) calls `NotificationService.cleanup_expired()`:
  - Delete `notification_recipients` rows where notification's `expires_at < now()`.
  - Then delete `notifications` rows that have no remaining recipients (orphaned).
  - Return count of deleted notifications for logging.
- Job runs with a lock to avoid overlapping runs.

---

## 10. Design Tokens and Compliance

- **Colors**: Use MD3 primary (`#0D1B2A` as primary?), surface (`#F5F7FA`), on-surface (`#111827`), error (`#DC2626`), success (`#059669`). The plan document should reference actual tokens from `dashboard/static/v3/theme.js` or Tailwind config.
- **Typography**: Geist for UI text, JetBrains Mono for timestamps and data.
- **Spacing**: 4px grid (8, 12, 16, 24, 32...).
- **Icons**: Material Symbols (rounded) for notifications, checkmarks, trash, etc.
- **Responsive**: Bell dropdown width adjusts; on mobile, full page replaces dropdown.

---

## 11. Acceptance Criteria

- Database migrations apply cleanly (`alembic upgrade head`)
- NotificationService.publish creates notification and recipient rows respecting settings
- Unread count accurate; updating read status updates DB and UI
- Bell dropdown resizable with drag handle; width persists in localStorage
- Filter toggle (show read/unread) persists in localStorage
- Full notifications page lists items, filters, pagination, bulk actions work
- Email arrives within ~5 minutes for events where user enabled email, using HTML template that matches app look
- Settings page toggles take effect immediately
- Cleanup job removes notifications older than retention period without errors
- No console errors or warnings in normal operation
- All API endpoints return correct HTTP status codes and JSON schemas
- Security: users only see their own notifications

---

## 12. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fan-out to many users blocks publish | High | Batch insert recipients; index (user_id, is_read); async if needed |
| Email rate limit exceeded | Medium | In-memory token bucket per user; suppress + log |
| Retention cleanup long-running | Medium | Batch deletes (LIMIT), run hourly, commit per batch |
| Data leakage between users | Critical | Always filter queries by `user_id`, use NotificationRecipient as access control |
| Migrations fail on production | High | Test upgrade/downgrade on staging; include explicit downgrade steps |

---

## 13. Task Breakdown (N1–N10)

**N1: Alembic migration for notifications tables**  
Create `alembic/versions/YYYYMMDD_create_notifications_tables.py` with upgrade/downngrade that creates `notifications`, `notification_recipients`, `notification_settings` tables and indexes. Use PostgreSQL UUID, JSON, TIMESTAMPTZ. Ensure downgrade drops in reverse order (recipients → settings → notifications) and drops indexes explicitly.

**N2: ORM models and NotificationService skeleton**  
Add model classes to `db/models.py` (Notifications, NotificationRecipient, NotificationSettings) with proper relationships. Create `notifications/service.py` with `NotificationService` class implementing publish, mark_read, get_unread_count, get_page, delete, cleanup_expired (stub for cleanup). Ensure publish respects `notification_settings` to skip disabled destinations.

**N3: API routes for notifications and settings**  
Create `dashboard/routes/notifications.py`, register in `dashboard/app.py`. Implement all endpoints from section 4 with Pydantic request/response schemas, JWT auth, error handling. Add to router with prefix `/api/v3/notifications`.

**N4: Top bar bell dropdown (resizable, filter toggle, localStorage)**  
Modify `dashboard/templates/v3/_topbar.html` to include bell icon with badge. Add dropdown markup. Extend `dashboard/static/v3/components/topbar.js` to initialize dropdown, handle resize (drag handle at right edge), filter toggle, and polling for unread count. Persist width and filter state in localStorage.

**N5: Full notifications page template and JS module**  
Create `dashboard/templates/v3/pages/notifications.html` (extend `_base.html`). Create `dashboard/static/v3/pages/notifications.js` with init, loadPage, filter, pagination, mark read, delete, bulk actions. Ensure responsive layout and empty states.

**N6: Email integration (SMTP, template, rate limiting)**  
Add SMTP settings to `config/settings.py` and `.env` template. Implement `notifications/email.py` with `AsyncEmailService` (queue, worker, rate limiting). Create HTML email template. Hook into `NotificationService.publish` to enqueue emails when user has `email_enabled` for the event type.

**N7: Instrument core modules to publish notifications**  
Identify instrumentation points (see section 7) and add `NotificationService.publish` calls. Ensure these are inside try/except to not block main logic. Start with a few key events (trade_executed, backtest_complete, strategy_toggled).

**N8: Settings page section for notifications**  
Add a new section in Settings page (likely `dashboard/templates/v3/pages/settings.html`) with table of event types and toggles. Add JS to fetch and PUT settings. Ensure settings are loaded on page init.

**N9: Retention cleanup job**  
Implement `NotificationService.cleanup_expired` to batch-delete expired notifications. Schedule job on FastAPI startup using `APScheduler` or a background task that runs hourly.

**N10: Testing, mock support and validation**  
Create mock data generator for notifications. Test all API endpoints with JWT (valid/invalid). Test email flow with a mock SMTP server (e.g., `aiosmtplib.SMTP` with `localhost:1025`). Verify localStorage persistence for dropdown width and filter. Cross-browser check. Add unit tests for `NotificationService` methods.

---

## 14. Implementation Notes

- Use **Write tool exclusively** for all file creation/modification (no Edit on .py or .html).
- After each `.py` write, run `py_compile` verification.
- After each `.html` write, verify Jinja2 syntax and `<html>` presence.
- Follow Python style: 4-space indentation, type annotations, `from __future__ import annotations`, no bare `except`.
- Follow FastAPI conventions: `Depends(get_db)`, Pydantic schemas for request/response, proper HTTP status codes.
- Reuse existing design system classes (from `_base.html`, `theme.js`, `shared/`).
- Security: never return other users' notifications; always filter by `user_id`.
- All datetime operations use UTC; use `datetime.utcnow()` or `datetime.now(UTC)`.

---

**End of Plan**
