# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v12.0 Library Redesign

## Current Position

Milestone: v12.0 Library Redesign
Phase: 104.2 of 104.2 (Skill Input Schema Validation)
Plan: 2 of 2 complete
Status: Phase Complete
Last activity: 2026-04-10 — Plan 02 complete (MCP layer input_data support)

Progress: [██████████] 100% (2/2 plans in Phase 104.2)

## Performance Metrics

**Previous milestones:**
- v1.0: 6 core phases + 3 patches
- v2.0: 4 phases, 9 plans
- v2.1: 5 phases, 16 plans
- v3.0: 5 phases, 13 plans
- v4.0: 4 phases, 13 plans
- v5.0: 1 phase, 7 plans
- v6.0: 1 phase, 3 plans
- v7.0: 7 phases, 13 plans
- v8.0: 7 phases, 14 plans
- v9.0: 8 phases, 25 plans
- v10.0: 5 phases, 7 plans
- v11.0: 5 phases, 10 plans

## Accumulated Context

### Decisions

All v1.0-v11.0 decisions archived in PROJECT.md Key Decisions table and previous STATE.md snapshots.

v12.0 design decisions (from design brief):
- Three filtering axes: type tabs (automatic), company dropdown (automatic), tag pills (user-defined escape hatch)
- Flat time-grouped list, not company-grouped sections (Norman: three-level nesting causes cognitive overload)
- Fix titles at write time (skills generate readable titles) + migration for existing bad titles
- Fix dedup at write time (same title + type + account within 1 hour = update) + migration for existing dupes
- Account resolution Option C: skills create Account first, pass both account_id + company_name
- Tag validation: max 20/doc, 200 unique/tenant, 50 chars, lowercase alphanumeric+hyphens
- PgBouncer DDL constraint: each migration statement via SQL Editor, not Alembic transactions
- Backend must complete before frontend (API dependency)
- Skill ecosystem updates are last (backward-compatible params mean existing skills keep working)
- [Phase 104.2]: input_data as JSON string in MCP tool signature for lean tool parameters
- [Phase 104.2]: Hardcoded MCP-side validation removed in favor of server-side schema validation

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

### Roadmap Evolution

- v12.0 roadmap created: Phases 101-104
- Phase 104.1 inserted after Phase 104: Legacy Model Cleanup — rewire 9 backend files from Account/AccountContact/OutreachActivity to PipelineEntry/Contact/Activity (URGENT)
- 104.1-02: outreach.py and timeline.py confirmed dead (no frontend callers), deleted entirely (735 lines removed)
- 104.1-02: Dead frontend accounts/ components noted for future cleanup (not in scope)
- 104.1-01: Used TIMESTAMP(timezone=True) for ai_summary_updated_at to match existing PipelineEntry column convention
- 104.1-03: Reply signal uses direction=inbound + status=completed (Activity has no 'replied' status); pipeline partition: retired_at IS NULL AND stage NOT IN ('identified')
- 104.1-05: Renamed auto_link_meeting_to_account -> auto_link_meeting_to_pipeline_entry; meetings.py now sets pipeline_entry_id (not account_id) when auto-linking
- 104.1-04: Graduate endpoint sets stage='qualified' instead of graduated_at=now; partition predicate: retired_at IS NULL AND stage NOT IN ('identified'); response models: entity_type/stage/last_activity_at replace entity_level/relationship_status/last_interaction_at
- Phase 104.2 inserted after Phase 104: Skill Input Schema Validation — two-step skill invocation with server-side input validation, repurpose parameters JSONB for input schemas (INSERTED)
- 104.2-01: Used lightweight inline JSON schema validator instead of jsonschema library (pyproject.toml protected); input_data serialized as JSON prefix to input_text for backward compatibility
- 104.2-02: input_data as JSON string in MCP tool signature; hardcoded meeting-processor UUID validation removed; input_requirements displayed in fetch_skills

## Session Continuity

Last session: 2026-04-10
Stopped at: Completed 104.2-02-PLAN.md (MCP layer input_data support) — Phase 104.2 complete
Resume file: None
