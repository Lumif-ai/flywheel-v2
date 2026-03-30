# Phase 72: Draft Enhancements - Research

**Researched:** 2026-03-30
**Domain:** Backend API design + React UI components for draft voice annotation and regeneration
**Confidence:** HIGH

## Summary

Phase 72 adds two capabilities to the existing draft review experience: (1) a voice annotation section showing which voice profile fields influenced each draft, and (2) a regenerate dropdown with quick actions and custom overrides that re-draft without touching the persistent voice profile.

The codebase is well-structured for this. The drafter engine (`email_drafter.py`) already loads the full 10-field voice profile and formats it into the system prompt. The key gap is that the voice profile snapshot used at draft time is not persisted -- `context_used` on `EmailDraft` stores context_refs (entries/entities from the scorer) but not the voice profile values. The regeneration endpoint needs to call the same drafter pipeline with modified voice parameters while keeping the persistent `EmailVoiceProfile` untouched.

**Primary recommendation:** Store a `voice_snapshot` dict inside `EmailDraft.context_used` JSONB at draft time (no schema migration needed). Build `POST /email/drafts/{draft_id}/regenerate` as a thin wrapper around the existing `_build_draft_prompt` + Claude call. Frontend adds a collapsible `VoiceAnnotation` component and a `RegenerateDropdown` to the existing `DraftReview.tsx`.

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | REST endpoint for regenerate | Already used for all email endpoints |
| SQLAlchemy async | current | DB access for draft + voice profile | Already used throughout backend |
| React + TypeScript | current | Frontend components | Already used throughout frontend |
| TanStack React Query | current | Data fetching + mutation hooks | Already used for all email hooks |
| Tailwind CSS | current | Styling | Already used throughout frontend |
| Pydantic | current | Request/response validation | Already used for all API models |
| Anthropic SDK | current | Claude API calls for regeneration | Already used in drafter engine |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | current | Icons (ChevronDown, RefreshCw, etc.) | UI icons for collapse/expand and regenerate |
| sonner | current | Toast notifications | Success/error feedback on regenerate |
| zustand | current | Email store state | Only if regeneration needs global state (likely not) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSONB voice_snapshot in context_used | New `voice_snapshot` column on email_drafts | Column is cleaner but requires migration; JSONB field already exists and is flexible |
| Dropdown with quick actions | Modal dialog | Dropdown is lighter weight and faster; matches "quick action" UX intent |

**Installation:** No new packages needed -- everything is already in the project.

## Architecture Patterns

### Backend: Regenerate Endpoint

**Pattern:** The regenerate endpoint follows the same structure as the existing `approve_draft` and `dismiss_draft` endpoints in `backend/src/flywheel/api/email.py`:
1. Load draft by ID + tenant ownership check
2. Verify status is "pending"
3. Load parent email (for subject, sender, body context)
4. Execute operation (call drafter with overrides)
5. Update draft row
6. Return response

**Key design decision:** The regenerate endpoint does NOT create a new `EmailDraft` row. It overwrites `draft_body` on the existing row and nulls `user_edits` (since the user hasn't edited the regenerated version yet). This preserves the 1:1 email-to-pending-draft relationship that the UI assumes.

### Backend: Voice Snapshot Storage

**Pattern:** Store the voice profile snapshot as a dict entry in the existing `context_used` JSONB column on `EmailDraft`. Currently `context_used` stores a list of context_ref dicts like `[{type: "entry", id: "..."}, ...]`. Add a single dict with `{type: "voice_snapshot", ...all 10 fields}`.

This approach:
- Requires zero schema migration
- Is queryable via JSONB operators if needed later
- Already serialized/deserialized by SQLAlchemy JSONB type

The `_upsert_email_draft` function in `email_drafter.py` already accepts `context_used: list` -- the snapshot dict gets appended to this list alongside the context_refs.

### Frontend: Component Structure

```
DraftReview.tsx (existing)
  +-- VoiceAnnotation (new) -- collapsible section
  +-- RegenerateDropdown (new) -- dropdown with quick actions
```

**VoiceAnnotation:** Collapsible component that reads `voice_snapshot` from draft's `context_used` array. Shows 5 key fields collapsed (tone, greeting_style, sign_off, avg_length, phrases) and all 10 when expanded.

**RegenerateDropdown:** Button dropdown with 4 preset actions + custom option. Each triggers `POST /email/drafts/{draft_id}/regenerate` with specific overrides.

### Recommended File Changes

```
backend/
  src/flywheel/
    api/email.py              # Add POST /drafts/{id}/regenerate endpoint
    engines/email_drafter.py  # Add voice_snapshot to context_used; extract regenerate helper

frontend/
  src/features/email/
    types/email.ts            # Add VoiceSnapshot type, update Draft interface
    components/
      DraftReview.tsx          # Add VoiceAnnotation + RegenerateDropdown
      VoiceAnnotation.tsx      # New: collapsible voice fields display
      RegenerateDropdown.tsx   # New: dropdown with quick actions
    hooks/
      useDraftActions.ts       # Add useRegenerateDraft mutation hook
```

### Anti-Patterns to Avoid
- **Don't create a separate regeneration engine.** The existing `_build_draft_prompt` and Claude call in `email_drafter.py` can be extracted into a reusable helper. The regenerate endpoint just calls it with merged voice overrides.
- **Don't modify the persistent EmailVoiceProfile during regeneration.** The overrides are one-time, per-draft only. The success criterion explicitly states: "visiting Voice Profile settings confirms the persistent profile is unchanged."
- **Don't fetch the email body from Gmail again during regeneration.** The draft row already exists -- use the existing email context. However, you DO need to re-fetch the email body since it's fetched on-demand (not stored). The parent `Email` row has `snippet` as fallback.
- **Don't add a new DB column for voice_snapshot.** The JSONB `context_used` column is sufficient and avoids a migration.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dropdown UI component | Custom dropdown from scratch | Existing pattern from DraftReview buttons or Radix DropdownMenu if available | Accessibility, keyboard nav, click-outside |
| Collapsible section | Custom show/hide div | Pattern already used in ThreadDetail.tsx (ChevronDown/ChevronRight toggle) | Consistent UX across the app |
| API mutation with cache invalidation | Raw fetch + manual cache clear | TanStack React Query useMutation (same pattern as useDraftActions.ts) | Already established pattern |
| Voice field merge logic | Complex merge in frontend | Backend handles merge in regenerate endpoint, returns complete new draft | Single source of truth |

**Key insight:** Every UI pattern needed already exists in the codebase. The collapsible section pattern is in `ThreadDetail.tsx` (reasoning toggle). The mutation pattern is in `useDraftActions.ts`. The button styling is in `DraftReview.tsx`. No new UI primitives needed.

## Common Pitfalls

### Pitfall 1: Losing User Edits on Regenerate
**What goes wrong:** User edits the draft, then clicks regenerate -- their edits vanish without warning.
**Why it happens:** Regenerate overwrites `draft_body` and nulls `user_edits`.
**How to avoid:** If `user_edits` is non-null, show a confirmation dialog ("You have unsaved edits. Regenerating will replace them.") before proceeding.
**Warning signs:** Users losing work silently.

### Pitfall 2: Voice Snapshot Not Present for Old Drafts
**What goes wrong:** Drafts created before Phase 72 deployment have no `voice_snapshot` in `context_used`.
**Why it happens:** Legacy drafts were created without snapshot logic.
**How to avoid:** Frontend must handle `voice_snapshot` being absent gracefully -- hide the "Voice applied" section entirely when no snapshot exists. Backend regenerate endpoint should load the current voice profile if no snapshot is stored.
**Warning signs:** Null reference errors, empty annotation sections.

### Pitfall 3: Gmail Body Re-fetch Failure During Regeneration
**What goes wrong:** Regenerate endpoint tries to fetch email body from Gmail but credentials have expired or API is down.
**Why it happens:** The original draft flow fetches body on-demand; regeneration must do the same.
**How to avoid:** Use the same `_fetch_body_with_fallback` pattern. If body fetch fails, fall back to `email.snippet`. Log the error in `context_used` (same pattern as initial draft).
**Warning signs:** 502 errors on regenerate, drafts regenerating without email context.

### Pitfall 4: Race Condition Between Regenerate and Approve
**What goes wrong:** User clicks regenerate, then immediately clicks approve before regeneration completes. Approves stale draft or gets inconsistent state.
**How to avoid:** Frontend disables approve/edit/dismiss buttons while regeneration is in-flight (loading spinner on the draft body area). The mutation's `isPending` state handles this naturally.
**Warning signs:** Draft status inconsistencies.

### Pitfall 5: Regeneration Quick Actions Producing Minimal Change
**What goes wrong:** User clicks "More casual" but the draft barely changes because the voice profile was already casual.
**Why it happens:** Quick action applies a relative override to an already-appropriate value.
**How to avoid:** Quick actions should use absolute overrides, not relative. E.g., "More casual" sets `formality_level: "casual"` regardless of current value, and adjusts tone accordingly.
**Warning signs:** User frustration, repeated regeneration attempts.

## Code Examples

### Backend: Voice Snapshot in Draft Creation

The existing `draft_email()` function in `email_drafter.py` calls `_load_voice_profile()` at step 1 and `_upsert_email_draft()` at step 9. The snapshot should be appended to `context_used` between those steps:

```python
# In draft_email(), after step 6 (build prompt), before step 9 (upsert):
voice_snapshot = {"type": "voice_snapshot", **voice_profile}

# In _upsert_email_draft, voice_snapshot is included in the context_used list:
full_context = list(context_used) + [voice_snapshot]
```

### Backend: Regenerate Endpoint Request/Response Models

```python
class RegenerateRequest(BaseModel):
    action: str | None = None  # "shorter", "longer", "more_casual", "more_formal"
    custom_instructions: str | None = None  # Free-form override text

class RegenerateDraftResponse(BaseModel):
    id: UUID
    draft_body: str
    voice_snapshot: dict
    message: str
```

### Backend: Quick Action Override Mapping

```python
QUICK_ACTION_OVERRIDES = {
    "shorter": {"avg_length": 40, "avg_sentences": 2, "paragraph_pattern": "short single-line"},
    "longer": {"avg_length": 150, "avg_sentences": 6, "paragraph_pattern": "2-3 sentence blocks"},
    "more_casual": {"formality_level": "casual", "tone": "friendly and relaxed", "emoji_usage": "occasional"},
    "more_formal": {"formality_level": "formal", "tone": "professional and polished", "emoji_usage": "never"},
}
```

### Backend: Regenerate Logic (Pseudo-code)

```python
@router.post("/drafts/{draft_id}/regenerate")
async def regenerate_draft(draft_id, body: RegenerateRequest, user, db):
    # 1. Load draft (same pattern as approve/dismiss)
    # 2. Verify pending status
    # 3. Load parent email
    # 4. Load current voice profile
    # 5. Apply quick action overrides OR custom instructions
    # 6. Re-fetch email body (with fallback)
    # 7. Re-assemble context from score's context_refs
    # 8. Build prompt with overridden voice profile
    # 9. Call Claude
    # 10. Update draft_body, null user_edits, update context_used with new voice_snapshot
    # 11. Return new draft body + voice snapshot
```

### Frontend: VoiceAnnotation Component Pattern

```typescript
// Follows the existing collapsible pattern from ThreadDetail.tsx
const [expanded, setExpanded] = useState(false)
const snapshot = draft.context_used?.find(c => c.type === 'voice_snapshot')
if (!snapshot) return null  // graceful fallback for old drafts

// Collapsed: show 5 key fields inline
// Expanded: show all 10 fields in a grid
```

### Frontend: RegenerateDropdown Quick Actions

```typescript
const QUICK_ACTIONS = [
  { key: 'shorter', label: 'Shorter', icon: ArrowDown },
  { key: 'longer', label: 'Longer', icon: ArrowUp },
  { key: 'more_casual', label: 'More casual', icon: Smile },
  { key: 'more_formal', label: 'More formal', icon: Briefcase },
] as const
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Draft is fire-and-forget | Draft stores context_used for traceability | Phase 55 | Foundation for voice annotation |
| Voice profile has 4 fields | Voice profile has 10 fields | Phase 70 | All 10 fields available for annotation |
| Voice profile editable via settings only | Settings UI with edit + reset | Phase 71 | Phase 72 adds per-draft overrides (complementary) |
| Drafter uses DEFAULT_VOICE_STUB on cold start | Drafter loads full 10-field profile | Phase 70 | Regeneration can override any of the 10 fields |

## Open Questions

1. **Email body re-fetch on regeneration**
   - What we know: The original draft pipeline fetches body from Gmail on-demand. Draft row stores `draft_body` but not the original email body.
   - What's unclear: Should regeneration re-fetch from Gmail (adds latency, possible auth failure) or should we start storing a body hash/reference?
   - Recommendation: Re-fetch from Gmail using the same `_fetch_body_with_fallback` pattern. The latency is acceptable (single API call) and keeps the architecture consistent. Storing email bodies would be a larger change and raises PII concerns.

2. **Custom instructions interaction with voice profile**
   - What we know: Custom instructions should allow free-form text like "make it sound more empathetic" or "add a question about their timeline."
   - What's unclear: Should custom instructions replace the voice profile entirely or augment it?
   - Recommendation: Augment. Pass custom instructions as an additional instruction block in the system prompt, layered on top of the (possibly overridden) voice profile. This preserves the user's core voice while honoring the specific request.

3. **Regeneration count limit**
   - What we know: Each regeneration costs one Claude API call.
   - What's unclear: Should there be a limit on how many times a user can regenerate a single draft?
   - Recommendation: No hard limit in Phase 72. The UI naturally limits this (user has to wait for each regeneration). If abuse becomes an issue, add a rate limit later.

4. **Should `DraftDetail` response include `context_used` or a derived `voice_snapshot`?**
   - What we know: The current `DraftDetail` Pydantic model returns `id`, `status`, `draft_body`, `user_edits` -- no `context_used`.
   - What's unclear: Should we expose the raw `context_used` list or extract just the voice_snapshot?
   - Recommendation: Add a `voice_snapshot: dict | None` field to `DraftDetail` that is extracted server-side from `context_used`. This keeps the API clean and avoids exposing internal context_ref structure to the frontend.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** -- `backend/src/flywheel/engines/email_drafter.py` (drafter pipeline, voice profile loading, prompt construction)
- **Codebase inspection** -- `backend/src/flywheel/api/email.py` (all existing draft lifecycle endpoints, Pydantic models, auth patterns)
- **Codebase inspection** -- `backend/src/flywheel/engines/email_voice_updater.py` (voice profile field structure, merge patterns)
- **Codebase inspection** -- `backend/src/flywheel/db/models.py` lines 1016-1094 (EmailDraft and EmailVoiceProfile schemas)
- **Codebase inspection** -- `frontend/src/features/email/components/DraftReview.tsx` (current draft UI, button patterns)
- **Codebase inspection** -- `frontend/src/features/email/components/ThreadDetail.tsx` (collapsible section pattern, Sheet layout)
- **Codebase inspection** -- `frontend/src/features/email/hooks/useDraftActions.ts` (mutation + cache invalidation pattern)
- **Codebase inspection** -- `frontend/src/features/email/types/email.ts` (TypeScript interfaces for Draft, ThreadDetailResponse)
- **Codebase inspection** -- `frontend/src/features/settings/components/VoiceProfileSettings.tsx` (voice profile field labels, display format)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- everything is already in the project, no new dependencies
- Architecture: HIGH -- follows established patterns for endpoint structure, mutation hooks, and UI components
- Pitfalls: HIGH -- identified from direct codebase analysis (race conditions, missing snapshots, body re-fetch)

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- all patterns are internal to the project)
