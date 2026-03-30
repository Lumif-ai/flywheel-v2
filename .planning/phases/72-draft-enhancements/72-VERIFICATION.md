---
phase: 72-draft-enhancements
verified: 2026-03-30T02:41:03Z
status: gaps_found
score: 4/7 must-haves verified
re_verification: false
gaps:
  - truth: "POST /email/drafts/{draft_id}/regenerate with action 'shorter' returns a regenerated draft body that is shorter"
    status: failed
    reason: "regenerate_draft_with_overrides uses the Integration model (line 526-529 of email_drafter.py) but Integration is not imported in email_drafter.py — calling this function at runtime will raise NameError: name 'Integration' is not defined"
    artifacts:
      - path: "backend/src/flywheel/engines/email_drafter.py"
        issue: "Integration referenced in regenerate_draft_with_overrides() but missing from imports block (line 45-52). Only ContextEntry, ContextEntity, Email, EmailDraft, EmailScore, EmailVoiceProfile are imported."
    missing:
      - "Add Integration to the from flywheel.db.models import (...) block in email_drafter.py"

  - truth: "POST /email/drafts/{draft_id}/regenerate with action 'more_casual' returns a regenerated draft with casual tone — persistent voice profile is unchanged"
    status: failed
    reason: "Same root cause as above — NameError on Integration will prevent any regeneration call from completing"
    artifacts:
      - path: "backend/src/flywheel/engines/email_drafter.py"
        issue: "Same missing import — blocks all regeneration paths"
    missing:
      - "Add Integration to the db.models import (same fix as above)"

  - truth: "POST /email/drafts/{draft_id}/regenerate with custom_instructions returns a draft incorporating the free-form instruction"
    status: failed
    reason: "Same root cause — NameError on Integration blocks all calls to regenerate_draft_with_overrides regardless of whether action or custom_instructions is used"
    artifacts:
      - path: "backend/src/flywheel/engines/email_drafter.py"
        issue: "Same missing import — blocks all regeneration paths"
    missing:
      - "Add Integration to the db.models import (same fix as above)"

  - truth: "After regenerating with 'More casual,' the draft voice annotation shows the overridden values — but visiting Voice Profile settings confirms the persistent profile is unchanged"
    status: failed
    reason: "Field name mismatch between backend and frontend: backend stores characteristic_phrases as 'phrases' in the voice_snapshot dict (VOICE_SNAPSHOT_FIELDS constant), but the frontend VoiceSnapshot TypeScript interface expects 'characteristic_phrases'. The API passes the dict through as-is, so snapshot.characteristic_phrases will always be undefined in the UI — phrases will always show 'Not set' even when they exist. Additionally blocked by the Integration NameError."
    artifacts:
      - path: "backend/src/flywheel/engines/email_drafter.py"
        issue: "VOICE_SNAPSHOT_FIELDS uses 'phrases' as the key (line 83), but the VoiceSnapshot TypeScript interface expects 'characteristic_phrases'"
      - path: "frontend/src/features/email/types/email.ts"
        issue: "VoiceSnapshot interface has 'characteristic_phrases: string[] | null' (line 33) but backend sends 'phrases'"
    missing:
      - "Either rename 'phrases' to 'characteristic_phrases' in VOICE_SNAPSHOT_FIELDS in email_drafter.py (and update _load_voice_profile and all related backend logic), OR rename 'characteristic_phrases' to 'phrases' in the frontend VoiceSnapshot interface and all VoiceAnnotation.tsx field references"

human_verification:
  - test: "Visually confirm 'Voice applied' section appears collapsed below draft body, with tone/greeting/sign-off/length badges visible"
    expected: "A subtle collapsed section with 5 inline badges appears below the draft textarea and above the action buttons"
    why_human: "Cannot verify visual rendering programmatically"
  - test: "Expand 'Voice applied' and confirm all 10 fields display in 2-column grid"
    expected: "10 labeled fields appear, with 'Not set' for null values"
    why_human: "Cannot verify interactive expand/collapse behavior programmatically"
  - test: "Confirm Approve, Edit, and Dismiss buttons are disabled while regeneration spinner is active"
    expected: "Buttons show opacity-50 and are non-interactive while regenerateMutation.isPending is true"
    why_human: "Cannot verify in-flight loading state programmatically"
---

# Phase 72: Draft Enhancements Verification Report

**Phase Goal:** Users can see exactly how their voice profile influenced each draft and quickly adjust drafts without editing the persistent voice profile. The draft review experience goes from "approve or edit" to "approve, regenerate with quick adjustments, or edit."
**Verified:** 2026-03-30T02:41:03Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every new draft stores a voice_snapshot in context_used JSONB | VERIFIED | `_build_voice_snapshot()` called in `draft_email()` at line 675-676; snapshot appended to context_used |
| 2 | POST /drafts/{id}/regenerate with action 'shorter' returns shorter draft | FAILED | `regenerate_draft_with_overrides` references `Integration` at line 526 but it is not imported — NameError at runtime |
| 3 | POST /drafts/{id}/regenerate with action 'more_casual' leaves persistent profile unchanged | FAILED | Same NameError blocks the call; persistent profile protection logic exists but unreachable |
| 4 | POST /drafts/{id}/regenerate with custom_instructions uses free-form instruction | FAILED | Same NameError blocks the call |
| 5 | Regeneration of a non-pending draft returns 400 | VERIFIED | `raise ValueError(f"Cannot regenerate a {draft.status} draft")` caught as 400 in endpoint |
| 6 | GET thread detail response includes voice_snapshot for each draft | VERIFIED | Extraction loop at lines 562-568 in email.py; `DraftDetail.voice_snapshot` field present |
| 7 | Each pending draft shows collapsible 'Voice applied' section with 5 key fields collapsed, 10 expanded | PARTIAL | Component is fully built and wired — but phrases field will always show 'Not set' due to key name mismatch ('phrases' vs 'characteristic_phrases') |

**Score:** 4/7 truths verified (2 fully verified, 1 partial, 3 failed + 1 partially structural gap)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/engines/email_drafter.py` | Voice snapshot storage + regenerate_draft_with_overrides helper | PARTIAL | QUICK_ACTION_OVERRIDES, VOICE_SNAPSHOT_FIELDS, _build_voice_snapshot, _generate_draft_body, regenerate_draft_with_overrides all exist and are substantive — but regenerate_draft_with_overrides will fail at runtime due to missing Integration import |
| `backend/src/flywheel/api/email.py` | POST /drafts/{id}/regenerate endpoint with RegenerateRequest model | VERIFIED | RegenerateRequest, RegenerateDraftResponse models present; endpoint registered; validation logic correct |
| `frontend/src/features/email/components/VoiceAnnotation.tsx` | Collapsible voice profile annotation | PARTIAL | Component exists and is substantive — COLLAPSED_FIELDS and ALL_FIELDS both reference 'characteristic_phrases' but backend sends 'phrases', so phrases badge/row will always show 'Not set' |
| `frontend/src/features/email/components/RegenerateDropdown.tsx` | Dropdown with 4 quick actions + custom instructions | VERIFIED | All 4 quick actions present (shorter/longer/more_casual/more_formal); custom instructions inline input with placeholder; confirmation dialog for drafts with user_edits |
| `frontend/src/features/email/hooks/useDraftActions.ts` | useRegenerateDraft mutation hook | VERIFIED | Hook present; POST to regenerate endpoint; cache invalidation for both email-threads and thread-detail; error toast via sonner |
| `frontend/src/features/email/components/DraftReview.tsx` | Integration of VoiceAnnotation and RegenerateDropdown | VERIFIED | Both components imported and rendered; VoiceAnnotation receives draft.voice_snapshot; RegenerateDropdown wired to regenerateMutation; approve/edit/dismiss all disabled when isRegenerating |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| email.py regenerate endpoint | email_drafter.regenerate_draft_with_overrides | Calls drafter helper with merged voice overrides | WIRED | Import at line 1010-1013; call at line 1026 |
| email_drafter.draft_email | EmailDraft.context_used | Appends voice_snapshot dict to context_used list | WIRED | Lines 675-676 in email_drafter.py |
| RegenerateDropdown.tsx | useDraftActions.useRegenerateDraft | Mutation call on quick action or custom submit | WIRED | `onRegenerate` prop called in DraftReview, which calls `regenerateMutation.mutate(request)` |
| DraftReview.tsx | VoiceAnnotation.tsx | Renders VoiceAnnotation with draft.voice_snapshot prop | WIRED | Line 113: `<VoiceAnnotation snapshot={draft.voice_snapshot} />` |
| useDraftActions.ts | POST /email/drafts/{id}/regenerate | React Query mutation with cache invalidation | WIRED | `api.post('/email/drafts/${draftId}/regenerate', request)` with invalidation of both query keys |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| DRAFT-01: DraftReview shows collapsible "Voice applied" annotation | PARTIAL | Component wired correctly; phrases field always shows 'Not set' due to key name mismatch |
| DRAFT-02: Regenerate dropdown with 4 quick actions (one-time overrides, no persistent profile change) | PARTIAL | Frontend is correct; backend will NameError on Integration when called |
| DRAFT-03: POST /email/drafts/{draft_id}/regenerate endpoint | PARTIAL | Endpoint defined and validated correctly; underlying helper will NameError at runtime |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/flywheel/engines/email_drafter.py` | 526-529 | `select(Integration)` with Integration not imported | Blocker | Any call to `regenerate_draft_with_overrides` will raise `NameError: name 'Integration' is not defined` — all regeneration paths fail at runtime |
| `backend/src/flywheel/engines/email_drafter.py` | 83 | `VOICE_SNAPSHOT_FIELDS` uses `"phrases"` | Warning | Field name mismatch with frontend `VoiceSnapshot.characteristic_phrases` — phrases never display in UI |

### Human Verification Required

#### 1. Voice applied section visual rendering

**Test:** Open a pending draft thread in the email view
**Expected:** A "Voice applied" section appears below the draft body textarea, collapsed by default, showing tone, greeting style, sign-off, avg length, and phrases badges
**Why human:** Cannot verify visual rendering programmatically

#### 2. Expand/collapse behavior

**Test:** Click the "Voice applied" chevron to expand
**Expected:** A 2-column grid appears showing all 10 voice fields with labels; null fields show "Not set"
**Why human:** Cannot verify interactive expand/collapse state programmatically

#### 3. Button disabling during regeneration

**Test:** Trigger a regeneration and observe button states before the API responds
**Expected:** Approve, Edit, and Dismiss buttons all show 50% opacity and are non-interactive; Regenerate button shows spinning loader
**Why human:** Cannot verify in-flight loading state programmatically

### Gaps Summary

**Two independent issues need fixing before the regeneration goal is achieved:**

**Gap 1 — Missing import (blocker):** `Integration` is used in `regenerate_draft_with_overrides()` to look up the gmail-read integration for email body re-fetching, but it is not in the import block at lines 45-52 of `email_drafter.py`. The module import check passes because the NameError only occurs when the function is actually called. Fix: add `Integration` to `from flywheel.db.models import (...)`.

**Gap 2 — Field name mismatch (warning, degrades UX):** The backend `VOICE_SNAPSHOT_FIELDS` constant uses `"phrases"` as the key, consistent with the rest of the backend (EmailVoiceProfile.phrases, _load_voice_profile dict, VoiceProfileResponse). However the frontend `VoiceSnapshot` TypeScript interface was defined with `characteristic_phrases`. Since the API passes the voice_snapshot dict through without transformation, the frontend receives `{phrases: [...]}` but looks for `characteristic_phrases`. TypeScript compiles without errors because `voice_snapshot` is typed as `dict | None` on the backend response and the frontend receives it as `unknown` before casting. The fix is to align the names — either rename the VOICE_SNAPSHOT_FIELDS entry and update all callers, or rename the frontend TypeScript field. The simpler fix is to update the frontend type and VoiceAnnotation.tsx references since the backend field name `phrases` is deeply established.

---

_Verified: 2026-03-30T02:41:03Z_
_Verifier: Claude (gsd-verifier)_
