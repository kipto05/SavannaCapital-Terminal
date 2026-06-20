# Research Lab v3 Implementation Plan

**Date**: 2025-06-19  
**Branch**: v3-dashboard  
**Phase**: PHASE 7 (V3_SEQUENTIAL_BUILD_PLAN.md)  
**Priority**: HIGH

---

## Executive Summary

The Research Lab is the quantitative research workspace where researchers explore datasets, write code, generate observations, and commit validated findings into the formal hypothesis pipeline.

This plan covers:
- **Frontend**: Complete v3 implementation following the design system
- **Backend**: No changes required (existing API sufficient)
- **Execution**: Mock Python execution for now (real execution deferred to future phase)
- **File Uploads**: Stub implementation (UI only, backend not implemented)
- **Timeline**: 1-2 days for functional UI with mocks

---

## Current State Assessment

### What Exists
- ✅ `Hypothesis` model in `db/models.py`
- ✅ POST `/api/quant/hypotheses` endpoint in `dashboard/routes/quant.py`
- ✅ v3 foundation: `_base.html`, design system, sidebar, topbar
- ✅ Reference templates: `dashscreens/.../research_lab/code.html` and `research_lab.md`

### What's Missing
- ❌ `dashboard/templates/v3/pages/research_lab.html` (new)
- ❌ `dashboard/static/v3/pages/research_lab.js` (new)
- ❌ Python execution backend (major undertaking)
- ❌ Secure file upload infrastructure
- ❌ Jupyter kernel integration
- ❌ Notebook persistence

---

## Python Execution Feasibility Analysis

### Option 1: Full Jupyter Kernel Integration (复杂, 高风险)

**Technical Requirements:**
- Install `jupyter_client`, `ipykernel` in venv
- spawn kernel process per research session
- Execute code in isolated namespace
- Capture stdout, stderr, display_data messages
- Handle kernel lifecycle (start, interrupt, restart)
- Implement resource limits (memory, timeout, CPU)
- Security: sandboxing, code injection prevention

**Complexity**: HIGH
- Kernel management across multiple users/sessions
- Async execution streaming to frontend via WebSocket
- File system isolation (chroot/jail)
- Package management (which conda env to use)
- GPU allocation coordination
- Session persistence across restarts

**Estimated Effort**: 3-5 days minimum for basic functionality, 2-3 weeks for production-ready with security

**Risk**: HIGH - introduces code execution vulnerabilities if not perfectly isolated

---

### Option 2: Restricted Python exec() with Sandbox (中等)

Use `exec()` in separate process with:
- Restricted builtins (no `import`, no `open`, no `eval`)
- AST pre-check to block dangerous operations
- Timeout enforcement via `signal.alarm` or multiprocessing timeout
- Memory limits via `resource.setrlimit`
- Whitelist of allowed modules: `numpy`, `pandas`, `scipy`, `sklearn`

**Complexity**: MEDIUM
- Building robust sandbox is non-trivial
- `exec()` cannot truly sandbox in Python (there are escape mechanisms)
- Need custom AST validator
- Must prevent infinite loops, memory bombs

**Estimated Effort**: 2-3 days for basic sandbox, 1 week for hardened version

**Risk**: MEDIUM - potential for code execution escapes if sandbox incomplete

---

### Option 3: Mock Execution (即插即用)

Simulate code execution with:
- Pre-defined outputs for known code blocks
- Random or seeded "realistic" output
- No actual Python runtime
- UI fully functional but logic fake

**Complexity**: LOW
- Simple JavaScript delays and string replacements
- All outputs hardcoded or procedurally generated
- No security concerns

**Estimated Effort**: 2-4 hours

**Risk**: LOW - production-ready UI, backend logic deferred

---

## Recommendation: Hybrid Approach

**Phase 1 (Now)**: Implement full UI with mock execution
- Users get complete interactive experience
- No security risks
- Fast delivery
- Easy to swap in real execution later

**Phase 2 (Future)**: Add restricted Python execution backend
- Create separate service: `/api/v2/research/execute`
- Executes in celery worker with resource limits
- Restricted namespace, timeout, memory cap
- Allow selected modules only
- Gradual rollout with feature flag

**Rationale**:
- Trading platform security is paramount - never rush code execution
- UI validation is valuable even without real execution
- Future execution service can be independently audited
- Allows stakeholders to approve UX before major backend investment

---

## File Upload Strategy

### Current State
No file upload infrastructure exists in the project.

### Implementation Options

**Option A: S3/Blob Storage Production**
- Upload to cloud storage with presigned URLs
- Scan for viruses (ClamAV)
- Validate file types (CSV, PDF, Py, IPYNB only)
- Size limits: 500MB max
- Retain metadata in DB: `ResearchDataset` model needed

**Complexity**: MEDIUM-HIGH (requires cloud setup, security scanning)

**Option B: Local Disk (Dev Only)**
- Save to `uploads/research/` with UUID filenames
- No scanning
- No persistence guarantees
- Manual cleanup

**Complexity**: LOW

**Option C: Stub Only (Recommended for v3 launch)**
- "Import New Data" button shows modal: "Feature coming in Q3 2025"
- Disabled file input
- Mock "Import successful" after delay

**Complexity**: TRIVIAL

**Recommendation**: Option C for now, plan Option A for Q3 release

---

## Backend Schema Changes (If Real Execution)

### New Models Required

```python
# db/models.py additions

class ResearchSession(Base):
    __tablename__ = "research_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    status = Column(String(20))  # active, archived
    kernel_state = Column(String(20))  # running, idle, dead
    metadata = Column(JSON)  # GPU used, memory, etc.

class ResearchDataset(Base):
    __tablename__ = "research_datasets"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"))
    name = Column(String(200))
    symbol = Column(String(20))
    timeframe = Column(String(10))
    file_path = Column(String(500))  # path on disk or S3 URL
    record_count = Column(Integer)
    loaded_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

class NotebookBlock(Base):
    __tablename__ = "notebook_blocks"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"))
    block_type = Column(String(20))  # code, markdown, visualization
    content = Column(Text)  # code or markdown
    output = Column(Text)  # execution result
    output_type = Column(String(20))  # stdout, png, json
    execution_count = Column(Integer)
    last_executed = Column(DateTime(timezone=True))
    order_index = Column(Integer)

class Observation(Base):
    __tablename__ = "research_observations"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"))
    hypothesis_id = Column(Integer, ForeignKey("hypotheses.id"), nullable=True)
    type = Column(String(30))  # STAT_SIG, ANOMALY, DATA_GAP, etc.
    title = Column(String(200))
    content = Column(Text)
    tags = Column(ARRAY(String))
    confidence = Column(Float)
    created_at = Column(DateTime(timezone=True))
    author_id = Column(Integer, ForeignKey("users.id"))
```

**Migrations Required**: 2-3 new Alembic revisions

---

## Detailed Task List

### Section A: Template Implementation

**Task A1**: Create base HTML structure with 3-panel layout
- Extend `v3/_base.html`
- Add research pipeline breadcrumb
- Create left panel (w-64) for dataset explorer
- Create center panel (flex-1) for notebook
- Create right panel (w-80) for observations
- Apply design system classes correctly

**Task A2**: Implement Dataset Explorer panel
- Header: "Available Datasets" with filter icon
- Dataset categories (Metals, Crypto, Equities)
- Dataset items: icon + name + size (hover reveal)
- "LOADED" badge for active dataset
- "Import New Data" button (stub, disabled)
- Use hardcoded `datasetMeta` from spec

**Task A3**: Implement Research Workspace (Notebook)
- Tab bar with file tabs (dataset file), "Run All" button, kernel status badge
- Notebook body with code blocks (syntax-highlighted HTML)
- Default code blocks:
  * Section 01: Environment Setup (load dataset)
  * Section 02: Hypothesis Generation (z-score calc)
- Markdown block with description
- Visualization placeholder: "Alpha Signal Intensity Map"
- Each code block has run button and collapsible output area

**Task A4**: Implement Observations Panel
- Header: "Key Observations" with subtitle
- Pre-loaded demo observation cards (3 cards: STAT_SIG, ANOMALY, DATA_GAP)
- Observation card structure: type badge, timestamp, content, tags
- Add observation form: type selector, notes textarea, "Add" button
- Workspace stats grid (RAM, GPU, Jobs, Runtime)
- "Commit to Hypothesis" button (primary, fixed at bottom)

**Task A5**: Add JavaScript module loading to template
- Include `research_lab.js` at bottom of page
- Initialize on DOMContentLoaded
- Call `initResearchLab()` function

---

### Section B: JavaScript Implementation

**Task B1**: Define data structures and state
```javascript
const ResearchLab = {
  _activeDataset: null,
  _observations: [], // array of observation objects
  _runtimeTimer: null,
  datasetMeta: {  // hardcoded from spec
    Metals: [
      { name: "XAUUSD_M15_2024", size: "2.3 MB", timeframe: "M15", symbol: "XAUUSD" },
      { name: "XAGUSD_M15_2024", size: "1.8 MB", timeframe: "M15", symbol: "XAGUSD" }
    ],
    "Crypto (L2)": [
      { name: "BTCUSD_OB_50ms_2024", size: "4.1 MB", timeframe: "M15", symbol: "BTCUSD" },
      { name: "ETHUSD_L2_Full_2024", size: "3.9 MB", timeframe: "M15", symbol: "ETHUSD" }
    ],
    Equities: [
      { name: "AAPL_M5_2024", size: "2.0 MB", timeframe: "M5", symbol: "AAPL" },
      { name: "TSLA_M5_2024", size: "1.7 MB", timeframe: "M5", symbol: "TSLA" }
    ]
  },
  mockObs: [ /* 3 demo cards */ ],
  runtimeStats: { ram: 2.4, gpu: 0, jobs: 0, runtime: "00:14:23" }
};
```

**Task B2**: Implement `renderDatasets()`
- Loop through `datasetMeta` categories
- Create category headers
- Create dataset items with hover effects
- Add click handler to call `activateDataset(dataset.name)`
- Mark currently active dataset with special styling + "LOADED" badge

**Task B3**: Implement `activateDataset(datasetName)`
- Find dataset in `datasetMeta`
- Set `_activeDataset`
- Update UI: add "LOADED" badge to selected item
- Call `loadNotebook(dataset)` to populate code blocks
- Add file tab for dataset (if not already open)
- Render Viz placeholder

**Task B4**: Implement `loadNotebook(dataset)`
- Populate code block placeholders with dataset-specific code:
  ```python
  df = sc.load_dataset("{datasetName}", start="2023-10-01")
  print(f"Loaded {len(df)} bars")
  ```
- Show notebook workspace
- Clear previous outputs

**Task B5**: Implement `runBlock(blockId)`
- Find code block element
- Show "running" spinner/status
- Set 700ms timeout
- Insert mock output after delay:
  * For Section 01: "Loaded 4320 bars\nmean=1.234, std=0.056"
  * For Section 02: "Found 68 potential alpha signals"
- Enable "Commit to Hypothesis" button after both blocks run

**Task B6**: Implement `renderViz()`
- Create 10×14 grid (140 cells)
- Generate colors: base on dataset name (consistent seed)
- Use HSL with fixed saturation/lightness, hue varies
- Render as div grid or canvas
- Add title "Alpha Signal Intensity Map"

**Task B7**: Implement observation management
- `renderObservations()`: display `_observations` array as cards
- `addObservation()`: read type + notes from form, create card object, unshift to array, re-render
- Cards have: type badge (color-coded), timestamp, content, tags
- "Delete" button on each (removes from array)

**Task B8**: Implement `commitObservation()`
- Gather payload:
  ```json
  {
    title: datasetName,
    description: combined observation notes (last 3 cards),
    symbol: dataset.symbol,
    timeframe: dataset.timeframe,
    status: "DRAFT"
  }
  ```
- POST to `/api/quant/hypotheses` using `apiFetch`
- On success:
  * Dispatch custom event `research.hypothesis.created`
  * Show toast "Hypothesis created, redirecting..."
  * `setTimeout(() => window.location.href = '/hypotheses', 600ms)`
- On error: show error toast

**Task B9**: Implement `updateRuntimeStats()`
- Every 5s, increment runtime counter
- Randomize RAM usage (±0.1 GB), GPU (±2%), jobs (0-1)
- Update DOM elements with formatted values
- Start timer on page load, clear on unmount

**Task B10**: Implement terminal chat `sendChat()`
- Get input from `#terminal-input`
- POST to `/api/v2/ai/chat` with `{query, context?}`
- On response, append to `#terminal-output`:
  * User query (prefixed "> ")
  * AI answer (plain text)
  * If `sql` field present, display in code block with syntax highlighting
- Clear input after send
- Support Enter key to submit

**Task B11**: Initialize on page load
```javascript
document.addEventListener('DOMContentLoaded', () => {
  initResearchLab();
});

function initResearchLab() {
  renderDatasets();
  renderObservations(); // demo cards
  startRuntimeUpdates();
  setupEventListeners();
}
```

---

### Section C: Integration & Polish

**Task C1**: Add route for Research Lab in `dashboard/app.py`
- Verify `/research` route exists (should map to `templates/v3/pages/research_lab.html`)
- If not, add:
  ```python
  @app.get("/research")
  async def research_lab():
      return templates.TemplateResponse("v3/pages/research_lab.html", {"request": request})
  ```
- Add to sidebar navigation

**Task C2**: Check shared dependencies
- Verify `apiFetch` exists in `shared/api.js` with correct base URL
- Verify Chart.js available if needed (not required for current spec)
- Verify design system CSS loaded in `_base.html`

**Task C3**: Test mock data flows end-to-end
- Load page → dataset explorer renders categories
- Click dataset → notebook loads, file tab added
- Click "Run All" or individual run buttons → outputs appear
- Render visualization → grid displays
- Add observation → card appears
- Commit → POST to hypotheses, redirect to /hypotheses
- Verify Hypotheses page receives custom event and refreshes

**Task C4**: Error handling and edge cases
- What if dataset not found in `datasetMeta`? (should never happen)
- What if POST fails? Show error toast, don't redirect
- What if user adds empty observation? Disable button or show validation
- What if terminal chat fails? Show error in output area

**Task C5**: Responsive design check (mobile/tablet)
- On small screens, panels collapse to drawers?
- Follow design system breakpoints
- Touch interactions for dataset items
- Horizontal scroll for tabs if needed

---

### Section D: Future-Proofing (Optional, Low Priority)

**Task D1**: Add feature flag for "real execution" toggle
- Read from `config.research.enable_real_execution`
- If false (default), show "Mock execution mode" banner
- If true, attempt WebSocket connection to kernel service

**Task D2**: Create stub endpoint for real execution (returns 501)
```python
# In dashboard/routes/quant.py or new router
@router.post("/execute")
async def execute_code(body: dict[str, Any]):
    # TODO: Implement kernel execution
    raise HTTPException(501, "Real code execution not yet implemented")
```

**Task D3**: Document migration path to real execution
- Write README in `research/` directory explaining architecture
- Outline steps to implement Jupyter integration
- Security considerations checklist

---

## Implementation Order

**Phase 1 (Day 1 - Morning)**:
1. Task A1-A5 (complete template)
2. Task B1-B3 (dataset selection working)
3. Basic verification (Task C1-C3 partial)

**Phase 2 (Day 1 - Afternoon)**:
4. Task B4-B6 (notebook execution + viz)
5. Task B7-B8 (observations + commit)
6. Task B9-B10 (runtime stats + terminal)
7. Full integration testing (Task C3-C5)

**Phase 3 (Day 2 - Polish)**:
8. Bug fixes and edge cases (Task C4)
9. Responsive design adjustments (Task C5)
10. Documentation (Task D3)
11. Optional: feature flag stub (Task D1-D2)

**Buffer**: 4-8 hours for unexpected issues

---

## Backend Schema Requirements (Future Real Execution)

If we move to real Python execution, we need:

1. **Alembic migration** to create:
   - `research_sessions`
   - `research_datasets`
   - `notebook_blocks`
   - `research_observations` (may already exist as Hypothesis? check)

2. **New router**: `dashboard/routes/research.py`
   - POST `/execute` - execute code block in sandbox
   - POST `/datasets/import` - upload and register dataset
   - GET `/sessions` - list/resume sessions
   - WebSocket `/ws/session/{id}` - streaming execution output

3. **Celery tasks**:
   - `research.execute_code_async(session_id, code)`
   - Sandbox with resource limits

4. **Security hardening**:
   - Run in separate Docker container (no host access)
   - Read-only filesystem except `/tmp`
   - Network isolation (no external calls)
   - CPU/memory limits via cgroups

---

## Testing Checklist

### Unit Tests (JavaScript)
- [ ] `renderDatasets()` produces correct DOM structure
- [ ] `activateDataset()` updates `_activeDataset` and UI
- [ ] `runBlock()` shows output after delay
- [ ] `renderViz()` creates 140 cells with deterministic colors
- [ ] `addObservation()` adds to array and re-renders
- [ ] `commitObservation()` POSTs correct payload
- [ ] `updateRuntimeStats()` updates every 5s

### Integration Tests
- [ ] Page loads without 404s
- [ ] All CSS classes resolve (no missing design system tokens)
- [ ] All API calls use `apiFetch` with proper auth headers
- [ ] POST `/api/quant/hypotheses` succeeds (check DB)
- [ ] Redirect to `/hypotheses` works
- [ ] Custom event `research.hypothesis.created` dispatched

### Manual QA
- [ ] Open Chrome DevTools, no console errors
- [ ] All interactive elements clickable
- [ ] Dataset hover effects smooth
- [ ] Code block run buttons show spinner/feedback
- [ ] Visualization renders with correct colors
- [ ] Observation cards can be added and deleted
- [ ] Commit button creates hypothesis in DB
- [ ] Redirect shows Hypotheses page with new card

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Python execution complexity | High | Certain | Use mock for v3 launch; defer real execution |
| File upload security | High | N/A (stub) | Not implemented; stub UI only |
| Performance with large datasets | Medium | Low | Mock data only; real datasets not loaded |
| Hypothesis commit failure | Medium | Low | Validate payload before POST; show error toast |
| Design system class errors | Low | Medium | Copy from existing pages, verify Tailwind config |

---

## Success Criteria

- [ ] Page renders with 3-panel layout matching reference
- [ ] Dataset explorer shows all categories and datasets
- [ ] Clicking dataset activates it and loads notebook code
- [ ] "Run All" button generates mock outputs after ~700ms
- [ ] Alpha Signal Intensity Map displays as 10×14 colored grid
- [ ] 3 demo observation cards visible on page load
- [ ] "Add Observation" creates new card with selected type
- [ ] "Commit to Hypothesis" POSTs successfully and redirects to /hypotheses
- [ ] Runtime stats (RAM, GPU, Jobs, Runtime) update every 5 seconds
- [ ] Terminal chat accepts input and displays mock/recent AI responses
- [ ] Zero JavaScript console errors
- [ ] Page responsive on mobile (panels collapse to drawers/hamburger)

---

## Appendix A: datasetMeta Structure

```javascript
{
  Metals: [
    { name: "XAUUSD_M15_2024", size: "2.3 MB", timeframe: "M15", symbol: "XAUUSD" },
    { name: "XAGUSD_M15_2024", size: "1.8 MB", timeframe: "M15", symbol: "XAGUSD" }
  ],
  "Crypto (L2)": [
    { name: "BTCUSD_OB_50ms_2024", size: "4.1 MB", timeframe: "M15", symbol: "BTCUSD" },
    { name: "ETHUSD_L2_Full_2024", size: "3.9 MB", timeframe: "M15", symbol: "ETHUSD" }
  ],
  Equities: [
    { name: "AAPL_M5_2024", size: "2.0 MB", timeframe: "M5", symbol: "AAPL" },
    { name: "TSLA_M5_2024", size: "1.7 MB", timeframe: "M5", symbol: "TSLA" }
  ]
}
```

---

## Appendix B: Mock Outputs

**Code Block 01 Output**:
```
Loaded 4320 bars
mean=1.234, std=0.056
```

**Code Block 02 Output**:
```
Found 68 potential alpha signals
Z-score threshold: 2.4
Win-rate estimate: 68% over 500ms horizon
```

---

## Appendix C: Observation Types

```javascript
const OBSERVATION_TYPES = [
  "STAT_SIG",      // Primary finding, actionable
  "ANOMALY",       // Unexpected pattern, investigate
  "DATA_GAP",      // Missing or corrupted data
  "VOLATILITY",    // Volatility regime change
  "REGIME_SHIFT",  // Market structure shift
  "MODEL_ALERT",   // ML model prediction drift
  "CORRELATION",   // Unusual correlation pattern
  "RISK"           // Risk warning
];
```

---

## Appendix D: API Payload Examples

### POST /api/quant/hypotheses

```json
{
  "title": "BTC Mean Reversion Alpha",
  "description": "Z-score thresholds above 2.4 showing 68% win-rate for mean reversion over 500ms horizon. Detected during London/NY overlap session.",
  "symbol": "BTCUSD",
  "timeframe": "M15",
  "status": "DRAFT"
}
```

Success Response (201):
```json
{
  "id": 42,
  "title": "BTC Mean Reversion Alpha",
  "description": "...",
  "status": "DRAFT",
  "created_at": "2025-06-19T14:23:45Z"
}
```

---

## Appendix E: Color Palette for Viz Grid

Use HSL with fixed saturation (70%) and lightness (50-70%):
- Hue: derived from dataset name hash
- Example: `hsl(${hash % 360}, 70%, 60%)`
- 10 rows × 14 cols = 140 cells

---

## Appendix F: References

- DASHBOARD_DOCUMENTATION.md pp.1247-1386 (Research Lab spec)
- V3_FRONTEND_REDESIGN_PLAN.md Section 3.2 (Research Lab)
- V3_SEQUENTIAL_BUILD_PLAN.md PHASE 7
- `dashscreens/stitch_savanna_quant_os/research_lab/code.html` (visual reference)
- `dashscreens/stitch_savanna_quant_os/research_lab/research_lab.md` (spec)

---

**END OF IMPLEMENTATION PLAN**
