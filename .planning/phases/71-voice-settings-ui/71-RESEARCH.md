# Phase 71: Voice Settings UI - Research

**Researched:** 2026-03-30
**Domain:** FastAPI REST endpoints, React settings UI, TanStack React Query, voice profile CRUD
**Confidence:** HIGH

## Summary

Phase 71 adds three API endpoints and a new Settings tab to let users view and edit their learned voice profile. The backend work is straightforward: the `EmailVoiceProfile` model already has all 10 fields (Phase 70), the `email.py` router already has the `/email` prefix and established patterns for auth/RLS, and the existing `voice_profile_init()` function in `gmail_sync.py` handles extraction with on-conflict-do-update semantics. The three new endpoints (GET, PATCH, POST reset) follow identical patterns to existing draft lifecycle endpoints.

The frontend work adds a `VoiceProfileSettings` component to the existing Settings page tab system. The Settings page already uses `@base-ui/react` Tabs, `@tanstack/react-query` for data fetching, `sonner` for toasts, and `lucide-react` for icons. The component pattern from `TenantSettings.tsx` and `GranolaSettings.tsx` provides the exact template: local state for editable fields, `useMutation` for save/reset, `useQuery` for profile fetch, and the `Dialog` component for confirmation modals.

**Primary recommendation:** Add all three endpoints to the existing `email.py` router (not a new router file). Build a single `VoiceProfileSettings.tsx` component using the exact same patterns as `TenantSettings.tsx` (inline edit + save) and `GranolaSettings.tsx` (mutation + toast feedback). The reset endpoint should delete the existing profile row then call `voice_profile_init()` without the idempotency guard.

## Standard Stack

### Core (already in project -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (project) | REST endpoints with `APIRouter` | All API endpoints use this |
| SQLAlchemy 2.0 | (project) | Async ORM with `Mapped[]` typed columns | All DB access |
| Pydantic v2 | (project) | Request/response models | All API schemas |
| @tanstack/react-query | ^5.91.2 | `useQuery`/`useMutation` for data fetching | All frontend data fetching |
| @base-ui/react | ^1.3.0 | Tabs primitive (used in Settings page) | UI component system |
| sonner | ^2.0.7 | Toast notifications | All mutation feedback |
| lucide-react | (project) | Icons | All UI icons |

### No New Dependencies
This phase requires zero new packages on either backend or frontend. Everything uses existing infrastructure.

## Architecture Patterns

### Relevant File Locations
```
backend/src/flywheel/
├── api/email.py                    # MODIFY: add 3 new endpoints
├── db/models.py                    # READ ONLY: EmailVoiceProfile model
├── services/gmail_sync.py          # MODIFY: extract reset logic from voice_profile_init()

frontend/src/
├── pages/SettingsPage.tsx           # MODIFY: add Voice Profile tab
├── features/settings/components/
│   └── VoiceProfileSettings.tsx     # NEW: voice profile view/edit component
```

### Pattern 1: API Endpoint with Tenant-Scoped Auth
**What:** Every endpoint uses `Depends(require_tenant)` for auth and `Depends(get_tenant_db)` for RLS-scoped DB session. The `user.sub` is the user UUID, `user.tenant_id` is the tenant UUID.
**Example from existing code:**
```python
@router.get("/voice-profile")
async def get_voice_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> VoiceProfileResponse:
    result = await db.execute(
        select(EmailVoiceProfile).where(
            EmailVoiceProfile.tenant_id == user.tenant_id,
            EmailVoiceProfile.user_id == user.sub,
        )
    )
    profile = result.scalar_one_or_none()
    # ...
```

### Pattern 2: Frontend Settings Component Structure
**What:** Each settings tab is a standalone component that handles its own data fetching and mutations. Uses `useQuery` for reads, `useMutation` for writes, `toast` for feedback, `Dialog` for confirmations.
**Key conventions from TenantSettings.tsx and GranolaSettings.tsx:**
- Local state with `useState` for editable fields
- `useMutation` with `onSuccess` that calls `queryClient.invalidateQueries`
- `toast.success()` / `toast.error()` from sonner for feedback
- `Dialog` from `@/components/ui/dialog` for confirmation (delete/reset)
- Loading spinner uses `Loader2` from lucide-react with `animate-spin`
- Disabled button state: `disabled={mutation.isPending}`

### Pattern 3: Settings Page Tab Registration
**What:** `SettingsPage.tsx` uses `Tabs/TabsList/TabsTrigger/TabsContent` from `@/components/ui/tabs`. Each tab is conditionally rendered.
**How to add Voice Profile tab:**
```tsx
{isAdmin && <TabsTrigger value="voice-profile">Voice Profile</TabsTrigger>}
// ...
{isAdmin && (
  <TabsContent value="voice-profile" className="mt-6">
    <VoiceProfileSettings />
  </TabsContent>
)}
```

### Pattern 4: Background Task for Heavy Operations
**What:** The reset endpoint needs to trigger re-extraction which is expensive (fetches 200 Gmail messages, calls LLM). Use `BackgroundTasks` from FastAPI, same as `trigger_sync()`.
**Key detail:** The existing `voice_profile_init()` has an idempotency guard (returns False if profile exists). For reset, we need to either: (a) delete the profile first then call `voice_profile_init()`, or (b) create a new function that skips the guard and uses `on_conflict_do_update`. Option (a) is simpler.

### Anti-Patterns to Avoid
- **Don't create a separate router file** for just 3 endpoints. The email router already handles voice-related operations (voice update background task).
- **Don't use `user.id`** -- always use `user.sub` for user UUID (the `id` is the Pydantic model ID, `sub` is the JWT subject = profile UUID).
- **Don't mix concerns** -- the reset endpoint should NOT do extraction synchronously. Always use BackgroundTasks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Voice extraction | Custom extraction logic for reset | `voice_profile_init()` from gmail_sync.py | Already handles 50-sample extraction, LLM call, upsert |
| Toast notifications | Custom notification system | `sonner` toast | Already integrated project-wide |
| Confirmation dialog | Custom modal | `Dialog` from `@/components/ui/dialog` | Used in TenantSettings for delete confirmation |
| Query invalidation | Manual refetch | `queryClient.invalidateQueries` | TanStack Query pattern used everywhere |

## Common Pitfalls

### Pitfall 1: Idempotency Guard in voice_profile_init()
**What goes wrong:** Calling `voice_profile_init()` for reset fails silently because the function returns `False` if a profile already exists.
**Why it happens:** The function was designed for first-time extraction during Gmail sync.
**How to avoid:** Delete the existing `EmailVoiceProfile` row BEFORE calling `voice_profile_init()` in the reset flow. Or better: the reset endpoint deletes the row, then calls the init function which will see no existing profile and proceed.
**Warning signs:** Reset returns 200 but profile doesn't change.

### Pitfall 2: PATCH Allowing Arbitrary Fields
**What goes wrong:** PATCH endpoint updates fields beyond tone and sign_off, breaking the "read-only for 8 fields" requirement.
**How to avoid:** Use a dedicated Pydantic model with ONLY `tone: str | None` and `sign_off: str | None` fields. Never accept arbitrary JSON.

### Pitfall 3: Background Reset Without Status Feedback
**What goes wrong:** User clicks Reset, gets immediate 200, but has no way to know when re-extraction completes.
**How to avoid:** After deleting the profile, return immediately. The GET endpoint will return null/empty. When extraction completes (via background task), the next GET will show the new profile. Frontend can poll or show "Re-learning in progress..." state.
**Implementation:** The simplest approach: delete profile -> return 200 with `{ status: "relearning" }` -> frontend shows empty state with "Re-learning..." message -> user refreshes or component re-polls.

### Pitfall 4: Missing Integration Check on Reset
**What goes wrong:** Reset is triggered but no Gmail integration exists -- background task fails silently.
**How to avoid:** Check for `gmail-read` integration BEFORE starting the reset. Return 400 if not connected.

### Pitfall 5: user.sub vs user.id
**What goes wrong:** Using `user.id` instead of `user.sub` in queries. The `TokenPayload` model uses `sub` (JWT standard) as the user UUID.
**How to avoid:** Always use `user.sub` for user_id in DB queries. Check existing endpoints for the pattern.

## Code Examples

### Backend: GET /email/voice-profile
```python
class VoiceProfileResponse(BaseModel):
    tone: str | None
    avg_length: int | None
    sign_off: str | None
    phrases: list[str]
    formality_level: str | None
    greeting_style: str | None
    question_style: str | None
    paragraph_pattern: str | None
    emoji_usage: str | None
    avg_sentences: int | None
    samples_analyzed: int
    updated_at: datetime

@router.get("/voice-profile", response_model=VoiceProfileResponse | None)
async def get_voice_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> VoiceProfileResponse | None:
    result = await db.execute(
        select(EmailVoiceProfile).where(
            EmailVoiceProfile.tenant_id == user.tenant_id,
            EmailVoiceProfile.user_id == user.sub,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    return VoiceProfileResponse(
        tone=profile.tone,
        avg_length=profile.avg_length,
        sign_off=profile.sign_off,
        phrases=profile.phrases or [],
        formality_level=profile.formality_level,
        greeting_style=profile.greeting_style,
        question_style=profile.question_style,
        paragraph_pattern=profile.paragraph_pattern,
        emoji_usage=profile.emoji_usage,
        avg_sentences=profile.avg_sentences,
        samples_analyzed=profile.samples_analyzed or 0,
        updated_at=profile.updated_at,
    )
```

### Backend: PATCH /email/voice-profile (tone + sign_off only)
```python
class VoiceProfilePatch(BaseModel):
    tone: str | None = None
    sign_off: str | None = None

@router.patch("/voice-profile")
async def update_voice_profile(
    body: VoiceProfilePatch,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> VoiceProfileResponse:
    result = await db.execute(
        select(EmailVoiceProfile).where(
            EmailVoiceProfile.tenant_id == user.tenant_id,
            EmailVoiceProfile.user_id == user.sub,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="No voice profile found")

    values = {}
    if body.tone is not None:
        values["tone"] = body.tone
    if body.sign_off is not None:
        values["sign_off"] = body.sign_off
    if values:
        values["updated_at"] = datetime.now(timezone.utc)
        await db.execute(
            update(EmailVoiceProfile)
            .where(
                EmailVoiceProfile.tenant_id == user.tenant_id,
                EmailVoiceProfile.user_id == user.sub,
            )
            .values(**values)
        )
        await db.commit()
    # Re-fetch and return updated profile
    # ...
```

### Backend: POST /email/voice-profile/reset
```python
@router.post("/voice-profile/reset")
async def reset_voice_profile(
    background_tasks: BackgroundTasks,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    # Verify Gmail integration exists
    intg_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == user.tenant_id,
            Integration.user_id == user.sub,
            Integration.provider == "gmail-read",
            Integration.status == "connected",
        )
    )
    integration = intg_result.scalars().first()
    if integration is None:
        raise HTTPException(status_code=400, detail="No Gmail integration connected")

    # Delete existing profile
    await db.execute(
        delete(EmailVoiceProfile).where(
            EmailVoiceProfile.tenant_id == user.tenant_id,
            EmailVoiceProfile.user_id == user.sub,
        )
    )
    await db.commit()

    # Re-extract in background (voice_profile_init now sees no existing row)
    integration_id = integration.id
    tenant_id = str(user.tenant_id)
    user_id = str(user.sub)

    async def _run_relearn():
        factory = get_session_factory()
        async with tenant_session(factory, tenant_id, user_id) as bg_db:
            fresh = await bg_db.execute(
                select(Integration).where(Integration.id == integration_id)
            )
            intg = fresh.scalar_one_or_none()
            if intg:
                await voice_profile_init(bg_db, intg)

    background_tasks.add_task(_run_relearn)
    return {"status": "relearning"}
```

### Frontend: VoiceProfileSettings component structure
```tsx
// Key patterns from existing settings components:
const { data: profile, isLoading } = useQuery({
  queryKey: ['voice-profile'],
  queryFn: () => api.get<VoiceProfile | null>('/email/voice-profile'),
})

const saveMutation = useMutation({
  mutationFn: (updates: { tone?: string; sign_off?: string }) =>
    api.patch('/email/voice-profile', updates),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['voice-profile'] })
    toast.success('Voice profile updated')
  },
})

const resetMutation = useMutation({
  mutationFn: () => api.post('/email/voice-profile/reset'),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['voice-profile'] })
    toast.success('Re-learning your voice from sent emails...')
    setResetDialogOpen(false)
  },
})
```

### The 10 Voice Profile Fields (display mapping)
| DB Field | Display Label | Type | Editable? |
|----------|--------------|------|-----------|
| tone | Tone | text | YES |
| sign_off | Sign-off | text | YES |
| avg_length | Average Length | int (words) | No |
| phrases | Signature Phrases | string[] | No |
| formality_level | Formality | text | No |
| greeting_style | Greeting Style | text | No |
| question_style | Question Style | text | No |
| paragraph_pattern | Paragraph Pattern | text | No |
| emoji_usage | Emoji Usage | text | No |
| avg_sentences | Avg Sentences | int | No |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 4-field voice profile | 10-field voice profile | Phase 70 (v7.0) | All 10 fields available in DB |
| 20-sample extraction | 50-sample extraction | Phase 70 (v7.0) | Better voice quality |
| No user visibility | Settings UI for voice | Phase 71 (this phase) | Users see + edit their profile |

## Open Questions

1. **GET endpoint returning null vs 404**
   - What we know: When no profile exists, the endpoint could return null/empty or 404
   - Recommendation: Return `null` (HTTP 200 with null body) -- this is cleaner for the frontend which needs to distinguish "no profile" from "error". The frontend shows the empty state ("Connect Gmail to get started") when profile is null.

2. **Polling after reset**
   - What we know: Reset triggers background extraction (takes 30-60 seconds). Frontend needs to know when it's done.
   - Recommendation: Simple approach -- after reset, show "Re-learning..." message. The component can poll GET every 5 seconds for a short period, or user can manually refresh. Avoid WebSocket complexity for a rare operation.

3. **PATCH semantics for empty string vs null**
   - What we know: User might want to clear tone or sign_off
   - Recommendation: Accept both empty string and null as "clear this field". Use `None` in the Pydantic model with explicit field presence checking.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/db/models.py` lines 1050-1101 -- EmailVoiceProfile model with all 10 fields
- `backend/src/flywheel/api/email.py` -- existing email router, endpoint patterns, auth deps
- `backend/src/flywheel/api/deps.py` -- `require_tenant`, `get_tenant_db` dependency chain
- `backend/src/flywheel/services/gmail_sync.py` lines 845-949 -- `voice_profile_init()` function
- `backend/src/flywheel/engines/email_voice_updater.py` -- voice update patterns and field list
- `frontend/src/pages/SettingsPage.tsx` -- tab structure, conditional rendering
- `frontend/src/features/settings/components/TenantSettings.tsx` -- inline edit + save pattern
- `frontend/src/features/settings/components/GranolaSettings.tsx` -- integration status, mutation + toast
- `frontend/src/lib/api.ts` -- API client with `get/post/patch/put/delete` methods

### Secondary (MEDIUM confidence)
- `.planning/phases/70-voice-profile-overhaul/70-RESEARCH.md` -- Phase 70 context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already in project, zero new packages
- Architecture: HIGH -- follows exact patterns from existing settings components and email endpoints
- Pitfalls: HIGH -- identified from direct code reading, particularly the idempotency guard in voice_profile_init()
- Code examples: HIGH -- derived directly from existing codebase patterns

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- no external dependencies or evolving APIs)
