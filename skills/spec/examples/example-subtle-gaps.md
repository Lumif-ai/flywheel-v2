# Example: Reviewing a Spec That Looks Complete But Has Fatal Gaps

This example demonstrates Mode 2 (Review) catching non-obvious issues in a spec
that appears well-written. The gaps are the kind that cause expensive rework
two weeks into development, not the kind a junior engineer would spot.

---

## The Spec Being Reviewed (input)

```markdown
# Team Permissions System — Specification

> Status: Reviewed
> Created: 2026-03-10

## Overview
Add role-based access control to the existing team workspace. Team admins can
assign roles (Admin, Editor, Viewer) to members, controlling what they can
see and do.

## Core Value
Team admins can control who has access to what, preventing unauthorized changes.

## Requirements

### Must Have
- **PERM-01**: Admin can invite users and assign roles
  - **Acceptance Criteria:**
    - [ ] Invite via email with role pre-selected
    - [ ] Roles: Admin, Editor, Viewer
    - [ ] Invited user receives email with join link
    - [ ] Join link expires after 7 days

- **PERM-02**: Permissions enforced on all actions
  - **Acceptance Criteria:**
    - [ ] Viewer: read-only access to all content
    - [ ] Editor: can create, edit, and delete their own content
    - [ ] Admin: full access including team settings and billing
    - [ ] Unauthorized actions return 403 with "You don't have permission"

- **PERM-03**: Admin can change a user's role
  - **Acceptance Criteria:**
    - [ ] Role change takes effect immediately
    - [ ] User sees updated permissions without re-login
    - [ ] Activity log records who changed what role and when

- **PERM-04**: Admin can remove users from the team
  - **Acceptance Criteria:**
    - [ ] Removed user loses access immediately
    - [ ] Removed user's content is preserved (not deleted)
    - [ ] Removed user receives email notification

### Should Have
- **PERM-05**: Audit log of all permission changes
  - **Acceptance Criteria:**
    - [ ] Log entries: timestamp, actor, action, target user, old role, new role
    - [ ] Filterable by date range and action type
    - [ ] Retained for 1 year

## Edge Cases & Error States
| Scenario | Expected Behavior |
|----------|-------------------|
| Admin removes the only other admin | Prevent action: "Team must have at least one admin" |
| Invited user's email doesn't match any existing account | Create account on join |
| Expired invite link clicked | Show "This invite has expired. Ask your team admin for a new one." |
| Editor tries to access team settings | Show settings page with fields disabled + "Contact admin to change" |

## Constraints
- Must work with existing session-based auth (no migration to JWT)
- Permissions checked server-side on every request (not just UI hiding)

## Anti-Requirements
- No custom roles (only Admin/Editor/Viewer)
- No per-resource permissions (roles apply to entire workspace)
- No SSO/SAML in this version
```

---

## Review Output (what `/spec review` produces)

### Critical (will cause rework)

**1. [Contradiction] PERM-02 says Editors can "delete their own content" — but PERM-04 says removed user's content is "preserved." Who owns orphaned content?**

This creates a cascade of undefined states:
- Editor creates 50 documents, gets removed. Documents stay. Good.
- New editor joins. Can they edit the orphaned documents? Spec doesn't say.
- Original editor gets re-invited. Do they regain ownership? Or are those now "unowned"?
- If an Admin edits an orphaned document, who is the new owner?

This seems minor but it determines your entire data model. "Content ownership" isn't a feature — it's a foundation. Building PERM-02 and PERM-04 without resolving this means you'll refactor the content model mid-sprint.

**Fix:** Add a requirement defining content ownership rules: (a) content is owned by creator forever (even if removed), (b) content transfers to the team (no individual owner), or (c) admin can reassign ownership. Each choice has different data model implications.

**2. [Completeness] No specification for what Editors can do to EACH OTHER's content.**

PERM-02 says Editors can "create, edit, and delete their own content." But:
- Can Editor A see Editor B's draft? What about published content?
- Can Editor A edit Editor B's published content? (Collaborative editing = yes. Blog authorship = no.)
- Can Editor A delete Editor B's content? (Almost certainly not, but the spec doesn't say.)

"Their own content" is doing enormous load-bearing work here. In a collaborative workspace, the boundary between "my content" and "our content" is the most contentious design decision. Leaving it to the engineer means two engineers will build it differently.

**Fix:** Define a content visibility/editability matrix:

| Action | Own content | Others' content |
|--------|-------------|-----------------|
| View | Yes | ? |
| Edit | Yes | ? |
| Delete | Yes | ? |

**3. [Missing requirement] No specification for the transition period when a role change happens mid-session.**

PERM-03 says "takes effect immediately" and "without re-login." But:
- User has Editor role, opens a document for editing
- Admin changes them to Viewer while document is open
- User clicks "Save"
- What happens? 403? Silent discard? Save succeeds because they had permission when they opened it?

This is a race condition that WILL happen in production. "Immediately" needs to define whether it means "next request" or "current open sessions." If it's current sessions, you need WebSocket push or polling for permission changes, which is significantly more architecture.

**Fix:** Choose: (a) next request — simpler, user sees 403 on save and loses unsaved work (bad UX but easy), or (b) push notification — more complex, user sees "Your permissions changed, this document is now read-only" in real-time (good UX, needs WebSocket).

### Major (likely edge case bugs)

**4. [Completeness] Edge case table misses the most dangerous scenario: what happens when the LAST admin demotes THEMSELVES?**

The spec handles "admin removes the only other admin" (prevented). But:
- Team has two admins (Alice and Bob)
- Alice changes Bob's role to Viewer
- Bob changes Alice's role to Viewer
- Now there are zero admins and nobody can manage the team

Neither action was "removing the last admin" — each was removing one of two. But the sequence creates an unrecoverable state.

**Fix:** The check must be "will this action result in zero admins?" not "is this the last admin?" This means checking if the target is the last user with Admin role after the change, not before.

**5. [Ambiguity] PERM-02 says Admin has "full access including team settings and billing" — but is billing access really a permission or a separate concern?**

If a startup has 3 admins, should all 3 see the credit card details and be able to change the plan? Most products separate "team admin" from "billing admin" because:
- Billing contains PCI-sensitive data
- Plan changes have financial impact
- Some orgs want IT to manage team access but finance to manage billing

If you ship Admin = billing access and a customer asks to separate them, it's a schema migration and new role type — exactly the thing the anti-requirements say you won't do ("No custom roles").

**Fix:** Either (a) explicitly state all Admins can manage billing (and accept the customer feedback risk), or (b) add a "Billing" permission flag separate from the Admin role (doesn't require custom roles, just a boolean).

**6. [Non-functional gap] No specification for permission check performance.**

"Permissions checked server-side on every request" — this means every API call now has a permission lookup. At 100 requests/second:
- DB lookup per request? That's 100 queries/second just for permissions
- Cached? What's the cache invalidation strategy when roles change "immediately"?
- In-memory? Then how do multiple server instances stay in sync?

The constraint says "every request" but doesn't specify the performance impact. If the team builds a naive DB-per-request implementation, they'll hit a wall at scale. If they cache, the "immediately" requirement for role changes conflicts with cache TTL.

**Fix:** Add a constraint: "Permission check must add < 5ms to request latency." This forces the team to think about caching strategy upfront. Suggest: cache permissions in Redis with a 30-second TTL, and invalidate on role change events.

### Minor (polish)

**7. [Ambiguity] "Activity log records who changed what role and when" (PERM-03) vs "Audit log of all permission changes" (PERM-05) — are these the same log?**

PERM-03 mentions an activity log inline. PERM-05 defines an audit log as a separate Should Have. Are they the same feature? If so, is it Must Have (PERM-03 implies yes) or Should Have (PERM-05 says)? If different, what goes in which?

**Fix:** Remove the log reference from PERM-03 and keep PERM-05 as the single source of truth for audit logging. Upgrade PERM-05 to Must Have if audit logging is required for the role change feature.

---

## Why This Example Matters

Every finding above passes the "two engineers would build this differently" test. The spec looks solid — it has acceptance criteria, edge cases, anti-requirements, constraints. A junior reviewer would approve it.

But the critical gaps (#1, #2, #3) would each cause 2-3 days of rework when discovered during development:
- **#1** (content ownership) forces a data model refactor
- **#2** (cross-user content) forces a permissions matrix redesign
- **#3** (mid-session role change) forces an architecture decision about real-time updates

These are exactly the gaps that cost teams the most: invisible until implementation, expensive to fix retroactively.

The review doesn't just say "add more detail." It identifies the specific decision points, explains why they matter, and proposes concrete options. The user picks, the spec updates, and the engineer has no ambiguity.
