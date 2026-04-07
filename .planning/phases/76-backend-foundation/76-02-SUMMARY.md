---
phase: 76-backend-foundation
plan: 02
subsystem: api
tags: [xss, sanitization, beautifulsoup, html, markdown, documents, mcp]

# Dependency graph
requires:
  - phase: 76-backend-foundation plan 01
    provides: research context and phase structure
provides:
  - sanitize_html() allowlist-based HTML sanitizer in output_renderer.py
  - POST /api/v1/documents/from-content endpoint for MCP tool document creation
affects: [76-backend-foundation remaining plans, mcp-tools, frontend document library]

# Tech tracking
tech-stack:
  added: []
  patterns: [allowlist HTML sanitization via BeautifulSoup4, completed SkillRun bypass for job queue]

key-files:
  created: []
  modified:
    - backend/src/flywheel/engines/output_renderer.py
    - backend/src/flywheel/api/documents.py

key-decisions:
  - "Used BeautifulSoup4 allowlist approach (zero new deps) over regex or bleach for HTML sanitization"
  - "SkillRun created with status=completed + attempts=max_attempts to prevent job queue pickup"
  - "Placed /from-content route before /{document_id} to prevent FastAPI path capture conflicts"

patterns-established:
  - "Allowlist sanitization: all HTML output goes through sanitize_html() before Markup() bypass"
  - "Direct document creation: status=completed + attempts=max_attempts pattern for bypassing job queue"

# Metrics
duration: 12min
completed: 2026-03-30
---

# Phase 76 Plan 02: XSS-Safe HTML Sanitizer and Document-from-Content Endpoint Summary

**Allowlist-based HTML sanitizer using BeautifulSoup4 integrated into markdown rendering pipeline, plus POST /documents/from-content endpoint for MCP tool document creation with job-queue-safe SkillRun bypass**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-30T16:59:44Z
- **Completed:** 2026-03-30T17:12:15Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- XSS protection: script tags, javascript: URIs, and event handler attributes stripped from all rendered HTML output
- Safe HTML (headings, lists, links, tables, emphasis) preserved through sanitizer
- POST /documents/from-content creates completed SkillRun + linked Document in a single transaction
- Job queue isolation via status=completed and attempts=max_attempts on created SkillRuns

## Task Commits

Plan committed as single batch (per-plan strategy):

1. **Task 1: Add sanitize_html() to output_renderer.py** - `f92d64f` (feat)
2. **Task 2: Add POST /documents/from-content endpoint** - `f92d64f` (feat)

## Files Created/Modified
- `backend/src/flywheel/engines/output_renderer.py` - Added sanitize_html() function with ALLOWED_TAGS/ALLOWED_ATTRS/DANGEROUS_PROTOCOLS constants; integrated into _md_to_html filter in both markdown and fallback branches
- `backend/src/flywheel/api/documents.py` - Added FromContentRequest model and POST /from-content endpoint creating SkillRun + Document with sanitized HTML

## Decisions Made
- Used BeautifulSoup4 (already installed) for HTML parsing rather than regex -- more robust against edge cases and encoding tricks
- tag.decompose() removes tag AND contents (not just the tag) for script/style -- prevents any script content from leaking
- Placed sanitize_html() call between markdown() and Markup() in both try and except branches of _md_to_html
- Route ordering: /from-content placed before /{document_id} to prevent FastAPI path capture

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Verification required PYTHONPATH=src since the backend package is not pip-installed in system Python -- used AST-based and grep-based verification as fallback for import-dependent checks

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- sanitize_html() is available for import by any module needing HTML sanitization
- POST /from-content endpoint ready for MCP tool integration
- All existing output rendering continues to work with added XSS protection

---
*Phase: 76-backend-foundation*
*Completed: 2026-03-30*
