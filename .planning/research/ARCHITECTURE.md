# Architecture Patterns — Broker Redesign Integration

**Domain:** Insurance broker module — Claude Code skills, hooks, portal automation, frontend redesign
**Researched:** 2026-04-15
**Confidence:** HIGH (all 7 areas verified against existing codebase)

---

## Recommended Architecture

Three-layer split (already decided, documented in SPEC-BROKER-REDESIGN.md):

| Layer | Role | Communication |
|-------|------|---------------|
| **Claude Code** | Intelligence (AI tasks) | REST API via httpx/curl to backend |
| **Backend** | Data (CRUD, state machines, deterministic engines) | FastAPI, PostgreSQL, Supabase Storage |
| **Frontend** | Presentation (display, approval gates, upload) | React Query to backend API |

This document focuses on **how each new integration area connects** to the existing architecture.

---

## Integration Area 1: Skills Calling Backend REST API

### Current State
- Backend exposes 50+ endpoints under `/api/v1/broker/*` via FastAPI sub-routers in `backend/src/flywheel/api/broker/`
- Frontend authenticates via Bearer token from `useAuthStore` (Supabase auth JWT)
- Backend uses `get_tenant_db` dependency for tenant-isolated sessions with RLS

### Integration Pattern

**Auth flow for skills:**
Skills run in Claude Code (user's terminal). They need a Bearer token to call backend endpoints.

```
User's Claude Code session
  -> Skill reads FLYWHEEL_API_TOKEN from environment
  -> Skill calls backend via httpx (Python) or curl (Bash)
  -> Backend validates JWT via existing auth middleware
  -> Backend applies RLS tenant isolation (same as frontend requests)
```

**Token source:** The spec defines `FLYWHEEL_API_TOKEN` environment variable. This must be set during session start. Two options:
1. **SessionStart hook** reads token from a known location (e.g., `~/.flywheel/token`) and exports it
2. **MCP session context** provides the token (if Flywheel MCP server runs with auth context)

**Recommendation:** Use option 1 (SessionStart hook). The existing `pre-read-context.py` hook already runs at session start and could be extended to export the token. This keeps auth centralized.

**Error handling pattern for skills:**
```python
import httpx, os, sys

API_URL = os.environ.get('FLYWHEEL_API_URL', 'http://localhost:8000/api/v1')
API_TOKEN = os.environ.get('FLYWHEEL_API_TOKEN', '')

async def api_call(method, path, **kwargs):
    if not API_TOKEN:
        print("Warning: FLYWHEEL_API_TOKEN not set. Backend calls will fail.")
        return None
    headers = {'Authorization': f'Bearer {API_TOKEN}', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await getattr(client, method)(f"{API_URL}{path}", headers=headers, **kwargs)
        if resp.status_code == 401:
            print("Auth expired. Re-authenticate and try again.")
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()
```

**Session management:** No session to manage. Each API call is stateless (JWT Bearer token). Token expiry is the only concern -- skills should check for 401 and surface a clear message.

### Components

| Component | Status | File |
|-----------|--------|------|
| Token export in SessionStart hook | **NEW** | `~/.claude/hooks/flywheel/pre-read-context.py` (extend) |
| Shared API helper for skills | **NEW** | `~/.claude/skills/broker/scripts/api_client.py` |
| Backend auth middleware | **EXISTING** | `backend/src/flywheel/auth/jwt.py` |
| Backend broker endpoints | **EXISTING** | `backend/src/flywheel/api/broker/*.py` |
| Batch coverage create endpoint | **NEW** | `backend/src/flywheel/api/broker/projects.py` |

### Data Flow

```
Skill SKILL.md
  -> Reads project context (MCP or API)
  -> AI processing (contract parsing, quote extraction)
  -> POST/PUT/PATCH to backend REST API
  -> Backend writes to PostgreSQL (tenant-isolated)
  -> Frontend polls via React Query (refetchInterval)
  -> UI updates automatically
```

---

## Integration Area 2: Hooks Auto-Triggering Backend Endpoints

### Current State
- 12 hooks already configured in `~/.claude/settings.json`
- Hooks use `read_event()` from shared `hook_utils.py` to parse stdin JSON
- Hooks are Python/Bash scripts, exit 0 for success, non-zero to block
- PreToolUse hooks can return `{"decision": "block", "reason": "..."}` to prevent tool execution
- PostToolUse hooks fire after tool completion (non-blocking)

### Integration Pattern

**Hook scripts that call backend API** need to:
1. Read the tool event from stdin (existing `read_event()` pattern)
2. Pattern-match the tool input to detect broker-relevant operations
3. Call the backend endpoint (same auth pattern as skills)
4. Exit 0 regardless of API call success (hooks must not block conversation)

**Event format for PostToolUse (Bash matcher):**
```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "curl -X PATCH .../broker/coverages/abc123 ..."},
  "tool_output": {"stdout": "...", "stderr": "...", "exit_code": 0}
}
```

**Pattern matching in hooks:**
```python
event = read_event()
command = event.get("tool_input", {}).get("command", "")

# Detect coverage write
if re.search(r'broker/(projects/[^/]+/coverages|coverages/[^/]+)', command):
    project_id = extract_project_id(command)
    # Call gap analysis
    api_call("post", f"/broker/projects/{project_id}/analyze-gaps")
```

**API URL discovery:** Hooks use `FLYWHEEL_API_URL` environment variable (same as skills). Default: `http://localhost:8000/api/v1`. Set in SessionStart hook alongside the token.

**Critical design decision:** Hook API calls must be fire-and-forget with timeout. A hook that hangs waiting for a slow backend response will block the conversation. Use `httpx.AsyncClient(timeout=5)` or subprocess with timeout.

### Components

| Component | Status | File |
|-----------|--------|------|
| `post-coverage-write.py` | **NEW** | `~/.claude/skills/broker/hooks/post-coverage-write.py` |
| `post-quote-write.py` | **NEW** | `~/.claude/skills/broker/hooks/post-quote-write.py` |
| `pipeline-check.py` | **NEW** | `~/.claude/skills/broker/hooks/pipeline-check.py` |
| `pre-portal-validate.py` | **NEW** | `~/.claude/skills/broker/hooks/pre-portal-validate.py` |
| Hook registration in settings.json | **MODIFY** | `~/.claude/settings.json` |
| Shared hook utilities | **EXISTING** | `~/.claude/hooks/flywheel/lib/hook_utils.py` |

### Data Flow

```
Claude Code executes Bash tool (e.g., curl PATCH /broker/coverages/123)
  -> PostToolUse fires
  -> post-coverage-write.py reads event from stdin
  -> Regex matches coverage URL pattern
  -> Extracts project_id
  -> Calls POST /broker/projects/{id}/analyze-gaps (fire-and-forget, 5s timeout)
  -> Exit 0
  -> Backend runs gap_detector.py synchronously
  -> Coverage records updated with gap_status, gap_amount
  -> Next time skill reads project data, gaps are current
```

---

## Integration Area 3: Playwright Portal Automation

### Current State
- No Playwright in the codebase currently
- Portal submission UI exists (`PortalSubmission.tsx`) but is a display component
- Backend has `POST /quotes/{id}/portal-screenshot` endpoint for screenshot upload
- Backend has `POST /quotes/{id}/portal-confirm` for confirmation

### Integration Pattern

**Architecture: Playwright runs locally, never on server.**

```
User triggers /broker:fill-portal in Claude Code
  -> Skill loads project data from backend API
  -> Skill loads field map YAML from local disk
  -> Skill shows data preview, waits for user approval
  -> Playwright launches Chromium (user's machine)
  -> User logs into carrier portal manually
  -> User confirms login complete
  -> Playwright script fills forms (carrier-specific selectors)
  -> Playwright takes screenshot
  -> Screenshot uploaded via POST /quotes/{id}/portal-screenshot
  -> User confirms or retries in Claude Code
```

**Browser session management:**
- Playwright launches a **persistent browser context** (not headless) so the user can see what is happening
- User handles login manually (no credential storage anywhere)
- Playwright scripts use `page.wait_for_selector()` with reasonable timeouts (30s)
- On any unexpected state: screenshot current page, stop execution, surface error

**Credential handling:** None. By design, Claude Code never sees portal credentials. The user types them into the visible browser window. This is a security requirement.

**Screenshot storage:**
```
Playwright takes screenshot -> saves to /tmp/broker-portal-{carrier}-{timestamp}.png
  -> Skill reads file bytes
  -> POST /broker/quotes/{id}/portal-screenshot (multipart upload)
  -> Backend stores in Supabase Storage "uploads" bucket
  -> Frontend retrieves via signed URL for display
```

**Dependency chain:** Playwright requires both the Python package and browser binaries. The `pre-portal-validate.py` PreToolUse hook validates this before any portal command executes.

### Components

| Component | Status | File |
|-----------|--------|------|
| Playwright base helpers | **NEW** | `~/.claude/skills/broker/fill-portal/scripts/base.py` |
| Mapfre carrier script | **NEW** | `~/.claude/skills/broker/fill-portal/scripts/mapfre.py` |
| Mapfre field map | **NEW** | `~/.claude/skills/broker/fill-portal/field-maps/mapfre.yaml` |
| fill-portal SKILL.md | **NEW** | `~/.claude/skills/broker/fill-portal/SKILL.md` |
| Portal screenshot endpoint | **EXISTING** | `backend/src/flywheel/api/broker/quotes.py` |
| Portal confirm endpoint | **EXISTING** | `backend/src/flywheel/api/broker/quotes.py` |
| PortalSubmission.tsx | **MODIFY** | `frontend/src/features/broker/components/PortalSubmission.tsx` |
| PreToolUse validation hook | **NEW** | `~/.claude/skills/broker/hooks/pre-portal-validate.py` |

---

## Integration Area 4: Frontend "Run in Claude Code" Buttons

### Current State
- No clipboard integration exists in the frontend
- Toast notifications use `sonner` (already installed, used in `ComparisonView.tsx`)
- No `RunInClaudeCodeButton` component exists

### Integration Pattern

**Simple clipboard + toast. No backend communication.**

```typescript
// RunInClaudeCodeButton.tsx
interface RunInClaudeCodeButtonProps {
  command: string;        // e.g., '/broker:process-project "Autopista GDL-Tepic"'
  label?: string;
  variant?: 'default' | 'prominent';
  description?: string;
}

function RunInClaudeCodeButton({ command, label, variant, description }: Props) {
  const [copied, setCopied] = useState(false);

  const handleClick = async () => {
    await navigator.clipboard.writeText(command);
    toast.success('Copied! Paste into Claude Code');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Render based on variant...
}
```

**Command templating:** Each usage site constructs the command string from current data:
```typescript
// In OverviewTab.tsx
<RunInClaudeCodeButton
  command={`/broker:process-project "${project.name}"`}
  variant="prominent"
  description="Upload documents first, then run this command"
/>

// In PortalSubmission.tsx (per carrier)
<RunInClaudeCodeButton
  command={`/broker:fill-portal ${project.id} ${carrier.id}`}
/>
```

**Browser compatibility:** `navigator.clipboard.writeText()` requires HTTPS or localhost. The dev server runs on `localhost:5173` (works). Production runs on HTTPS (works). No polyfill needed.

**No feedback loop back from Claude Code:** The frontend cannot know if the user actually ran the command. This is by design -- the frontend polls for data changes via React Query `refetchInterval` to detect when Claude Code has written results.

### Components

| Component | Status | File |
|-----------|--------|------|
| `RunInClaudeCodeButton` | **NEW** | `frontend/src/features/broker/components/shared/RunInClaudeCodeButton.tsx` |
| Toast library | **EXISTING** | `sonner` (already installed) |
| Usage in OverviewTab | **MODIFY** | `frontend/src/features/broker/components/tabs/OverviewTab.tsx` |
| Usage in PortalSubmission | **MODIFY** | `frontend/src/features/broker/components/PortalSubmission.tsx` |
| Usage in CompareTab | **MODIFY** | `frontend/src/features/broker/components/tabs/CompareTab.tsx` |
| Usage in QuotesTab | **MODIFY** | `frontend/src/features/broker/components/tabs/QuotesTab.tsx` |

### Data Flow

```
User clicks "Run in Claude Code" button
  -> navigator.clipboard.writeText(command)
  -> Toast: "Copied! Paste into Claude Code"
  -> Button text: "Copied" for 2s
  -> User switches to terminal, pastes command
  -> Claude Code skill executes, writes to backend
  -> Frontend React Query polling detects data change
  -> UI updates automatically
```

---

## Integration Area 5: New "Analysis" Tab in Project Detail

### Current State
- `BrokerProjectDetail.tsx` has 5 tabs: Overview, Coverage, Carriers, Quotes, Compare
- Tab routing uses `useSearchParams` with `?tab=` query parameter
- `TAB_CONFIG` array drives both tab list and content rendering
- `StepIndicator` has 5 steps hardcoded (skeleton renders 5)
- `ProjectCoverage` type is missing fields needed for analysis view (`contract_clause`, `source_excerpt`, `source_page`, `ai_critical_finding`)

### Integration Pattern

**Add "Analysis" as tab index 1 (between Overview and Coverage):**

```typescript
// BrokerProjectDetail.tsx - MODIFY TAB_CONFIG
const TAB_CONFIG = [
  { key: 'overview', label: 'Overview' },
  { key: 'analysis', label: 'Analysis' },    // NEW
  { key: 'coverage', label: 'Coverage' },
  { key: 'carriers', label: 'Carriers' },
  { key: 'quotes', label: 'Quotes' },
  { key: 'compare', label: 'Compare' },
] as const
```

**Data flow:** The Analysis tab reads the SAME data as Coverage tab -- `ProjectCoverage` records from `GET /broker/projects/{id}` (which returns `project.coverages[]`). No new endpoint needed.

**Key difference:** The Analysis tab presents coverages grouped by `category` and displayed alongside `source_excerpt` text, while the Coverage tab presents them in an editable ag-grid.

**Type updates required first:**
```typescript
// ADD to ProjectCoverage type (fields exist in backend, missing from frontend type)
contract_clause: string | null;
source_excerpt: string | null;
source_page: number | null;
source_section: string | null;
gap_amount: number | null;
gap_notes: string | null;
current_limit: number | null;
current_carrier: string | null;
current_policy_number: string | null;
current_expiry: string | null;
```

**Polling for live analysis:** When `analysis_status === 'running'`, the `useBrokerProject` hook already supports `refetchInterval`. Add conditional polling:
```typescript
useQuery({
  queryKey: ['broker-project', projectId],
  queryFn: () => fetchBrokerProject(projectId),
  refetchInterval: project?.analysis_status === 'running' ? 10_000 : false,
});
```

### Components

| Component | Status | File |
|-----------|--------|------|
| `AnalysisTab` | **NEW** | `frontend/src/features/broker/components/tabs/AnalysisTab.tsx` |
| `DocumentViewer` | **NEW** | `frontend/src/features/broker/components/analysis/DocumentViewer.tsx` |
| `RequirementCard` | **NEW** | `frontend/src/features/broker/components/analysis/RequirementCard.tsx` |
| `BrokerProjectDetail` tab config | **MODIFY** | `frontend/src/features/broker/components/BrokerProjectDetail.tsx` |
| `StepIndicator` (5 -> 6 steps) | **MODIFY** | `frontend/src/features/broker/components/StepIndicator.tsx` |
| `ProjectCoverage` type | **MODIFY** | `frontend/src/features/broker/types/broker.ts` |
| `useBrokerProject` hook (polling) | **MODIFY** | `frontend/src/features/broker/hooks/useBrokerProject.ts` |

### Data Flow

```
GET /broker/projects/{id}
  -> Returns project with coverages[] (includes new fields: contract_clause, source_excerpt, etc.)
  -> AnalysisTab groups coverages by category ("insurance" vs "surety")
  -> Left pane: DocumentViewer assembles source_excerpt text with clause highlighting
  -> Right pane: RequirementCard per coverage, with clause link that scrolls left pane
  -> When analysis_status === 'running': shimmer loading state, poll every 10s
  -> When analysis_status transitions to 'completed': stop polling, render cards with stagger animation
```

---

## Integration Area 6: AG-Grid Expandable Groups in Comparison Matrix

### Current State
- `ComparisonGrid.tsx` uses a custom HTML `<table>` (NOT ag-grid)
- `ComparisonView.tsx` orchestrates filtering, carrier toggling, export
- `TotalPremiumRow.tsx` renders the total row in `<tfoot>`
- `ComparisonTabs.tsx` splits by Insurance vs Surety categories
- The custom table works but lacks: sticky headers, expandable groups, consistent theming with rest of broker module

### Integration Pattern

**Replace custom `<table>` with ag-grid.** This is the spec's explicit decision and the reasoning is sound (consistency, sticky headers, column visibility, row grouping, pinned bottom rows).

**Key ag-grid features used:**

1. **Row grouping** for expandable coverage groups:
```typescript
const columnDefs: ColDef[] = [
  {
    field: 'coverageGroup',  // e.g., "General Liability Coverage"
    rowGroup: true,
    hide: true,  // hidden column used only for grouping
  },
  {
    field: 'coverage_type',
    headerName: 'Coverage',
    pinned: 'left',
    width: 200,
  },
  // Dynamic carrier columns generated from data
  ...carriers.map(carrier => ({
    headerName: carrier.name,
    field: `carrier_${carrier.id}`,
    cellRenderer: ComparisonCellRenderer,
    width: 180,
  })),
];
```

2. **Custom group renderer** for expandable headers:
```typescript
const groupRowRendererParams = {
  innerRenderer: (params) => {
    const count = params.node.allChildrenCount;
    return `${params.value} (${count} rows)`;
  },
  suppressCount: true,
};
```

3. **Pinned bottom row** for total premium:
```typescript
<AgGridReact
  pinnedBottomRowData={[{
    coverage_type: 'Total Premium',
    ...Object.fromEntries(carriers.map(c => [
      `carrier_${c.id}`,
      { premium: totals[c.name], is_total: true }
    ]))
  }]}
/>
```

4. **Row height 64px** for two-line cells (premium + limit/deductible):
```typescript
const ComparisonCellRenderer = (params: ICellRendererParams) => {
  const cell = params.value as ComparisonQuoteCell | null;
  if (!cell) return <span className="text-muted-foreground">--</span>;
  return (
    <div className="flex flex-col justify-center h-full">
      <span className="font-semibold text-sm">{formatCurrency(cell.premium)}</span>
      <span className="text-xs text-muted-foreground">
        Limit: {formatCurrency(cell.limit_amount)} | Ded: {formatCurrency(cell.deductible)}
      </span>
    </div>
  );
};
```

5. **Default expansion state:**
```typescript
groupDefaultExpanded: 1  // First level expanded by default
```

**Data transformation:** The existing `ComparisonMatrix` API response has `coverages[]` with nested `quotes[]`. This needs to be flattened for ag-grid row data:
```typescript
const rowData = coverages.map(cov => ({
  coverage_type: cov.coverage_type,
  coverageGroup: getCoverageGroup(cov.coverage_type, cov.category),
  required_limit: cov.required_limit,
  ...Object.fromEntries(cov.quotes.map(q => [`carrier_${q.carrier_config_id}`, q])),
}));
```

**Coverage group mapping:**
```typescript
function getCoverageGroup(type: string, category: string): string {
  if (category === 'surety') return 'Surety Bonds';
  const groupMap: Record<string, string> = {
    'general_liability': 'General Liability Coverage',
    'rc_general': 'General Liability Coverage',
    'rc_operations': 'General Liability Coverage',
    'car': 'Equipment & CAR Coverage',
    'builders_risk': 'Equipment & CAR Coverage',
    'professional_liability': 'Professional & Environmental',
    'environmental': 'Professional & Environmental',
  };
  return groupMap[type] || 'Other Coverage';
}
```

**AG-Grid Enterprise vs Community:** Row grouping (`rowGroup: true`) requires AG-Grid Enterprise license. Check if the project already has Enterprise. If not, implement grouping manually with `fullWidthCellRenderer` for group headers (Community-compatible approach) or use the simpler pattern from `CoverageTab.tsx` which renders separate grids per category section.

### Components

| Component | Status | File |
|-----------|--------|------|
| `ComparisonGrid.tsx` | **REWRITE** | Replace HTML table with ag-grid |
| `ComparisonCellRenderer` | **NEW** | `frontend/src/features/broker/components/comparison/ComparisonCellRenderer.tsx` |
| `TotalPremiumRow.tsx` | **DELETE** | Replaced by ag-grid `pinnedBottomRowData` |
| `ComparisonView.tsx` | **MODIFY** | Update to pass ag-grid props instead of table props |
| `ComparisonTabs.tsx` | **MODIFY or DELETE** | Groups now handled by ag-grid row grouping, may not need separate Insurance/Surety tabs |

### Data Flow

```
GET /broker/projects/{id}/comparison
  -> Returns ComparisonMatrix { coverages[], partial, total_carriers }
  -> ComparisonView transforms: flatten coverages into ag-grid rowData
  -> Assign coverageGroup to each row based on coverage_type + category
  -> Generate dynamic carrier columns from unique carriers in data
  -> Set pinnedBottomRowData with computed totals per carrier
  -> ag-grid renders with row grouping, expandable headers, sticky columns
  -> Carrier show/hide: columnApi.setColumnVisible()
  -> Recommended column: apply custom headerClass + cellClass with coral border
```

---

## Integration Area 7: Skills Reading Uploaded PDFs from Supabase Storage

### Current State
- Files uploaded via `POST /broker/projects/{id}/documents` endpoint
- Stored in Supabase Storage "uploads" bucket via `document_storage.py`
- `upload_file()` stores bytes, returns storage path
- `get_file_url()` generates signed URLs (default 1-hour expiry)
- Backend has file/document endpoints in `backend/src/flywheel/api/files.py`
- `UploadedFile` model tracks metadata including `extracted_text`

### Integration Pattern

**Two access paths, chosen by accuracy requirement:**

**Path A: Native PDF Reading (HIGH accuracy -- for contracts and quotes)**
```
Skill needs to parse contract PDF
  -> GET /broker/projects/{id} (includes document metadata with file IDs)
  -> GET /broker/files/{file_id} (returns signed URL from Supabase Storage)
  -> Skill fetches signed URL -> gets raw PDF bytes
  -> Claude Code reads PDF natively (multimodal PDF understanding)
  -> Extracts coverage requirements with clause references
```

This is the preferred path for `parse-contract` and `extract-quote` because Claude's native PDF reading preserves layout, tables, and formatting that text extraction loses.

**Path B: Extracted Text (FAST -- for predictable formats)**
```
Skill needs policy data
  -> MCP file_read tool -> returns UploadedFile.extracted_text
  -> Skill processes plain text
```

This path works for `parse-policies` where format is more predictable (ACORD 25 has standard field positions).

**Signed URL flow details:**

1. Backend generates signed URL via Supabase Storage API:
```python
# document_storage.py - existing code
async def get_file_url(storage_path: str, expires_in: int = 3600) -> str:
    url = f"{supabase_url}/storage/v1/object/sign/{UPLOADS_BUCKET}/{storage_path}"
    resp = await client.post(url, json={"expiresIn": expires_in}, headers=...)
    return f"{supabase_url}{resp.json()['signedURL']}"
```

2. Skill fetches the signed URL:
```python
# In skill script
resp = await api_call("get", f"/broker/files/{file_id}")
signed_url = resp["url"]  # 1-hour validity
# Download PDF bytes
pdf_bytes = httpx.get(signed_url).content
# Save to temp file for Claude to read
with open(f"/tmp/broker-{file_id}.pdf", "wb") as f:
    f.write(pdf_bytes)
# Claude Code reads the file natively using Read tool
```

3. Claude Code's Read tool can read PDF files directly (multimodal). The skill saves the PDF to a temp path and then Claude reads it.

**Important constraint:** Signed URLs expire after 1 hour (default). For long-running pipeline skills, generate fresh URLs for each document as needed, not all upfront.

**Fallback chain:**
1. Try native PDF read via signed URL (best accuracy)
2. If signed URL fails (expired, storage error): try `file_read` MCP tool for `extracted_text`
3. If `extracted_text` is empty: surface error to user with document ID

### Components

| Component | Status | File |
|-----------|--------|------|
| File URL endpoint | **EXISTING** | `backend/src/flywheel/api/files.py` |
| `document_storage.py` | **EXISTING** | `backend/src/flywheel/services/document_storage.py` |
| `file_read` MCP tool | **EXISTING** | `backend/src/flywheel/tools/file_tools.py` |
| PDF download helper in skills | **NEW** | `~/.claude/skills/broker/scripts/api_client.py` (add `download_pdf()`) |

---

## Component Boundary Summary

### New Components (to build)

| Component | Layer | Depends On |
|-----------|-------|------------|
| `api_client.py` (shared skill helper) | Skills | SessionStart hook (token), Backend API |
| 4 hook scripts | Hooks | `hook_utils.py`, Backend API |
| `fill-portal` scripts + field maps | Skills | Playwright, Backend API |
| `RunInClaudeCodeButton` | Frontend | `sonner` (toast) |
| `AnalysisTab` + sub-components | Frontend | `useBrokerProject` hook, `ProjectCoverage` type |
| `ComparisonCellRenderer` | Frontend | ag-grid, `ComparisonMatrix` type |
| Batch coverage endpoint | Backend | Existing coverage model |
| Dashboard stats premium field | Backend | Existing stats endpoint |

### Modified Components

| Component | What Changes |
|-----------|-------------|
| `BrokerProjectDetail.tsx` | Add "Analysis" tab to TAB_CONFIG, update skeleton |
| `StepIndicator.tsx` | 5 steps -> 6 steps, add Analysis step status mapping |
| `ComparisonGrid.tsx` | Full rewrite: HTML table -> ag-grid |
| `ProjectCoverage` type | Add 10 missing fields |
| `BrokerProject` type | Remove 5 stale fields |
| `CarrierQuote` type | Remove 6 stale fields |
| `settings.json` | Add 4 new hook entries |
| `pre-read-context.py` | Export API URL + token |
| `gridTheme` | Update hover color, remove column separators |
| `api.ts` | Fix 4 endpoint paths |
| Various tabs | Add `RunInClaudeCodeButton` usage |

### Unchanged Components

| Component | Why Unchanged |
|-----------|--------------|
| Backend auth middleware | Skills use same JWT flow as frontend |
| Backend broker sub-routers (existing) | No changes to existing 50 endpoints |
| `gap_detector.py`, `quote_comparator.py` | Called via existing endpoints, not modified |
| `document_storage.py` | Signed URL flow already works |
| React Query setup | Existing polling pattern reused |
| `hook_utils.py` | Existing utilities sufficient for new hooks |

---

## Build Order (Dependency-Driven)

```
Phase 0: Foundation (blocks everything)
  |-- Fix 4 API path mismatches in api.ts
  |-- Fix types (remove stale, add missing)
  |-- Update gridTheme
  |-- Add shared cell renderers (CurrencyCell, ClauseLink, CarrierCell, ToggleCell, DaysCell)
  |-- Add batch coverage endpoint
  |-- Add total_premium to dashboard stats
  |
Phase 1: Skills Infrastructure (blocks skills)
  |-- Shared api_client.py for skills
  |-- Token export in SessionStart hook
  |-- Hook scripts (post-coverage-write, post-quote-write, pipeline-check, pre-portal-validate)
  |-- Hook registration in settings.json
  |-- Skill directory structure + router SKILL.md
  |-- field_validator.py
  |-- Playwright base.py + mapfre scripts
  |
Phase 2: AI Skills + High-Impact Frontend (parallel tracks)
  |-- Skills track: parse-contract, parse-policies, extract-quote, pipeline skills
  |-- Frontend track: Analysis tab, Coverage tab updates, Comparison matrix rewrite
  |
Phase 3: Remaining Frontend
  |-- RunInClaudeCodeButton component
  |-- Overview tab redesign
  |-- Email approval updates
  |-- Quote tracking updates
  |-- Portal submission with Run in Claude Code
  |-- Recommendation delivery
  |
Phase 4: Polish
  |-- CSS animations (fadeUp, shimmer, pulse, stagger)
  |-- Dashboard MetricCards
  |-- Carrier logos
```

**Ordering rationale:**
- Phase 0 must be first because type fixes and cell renderers are imported by every subsequent component
- Phase 1 must precede Phase 2 because skills need the API client, hooks, and Playwright infrastructure
- Phase 2 skills and frontend are parallelizable -- skills write data, frontend displays it, but neither blocks the other
- Phase 3 frontend pages depend on `RunInClaudeCodeButton` which is quick to build -- could be pulled into Phase 2
- Phase 4 is pure visual polish with no functional dependencies

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Skills Storing Local Copies of Backend Logic
**What:** Copying `gap_detector.py` or `quote_comparator.py` into the skills directory
**Why bad:** Two sources of truth. Backend updates will not propagate to skills.
**Instead:** Skills call backend endpoints (`POST /analyze-gaps`, `GET /comparison`). The spec explicitly calls this out.

### Anti-Pattern 2: Hooks That Block on API Failures
**What:** Hook script waits for backend response, backend is slow/down, conversation hangs
**Why bad:** Hooks run synchronously in the tool pipeline. A hanging hook blocks Claude Code.
**Instead:** All hook API calls use 5-second timeout. On failure: log error, exit 0. Never block.

### Anti-Pattern 3: Storing Carrier Portal Credentials
**What:** Saving portal login/password in config, env var, or skill memory
**Why bad:** Security risk. Credentials in plaintext on disk.
**Instead:** User logs in manually in the visible browser window. Playwright only fills form fields after login.

### Anti-Pattern 4: Custom HTML Tables Alongside AG-Grid
**What:** Using `<table>` for comparison while rest of module uses ag-grid
**Why bad:** Visual inconsistency, duplicate scroll/responsive logic, no shared theme
**Instead:** Use ag-grid for all tabular data. Custom cell renderers solve the two-row cell problem.

### Anti-Pattern 5: Frontend Triggering AI Directly
**What:** Adding `POST /projects/{id}/analyze` that runs AI on the backend
**Why bad:** Violates the three-layer split. Backend should only do deterministic work.
**Instead:** Frontend shows "Run in Claude Code" button. AI runs in Claude Code, writes results to backend via API.

---

## Scalability Considerations

| Concern | Current (1-5 users) | At 50 users | At 500 users |
|---------|---------------------|-------------|--------------|
| Signed URL generation | Inline in API handler | Same (Supabase handles load) | Add URL caching layer |
| Hook API calls | Direct httpx calls | Same (1 call per hook per tool use) | Same (hooks are per-session, not shared) |
| Comparison matrix data | Single API call, full matrix | Same (max ~20 carriers x 15 coverages) | Same (matrix is bounded by business domain) |
| PDF processing | Claude Code (local) | Each user runs their own CC | Same (CC scales per-seat) |
| React Query polling | 10s interval per running analysis | Same (polling is per-tab, not global) | Consider WebSocket for push updates |

---

## Sources

- SPEC-BROKER-REDESIGN.md -- primary spec (all 7 integration areas defined), HIGH confidence
- `frontend/src/features/broker/` -- existing component tree, types, API functions, hooks, HIGH confidence
- `backend/src/flywheel/api/broker/` -- existing endpoint definitions (projects.py, quotes.py), HIGH confidence
- `backend/src/flywheel/services/document_storage.py` -- Supabase Storage signed URL flow, HIGH confidence
- `~/.claude/settings.json` -- existing hook configuration (12 hooks), HIGH confidence
- `~/.claude/hooks/flywheel/lib/hook_utils.py` -- shared hook utilities (read_event, log_hook), HIGH confidence
- `~/.claude/hooks/flywheel/pre-read-context.py` -- SessionStart hook pattern, HIGH confidence
- `frontend/src/lib/api.ts` -- existing auth and request pattern (Bearer token from useAuthStore), HIGH confidence
- `frontend/src/shared/grid/theme.ts` -- existing ag-grid theme (themeQuartz with coral accent), HIGH confidence
- `frontend/src/features/broker/components/comparison/ComparisonGrid.tsx` -- current HTML table implementation, HIGH confidence
- `frontend/src/features/broker/components/BrokerProjectDetail.tsx` -- current tab config (5 tabs, searchParams routing), HIGH confidence
