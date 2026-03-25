---
phase: 49-living-company-profile
plan: 02
subsystem: frontend
tags: [profile, crawl, sse, document-analysis, react-query]

# Dependency graph
requires:
  - phase: 49-living-company-profile
    plan: 01
    provides: crawl_error SSE event, POST /profile/analyze-document endpoint
provides:
  - useProfileCrawl hook for profile-scoped crawl with SSE streaming
  - Inline URL crawl and document analyze UI on empty Company Profile page
affects: [company-profile-ux, onboarding-flow-decoupling]

# Tech tracking
tech-stack:
  added: []
  patterns: [profile-scoped crawl hook subset of useOnboarding, inline crawl panel reusing LiveCrawl component]

key-files:
  created:
    - frontend/src/features/profile/hooks/useProfileCrawl.ts
  modified:
    - frontend/src/features/profile/components/CompanyProfilePage.tsx

key-decisions:
  - "useProfileCrawl is a focused subset of useOnboarding -- no cache checking, merge mode, or edit mode"
  - "URL input uses inline normalizeUrl/isValidUrl rather than importing UrlInput component (onboarding-specific copy)"
  - "CrawlPanel and DocumentAnalyzePanel are local components, not shared -- profile-specific UX"

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 49 Plan 02: Inline crawl and document analyze UI for Company Profile Summary

**Replaced broken "Run onboarding" redirect with inline URL crawl panel and document upload + analyze on empty Company Profile page**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T14:45:39Z
- **Completed:** 2026-03-25T14:48:31Z
- **Tasks:** 2
- **Files created:** 1
- **Files modified:** 1

## Accomplishments
- Created useProfileCrawl hook: focused crawl trigger + SSE streaming + React Query invalidation (no onboarding baggage)
- Rewrote empty profile state with two-panel layout: URL crawl panel (with domain prefill) and document upload + analyze panel separated by "or" divider
- URL crawl streams live discovery items via LiveCrawl component reuse
- Document upload triggers file upload, profile link, and analyze-document endpoint in sequence
- Profile auto-refreshes after crawl completion or document analysis via queryClient.invalidateQueries
- UploadedFilesSection now renders in empty state when files exist
- Removed Link/Plus imports and all references to /onboarding redirect

## Task Commits

1. **Task 1: Create useProfileCrawl hook** - `47700df` (feat)
2. **Task 2: Rewrite CompanyProfilePage empty state** - `5566d47` (feat)

## Files Created/Modified
- `frontend/src/features/profile/hooks/useProfileCrawl.ts` - New hook: profile-scoped crawl with SSE streaming and query invalidation
- `frontend/src/features/profile/components/CompanyProfilePage.tsx` - Rewrote empty state with CrawlPanel, DocumentAnalyzePanel, "or" divider

## Decisions Made
- useProfileCrawl is a focused subset of useOnboarding -- no cache checking, merge mode, or edit mode
- URL input uses inline normalizeUrl/isValidUrl rather than importing UrlInput component (has onboarding-specific copy)
- CrawlPanel and DocumentAnalyzePanel are local components, not shared -- profile-specific UX

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Company Profile page now provides complete inline experience for populating company intelligence
- Both URL crawl and document analyze paths end with profile data refresh
- No dependency on onboarding flow -- fully decoupled

---
*Phase: 49-living-company-profile*
*Completed: 2026-03-25*
