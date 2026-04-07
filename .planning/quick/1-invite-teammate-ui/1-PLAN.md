---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/features/settings/components/TeamManager.tsx
autonomous: true
must_haves:
  truths:
    - "Settings > Team tab shows current members with name, role, and joined date"
    - "Admin can type an email and send an invite"
    - "Admin can remove a non-self member"
    - "Pending invites appear in the members list with 'pending' badge"
    - "Success/error feedback shown via toast notifications"
  artifacts:
    - path: "frontend/src/features/settings/components/TeamManager.tsx"
      provides: "Team management UI wired to real backend endpoints"
  key_links:
    - from: "TeamManager.tsx"
      to: "/api/v1/tenants/members"
      via: "useQuery with api.get"
      pattern: "api\\.get.*tenants/members"
    - from: "TeamManager.tsx"
      to: "/api/v1/tenants/invite"
      via: "useMutation with api.post"
      pattern: "api\\.post.*tenants/invite"
    - from: "TeamManager.tsx"
      to: "/api/v1/tenants/members/{user_id}"
      via: "useMutation with api.delete"
      pattern: "api\\.delete.*tenants/members"
---

<objective>
Fix TeamManager.tsx to wire correctly to the existing backend endpoints.

The component already exists and is mounted in the Settings page under the "Team" tab.
However, the API paths are wrong -- it uses `/tenants/${tenantId}/members` and
`/tenants/${tenantId}/invites` but the backend uses `/tenants/members` and
`/tenants/invite` (tenant derived from auth token, not URL). The response shape also
differs: the backend returns a single list of MemberItem objects with a `status` field
("active" or "pending") rather than separate members/invites endpoints.

Purpose: Make the Team settings tab functional against the real backend.
Output: Working TeamManager.tsx with correct API wiring and toast feedback.
</objective>

<execution_context>
@/Users/sharan/.claude/get-shit-done/workflows/execute-plan.md
@/Users/sharan/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/features/settings/components/TeamManager.tsx
@frontend/src/pages/SettingsPage.tsx
@frontend/src/lib/api.ts
@backend/src/flywheel/api/tenant.py (lines 55-110 for models, 295-370 for invite, 441-520 for members/delete)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite TeamManager.tsx to match backend API contract</name>
  <files>frontend/src/features/settings/components/TeamManager.tsx</files>
  <action>
Rewrite TeamManager.tsx to fix the API contract mismatch. Key changes:

1. **Fix the MemberItem interface** to match the backend response model:
   ```
   interface MemberItem {
     user_id: string | null
     email: string
     name: string | null
     role: string
     joined_at: string | null
     status: "active" | "pending"
     expires_at: string | null
   }
   ```

2. **Single query for all members + invites** — the backend returns both in one list:
   - `GET /tenants/members` (no tenantId in URL — backend derives from auth token)
   - Query key: `['tenant-members']` (no tenantId needed)
   - No separate invites query — remove the old `useQuery` for invites entirely

3. **Fix invite mutation**:
   - `POST /tenants/invite` with body `{ email }` (not `/tenants/${tenantId}/invites`)
   - On success: invalidate `['tenant-members']`, clear input, show toast via `sonner`: `toast.success('Invite sent')`
   - On error: show `toast.error(err.message || 'Failed to send invite')` — remove the inline error message

4. **Fix remove mutation**:
   - `DELETE /tenants/members/${userId}` (not `/tenants/${tenantId}/members/${memberId}`)
   - On success: invalidate `['tenant-members']`, show `toast.success('Member removed')`

5. **Remove revoke invite mutation** — there is no backend endpoint for revoking invites. Do not render a Revoke button.

6. **Remove the `useTenantStore` import** — no longer needed since tenantId is not in URLs. Keep `useAuthStore` for current user check.

7. **Render the unified list** split into two sections visually:
   - **Active Members section**: filter `status === "active"`. Show avatar circle with first letter of `name ?? email`. Show name (bold) and email below (or just email if no name). Show role badge. Show "Remove" X button (same logic: not self, not last admin). Show "(you)" next to current user (match on `user_id === currentUser?.id`).
   - **Pending Invites section**: filter `status === "pending"`. Show Mail icon + email. Show "Pending" badge (use `outline` variant). Show expires date. No revoke button (endpoint doesn't exist).

8. **Add `import { toast } from 'sonner'`** for toast notifications instead of inline success/error messages. Remove the inline `inviteMutation.isError` and `inviteMutation.isSuccess` message blocks.

9. **Keep the existing UI patterns**: Input + Button for invite form, divide-y list styling, Skeleton loading states, `size-icon-xs` ghost button for remove, Badge for roles. Keep the `enabled: !!currentUser` guard (or just always enabled since auth is required for the settings page — use `enabled: true` since the route is already auth-gated).

10. **Remove `invitesLoading` state** since there's only one query now. Use `isLoading` from the single members query for both sections.
  </action>
  <verify>
    Run `cd /Users/sharan/Projects/flywheel-v2/frontend && npx tsc --noEmit` to confirm no type errors.
    Visually inspect the component: it should have one useQuery, two useMutations (invite + remove), toast feedback, and two rendered sections (active members, pending invites).
  </verify>
  <done>
    TeamManager.tsx compiles without errors, calls correct backend endpoints (`/tenants/members`, `/tenants/invite`, `/tenants/members/{id}`), shows toast notifications on success/error, renders active members and pending invites from a single API response.
  </done>
</task>

</tasks>

<verification>
- `npx tsc --noEmit` passes in frontend directory
- TeamManager.tsx uses `/tenants/members` (GET), `/tenants/invite` (POST), `/tenants/members/${id}` (DELETE)
- No references to `${tenantId}` in API paths
- No separate invites query or revoke mutation
- Toast notifications via sonner on invite success/error and member removal
</verification>

<success_criteria>
TeamManager.tsx correctly wired to backend: single members query, invite and remove mutations with correct paths, toast feedback, no type errors.
</success_criteria>

<output>
After completion, create `.planning/quick/1-invite-teammate-ui/1-SUMMARY.md`
</output>
