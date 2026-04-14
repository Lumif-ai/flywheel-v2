# Project Research Summary

**Project:** Broker Frontend MVP
**Domain:** Insurance broker workflow management (comparison tools, project management, Excel deliverables)
**Researched:** 2026-04-14
**Confidence:** HIGH

## Executive Summary

This is a frontend build-out on top of a complete backend (28 endpoints, 6 tables, 7 AI engines, 17 existing components). The project adds the missing UI surface that transforms a working API into a usable product. The core challenge is NOT technical novelty — the stack is already decided, the patterns are already proven in the codebase, and zero new dependencies are required. The challenge is disciplined execution: build in the right order to avoid regressions, preserve existing business logic during component rewrites, and avoid the CSS/ag-grid traps that look simple but cause production bugs.

The recommended approach is phased, dependency-first construction: extract shared infrastructure before building on it, build layout-level components before page-level ones, and build the comparison matrix (the crown jewel feature) only after the tab structure it lives in is stable. The 3-gate workflow (review extractions → approve solicitations → export comparison) maps to a natural build sequence that produces usable value at each phase.

The primary risk is regressions on the existing GTM pipeline module during ag-grid infrastructure extraction. The secondary risk is the CSS sticky comparison matrix failing silently in Chrome when ancestor elements have overflow set. Both risks have clear mitigations: copy-first extraction with smoke testing, and using ag-grid pinned columns or CSS Grid instead of table-element sticky. The Excel export has one non-obvious pitfall: openpyxl workbook generation is synchronous and must be offloaded to a thread pool with `run_in_executor` to avoid blocking FastAPI's event loop.

## Key Findings

### Recommended Stack

No new dependencies are needed. Every feature in the spec maps to technologies already installed and used in production. React 19, Vite 6, TypeScript 5.5, Tailwind CSS 4, react-router 7, TanStack Query 5, Zustand 5, ag-grid Community 35, shadcn/ui (27 components installed), and openpyxl (system-wide Python) cover everything. The ag-grid Enterprise license (required for built-in Excel export) is correctly excluded — backend-generated xlsx via openpyxl is the right approach and matches the existing StreamingResponse download pattern already used twice in the codebase.

**Core technologies:**
- React 19 + TypeScript 5.5: UI framework — already in use everywhere, no changes
- ag-grid Community 35: interactive data grids — proven in pipeline module; broker extracts shared theme + renderers
- shadcn/ui: component primitives — 27 components installed including Tabs, Badge, Dialog, Skeleton
- TanStack Query 5: server state and polling — all existing broker hooks already use it
- Native HTML table + Tailwind CSS sticky: comparison matrix — simpler and more correct than ag-grid for read-only multi-sticky layout
- openpyxl + FastAPI StreamingResponse: Excel export — pattern already proven in documents.py and tenant.py
- react-router useSearchParams: tab state in URL — already used in PipelinePage for filter state

### Expected Features

**Must have (table stakes):**
- Side-by-side comparison matrix with frozen first column — brokers use Excel for this today; without it the tool has no value proposition
- Coverage gap and exclusion visibility with critical exclusion alert box above matrix — brokers carry E&O liability; missed exclusions are career-ending
- Excel export as .xlsx with two sheets (Insurance + Surety) — this is the actual deliverable that goes to the client
- Task list ordered by urgency on dashboard — broker opens app 2x/day needing "what requires my attention and in what order"
- Insurance vs Surety tab separation — Mexico construction requires both; mixing them is a domain error
- Solicitation email review and approval — Gate 2 components exist; polish is needed

**Should have (differentiators):**
- "Show Differences Only" toggle (default ON) — cuts matrix noise by 40-60%; Tufte-inspired data reduction
- Two-row cell layout (premium bold top, limit+deductible muted below) — premium UI matching broker mental model
- Persistent gate strip on every broker page ("Review: 3 | Approve: 1 | Export: 2") — eliminates dashboard round-trips
- Horizontal step indicator on project detail (Extract > Review > Solicit > Compare > Deliver)
- Carrier selection checkboxes in matrix headers — controls which carriers appear in Excel export
- "Highlight Best Values" toggle (off by default) — safety colors always visible; competitive colors opt-in
- Total premium sticky row at matrix bottom — the bottom-line number brokers and clients care most about

**Defer (v2+):**
- Carrier roster management improvements — existing CarrierSettings.tsx is adequate for MVP
- Client profile section on Overview tab — project info sidebar covers key metadata
- TCOR (Total Cost of Risk) calculation — complex actuarial, separate InsurTech product
- Analytics/reporting dashboard — win rates, placement time; separate module, not operational
- Commission tracking — different data model, different regulatory requirements (Mexico CNSF)

### Architecture Approach

The architecture has four major structural decisions: (1) extract ag-grid infrastructure from pipeline to a shared module before broker uses it; (2) build the comparison matrix as a native HTML table with CSS sticky rather than ag-grid; (3) mount the gate strip in AppShell layout (not per-page) to prevent mount/unmount flicker and duplicate polling; (4) use `?tab=` URL query params with `replace: true` for tab state, matching the proven PipelinePage pattern.

**Major components:**
1. `src/shared/grid/` — extracted theme, 4 generic cell renderers (DateCell, StatusPill, ExpandToggleCell, CurrencyCell), and `useColumnPersistence(storageKey)` hook; foundation for both pipeline and broker
2. `BrokerGateStrip` in AppShell layout — persistent gate counts polling at 60s; renders null for non-broker tenants; single instance prevents duplicate fetches
3. `BrokerProjectDetail` redesign — 5 tabs (Overview/Coverage/Carriers/Quotes/Compare) with `?tab=` URL state and step indicator above tabs
4. `comparison/` subfolder — `ComparisonView` orchestrator, `ComparisonMatrix` (enhanced HTML table), `ComparisonCell` (two-row), `CriticalAlertBox`, `ComparisonToolbar`; the product's core deliverable surface
5. `BrokerDashboard` redesign — task list ordered by urgency replaces KPI cards; requires new dashboard aggregation backend endpoint
6. `ProjectsTable` — ag-grid adoption for projects list using shared grid toolkit
7. Excel export — `GET /broker/projects/:id/export-comparison` returns StreamingResponse; frontend uses fetch + Blob + createObjectURL

### Critical Pitfalls

1. **ag-grid extraction breaks pipeline** — PipelinePage.tsx is 757 lines with deeply coupled state. Moving cell renderers without updating all imports causes pipeline grid to silently render blank. Prevention: copy-first (shared is a copy, not a move), smoke-test `/pipeline` after every file move, TypeScript strict mode catches wrong paths at build time.

2. **CSS sticky fails silently in Chrome on table elements** — Chrome has known bugs with `position: sticky` on `<td>/<th>` when any ancestor has `overflow: auto/hidden/scroll`. Current ComparisonMatrix has no sticky — the spec adds it. Prevention: use ag-grid `pinned: 'left'` (proven in PipelinePage) OR switch matrix to CSS Grid layout. Test in Chrome specifically.

3. **CoverageTable inline edit loses `is_manual_override` flag during ag-grid migration** — ag-grid's `onCellValueChanged` replaces React-controlled inputs. The `is_manual_override: true` flag must survive the migration or the system treats manual corrections as AI extractions. Prevention: document all edit logic before rewriting; verify PATCH includes `is_manual_override: true` in network tab.

4. **Excel export blocks FastAPI event loop** — openpyxl's `Workbook.save()` is synchronous CPU-bound. Running directly in async route freezes all concurrent requests for 50-200ms. Prevention: wrap workbook generation in `asyncio.run_in_executor(None, _build_workbook_sync, data)`.

5. **Gate strip polling storm** — If gate strip is placed per-page instead of in layout, it remounts on navigation and creates duplicate polling. Prevention: single instance in AppShell, `refetchInterval: 60_000`, `staleTime: 25_000`; invalidate on project-status-changing mutations.

## Implications for Roadmap

Based on research, suggested phase structure (7 phases):

### Phase 1: Shared ag-grid Toolkit Extraction
**Rationale:** Foundation that both pipeline and broker consume. Must be stable before any broker grid component is built. Doing this first ensures GTM never regresses and broker starts from a clean shared import surface.
**Delivers:** `src/shared/grid/` with theme, 4 generic cell renderers, and `useColumnPersistence(storageKey)` hook; pipeline updated to import from shared; smoke test on `/pipeline` passes.
**Addresses:** Prerequisite for project table, coverage table, carriers table
**Avoids:** Pitfall 1 (pipeline breakage), Pitfall 7 (ag-grid version mismatch), Pitfall 9 (localStorage key collision)

### Phase 2: Gate Strip + Dashboard Redesign
**Rationale:** Gate strip lives in AppShell layout — touching layout.tsx early, before other changes accumulate, reduces conflict risk. Dashboard task list is self-contained with new backend endpoints. Both require the same new backend aggregation endpoints so they bundle naturally.
**Delivers:** Persistent gate strip on all broker pages; dashboard task list replacing KPI cards; `GET /broker/gate-counts` and `GET /broker/dashboard-tasks` backend endpoints; `useGateCounts` and `useDashboardTasks` hooks.
**Avoids:** Pitfall 5 (polling storm — layout-level only, 60s interval), Pitfall 11 (BrokerGuard flash — gate strip inside guard)

### Phase 3: Tabbed Project Detail + Step Indicator
**Rationale:** Structural change that all tab content hangs off. Must be stable before comparison matrix (Phase 5). Tab routing via `useSearchParams` is identical to the proven PipelinePage pattern — no unknowns.
**Delivers:** BrokerProjectDetail redesigned with 5 tabs and step indicator; `?tab=` URL state with `replace: true`; existing components (CoverageTab, CarriersTab, QuotesTab) moved into tab structure.
**Avoids:** Pitfall 6 (back button history pollution — use `replace: true`)

### Phase 4: Projects List Page (ag-grid Adoption)
**Rationale:** Replaces HTML ProjectTable with ag-grid using shared toolkit. Self-contained. Can run in parallel with Phase 3. Delivers immediate sort/filter/search value.
**Delivers:** ProjectsTable with ag-grid, status filter chips, search by name/client, sort by days-in-stage.
**Avoids:** Pitfall 7 (import pattern must match pipeline exactly), Pitfall 9 (unique localStorage key)

### Phase 5: Comparison Matrix Rebuild
**Rationale:** Most complex component. Builds on stable tab structure from Phase 3. Requires the most careful CSS/layout work. Build after foundation is solid.
**Delivers:** ComparisonMatrix with Insurance/Surety tabs; frozen first column + sticky headers; two-row ComparisonCell; CriticalAlertBox above tabs; "Show Differences Only" toggle; "Highlight Best Values" toggle; carrier checkboxes in headers; total premium sticky row.
**Avoids:** Pitfall 3 (CSS sticky Chrome bugs — test in Chrome, use pinned columns as fallback), Pitfall 8 (two-row cell height — fixed 64px rowHeight, not autoHeight)

### Phase 6: Excel Export
**Rationale:** Simple once comparison data is available from Phase 5. One non-obvious pitfall (event loop) with a documented fix. Backend pattern already exists twice in the codebase.
**Delivers:** Export endpoint returning formatted .xlsx with two sheets (Insurance + Surety), color fills, exclusion summary; frontend download via fetch + Blob + createObjectURL.
**Avoids:** Pitfall 4 (event loop blocking — wrap openpyxl in `run_in_executor`)

### Phase 7: CoverageTable ag-grid Migration + Polish
**Rationale:** CoverageTable migration is the highest-risk individual component change due to `is_manual_override` business logic. Defer to last so it doesn't destabilize earlier phases. Polish bundles here.
**Delivers:** CoverageTable on ag-grid with working inline edit; `is_manual_override: true` preserved; empty states for key screens; final UX polish.
**Avoids:** Pitfall 2 (business logic loss — document full edit flow before rewriting)

### Phase Ordering Rationale

- Phases 1 → 5 → 6 are a hard dependency chain: shared grid before broker grids; tab structure before comparison matrix; matrix before Excel export
- Phases 2 and 3 can run in parallel (no shared files)
- Phases 3 and 4 can run in parallel after Phase 1 completes
- Phase 7 is deliberately last because it rewrites a working component with business logic risk
- Each phase delivers usable value: Phase 2 makes every page more useful; Phase 3 makes existing components accessible; Phase 5 is the product's core deliverable

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (Comparison Matrix):** CSS sticky on table elements in Chrome has documented failure modes. Planning must explicitly choose between HTML table sticky vs ag-grid `pinned: 'left'` approach before implementation begins. A 30-minute prototype during planning would de-risk the choice.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Pure refactor of existing code. TypeScript and smoke tests validate correctness.
- **Phase 2:** Standard polling + layout injection patterns. Backend aggregation endpoint design is the only open question (see Gaps).
- **Phase 3:** Identical to proven PipelinePage useSearchParams pattern.
- **Phase 4:** Uses shared toolkit from Phase 1. Standard ag-grid configuration.
- **Phase 6:** StreamingResponse pattern already exists. `run_in_executor` is documented standard.
- **Phase 7:** Risk is business logic preservation, not pattern research. Pre-flight documentation is the mitigation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct package.json inspection + codebase analysis. Zero new dependencies means zero compatibility uncertainty. |
| Features | HIGH | Approved spec (SPEC-BROKER-FRONTEND-MVP.md) + domain research on major broker AMS systems validates feature set. Mexico construction specifics (seguros + fianzas) well-documented. |
| Architecture | HIGH | All recommendations from reading actual production code with specific line numbers cited. Patterns verified as working in existing codebase. |
| Pitfalls | HIGH (codebase) / MEDIUM (CSS, openpyxl) | Pitfalls 1, 2, 7, 9, 12 from direct code analysis. Pitfalls 3, 4, 5, 6, 8 from web research with multiple source agreement. |

**Overall confidence:** HIGH

### Gaps to Address

- **CSS sticky vs ag-grid pinned decision for comparison matrix:** Both solutions are viable but require different implementations. Phase 5 planning should explicitly choose the approach, ideally with a quick prototype to validate before full implementation.
- **Dashboard aggregation endpoint urgency scoring:** The algorithm for ordering tasks by urgency (days waiting + gate type weighting) is not fully specified in research. Phase 2 planning should spec the urgency model before backend implementation begins.
- **Gate-counts query performance at scale:** For MVP (< 100 projects per tenant), a simple COUNT with WHERE clauses is fine. Flag for monitoring post-launch. If tenant project counts grow, an indexed view may be needed.

## Sources

### Primary (HIGH confidence)
- `SPEC-BROKER-FRONTEND-MVP.md` — approved spec, post board review
- `frontend/package.json` — direct dependency inspection
- `frontend/src/features/pipeline/` — ag-grid patterns (PipelinePage.tsx 757 lines), 13 cell renderers, usePipelineColumns.ts 167 lines
- `frontend/src/features/broker/` — 17 existing components, API functions, hooks, types
- `frontend/src/app/layout.tsx` — AppShell architecture, SidebarInset structure
- `backend/src/flywheel/api/documents.py` (lines 638-690) — StreamingResponse download pattern
- `backend/src/flywheel/api/broker.py` — existing broker API patterns

### Secondary (MEDIUM confidence)
- [CSS-Tricks: Sticky header + sticky first column](https://css-tricks.com/a-table-with-both-a-sticky-header-and-a-sticky-first-column/) — sticky table implementation
- [Polypane: All the ways position:sticky can fail](https://polypane.app/blog/getting-stuck-all-the-ways-position-sticky-can-fail/) — Chrome overflow ancestor failure modes
- [AG Grid migration docs](https://www.ag-grid.com/react-data-grid/migration/) — module system compatibility
- [AMS Comparison 2026: Epic vs HawkSoft vs AMS360](https://www.quotesweep.com/blog/ams-comparison-2026) — broker feature benchmarking
- [Howden Mexico Surety Solutions](https://www.howdengroup.com/mx-es/world-class-surety-insurance-solutions) — Mexico fianza market validation
- [TanStack Query polling patterns](https://javascript.plainenglish.io/tanstack-query-mastering-polling-ee11dc3625cb) — refetchInterval behavior

### Tertiary (MEDIUM-LOW confidence)
- [FastAPI Excel export patterns](https://github.com/fastapi/fastapi/issues/1277) — run_in_executor recommendation
- [Insurance UX Design Trends 2025](https://www.g-co.agency/insights/insurance-ux-design-trends-industry-analysis) — dashboard patterns
- [BrokerEdge workflow management](https://www.damcogroup.com/insurance/brokeredge-broker-management-software) — task management patterns

---
*Research completed: 2026-04-14*
*Ready for roadmap: yes*
