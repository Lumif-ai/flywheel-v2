# Phase 63: Meeting Prep Loop - Research

**Researched:** 2026-03-28
**Domain:** Python backend (account-scoped meeting prep endpoint, context store reader, LLM briefing generation); React frontend (prep trigger, SSE streaming, briefing viewer)
**Confidence:** HIGH

## Summary

Phase 63 is the "flywheel closes" phase — the system that produces actionable meeting briefings by reading all the enriched intelligence that phases 60-62 have been writing. The key architectural insight is that a **significant portion of both the backend engine and the frontend viewer already exist**. The `_execute_meeting_prep` function in `skill_executor.py` is a fully-working web prep engine (~600 LOC) that reads from the context store and generates HTML briefings via LLM. The `MeetingPrepRenderer.tsx` component renders those briefings. The SSE streaming infrastructure (`useSSE`, `SkillRun`, `job_queue_loop`) is battle-tested across three prior phases.

What is missing is the **account-scoped trigger surface**. The existing `_execute_meeting_prep` was built for the onboarding flow (LinkedIn URL as primary identifier, web research first). Phase 63 needs a new variant that starts from an **account_id** — reading `ContextEntry` rows already linked to that account via the pipeline from phases 60-62, constructing a structured briefing prompt from account-scoped intel, and producing the same HTML output. This is a new execution path inside `skill_executor.py` and a new API endpoint (not a change to the existing onboarding path).

The frontend work is two trigger surfaces (meetings page and relationship detail page), the SSE progress display, and a briefing viewer. All three are additive — no existing components need to be modified except adding a "Prep" button to already-built pages.

**Primary recommendation:** Build in two plans: (1) Backend — new `POST /relationships/{id}/prep` endpoint + new `_execute_account_meeting_prep()` in skill_executor that reads account-scoped ContextEntry rows (INTEL_FILES + contacts + action-items) and generates an HTML briefing via LLM; (2) Frontend — prep trigger button on MeetingDetailPage and RelationshipDetail, SSE streaming via the existing useSSE + stream URL pattern, and a PrepBriefingViewer component using the existing MeetingPrepRenderer.

## Standard Stack

### Core (all already installed — no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | Prep endpoint | Already used by all API routes |
| SQLAlchemy async | 2.0.x | Account-scoped ContextEntry queries | Used by `relationships.py` for the same INTEL_FILES pattern |
| AsyncAnthropic | latest | LLM briefing generation | Used by `_execute_meeting_prep` and all skill executors |
| sse-starlette | 2.x | SSE streaming | Already wired in `skills.py` |
| @tanstack/react-query | ^5.91.2 | Data fetching and mutation | Standard for all hooks |
| react-router | ^7.13.1 | Navigation to briefing view | Already used in meeting and relationship pages |
| lucide-react | ^0.577.0 | Loading/progress icons | Already installed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `MeetingPrepRenderer` | (internal) | Render HTML briefings | Already exists in `features/documents/components/renderers/` |
| `useSSE` | (internal `/lib/sse.ts`) | Stream prep events | Already used by OnboardingMeetingPrep |
| `MeetingPrepRenderer.tsx` | (internal) | Briefing HTML display | Re-use exactly as-is |

### No New npm Packages Needed

All required frontend libraries are present. The SSE event types (`stage`, `done`, `error`) are already defined.

### Backend: No New Dependencies

`_execute_meeting_prep` already imports everything needed (anthropic, SQLAlchemy, asyncio). The account-scoped variant reuses the same imports.

## Architecture Patterns

### Key Existing Infrastructure to Reuse

```
backend/src/flywheel/
├── services/skill_executor.py    # _execute_meeting_prep: REUSE this pattern (account variant)
├── api/relationships.py          # INTEL_FILES constant: account-scoped context query
├── api/skills.py                 # SSE streaming endpoint: REUSE exactly
├── services/job_queue.py         # Picks up pending SkillRuns: NO CHANGES NEEDED
└── db/models.py                  # SkillRun model: NO CHANGES NEEDED

frontend/src/
├── features/documents/components/renderers/MeetingPrepRenderer.tsx  # REUSE as-is
├── features/onboarding/components/OnboardingMeetingPrep.tsx         # SSE pattern to follow
├── features/meetings/components/MeetingDetailPage.tsx               # ADD prep button here
└── features/relationships/components/RelationshipDetail.tsx         # ADD prep button here
```

### Recommended New Structure

```
backend/src/flywheel/
└── api/
    └── relationships.py           # ADD: POST /relationships/{id}/prep

frontend/src/
├── features/relationships/
│   ├── api.ts                     # ADD: triggerRelationshipPrep(id)
│   ├── hooks/
│   │   └── useRelationshipPrep.ts # NEW: mutation + SSE state machine
│   └── components/
│       └── PrepBriefingPanel.tsx  # NEW: trigger + streaming + viewer
└── features/meetings/
    └── components/
        └── MeetingDetailPage.tsx  # MODIFY: add prep button (account_id present)
```

### Pattern 1: Account-Scoped Prep Execution Path

**What:** New `_execute_account_meeting_prep()` coroutine in `skill_executor.py` that reads ContextEntry rows by `account_id` instead of researching via LinkedIn URL.

**When to use:** When triggered from a relationship page or meeting page where `account_id` is known.

**How it differs from `_execute_meeting_prep`:**
- Input: `account_id` UUID + optional meeting_id UUID (for meeting-specific context)
- Stage 1b: Queries `ContextEntry` rows scoped to `account_id` using the same `INTEL_FILES` list as `relationships.py` (6 file types: competitive-intel, pain-points, icp-profiles, insights, action-items, product-feedback) PLUS contacts
- Stage 2: Skips web research entirely (context store is the intelligence source)
- Stage 3: Passes structured intel sections to briefing LLM
- Stage 4: Same HTML generation as existing `_execute_meeting_prep`
- Stage 5: No writeback needed (context store already has the data)

**Input text format for SkillRun.input_text:**
```
Account-ID: {account_id}
Meeting-ID: {meeting_id}  # optional
Account-Name: {account_name}
```

**Dispatch in `execute_run()`:**
```python
# In the existing dispatch block
is_account_meeting_prep = run.skill_name == "meeting-prep" and run.input_text and run.input_text.startswith("Account-ID:")
if is_account_meeting_prep:
    output, token_usage, tool_calls = await _execute_account_meeting_prep(...)
elif is_meeting_prep:
    output, token_usage, tool_calls = await _execute_meeting_prep(...)
```

### Pattern 2: New Prep API Endpoint

**What:** `POST /relationships/{id}/prep` creates a SkillRun and returns `{run_id, stream_url}`.

**Why a new endpoint instead of `POST /skills/runs`:**
- Enforces `account_id` scoping (tenant + graduated_at check)
- Returns the `stream_url` directly for convenience
- Follows the same pattern as `POST /meetings/{id}/process`

```python
# Source: meetings.py POST /{id}/process pattern
@router.post("/relationships/{id}/prep")
async def prep_relationship(
    id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Trigger meeting prep for a relationship. Returns run_id + stream_url."""
    # Verify account exists and is graduated (partition predicate)
    account = await _get_graduated_account(db, id, user.tenant_id)

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="meeting-prep",
        input_text=f"Account-ID: {id}\nAccount-Name: {account.name}",
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.commit()

    return {
        "run_id": str(run.id),
        "stream_url": f"/api/v1/skills/runs/{run.id}/stream",
    }
```

### Pattern 3: Account Context Reader

**What:** `_read_account_context()` helper that queries all intel ContextEntry rows for an account.

**Reuses:** The exact `INTEL_FILES` list and query pattern from `relationships.py` (`get_relationship` endpoint lines 415-427).

```python
# Source: relationships.py intel_entries_result query
PREP_CONTEXT_FILES = [
    "contacts",           # person names + roles
    "competitive-intel",  # competitor mentions
    "pain-points",        # known pain
    "icp-profiles",       # ICP fit signals
    "insights",           # meeting insights
    "action-items",       # open commitments
    "product-feedback",   # product feedback
]

async def _read_account_context(
    factory: async_sessionmaker,
    tenant_id: UUID,
    account_id: UUID,
) -> dict[str, list[str]]:
    """Return {file_name: [content, ...]} for all intel ContextEntry rows for the account."""
    async with factory() as session:
        await session.execute(sa_text("SET app.tenant_id = :tid"), {"tid": str(tenant_id)})
        rows = (await session.execute(
            select(ContextEntry.file_name, ContextEntry.content, ContextEntry.date)
            .where(
                ContextEntry.account_id == account_id,
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.deleted_at.is_(None),
                ContextEntry.file_name.in_(PREP_CONTEXT_FILES),
            )
            .order_by(ContextEntry.date.desc())
            .limit(100)
        )).all()

    by_file: dict[str, list[str]] = {}
    for file_name, content, date in rows:
        if content:
            by_file.setdefault(file_name, []).append(content)
    return by_file
```

### Pattern 4: Frontend SSE State Machine

**What:** React hook `useRelationshipPrep` following the exact pattern of `OnboardingMeetingPrep.tsx`.

**SSE event types consumed (already defined in existing SSEEventType union):**
- `stage` → update status message (data.message)
- `done` → extract data.rendered_html, set phase='done'
- `error` → set error message, phase='idle'

```typescript
// Source: OnboardingMeetingPrep.tsx SSE pattern
export function useRelationshipPrep(accountId: string) {
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>('idle')
  const [status, setStatus] = useState<string | null>(null)
  const [briefingHtml, setBriefingHtml] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sseUrl, setSseUrl] = useState<string | null>(null)

  const handleEvent = useCallback((event: SSEEvent) => {
    const data = event.data as Record<string, unknown>
    switch (event.type) {
      case 'stage': setStatus(data.message as string); break
      case 'done':
        setBriefingHtml((data.rendered_html as string) ?? '')
        setPhase('done')
        setSseUrl(null)
        break
      case 'error':
        setError(data.message as string ?? 'Prep failed')
        setPhase('idle')
        setSseUrl(null)
        break
    }
  }, [])

  useSSE(sseUrl, handleEvent)

  const startPrep = async () => {
    setPhase('running')
    setError(null)
    setBriefingHtml(null)
    const res = await api.post<{ run_id: string; stream_url: string }>(
      `/relationships/${accountId}/prep`
    )
    setSseUrl(`/api/v1/skills/runs/${res.run_id}/stream`)
  }

  return { phase, status, briefingHtml, error, startPrep }
}
```

### Pattern 5: Briefing Prompt Structure

**What:** The `_generate_account_briefing()` sync function (run in `asyncio.to_thread`) builds the LLM prompt from structured account intel.

**Briefing sections** (from success criteria):
1. Relationship summary — account name, type, last interaction, signal count
2. Known pain points — from pain-points ContextEntries
3. Open action items — from action-items ContextEntries
4. Competitive landscape — from competitive-intel ContextEntries
5. Suggested questions — derived from the above intel

**System prompt:** Reuse the meeting-prep SKILL.md prompt (loaded from DB first, filesystem fallback) with an override block that says "context store intel has already been collected, generate the briefing from the structured data below."

**User message format:**
```
Generate a meeting prep briefing for [Account Name].

## Account Summary
- Type: [customer/prospect/advisor/investor]
- Last interaction: [date]

## Known Pain Points
[formatted list from pain-points file]

## Open Action Items
[formatted list from action-items file]

## Competitive Intel
[formatted list from competitive-intel file]

## Contact Intelligence
[formatted list from contacts file]

## ICP Fit Signals
[formatted list from icp-profiles file]

## Meeting Insights
[formatted list from insights file]
```

### Anti-Patterns to Avoid

- **Triggering web research for account-scoped prep:** The context store IS the intelligence. The whole point of phases 60-62 was to build this. Do not call `_research_person()` or `_research_company()` in the account-scoped path.
- **Using POST /skills/runs for prep trigger:** The existing `POST /skills/runs` endpoint validates against `skill_definitions` table and doesn't enforce account partition predicates. Use the dedicated prep endpoint.
- **Building a new SSE stream:** `GET /api/v1/skills/runs/{run_id}/stream` already handles late-connect replay and polling. Just use it.
- **Modifying `_execute_meeting_prep`:** The existing function serves the onboarding flow and is working. Add `_execute_account_meeting_prep` as a new function, dispatch on the input format.
- **Storing the briefing as a ContextEntry:** Briefings are ephemeral — they're stored on `SkillRun.rendered_html`. The spec says "user-initiated only (no auto-trigger in v1)" and there's no spec requirement to persist briefing HTML beyond the SkillRun record.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming | Custom event emitter | `GET /api/v1/skills/runs/{run_id}/stream` | Already handles late-connect replay, polling, done/error events |
| HTML sanitization | Custom sanitizer | `sanitizeHTML` from `@/lib/sanitize` | Already used by MeetingPrepRenderer — same output format |
| Briefing HTML rendering | Custom HTML renderer | `MeetingPrepRenderer` component | Already handles inline-style HTML from LLM with design-token overrides |
| Account context query | Custom ORM query | Mirror `INTEL_FILES` query from `relationships.py` lines 415-427 | The exact same query pattern, already optimized |
| SSE hook | Custom EventSource wrapper | `useSSE` from `@/lib/sse` | Already handles auth (token in query param), reconnect |
| LLM prompt loading | Hardcoded prompt | `_load_skill_from_db(factory, "meeting-prep")` with filesystem fallback | Consistent with how `_execute_meeting_prep` loads the SKILL.md |

## Common Pitfalls

### Pitfall 1: Input Text Parsing Collision
**What goes wrong:** The existing `execute_run()` dispatch checks `run.skill_name == "meeting-prep"` for ALL meeting prep runs and routes them to `_execute_meeting_prep`. An account-scoped run with `input_text="Account-ID: ..."` would get passed to the LinkedIn-URL-based function, which would try to parse a LinkedIn URL and produce a degraded briefing.
**Why it happens:** The dispatch uses `skill_name` only, not `input_text` format.
**How to avoid:** Add format detection BEFORE the existing `is_meeting_prep` branch:
```python
is_account_meeting_prep = (
    run.skill_name == "meeting-prep"
    and run.input_text
    and run.input_text.startswith("Account-ID:")
)
if is_account_meeting_prep:
    ...
elif is_meeting_prep:
    ...
```
**Warning signs:** Briefing says "the contact" instead of account name; LLM output is web-research-only with no context store intelligence.

### Pitfall 2: Missing Tenant Partition in Context Reader
**What goes wrong:** The `_read_account_context` helper queries ContextEntry without setting the RLS config parameter. Supabase RLS policies enforce `app.tenant_id` — forgetting to set it returns zero rows.
**Why it happens:** Easy to miss when writing a new async helper; existing code always includes it.
**How to avoid:** Always run `await session.execute(sa_text("SET app.tenant_id = :tid"), {"tid": str(tenant_id)})` before any ContextEntry query.
**Warning signs:** `by_file` dict is empty even though the account has processed meetings; no error raised.

### Pitfall 3: SSE URL Auth Token
**What goes wrong:** The frontend uses `useSSE(sseUrl, handleEvent)` but the `EventSource` API cannot send Authorization headers. The SSE endpoint requires a `?token=` query param.
**Why it happens:** `useSSE` handles this internally, but if building the URL manually you'd forget the token.
**How to avoid:** Use `useSSE` from `@/lib/sse` directly — it appends the token internally. Never construct the EventSource manually.
**Warning signs:** 401 errors in network tab on the stream URL.

### Pitfall 4: Empty Context Store for New Accounts
**What goes wrong:** Account exists but has no processed meetings yet (no ContextEntry rows with `account_id` set). The briefing LLM receives an empty intel dict and generates a placeholder briefing or errors.
**Why it happens:** The context store is populated by meeting processing — accounts that haven't had meetings processed yet have no intel.
**How to avoid:** In the backend, check `len(by_file) == 0` after reading context. Return a specific SSE `stage` event informing the user there's no context, then still generate a web-research fallback OR return a user-friendly error. The spec says "reads context store entries linked to the account" but doesn't require fallback — surface the gap clearly.
**Warning signs:** Briefing HTML is generic with no specific pain points or action items.

### Pitfall 5: SkillRun Not Visible in Job Queue
**What goes wrong:** The new `POST /relationships/{id}/prep` creates a SkillRun with `status="pending"` but the job queue worker never picks it up because `execute_run` doesn't have the account-scoped dispatch.
**Why it happens:** The job queue worker polls for `status="pending"` runs and calls `execute_run()` — if the new dispatch isn't in `execute_run`, the run stays pending forever.
**How to avoid:** Add the `is_account_meeting_prep` dispatch INSIDE `execute_run()` in `skill_executor.py`, not in a separate code path.
**Warning signs:** SSE stream never emits `stage` events after the `run_id` is returned; run stays `pending` in DB.

## Code Examples

### Account Intel Query (mirrors relationships.py exactly)

```python
# Source: relationships.py lines 415-427 — exact same pattern
intel_entries_result = await db.execute(
    select(ContextEntry)
    .where(
        ContextEntry.account_id == account_id,
        ContextEntry.tenant_id == tenant_id,
        ContextEntry.deleted_at.is_(None),
        ContextEntry.file_name.in_(PREP_CONTEXT_FILES),
    )
    .order_by(ContextEntry.date.desc())
    .limit(100)  # More than the 50 in relationships.py — prep needs full picture
)
intel_entries = intel_entries_result.scalars().all()
```

### SSE Event Emission (existing pattern)

```python
# Source: skill_executor.py _append_event_atomic — already exists
await _append_event_atomic(factory, run_id, {
    "event": "stage",
    "data": {"stage": "reading_context", "message": f"Reading intelligence for {account_name}..."},
})
```

### Briefing Prompt Construction

```python
# Construct user message from structured intel
sections = []
if by_file.get("pain-points"):
    sections.append("## Known Pain Points\n" + "\n".join(f"- {c}" for c in by_file["pain-points"][:5]))
if by_file.get("action-items"):
    sections.append("## Open Action Items\n" + "\n".join(f"- {c}" for c in by_file["action-items"][:5]))
if by_file.get("competitive-intel"):
    sections.append("## Competitive Intel\n" + "\n".join(f"- {c}" for c in by_file["competitive-intel"][:5]))
if by_file.get("contacts"):
    sections.append("## Contacts\n" + "\n".join(f"- {c}" for c in by_file["contacts"][:5]))

user_content = f"Generate a meeting prep briefing for {account_name}.\n\n" + "\n\n".join(sections)
```

### Frontend Prep Button Pattern

```typescript
// Source: MeetingDetailPage.tsx "Process" button pattern
const { phase, status, briefingHtml, error, startPrep } = useRelationshipPrep(accountId)

<Button
  onClick={startPrep}
  disabled={phase === 'running'}
  variant="default"
  size="sm"
>
  {phase === 'running'
    ? <><Loader2 className="size-4 mr-2 animate-spin" />{status ?? 'Preparing...'}</>
    : 'Prep for Meeting'
  }
</Button>

{briefingHtml && (
  <MeetingPrepRenderer renderedHtml={briefingHtml} />
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LinkedIn URL as primary prep input | Account ID + context store as primary prep input | Phase 63 | No web research needed — intelligence is already in the store |
| Onboarding-only prep | Prep from any account/meeting surface | Phase 63 | Closes the flywheel loop |
| Generic prep briefing | Account-scoped briefing with relationship history | Phase 63 | Higher relevance: shows what's KNOWN, not what was researched |

**Existing / do not change:**
- `_execute_meeting_prep`: The onboarding/LinkedIn-URL-based path. Stays unchanged.
- `POST /onboarding/meeting-prep`: The anonymous-allowed onboarding endpoint. Stays unchanged.
- `GET /api/v1/skills/runs/{run_id}/stream`: The SSE stream endpoint. Stays unchanged.
- `MeetingPrepRenderer`: The briefing HTML renderer. Stays unchanged.

## Open Questions

1. **Should prep be triggerable from a specific meeting (not just from the relationship)?**
   - What we know: The spec says "trigger from meetings page OR relationship page"
   - What's unclear: If triggered from a meeting, should the briefing include meeting-specific context (attendees, meeting type, past meeting summary)?
   - Recommendation: Always pass `account_id`; optionally pass `meeting_id` in the input_text. The `_execute_account_meeting_prep` can enrich the prompt with meeting-specific data when `meeting_id` is present.

2. **What happens when the account has no processed meetings (empty context store)?**
   - What we know: The spec says "reads context store entries linked to the account" — no fallback mentioned.
   - What's unclear: Should it fall back to web research (like the onboarding path), show a friendly error, or still generate a partial briefing?
   - Recommendation: Show a friendly "Not enough context yet — process some meetings with this account first" message. Do not silently fall back to web research, as that would confuse the user about why the briefing looks generic.

3. **Briefing persistence: can the user re-view a past briefing?**
   - What we know: `SkillRun.rendered_html` persists the HTML. `GET /skills/runs/{run_id}` returns it. The `HistoryList` component shows past runs.
   - What's unclear: Should the prep UI link to the run in history, or just show the latest?
   - Recommendation: Show the latest generated briefing in the panel. The history list already surfaces all past runs. No new persistence logic needed.

## Sources

### Primary (HIGH confidence)

- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/services/skill_executor.py` — `_execute_meeting_prep` (lines 1743-2390), dispatch logic (lines 573-595, 663-666)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/relationships.py` — INTEL_FILES constant (lines 56-63), account intel query (lines 415-427)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/skills.py` — SSE stream endpoint (lines 299-400)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/meetings.py` — `POST /{id}/process` pattern (lines 360-390)
- `/Users/sharan/Projects/flywheel-v2/frontend/src/features/onboarding/components/OnboardingMeetingPrep.tsx` — complete SSE state machine pattern
- `/Users/sharan/Projects/flywheel-v2/frontend/src/features/documents/components/renderers/MeetingPrepRenderer.tsx` — briefing HTML renderer
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/engines/meeting_prep.py` — context reader helpers (`pre_read_context`, `find_company_context`, `synthesize_meeting_context`)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` — SkillRun model (lines 288-330)

### Secondary (MEDIUM confidence)

- Phase 62 RESEARCH.md — confirmed meetings feature slice structure, SSE hook, and relationship tabs are already built
- Phase 61 RESEARCH.md — confirmed ContextEntry rows have `account_id` set by meeting processor

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all confirmed from direct codebase inspection
- Architecture: HIGH — pattern directly mirrors existing implementations in codebase
- Pitfalls: HIGH — pitfalls derived from reading actual dispatch logic and RLS patterns in production code

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable codebase, 30-day window)
