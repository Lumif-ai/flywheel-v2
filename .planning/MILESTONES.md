# Milestones

## v1.0 — Email Copilot ✓

**Goal:** Ship a dogfooding-ready email copilot that syncs Gmail, scores emails using context store, drafts replies in the user's voice, and provides a review UI for approval.

**Started:** 2026-03-24
**Completed:** 2026-03-25
**Phases:** 1-6 (core) + 48, 49, 49.1 (patches)
**Last phase number:** 49.1

**Key deliverables:**
- Gmail read sync with expanded OAuth scopes
- 5-tier email scoring using context store intelligence
- Voice-learned draft reply generation (Sonnet)
- Scored inbox UI with virtual list + draft approval flow
- Critical email toast alerts
- Feedback flywheel (edit-to-learn voice updates, re-scoring)

---

## v2.0 — AI-Native CRM ✓

**Goal:** Founders never lose track of an account again — a single screen with all contacts, timeline, commitments, intel, and next actions, all auto-populated from skill runs.

**Started:** 2026-03-26
**Completed:** 2026-03-27
**Phases:** 50-53 (4 phases, 9 plans)
**Last phase number:** 53
**Stats:** 63 files changed, +7,866 lines

**Key deliverables:**
- CRM data model — accounts, contacts, outreach tables with RLS and company name normalization
- Seed CLI — 206 real accounts, 235 contacts, 81 outreach activities from GTM stack files
- Full REST API — accounts/contacts CRUD, outreach pipeline, unified timeline, pulse signals, auto-graduation
- Accounts page — searchable, filterable, sortable table with pagination at `/accounts`
- Account detail — 3-column deep-dive with contacts panel, chronological timeline, intel sidebar, action bar
- Pipeline page — prospect triage with fit score ranking and Graduate action
- Sidebar navigation — Accounts and Pipeline links integrated into app shell
- Pulse signals — revenue-gated signal cards on Briefing page linking to accounts

---
