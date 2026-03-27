---
phase: 58-unified-company-intelligence-engine
plan: 01
subsystem: api
tags: [anthropic, company-intel, skill-executor, document-upload, web-research, gap-aware]

# Dependency graph
requires:
  - phase: 57-relationship-surfaces
    provides: relationship detail page and AskPanel built on company intel context entries
provides:
  - _execute_company_intel accepts DOCUMENT_FILE:{uuid} input, skips crawl, fetches text from DB
  - _execute_company_intel accepts SUPPLEMENTARY_DOCS with multiple DOCUMENT_FILE refs
  - enrich_with_web_research is gap-aware — skips already-populated profile categories
  - _get_existing_profile_keys async helper in company_intel.py
affects: [58-02, 58-03, company-intel onboarding flow, document upload processing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DOCUMENT_FILE_PREFIX constant for discriminating document vs URL inputs at function entry"
    - "_get_existing_profile_keys reads ContextEntry.file_name to determine already-populated categories before LLM enrichment"
    - "Gap-aware prompt engineering: (SKIP - already have) prefix on search items + reduced max_uses"

key-files:
  created: []
  modified:
    - backend/src/flywheel/services/skill_executor.py
    - backend/src/flywheel/engines/company_intel.py

key-decisions:
  - "DOCUMENT_FILE_PREFIX constant defined inside _execute_company_intel (not module-level) to keep it co-located with its only use"
  - "is_document discriminator drives both source_label ('document-upload' vs 'website-crawl') and companies cache upsert skip"
  - "Supplementary doc fetch failures are logged as warnings (not errors) — partial data still better than abort"
  - "max_uses reduced from 5 to 3 when existing_profile_keys count exceeds half of total profile files (3 out of 5)"
  - "SKIP prefix applied per file_name to search items: leadership.md, company-details.md, competitive-intel.md, tech-stack.md"

patterns-established:
  - "Pattern: Input format discriminator at function entry — parse lines, detect prefix, set is_document flag, then branch"
  - "Pattern: Gap-aware enrichment — read existing DB state before LLM call to skip redundant work"

# Metrics
duration: 18min
completed: 2026-03-27
---

# Phase 58 Plan 01: Document Input and Gap-Aware Enrichment Summary

**DOCUMENT_FILE:{uuid} input path (skips crawl), SUPPLEMENTARY_DOCS merge, and gap-aware `enrich_with_web_research` that reads existing profile before researching**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-27T00:00:00Z
- **Completed:** 2026-03-27T00:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `_execute_company_intel` now handles three input formats: `DOCUMENT_FILE:{uuid}` (skips crawl, fetches `extracted_text` from DB with RLS), URL + `SUPPLEMENTARY_DOCS` (crawls URL, appends document texts), and plain URL (unchanged)
- Companies cache upsert (Stage 4a) skipped for document-only inputs — no domain to cache against
- `_get_existing_profile_keys` async helper queries `context_entries` for already-populated profile `file_name` values
- `enrich_with_web_research` accepts optional `existing_profile_keys` kwarg; modifies prompt with gap notice and `(SKIP - already have)` prefixes; reduces `max_uses` from 5 to 3 when profile is already rich

## Task Commits

All tasks committed in a single per-plan commit:

1. **Task 1: URL vs Document discriminator and SUPPLEMENTARY_DOCS handling** - `398f790` (feat)
2. **Task 2: Gap-aware enrichment — read existing profile before web research** - `398f790` (feat)

## Files Created/Modified
- `backend/src/flywheel/services/skill_executor.py` — Input discriminator, DOCUMENT_FILE DB fetch, supplementary doc merge, existing_keys call before enrich
- `backend/src/flywheel/engines/company_intel.py` — `_get_existing_profile_keys` helper, `enrich_with_web_research` new kwarg + gap-aware prompt

## Decisions Made
- `DOCUMENT_FILE_PREFIX` constant is defined inside `_execute_company_intel` (not module-level) since it's only used there — avoids polluting the module namespace
- `is_document` drives `source_label` ("document-upload" vs "website-crawl") and gates the companies cache upsert
- Supplementary document fetch errors are caught and logged as warnings, not errors — partial supplementary data is still preferable to aborting the run
- The `max_uses` threshold is "more than half the total profile files" (i.e., >2 out of 5 profile files populated triggers reduction from 5 to 3)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01 complete: company intel engine now handles document inputs and is gap-aware for enrichment
- Plan 02 ready to proceed: can build on the document-aware enrichment path for onboarding flow updates
- Plan 03 ready: frontend trigger for document-only intel run can now call the backend with `DOCUMENT_FILE:{uuid}` input

---
*Phase: 58-unified-company-intelligence-engine*
*Completed: 2026-03-27*
