# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-10)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v13.0 Skill Platform — Phase 105

## Current Position

Milestone: v13.0 Skill Platform
Phase: 105 of 109 (Foundation + Export Infrastructure)
Plan: 1 of 2 in current phase
Status: Executing
Last activity: 2026-04-10 — Completed 105-01 (foundation export infrastructure)

Progress: [█████░░░░░] 50%

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
- v12.0: 6 phases (4 + 2 inserted)

## Accumulated Context

### Decisions

All v1.0-v12.0 decisions archived in PROJECT.md Key Decisions table.

v13.0 Phase 105 Plan 01:
- WeasyPrint system deps in Dockerfile only -- no local uv sync required
- HTML sanitization at two points in export path (fragment wrapper + full-document body)
- asyncio.to_thread wraps both PDF and DOCX export

v13.0 pre-GSD context:
- Pre-GSD code exists for one-pager skill, export service, OnePagerRenderer — needs validation against research findings
- WeasyPrint NOT in pyproject.toml or Dockerfile — must fix before PDF export works
- export_as_pdf is sync — must wrap in asyncio.to_thread
- HTML sanitization gap in _wrap_fragment_as_document — XSS risk
- Anthropic SDK upgrade to >=0.93.0 needed for output_config structured outputs
- File upload backend ALREADY EXISTS (api/files.py, file_extraction.py, UploadedFile model)
- PII redaction belongs at export/share boundary, not pre-storage
- Archived pii-redactor script (560 lines) — port, don't rebuild
- No more hardcoded is_xyz branches in skill executor
- Legal doc advisor (Phase 107) ships MCP/CLI-first — user provides file path. Web file upload UI comes in Phase 108. No brainstorm needed — archived skill is v3.0 and mature. Phase 107 research defines the structured JSON schema.
- No phase reordering — 107 before 108 is correct

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

## Session Continuity

Last session: 2026-04-10
Stopped at: Completed 105-01-PLAN.md — ready for 105-02
Resume file: None
