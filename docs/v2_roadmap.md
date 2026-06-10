
# Savanna Capital Quant OS — v2 Roadmap

> Scope: five feature clusters that complete the platform.
> Each cluster has: goal, UI sections → endpoint map, DB schema, implementation notes.

---

## 1 · AI Trading Agent (inbuilt self-analysis & signals)

### Goal
A background agent that continuously analyses open-market data across all
linked symbols, produces directional signals with confidence scores, and
surfaces them to the dashboard — optionally forwarding high-confidence
signals directly to live MT5 orders via the existing execution layer.

### Why now
- `db/models.py` already defines `AIAdvisorSuggestion` (DB table live)
- `ai_advisor/advisor.py` stubbed in CLAUDE.md but not yet implemented
- `/api/ai_advisor/suggestions` page endpoint exists in `page_ai_research.html`
- Agent loop is the only remaining "live" brain of the platform

### UI sections (upgrade `page_ai_research.html`)

| Section | What it shows | Data source |
|---------|---------------|-------------|
| **Signal feed** (top, scrollable) | Latest AI suggestions with symbol, side, confidence bar, reasoning snippet | `GET /api/ai_advisor/suggestions?limit=50&min_conf=0.7` |
| **Signal detail pane** | Full reasoning: indicator snapshot, support/resistance zones, risk/reward estimate | `GET /api/ai_advisor/suggestions/{id}` |
| **Agent status pill** | LLM connection / last analysis timestamp / queue depth | `GET /api/ai_advisor/status` |
| **Auto-execute toggle** | Per-symbol bool: forward signals → `execution/order_manager.py` automatically | `PATCH /api/ai_advisor/config` |
| **Cooldown & filters** | Min confidence, max symbols per session, blacklist symbols | persisted in `PlatformSetting` |
| **Performance ledger** | Win/loss tracking per AI-suggested trade vs baseline | join on `Trade.ai_suggestion_id` |

### Backend endpoints (new file `dashboard/routes/ai_advisor.py`)

```
GET    /api/ai_advisor/status          — agent uptime, queue depth, last run ts
GET    /api/ai_advisor/suggestions     — list recent suggestions (paginated)
GET    /api/ai_advisor/suggestions/{id}— single suggestion with full context
PATCH  /api/ai_advisor/config          — toggle auto-execute, set confidence floor
POST   /api/ai_advisor/analyse         — force an analysis run (returns suggestions)
```

### New DB model (already drafted in `db/models.py`)

`AIAdvisorSuggestion` already exists with columns: id, symbol, timeframe,
side, confidence, reasoning, market_context (JSON), created_at,
consumed (bool). Add one column:

```python
executed = Column(Boolean, default=False, nullable=False)   # did order_manager take it?
```

Alembic auto-migration: `alembic revision --autogenerate -m "add ai_advisor.executed"`.

### Core service `ai_advisor/advisor.py` (write from scratch)

```python
class AIAdvisor:
    def __init__(self, db_session_factory, mt5_adapter_factory, anthropic_client):
        ...

    async def suggest(self, symbol, timeframe, df, stats, trades) -> dict | None:
        """Call Claude with market-context prompt. Return parsed dict or None on cooldown/failure."""

    async def analyse_all(self, enabled_symbols: list[str]) -> list[dict]:
        """Fan out suggest() across symbols. Deduplicate. Persist to DB."""

    def _build_prompt(self, symbol, df, stats, trades) -> str:
        """OHLCV summary, indicator snapshot, recent trade P&L, position state."""

    def _parse_response(self, text: str) -> dict | None:
        """Extract JSON from Claude response. Require keys: side, confidence, reasoning."""

    def _cooldown(self, symbol: str) -> bool: ...
```

### Agent loop (integrate into existing engine `quant/runner.py`)

The existing engine already has a polling tick. Add one async call per tick:

```python
if config.ai.enabled and time.time() - last_ai_tick > config.ai.cooldown_minutes * 60:
    suggestions = await advisor.analyse_all(enabled_symbols)
    for s in suggestions:
        if s.confidence >= config.ai.min_confidence_to_show:
            db.add(AIAdvisorSuggestion(**s))
    db.commit()
```

Key: the advisor is **never allowed to block the engine loop** — failures are
logged and swallowed (per CLAUDE invariant #16).

### Notification routing (see §2)

High-confidence AI signals (≥ 85 %) trigger two notification paths:
1. **Dashboard bell notification** — persisted in `ai_advisor_suggestions` table;
   front-end inbox polls every poll_interval_ms.
2. **Admin email** — if `config.ai.email_alerts` is true and signal confidence ≥
   configured floor (default 90 %).

---

## 2 · Notification System

### Goal
Two-tier alerting: a **bell icon** in the header opens an in-dashboard
inbox; certain events also fire **email** to the admin inbox.

### UI

| Element | Behaviour |
|---------|-----------|
| 🔔 bell icon (header, right of "System Status" DNS icon) | Red dot badge when `unread_count > 0`. Click opens dropdown. |
| Notification dropdown | Scrollable list: newest first. Each row: severity icon, message, timestamp, dismiss ×. Click row → mark read. |
| Settings → Notifications tab | Toggle per-category: email ON/OFF, dashboard ON/OFF, sound ON/OFF. |

### Notification categories & routing

| Category | Trigger | Email? | Dashboard? | Who sees it |
|----------|---------|--------|------------|-------------|
| `AI_SIGNAL` | AI advisor produces a suggestion with confidence ≥ `config.ai.email_alert_min` | Admin only | Admin + any linked accounts (future) | Admin |
| `DRAWDOWN_BREACH` | Daily or weekly DD exceeds configured floor (default −2 %) | Admin | All logged-in users | Admin |
| `MARGIN_CALL` | Margin usage > 80 % or free margin < 20 % | Admin + immediate | All | Admin |
| `ORDER_FILLED` | Live trade executed (from order_manager) | Optional | Admin + account owner | Admin |
| `RISK_ALERT` | Concentration > 35 % or correlation spike | Admin | All | Admin |
| `ENGINE_DOWN` | Heartbeat older than 120 s | Admin (critical) | All | Admin |
| `STRATEGY_TOGGLED` | Strategy enabled/disabled via registry | No | Admin | Admin |

### New DB model: `Notification`

```python
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # null = broadcast
    category = Column(String(32), nullable=False, index=True)          # ai_signal, drawdown, margin…
    severity = Column(String(16), nullable=False)                       # info, warning, error
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    link_url = Column(String(255), nullable=True)                       # deep-link into app
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    email_sent = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
```

Alembic migration required.

### New DB model: `NotificationPreference` (one row per user per category)

```python
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(32), nullable=False)
    email_enabled = Column(Boolean, default=False, nullable=False)
    dashboard_enabled = Column(Boolean, default=True, nullable=False)
    sound_enabled = Column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "category"),)
```

### Backend endpoints (`dashboard/routes/notifications.py`)

```
GET    /api/notifications/unread_count        — {count: N}
GET    /api/notifications?offset=&limit=&category=
POST   /api/notifications/{id}/read           — mark single as read
POST   /api/notifications/read_all            — mark all as read
GET    /api/notifications/preferences         — current user's prefs
PATCH  /api/notifications/preferences         — bulk update prefs
POST   /api/notifications/{id}/dismiss        — hard delete / archive
```

**Email sending**: use `httpx` to POST to a local SMTP relay (e.g. `smtplib`
with Gmail SMTP or a self-hosted Poste/MailHog). Keep it in a background
thread so the FastAPI loop never blocks. The email template lives in
`dashboard/static/email_templates/notification.html`.

**Implementation order**:
1. DB models + migration
2. `notifications.py` router + endpoints
3. Bell icon + dropdown in `_base.html` header
4. Settings → Notifications tab in `page_settings.html`
5. Wire events: risk engine, AI advisor, order manager all call
   `notify(category, severity, title, body, link_url)` helper.

---

## 3 · Multi-Account Linking (upgrade existing scaffold)

### Current state
`page_multi_account.html` exists with basic scaffold: instance matrix table
(account_id, broker, server, status, equity), recent orders table. No backend
endpoints exist for multi-account operations.

### Goal
Allow the admin to link **multiple MT5 accounts** (different brokers or
sub-accounts) under one dashboard. Each account runs its own strategy set
independently; the dashboard aggregates equity, exposure, and risk across all.

### DB model: `LinkedAccount`

```python
class LinkedAccount(Base):
    __tablename__ = "linked_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(64), nullable=False)              # e.g. "Alpha-BTC"
    broker = Column(String(64), nullable=False)              # e.g. "JustMarkets"
    server = Column(String(128), nullable=False)
    mt5_login = Column(String(64), nullable=False)
    mt5_password_enc = Column(String(255), nullable=False)   # Fernet-encrypted
    account_type = Column(String(16), nullable=False)        # live / demo
    is_active = Column(Boolean, default=True, nullable=False)
    equity = Column(Float, nullable=True)
    margin = Column(Float, nullable=True)
    free_margin = Column(Float, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    linked_at = Column(DateTime, default=func.now(), nullable=False)
```

Encryption: use Fernet from `cryptography` package. Key stored in env var
`MT5_PASSWORD_ENC_KEY`.

### Backend endpoints (`dashboard/routes/multi_account.py`)

```
GET    /api/accounts                      — list linked accounts with live MT5 snapshot
POST   /api/accounts                      — register new MT5 account (encrypts password)
PATCH  /api/accounts/{id}                 — update label / active flag
DELETE /api/accounts/{id}                 — unlink
POST   /api/accounts/{id}/sync            — force MT5 sync (positions + account info)
POST   /api/accounts/{id}/trade           — place order on this account
GET    /api/accounts/{id}/positions       — positions for one account
GET    /api/accounts/summary              — aggregated equity/margin across all accounts
```

### Frontend upgrades (`page_multi_account.html`)

| Section | Upgrade |
|---------|---------|
| Instance matrix header | Add **+ Link Account** button → modal form (label, broker, server, login, password, type) |
| Matrix row | Add eye icon to toggle active/inactive; risk-of-day badge |
| Matrix row | Add inline equity/margin sparkline (mini canvas Chart.js, 30-day snapshot) |
| Sync button | "Sync All" → `POST /api/accounts/sync-all` (background thread, 30 s poll) |
| Recent Orders | Expand to per-account tab filter |
| Bottom panel | **Aggregated Exposure** — donut across accounts; **Account Equity Curve** — multi-line chart |

### Sidebar impact
None. Sidebar stays the same; the page URL `/multi-account` already exists.

---

## 4 · Profile Settings (click avatar in header)

### Current state
`_base.html` line 199: a static `div` with initials "SC". No route or page
exists. No profile page in `dashboard/routes/`. Settings page (`page_settings.html`)
exists but has no user-profile tab.

### Goal
Clicking the avatar opens a **popover / modal** (not a new page) with:
profile info, change-password form, and linked-auth info. A dedicated
`/settings` tab "Profile" persists as a regular page for full edits.

### UI — Avatar popover (on-click, no page navigation)

| Field | Type | Validation |
|-------|------|------------|
| Username | readonly display | — |
| Role | readonly display (admin / trader / viewer) | — |
| Email | text input | valid email, required |
| Full name | text input | required |
| Change password | current + new + confirm | min 12 chars, must match |
| Save button | POST → API | flash success / error |

### UI — Settings → Profile tab (full page, mobile-friendly)

Same fields as above plus:
- MF A (2FA) toggle — store `otp_secret` in `User.otp_secret` column (new)
- Last login IP + timestamp (read-only)
- API token rotation: "Regenerate API key" → creates new `api_key` column on User,
  invalidates old one
- Linked accounts mini-table: shows `LinkedAccount` rows, link/unlink inline

### DB changes

Add to existing `User` model:

```python
email = Column(String(255), nullable=True)
full_name = Column(String(255), nullable=True)
otp_secret = Column(String(64), nullable=True)       # TOTP secret base32
otp_enabled = Column(Boolean, default=False, nullable=False)
api_key = Column(String(64), nullable=True, index=True)  # rotateable bearer
api_key_created_at = Column(DateTime, nullable=True)
```

Alembic migration required.

### Backend endpoints (`dashboard/routes/account.py` — new)

```
GET    /api/account/me                     — current user profile
PATCH  /api/account/me                     — update email, name
POST   /api/account/change-password        — verify current, set new (bcrypt)
POST   /api/account/api-key/regenerate     — rotate api_key
POST   /api/account/2fa/enable             — generate TOTP secret (return QR URI)
POST   /api/account/2fa/verify             — verify TOTP code
POST   /api/account/2fa/disable            — disable 2FA
```

### Implementation notes

- Password change: always re-hash with bcrypt. Never log old/new password.
- API key: 32-byte random hex (`secrets.token_hex(32)`); stored hashed? No —
  API key is a bearer token, same treatment as JWT but longer-lived. Send it
  once at creation; store plaintext in DB and send header `X-API-Key`.
- 2FA: use `pyotp`. QR URI returned in response; frontend renders with
  `qrcode.js` CDN. Enrolment flow: POST enable → get QR → user scans app →
  POST verify with TOTP code → 2FA enabled.

---

## 5 · Theme Changing Infrastructure

### Current state
Tailwind config is in `_base.html` `<script id="tailwind-config">` with a
single hardcoded dark palette. `darkMode: "class"` is configured but never
toggled. All pages assume dark mode.

### Goal
Support **three themes**: Dark (default), Light, and a custom
"Midnight-Savanna" dark-tinted variant. User preference persisted in
`PlatformSetting` (key = `ui_theme`, value = `"dark" | "light" | "midnight"`).
No migration needed — `PlatformSetting` already exists.

### Theme definitions

| Theme | Background | Surface | Text primary | Accent |
|-------|-----------|---------|--------------|--------|
| **Dark** (current) | `#0a0e13` | `#1c2025` | `#e0e2ea` | `#00daf3` |
| **Light** | `#f8f9fa` | `#ffffff` | `#1a1a2e` | `#0077b6` |
| **Midnight** | `#0d1117` | `#161b22` | `#c9d1d9` | `#00daf3` |

### Implementation

**Step 1 — extend Tailwind config in `_base.html`**

```javascript
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Dark (default) — existing palette
        "bg-primary":   "var(--bg-primary, #0a0e13)",
        "bg-surface":   "var(--bg-surface, #1c2025)",
        "text-primary": "var(--text-primary, #e0e2ea)",
        "accent":       "var(--accent, #00daf3)",
      }
    }
  }
}
```

Wrap the existing hardcoded color block in CSS variables inside the
`<style>` tag:

```css
:root { /* light */ }
[data-theme="dark"]  { --bg-primary: #0a0e13; --bg-surface: #1c2025; --text-primary: #e0e2ea; --accent: #00daf3; }
[data-theme="midnight"] { --bg-primary: #0d1117; --bg-surface: #161b22; --text-primary: #c9d1d9; --accent: #00daf3; }
```

**Step 2 — theme switcher in `_base.html` header**

Replace the header material-icon-only status icons with a small segmented
control or dropdown:

```html
<div class="flex items-center gap-1 bg-surface-container rounded border border-outline-variant p-0.5">
  <button onclick="setTheme('dark')"     class="theme-btn px-2 py-1 text-[10px] rounded …">Dark</button>
  <button onclick="setTheme('light')"    class="theme-btn px-2 py-1 text-[10px] rounded …">Light</button>
  <button onclick="setTheme('midnight')" class="theme-btn px-2 py-1 text-[10px] rounded …">Midnight</button>
</div>
```

**Step 3 — `setTheme()` helper**

```javascript
function setTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  localStorage.setItem('theme', name);
  apiFetch('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify({key: 'ui_theme', value: name})
  }).catch(() => {});
  document.querySelectorAll('.theme-btn').forEach(function(b) {
    b.classList.toggle('bg-surface-container-high', b.dataset.theme === name);
  });
}
```

Bootstrap: on page load, read `localStorage.theme` (instant, before paint)
then reconcile server-side via `GET /api/settings`.

**Step 4 — Settings → Appearance tab**

Add a "Appearance" section to `page_settings.html`:
- Theme selector (radio cards: Dark / Light / Midnight)
- Font scale slider (small / default / large)
- Compact mode toggle (dense tables vs. spacious)
- Preview pane showing a mock KPI card in the selected theme

All values stored in `PlatformSetting` (already has `key/value/type` columns).

### Migration effort
**Zero DB migrations.** Existing `PlatformSetting` table covers all
preferences. Theme preference is a simple string key.

### Colour consistency rule
Every component must use CSS variable classes — never hard-code a hex.
Audit pass required on all `page_*.html` files once the variable system
is in place.

---

## Implementation Priority (v2 completion order)

| Priority | Cluster | Estimated effort | Dependencies |
|----------|---------|-----------------|--------------|
| **P0** | AI Trading Agent — advisor service | 2–3 days | Anthropic API key env var; DB model exists |
| **P0** | AI Trading Agent — engine loop integration | 1 day | Agent service, config.ai block |
| **P1** | Notification system — DB + endpoints | 2 days | None; independent of AI |
| **P1** | Notification system — UI (bell + dropdown) | 1 day | Endpoints, _base.html touch |
| **P1** | Profile settings — DB + endpoints | 1.5 days | None |
| **P1** | Profile settings — avatar popover | 0.5 day | Endpoints, _base.html touch |
| **P2** | Multi-account — DB + endpoints | 2 days | MT5 adapter refactor for multi-connection |
| **P2** | Multi-account — UI upgrade | 1.5 days | Endpoints |
| **P2** | Theme infrastructure | 1.5 days | Settings API already exists |
| **P2** | Theme audit pass (all pages) | 1 day | Theme infra |

**Total estimate: ~13–14 developer-days.**

### Critical path

```
db/models (AIAdvisorSuggestion.executed, LinkedAccount, User.otp_secret/api_key)
    ↓
alembic migration (single combined migration covering all three additions)
    ↓
Parallel tracks:
  Track A: ai_advisor/advisor.py → dashboard/routes/ai_advisor.py → page_ai_research.html
  Track B: dashboard/routes/notifications.py → bell UI → wire events
  Track C: dashboard/routes/account.py → profile popover + settings tab
  Track D: dashboard/routes/multi_account.py → MT5 multi-connection → page_multi_account.html
  Track E: CSS variables + theme switcher → _base.html → audit pass
```

### Files touched summary

| File | Action |
|------|--------|
| `ai_advisor/advisor.py` | Create (core agent) |
| `dashboard/routes/ai_advisor.py` | Create |
| `dashboard/routes/notifications.py` | Create |
| `dashboard/routes/account.py` | Create |
| `dashboard/routes/multi_account.py` | Create |
| `db/models.py` | Add columns: `AIAdvisorSuggestion.executed`, `LinkedAccount`, `User.otp_secret`, `User.api_key` |
| `alembic/versions/XXXX_add_v2_models.py` | New migration |
| `config/settings.py` | Add `ai.*` block if missing, ensure `cors_origins` includes email backend |
| `_base.html` | Bell icon + theme switcher + avatar click handler |
| `page_ai_research.html` | Full upgrade (signal feed + detail) |
| `page_multi_account.html` | Full upgrade (link modal + per-account sparklines) |
| `page_settings.html` | Add Appearance + Notifications tabs |
| `page_portfolio_risk.html` | Already complete (v1) |
| `dashboard/static/email_templates/notification.html` | Create |
| `quant/engine.py` or `quant/runner.py` | Hook advisor into engine tick |

---

## Non-Functional Requirements

- All notification + AI agent calls remain **async** and **fire-and-forget**.
  Failures return None / empty; never block the engine loop.
- Email sending must use a **background thread** (not `await` a blocking
  `smtplib` call inside the event loop).
- Theme switch must be **instant** (< 50 ms) via CSS variables and
  `localStorage`; server sync is best-effort and non-blocking.
- All new endpoints require JWT. Exception: email webhook callbacks if any
  (then use a separate `X-Webhook-Secret` header).
- All passwords / MT5 credentials / API keys stored encrypted or hashed.
  MT5 passwords → Fernet; user password + API key → bcrypt.
