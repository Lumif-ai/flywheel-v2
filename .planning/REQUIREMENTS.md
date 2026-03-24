# Requirements: Flywheel V2 — Email Copilot

**Defined:** 2026-03-24
**Core Value:** Use accumulated work knowledge to eliminate the cognitive load of email triage and response

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Gmail Integration

- [ ] **GMAIL-01**: System can initiate OAuth flow with gmail.readonly + gmail.modify + gmail.send scopes (separate from existing send-only integration)
- [ ] **GMAIL-02**: System stores Gmail read credentials as a separate Integration row (does not modify existing gmail send integration)
- [ ] **GMAIL-03**: System polls Gmail every 5 minutes via background worker for new messages using incremental sync (historyId)
- [ ] **GMAIL-04**: System falls back to full sync when historyId expires or returns 404
- [ ] **GMAIL-05**: System imports user's last 200 sent emails and filters to ~100 substantive (>3 sentences) for voice profile extraction
- [ ] **GMAIL-06**: System groups synced emails by Gmail thread_id for thread-level display
- [ ] **GMAIL-07**: System fetches full email body on-demand via Gmail API when user opens thread or drafting is triggered (no permanent body storage)
- [ ] **GMAIL-08**: System handles concurrent polling for multiple users with asyncio.gather and per-integration timeouts

### Email Scoring

- [ ] **SCORE-01**: System scores each email message on a 1-5 priority scale (5=critical, 1=noise)
- [ ] **SCORE-02**: System cross-references sender email against context_entities (people, companies) to inform scoring
- [ ] **SCORE-03**: System cross-references email subject/snippet against context_entries via full-text search to detect topic relevance
- [ ] **SCORE-04**: System classifies emails into categories (meeting_followup, deal_related, action_required, informational, marketing, personal)
- [ ] **SCORE-05**: System routes scored emails to suggested actions (notify, draft_reply, file, archive) based on priority
- [ ] **SCORE-06**: System provides scoring reasoning and context references for each score (transparency)
- [ ] **SCORE-07**: System displays thread-level priority as the highest unhandled message score in the thread
- [ ] **SCORE-08**: System re-scores threads when new messages arrive
- [ ] **SCORE-09**: System biases toward aggressive escalation over conservative suppression (false negative is 1000x worse than false positive)

### Voice Learning

- [ ] **VOICE-01**: System extracts voice profile from substantive sent emails (tone, avg length, sign-off, characteristic phrases)
- [ ] **VOICE-02**: System filters out auto-replies, OOO messages, and calendar acceptances before voice profile extraction
- [ ] **VOICE-03**: System stores voice profile per user (EmailVoiceProfile model)
- [ ] **VOICE-04**: System updates voice profile when user edits drafts before sending (learns from corrections)

### Draft Generation

- [ ] **DRAFT-01**: System generates draft replies for emails scored as important (priority 3-4) using assembled context + voice profile
- [ ] **DRAFT-02**: System fetches email body on-demand from Gmail API for draft generation (not from stored data)
- [ ] **DRAFT-03**: System assembles relevant context from context store (meeting notes, company intel, entity relationships) for each draft
- [ ] **DRAFT-04**: System applies voice profile (tone, length, sign-off, phrases) to generated drafts
- [ ] **DRAFT-05**: System stores drafts with configurable visibility delay (draft_visibility_delay_days: 0 for internal, tunable for external)
- [ ] **DRAFT-06**: User can approve a draft to send it (one-tap send via existing email dispatch)
- [ ] **DRAFT-07**: User can edit a draft before approving (edits feed back to voice learning)
- [ ] **DRAFT-08**: User can dismiss a draft (dismissal feeds back to scoring refinement)

### Review UI

- [ ] **UI-01**: User can view scored email threads in a prioritized list (grouped by priority tier)
- [ ] **UI-02**: User can view thread detail with individual message scores, reasoning, and context references
- [ ] **UI-03**: User can approve, edit, or dismiss draft replies from the thread detail view
- [ ] **UI-04**: User receives in-app alert for critical emails (priority 5)
- [ ] **UI-05**: User can view daily digest of low-priority emails that were auto-filed/archived
- [ ] **UI-06**: Thread list uses virtual scrolling for performance at scale

### Data Model

- [ ] **DATA-01**: Email model stores Gmail pointer (message_id, thread_id, sender, subject, received_at, labels) — no body storage
- [ ] **DATA-02**: EmailScore model stores priority, category, suggested_action, reasoning, context_refs, sender_entity_id
- [ ] **DATA-03**: EmailDraft model stores draft_body, status, context_used, user_edits, visible_after
- [ ] **DATA-04**: EmailVoiceProfile model stores tone, avg_length, sign_off, phrases, samples_analyzed
- [ ] **DATA-05**: All models are tenant-isolated via RLS (consistent with existing architecture)
- [ ] **DATA-06**: Alembic migration creates all new tables with proper indexes and constraints

### Feedback Loop

- [ ] **FEED-01**: System refines scoring based on user approve/dismiss patterns over time
- [ ] **FEED-02**: System updates voice profile from user edits to drafts (diff analysis)
- [ ] **FEED-03**: System re-scores threads when new messages arrive in existing threads

### API

- [ ] **API-01**: GET endpoint to list scored email threads (with pagination, filtering by priority)
- [ ] **API-02**: GET endpoint to get thread detail (messages, scores, drafts, context refs)
- [ ] **API-03**: POST endpoint to approve a draft (triggers send via email dispatch)
- [ ] **API-04**: POST endpoint to dismiss a draft
- [ ] **API-05**: PUT endpoint to edit a draft before approval
- [ ] **API-06**: GET endpoint to get daily digest summary
- [ ] **API-07**: POST endpoint to trigger manual Gmail sync

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Notifications

- **NOTIF-01**: User receives Slack DM for critical emails
- **NOTIF-02**: User can configure notification preferences (which priority levels trigger alerts)

### CLI

- **CLI-01**: User can check email status from terminal (flywheel email status)
- **CLI-02**: User can approve/dismiss drafts from terminal (flywheel email approve <id>)

### Advanced

- **ADV-01**: User can manage multiple Gmail accounts
- **ADV-02**: System uses Gmail push notifications (Pub/Sub) instead of polling for real-time sync
- **ADV-03**: Morning briefing mode (conversational summary instead of thread list)
- **ADV-04**: System can auto-unsubscribe from marketing emails on user confirmation

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-send / YOLO mode | Trust must be earned first; all replies are drafts for review in v1 |
| Morning briefing UX | Long-term vision requiring proven trust and usage patterns |
| Email body permanent storage | Privacy risk; extract context, fetch on-demand |
| Gmail push notifications (Pub/Sub) | Premature optimization; polling is sufficient for MVP; requires GCP infrastructure |
| Multi-account Gmail | Single account sufficient for dogfooding; adds OAuth complexity |
| Outlook/Microsoft email support | Gmail-first; Outlook can follow same patterns later |
| Auto-unsubscribe actions | Suggest only, don't act — too risky for v1 |
| Claude Code skill version | Platform feature is architecturally superior (always-on, direct DB, rich UI) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| DATA-06 | Phase 1 | Pending |
| GMAIL-01 | Phase 1 | Pending |
| GMAIL-02 | Phase 1 | Pending |
| GMAIL-03 | Phase 2 | Pending |
| GMAIL-04 | Phase 2 | Pending |
| GMAIL-05 | Phase 2 | Pending |
| GMAIL-06 | Phase 2 | Pending |
| GMAIL-07 | Phase 2 | Pending |
| GMAIL-08 | Phase 2 | Pending |
| VOICE-01 | Phase 2 | Pending |
| VOICE-02 | Phase 2 | Pending |
| VOICE-03 | Phase 2 | Pending |
| SCORE-01 | Phase 3 | Pending |
| SCORE-02 | Phase 3 | Pending |
| SCORE-03 | Phase 3 | Pending |
| SCORE-04 | Phase 3 | Pending |
| SCORE-05 | Phase 3 | Pending |
| SCORE-06 | Phase 3 | Pending |
| SCORE-07 | Phase 3 | Pending |
| SCORE-08 | Phase 3 | Pending |
| SCORE-09 | Phase 3 | Pending |
| DRAFT-01 | Phase 4 | Pending |
| DRAFT-02 | Phase 4 | Pending |
| DRAFT-03 | Phase 4 | Pending |
| DRAFT-04 | Phase 4 | Pending |
| DRAFT-05 | Phase 4 | Pending |
| DRAFT-06 | Phase 4 | Pending |
| DRAFT-07 | Phase 4 | Pending |
| DRAFT-08 | Phase 4 | Pending |
| API-01 | Phase 5 | Pending |
| API-02 | Phase 5 | Pending |
| API-03 | Phase 5 | Pending |
| API-04 | Phase 5 | Pending |
| API-05 | Phase 5 | Pending |
| API-06 | Phase 5 | Pending |
| API-07 | Phase 5 | Pending |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 5 | Pending |
| UI-05 | Phase 5 | Pending |
| UI-06 | Phase 5 | Pending |
| VOICE-04 | Phase 6 | Pending |
| FEED-01 | Phase 6 | Pending |
| FEED-02 | Phase 6 | Pending |
| FEED-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after initial definition*
