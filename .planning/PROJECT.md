# Flywheel V2 — Email Copilot

## What This Is

An AI-powered email copilot built into Flywheel V2 that reads your Gmail inbox, scores each message using the platform's deep context store (meeting notes, company intel, project knowledge, entity relationships), drafts replies in your voice, and presents a review UI for approval before sending. The first action-oriented channel for Flywheel's knowledge-compounding engine.

## Core Value

Use accumulated work knowledge (meetings, companies, projects, relationships) to eliminate the cognitive load of email triage and response — the user IS the bottleneck, and this automates the bottleneck itself.

## Current Milestone: v1.0 Email Copilot

**Goal:** Ship a dogfooding-ready email copilot that syncs Gmail, scores emails using context store, drafts replies in the user's voice, and provides a review UI for approval.

**Target features:**
- Gmail read/sync via expanded OAuth scopes
- Email scoring using context store intelligence
- Draft reply generation with learned voice profile
- Review UI for approving/editing/dismissing drafts
- In-app alerts for critical emails
- Feedback loop from user actions to improve scoring/drafting

## Requirements

### Validated

<!-- Existing Flywheel V2 capabilities this builds on -->

- ✓ Gmail OAuth (send-only) — `services/google_gmail.py`
- ✓ Background sync loop pattern — `services/calendar_sync.py`
- ✓ Context store with full-text search + entity graph — `context_utils.py`
- ✓ Skill executor with async tool loop — `services/skill_executor.py`
- ✓ Email send dispatch — `services/email_dispatch.py`
- ✓ Tenant isolation via RLS — all tables
- ✓ AES-256-GCM credential encryption — `auth/encryption.py`

### Active

- [ ] Gmail read sync (expanded scopes, background polling)
- [ ] Email scoring using context store
- [ ] Draft reply generation with voice learning
- [ ] Review UI (scored threads + draft approvals)
- [ ] In-app critical email alerts
- [ ] Feedback loop (approvals/edits improve scoring + voice)

### Out of Scope

- Auto-send / YOLO mode — trust must be earned first, draft-only for v1
- Morning briefing UX — long-term vision, requires proven trust
- Slack DM notifications — defer to v2, in-app alerts first
- Multi-account Gmail — single account for v1
- Gmail push notifications (Pub/Sub) — polling is sufficient for MVP
- Unsubscribe automation — suggest only, don't act

## Context

**Existing architecture:** FastAPI + PostgreSQL (async, tenant-isolated, RLS), Supabase Storage, multi-provider OAuth (Google, Microsoft, Slack), skill-based execution (async tool loops with context weighting), context store (atomic facts + full-text search + entity graph).

**Key patterns to follow:**
- `calendar_sync.py` — background sync loop (5-min poll)
- `meeting-processor` skill — template for email processing skill
- `email_dispatch.py` — already sends via Gmail/Outlook/Resend

**Concept brief:** `.planning/CONCEPT-BRIEF-email-copilot.md` — full brainstorm output with advisory board analysis, data model, architecture, and phased plan.

**Key brainstorm decisions:**
- Extract context from emails + discard body; fetch on-demand via Gmail API
- Score at message level, display at thread level (highest score wins)
- Ship scoring + drafting together, with configurable draft visibility delay
- `draft_visibility_delay_days: 0` for internal, tunable for external
- Aggressive on escalation, conservative on suppression (false negative is 1000x worse)
- Voice learning from ~100 substantive sent emails (>3 sentences)

## Constraints

- **Stack**: FastAPI + PostgreSQL + SQLAlchemy 2.0 (async) — existing backend
- **Frontend**: React + Vite — existing frontend
- **Gmail API**: Rate limits apply — budget polling per user at scale
- **Privacy**: No permanent raw email body storage — extract context, fetch on-demand
- **Trust**: All replies are drafts for review — no auto-send in v1
- **Scoring bias**: Aggressive escalation, conservative suppression

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Extract + discard email body | Clean separation: scoring needs signals, drafting fetches on-demand. Minimizes PII liability | — Pending |
| Three-entity data model (Email, EmailScore, EmailDraft) | Torvalds napkin test — simple, decomplected, each entity has clear purpose | — Pending |
| Configurable draft visibility delay | Allows aggressive dogfooding (delay=0) while protecting external users (delay=7) | — Pending |
| Voice learning from sent mail | Pull last 200 sent, filter to ~100 substantive. Enough for patterns without over-fitting | — Pending |
| Thread-level display, message-level scoring | Matches human mental model — "this thread got important when Sarah replied" | — Pending |
| Poll every 5 min (not push) | Follows calendar_sync pattern. Gmail Pub/Sub is premature optimization for MVP | — Pending |

---
*Last updated: 2026-03-24 after milestone v1.0 initialization*
