# Domain Pitfalls

**Domain:** Broker Frontend MVP -- ag-grid extraction, comparison matrix, Excel export, tab routing, migration from HTML tables
**Researched:** 2026-04-14
**Confidence:** HIGH for codebase-specific pitfalls (direct code analysis). MEDIUM for CSS sticky positioning (verified across multiple sources). MEDIUM for openpyxl/FastAPI export (web research + official docs).

---

## Critical Pitfalls

Mistakes that cause rewrites, regressions, or production outages.

### Pitfall 1: Extracting Shared ag-grid Infrastructure Breaks Pipeline

**What goes wrong:** Moving the grid theme, cell renderers, and column state hook from `features/pipeline/` to shared locations (`lib/`, `components/grid/`, `hooks/`) while PipelinePage.tsx has 757 lines of deeply coupled state management. Any import path change or renamed export silently breaks the pipeline grid, which is the most-used feature in the app.

**Why it happens:** The technical spec (SPEC-BROKER-FRONTEND-TECHNICAL.md) calls for extracting 5 cell renderers and the theme from pipeline. But PipelinePage.tsx references `pipelineTheme` inline (line 34-47), `usePipelineColumns` imports 11 cell renderers from relative paths (lines 3-13), and the column state persistence key is hardcoded as `'pipeline-col-state'` (line 15). A refactor that changes any of these paths without updating every reference will break the working pipeline.

**Consequences:** Pipeline grid shows blank/white screen, no error message (ag-grid fails silently when cell renderers are undefined). Users lose access to their primary CRM view. Since pipeline is behind a feature flag that is already enabled for all tenants, this breaks production immediately.

**Prevention:**
1. Extract shared infrastructure in a DEDICATED phase BEFORE building any broker grid components
2. After extraction, verify pipeline still renders by running the app and checking `/pipeline` manually
3. Use TypeScript strict mode -- if a cell renderer import path is wrong, TS will catch it at build time
4. Keep pipeline-specific renderers (`ChannelsCell`, `ContactCell`, `NextStepCell`, `OutreachStatusCell`, `AiInsightCell`, `NameCell`, `ExpandToggleCell`, `FitTierBadge`, `StagePill`, `ContactStatusPill`, `DatePickerEditor`, `DateCell`, `ChannelIconsCell`) in `features/pipeline/` -- only extract the 5 generic ones listed in the spec
5. The `usePipelineColumns` hook (168 lines) should NOT be refactored -- only extract the column state persistence pattern into `useGridColumnState(storageKey)` and have `usePipelineColumns` import and use it

**Detection:** Pipeline grid shows white/empty content area. No TypeScript errors if `any` types leak through. Always smoke-test `/pipeline` after any shared infrastructure change.

**Files at risk:**
- `frontend/src/features/pipeline/components/PipelinePage.tsx` (757 lines, the most complex component)
- `frontend/src/features/pipeline/hooks/usePipelineColumns.ts` (167 lines)
- `frontend/src/features/pipeline/hooks/useContactColumns.ts`
- `frontend/src/features/pipeline/components/cell-renderers/` (13 renderer files)

### Pitfall 2: CoverageTable Inline Edit State Lost During ag-grid Migration

**What goes wrong:** The existing `CoverageTable.tsx` (193 lines) has working inline editing using React state (`useState` for `editingId` and `editValues`). Migrating to ag-grid means replacing this with ag-grid's built-in cell editing (`editable: true`, `cellEditor`). During migration, the existing edit-save-cancel flow, the `is_manual_override` flag setting, and the `useCoverageMutation` integration can be lost or subtly broken.

**Why it happens:** ag-grid's inline editing model is fundamentally different from React controlled inputs:
- React approach (current): component owns state, explicit save/cancel buttons, mutation fires on save
- ag-grid approach: grid owns edit state, `onCellValueChanged` fires after edit completes, no explicit save button
The current CoverageTable sets `is_manual_override: true` on save (line 36) -- this business logic MUST survive the migration.

**Consequences:** Edited coverages lose the `is_manual_override` flag, meaning the system treats manual corrections as AI-extracted data. This breaks the confidence display and could cause AI to overwrite broker corrections on re-analysis.

**Prevention:**
1. Before migrating CoverageTable, document every piece of business logic in the current component:
   - `is_manual_override: true` set on every save (line 36)
   - Three fields are editable: `coverage_type`, `description`, `required_limit` (lines 86-110)
   - Number input for `required_limit` with null handling (lines 100-110)
   - `category`, `confidence`, and `source` are read-only even in edit mode (lines 112-114)
2. In the ag-grid version, use `onCellValueChanged` callback and ensure it includes `is_manual_override: true` in the mutation payload
3. Write a manual test checklist: edit a coverage -> verify API call includes `is_manual_override: true`

**Detection:** Check network tab after editing a coverage cell -- the PATCH request must include `is_manual_override: true`.

**Files at risk:**
- `frontend/src/features/broker/components/CoverageTable.tsx` (193 lines, working inline edit)
- `frontend/src/features/broker/hooks/useCoverageMutation.ts`

### Pitfall 3: ComparisonMatrix CSS Sticky Fails with overflow:auto Ancestor

**What goes wrong:** The comparison matrix spec requires frozen first column (coverage names) + sticky header row + horizontal scroll for 5+ carriers. CSS `position: sticky` fails silently when ANY ancestor element between the sticky element and the scroll container has `overflow: hidden`, `overflow: auto`, or `overflow: scroll`. The current ComparisonMatrix.tsx wraps the table in `<div className="overflow-x-auto rounded-lg border">` (line 161) -- this creates the scroll context, but if a PARENT of this div also has overflow set (common in layout components), sticky will not work.

**Why it happens:** `position: sticky` sticks relative to its nearest scrolling ancestor. If a parent layout div (e.g., the `lg:col-span-2` grid cell in BrokerProjectDetail.tsx line 62, or the `p-6 space-y-6` wrapper) has any overflow property, the sticky element becomes constrained to that container instead of the intended scroll container. The current `ComparisonMatrix` does NOT use sticky at all (it is a plain HTML table) -- the spec ADDS this requirement.

**Consequences:** First column scrolls away with horizontal scroll, making the matrix unreadable when comparing 5+ carriers. Users cannot see which coverage row they are looking at. This is the #1 screen in the product per the spec.

**Prevention:**
1. Do NOT use `<table>` with `position: sticky` on `<td>`/`<th>` elements. Chrome has known bugs with sticky on table elements (works in Firefox/Safari but not reliably in Chrome).
2. Use CSS Grid or Flexbox layout instead of `<table>` for the comparison matrix. This avoids all table-specific sticky bugs.
3. Alternatively, use ag-grid's built-in `pinned: 'left'` for the coverage column (proven working in PipelinePage.tsx line 19-30). ag-grid handles the frozen column internally without CSS sticky.
4. Audit ALL ancestor elements for `overflow` properties. The chain from the sticky element to the viewport must have NO intermediate `overflow: hidden/auto/scroll`.
5. Z-index layering: sticky header cells need z-index higher than sticky first-column cells, and the top-left corner cell needs the highest z-index of all.

**Detection:** Scroll horizontally in the comparison matrix with 5+ carriers. If the first column moves with the scroll, sticky is broken. Test in Chrome specifically.

**Files at risk:**
- `frontend/src/features/broker/components/ComparisonMatrix.tsx` (187 lines, currently no sticky)
- `frontend/src/features/broker/components/BrokerProjectDetail.tsx` (parent layout with grid)

### Pitfall 4: Excel Export Blocks FastAPI Event Loop

**What goes wrong:** openpyxl generates the entire Excel workbook in memory before returning it. For a comparison matrix with many carriers and coverages (the spec shows 2 sheets: Insurance + Surety Bonds), the workbook is constructed synchronously. If the export endpoint is a regular async FastAPI route, it blocks the event loop during workbook generation, freezing ALL other requests.

**Why it happens:** openpyxl's `Workbook.save()` is a CPU-bound synchronous operation. FastAPI's `StreamingResponse` only helps with the HTTP transfer -- the workbook must be fully built in memory before streaming starts. For a typical comparison matrix (20 coverage rows x 5 carriers x 2 sheets with formatting), this takes 50-200ms. Not huge, but it blocks every concurrent request during that time.

**Consequences:** Other users experience 50-200ms latency spikes when any broker exports. On a slow server or with large matrices, this can cause timeouts for concurrent requests.

**Prevention:**
1. Use `run_in_executor` to offload openpyxl workbook generation to a thread pool:
   ```python
   import asyncio
   from io import BytesIO
   
   async def generate_excel(data):
       loop = asyncio.get_event_loop()
       buffer = await loop.run_in_executor(None, _build_workbook_sync, data)
       return buffer
   ```
2. Use `BytesIO` buffer, never write to disk on the server
3. Set proper Content-Disposition header for the filename: `Content-Disposition: attachment; filename="comparison_{project_name}_{date}.xlsx"`
4. Set Content-Type to `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
5. The backend already has openpyxl installed (confirmed in `.venv`)

**Detection:** During load testing, export requests cause latency spikes for other endpoints. Monitor event loop blocking with `asyncio` debug mode.

**Files at risk:**
- `backend/src/flywheel/api/broker.py` (new endpoint to be added)
- No existing Excel export endpoint exists -- this is net-new code

---

## Moderate Pitfalls

### Pitfall 5: Gate Strip Polling Creates N+1 Query Storm

**What goes wrong:** The persistent gate strip shows counts for 3 gates (Review, Approve, Export) on every broker page. If implemented as a React Query hook with `refetchInterval`, it fires a separate API call every N seconds from EVERY mounted broker page component. If the gate strip component is mounted in the layout (which it should be, since it persists across pages), a single polling query is fine. But if each page ALSO fetches gate counts for its own rendering, you get duplicate queries.

**Why it happens:** React Query deduplicates queries by query key, but only within the same `staleTime` window. The existing `useBrokerQuotes` hook (line 19-26) already uses conditional `refetchInterval` -- returning `10_000` when quotes are extracting. Adding another polling hook for gate counts creates overlapping network traffic. Additionally, the gate strip counts require aggregation across ALL projects (not just one), so the backend query is heavier.

**Consequences:** API gets hammered with repeated count queries every 10-30 seconds per tab. Database load increases linearly with connected broker users. On mobile with spotty connections, these polling requests queue up and fire simultaneously when connectivity returns.

**Prevention:**
1. Single gate counts endpoint: `GET /broker/gate-counts` returning `{review: 3, approve: 1, export: 2}`
2. One React Query hook with `refetchInterval: 30_000` (30 seconds is sufficient for gate counts)
3. Use `staleTime: 25_000` to prevent refetch on component remount during page navigation
4. Invalidate gate counts on any mutation that changes project status (e.g., approve project, send solicitation)
5. Do NOT poll from individual page components -- only the layout-level gate strip polls

**Detection:** Open browser DevTools Network tab. Navigate between broker pages. Count how many `/gate-counts` requests fire per minute. Should be exactly 2 (one per 30s), not 2x per page.

### Pitfall 6: Tab Routing in Project Detail Loses State on Back Button

**What goes wrong:** The spec requires 5 tabs in project detail (Overview, Coverage, Carriers, Quotes, Compare). If tab state is stored in URL query params (e.g., `/broker/projects/:id?tab=compare`), the browser back button creates confusing navigation: clicking tabs forward (Overview -> Coverage -> Compare) then hitting back goes Compare -> Coverage -> Overview, which feels like navigating "between pages" rather than "between tabs."

**Why it happens:** Each `setSearchParams` call with `replace: false` pushes a new history entry. The existing PipelinePage.tsx solves this correctly by using `{ replace: true }` (line 191) for filter changes. But a developer unfamiliar with this pattern will use the default (push) behavior.

**Consequences:** Users get trapped in history loops. Pressing back 5 times to return to the projects list instead of once. This is a UX bug that users notice immediately.

**Prevention:**
1. Use `replace: true` for ALL tab changes: `setSearchParams({tab: 'compare'}, { replace: true })`
2. Alternative: store active tab in component state (not URL), and only use URL for deep-linking on initial load. Read tab from URL on mount, then ignore URL changes. This is simpler and avoids history pollution entirely.
3. The existing broker routes (`/broker/projects/:id`) do NOT currently use query params -- the project detail renders all sections vertically (BrokerProjectDetail.tsx lines 60-101). The spec CHANGES this to tabs, which means adding URL-based tab state.
4. Test: navigate to project detail -> click 3 different tabs -> hit browser back -> should return to projects list in ONE click

**Detection:** Browser history grows with each tab click. Back button cycles through tabs instead of going to previous page.

### Pitfall 7: ag-grid Version Mismatch Between Pipeline and Broker

**What goes wrong:** The pipeline already uses ag-grid with `AllCommunityModule` and `themeQuartz` (PipelinePage.tsx lines 4-6). If the broker module imports ag-grid differently (e.g., importing individual modules for tree-shaking, or using a different ag-grid package version), you get runtime errors about duplicate grid instances or missing modules.

**Why it happens:** ag-grid v33+ changed the module system significantly. The pipeline uses the old-style `AllCommunityModule` import. If a developer follows current ag-grid docs (which default to the new module system), they will write incompatible imports.

**Consequences:** Runtime error: "AG Grid: no modules registered" or "AG Grid: multiple grid instances detected". Grid renders as empty div with no visible error in the UI.

**Prevention:**
1. Broker MUST use the same ag-grid import pattern as pipeline: `import { AllCommunityModule, themeQuartz } from 'ag-grid-community'` and `import { AgGridReact } from 'ag-grid-react'`
2. The shared grid theme extraction (SPEC section 1.1) should be the canonical import source -- both pipeline and broker import theme from `lib/grid-theme.ts`
3. Check `package.json` for ag-grid version before writing any broker grid code. Pin the version if not already pinned.
4. NEVER import from `@ag-grid-community/core` or `@ag-grid-community/react` -- these are the new modular packages that conflict with the existing `ag-grid-community` package

**Detection:** Console errors containing "AG Grid" on any page with a grid. White/empty grid area.

### Pitfall 8: Two-Row Cell Layout in ag-grid Comparison Matrix

**What goes wrong:** The spec requires two-row cells (premium bold top, limit + deductible muted bottom). ag-grid cells are single-value by default. Custom cell renderers that return multi-line JSX can have height calculation issues: ag-grid measures cell height on first render, and if the content is dynamic (some cells have 2 lines, some have 1), rows end up with inconsistent heights or clipped content.

**Why it happens:** ag-grid's default `rowHeight` is fixed (set to 44 in the pipeline theme, line 42). Two-row cells need more height. If you set a fixed `rowHeight` that accommodates two-row cells, single-row cells (empty/no-quote cells) have excessive whitespace. If you use `autoHeight`, ag-grid recalculates row heights on every render, causing layout thrashing with many cells.

**Consequences:** Clipped cell content (premium shows but limit/deductible is hidden), or excessive whitespace in empty cells, or slow rendering with `autoHeight` on 20+ coverage rows.

**Prevention:**
1. Use a fixed `rowHeight` of ~64px for the comparison matrix grid (NOT the global theme's 44px)
2. Override `rowHeight` at the grid instance level, not the theme level, so pipeline keeps 44px
3. Cell renderer should always render both lines, using an em-dash for missing values (the existing `ComparisonMatrix.tsx` already does this correctly with `formatCurrency` returning "\u2014" for null)
4. Do NOT use `autoHeight` for the comparison matrix -- fixed height is more predictable

**Detection:** Visual inspection: cells look clipped at bottom, or vary in height row-to-row.

---

## Minor Pitfalls

### Pitfall 9: localStorage Collision Between Pipeline and Broker Column State

**What goes wrong:** The pipeline uses `localStorage.setItem('pipeline-col-state', ...)` (usePipelineColumns.ts line 15). If the broker column state hook uses a similar key without namespacing, column state from one module could overwrite the other.

**Prevention:** The shared `useGridColumnState(storageKey)` pattern in the spec handles this correctly -- just ensure unique keys: `'broker-projects-col-state'`, `'broker-coverage-col-state'`, `'broker-comparison-col-state'`. Never use a generic key like `'col-state'`.

### Pitfall 10: Currency Formatting Inconsistency (MXN vs USD)

**What goes wrong:** The existing ComparisonMatrix defaults to `currency = 'MXN'` (line 111). The CoverageTable uses `'USD'` (line 139). The spec targets Mexico-based brokers. If some components format as USD and others as MXN, the numbers look wrong (MXN uses `$` prefix in Mexico, same as USD, but amounts are 20x larger).

**Prevention:** Currency must come from `project.currency` consistently. The existing code already passes `currency={project.currency || 'MXN'}` to ComparisonMatrix (BrokerProjectDetail.tsx line 95). Ensure ALL new monetary formatters use the project currency, never hardcode.

### Pitfall 11: BrokerGuard Null Flash on Page Refresh

**What goes wrong:** The `BrokerGuard` component (routes.tsx lines 144-151) returns `null` when `activeTenant` is null (loading state). On page refresh, there is a brief flash of nothing before the tenant loads. This is intentional (prevents redirect before hydration), but if the broker layout has a persistent gate strip, the gate strip also disappears during this flash.

**Prevention:** The gate strip should be inside `BrokerGuard`, not outside it. This means it disappears during the tenant loading flash, which is acceptable (sub-second). Do NOT try to render the gate strip before tenant loads -- it would fire API calls without tenant context.

### Pitfall 12: Existing Broker Components Import Chain

**What goes wrong:** The existing 17 broker components have direct imports between them (e.g., BrokerProjectDetail imports CoverageTable, ComparisonMatrix, GapAnalysis, etc.). When rewriting these components, changing the export signature of any component (e.g., renaming a prop) silently breaks all importers if TypeScript is not strict.

**Prevention:** Before starting any component rewrite, grep for all importers of that component:
```bash
grep -r "from.*CoverageTable\|import.*CoverageTable" frontend/src --include="*.tsx"
```
Update all importers in the same commit as the component change.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Shared grid infrastructure extraction | Pitfall 1: Breaking pipeline | Extract-then-verify in isolation before broker uses it. Smoke test `/pipeline` after every file move. |
| Comparison matrix with sticky columns | Pitfall 3: CSS sticky fails in Chrome | Use ag-grid `pinned: 'left'` OR CSS Grid layout instead of `<table>` + sticky. Test in Chrome specifically. |
| CoverageTable migration to ag-grid | Pitfall 2: Business logic lost | Document all edit logic before rewriting. Verify `is_manual_override` survives migration. |
| Excel export endpoint | Pitfall 4: Event loop blocking | Use `run_in_executor` for openpyxl. Return `StreamingResponse` with `BytesIO`. |
| Gate strip implementation | Pitfall 5: Polling storm | Single endpoint, single hook, layout-level only, 30s interval. |
| Tab routing in project detail | Pitfall 6: Back button pollution | Use `replace: true` or component-state tabs with URL read-on-mount only. |
| Any new ag-grid usage | Pitfall 7: Version mismatch | Match pipeline's import pattern exactly. Never mix module systems. |
| Two-row comparison cells | Pitfall 8: Height issues | Fixed 64px row height for comparison grid. No `autoHeight`. |

---

## Sources

- Direct codebase analysis of all files referenced above (HIGH confidence)
- [CSS-Tricks: Sticky header + sticky column table](https://css-tricks.com/a-table-with-both-a-sticky-header-and-a-sticky-first-column/) (MEDIUM)
- [Polypane: All the ways position:sticky can fail](https://polypane.app/blog/getting-stuck-all-the-ways-position-sticky-can-fail/) (MEDIUM)
- [FastAPI Excel export patterns](https://github.com/fastapi/fastapi/issues/1277) (MEDIUM)
- [TanStack Query polling patterns](https://javascript.plainenglish.io/tanstack-query-mastering-polling-ee11dc3625cb) (MEDIUM)
- [AG Grid migration docs](https://www.ag-grid.com/react-data-grid/migration/) (HIGH)
- [AG Grid module architecture](https://www.ag-grid.com/javascript-data-grid/modules/) (HIGH)
