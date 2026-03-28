---
phase: 62-meeting-surfaces-and-relationship-enrichment
plan: 03
subsystem: api
tags: [relationships, meetings, context-entries, intel, crm, timeline]

# Dependency graph
requires:
  - phase: 62-01
    provides: Meeting model with account_id linkage and meeting_processor_web CONTEXT_FILE_MAP
  - phase: 61
    provides: ContextEntry rows written by write_context_entries() with INTEL_FILES file names
  - phase: 57
    provides: GET /relationships/{id} endpoint with IntelligenceTab and TimelineTab frontend
provides:
  - Meeting rows merged into relationship detail timeline (title, tldr, type badge, attendee count)
  - ContextEntry intel rows (competitive-intel, pain-points, icp-profiles, insights, action-items, product-feedback) surfaced in intel dict
  - Existing account.intel JSONB values preserved — meeting intel fills gaps only
affects:
  - phase 57 frontend (RelationshipDetail TimelineTab and IntelligenceTab now receive enriched data)
  - phase 62-04 (any further relationship surface work)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INTEL_FILES constant: module-level list of ContextEntry file_name values from CONTEXT_FILE_MAP — single source of truth for which meeting-sourced intel files belong in IntelligenceTab"
    - "Gap-fill merge pattern: existing account.intel takes precedence; intel dict only gains keys that are missing or empty"
    - "Timeline merge pattern: ContextEntry rows + Meeting rows combined into one list, sorted by date desc, capped at 20"

key-files:
  created: []
  modified:
    - backend/src/flywheel/api/relationships.py

key-decisions:
  - "62-03 execution: Meeting rows serialized manually (not via _serialize_timeline_item) — set direction='bidirectional' directly since _derive_direction already handles meeting: prefix but is not called here"
  - "62-03 execution: INTEL_FILES excludes 'contacts' — contact data surfaces via AccountContact/PeopleTab, not IntelligenceTab"
  - "62-03 execution: intel gap-fill keyed on file_name.replace('-', '_') — matches lookupValue() two-pass scan pattern in frontend (pain_points matches 'pain' case-insensitive scan)"
  - "62-03 execution: attendees list is JSONB dict/list — len(attendees_list) gives attendee count for contact_name field"

patterns-established:
  - "Timeline merge: fetch ContextEntry rows (limit 10) + Meeting rows (limit 20), combine, sort by date desc, cap at 20"
  - "Intel gap-fill: dict(account.intel or {}), then for each ContextEntry only set if key absent or falsy"

# Metrics
duration: 2min
completed: 2026-03-28
---

# Phase 62 Plan 03: Meeting Surfaces - Relationship Enrichment Summary

**Meeting rows and ContextEntry intel from Phase 61 processing now surface in GET /relationships/{id} — timeline shows meeting title/tldr/type/attendees, intel dict gains pain-points/competitive-intel/insights/action-items from processed meetings**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-28T05:37:40Z
- **Completed:** 2026-03-28T05:39:05Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Meeting model imported into relationships.py; INTEL_FILES constant defined at module level listing all 6 IntelligenceTab-relevant ContextEntry file names
- Meeting rows queried per account, serialized with title+tldr display_content, source=meeting:{type}, direction=bidirectional, attendee count, merged into combined timeline sorted by date desc, capped at 20
- ContextEntry intel rows (competitive-intel, pain-points, icp-profiles, insights, action-items, product-feedback) queried and merged into intel dict — existing account.intel JSONB values preserved, meeting intel fills gaps only

## Task Commits

Plan batch commit (per-plan strategy):

1. **Tasks 1+2: Meeting timeline + ContextEntry intel enrichment** - `900bec2` (feat)

## Files Created/Modified

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/relationships.py` - Added Meeting import, INTEL_FILES constant, meeting timeline query+serialization, ContextEntry intel query+gap-fill merge, enriched intel return

## Decisions Made

- Meeting rows serialized as inline dicts (not via `_serialize_timeline_item`) because the Meeting ORM model doesn't share the ContextEntry interface — direction set directly as "bidirectional"
- `INTEL_FILES` excludes "contacts" — contact data already surfaces via AccountContact rows in PeopleTab; adding it to intel dict would duplicate and confuse IntelligenceTab display
- Gap-fill merge uses `file_name.replace("-", "_")` key transformation so keys like `pain_points` align with the two-pass `lookupValue()` scan in the frontend IntelligenceTab
- `attendees` field on Meeting model is JSONB (list or dict); `len(m.attendees or [])` gives attendee count safely

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 62 Plan 03 complete. The relationship detail endpoint now returns enriched timeline (meetings + ContextEntry activity) and enriched intel (account.intel merged with meeting-extracted intelligence).
- Frontend TimelineTab and IntelligenceTab in Phase 57 already render these shapes without modification.
- Ready for Phase 62 Plan 04 (any remaining meeting surfaces work).

---
*Phase: 62-meeting-surfaces-and-relationship-enrichment*
*Completed: 2026-03-28*
