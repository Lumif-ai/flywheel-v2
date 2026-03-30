---
phase: 70-voice-profile-overhaul
plan: 03
subsystem: api
tags: [voice-profile, email-drafting, llm-prompts, anthropic]

# Dependency graph
requires:
  - phase: 70-01
    provides: "6 new nullable columns on EmailVoiceProfile (formality_level, greeting_style, question_style, paragraph_pattern, emoji_usage, avg_sentences)"
provides:
  - "Draft system prompt using all 10 voice profile fields for authentically-voiced replies"
  - "Voice updater capable of learning and persisting all 10 fields from edit diffs"
  - "NULL-safe fallbacks via DEFAULT_VOICE_STUB for existing profiles missing new fields"
affects: [70-voice-profile-overhaul]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "10-field voice profile with DEFAULT_VOICE_STUB fallbacks"
    - "Running average merge for numeric fields (avg_length, avg_sentences)"
    - "Direct replacement merge for categorical fields (formality, greeting, question, paragraph, emoji)"

key-files:
  created: []
  modified:
    - "backend/src/flywheel/engines/email_drafter.py"
    - "backend/src/flywheel/engines/email_voice_updater.py"

key-decisions:
  - "Used direct replacement merge for 5 categorical fields (same pattern as tone/sign_off)"
  - "Used running average merge for avg_sentences (same pattern as avg_length)"
  - "Updated Haiku references to 'voice learning model' to reflect Phase 69 configurable models"

patterns-established:
  - "10-field voice profile: tone, avg_length, sign_off, phrases, formality_level, greeting_style, question_style, paragraph_pattern, emoji_usage, avg_sentences"

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 70 Plan 03: Engine Integration Summary

**Expanded draft system prompt and voice updater to use all 10 voice profile fields with NULL-safe fallbacks**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T00:01:14Z
- **Completed:** 2026-03-30T00:04:07Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Draft system prompt now includes formality, greeting style, paragraph pattern, question style, emoji usage, and sentence count -- producing visibly different drafts for casual vs formal profiles
- Voice updater can detect and persist changes to any of the 10 fields from user edit diffs
- Existing profiles with NULL new fields fall back to sensible defaults via DEFAULT_VOICE_STUB
- Updated stale "Haiku" references to "voice learning model" reflecting Phase 69 model configurability

## Task Commits

Single plan-level commit (per-plan strategy):

1. **Task 1: Expand DEFAULT_VOICE_STUB, _load_voice_profile, DRAFT_SYSTEM_PROMPT, _build_draft_prompt** - `bcb8051` (feat)
2. **Task 2: Expand voice updater prompt, merge logic, and UPDATE statement** - `bcb8051` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/email_drafter.py` - Added 6 new fields to DEFAULT_VOICE_STUB, _load_voice_profile return dict, DRAFT_SYSTEM_PROMPT, and _build_draft_prompt format call
- `backend/src/flywheel/engines/email_voice_updater.py` - Added 6 new fields to _UPDATE_VOICE_SYSTEM prompt, current_profile_json, merge logic (5 direct + 1 running avg), and UPDATE .values()

## Decisions Made
- Used direct replacement merge for formality_level, greeting_style, question_style, paragraph_pattern, emoji_usage (same pattern as tone/sign_off -- last edit wins)
- Used running average merge for avg_sentences (same pattern as avg_length -- smooths over time)
- Replaced "Haiku" references with "voice learning model" since Phase 69 made the model configurable per tenant

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both engines now consume all 10 voice profile fields from Phase 70-01 schema
- Ready for Phase 70-02 (voice profile init) if not already done, or Phase 70-04 (testing/verification)
- No regressions to existing 4-field behavior -- all new fields have fallback defaults

---
*Phase: 70-voice-profile-overhaul*
*Completed: 2026-03-30*
