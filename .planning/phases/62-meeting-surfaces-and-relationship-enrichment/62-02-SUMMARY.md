---
phase: 62
plan: 02
subsystem: frontend/settings
tags: [settings, integrations, granola, ui]
dependency_graph:
  requires:
    - "60-02: Granola adapter + POST /integrations/granola/connect"
    - "61-03: POST /meetings/sync endpoint"
    - "59-01: integrations table + RLS"
  provides:
    - "GranolaSettings component with connect/disconnect/sync UI"
    - "Settings Integrations tab visible to non-anonymous users"
  affects:
    - "frontend/src/pages/SettingsPage.tsx"
    - "frontend/src/features/settings/components/"
tech_stack:
  added: []
  patterns:
    - "useMutation + toast.success/error for connect/disconnect/sync"
    - "useQuery ['integrations'] with client-side filter for provider=granola AND status=connected"
    - "date-fns formatDistanceToNow for last_synced_at relative display"
key_files:
  created:
    - frontend/src/features/settings/components/GranolaSettings.tsx
  modified:
    - frontend/src/pages/SettingsPage.tsx
decisions:
  - "Client-side filter checks BOTH provider=granola AND status=connected — disconnected rows may remain in DB"
  - "syncMutation calls POST /meetings/sync (not /integrations/{id}/sync) per plan spec — meetings-domain endpoint returns synced/skipped/already_seen stats"
  - "Disconnect button uses outline variant with destructive text color rather than variant=destructive — avoids full-red button, signals caution appropriately"
metrics:
  duration: "< 2 minutes"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
  completed_date: "2026-03-28"
---

# Phase 62 Plan 02: Granola Settings UI Summary

Granola connection settings UI with API key input, connect/disconnect flow, and sync controls under a new Integrations tab in the Settings page.

## Tasks Completed

| # | Task | Status | Files |
|---|------|--------|-------|
| 1 | GranolaSettings component | Done | GranolaSettings.tsx (created) |
| 2 | Add Integrations tab to SettingsPage | Done | SettingsPage.tsx (modified) |

## What Was Built

### GranolaSettings component (`frontend/src/features/settings/components/GranolaSettings.tsx`)

Two render states:

**Not-connected state:**
- CalendarDays icon heading + description text
- Password input with Eye/EyeOff show-hide toggle
- Connect button (disabled when empty or pending) with Loader2 spinner while connecting
- `connectMutation` POSTs to `/integrations/granola/connect` with `{ api_key }`, invalidates `['integrations']`, shows toast.success, clears input on success

**Connected state:**
- Green CheckCircle2 icon heading + "Connected" status text in green
- Last synced card showing `formatDistanceToNow` relative time (or "Never")
- Sync Now button → `syncMutation` POSTs to `/meetings/sync`, invalidates `['meetings']`, shows detailed toast with synced/skipped/already_seen counts
- Disconnect button (outline/destructive color) → `disconnectMutation` DELETEs `/integrations/{id}`, invalidates `['integrations']`

### SettingsPage (`frontend/src/pages/SettingsPage.tsx`)

Added Integrations tab after Team tab in TabsList and corresponding TabsContent, gated behind `isAdmin` (same as Workspace and Team tabs).

## Verification

- `npx tsc --noEmit` — passes with zero errors in created/modified files
- `npm run build` — pre-existing errors in PipelineGrid and CompanyProfilePage (unrelated to this plan); no new errors introduced

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

- Client-side `provider === 'granola' && status === 'connected'` double-check per plan's CRITICAL note — a disconnected row may exist from a previous connection
- `syncMutation` calls `/meetings/sync` (not `/integrations/{id}/sync`) as specified — the meetings endpoint returns sync stats (synced/skipped/already_seen) relevant for user feedback
- Destructive outline variant for Disconnect button: avoids full red button while still signaling risk

## Self-Check: PASSED
