---
phase: 57-relationship-surfaces
plan: "03"
subsystem: frontend-detail-page
tags: [relationships, detail-page, two-panel, tabs, header, avatar]
dependency_graph:
  requires: [57-01]
  provides: [relationship-detail-shell, relationship-header]
  affects: [RelationshipDetail.tsx, RelationshipHeader.tsx]
tech_stack:
  added: []
  patterns:
    - TAB_CONFIG constant at module level drives all tab rendering (single source of truth)
    - fromType URL param always drives tab config and back-link (never account.relationship_type)
    - Two-panel layout (320px AI slot left + flex-1 main right) with lg:flex-row breakpoint
    - Inline rgba styles for badge colors — avoids combinatorial CSS class explosion
key_files:
  created:
    - frontend/src/features/relationships/components/RelationshipHeader.tsx
  modified:
    - frontend/src/features/relationships/components/RelationshipDetail.tsx
decisions:
  - "[57-03] TAB_CONFIG defined at module level outside component — avoids recreation on every render and is the single authoritative source for tab sets per type"
  - "[57-03] fromType URL param drives tab config and back-link — CRITICAL: never derived from account.relationship_type (account may belong to multiple types)"
  - "[57-03] AI panel placeholder is a dashed border div — Plan 05 replaces with AskPanel component (clearly commented)"
  - "[57-03] Type badges each wrap in Link to /relationships/{typePlural} — active fromType badge gets rgba(233,77,53,0.2) vs 0.1 for others"
metrics:
  duration: "~4 minutes"
  completed: "2026-03-27"
  tasks_completed: 2
  files_changed: 2
---

# Phase 57 Plan 03: RelationshipDetail Page Skeleton Summary

**One-liner:** Two-panel RelationshipDetail shell — 320px AI slot + type-driven tab navigation, RelationshipHeader with avatar/badges/domain, fromType URL param as single source of truth for tabs and back-link.

## What Was Built

### Task 1: RelationshipHeader component

Created `RelationshipHeader.tsx` with props `{ account: RelationshipDetailItem; fromType: RelationshipType }`:

- **Avatar**: 48px (`size="xl"`) with initials from account.name, brand-coral tint background (`rgba(233,77,53,0.12)`) + coral text — matches sidebar avatar style
- **Name**: `typography.pageTitle` styles (28px, 700 weight, -0.02em letter-spacing)
- **Domain**: external link with Globe icon when account.domain exists, matching AccountDetailPage pattern
- **Type badges**: map `account.relationship_type` array to `<Link>` elements navigating to `/relationships/{typePlural}`; active `fromType` badge gets `rgba(233,77,53,0.2)`, others `rgba(233,77,53,0.1)`; inline styles to avoid CSS class explosion
- **Entity level**: small secondary text (`capitalize(account.entity_level)`)
- **Relationship status**: badge-translucent with color-coded background/text (active=green, at_risk=amber, churned=red, default=gray)
- **Layout**: `flex-col sm:flex-row` — stacks on mobile, horizontal on tablet+

### Task 2: RelationshipDetail page with two-panel layout and type-driven tabs

Replaced placeholder with full implementation:

**URL params:**
- `id` from `useParams<{ id: string }>()`
- `fromType` from `useSearchParams()` with fallback to `'prospect'` — always from URL, never from account data

**TAB_CONFIG constant** (module-level):
- `prospect` / `customer`: Timeline, People, Intelligence, Commitments (4 tabs)
- `advisor` / `investor`: Timeline, People, Commitments (3 tabs — no Intelligence)

**Layout (three states):**
1. **Loading**: `DetailSkeleton` — matches two-panel structure (circular avatar skeleton, 320px left block, tabs + content skeleton on right)
2. **Error/not found**: back link + "Relationship not found" message with explanation text
3. **Loaded**: Full two-panel layout

**Two-panel layout:**
- Outer wrapper: warm tint background (`registers.relationship.background`), `min-h-dvh`
- Content: maxWidth `spacing.maxGrid`, padding `spacing.section/pageDesktop`
- Back link: `<Link to="/relationships/{fromType}s">` with ArrowLeft, shows "Prospects" / "Customers" etc.
- `<RelationshipHeader account={account} fromType={fromType} />`
- Two-panel: `flex flex-col lg:flex-row gap-6 mt-6`
  - Left (AI slot): `w-full lg:w-[320px] lg:shrink-0` — dashed border placeholder with "AI Panel" text; `{/* AskPanel slot — replaced in Plan 05 */}` comment
  - Right (main): `flex-1 min-w-0` — `<Tabs defaultValue="timeline">` with `<TabsList variant="line">` mapped from `TAB_CONFIG[fromType]`; each `TabsContent` has "Coming soon..." placeholder for Plan 04

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `npx tsc --noEmit` passes with zero errors
- RelationshipHeader: 129 lines (> 30 min)
- RelationshipDetail: 204 lines (> 80 min)
- TAB_CONFIG defined at module level — single authoritative constant
- `fromType` reads from `useSearchParams()` only — never from `account.relationship_type`
- AI panel slot clearly commented for Plan 05
- Tab placeholders clearly marked for Plan 04
- Intelligence tab present in prospect/customer TAB_CONFIG entries, absent from advisor/investor

## Self-Check: PASSED

Files verified:
- FOUND: frontend/src/features/relationships/components/RelationshipHeader.tsx
- FOUND: frontend/src/features/relationships/components/RelationshipDetail.tsx

Commit verified: f3ad455 — feat(57-03): RelationshipDetail two-panel layout with type-driven tabs
