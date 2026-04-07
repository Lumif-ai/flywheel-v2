# Phase 76: Backend Foundation - Research

**Researched:** 2026-03-30
**Domain:** FastAPI endpoint implementation, markdown rendering, XSS sanitization
**Confidence:** HIGH

## Summary

Phase 76 adds four backend endpoints that MCP tools will consume: a skill prompt endpoint, a meeting PATCH endpoint, a document-from-content POST endpoint, and XSS-safe markdown rendering. All four follow established patterns already present in the codebase.

The codebase has strong conventions: every authenticated endpoint uses `require_tenant` + `get_tenant_db` dependency injection, SkillRun creation follows a consistent pattern, and the existing `output_renderer.py` handles markdown-to-HTML via the `markdown` library with Jinja2's `Markup()` class. The primary risk is XSS -- the current `_md_to_html` filter converts markdown to HTML and wraps it in `Markup()` which bypasses Jinja2 autoescape, and the `markdown` library passes through `<script>` tags, `javascript:` URIs, and event handler attributes verbatim.

**Primary recommendation:** Follow existing endpoint patterns exactly; add a `sanitize_html()` function using BeautifulSoup4 (already installed) as an allowlist-based HTML sanitizer injected between `markdown.markdown()` and `Markup()` in the output renderer.

## Standard Stack

### Core (already installed -- zero new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | API framework | Already used for all endpoints |
| SQLAlchemy | >=2.0 | Async ORM | Already used for all DB access |
| Pydantic | >=2.0 | Request/response validation | Already used for all models |
| markdown | 3.9 | Markdown-to-HTML conversion | Already used in output_renderer.py |
| markupsafe | 3.0.3 | Markup() for Jinja2 bypass | Already used in output_renderer.py |
| beautifulsoup4 | >=4.12 | HTML sanitization (allowlist) | Already in pyproject.toml deps |

### No New Dependencies
The constraint is explicit: zero new dependencies for this entire milestone. BeautifulSoup4 is already declared in `pyproject.toml` and imported elsewhere. The `html.parser` backend is stdlib.

## Architecture Patterns

### Existing Endpoint Pattern (MUST follow)
Every endpoint in this codebase follows this exact structure:

```python
from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload

@router.get("/some-path")
async def endpoint_name(
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    # Query using db session (RLS-scoped)
    result = await db.execute(select(Model).where(...))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {...}
```

### Router Registration Pattern
Each API module has a `router = APIRouter(prefix="/...", tags=["..."])` and is registered in `main.py` with `app.include_router(router, prefix="/api/v1")`. Existing routers: `skills_router` (prefix="/skills"), `meetings_router` (prefix="/meetings"), `documents_router` (prefix="/documents").

New endpoints go into EXISTING router files -- no new router registration needed.

### SkillRun Creation Pattern (for documents/from-content)
From `skill_executor.py` lines 700-754, the pattern for creating a completed skill run + document:

```python
# 1. Create SkillRun with status="completed"
run = SkillRun(
    tenant_id=user.tenant_id,
    user_id=user.sub,
    skill_name=skill_name,
    input_text=input_text,
    output=raw_output,
    rendered_html=rendered_html,
    status="completed",
    attempts=3,         # max_attempts default, prevents job queue pickup
    max_attempts=3,     # explicit
)
db.add(run)
await db.flush()

# 2. Create Document linked to the run
doc = Document(
    tenant_id=user.tenant_id,
    user_id=user.sub,
    title=title,
    document_type=skill_name,
    storage_path=None,
    file_size_bytes=len(rendered_html.encode("utf-8")),
    skill_run_id=run.id,
    metadata_=metadata,
)
db.add(doc)
await db.commit()
```

### Job Queue Bypass (CRITICAL)
`job_queue.py` line 42-44 claims jobs with:
```python
.where(SkillRun.status == "pending")
.where(SkillRun.scheduled_for <= datetime.now(timezone.utc))
.where(SkillRun.attempts < SkillRun.max_attempts)
```

To prevent the job queue from picking up from-content runs:
- Set `status="completed"` (not "pending") -- this alone is sufficient
- Also set `attempts=max_attempts` as a belt-and-suspenders guard

### SkillDefinition Lookup Pattern (for prompt endpoint)
From `skills.py` `_get_available_skills_db()`, the tenant-aware skill lookup:

```python
# Check tenant overrides
has_overrides = await db.execute(
    select(TenantSkill.skill_id)
    .where(TenantSkill.tenant_id == tenant_id)
    .limit(1)
)
if has_overrides.scalar_one_or_none() is not None:
    # Use tenant_skills join
    stmt = select(SkillDefinition).join(TenantSkill, ...).where(...)
else:
    # All enabled skills available
    stmt = select(SkillDefinition).where(SkillDefinition.enabled == True)
```

The prompt endpoint needs a SIMPLER version: just look up by name, check enabled + tenant access, return `system_prompt` field.

### Meeting Update Pattern
`Meeting` model fields for the PATCH:
- `ai_summary`: `Mapped[str | None]` (Text) -- the field to write
- `processing_status`: `Mapped[str]` (Text) -- status to update

Existing meeting endpoints already use owner-check pattern (`meeting.user_id == user.sub`). The PATCH endpoint should enforce the same ownership for writes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML sanitization | Regex-based strip | BeautifulSoup4 allowlist decompose | Regex is trivially bypassable; BS4 handles malformed HTML correctly |
| Markdown rendering | Custom parser | `markdown.markdown(text, extensions=["extra"])` | Already in use, well-tested |
| Request validation | Manual field checks | Pydantic BaseModel | Already the pattern everywhere |
| Auth + tenant scoping | Custom middleware | `require_tenant` + `get_tenant_db` deps | RLS already configured |

## Common Pitfalls

### Pitfall 1: Job Queue Picks Up "from-content" Runs
**What goes wrong:** If you create a SkillRun with status="pending", the job_queue_loop will claim it and try to execute it, causing errors or duplicate processing.
**Why it happens:** The job queue polls for `status='pending' AND attempts < max_attempts`.
**How to avoid:** Create with `status="completed"` AND `attempts=max_attempts` (default 3). The status alone is sufficient, but both together are defensive.
**Warning signs:** Unexpected "running" status on from-content runs; skill_executor errors for unknown skill names.

### Pitfall 2: XSS via Markup() Bypass
**What goes wrong:** The `_md_to_html` Jinja2 filter converts markdown to HTML then wraps in `Markup()`, bypassing autoescape. If the input contains `<script>` tags, `javascript:` URIs, or `onerror` attributes, they pass through verbatim.
**Why it happens:** `markdown.markdown()` with `extra` extension preserves raw HTML. `Markup()` tells Jinja2 "this is safe, don't escape."
**How to avoid:** Sanitize HTML BETWEEN `markdown.markdown()` and `Markup()` using an allowlist approach.
**Warning signs:** Script tags in rendered_html column; browser console XSS alerts.
**Verified:** Tested locally -- `markdown.markdown('<script>alert(1)</script>', extensions=['extra'])` outputs `<script>alert(1)</script>` unchanged.

### Pitfall 3: Frontend dangerouslySetInnerHTML Without Sanitization
**What goes wrong:** Multiple frontend components inject `rendered_html` directly without sanitization.
**Components that DO sanitize (use `sanitizeHTML` from `@/lib/sanitize`):**
- `SkillOutput.tsx`
- `MeetingPrepRenderer.tsx`
- `OutputViewer.tsx`

**Components that DO NOT sanitize (raw dangerouslySetInnerHTML):**
- `OnboardingMeetingPrep.tsx` (line 237)
- `MomentLand.tsx` (line 66)
- `PrepBriefingPanel.tsx` (line 124)
- `MeetingDetailPage.tsx` (line 363)
- `BriefingFullViewer.tsx` (line 256)
- `FirstVisitHero.tsx` (line 158)

**How to avoid:** Backend sanitization is the primary defense (defense in depth). Frontend should also sanitize, but that's a separate phase concern.

### Pitfall 4: SkillDefinition.system_prompt Is Nullable
**What goes wrong:** Not all skills have system_prompt populated. If the endpoint returns the field as-is, callers may get null.
**How to avoid:** Return 404 for `system_prompt is None` or return an explicit null with documentation. MCP tools should handle both cases.

### Pitfall 5: Meeting Ownership on PATCH
**What goes wrong:** Any tenant member could overwrite another user's ai_summary.
**How to avoid:** Existing `get_meeting` detail endpoint uses `meeting.user_id == user.sub` for owner-only fields. The PATCH should enforce the same ownership check for writes.

## Code Examples

### 1. GET /skills/{name}/prompt Endpoint
```python
@router.get("/{skill_name}/prompt")
async def get_skill_prompt(
    skill_name: str,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    """Return the system_prompt for an enabled skill."""
    # Simplified lookup: by name + enabled + tenant access
    result = await db.execute(
        select(SkillDefinition).where(
            SkillDefinition.name == skill_name,
            SkillDefinition.enabled == True,
        )
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    return {"skill_name": skill.name, "system_prompt": skill.system_prompt}
```

**Note:** Should also check tenant_skills if tenant has overrides (same pattern as `_get_available_skills_db`). The prompt endpoint needs the same tenant-scoping logic.

### 2. PATCH /meetings/{id} Endpoint
```python
class MeetingPatchRequest(BaseModel):
    ai_summary: str | None = None
    processing_status: str | None = None

@router.patch("/{meeting_id}")
async def patch_meeting(
    meeting_id: UUID,
    body: MeetingPatchRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    result = await db.execute(
        select(Meeting).where(
            Meeting.id == meeting_id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        ).limit(1)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if body.ai_summary is not None:
        meeting.ai_summary = body.ai_summary
    if body.processing_status is not None:
        meeting.processing_status = body.processing_status

    await db.commit()
    await db.refresh(meeting)
    return {"id": str(meeting.id), "processing_status": meeting.processing_status}
```

### 3. POST /documents/from-content Endpoint
```python
class FromContentRequest(BaseModel):
    title: str
    skill_name: str
    markdown_content: str
    metadata: dict = {}

@router.post("/from-content", status_code=201)
async def create_from_content(
    body: FromContentRequest,
    user: TokenPayload = Depends(require_tenant),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    from flywheel.engines.output_renderer import render_output

    rendered_html = render_output(body.skill_name, body.markdown_content)

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name=body.skill_name,
        input_text=body.markdown_content[:200],
        output=body.markdown_content,
        rendered_html=rendered_html,
        status="completed",
        attempts=3,
        max_attempts=3,
    )
    db.add(run)
    await db.flush()

    doc = Document(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        title=body.title,
        document_type=body.skill_name,
        storage_path=None,
        file_size_bytes=len(rendered_html.encode("utf-8")),
        skill_run_id=run.id,
        metadata_=body.metadata,
    )
    db.add(doc)
    await db.commit()

    return {"document_id": str(doc.id), "skill_run_id": str(run.id)}
```

### 4. HTML Sanitizer Using BeautifulSoup4
```python
from bs4 import BeautifulSoup

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "strong", "em", "b", "i", "u", "s", "code", "pre", "blockquote",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
    "dl", "dt", "dd",
    "sup", "sub",
}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
DANGEROUS_PROTOCOLS = {"javascript", "vbscript", "data"}


def sanitize_html(html: str) -> str:
    """Allowlist-based HTML sanitizer using BeautifulSoup4."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.decompose()
            continue
        # Filter attributes
        allowed = ALLOWED_ATTRS.get(tag.name, set())
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag[attr]
        # Sanitize href/src protocols
        for url_attr in ("href", "src"):
            if url_attr in tag.attrs:
                val = tag[url_attr].strip().lower()
                if any(val.startswith(p + ":") for p in DANGEROUS_PROTOCOLS):
                    del tag[url_attr]

    return str(soup)
```

**Integration point:** Modify `_md_to_html` in `output_renderer.py`:
```python
def _md_to_html(text):
    if not text:
        return ""
    import markdown as _md
    from markupsafe import Markup
    html = _md.markdown(str(text), extensions=["extra"])
    html = sanitize_html(html)  # <-- ADD THIS
    return Markup(html)
```

## Key Model Fields Reference

### SkillDefinition (for prompt endpoint)
- `name`: str, unique, indexed
- `system_prompt`: str | None (Text) -- THE field to return
- `enabled`: bool, default True
- Tenant scoping via optional `TenantSkill` join

### SkillRun (for from-content)
- `status`: str, default "pending" -- set to "completed"
- `attempts`: int, default 0 -- set to 3
- `max_attempts`: int, default 3 -- match attempts
- `output`: str | None -- raw markdown content
- `rendered_html`: str | None -- sanitized HTML
- `tenant_id`, `user_id`: required FKs

### Meeting (for PATCH)
- `ai_summary`: str | None (Text) -- writable
- `processing_status`: str, default "pending" -- writable
- `user_id`: UUID -- for ownership check
- `tenant_id`: UUID -- for RLS scoping

### Document (for from-content)
- `skill_run_id`: UUID | None FK -- links to SkillRun
- `storage_path`: str | None -- set to None (content served from skill_run)
- `metadata_`: mapped as "metadata" column (JSONB)
- `document_type`: str -- set to skill_name

## Testing Pattern

Existing tests use FastAPI TestClient with dependency overrides:

```python
from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.main import app

# Override auth
app.dependency_overrides[require_tenant] = lambda: _make_user()

# Override DB with mock
mock_db = AsyncMock(spec=AsyncSession)
app.dependency_overrides[get_tenant_db] = lambda: mock_db

client = TestClient(app)
response = client.get("/api/v1/skills/")
```

Tests mock `db.execute()` return values using a `MockResult` helper class.

## Open Questions

1. **Tenant-scoping for prompt endpoint**
   - What we know: `_get_available_skills_db` checks tenant_skills overrides. The prompt endpoint should respect the same access control.
   - What's unclear: Should the prompt endpoint do the full tenant_skills check, or is a simple `enabled=True` check sufficient for MCP tool usage?
   - Recommendation: Use the full tenant-scoping pattern (copy from `_get_available_skills_db`) for consistency and security.

2. **processing_status validation on PATCH**
   - What we know: The field is a plain text column with no DB-level enum constraint.
   - What's unclear: Should the PATCH validate against a known set of statuses?
   - Recommendation: Validate against known values: `["pending", "processing", "complete", "failed", "skipped", "recorded", "scheduled"]`.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/api/skills.py` -- existing skill endpoint patterns, tenant-scoping logic
- `backend/src/flywheel/api/meetings.py` -- existing meeting endpoints, owner-check pattern
- `backend/src/flywheel/api/documents.py` -- existing document endpoints, Document+SkillRun linking
- `backend/src/flywheel/api/deps.py` -- `require_tenant`, `get_tenant_db` dependency chain
- `backend/src/flywheel/engines/output_renderer.py` -- `_md_to_html` filter, `Markup()` bypass
- `backend/src/flywheel/services/job_queue.py` -- WHERE clause: `status='pending' AND attempts < max_attempts`
- `backend/src/flywheel/db/models.py` -- SkillRun, Meeting, SkillDefinition, Document model definitions
- `backend/src/flywheel/services/skill_executor.py` -- SkillRun creation + Document creation pattern
- `backend/src/tests/test_skills_api.py` -- test pattern with dependency overrides

### Verified (HIGH confidence)
- Local test: `markdown.markdown('<script>alert(1)</script>')` outputs `<script>alert(1)</script>` -- XSS confirmed
- Local test: `BeautifulSoup` tag decompose works for sanitization
- `pyproject.toml` confirms beautifulsoup4 is already a dependency
- No `nh3` or `bleach` installed; no sanitizer exists in backend currently

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in pyproject.toml, verified installed
- Architecture: HIGH -- all patterns copied from existing codebase
- Pitfalls: HIGH -- XSS verified via local test, job queue WHERE clause read directly
- Sanitization approach: MEDIUM -- BeautifulSoup4 is not a purpose-built sanitizer, but the allowlist decompose approach is sound for the tag set we need

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable codebase patterns, no external dependency changes)
