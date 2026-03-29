---
phase: 56-pipeline-grid
verified: 2026-03-27T12:00:00Z
status: human_needed
score: 19/20 must-haves verified
re_verification: false
human_verification:
  - test: "Sidebar badge counts do NOT increment after graduation"
    expected: "After graduating an account to Customer/Advisor/Investor, the sidebar should show an incremented badge count for that relationship type"
    why_human: "Sidebar badge rendering is deferred to Phase 57 — no sidebar component reads the signals query key. The pipeline query cache is invalidated, but no sidebar badge UI exists yet. ROADMAP success criterion 5 explicitly requires badge increment. Phase 56 plan explicitly deferred this to Phase 57. Needs product owner decision: does this gap block phase sign-off?"
---

# Phase 56: Pipeline Grid Verification Report

**Phase Goal:** The Pipeline page is a configurable Airtable-style data grid with filters, saved view tabs, and a graduation flow. The design system tokens powering this phase are also established here — shadows, badges, avatars, transitions — so Phase 57 inherits them without rework.
**Verified:** 2026-03-27T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Card shadows render as two-layer box-shadow without visible borders | VERIFIED | `--card-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)` in index.css; dark mode variant also present |
| 2 | Avatar renders initials at 32px (default) and 48px (xl) sizes | VERIFIED | `data-[size=xl]:size-12` in avatar.tsx line 20; xl fallback text scaled via `group-data-[size=xl]/avatar:text-base` |
| 3 | Skeleton shimmer animation plays on loading states | VERIFIED | `ShimmerSkeleton` exported from skeleton.tsx using `animate-shimmer` class; `animate-shimmer` keyframe defined in index.css at line 187 |
| 4 | Empty state renders icon, text, and CTA button | VERIFIED | `EmptyState` component at `frontend/src/components/ui/empty-state.tsx` with `LucideIcon`, title, description, optional Button CTA |
| 5 | All interactive elements transition in 150ms | VERIFIED | `--transition-fast: 150ms ease` in index.css; `transition-interactive` utility class uses it; `.badge-translucent` shares pill shape |
| 6 | Badge-translucent utility provides opacity-10 background + full-opacity text pattern | VERIFIED | `.badge-translucent` in index.css `@layer utilities`; FitTierBadge applies `className="badge-translucent"` and inline `style={{ background: badges.fitTier[tier].bg, color: badges.fitTier[tier].text }}` |
| 7 | Pipeline page renders an AG Grid with 9 columns at 56px row height | VERIFIED | `AgGridReact` in PipelinePage.tsx; `rowHeight: 56` in themeQuartz.withParams(); 9 columns defined in usePipelineColumns.ts |
| 8 | Columns are resizable and reorderable; column state persists in localStorage | VERIFIED | `resizable: true` per ColDef; `defaultColDef={{ resizable: true, sortable: true }}`; localStorage key `flywheel:pipeline:columnState` read/written in usePipelineColumns.ts |
| 9 | Grid uses app design tokens via themeQuartz.withParams() | VERIFIED | `themeQuartz.withParams({ backgroundColor: 'var(--card-bg)', ... accentColor: 'var(--brand-coral)' })` — no ag-grid CSS imports |
| 10 | Company column shows avatar initials + company name + domain | VERIFIED | `CompanyCell.tsx` uses `Avatar`/`AvatarFallback` with size="default", renders `data.name` and `data.domain` |
| 11 | Contact column shows primary contact name + title | VERIFIED | `ContactCell.tsx` renders `data.primary_contact_name` and `data.primary_contact_title`; shows em dash when null |
| 12 | Pipeline endpoint returns primary contact data without N+1 queries | VERIFIED | `primary_contact_sq` DISTINCT subquery with LEFT JOIN at outreach.py line 407-434; not a loop query |
| 13 | Graduate button calls onGraduate from grid context and opens modal | VERIFIED | `GraduateButton` reads `props.context.onGraduate?.(data.id, data.name)`; PipelinePage context wires `setGraduatingAccount` replacing the Plan 02 stub |
| 14 | Fit Tier and Outreach Status multi-select narrow grid rows in real time | VERIFIED | `PipelineFilterBar.tsx` MultiSelect checkboxes with `string[]` arrays; 300ms debounce on search input (lines 153-155) |
| 15 | Saved view tabs (All, Hot, Stale, Replied) filter with URL persistence | VERIFIED | `PipelineViewTabs.tsx` uses `useSearchParams` from react-router; Hot sets `['Excellent', 'Strong']`, Replied sets `['replied']`, Stale applies client-side filter |
| 16 | Stale rows (>14 days) render with warm tint background without filter interaction | VERIFIED | `getRowStyle` in PipelinePage.tsx checks `days_since_last_outreach > 14` and returns `{ background: 'var(--brand-tint-warmest)' }` |
| 17 | Replied rows float to top with coral accent without filter interaction | VERIFIED | `postSortRows` pushes `last_outreach_status === 'replied'` rows first; `getRowStyle` adds `{ borderLeft: '3px solid var(--brand-coral)' }` |
| 18 | Page size selector offers 25/50/100 with server-side pagination | VERIFIED | `PAGE_SIZE_OPTIONS = [25, 50, 100]` in PipelinePage.tsx; `pageSize` drives `limit` param to usePipeline; "Showing X-Y of Z" display |
| 19 | Graduate modal submits to POST /relationships/{id}/graduate with types array | VERIFIED | `api.ts` calls `api.post(\`/relationships/${payload.id}/graduate\`)`; GraduationModal has Customer/Advisor/Investor checkboxes with entity_level auto-detection; `useGraduate` invalidates pipeline+relationships+signals+accounts |
| 20 | Sidebar badge count increments after graduation | HUMAN NEEDED | `useGraduate` invalidates `['signals']` query key but no sidebar badge UI component exists yet — deferred to Phase 57. ROADMAP success criterion 5 lists this as required. |

**Score:** 19/20 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/index.css` | CSS tokens: --card-shadow, --brand-tint-warm, --brand-tint-warmest, --transition-fast, --row-height-grid, badge-translucent, slide-out-right | VERIFIED | All tokens present in both light and dark modes; utilities in @layer utilities |
| `frontend/src/lib/design-tokens.ts` | shadows, transitions, registers, badges exports | VERIFIED | All 4 objects exported; cardShadow, cardShadowHover, brandTintWarm, brandTintWarmest in colors |
| `frontend/src/components/ui/avatar.tsx` | Avatar with xl (48px) size variant | VERIFIED | `data-[size=xl]:size-12` present at line 20 |
| `frontend/src/components/ui/skeleton.tsx` | ShimmerSkeleton using animate-shimmer | VERIFIED | `ShimmerSkeleton` exported at line 24 using `animate-shimmer` class |
| `frontend/src/components/ui/empty-state.tsx` | EmptyState with icon, title, description, action | VERIFIED | File exists; exports `EmptyState`; uses LucideIcon, Button CTA |
| `frontend/src/features/pipeline/components/PipelinePage.tsx` | AG Grid replacing HTML table | VERIFIED | Contains `AgGridReact`, `themeQuartz`, `usePipelineColumns`, all plan 03 wiring |
| `frontend/src/features/pipeline/hooks/usePipelineColumns.ts` | 9 column definitions + localStorage persistence | VERIFIED | Contains 9 ColDef entries; localStorage key `flywheel:pipeline:columnState`; `getColumnState()`/`setItem` |
| `frontend/src/features/pipeline/components/cell-renderers/CompanyCell.tsx` | Avatar + company name + domain | VERIFIED | Uses Avatar/AvatarFallback, renders name and domain |
| `frontend/src/features/pipeline/components/cell-renderers/ContactCell.tsx` | Contact name + title | VERIFIED | Renders primary_contact_name and primary_contact_title |
| `frontend/src/features/pipeline/components/cell-renderers/FitTierBadge.tsx` | Translucent badge using badge-translucent class | VERIFIED | Uses `className="badge-translucent"` + inline rgba styles from badges.fitTier tokens |
| `frontend/src/features/pipeline/components/cell-renderers/OutreachDot.tsx` | 8px status dot | VERIFIED | File exists |
| `frontend/src/features/pipeline/components/cell-renderers/GraduateButton.tsx` | Action button reading props.context.onGraduate | VERIFIED | Reads `context.onGraduate?.(data.id, data.name)` at line 21 |
| `frontend/src/features/pipeline/components/cell-renderers/DaysSinceCell.tsx` | Color-coded days cell | VERIFIED | File exists |
| `frontend/src/features/pipeline/components/PipelineFilterBar.tsx` | Multi-select filter bar + debounced search | VERIFIED | MultiSelect with checkboxes, `string[]` props, 300ms debounce |
| `frontend/src/features/pipeline/components/PipelineViewTabs.tsx` | Saved view tabs with URL persistence | VERIFIED | useSearchParams; All/Hot/Stale/Replied tabs; `?view=` param written |
| `frontend/src/features/pipeline/components/GraduationModal.tsx` | Type-selection dialog with Customer/Advisor/Investor | VERIFIED | Dialog with 3 type options, entity_level auto-detection, useGraduate hook |
| `frontend/src/features/pipeline/hooks/useGraduate.ts` | Mutation calling /relationships/{id}/graduate | VERIFIED | Calls `graduateAccount(payload)`; invalidates pipeline+relationships+signals+accounts |
| `frontend/src/features/pipeline/api.ts` | Updated graduation endpoint + array params | VERIFIED | `/relationships/${payload.id}/graduate` at line 24 |
| `backend/src/flywheel/api/outreach.py` | fit_tier/outreach_status/search list params + primary contact JOIN | VERIFIED | `list[str] | None = Query(default=None)` at lines 349-351; DISTINCT subquery LEFT JOIN; IN() on both data and count queries |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `PipelinePage.tsx` | `usePipelineColumns.ts` | `usePipelineColumns` hook call | WIRED | Line 97 |
| `usePipelineColumns.ts` | localStorage | `flywheel:pipeline:columnState` key | WIRED | Lines 11, 120, 134 |
| `PipelinePage.tsx` | `ag-grid-react` | `AgGridReact` component with theme prop | WIRED | Lines 4-5, 237+ |
| `GraduateButton.tsx` | `PipelinePage.tsx` | `props.context.onGraduate` → `setGraduatingAccount` | WIRED | GraduateButton line 21; PipelinePage line 251-252 |
| `useGraduate.ts` | `POST /relationships/{id}/graduate` | `api.post` call in api.ts | WIRED | api.ts line 24; useGraduate.ts calls graduateAccount |
| `PipelineViewTabs.tsx` | URL query params | `useSearchParams` `?view=` | WIRED | Lines 1, 25, 31-33 |
| `PipelineFilterBar.tsx` | `usePipeline.ts` (via PipelinePage) | filter state passed as params | WIRED | PipelinePage passes fitTier/outreachStatus/search to usePipeline at lines 63-70 |
| `GraduationModal.tsx` | `useGraduate.ts` | `graduate.mutate({ types: selectedTypes })` | WIRED | Lines 36, 53-54 |
| `design-tokens.ts` | `index.css` | `var(--card-shadow)` references | WIRED | shadows.card = `'var(--card-shadow)'` at line 47 |

---

## Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| DS-01: Card shadows, warm tints | SATISFIED | --card-shadow two-layer, --brand-tint-warm, --brand-tint-warmest |
| DS-02: Badge translucent pattern | SATISFIED | badge-translucent utility + badges.fitTier design tokens |
| DS-03: Avatar sizes (default 32px, xl 48px) | SATISFIED | data-[size=xl]:size-12 confirmed |
| DS-04: Skeleton shimmer + EmptyState | SATISFIED | ShimmerSkeleton and EmptyState both verified |
| GRID-01: AG Grid with 9 columns at 56px | SATISFIED | AgGridReact with themeQuartz rowHeight:56, 9 ColDefs |
| GRID-02: Resize, reorder, localStorage persistence | SATISFIED | resizable:true per column, localStorage key flywheel:pipeline:columnState |
| GRID-03: Filter bar with multi-select + search + view tabs | SATISFIED | PipelineFilterBar MultiSelect, 300ms debounce; PipelineViewTabs URL-persisted |
| GRID-04: Stale row tint + reply float-to-top | SATISFIED | getRowStyle + postSortRows confirmed |
| GRID-05: Graduation flow (modal + API + slide-out) | PARTIALLY SATISFIED | Modal, API, slide-out animation confirmed; sidebar badge increment deferred to Phase 57 |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `PipelinePage.tsx` | 251 (Plan 02 stub replaced) | No anti-patterns found — onGraduate stub was correctly replaced with `setGraduatingAccount` | — | — |

No TODO/FIXME/placeholder patterns found in delivered files. No empty implementations. No stub return values.

---

## Human Verification Required

### 1. Sidebar badge count after graduation

**Test:** Open the Pipeline page, click "Graduate" on any account row, select "Customer", submit. After the modal closes and the row slides out, check if the sidebar shows an incremented badge count next to Customers.
**Expected:** Sidebar badge count for "Customers" (or equivalent) increases by 1.
**Why human:** No sidebar badge component exists in Phase 56 code. `useGraduate` invalidates the `['signals']` query key, but no UI component currently reads it to display badge counts. This feature is explicitly deferred to Phase 57 (per Plan 03's must_have: "sidebar badge display deferred to Phase 57"). ROADMAP success criterion 5 lists badge increment as required. Product owner must decide: is this an acceptable Phase 56 gap (completed in Phase 57) or a blocker?

---

## Gaps Summary

One gap exists between the ROADMAP success criterion and what was delivered:

**ROADMAP Success Criterion 5** states: "the sidebar badge count for the selected type increments" — this is explicitly in scope per the ROADMAP.

**Plan 03 must_have truth** states: "Graduated row slides out with animation and query cache is invalidated **(sidebar badge display deferred to Phase 57)**" — this explicitly descoped it at the plan level.

The graduation flow itself (modal, API call, slide-out animation, cache invalidation) is fully implemented and working. Only the sidebar badge rendering is missing — which requires Phase 57's sidebar redesign work to be meaningful anyway.

All other 19 must-haves are fully verified. The codebase matches the SUMMARY claims with no gaps on the core pipeline grid, design system tokens, or graduation flow. TypeScript compiled with zero errors.

---

_Verified: 2026-03-27T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
