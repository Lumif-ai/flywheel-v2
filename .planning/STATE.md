## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-24 — Milestone v1.0 Email Copilot started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Use accumulated work knowledge to eliminate the cognitive load of email triage and response
**Current focus:** Defining requirements for Email Copilot v1.0

## Accumulated Context

- Concept brief completed via brainstorm with 15-advisor board (.planning/CONCEPT-BRIEF-email-copilot.md)
- Two achievable moat powers identified: switching costs + cornered resource (context store)
- ~70% of infrastructure already exists (Gmail OAuth, sync pattern, context store, skill executor, email dispatch)
- Data model: Email (pointer) → EmailScore (intelligence) → EmailDraft (action) + EmailVoiceProfile
- Architecture: poll Gmail every 5 min → extract context → score → route (notify/draft/file/archive) → review UI → send

## Todos

(None yet)
