---
phase: quick
plan: 1
subsystem: frontend/settings
tags: [team-management, api-wiring, ui]
dependency_graph:
  requires: [backend-tenant-api]
  provides: [team-management-ui]
  affects: [settings-page]
tech_stack:
  added: []
  patterns: [sonner-toast, unified-member-query]
key_files:
  created: []
  modified:
    - frontend/src/features/settings/components/TeamManager.tsx
decisions:
  - Removed useTenantStore dependency since backend derives tenant from auth token
  - Single useQuery replaces separate members+invites queries matching backend unified response
  - No revoke invite button since backend has no revoke endpoint
  - canRemove logic excludes self AND last-admin (backend also enforces both)
metrics:
  duration: 50s
  completed: 2026-03-30
---

# Quick Task 1: Invite Teammate UI Summary

Wire TeamManager.tsx to real backend endpoints with correct API paths, unified member list, and toast feedback.

## What Changed

**TeamManager.tsx** was rewritten to match the actual backend API contract:

1. **API paths fixed**: `/tenants/members` (GET), `/tenants/invite` (POST), `/tenants/members/{userId}` (DELETE) -- no tenantId in URLs
2. **Single query**: Backend returns active members and pending invites in one `MemberItem[]` list with `status` field, replacing the two separate queries
3. **Interface updated**: `MemberItem` now matches backend model (user_id, email, name, role, joined_at, status, expires_at)
4. **Toast notifications**: Replaced inline success/error messages with `sonner` toast calls
5. **Removed dead code**: `useTenantStore` import, `revokeMutation`, separate `invitesLoading` state, `Invite` interface

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| ec28a73 | feat(quick-1): wire TeamManager.tsx to real backend API contract |

## Verification

- `npx tsc --noEmit` passes with zero errors
- No references to `${tenantId}` in API paths
- Single `useQuery` with key `['tenant-members']`
- Two `useMutation` hooks (invite + remove), no revoke
- `toast.success` / `toast.error` calls for all mutations

## Self-Check: PASSED
