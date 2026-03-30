---
phase: 72-draft-enhancements
plan: 02
subsystem: frontend
tags: [email, drafting, voice-annotation, regeneration, ui-components]

# Dependency graph
requires:
  - phase: 72-01
    provides: Voice snapshot persistence in context_used, POST /drafts/{id}/regenerate endpoint
provides:
  - VoiceAnnotation collapsible component showing voice fields per draft
  - RegenerateDropdown with 4 quick actions + custom instructions
  - Integrated draft review with regeneration and button disabling
affects: [email-thread-detail, draft-review-ux]

# Tech tracking
tech-stack:
  added: []
  patterns: [collapsible-voice-annotation, dropdown-quick-actions, regeneration-loading-state]

key-files:
  created:
    - frontend/src/features/email/components/VoiceAnnotation.tsx
    - frontend/src/features/email/components/RegenerateDropdown.tsx
  modified:
    - frontend/src/features/email/types/email.ts
    - frontend/src/features/email/hooks/useDraftActions.ts
    - frontend/src/features/email/components/DraftReview.tsx

key-decisions:
  - "Used existing DropdownMenu primitive (base-ui) for RegenerateDropdown instead of custom click-outside pattern"
  - "VoiceAnnotation shows 5 key fields as badges when collapsed, all 10 in 2-column grid when expanded"
  - "Confirmation dialog only shown when draft has user_edits that would be replaced"

patterns-established:
  - "Voice annotation pattern: collapsible secondary info section below draft body"
  - "Quick action regeneration: dropdown triggers mutation with loading state propagated to disable other actions"

# Metrics
duration: 2min
completed: 2026-03-30
---

# Phase 72 Plan 02: Voice Annotation & Regenerate Dropdown Summary

**Collapsible voice profile annotation per draft + 4-action regenerate dropdown with custom instructions, integrated into DraftReview with loading states**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-30T02:35:05Z
- **Completed:** 2026-03-30T02:37:01Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- VoiceSnapshot, RegenerateRequest, and RegenerateDraftResponse TypeScript interfaces added to email types
- Draft interface extended with optional voice_snapshot field
- useRegenerateDraft mutation hook with cache invalidation and error toast
- VoiceAnnotation component: collapsed shows tone, greeting, sign-off, avg length, phrases as badges; expanded shows all 10 fields in 2-column grid
- RegenerateDropdown: Shorter, Longer, More casual, More formal quick actions + Custom free-form instructions with inline input
- Confirmation dialog when regenerating a draft with user edits
- Approve, Edit, and Dismiss buttons disabled during regeneration to prevent race conditions
- Legacy drafts without voice_snapshot gracefully show no annotation section

## Task Commits

Per-plan commit strategy (single commit for all tasks):

1. **Task 1: VoiceSnapshot type + useRegenerateDraft hook** - `d1253d7` (feat)
2. **Task 2: VoiceAnnotation + RegenerateDropdown + DraftReview integration** - `d1253d7` (feat)

## Files Created/Modified
- `frontend/src/features/email/types/email.ts` - Added VoiceSnapshot, RegenerateRequest, RegenerateDraftResponse interfaces; extended Draft with voice_snapshot
- `frontend/src/features/email/hooks/useDraftActions.ts` - Added useRegenerateDraft mutation hook with POST to regenerate endpoint, cache invalidation, error toast
- `frontend/src/features/email/components/VoiceAnnotation.tsx` - New component: collapsible voice profile display (5 badges collapsed, 10-field grid expanded)
- `frontend/src/features/email/components/RegenerateDropdown.tsx` - New component: dropdown with 4 quick actions, custom instructions input, confirmation dialog for edited drafts
- `frontend/src/features/email/components/DraftReview.tsx` - Integrated VoiceAnnotation and RegenerateDropdown, disabled action buttons during regeneration

## Decisions Made
- Used existing DropdownMenu primitive (base-ui) for the regenerate dropdown rather than a custom click-outside implementation
- VoiceAnnotation shows 5 key fields as inline badges when collapsed, all 10 fields in a 2-column grid when expanded
- Confirmation dialog only appears when the draft has user_edits that would be lost on regeneration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None

## Next Phase Readiness
- Phase 72 complete: both backend (72-01) and frontend (72-02) plans executed
- Voice annotation and regeneration fully wired end-to-end
- Ready for visual verification and any follow-on polish

---
*Phase: 72-draft-enhancements*
*Completed: 2026-03-30*
