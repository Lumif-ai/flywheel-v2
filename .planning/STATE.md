# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** Conversations automatically become tracked commitments and executed deliverables -- the founder's daily operating system
**Current focus:** v23.0 In-Context Skill Execution

## Current Position

Milestone: v23.0 In-Context Skill Execution
Phase: 154 of 157 (Core MCP Tools — Routing + Context Warming)
Plan: 3 of 3 in current phase (COMPLETE)
Status: Phase 154 Complete
Last activity: 2026-04-21 -- Plan 154-03 complete (MCP tool wiring for route + preamble)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 135s
- Total execution time: 0.08 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 153 | 2 | 269s | 135s |

**Recent Trend:**
- Last 5 plans: 153-02 (170s), 153-03 (99s)
- Trend: Accelerating

*Updated after each plan completion*
| Phase 153 P01 | 490 | 2 tasks | 4 files |
| Phase 153 P03 | 99 | 2 tasks | 1 files |
| Phase 154 P01 | 78s | 2 tasks | 1 files |
| Phase 154 P02 | 1min | 1 tasks | 1 files |
| Phase 154 P03 | 73s | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v22.0 shipped: Skill Platform Consolidation complete (Phases 146-152.1). Skills served via MCP from Supabase. Local ~/.claude/skills/ mirror retired for broker module.
- v23.0 scope: In-Context Skill Execution replaces Project Primitive Platform (deferred). Eliminate server-side LLM spend for CLI/Desktop callers.
- [Phase 153]: Validate skill tools AFTER normalization (not raw prompts) to test what API serves
- [Phase 154]: Used row_number() window function for top-5 entries per file in single query for preamble endpoint

### Prior Milestone Context

v22.0 residual: Phase 152 Task 3 (telemetry gate + GitHub PR) still PENDING but non-blocking for v23.0. Phase 151 SC5 SLO AMEND approved (cold p99 3500ms ngrok / 1500ms same-region / 50ms warm).

### Research Flags

- Phase 153: Per-skill tool-name audit and parameter transformation mapping needed (C1 pitfall -- naive regex breaks parameter schemas)
- Phase 157: Desktop auth flow for users who never installed CLI needs validation

### Pending Todos

None yet.

### Blockers/Concerns

- C1 pitfall: Server-side tool names have different parameter schemas than MCP equivalents. Per-skill audit mandatory, not bulk regex.
- C2 pitfall: protected=True and cc_executable must be orthogonal (decoupled).
- C3 pitfall: Strict ordering for flywheel_run_skill redirect -- normalize -> verify -> dual-path -> redirect (never remove).
- C4 pitfall: Unbounded context reads can blow context window. Hard 8k/16k char caps needed on all context/data tools.

## Session Continuity

Last session: 2026-04-21
Stopped at: Completed 154-03-PLAN.md. Phase 154 complete (all 3 plans done).
Resume file: None
