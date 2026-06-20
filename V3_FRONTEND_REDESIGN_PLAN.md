# V3 Frontend Redesign Plan
## Savanna Capital Quantum Terminal

**Date:** 2025-06-15 (v2-scaffold → v3 redesign)  
**Status:** Planning Phase  
**Scope:** Frontend UI rebuild with new design system, plus full backend rebuild (separate focus)

---

## Executive Summary

This plan outlines a complete frontend redesign of the Savanna Capital trading platform from v2 to v3, introducing:

- **Unified design system** with Material Design 3-inspired color palette, typography (Geist + JetBrains Mono), and 4px spacing grid
- **Common layout shell** with collapsible sidebar (240px → 48px) and fixed top navigation bar
- **Dark-first aesthetic** with high-density data displays and professional terminal feel
- **Page-by-page rebuild** based on reference designs in `dashscreens/stitch_savanna_quant_os/`
- **No v2 templates modified** → all new templates in `dashboard/templates/v3/` (parallel structure)

---

## 1. Architecture Changes

### 1.1 New Base Template Structure

**File:** `dashboard/templates/v3/_base.html`

Provides the common layout shell for all pages (except standalone pages like login, settings, profile):

```html
<!DOCTYPE html>
<html class="dark" lang="en">
<head>
  <!-- Meta tags, Tailwind config, Material Icons, Google Fonts (Geist, JetBrains Mono) -->
  <!-- Custom CSS: scrollbars, glass effects, grid patterns -->
  <!-- Tailwind config with design system colors, spacing, typography -->
</head>
<body class="bg-background text-on-surface font-body-md overflow-hidden h-screen">
  <!-- Collapsible Sidebar -->
  <aside id="sidebar" class="fixed left-0 top-0 h-full flex flex-col transition-all duration-300">
    <!-- Branding (logo + version) -->
    <!-- Navigation items (icons + labels, icons-only when collapsed) -->
    <!-- Bottom: Settings, Support links -->
  </aside>

  <!-- Main Content Wrapper -->
  <div id="main-wrapper" class="ml-[240px] flex flex-col h-screen transition-all duration-300">
    <!-- Fixed Top Navigation Bar -->
    <header class="h-12 border-b border-outline-variant flex justify-between items-center px-container-padding">
      <!-- Left: App name, domain links (Research, Execution, Operations, Analytics) -->
      <!-- Right: Deploy button, notifications, terminal, profile, dark/light toggle -->
    </header>

    <!-- Page Content -->
    <main class="flex-1 overflow-y-auto p-panel-gap">
      {% block content %}{% endblock %}
    </main>
  </div>

  <!-- JavaScript: Sidebar collapse logic, theme toggle, global state -->
</body>
</html>
```

**Key Features:**
- Sidebar collapsed state: width reduces to 48px (icons only), `main-wrapper` margin adjusts to `ml-[48px]`
- Dark/light mode toggle stored in `localStorage` with system preference detection
- Top nav bar appears on all pages EXCEPT: `login.html`, `settings.html`, `profile.html` (standalone)
- All pages extend base: `{% extends "v3/_base.html" %}`

### 1.2 Design System (Tailwind Config)

**Colors** (Material Design 3 inspired):
```javascript
extend: {
  colors: {
    surface: '#101419',
    surface_dim: '#101419',
    surface_container_lowest: '#0a0e13',
    surface_container_low: '#181c21',
    surface_container: '#1c2025',
    surface_container_high: '#262a30',
    surface_container_highest: '#31353b',
    on_surface: '#e0e2ea',
    on_surface_variant: '#bac9cc',
    primary: '#c3f5ff',
    primary_container: '#00e5ff',
    primary_fixed: '#9cf0ff',
    primary_fixed_dim: '#00daf3',
    on_primary: '#00363d',
    on_primary_container: '#00626e',
    secondary: '#bcc7de',
    secondary_container: '#3e495d',
    on_secondary: '#263143',
    tertiary: '#ffecad',
    tertiary_container: '#f4ce00',
    on_tertiary: '#3a3000',
    error: '#ffb4ab',
    error_container: '#93000a',
    on_error: '#690005',
    outline: '#849396',
    outline_variant: '#3b494c',
    // ... semantic colors
  }
}
```

**Spacing**:
- Base unit: `4px`
- Sidebar width: `240px` (expanded), `48px` (collapsed)
- Panel gap: `1px` (using 1px borders instead of gaps)
- Container padding: `12px`
- Cell padding: `8px` horizontal, `4px` vertical

**Typography**:
```javascript
fontFamily: {
  display_lg: ['Geist'],      // Page titles
  headline_md: ['Geist'],     // Section headers
  body_md: ['Geist'],         // Body text
  label_sm: ['JetBrains Mono'], // Labels, metadata
  data_lg: ['JetBrains Mono'], // Large numbers
  data_md: ['JetBrains Mono'], // Table data
}
```

**Border Radius**:
- DEFAULT: `0.125rem` (2px)
- lg: `0.25rem` (4px)
- xl: `0.5rem` (8px)
- full: `0.75rem` (12px)

---

## 2. File Structure

```
dashboard/
├── templates/
│   ├── v3/                          # NEW: all v3 templates
│   │   ├── _base.html              # Base layout with sidebar + top bar
│   │   ├── _sidebar.html           # Sidebar partial (nav items)
│   │   ├── _topbar.html            # Top nav partial (search, actions)
│   │   ├── _theme.html             # Theme toggle, CSS custom properties
│   │   ├── pages/
│   │   │   ├── login.html          # REDESIGN (institutional login)
│   │   │   ├── mission_control.html # REDESIGN (executive overview)
│   │   │   ├── executive_analytics.html # REDESIGN
│   │   │   ├── portfolio_risk.html # REDESIGN
│   │   │   ├── research_lab.html   # REDESIGN (per spec)
│   │   │   ├── hypotheses.html     # REDESIGN (kanban board)
│   │   │   ├── optimization.html   # REDESIGN (parameter optimization)
│   │   │   ├── ai_research.html    # UNCHANGED (stays same)
│   │   │   ├── strategy_library.html # COMPLETE REBUILD (new template)
│   │   │   ├── risk_compliance.html # COMPLETE REBUILD (new template)
│   │   │   ├── backtesting_center.html # COMPLETE REBUILD (new template)
│   │   │   ├── ml_dashboard.html     # ML Center dashboard (from institutional_ml_center_rebuild)
│   │   │   ├── ml_training.html      # ML Training Center (from ml_strategy_builder_alpha_generation)
│   │   │   ├── ml_classification.html # Trade Classification Feed (from trade_intelligence_ai_risk_filter)
│   │   │   ├── ml_monitoring.html    # ML Strategy Trades Monitoring (page_ml_monitoring.html)
│   │   │   ├── trade_operations.html # Evaluate from v2 (not mentioned)
│   │   │   ├── multi_account.html  # Evaluate from v2 (not mentioned)
│   │   │   └── settings.html       # UNCHANGED? (standalone, no top bar)
│   │   └── partials/
│   │       ├── _kpi_tile.html      # Reusable KPI card component
│   │       ├── _data_table.html    # Reusable table with sorting
│   │       ├── _chart_card.html    # Chart container with header
│   │       └── _status_badge.html  # Status indicator badges
│   ├── pages/                       # v2 templates (keep until v3 complete)
│   └── partials/
├── static/
│   └── v3/
│       ├── app.js                  # Main v3 application JS
│       ├── theme.js                # Dark/light mode logic
│       ├── components/
│       │   ├── sidebar.js
│       │   ├── topbar.js
│       │   ├── tables.js
│       │   └── charts.js
│       ├── pages/
│       │   ├── mission_control.js
│       │   ├── executive_analytics.js
│       │   ├── portfolio_risk.js
│       │   ├── strategy_library.js
│       │   ├── risk_compliance.js
│       │   ├── backtesting_center.js
│       │   ├── ml_center.js
│       │   ├── research_lab.js
│       │   ├── hypotheses.js
│       │   ├── optimization.js
│       │   └── ai_research.js     # Keep existing
│       └── shared/
│           ├── api.js             # Centralized API calls
│           ├── utils.js           # Date/number formatting
│           ├── charts.js          # Chart.js configurations
│           └── websocket.js       # Real-time updates
└── routes/
  ├── v3/                           # Optional: new API routes if needed
  │   ├── __init__.py
  │   ├── strategies.py            # Rebuild with new endpoints
  │   ├── ml.py                    # Complete redesign
  │   ├── backtesting.py
  │   ├── risk.py
  │   ├── account.py
  │   ├── trades.py
  │   ├── quant.py
  │   ├── ai_advisor.py            # Keep if unchanged
  │   ├── transcription.py
  │   └── settings.py
  └── __init__.py
```

**Note:** Backend rebuild is out of scope for this frontend plan, but route structure shown for completeness.

---

## 3. Page-by-Page Redesign Plan

### 3.1 Pages with Reference Templates (Direct Reimplementation)

These pages have complete reference implementations in `dashscreens/stitch_savanna_quant_os/`:

| Page | Source Reference | Priority | Notes |
|------|-----------------|----------|-------|
| **Login** | `institutional_login_gate/code.html` | HIGH | First impression, keep scanner animation |
| **Mission Control** | `mission_control_dashboard_2/code.html` | HIGH | Dashboard with sidebar + topbar built in, remove internal nav |
| **Executive Analytics** | `executive_analytics_reporting/code.html` | MEDIUM | Teardown/slide-out panels for tear sheet |
| **Portfolio Risk** | `portfolio_risk_monitor/code.html` | HIGH | Grid layout with correlation matrix |
| **Research Lab** | `research_lab/research_lab.md` + existing | HIGH | Follow layout spec: 3-panel workspace |
| **Hypotheses** | `hypothesis_center/code.html` | MEDIUM | Kanban board with draggable cards |
| **Optimization** | `optimization_hub/code.html` | MEDIUM | Parameter surface heatmap + top results table |
| **AI Research** | Existing v2 (no change) | LOW | Keep current implementation |

**Implementation Steps for Each Page:**
1. Copy structure from reference `code.html`
2. Replace hardcoded data with API calls to v3 backend endpoints
3. Implement JavaScript functionality (polling, websocket updates, chart rendering)
4. Adapt to base template (remove sidebar/top nav if present, fill `{% block content %}`)
5. Add page-specific JS in `static/v3/pages/{page}.js`

---

### 3.2 Pages Requiring Complete Rebuild (New Templates)

These pages are referenced in the template folders but need significant adaptation:

#### **Strategy Library** (`strategy_library/code.html`)

**New Design Features:**
- Fixed sidebar + top bar (already in reference)
- Grid layout: 240px left panel (filters), 8 columns center (strategy grid), 340px right panel (details)
- Strategy cards in `trading-grid` CSS (gap: 1px, borders instead of shadows)
- Detail panel slide-up from bottom (equity curve, Monte Carlo, performance metrics)
- View toggles: Table / Grid / Evidence
- Action buttons: Toggle, Edit Params, Copy, Backtest, Deploy

**Files to Create:**
- `dashboard/templates/v3/pages/strategy_library.html`
- `dashboard/static/v3/pages/strategy_library.js`

**API Endpoints Needed:**
```
GET    /api/v3/strategies/                    # List strategies with stats
GET    /api/v3/strategies/{name}              # Strategy details
GET    /api/v3/strategies/{name}/equity       # Equity curve
GET    /api/v3/strategies/{name}/monte-carlo  # Simulation paths
GET    /api/v3/strategies/{name}/performance  # Monthly returns, metrics
GET    /api/v3/strategies/{name}/trades       # Trade history
GET    /api/v3/strategies/{name}/backtests    # Backtest run history
POST   /api/v3/strategies/{name}/toggle       # Enable/disable
PUT    /api/v3/strategies/{name}/params       # Update parameters
POST   /api/v3/strategies/{name}/copy         # Clone strategy
GET    /api/v3/strategies/evidence            # Combined event log
```

**Special Components:**
- Chart.js line chart (equity curve) with fill
- Monte Carlo: multiple light lines (opacity 0.3)
- Monthly returns heatmap (12 months × years)
- Parameter editor modal (JSON textarea with validation)
- Copy strategy modal

---

#### **Risk & Compliance** (`risk_management_compliance/code.html`)

**New Design Features:**
- CSS Grid layout: `grid-cols-[240px_1fr_340px]` with `grid-rows-[64px_1fr_300px]`
- 1px gap grid system (background color shows through)
- Top telemetry bar: VaR, Beta, Margin usage
- Left sidebar: Risk navigation (Risk Telemetry, Compliance, Stress Tests, Margin, Reports)
- Main area: Strategy risk metrics table
- Bottom panel: Compliance event log (scrollable)
- Right sidebar: Risk alerts, VaR breakdown, stress test results

**Files to Create:**
- `dashboard/templates/v3/pages/risk_compliance.html`
- `dashboard/static/v3/pages/risk_compliance.js`

**API Endpoints Needed:**
```
GET    /api/v3/risk/overview                # VaR, Beta, margin metrics
GET    /api/v3/risk/strategies              # Strategy risk metrics table
GET    /api/v3/risk/compliance/events       # Compliance log
GET    /api/v3/risk/alerts                  # Active risk alerts
GET    /api/v3/risk/stress-tests           # Stress test scenarios/results
```

---

#### **Backtesting Center** (`backtesting_center/code.html`)

**New Design Features:**
- Left sidebar (w-72): Configuration panel
  - Strategy select, symbol, timeframe, execution mode (OHLC/Every Tick)
  - Date range pickers
  - Parameter overrides table (from strategy.default_params)
  - RUN BACKTEST button with progress indicator
- Main content:
  - Summary metrics row (5 KPI tiles)
  - Equity & drawdown chart (dual axis)
  - Bottom row: Trade distribution histogram + Monthly returns heatmap
  - Run history table (expandable rows)
- Results modals for detailed view

**Files to Create:**
- `dashboard/templates/v3/pages/backtesting_center.html`
- `dashboard/static/v3/pages/backtesting_center.js`

**API Endpoints Needed:**
```
GET    /api/v3/backtest/strategies          # List strategies with default_params
GET    /api/v3/backtest/symbols             # Asset groups + metadata
GET    /api/v3/backtest/timeframes          # Available timeframes
POST   /api/v3/backtest/run                 # Queue backtest job
GET    /api/v3/backtest/runs                # Recent runs (with filters)
GET    /api/v3/backtest/run/{run_id}        # Full run with trades
GET    /api/v3/backtest/run/{run_id}/equity # Equity curve data
GET    /api/v3/backtest/run/{run_id}/distribution?bins=30
GET    /api/v3/backtest/run/{run_id}/monthly
DELETE /api/v3/backtest/run/{run_id}        # Cleanup
```

**Charts:**
- Equity/Drawdown: Chart.js line chart (2 datasets)
- Distribution: Histogram (bar chart)
- Monthly heatmap: Grid layout with colored cells

---

#### **ML Center** (`machine_learning_center/` + new functionality)

**Status:** Complete redesign + new functionality (user will provide new files)

**What We Know:**
- Reference template exists but ML layer needs "complete redesign"
- New files will be added to `dashscreens/stitch_savanna_quant_os/machine_learning_center/` to accommodate new functionality
- User will supply these files

**Action:** Wait for user to provide new ML design files, then:
- Create `dashboard/templates/v3/pages/ml_center.html` based on new spec
- Implement `dashboard/static/v3/pages/ml_center.js`
- Define v3 ML API endpoints as needed

**Anticipated Features** (based on v2 + likely enhancements):
- Model training interface (symbol, timeframe, model type, hyperparams)
- Model registry grid (status badges: pending/training/ready/active/failed)
- Feature importance visualization
- Deployed ML strategies management
- Live prediction stream
- Model performance metrics (accuracy, precision, recall, F1)
- Training history and artifact management

**Placeholder for now:** Mark as "awaiting design spec"

---

### 3.3 Pages That Stay the Same (No Top Bar Removed)

**AI Research** (`page_ai_research.html`)
- Keep current v2 implementation unchanged
- May need minor CSS updates to match design system colors
- Ensure it works with new base template (test sidebar compatibility)

**Trade Operations & Multi-Account Management**
- Not explicitly called out as "stays same" or "rebuild"
- **Decision:** Review after base template complete; likely need redesign to match new design language
- Status: Defer decision until phase 2

**Settings** (`page_settings.html`)
- Standalone page (no sidebar/topbar)
- Keep current layout (form-based settings)
- Match design system colors and typography
- Ensure form validation and save UX matches new patterns

---

## 4. API Endpoint Strategy

### 4.1 Backend Rebuild Note

> **IMPORTANT:** There will be a full backend rebuild alongside this frontend work. The frontend plan assumes v3 API endpoints will exist with potentially different routes and response formats. This plan focuses on frontend structure; API contracts to be defined separately.

### 4.2 Anticipated API Structure

Base path: `/api/v3/` (new versioned namespace)

```
/api/v3/
├── auth/
│   ├── login
│   └── refresh
├── account/
│   ├── stats
│   ├── snapshots
│   └── mt5/account
├── strategies/
│   ├── /
│   ├── {name}
│   ├── {name}/toggle
│   ├── {name}/params
│   ├── {name}/copy
│   ├── {name}/equity
│   ├── {name}/monte-carlo
│   ├── {name}/performance
│   ├── {name}/trades
│   ├── {name}/backtests
│   ├── {name}/evidence
│   └── {name}/versions
├── backtest/
│   ├── strategies
│   ├── symbols
│   ├── timeframes
│   ├── run
│   ├── runs
│   ├── run/{run_id}
│   ├── run/{run_id}/equity
│   ├── run/{run_id}/distribution
│   └── run/{run_id}/monthly
├── risk/
│   ├── overview
│   ├── strategies
│   ├── compliance/events
│   ├── alerts
│   └── stress-tests
├── ml/                         # ML Center (new)
│   ├── models
│   ├── train
│   ├── models/{id}
│   ├── models/{id}/deploy
│   ├── predict
│   ├── models/{id}/features
│   ├── retrain/{id}
│   └── history
├── quant/
│   ├── hypotheses
│   ├── hypotheses/{id}
│   ├── optimise
│   ├── optimise/{run_id}
│   └── optimise/{run_id}/deploy
├── ai/
│   ├── suggestions
│   ├── heatmap
│   ├── reasoning/{symbol}
│   ├── chat
│   ├── toggle
│   └── config
├── data/
│   ├── datasets
│   └── datasets/{symbol}/ohlcv
├── journal/
│   ├── annotations
│   └── annotations/{id}
└── settings/
    ├── effective
    └── update
```

**Note:** Some endpoints may stay at `/api/v2/` if backend not rebuilt; frontend should be configurable.

---

## 5. Shared Components Library

### 5.1 Reusable Jinja2 Partials (`dashboard/templates/v3/partials/`)

- `_kpi_tile.html` → Title, value, delta, icon, status color
- `_data_table.html` → Table with sticky header, sorting, pagination, row actions
- `_chart_card.html` → Card container with title, actions, Chart.js canvas, loading state
- `_status_badge.html` → Active/Inactive/Pending/Failed with appropriate colors
- `_form_field.html` → Label + input + error message + helper text
- `_modal.html` → Generic modal overlay with header, body, footer actions

### 5.2 JavaScript Utilities (`dashboard/static/v3/shared/`)

- `api.js`: Centralized fetch wrapper with JWT injection, error handling, retries
- `utils.js`: Date formatting, number formatting (currency, percentages), debounce
- `charts.js`: Chart.js defaults (colors, fonts), common chart types (line, bar, scatter, doughnut)
- `websocket.js`: WebSocket connection manager with auto-reconnect, event handlers
- `tables.js`: DataTable wrapper with sorting, filtering, pagination
- `forms.js`: Form validation, file uploads, progress tracking

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
1. Base template `_base.html` with collapsible sidebar + topbar
2. Design system Tailwind config (colors, spacing, typography) in base template
3. Theme toggle (dark/light) with localStorage persistence
4. Sidebar component with navigation items (drawn from config/routes)
5. Top bar component with notifications, profile, connect button
6. Shared CSS in `static/v3/shared/styles.css`
7. Basic app shell JS in `static/v3/app.js`

**Pages to Migrate (Test Base Template):**
- Login page (standalone, no base)
- Settings page (standalone, no base)

**Testing:**
- Verify sidebar collapse/expand
- Verify theme persistence
- Verify all pages render with base template structure

---

### Phase 2: Dashboard Pages (Week 3-4)

**Deliverables:**
1. Mission Control page (complete reference template)
2. Executive Analytics page
3. Portfolio Risk Monitor page
4. Research Lab page (per research_lab.md spec)
5. Hypotheses Center page (kanban board)
6. Optimization Hub page

**For Each Page:**
- Create HTML template extending base
- Create page-specific JS module
- Wire up API calls (mock data if v3 backend not ready)
- Implement charts (Chart.js configurations)
- Add polling/WebSocket for real-time data

**API Mocking:**
If v3 backend incomplete, create mock API layer in `static/v3/shared/api-mock.js` that:
- Returns realistic sample data
- Simulates network latency (200-500ms)
- Logs to console for debugging
- Can be toggled via `?mock=1` query param

---

### Phase 3: Core Trading Pages (Week 5-6)

**Deliverables:**
1. Strategy Library (complete rebuild from reference)
2. Risk & Compliance (complete rebuild from reference)
3. Backtesting Center (complete rebuild from reference)

**Complex Components:**
- Strategy Library: Detail panel slide-up, chart rendering, param editor modal
- Backtesting: Configuration form, run history, result visualization
- Risk: Risk grid layout, correlation matrix, compliance event feed

---

### Phase 4: AI/ML Pages (Week 7-8)

**Deliverables:**
1. AI Research page (minor update, verify compatibility)
2. ML Center (complete redesign based on new spec TBD)
   - Wait for user-provided ML design files
   - Implement new functionality as specified

**Deferred if ML Spec Not Ready:**
- Mark ML Center as placeholder with "Under Construction" notice
- Complete other pages first

---

### Phase 5: Remaining Pages & Polish (Week 9-10)

**Deliverables:**
1. Trade Operations page (review from v2, redesign to match design system)
2. Multi-Account Management page (review from v2, redesign to match design system)
3. Settings page (update form styling to new design system)
4. Any missing modal components (strategy copy, parameter edit, etc.)

**Polish Tasks:**
- Animations (framer motion or CSS transitions)
- Loading skeletons for all data fetches
- Error boundary handling
- Responsive breakpoints (mobile, tablet, desktop)
- Accessibility audit (ARIA labels, keyboard navigation)
- Cross-browser testing
- Performance optimization (code splitting, lazy loading)

---

## 7. Detailed File Change List

### Files to CREATE

**Templates (17 new):**
```
dashboard/templates/v3/_base.html
dashboard/templates/v3/_sidebar.html
dashboard/templates/v3/_topbar.html
dashboard/templates/v3/_theme.html
dashboard/templates/v3/pages/login.html
dashboard/templates/v3/pages/mission_control.html
dashboard/templates/v3/pages/executive_analytics.html
dashboard/templates/v3/pages/portfolio_risk.html
dashboard/templates/v3/pages/research_lab.html
dashboard/templates/v3/pages/hypotheses.html
dashboard/templates/v3/pages/optimization.html
dashboard/templates/v3/pages/strategy_library.html
dashboard/templates/v3/pages/risk_compliance.html
dashboard/templates/v3/pages/backtesting_center.html
dashboard/templates/v3/pages/ml_center.html
dashboard/templates/v3/pages/ai_research.html (copy from v2, update styles)
dashboard/templates/v3/pages/trade_operations.html (tbd)
dashboard/templates/v3/pages/multi_account.html (tbd)
dashboard/templates/v3/pages/settings.html (standalone)
dashboard/templates/v3/partials/_kpi_tile.html
dashboard/templates/v3/partials/_data_table.html
dashboard/templates/v3/partials/_chart_card.html
dashboard/templates/v3/partials/_status_badge.html
dashboard/templates/v3/partials/_form_field.html
dashboard/templates/v3/partials/_modal.html
```

**JavaScript (15+ modules):**
```
dashboard/static/v3/app.js
dashboard/static/v3/theme.js
dashboard/static/v3/components/sidebar.js
dashboard/static/v3/components/topbar.js
dashboard/static/v3/components/tables.js
dashboard/static/v3/components/charts.js
dashboard/static/v3/components/modals.js
dashboard/static/v3/shared/api.js
dashboard/static/v3/shared/api-mock.js (optional)
dashboard/static/v3/shared/utils.js
dashboard/static/v3/shared/charts.js
dashboard/static/v3/shared/forms.js
dashboard/static/v3/shared/websocket.js
dashboard/static/v3/pages/mission_control.js
dashboard/static/v3/pages/executive_analytics.js
dashboard/static/v3/pages/portfolio_risk.js
dashboard/static/v3/pages/research_lab.js
dashboard/static/v3/pages/hypotheses.js
dashboard/static/v3/pages/optimization.js
dashboard/static/v3/pages/strategy_library.js
dashboard/static/v3/pages/risk_compliance.js
dashboard/static/v3/pages/backtesting_center.js
dashboard/static/v3/pages/ml_center.js
dashboard/static/v3/pages/trade_operations.js (tbd)
dashboard/static/v3/pages/multi_account.js (tbd)
dashboard/static/v3/pages/settings.js
```

**CSS (optional custom):**
```
dashboard/static/v3/styles.css  (overrides, custom utilities)
```

**Backend Routes (if new v3 namespace):**
```
dashboard/routes/v3/__init__.py
dashboard/routes/v3/strategies.py
dashboard/routes/v3/backtesting.py
dashboard/routes/v3/risk.py
dashboard/routes/v3/ml.py
dashboard/routes/v3/quant.py
dashboard/routes/v3/ai.py
dashboard/routes/v3/account.py
dashboard/routes/v3/trades.py
dashboard/routes/v3/settings.py
```

**Tests:**
```
dashboard/tests/v3/test_templates.py
dashboard/tests/v3/test_static.py
dashboard/tests/v3/test_api_v3.py
```

---

### Files to MODIFY

1. **`main.py`** → Add route for v3 templates:
   ```python
   @app.get("/v3/{page_name}")
   async def serve_v3_page(page_name: str):
       # Render v3 template with base
   ```

2. **`dashboard/app.py`** → Mount new v3 routes under `/api/v3/` if separate namespace

3. **`dashboard/templates/login.html`** → Redesign to match institutional login reference

4. **`dashboard/templates/pages/settings.html`** → Update form styles to design system (keep standalone)

5. **`dashboard/static/v3/shared/api.js`** → Centralize all API calls with configurable base path (`/api/v3` or `/api/v2` fallback)

---

## 8. Design System Usage Guidelines

### 8.1 Color Semantics

| Semantic | Color | Usage |
|----------|-------|-------|
| Primary | `primary-container` (#00e5ff) | Primary actions, active states, highlights |
| On Primary | `on-primary` (#00363d) | Text on primary backgrounds |
| Background | `background` (#0B0F14) | Page background |
| Surface | `surface-container` (#1c2025) | Cards, panels, containers |
| On Surface | `on-surface` (#e0e2ea) | Primary text |
| Outline | `outline-variant` (#3b494c) | Borders, dividers, grid gaps |
| Error | `error` (#ffb4ab) / `error-container` (#93000a) | Errors, negative PnL |
| Success | Use `primary` for positive indicators | Win rate, profitable trades |

### 8.2 Typography Scale

| Class | Font | Size | Weight | Use |
|-------|------|------|--------|-----|
| `font-display-lg` | Geist | 32px | 600 | Page titles |
| `font-headline-md` | Geist | 20px | 600 | Section headers |
| `font-body-md` | Geist | 14px | 400 | Body text, labels |
| `font-label-sm` | JetBrains Mono | 11px | 500 | Table headers, metadata |
| `font-data-lg` | JetBrains Mono | 16px | 500 | Large KPIs |
| `font-data-md` | JetBrains Mono | 13px | 400 | Table data, numbers |

### 8.3 Spacing Rhythm

- Use multiples of `4px` for all margins, padding, gaps
- Standard cell padding: `px-2 py-1` (8px horizontal, 4px vertical)
- Panel gaps: Use `border-b border-r border-outline-variant` instead of margin gaps
- Container padding: `12px` around page edges

### 8.4 Component Patterns

**Card/Panel:**
```html
<div class="bg-surface-container border border-outline-variant">
  <div class="px-4 py-2 border-b border-outline-variant bg-surface-container-high">
    <h3 class="font-label-sm uppercase">Panel Title</h3>
  </div>
  <div class="p-4">Content</div>
</div>
```

**Button:**
```html
<button class="bg-primary-container text-on-primary font-label-sm px-4 py-2 rounded hover:opacity-90">
  Action
</button>
```

**Status Badge:**
```html
<span class="px-2 py-1 text-[10px] uppercase font-bold bg-primary-container/20 text-primary rounded">
  Active
</span>
```

---

## 9. Testing Strategy

### 9.1 Unit Tests
- Template rendering (Jinja2)
- JavaScript utilities (api.js, utils.js, charts.js)
- Component lifecycle (sidebar toggle, theme switch)

### 9.2 Integration Tests
- Page loads without JavaScript errors
- API calls resolve with proper error handling
- Charts render with mock data
- Real-time updates via WebSocket (if used)

### 9.3 Manual Testing Checklist
- [ ] Sidebar collapses to icons only (48px width)
- [ ] Main content area adjusts width on sidebar toggle
- [ ] Theme toggle switches between dark/light (persists on reload)
- [ ] All pages accessible via navigation
- [ ] Mobile layout: sidebar becomes drawer or hamburger menu
- [ ] Tables render with sticky headers
- [ ] Charts render responsive to container resize
- [ ] All API calls include JWT authorization header
- [ ] Error states display user-friendly messages
- [ ] Loading states show spinners/skeletons

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend API not ready | High | Use mock API layer; frontend can develop independently |
| ML redesign spec delayed | Medium | Defer ML Center until spec finalized; complete other pages first |
| Design system inconsistencies | Medium | Create shared partials/components early; enforce via code review |
| Reference templates incomplete | Low | Fill gaps with v2 patterns adapted to design system |
| Browser compatibility issues | Low | Test on Chrome/Firefox/Safari; use autoprefixer if needed |
| Performance regressions | Medium | Lazy load page-specific JS; optimize chart rendering |
| Responsive layout issues | Medium | Implement mobile-first breakpoints; test on viewport sizes |

---

## 11. Success Metrics

- **Design System Adoption:** All v3 pages use consistent colors, typography, spacing
- **Component Reuse:** ≥70% of UI elements built from shared partials/components
- **Code Quality:** Zero console errors, TypeScript/ESLint clean, responsive on all breakpoints
- **Performance:** Page load < 2s, charts render < 500ms, smooth animations (60fps)
- **Accessibility:** WCAG AA compliance (contrast ratios, keyboard nav, ARIA labels)
- **User Acceptance:** Stakeholder sign-off on visual design and interaction patterns

---

## 12. Next Steps

1. **Review this plan with stakeholders** → Get alignment on architecture, priorities, timeline
2. **Set up v3 folder structure** → Create `templates/v3/`, `static/v3/` directories
3. **Implement base template** → Start with `_base.html`, sidebar, topbar, theme toggle
4. **Create design system documentation** → Living style guide with color, typography, component examples
5. **Begin Phase 1 implementation** → Foundation work (base template, login, settings)

---

**Appendix A:** Reference Templates Summary  
**Appendix B:** API Mocking Strategy (detailed)  
**Appendix C:** Migration Guide from v2 to v3 (for any reusable logic)  
**Appendix D:** Backend API Contract Template (to be filled by backend team)

---

## Appendix A: Reference Templates Quick Reference

| Reference Path | Page | Key Components |
|----------------|------|----------------|
| `institutional_login_gate/code.html` | Login | Scanner beam, grid bg, glass panel, typing effect |
| `mission_control_dashboard_2/code.html` | Mission Control | KPI tiles, trading-grid, strategy cards, live logs terminal |
| `executive_analytics_reporting/code.html` | Executive Analytics | NAV chart, allocation donut, risk/return scatter, drawdown profile |
| `portfolio_risk_monitor/code.html` | Portfolio Risk | Risk grid layout, positions table, allocation donut (canvas), correlation matrix |
| `research_lab/research_lab.md` | Research Lab | 3-panel layout, dataset explorer, notebook workspace, observation panel |
| `hypothesis_center/code.html` | Hypotheses | Kanban board, draggable cards, status columns, progress indicators |
| `optimization_hub/code.html` | Optimization | Parameter surface heatmap (canvas), top results table, history list |
| `strategy_library/code.html` | Strategy Library | Grid layout, detail panel slide-up, charts (equity/MC/monthly), view toggles |
| `risk_management_compliance/code.html` | Risk & Compliance | 3-column grid, telemetry bar, sidebar nav, compliance log |
| `backtesting_center/code.html` | Backtesting | Config sidebar, equity/drawdown chart, distribution + monthly heatmap |
| `machine_learning_center/` | ML Center | **Awaiting new spec** |

---

## Appendix B: API Mocking Strategy (Detailed)

### When to Use Mocks
- V3 backend endpoints not yet implemented
- Frontend development needs realistic data structures
- Integration testing isolation

### Mock Implementation

**File:** `dashboard/static/v3/shared/api-mock.js`

```javascript
const MOCK_DELAY = 300; // ms

const mockResponses = {
  '/api/v3/account/stats': {
    equity: 12482904.32,
    balance: 12000000,
    margin: 1775000,
    realized_pnl: 142502.11,
    unrealized_pnl: 44000,
    timestamp: new Date().toISOString()
  },
  '/api/v3/strategies/': [
    {
      name: 'momentum_reversion',
      label: 'Momentum Reversion',
      symbol: 'BTCUSD',
      timeframe: 'M15',
      is_active: true,
      version: 3,
      stats: {
        trades: 142,
        win_rate: 0.68,
        avg_pnl_r: 0.234,
        net_pnl_r: 33.2,
        profit_factor: 2.1,
        max_drawdown: 0.042,
        sharpe: 2.84
      }
    },
    // ... more strategies
  ],
  // ... other endpoints
};

export async function mockFetch(url, options) {
  await new Promise(resolve => setTimeout(resolve, MOCK_DELAY));
  
  const path = new URL(url, 'http://localhost').pathname;
  if (mockResponses[path]) {
    return {
      ok: true,
      json: async () => mockResponses[path]
    };
  }
  
  return {
    ok: false,
    status: 404,
    json: async () => ({ error: 'Mock endpoint not found' })
  };
}
```

**Usage in `api.js`:**
```javascript
const USE_MOCKS = window.location.search.includes('mock=1');

export async function apiFetch(endpoint, options = {}) {
  if (USE_MOCKS) {
    return mockFetch(endpoint, options);
  }
  // Real API call...
}
```

---

## Appendix C: Migration Guide from v2 to v3

### Template Changes
1. Remove hardcoded sidebar HTML from v2 page templates
2. Replace with `{% extends "v3/_base.html" %}`
3. Move page content into `{% block content %}...{% endblock %}`
4. Update CSS class names to match new design system (e.g., `bg-surface-container` vs `bg-gray-900`)

### JavaScript Changes
1. Remove inline scripts from templates
2. Move to page-specific module in `static/v3/pages/{page}.js`
3. Use shared utilities from `shared/` directory
4. Replace direct `fetch()` calls with `apiFetch()` wrapper
5. Use Chart.js configs from `shared/charts.js`

### API Changes
1. Check if v2 endpoints still exist in v3 backend
2. Update endpoint paths from `/api/...` to `/api/v3/...` as needed
3. Adapt to new response formats (if changed)
4. Add error handling for network failures

---

## Appendix D: Backend API Contract Template

To be completed by backend team for each endpoint:

```
Endpoint: GET /api/v3/strategies/
Method: GET
Description: List all strategies with computed statistics
Response:
{
  "strategies": [
    {
      "name": "momentum_reversion",
      "label": "Momentum Reversion",
      "symbol": "BTCUSD",
      "timeframe": "M15",
      "is_active": true,
      "version": 3,
      "stats": {
        "trades": 142,
        "win_rate": 0.68,
        "avg_pnl_r": 0.234,
        "net_pnl_r": 33.2,
        "profit_factor": 2.1,
        "max_drawdown": 0.042,
        "sharpe": 2.84
      }
    }
  ]
}
Error Codes: 401, 403, 500
```

---

**End of Plan**

*Prepared for: Savanna Capital v3 Redesign*  
*Focus: Frontend UI/UX Rebuild with Design System + Collapsible Layout*  
*Parallel Effort: Full Backend Rebuild (separate tracking)*
