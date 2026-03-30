# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v7.0 Email Voice & Intelligence Overhaul — Phase 75 Context Extraction Pipeline

## Current Position

Milestone: v7.0 Email Voice & Intelligence Overhaul
Phase: 74 complete, ready for Phase 75
Plan: —
Status: Phase 74 complete (verified)
Last activity: 2026-03-30 — Phase 74 executed and verified (2/2 plans)

Progress: [████████░░] 86%

## Performance Metrics

**Velocity (v6.0):**
- Phase 68: 3 plans, completed 2026-03-29

**Previous milestones:**
- v1.0: 6 core phases + 3 patches
- v2.0: 4 phases, 9 plans
- v2.1: 5 phases, 16 plans
- v3.0: 5 phases, 13 plans
- v4.0: 4 phases, 13 plans
- v5.0: 1 phase, 7 plans
- v6.0: 1 phase, 3 plans

## Accumulated Context

### Decisions

All v1.0-v6.0 decisions archived in milestone ROADMAP archives.

v7.0 decisions made:
- Model config stored in tenant.settings["email_engine_models"] JSONB path (no new table) — decided in 69-01
- All 5 engine defaults upgraded to claude-sonnet-4-6 (from Haiku for scoring/voice/learning) — decided in 69-01
- Voice profile expanded to 10 fields (6 new nullable columns with server_default, no backfill) — decided in 70-01
- Extraction uses 50 sent emails (up from 20), updater handles all 10 fields with running avg for avg_sentences — decided in 70-02/03

- [Phase 72]: Voice snapshot stored as {type: voice_snapshot} in context_used JSONB; regeneration merges overrides without mutating persistent profile
- [Phase 72]: Used existing DropdownMenu primitive (base-ui) for regenerate dropdown; VoiceAnnotation shows 5 badges collapsed, 10-field grid expanded
- [Phase 73]: Voice content formatted as markdown (not JSON) for direct MCP readability; confidence mapped from samples count (high>=20, medium>=5, low<5); catalog stays active on reset
- [Phase 74-01]: Detail tags use category:key format for deterministic dedup; source label is caller-provided; engine-sourced writes skip graph extraction; relationship signals stored in insights file
- [Phase 74-02]: Body truncated to 8000 chars for context window; snippet fallback < 50 chars, skip < 20 chars; per-item error isolation in writer integration

Pending decisions for v7.0 (from spec open questions):
- Whether context extraction cap (200/day) should be configurable per tenant or global
- Whether "Reset & Relearn" should clear incremental learning history

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-03-30
Stopped at: Phase 74 complete — ready for Phase 75 Context Extraction Pipeline
Resume file: None
