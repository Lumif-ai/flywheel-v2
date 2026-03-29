---
phase: 69-model-configuration
plan: 01
subsystem: engines
tags: [anthropic, claude, model-config, tenant-settings, jsonb]

# Dependency graph
requires:
  - phase: 66.1-flywheel-stabilization
    provides: email scoring, drafting, and voice engines
provides:
  - Shared get_engine_model() helper for per-tenant model resolution
  - ENGINE_DEFAULTS dict with 5 engine keys defaulting to claude-sonnet-4-6
  - All email engines migrated from hardcoded constants to configurable models
affects: [70-voice-profile-v2, 71-context-extraction, 74-advanced-features]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-tenant engine model configuration via settings JSONB]

key-files:
  created:
    - backend/src/flywheel/engines/model_config.py
  modified:
    - backend/src/flywheel/engines/email_scorer.py
    - backend/src/flywheel/engines/email_drafter.py
    - backend/src/flywheel/engines/email_voice_updater.py
    - backend/src/flywheel/services/gmail_sync.py

key-decisions:
  - "All 5 engine defaults set to claude-sonnet-4-6 (upgrading scoring, voice_extraction, voice_learning from Haiku)"
  - "Model config stored in tenant.settings['email_engine_models'] JSONB path (no new table needed)"
  - "Non-Claude model names allowed but logged with warning"

patterns-established:
  - "get_engine_model(db, tenant_id, engine_key): standard way to resolve model for any engine"
  - "ENGINE_DEFAULTS as single source of truth for fallback models"

# Metrics
duration: 2min
completed: 2026-03-29
---

# Phase 69 Plan 01: Model Configuration Summary

**Shared get_engine_model() helper with per-tenant JSONB config, migrating 4 email engine files from hardcoded Haiku/Sonnet constants to configurable defaults**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-29T23:35:57Z
- **Completed:** 2026-03-29T23:38:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created model_config.py with ENGINE_DEFAULTS (5 keys) and async get_engine_model() helper
- Migrated email_scorer.py, email_drafter.py, email_voice_updater.py, and gmail_sync.py to use shared helper
- Upgraded default models from Haiku to Sonnet for scoring, voice_extraction, and voice_learning engines
- Zero hardcoded _HAIKU_MODEL or _SONNET_MODEL constants remain in email engine files

## Task Commits

Single per-plan commit:

1. **All tasks** - `c16e314` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/model_config.py` - New shared helper: get_engine_model() + ENGINE_DEFAULTS
- `backend/src/flywheel/engines/email_scorer.py` - Removed _HAIKU_MODEL, uses get_engine_model(db, tenant_id, "scoring")
- `backend/src/flywheel/engines/email_drafter.py` - Removed _SONNET_MODEL, uses get_engine_model(db, tenant_id, "drafting")
- `backend/src/flywheel/engines/email_voice_updater.py` - Removed _HAIKU_MODEL, uses get_engine_model(db, tenant_id, "voice_learning")
- `backend/src/flywheel/services/gmail_sync.py` - Removed _HAIKU_MODEL, voice_profile_init resolves model and passes to _extract_voice_profile

## Decisions Made
- All 5 engine defaults set to claude-sonnet-4-6 (intentional upgrade from Haiku per spec)
- Model config path: tenant.settings["email_engine_models"][engine_key] (reuses existing JSONB column)
- Non-Claude model names are allowed but logged with a warning (future-proofing)
- _extract_voice_profile receives model as parameter from voice_profile_init (not internal resolution)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- model_config.py is ready for use by Phase 71 (context extraction engine) via the "context_extraction" key
- Any future engine can import get_engine_model and resolve its model per-tenant
- Admin UI for model selection can write to tenant.settings["email_engine_models"] directly

---
*Phase: 69-model-configuration*
*Completed: 2026-03-29*
