# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-08)

**Core value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system
**Current focus:** v11.0 Briefing Page Redesign — Phase 99: Needs Attention and Team Activity Sections

## Current Position

Milestone: v11.0 Briefing Page Redesign
Phase: 99 of 100 (Needs Attention and Team Activity Sections)
Plan: 2 of 2 (complete)
Status: Complete
Last activity: 2026-04-08 — Plan 02 complete (TeamActivitySection with grouped feed and expand/collapse)

Progress: [██████████] 95%

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

## Accumulated Context

### Decisions

All v1.0-v9.0 decisions archived in PROJECT.md Key Decisions table.

v10.0 design decisions:
- Person-first grid as default view (company toggle secondary) — JTBD is always person-level for outreach
- Grid is command center (scan+filter+select), detail panel is editing surface (messages, fields, actions)
- Sequences are emergent (activities sorted by step_number), not configured (no sequence builder UI)
- AI-computed next_step derived from activity status + elapsed time (not manually maintained)
- Claude Code sends emails via Playwright, not in-app send buttons — grid is visibility, not execution
- No auto-send without approval — founder reviews and approves every step
- Post-query filtering for status/channel on latest activity (avoids lateral join complexity)
- compute_next_step as pure function outside PipelineService for testability
- SingleSelectFilter for all contact filters (backend accepts single-value params)
- AgGridReact key={mode} forces remount on mode switch for clean column/sort state
- Contact row click navigates to parent company profile (detail panel deferred to Phase 93)
- Hooks invalidate both ['contacts'] and ['contact-activities'] query keys for grid/panel sync
- Activity mutation success toast only on status changes to avoid noise
- Contact panel 480px width (wider than company panel 420px) for textarea editing comfort
- EditableField: click-to-edit with blur-save, pencil icon on hover
- Action buttons contextual to status: Approve for drafted, Skip for drafted/approved, Mark Replied for sent
- MCP outreach tools are ID-based (not name-based) for batch workflows: list returns IDs, create accepts IDs
- Skill protection: fail-closed boolean (protected=true default), frontmatter public flag inverted to protected in DB

v11.0 design decisions:
- /briefing/v2 is a new endpoint (not a breaking change to existing /briefing) — old endpoint stays until cleanup phase
- Narrative summary generated server-side via LLM (not streamed) to keep Phase 96 self-contained
- Chat panel navigates to /chat on submit (inline streaming deferred to future CHAT-F01)
- Phase 98 and Phase 99 are independently shippable from the same shell — parallel execution possible
- BriefingPageV2 uses 100dvh with overflow:hidden for independent column scrolling inside sidebar shell
- Right panel hidden on mobile via Tailwind hidden lg:flex (responsive breakpoint at 1024px)
- briefing_v2 flag defaults to true (active dev) — controlled via VITE_FEATURE_BRIEFING_V2 env var
- Time-of-day greeting (morning/afternoon/evening) in BriefingPageV2
- Cold start detection is client-side (all sections empty = show card), not a separate API flag
- Coral left-border accent on loaded narrative BrandedCard for visual warmth
- Suggested questions derived from live briefing data (meetings/replies/tasks) with sensible defaults
- Chat panel submit follows GlobalChatInput pattern: sendMessage + navigate('/chat')
- Reused existing briefing router with /v2 sub-path (not a separate router)
- Company resolution: joinedload on pipeline_entry and account to avoid N+1
- prep_status derived from skill_run_id OR ai_summary presence
- TodaySection: inline MeetingCard/PrepButton (not exported), NavLink for View Prep, useNavigate for Prep with chat prefill
- LLM narrative uses func.distinct for skill_name dedup in data gathering
- EmailDraft query uses tuple select pattern to avoid N+1 on Email join
- Team activity defaults to 24h lookback when last_visit is None (first-time users)
- TasksSection: local component state for checkbox optimism (not cache manipulation), two-step mutation chain for status transitions
- Client-side dismiss for reply/follow_up attention items via local Set state (no server persistence for v1)
- Sub-section type labels shown only when multiple attention types have items
- Cross-cache invalidation: draft mutations invalidate both email and briefing-v2 query keys
- Filter done/dismissed/deferred tasks from display rather than disabling checkboxes
- Cast TaskItem.status (string) to TaskStatus at call site for type-safe transition logic
- Activity items not clickable for v1 (navigation targets unclear per research)
- formatTimeAgo copied locally in TeamActivitySection (PulseSignals being removed in Phase 100)
- Groups default collapsed for scannable feed

### Pending Todos

- Title matching false positives in _filter_unprepped (requires meeting_id on SkillRun — deferred from 66.1)
- Private import coupling in flywheel_ritual.py (documented as tech debt)

### Blockers/Concerns

None active.

### Roadmap Evolution

- Phase 95 added: Skill IP Protection
- v11.0 roadmap created: Phases 96–100

## Session Continuity

Last session: 2026-04-08
Stopped at: Completed 099-02-PLAN.md (TeamActivitySection with grouped feed, Phase 99 complete)
Resume file: None
