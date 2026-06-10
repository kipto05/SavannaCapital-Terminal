# Trade Operations & Journaling — Implementation Plan

## Scope
Full rebuild of `dashboard/templates/pages/page_trade_ops.html` matching the stitch reference layout at `dashscreens/stitch_savanna_quant_os/trade_operations_journaling/`. The page treats the window as **independent panels**, not rows or a numbered grid.

---

## Existing Assets (read-only)

### Backend — v2 Monitoring Endpoints (`dashboard/v2/routes/monitoring.py`)
| Endpoint | Returns | Auth |
|---|---|---|
| `GET /api/v2/mt5/account` | MT5 account info (login, server, equity, balance, margin) | None — public |
| `GET /api/v2/mt5/positions` | Open MT5 positions, optionally filtered by symbol | None — public |
| `GET /api/v2/mt5/orders` | Pending MT5 orders, optionally filtered by symbol | None — public |
| `GET /api/v2/mt5/connection` | Connection health check | None — public |

### Backend — Existing Trade & Annotation Endpoints
| Endpoint | Returns | Auth |
|---|---|---|
| `GET /api/trades/recent?limit=N` | Recent trades from DB (via dashboard/app.py) | JWT required |
| `GET /api/transcription/history` | Journal/annotation history | JWT required |

> **Conflict on auth**: v2 monitoring endpoints intentionally skip JWT (MT5-specific infra). Existing `/api/trades/recent` and `/api/transcription/history` are JWT-protected. The page must handle 401 on the history call and prompt re-authentication.

### DB Models
- **`Trade`** (`id, ticket, symbol, timeframe, side, strategy_name, entry, sl, tp, tp1, tp2, lot_size, open_price, close_price, pnl, pnl_r, opened_at, closed_at, source, backtest_run_id, is_active, closed_reason, tag, notes`) — all trades (live + backtest + ai_advisor)
- **`TradeAnnotation`** (`id, trade_id, note, tag, created_at`) — via `Trade.annotations` relationship

---

## Seven Independent Panels

Each panel is a `<section>` or `<div>` with `bg-surface border border-outline-variant`. Panels are stacked in the content area with **independent heights and widths** — they do not constrain each other into a 12-col grid.

### Panel 1 — Top Command Bar
**Position**: Full-width header bar atop the workspace (fixed height, `h-12`).
**Contents**:
- Search input (left group, `w-80`)
- Filter button
- Account dropdown (`Account: ALL` → fetches account list, future-proofing)
- Regime badge/button (`Regime: VOLATILE`)

> **Decision**: Search/filter/account/regime are page-scoped, not global nav. They live here. Confirm: do we wire account-select to an existing accounts API, or is "ALL" the only option for this build?

> **Decision**: Regime is static for V1 (shows current config value). We can add a dropdown later.

### Panel 2 — Live Executions & Pending Orders
**Position**: Upper-left area, takes remaining width beside Panel 5 (Journal). Tall — expands to fill available vertical space above Panels 3 & 4.
**Contents**:
- Header bar: bolt icon, "Live Executions & Pending Orders" label, total unrealized PnL summary (`$42,190.40` sample), overflow menu
- Scrollable table (9 columns, sticky header):
  - Account | Symbol | Type (BUY green / SELL red) | Status badge (FILLED / PENDING) | Price | Size | TP / SL | Unrealized PnL | Action (close button)
- Row hover + click highlight effect

**Data sources**:
- Positions: `GET /api/v2/mt5/positions`
- Orders: `GET /api/v2/mt5/orders`
- Account summary: `GET /api/v2/mt5/account`

### Panel 3 — Execution Quality Analytics
**Position**: Directly below Panel 2 (or in a middle-row beside Panel 4). Width matches Panel 2.
**Contents**:
- Header bar with `analytics` icon + `Exec Quality` label
- 2×2 grid of KPI cards inside:
  - **Slippage (Avg)**: value + `bps` label + progress bar
  - **Latency**: value + `ms` label + progress bar
  - **Fill Rate**: value + `%` label + progress bar
  - **Rejections**: value + `%` label + progress bar

> **Decision**: V1 shows static/placeholder values from the stitch. Do we compute real slippage/latency from MT5 execution reports (dealer_time vs request_time), or keep placeholders for now?

### Panel 4 — Historical Trade Log
**Position**: Beside Panel 3 (same row if space permits), or below Panel 2 on narrow screens. Below Panel 2 when the window is wide enough.
**Contents**:
- Header bar: `history` icon + `Historical Log` label + `EXPORT CSV` button
- Scrollable table (6 columns, sticky header, smaller font `text-[12px]`):
  - Time (UTC) | Symbol | Side | Profit | R:R | Strategy
- On row click: highlights the row, populates Panel 5's trade selector and alpha tags

**Data source**: `GET /api/trades/recent?limit=50` (JWT) — falls back to v2 `/api/v2/mt5/positions` for open trades if JWT fails.

### Panel 5 — Journal & Annotations
**Position**: Right sidebar (narrower, `w-sidebar-width` or `min-w-[280px]`). Spans the full height beside Panels 2–4.
**Contents** (top to bottom):
1. Header bar: `edit_note` icon + `Journal & Annotations` label + `SAVE ENTRY` button
2. Scrollable form area:
   - **Trade selector dropdown** (`<select>` populated from historical log selection)
   - **Alpha Factor & Regime Tags** — toggle chips: Mean Reversion, Volatility Spike, HFT Front-run, Liquidity Gap, Order Block
   - **Hypothesis / Post-Mortem Notes** — `<textarea>` fills from selected trade or user input
   - **Chart Attachment Placeholder** — `h-48` dashed-border drop zone with camera icon + label
3. **Footer — Potential Alpha Leakage**: label + amber value + progress bar (V1: static)

**Data source**:
- Trade annotations: `GET /api/transcription/history` (JWT)
- Save annotation: same endpoint or new `POST /api/transcription/anotate`?

> **Decision needed**: Do we add a new `POST /api/v2/journal/annotation` endpoint for saving notes/tags, or reuse the existing transcription API? Reusing is simpler but semantically odd.

### Panel 6 — Global Status Bar
**Position**: Full-width footer, fixed `h-6`.
**Contents**:
- Left group: port indicator (`READY: LISTENING ON PORT 8443`) + sync freshness (`Sync: 12ms ago` with green dot)
- Right group: live ticker prices (XAUUSD, BTC) + EST clock

**Data sources**:
- Port: hardcoded from config (or injected server-side via Jinja)
- Sync: `GET /api/v2/mt5/connection` → `last_tick_time` delta
- Ticker prices: `GET /api/v2/mt5/account` or new quote endpoint

> **Decision**: The stitch shows a server port, but the FastAPI dashboard usually runs on 8000. Should we show the dashboard port, the engine port, or hide this entirely?

---

## Layout Structure (HTML)

```
┌─────────────────────────────────────────────────────────────┐
│ Panel 1 — Top Command Bar (height: h-12, full-width)        │
├────────────────────────────────────┬────────────────────────┤
│ Panel 2 — Live Executions          │ Panel 5 — Journal      │
│ (flex-1, tall)                     │ (sidebar-width,        │
│                                    │  full height)           │
├──────────────┬─────────────────────┤                        │
│ Panel 3      │ Panel 4            │                        │
│ Exec Quality │ Historical Log     │                        │
│ (h-1/3)      │ (h-1/3)            │                        │
└──────────────┴─────────────────────┴────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Panel 6 — Global Status Bar (height: h-6, full-width)      │
└─────────────────────────────────────────────────────────────┘
```

The left column (Panels 2–4) is a flex-col with `gap-panel-gap`. Panels 3 and 4 sit side-by-side inside a `grid grid-cols-2 gap-panel-gap` row. Panels 2 and 5 are independent — they share the middle row but have no grid dependency.

---

## Files to Create / Modify

| Action | File | Notes |
|---|---|---|
| **CREATE** | `dashboard/v2/routes/trade_ops.py` | New v2 router for trade-ops endpoints (positions, orders, history, annotations CRUD) |
| **CREATE** | `dashboard/v2/routes/journal.py` | New v2 router for journal/annotation endpoints (list, create, delete for trade_id) |
| **MODIFY** | `dashboard/v2/app.py` | Include new routers |
| **REWRITE** | `dashboard/templates/pages/page_trade_ops.html` | Full stitch layout with all 7 panels |
| **VERIFY** | `py_compile` on all new/modified .py files | Per CLAUDE.md Rule 3 |

---

## JS Interactivity (in page template, like backtesting page)

- **Polling**: `mutate_position()`-style — re-fetch positions/orders every `config.dashboard.poll_interval_ms`
- **Row click**: Highlight row in Panel 4 → populate trade selector in Panel 5 → load existing annotations
- **Tag toggle**: Click alpha tag chip → toggle active styling → update tag list for save
- **Save annotation**: POST → reload annotation list → show success feedback
- **Close button**: Row action in Panel 2 → confirm modal → call MT5 close order
- **Price flash**: `setInterval` random cell flash (from stitch)

---

## Questions Before Building

1. **Account selector**: Should we wire it to a real accounts API, or leave as "ALL" placeholder in V1?
2. **Regime badge**: Static display or interactive toggle?
3. **Exec Quality KPIs**: Real computation from MT5 dealer timestamps, or static placeholders?
4. **Journal save endpoint**: Reuse `/api/transcription/history` POST, or new v2 endpoint?
5. **Server port in status bar**: Dashboard port (8000), engine port, or different field?
6. **Chrome/main.html compatibility**: Do existing pages, success/failure of these operations trigger refresh? Does this page need a parent node ID or can it operate standalone?

---

## After-Plan Checklist (per CLAUDE.md Completion Checklist)

- [ ] All required fields satisfied
- [ ] Architecture respected (thin routers, no business logic in templates)
- [ ] Skills followed (fastapi.md, sqlalchemy.md)
- [ ] py_compile passes
- [ ] Jinja2 verification passes
- [ ] Mobile / tablet / desktop verified (responsive Tailwind classes)
- [ ] Error states verified (empty tables, J401 on auth-protected calls)
- [ ] No look-ahead introduced
- [ ] All datetimes UTC
- [ ] No bare except blocks
- [ ] No new fix_*.py scripts
