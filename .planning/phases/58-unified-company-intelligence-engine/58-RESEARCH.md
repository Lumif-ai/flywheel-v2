# Phase 58: Unified Company Intelligence Engine - Research

**Researched:** 2026-03-27
**Domain:** Python backend engine extension + FastAPI endpoints + React frontend buttons/modals
**Confidence:** HIGH

## Summary

Phase 58 unifies two divergent paths for populating company intelligence: the skill engine path
(URL crawl → `_execute_company_intel`) and the background enrichment path (document upload →
`analyze_document` → `_run_background_enrichment`). After this phase, every source of company
intelligence — URL crawls, document uploads, refresh, and reset — flows through a single
`_execute_company_intel` function that has been extended to accept either a URL or raw document
text. The background enrichment side-path in `profile.py` is removed entirely.

The three plans map cleanly to three tiers of the stack. Plan 58-01 is pure Python engine work:
extending `_execute_company_intel` to accept a discriminated input (URL vs. document text), making
the enrichment prompt gap-aware by reading existing `company-intel-onboarding` entries before
issuing web searches, and adding the dedup-merge write path. Plan 58-02 is API layer work: routing
`POST /profile/analyze-document` through a SkillRun, adding `POST /profile/refresh` and
`POST /profile/reset` endpoints, and removing the `_run_background_enrichment` background task
path. Plan 58-03 is frontend work: adding Refresh and Reset buttons to `CompanyProfilePage`, a
confirmation modal for Reset, and wiring both actions to the existing SSE streaming UI already used
for URL crawls (`LiveCrawl` + `useProfileCrawl`).

The codebase is in excellent shape for this refactor. The `_execute_company_intel` function already
emits all the right SSE events (`stage`, `discovery`, `done`). The `useSSE` + `useProfileCrawl`
hook pattern is established and reusable. The `SkillRun` → `events_log` → `/skills/runs/{id}/stream`
SSE pipeline already handles late-connect replay. The only new behavioral logic is (1) the URL-vs-
document discriminator, (2) the gap-aware enrichment prompt, (3) the refresh content aggregation
(URL crawl + all linked document texts), and (4) the soft-delete + re-run reset flow.

**Primary recommendation:** Implement plans in order 58-01 → 58-02 → 58-03. Each plan is
independently deployable and the engine change (58-01) is a prerequisite for the API changes
(58-02) which are a prerequisite for the frontend changes (58-03).

---

## Standard Stack

No new libraries are needed. All dependencies are already installed and in use.

### Core (existing, verified in use)
| Component | Location | Purpose | How Phase 58 Uses It |
|-----------|----------|---------|----------------------|
| `flywheel.engines.company_intel` | `backend/src/flywheel/engines/company_intel.py` | Crawl, structure, enrich functions | Extended with document text path |
| `flywheel.services.skill_executor._execute_company_intel` | `backend/src/flywheel/services/skill_executor.py:811` | Async engine orchestrator | Extended to accept URL or doc text; gap-aware enrichment added |
| `flywheel.storage.append_entry` | `backend/src/flywheel/storage.py:89` | Async context entry writer | Used in refresh/reset write paths |
| `flywheel.db.models.SkillRun` | `backend/src/flywheel/db/models.py:288` | Job record + events_log | Created by analyze-document, refresh, reset |
| `flywheel.db.models.ContextEntry` | `backend/src/flywheel/db/models.py:182` | Company intel storage | Soft-deleted on reset, read for gap analysis |
| `sse_starlette.sse.EventSourceResponse` | FastAPI dependency | SSE streaming | Existing crawl stream pattern reused |
| `useSSE` | `frontend/src/lib/sse.ts` | Frontend SSE client | Reused for refresh/reset streaming |
| `useProfileCrawl` | `frontend/src/features/profile/hooks/useProfileCrawl.ts` | SSE state management | Extended or cloned for refresh/reset |
| `LiveCrawl` | `frontend/src/features/onboarding/components/LiveCrawl.tsx` | Discovery streaming UI | Reused for refresh/reset progress |

### No New Dependencies
```bash
# No npm install or pip install needed for Phase 58
```

---

## Architecture Patterns

### Pattern 1: URL vs. Document Text Discriminator in `_execute_company_intel`

The function currently takes `input_text: str` and treats it as a URL. The extension adds a
discriminator: if `input_text` starts with `DOCUMENT:` (a sentinel prefix), skip the crawl stage
and treat the rest as pre-extracted document text. Otherwise, treat as URL.

**What:** Single entrypoint that handles both inputs without overloading the signature.
**When to use:** Any time `_execute_company_intel` is called — engine decides internally.

```python
# In _execute_company_intel
DOCUMENT_PREFIX = "DOCUMENT:"

async def _execute_company_intel(
    api_key: str,
    input_text: str,           # URL or "DOCUMENT:<extracted_text>"
    factory: async_sessionmaker,
    run_id: UUID,
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> tuple[str, dict, list]:
    url = input_text.strip()
    is_document = url.startswith(DOCUMENT_PREFIX)

    if is_document:
        # Skip Stage 1 (crawl), go straight to Stage 2 (structure)
        raw_text = url[len(DOCUMENT_PREFIX):]
        pages_crawled = 0
        await _append_event_atomic(factory, run_id, {
            "event": "stage",
            "data": {"stage": "structuring", "message": "Analyzing document..."},
        })
    else:
        # Stage 1: crawl
        crawl_result = await crawl_company(url)
        raw_text = ...
        pages_crawled = crawl_result.get("pages_crawled", 0)
        # ... existing crawl events ...
```

**Source:** Verified by reading `skill_executor.py:811-1191` — current flow is URL-only.

### Pattern 2: Gap-Aware Enrichment Prompt

The `enrich_with_web_research` function in `company_intel.py` currently builds `known_summary` from
the in-memory `intelligence` dict (what was just extracted from the URL or document). After Phase 58,
it also reads the tenant's existing `company-intel-onboarding` context entries and focuses searches
on keys that are still empty or missing.

**What:** Before issuing web searches, read all existing profile entries and list what is already
known vs. what is missing. The enrichment prompt says "we already have X — focus research on Y."
**When to use:** In `enrich_with_web_research`, after building `known_summary`, before sending to
the LLM.

```python
# Read existing entries to find gaps
async def _get_existing_profile_summary(
    factory: async_sessionmaker,
    tenant_id: UUID,
) -> dict:
    """Returns dict of what's already populated in the tenant's profile."""
    async with factory() as session:
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        rows = (await session.execute(
            select(ContextEntry.file_name, ContextEntry.content).where(
                ContextEntry.tenant_id == tenant_id,
                ContextEntry.source == "company-intel-onboarding",
                ContextEntry.deleted_at.is_(None),
            )
        )).all()
    # Map file_name -> has_content bool
    return {file_name: bool(content) for file_name, content in rows}
```

The enrichment prompt is then updated to say: "Already have: [X, Y]. Missing: [A, B, C]. Focus research on missing fields."

### Pattern 3: SkillRun-Routed Document Analysis

`POST /profile/analyze-document` currently calls `structure_intelligence` directly and runs
`_run_background_enrichment` as a `BackgroundTasks` task. After Phase 58 it creates a `SkillRun`
and enqueues it exactly like `POST /onboarding/crawl`.

```python
@router.post("/analyze-document")
async def analyze_document(
    body: AnalyzeDocumentRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    # Fetch uploaded file, get extracted_text
    uploaded = ...
    extracted_text = uploaded.extracted_text

    # Create SkillRun with DOCUMENT: prefix sentinel
    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=f"DOCUMENT:{extracted_text}",
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await db.commit()

    return {"run_id": str(run.id)}
```

Frontend connects to `/api/v1/skills/runs/{run_id}/stream` (or the existing onboarding crawl stream
endpoint pattern) for SSE events.

### Pattern 4: Refresh Endpoint

`POST /profile/refresh` re-runs company intelligence with ALL available sources: the tenant's URL
(from `tenant.domain`) plus the extracted text from all linked document files. This produces a
single SkillRun whose `input_text` aggregates all sources.

```python
@router.post("/refresh")
async def refresh_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    # Get tenant URL
    tenant = (await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )).scalar_one_or_none()

    # Get all linked document texts
    linked_files = (await db.execute(
        select(UploadedFile).where(
            UploadedFile.tenant_id == user.tenant_id,
            # filter: metadata_->>'profile_linked' = 'true'
        )
    )).scalars().all()
    doc_texts = [f.extracted_text for f in linked_files if f.extracted_text]

    # Build input: URL + docs, or docs only if no URL
    if tenant and tenant.domain:
        url = f"https://{tenant.domain}"
        # URL crawl is the primary input; docs are secondary
        # Pack doc texts into input as supplementary
        doc_payload = "\n---\n".join(doc_texts) if doc_texts else ""
        input_text = f"{url}\n\nSUPPLEMENTARY_DOCS:\n{doc_payload}" if doc_payload else url
    elif doc_texts:
        input_text = f"DOCUMENT:{chr(10).join(doc_texts)}"
    else:
        raise HTTPException(400, detail="No URL or documents available to refresh from")

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="company-intel",
        input_text=input_text,
        status="pending",
    )
    ...
    return {"run_id": str(run.id)}
```

### Pattern 5: Reset Endpoint — Soft-Delete Then Refresh

`POST /profile/reset` soft-deletes all `company-intel-onboarding` context entries for the tenant,
then calls the same refresh logic. The soft-delete sets `deleted_at = now()` and does NOT do a
hard delete, preserving audit history.

```python
@router.post("/reset")
async def reset_profile(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    from datetime import datetime, timezone
    from sqlalchemy import update as sa_update

    # Soft-delete all company-intel-onboarding entries
    await db.execute(
        sa_update(ContextEntry)
        .where(
            ContextEntry.tenant_id == user.tenant_id,
            ContextEntry.source == "company-intel-onboarding",
            ContextEntry.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()

    # Then run the same refresh flow
    return await refresh_profile(user=user, db=db)
```

### Pattern 6: Frontend SSE Reuse Pattern

The `useProfileCrawl` hook and `LiveCrawl` component already implement the full SSE lifecycle for
URL crawls. The Refresh and Reset buttons follow the exact same pattern:

1. Button click → POST to `/profile/refresh` or `/profile/reset` → get `run_id`
2. Set `sseUrl` to `/api/v1/skills/runs/{run_id}/stream` (or `/api/v1/onboarding/crawl/{run_id}/stream`)
3. `useSSE` connects and streams events into `crawlItems` state
4. `LiveCrawl` renders the discovery stream

The `useProfileCrawl` hook can be extended with a `startRefresh()` and `startReset()` action, or a
new `useProfileRefresh` hook can be created that reuses the same state shape. Prefer extending the
existing hook to avoid duplication.

### Pattern 7: Confirmation Modal for Reset

Reset is destructive (soft-deletes all profile data then re-runs). Use a simple inline confirmation
pattern — not a modal component — since the design system doesn't have a reusable Modal component.
Instead: clicking Reset reveals an inline confirmation row ("Are you sure? This will clear your
current profile. [Confirm Reset] [Cancel]"). This is consistent with the existing edit/cancel
patterns in `CategoryCard`.

### Recommended Project Structure (files touched)

```
backend/src/flywheel/
├── engines/
│   └── company_intel.py          # [MODIFY] gap-aware enrichment prompt; _get_existing_profile_summary helper
├── services/
│   └── skill_executor.py         # [MODIFY] _execute_company_intel: URL vs DOCUMENT discriminator; SUPPLEMENTARY_DOCS handling; gap-aware enrichment call
├── api/
│   └── profile.py                # [MODIFY] analyze-document → SkillRun route; add /refresh, /reset; remove _run_background_enrichment

frontend/src/features/profile/
├── components/
│   └── CompanyProfilePage.tsx    # [MODIFY] add Refresh + Reset buttons, inline reset confirmation, SSE stream overlay
└── hooks/
    └── useProfileCrawl.ts        # [MODIFY] add startRefresh() + startReset() actions; or create useProfileActions.ts
```

### Anti-Patterns to Avoid

- **Keeping `_run_background_enrichment` alive alongside the new SkillRun path:** Remove it
  entirely. The enrichment path must be unified — two paths means two places to update when the
  engine changes.
- **Adding a new SSE endpoint for profile refresh:** Reuse the existing
  `/api/v1/onboarding/crawl/{run_id}/stream` or `/api/v1/skills/runs/{run_id}/stream` endpoint.
  No new SSE route needed.
- **Hard-deleting context entries on reset:** Always soft-delete with `deleted_at`. Hard deletes
  cannot be undone and lose audit history.
- **Re-running enrichment on every document structuring call (same 10 searches):** The gap-aware
  prompt is the key fix. Read existing profile before enriching; only research what's missing.
- **Triggering refresh/reset automatically:** Prior decisions state AI synthesis never auto-triggers
  on page load. Refresh and Reset are always explicit user actions.
- **Blocking the HTTP response while the engine runs:** All three new endpoints (analyze-document,
  refresh, reset) must return a `run_id` immediately and let the job queue worker execute the
  engine asynchronously.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE event streaming | New SSE endpoint | `/api/v1/onboarding/crawl/{run_id}/stream` or `/api/v1/skills/runs/{run_id}/stream` | Both already handle late-connect replay, auth via query param |
| Frontend streaming UI | New streaming component | `LiveCrawl` + `useProfileCrawl` | Already handles `stage`, `text`, `done`, `crawl_error` events |
| Context store writes | Custom INSERT logic | `storage.append_entry()` | Handles dedup, catalog upsert, RLS scoping |
| Async job execution | Inline awaiting | `SkillRun` with `status="pending"`, picked up by job queue worker | Worker already claims and executes pending runs |
| Document text extraction | Custom PDF/DOCX parser | `extract_from_document()` in `company_intel.py` (already in `UploadedFile.extracted_text`) | Text is pre-extracted at upload time; just read from `extracted_text` column |
| Dedup merge on refresh | Custom merge logic | `append_entry` with evidence deduplication already built in | The storage layer deduplicates entries with the same source |

**Key insight:** The engine, streaming, and storage infrastructure are all built and working. Phase 58
is primarily an integration refactor — routing existing paths through a unified entrypoint — not
new infrastructure.

---

## Common Pitfalls

### Pitfall 1: DOCUMENT: Sentinel Prefix Truncation
**What goes wrong:** Document text can be very long (10MB+). If `input_text` is stored in the
`SkillRun.input_text` column and the extracted text is large, it could hit DB column limits or
cause performance issues.
**Why it happens:** The `SkillRun.input_text` column is `Text` type (unlimited in Postgres), but
sending megabytes through the job queue is wasteful.
**How to avoid:** Store only a reference in `input_text` (e.g., `DOCUMENT_FILE:{file_id}`) rather
than the full text. The engine then fetches `UploadedFile.extracted_text` by `file_id` at execution
time. This keeps `SkillRun.input_text` small and avoids duplicating the document text.
**Warning signs:** `input_text` columns containing many kilobytes of text in `skill_runs` table.

### Pitfall 2: Refresh with No URL and No Documents
**What goes wrong:** A tenant who only has guided-question answers (Tier 3) or who never linked
any documents has no URL in `tenant.domain` and no linked files. Calling refresh returns 400.
**Why it happens:** The refresh logic requires at least one source to work from.
**How to avoid:** In the refresh endpoint, check both `tenant.domain` and linked document count.
If neither is available, return 400 with a clear message: "Add a company URL or upload a document
to refresh from." The frontend should grey out the Refresh button when there's nothing to refresh.
**Warning signs:** Refresh button active when profile has no URL or documents.

### Pitfall 3: Reset Before Background Enrichment Completes
**What goes wrong:** User clicks Reset while `_run_background_enrichment` is still running in the
background. The background task then writes enrichment results AFTER the soft-delete, recreating
entries.
**Why it happens:** The background task holds a reference to the enrichment data and doesn't check
if the profile was reset.
**How to avoid:** This pitfall is eliminated once 58-02 removes `_run_background_enrichment` entirely.
Until then (during implementation), the reset endpoint should be added only after the background
enrichment path is removed.
**Warning signs:** Profile shows data after reset.

### Pitfall 4: Gap-Aware Enrichment Reads Deleted Entries
**What goes wrong:** After a reset, the gap-aware query reads soft-deleted entries (no `deleted_at
IS NULL` filter) and thinks the profile is fully populated, suppressing web searches.
**Why it happens:** Missing `deleted_at.is_(None)` filter in the gap query.
**How to avoid:** Always filter `deleted_at.is_(None)` in the existing profile summary query. This
is the same filter used everywhere else in the codebase.
**Warning signs:** Enrichment does fewer searches than expected after a reset.

### Pitfall 5: Frontend Shows Refresh Stream Over Existing Profile
**What goes wrong:** When Refresh runs, the SSE stream overlay appears but the existing profile
cards are still visible underneath, creating a confusing layered state.
**Why it happens:** The `CrawlPanel` currently only shows when `!hasGroups`. On a refresh, the
profile already has groups.
**How to avoid:** Track a `refreshRunId` state in `CompanyProfilePage`. When set, render the
`LiveCrawl` overlay in a modal-like panel (or replace the profile body). On `done`, invalidate
`['company-profile']` query and clear `refreshRunId`. The same pattern as the existing `phase`
state in `useProfileCrawl`.

### Pitfall 6: RLS Context Not Set in Refresh/Reset DB Sessions
**What goes wrong:** The refresh/reset endpoints create new DB sessions for writing context entries
but forget to `SET app.tenant_id` and `SET app.user_id`, causing RLS failures.
**Why it happens:** The current `analyze_document` background task already has this pattern
(setting config twice per session). It's easy to forget in new endpoints.
**How to avoid:** Always use the `_execute_company_intel` path through the job queue worker, which
already handles RLS context setting correctly. The endpoints just create the `SkillRun` — the
worker sets RLS before writing.

---

## Code Examples

Verified patterns from codebase:

### Creating a SkillRun for engine execution (from `/onboarding/crawl`)
```python
# Source: backend/src/flywheel/api/onboarding.py:752-765
run = SkillRun(
    tenant_id=tenant_id,
    user_id=user.sub,
    skill_name="company-intel",
    input_text=body.url,
    status="pending",
)
db.add(run)
await db.flush()
await db.refresh(run)
await db.commit()
return {"run_id": str(run.id)}
```

### SSE stream endpoint pattern (from `/onboarding/crawl/{run_id}/stream`)
```python
# Source: backend/src/flywheel/api/onboarding.py:769-860
# Existing stream endpoint polls SkillRun.events_log every 1 second
# Handles: discovery, stage, crawl_error, done events
# Auth: JWT via ?token= query param (EventSource can't send headers)
```

### Soft-deleting context entries
```python
# Source: same pattern as used in other cleanup paths
from sqlalchemy import update as sa_update
await db.execute(
    sa_update(ContextEntry)
    .where(
        ContextEntry.tenant_id == user.tenant_id,
        ContextEntry.source == "company-intel-onboarding",
        ContextEntry.deleted_at.is_(None),
    )
    .values(deleted_at=datetime.now(timezone.utc))
)
await db.commit()
```

### Reading existing profile entries for gap detection
```python
# Source: same query pattern as GET /profile (profile.py:94-101)
entries_result = await db.execute(
    select(ContextEntry).where(
        ContextEntry.deleted_at.is_(None),
        ContextEntry.source == "company-intel-onboarding",
    )
)
entries = entries_result.scalars().all()
populated_files = {e.file_name for e in entries if e.content and e.content.strip()}
```

### Frontend: starting a crawl and connecting SSE
```typescript
// Source: frontend/src/features/profile/hooks/useProfileCrawl.ts:95-114
const startCrawl = useCallback(async (url: string) => {
  setPhase('crawling')
  const res = await api.post<{ run_id: string }>('/onboarding/crawl', { url })
  setSseUrl(`/api/v1/onboarding/crawl/${res.run_id}/stream`)
}, [])

// useSSE connects to sseUrl and dispatches events to handleEvent callback
useSSE(sseUrl, handleEvent)
```

### Frontend: invalidating profile query on SSE done
```typescript
// Source: frontend/src/features/profile/hooks/useProfileCrawl.ts:59-63
case 'done': {
  setPhase('complete')
  queryClient.invalidateQueries({ queryKey: ['company-profile'] })
  break
}
```

---

## State of the Art

| Old Approach | New Approach (Phase 58) | Impact |
|---|---|---|
| `analyze_document` calls `structure_intelligence` directly in-request | Routes through SkillRun → job queue → `_execute_company_intel` | SSE streaming, unified events, proper attribution |
| `_run_background_enrichment` as FastAPI BackgroundTasks | Removed; enrichment is part of `_execute_company_intel` inline flow | One code path, observable via SSE, no orphaned background tasks |
| Enrichment always does same 10 web searches | Gap-aware enrichment reads existing profile first | Fewer redundant searches; faster runs on already-rich profiles |
| No Refresh or Reset capability | `POST /profile/refresh` and `POST /profile/reset` endpoints | Founders can update stale profiles without re-onboarding |
| Enrichment status tracked on `UploadedFile.metadata_` | Status tracked on `SkillRun.status` field | Standard pattern; observable through existing SSE stream |

**Deprecated/outdated after Phase 58:**
- `_run_background_enrichment()` function in `profile.py`: removed entirely
- `EnrichmentBanner` component in `CompanyProfilePage.tsx`: replaced by SSE stream overlay
- `enrichment_status` field on `CompanyProfileResponse`: no longer needed (or kept for backward compat and always null)
- `POST /profile/retry-enrichment` endpoint: could be removed or kept pointing to a fresh SkillRun

---

## Open Questions

1. **DOCUMENT_FILE reference vs. inline text in `input_text`**
   - What we know: `UploadedFile.extracted_text` already stores the pre-extracted text at upload time
   - What's unclear: Whether to store `DOCUMENT_FILE:{uuid}` (compact, requires DB lookup in worker) or `DOCUMENT:{text}` (self-contained, possibly large)
   - Recommendation: Store `DOCUMENT_FILE:{file_id}` in `input_text`. The worker's `_execute_company_intel` fetches `extracted_text` from `UploadedFile` at execution time. Keeps job queue payloads small. Requires a small DB query in the engine but this is standard practice.

2. **Refresh stream endpoint: `/onboarding/crawl/stream` vs. `/skills/runs/stream`**
   - What we know: Both SSE endpoints work. The onboarding stream endpoint has special `text` event formatting (converts `discovery` events to `text` for `useProfileCrawl`). The skills stream passes events through as-is.
   - What's unclear: Which endpoint the frontend should use for refresh/reset streams.
   - Recommendation: Use `/api/v1/skills/runs/{run_id}/stream` for consistency. Update `useProfileCrawl` to handle both the `discovery` event type (used by the skills stream) and the existing `text` event type. The skills stream passes events raw so the frontend receives `discovery` events directly.

3. **Handling of `SUPPLEMENTARY_DOCS` in `_execute_company_intel`**
   - What we know: Refresh needs both URL crawl AND document text. The current engine only handles one input.
   - What's unclear: The cleanest way to pass multiple sources to the engine.
   - Recommendation: For refresh, run the URL crawl normally, then also structure any linked document texts as additional passes through `structure_intelligence`. Merge all intelligence dicts before enrichment. The `input_text` format for refresh could be `{url}\nDOCUMENT_FILE:{id1}\nDOCUMENT_FILE:{id2}` with the engine splitting on newlines.

4. **`useProfileCrawl` vs. new `useProfileRefresh` hook**
   - What we know: `useProfileCrawl` has hard-coded `/onboarding/crawl` POST endpoint
   - What's unclear: Whether to extend it with new actions or create a separate hook
   - Recommendation: Create a `useProfileRefresh` hook that has `startRefresh()` and `startReset()` actions, calls the new profile endpoints, but uses the exact same SSE state shape (`phase`, `crawlItems`, `crawlStatus`, `error`). The `LiveCrawl` component is shared. This avoids a God hook.

---

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/engines/company_intel.py` — full read; all functions, constants, deprecated `write_company_intelligence`
- `backend/src/flywheel/services/skill_executor.py:811-1191` — full read of `_execute_company_intel`; stages 1-4; event types; write path
- `backend/src/flywheel/api/profile.py` — full read; `analyze_document`, `_run_background_enrichment`, `retry_enrichment`
- `backend/src/flywheel/api/onboarding.py:729-860` — `/onboarding/crawl` + SSE stream endpoint; verified event format
- `backend/src/flywheel/api/skills.py:299-401` — `/skills/runs/{id}/stream` SSE endpoint; late-connect replay
- `backend/src/flywheel/db/models.py:182-334` — `ContextEntry`, `SkillRun`, `UploadedFile` models; `deleted_at` soft-delete pattern
- `backend/src/flywheel/storage.py:89-130` — `append_entry` signature and behavior
- `frontend/src/features/profile/components/CompanyProfilePage.tsx` — full read; `CrawlPanel`, `DocumentAnalyzePanel`, `EnrichmentBanner`
- `frontend/src/features/profile/hooks/useProfileCrawl.ts` — full read; SSE hook pattern
- `frontend/src/lib/sse.ts` — full read; `useSSE` hook; event type list
- `frontend/src/features/onboarding/components/LiveCrawl.tsx` — partial read; confirms reusability

### No External Research Needed
This phase is entirely internal refactoring of existing code. All technical questions were answered
by reading the codebase directly. No library research, WebSearch, or Context7 queries required.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies verified by direct codebase reads
- Architecture: HIGH — patterns extracted directly from working code, not hypothetical
- Pitfalls: HIGH — identified by reading both the code being removed and the code being extended
- Plan decomposition: HIGH — three-plan split maps directly to three distinct code layers

**Research date:** 2026-03-27
**Valid until:** 60 days (internal architecture; stable until a major refactor touches these files)
