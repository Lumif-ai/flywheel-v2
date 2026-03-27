---
phase: 57-relationship-surfaces
plan: "01"
subsystem: frontend-data-layer + backend-serialization
tags: [relationships, api, hooks, sidebar, routing, types]
dependency_graph:
  requires: [56-pipeline-grid]
  provides: [relationships-data-layer, relationships-routes, sidebar-redesign]
  affects: [AppSidebar, routes.tsx, relationships.py]
tech_stack:
  added: []
  patterns:
    - queryKeys factory with nested .relationships and .signals namespaces
    - useSignals staleTime=30_000 for sidebar badge counts without realtime overhead
    - _serialize_timeline_item helper for direction/contact_name derivation
    - enabled: !!user guard on all React Query hooks
key_files:
  created:
    - frontend/src/features/relationships/types/relationships.ts
    - frontend/src/features/relationships/api.ts
    - frontend/src/features/relationships/hooks/useRelationships.ts
    - frontend/src/features/relationships/hooks/useRelationshipDetail.ts
    - frontend/src/features/relationships/hooks/useSignals.ts
    - frontend/src/features/relationships/hooks/useCreateNote.ts
    - frontend/src/features/relationships/hooks/useSynthesize.ts
    - frontend/src/features/relationships/hooks/useAsk.ts
    - frontend/src/features/relationships/components/RelationshipListPage.tsx
    - frontend/src/features/relationships/components/RelationshipDetail.tsx
  modified:
    - backend/src/flywheel/api/relationships.py
    - frontend/src/features/navigation/components/AppSidebar.tsx
    - frontend/src/app/routes.tsx
decisions:
  - "[57-01] ContactItem uses created_at (not last_contacted_at) — backend does not expose last_contacted_at; created_at used for 'Added X ago' display"
  - "[57-01] signalByType helper reads from useSignals() data — avoids prop drilling signal counts through sidebar tree"
  - "[57-01] Placeholder components created in Plan 01 so routes register immediately — Plans 02/03 replace them with real implementations"
metrics:
  duration: "~5 minutes"
  completed: "2026-03-27"
  tasks_completed: 3
  files_changed: 13
---

# Phase 57 Plan 01: Foundation Data Layer Summary

**One-liner:** Complete relationships data foundation — backend intel+direction+contact_name serialization, 8-file TypeScript data layer, sidebar RELATIONSHIPS section with coral badge counts, and 5 lazy routes.

## What Was Built

### Backend (Task 1)
Patched `GET /relationships/{id}` (RAPI-02) in `relationships.py`:

- Added `intel: dict` field to `RelationshipDetail` Pydantic model and to the return dict (`account.intel or {}`)
- Extended `TimelineItem` with `direction: str | None` and `contact_name: str | None`
- Added `_derive_direction(source)` helper — maps source prefixes to "inbound" / "outbound" / "internal" / "bidirectional"
- Added `_extract_contact_name(content)` helper — regex extracts name from "Email from X:" / "Meeting with X:" patterns
- Added `_serialize_timeline_item(entry)` helper — replaces the inline dict comprehension

### Frontend Data Layer (Task 2)

**Types** (`types/relationships.ts`):
- `RelationshipType` union type
- `RelationshipListItem`, `ContactItem` (uses `created_at`, no `last_contacted_at`), `TimelineItem` (with `direction` + `contact_name`), `RelationshipDetailItem` (extends list item with `intel`)
- `TypeBadge`, `SignalsResponse`, `AskResponse`

**API** (`api.ts`):
- `queryKeys` factory: `relationships.all`, `.list(type)`, `.detail(id)`, `signals.all`
- 6 API functions: `fetchRelationships`, `fetchRelationshipDetail`, `fetchSignals`, `createNote`, `synthesize`, `askRelationship`

**Hooks** (6 files):
- `useRelationships(type)` — list query, enabled: !!user
- `useRelationshipDetail(id)` — detail query, enabled: !!id && !!user
- `useSignals()` — sidebar badge counts, staleTime: 30s
- `useCreateNote()` — mutation, invalidates detail on success
- `useSynthesize()` — mutation, invalidates detail on success, 429 toast via sonner
- `useAsk()` — stateless mutation, no cache invalidation

### Sidebar + Routes (Task 3)

**AppSidebar** restructured into 3 SidebarGroups:
1. General nav: Briefing, Company Profile, Library, Email, Accounts (backward compat)
2. RELATIONSHIPS group with styled label (11px, uppercase, 0.06em letter-spacing): Prospects / Customers / Advisors / Investors — each with coral badge count via `useSignals()`
3. Pipeline — repositioned below Relationships

**routes.tsx**: 5 lazy routes added after `/pipeline`:
- `/relationships/prospects` → `<RelationshipListPage type="prospect" />`
- `/relationships/customers` → `<RelationshipListPage type="customer" />`
- `/relationships/advisors` → `<RelationshipListPage type="advisor" />`
- `/relationships/investors` → `<RelationshipListPage type="investor" />`
- `/relationships/:id` → `<RelationshipDetail />`

**Placeholder components** created for Plans 02/03 to replace.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `npx tsc --noEmit` passes with zero errors
- Backend syntax verified with `python3 -m py_compile`
- All 8 data layer files confirmed to exist
- `intel` key present in RAPI-02 return dict (grep verified)
- `direction` and `contact_name` in `TimelineItem` model and serialization helper

## Self-Check: PASSED

Files verified:
- FOUND: frontend/src/features/relationships/api.ts
- FOUND: frontend/src/features/relationships/types/relationships.ts
- FOUND: frontend/src/features/relationships/hooks/useRelationships.ts
- FOUND: frontend/src/features/relationships/hooks/useRelationshipDetail.ts
- FOUND: frontend/src/features/relationships/hooks/useSignals.ts
- FOUND: frontend/src/features/relationships/hooks/useCreateNote.ts
- FOUND: frontend/src/features/relationships/hooks/useSynthesize.ts
- FOUND: frontend/src/features/relationships/hooks/useAsk.ts
- FOUND: frontend/src/features/relationships/components/RelationshipListPage.tsx
- FOUND: frontend/src/features/relationships/components/RelationshipDetail.tsx

Commit verified: 62f50d9 — feat(57-01): data layer, sidebar RELATIONSHIPS section, routes
