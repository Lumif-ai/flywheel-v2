---
phase: 120-briefing-intelligence-surface
plan: "01"
subsystem: api
tags: [pydantic, briefing, market-patterns, pain-landscape, context-store, sqlalchemy, llm-narrative]

# Dependency graph
requires:
  - phase: 111-meeting-intelligence
    provides: "pain-landscape.md ContextEntry rows written by meeting-intelligence skill"
provides:
  - "PainPatternItem and MarketPatternsSection Pydantic models in briefing.py"
  - "market_patterns field always present on BriefingV2Response (never null/missing)"
  - "_build_market_patterns() async section builder in briefing_v2.py"
  - "top_pain_patterns injected into narrative facts dict (max 3 slugs)"
affects: [121-briefing-ui, frontend-briefing-page, meeting-prep-skill]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Section builder pattern: _build_X(session, tenant_id) -> dict, always returns safe default on exception"
    - "Python-side confidence sort (never SQL alphabetical) for high/medium/low severity ordering"
    - "default_factory=MarketPatternsSection guarantees always-present field in API response"

key-files:
  created: []
  modified:
    - backend/src/flywheel/api/briefing.py
    - backend/src/flywheel/services/briefing_v2.py

key-decisions:
  - "market_patterns uses default_factory=MarketPatternsSection (not Optional/None) — guarantees field is always present for frontend type contract"
  - "Confidence sorting done in Python not SQL (alphabetical order: 'high' < 'low' < 'medium' is wrong for severity)"
  - "Only pain: prefix entries returned (detail.like('pain: %')) — cluster entries excluded"
  - "top_pain_patterns limited to 3 slugs max in narrative facts to avoid LLM timeout (5s circuit breaker)"
  - "detail.like('pain: %') filter distinguishes pain entries from cluster entries in pain-landscape.md"

patterns-established:
  - "Section builders follow _build_X(session, tenant_id) pattern: always return safe default dict on exception, never raise"
  - "Narrative enrichment: build data sections before _generate_narrative() so facts can be injected"

# Metrics
duration: 18min
completed: 2026-04-13
---

# Phase 120 Plan 01: Briefing Intelligence Surface — Market Patterns Backend Summary

**pain-landscape.md context entries surfaced in briefing API via _build_market_patterns() with confidence-sorted Pydantic response and narrative injection**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-04-13T16:21:00Z
- **Completed:** 2026-04-13T16:39:21Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `PainPatternItem` and `MarketPatternsSection` Pydantic models to `briefing.py`, with `market_patterns` field on `BriefingV2Response` using `default_factory` to guarantee it is never missing or null in the API response
- Added `_build_market_patterns()` async section builder that queries pain-landscape.md ContextEntries, filters to pain-only entries (excluding clusters), and sorts by confidence severity in Python (high > medium > low)
- Wired market patterns into `assemble_briefing_v2()` before narrative generation, passing `top_pain_patterns` (max 3 slugs) into the narrative facts dict so Claude Haiku can reference top pains in the morning brief

## Task Commits

Per-plan strategy — one commit covers all tasks:

1. **Task 1: Pydantic models (PainPatternItem, MarketPatternsSection, BriefingV2Response.market_patterns)** — included in `268de3c`
2. **Task 2: _build_market_patterns(), assemble_briefing_v2() wiring, narrative enrichment** — included in `268de3c`

**Plan commit:** `268de3c` feat(120-01): add market_patterns intelligence to briefing backend

## Files Created/Modified

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/briefing.py` — Added `PainPatternItem`, `MarketPatternsSection` models; `Field` import; `market_patterns` field with `default_factory` on `BriefingV2Response`
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/briefing_v2.py` — Added `CONFIDENCE_ORDER` constant, `_build_market_patterns()` function, wired call in `assemble_briefing_v2()`, extended `_generate_narrative()` with `market_patterns` param and `top_pain_patterns` facts injection, extended system prompt

## Decisions Made

- `market_patterns` uses `default_factory=MarketPatternsSection` (not `Optional[MarketPatternsSection] = None`) — guarantees the field is always present in the API response, so the frontend never receives a missing field error regardless of whether synthesis has run
- Confidence sorting is done in Python after fetching from DB — SQL alphabetical ordering (`high < low < medium`) is wrong for severity; Python sort with `CONFIDENCE_ORDER = {"high": 2, "medium": 1, "low": 0}` gives correct descending severity
- `detail.like("pain: %")` filter ensures only pain entries are returned — cluster entries (written with `"cluster: "` prefix by meeting-intelligence) are excluded from the patterns list
- `top_pain_patterns` capped at 3 slugs (not full content) in narrative facts — the existing `asyncio.wait_for(..., timeout=5.0)` circuit breaker is tight and full content would risk timeouts

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. The `python` command was not found in shell (macOS has `python3` only at base, but venv has both). Switched to `source .venv/bin/activate && python` for verification commands. No code changes required.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Backend endpoint now returns `market_patterns` field on every `/briefing/v2` response
- Frontend (Phase 120 Plan 02 or 03) can render the `MarketPatternsSection` without any backend changes
- When synthesis has not run for a tenant: `{"patterns": [], "total_count": 0}` (safe empty state)
- When synthesis has run: patterns list contains pain slugs sorted high > medium > low confidence

---
*Phase: 120-briefing-intelligence-surface*
*Completed: 2026-04-13*
