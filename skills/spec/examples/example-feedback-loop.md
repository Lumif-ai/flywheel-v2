# Example: The Full Feedback Loop — Spec → Execution → Gaps → Spec Update

This example demonstrates the living document cycle. A spec is written,
execution begins, the agent discovers ambiguities, logs them to SPEC-GAPS.md,
and the spec skill resolves them back into the spec.

---

## Phase 1: Initial Spec (abbreviated)

```markdown
# Notification System — Specification

## Core Value
Users receive timely, relevant notifications about events that matter to them.

## Requirements

### Must Have
- **NOTIF-01**: System sends notifications when events occur
  - **Acceptance Criteria:**
    - [ ] Notification sent within 5 seconds of triggering event
    - [ ] Events: new comment on user's post, mention in comment, team invite,
          document shared with user
    - [ ] Notification includes: event type, actor name, content preview, link to source

- **NOTIF-02**: User can view notification history
  - **Acceptance Criteria:**
    - [ ] Bell icon in header shows unread count (badge)
    - [ ] Dropdown shows last 20 notifications, newest first
    - [ ] Unread notifications visually distinct from read
    - [ ] Clicking notification marks as read and navigates to source
    - [ ] "Mark all as read" button at top of dropdown

- **NOTIF-03**: User can configure notification preferences
  - **Acceptance Criteria:**
    - [ ] Per-event-type toggles: on/off
    - [ ] Changes take effect immediately
    - [ ] Default: all notifications on

## Edge Cases & Error States
| Scenario | Expected Behavior |
|----------|-------------------|
| User mentioned in a deleted comment | No notification sent (check existence before sending) |
| User has notifications disabled for event type | No notification sent, no record created |
| 50 comments in 1 minute on user's post | Batch into single notification: "12 new comments on your post" |
```

---

## Phase 2: Execution Begins — Agent Hits Ambiguities

During GSD Phase 2 execution, the executor builds NOTIF-01 and NOTIF-02.
It hits several spec gaps and logs them:

### SPEC-GAPS.md (written by gsd-executor)

```markdown
# Specification Gaps — Discovered During Execution

## GAP-001 [OPEN]
- **Discovered by**: gsd-executor, Phase 2, Task 3 (notification delivery)
- **Timestamp**: 2026-03-20 14:23
- **Context**: Building the notification sending pipeline
- **Gap**: Spec says "notification sent within 5 seconds" but doesn't specify
  the delivery CHANNEL. Is this in-app only? Email too? Push notifications?
  The architecture is completely different for each.
- **Options**: (a) in-app only (b) in-app + email (c) in-app + email + push
- **Assumed**: (a) In-app only — built a database-backed notification store
  with real-time delivery via polling. No email integration.
- **Severity**: Critical — if email is expected, the entire delivery pipeline
  needs to be rebuilt with a queue, email templates, and delivery tracking.

## GAP-002 [OPEN]
- **Discovered by**: gsd-executor, Phase 2, Task 5 (notification dropdown)
- **Timestamp**: 2026-03-20 15:41
- **Context**: Building the notification list UI
- **Gap**: Spec says "content preview" in NOTIF-01 but doesn't define what
  "preview" means for different event types. A comment has text to preview.
  A team invite has no "content" — just the invite itself. A shared document
  has a title but no body text.
- **Options**:
  (a) Show first 80 chars of content (only works for comments)
  (b) Use event-specific templates:
      - Comment: "{actor} commented: {first 80 chars}"
      - Mention: "{actor} mentioned you in {document title}"
      - Invite: "{actor} invited you to {team name}"
      - Share: "{actor} shared {document title} with you"
- **Assumed**: (b) Event-specific templates — more work but better UX
- **Severity**: Minor — either approach works, but templates are harder to
  change if the user wanted something simpler.

## GAP-003 [OPEN]
- **Discovered by**: gsd-executor, Phase 2, Task 7 (batching logic)
- **Timestamp**: 2026-03-20 16:55
- **Context**: Implementing the "50 comments → batch notification" edge case
- **Gap**: Spec says batch "50 comments in 1 minute" into one notification.
  But what's the batching WINDOW? If comments come in at this rate:
  - t=0s: comment 1 → send notification immediately?
  - t=2s: comment 2 → update the notification? Send a new one?
  - t=5s: comment 3 → now batch?
  When does batching START and when does the batch CLOSE?
- **Options**:
  (a) No real-time batching — run a cron every 60 seconds, batch anything
      pending into digest notifications
  (b) Debounce: wait 30 seconds after first event, then send everything
      accumulated (real-time but slightly delayed)
  (c) Threshold: send immediately for first event, switch to batching
      after 5 events in 60 seconds
- **Assumed**: (b) Debounce with 30-second window. First comment triggers
  a 30-second timer. When timer fires, send one notification summarizing
  all comments received. If no more comments, user waits max 30 seconds.
- **Severity**: Major — the UX difference between "instant notification for
  every comment" and "30-second delay on first comment" is significant.
  Users expecting real-time will think notifications are broken.

## GAP-004 [OPEN]
- **Discovered by**: gsd-executor, Phase 2, Task 8 (mark as read)
- **Timestamp**: 2026-03-20 17:30
- **Context**: Implementing "clicking notification marks as read"
- **Gap**: If user navigates to the source (e.g., opens the document) WITHOUT
  clicking the notification (typed the URL, used a bookmark, clicked a link
  in email), is the related notification automatically marked as read?
  Or does it stay unread until explicitly clicked in the notification dropdown?
- **Options**:
  (a) Only mark read when notification itself is clicked (simple, predictable)
  (b) Auto-mark read when user visits the source (smarter, but complex —
      need to track which notifications relate to which pages)
- **Assumed**: (a) Only on notification click — simpler, and users expect
  the badge to represent "things I haven't acknowledged" not "pages I
  haven't visited."
- **Severity**: Minor — either approach is reasonable. Auto-read is nicer
  UX but significantly more implementation complexity.
```

---

## Phase 3: Spec Review with Gaps (`/spec review --include-gaps`)

The user runs `/spec review --include-gaps` after Phase 2 execution.
The skill reads both the original spec AND SPEC-GAPS.md:

### Review Output

```
## Spec Review: Notification System (with execution gaps)

### Critical — Execution Gaps Requiring Decision

1. **[GAP-001] Notification delivery channel undefined.**
   Agent assumed in-app only. If email notifications are expected,
   the delivery pipeline needs to be completely rebuilt.
   → Decision needed: in-app only, or in-app + email?

### Major — Execution Gaps Requiring Decision

2. **[GAP-003] Batching window undefined.**
   Agent assumed 30-second debounce. This means the FIRST comment
   in a burst has a 30-second delay before the user is notified.
   Users expecting real-time will report "notifications don't work."
   → Decision needed: accept 30s delay, or use threshold approach
     (instant for first, batch after 5)?

### Confirmed — Agent's Assumptions Were Reasonable

3. **[GAP-002] Event-specific templates.** Agent's choice of per-event
   templates is correct. Confirm and close.

4. **[GAP-004] Mark-read only on click.** Agent's choice to only mark
   read on notification click (not page visit) is the simpler and
   more predictable UX. Confirm and close.

### Additional Review Findings (not from execution)

5. **[Completeness] No specification for notification DELETION.**
   Can users delete individual notifications? Clear all? Is there
   a retention period? After 6 months of usage, a user could have
   10,000+ notifications in the dropdown's "show more" list.
   Fix: Add retention policy (e.g., auto-delete after 90 days).

6. **[Non-functional] No specification for notification delivery
   reliability.** "Within 5 seconds" is a timing target but not
   a reliability target. What % of notifications must be delivered?
   If the system is under load, is it acceptable to drop notifications?
   Fix: Define SLA (e.g., 99.9% delivery within 5 seconds).
```

---

## Phase 4: User Resolves Gaps

**User responds:**

> "In-app only for now. Email in v2. The 30-second debounce is fine —
> the use case is comment threads, not chat. Confirm the templates
> and mark-as-read assumptions. For deletion, auto-delete after 90 days.
> Don't worry about SLA for v1."

---

## Phase 5: Spec Updated

The skill updates the original spec:

**NOTIF-01 updated:**
```markdown
- **NOTIF-01**: System sends IN-APP notifications when events occur
  - **Acceptance Criteria:**
    - [ ] Notification sent within 5 seconds of triggering event (in-app only, no email in v1)
    - [ ] ...
```

**Edge case updated:**
```markdown
| 50 comments in 1 minute on user's post | Debounce: 30-second window from first event. Batch all events in window into single notification: "12 new comments on your post" |
```

**New requirement added:**
```markdown
- **NOTIF-04**: Old notifications auto-cleaned
  - **Acceptance Criteria:**
    - [ ] Notifications older than 90 days automatically deleted
    - [ ] Deletion runs daily, off-peak hours
    - [ ] No user-facing notification deletion controls in v1
```

**Anti-requirement added:**
```markdown
- Email notifications — Reason: deferred to v2 (GAP-001 resolution)
```

**SPEC-GAPS.md updated:**
```markdown
## GAP-001 [RESOLVED]
- ...
- **Resolved**: 2026-03-20 — In-app only, email in v2
- **Spec Updated**: Yes — NOTIF-01 updated, anti-requirement added

## GAP-002 [RESOLVED]
- ...
- **Resolved**: 2026-03-20 — Templates confirmed
- **Spec Updated**: No — assumption was correct, no spec change needed

## GAP-003 [RESOLVED]
- ...
- **Resolved**: 2026-03-20 — 30-second debounce confirmed
- **Spec Updated**: Yes — edge case table updated with explicit batching window

## GAP-004 [RESOLVED]
- ...
- **Resolved**: 2026-03-20 — Click-to-read confirmed
- **Spec Updated**: No — assumption was correct, no spec change needed
```

---

## Why This Example Matters

This is the cycle that doesn't exist in any spec tool today:

1. **The spec was good** — it had requirements, acceptance criteria, edge cases.
   Traditional spec review would have approved it.

2. **Execution revealed what review missed.** GAP-001 (delivery channel) is
   obvious in hindsight but wasn't flagged by review because the reviewer —
   human or AI — operates at the same abstraction level as the spec writer.
   The executor operates at implementation level, where ambiguity becomes
   blocking.

3. **The gaps were captured, not lost.** Without SPEC-GAPS.md, these decisions
   would live in the executor's context window (lost on reset) or in a Slack
   message (unsearchable). Now they're structured, severity-rated, and
   traceable.

4. **Resolution was fast.** The user made 4 decisions in one sentence.
   No meeting, no follow-up thread, no "can you remind me what we decided."
   The gap format presented options, the user picked, the spec updated.

5. **Future phases benefit.** When Phase 3 begins (notification preferences),
   the executor reads the updated spec and RESOLVED gaps. It knows emails
   are v2, batching uses debounce, and templates are per-event-type. No
   re-discovery of decisions already made.
