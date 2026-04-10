# Architecture Patterns

**Domain:** Structured skill output, document export, file upload, and PII redaction integration
**Researched:** 2026-04-10
**Confidence:** HIGH (based on direct codebase analysis, not web research)

---

## Current Architecture (Deep Dive)

### Execution Flow: API Call to Document in Library

```
1. POST /skills/runs (api/skills.py:StartRunRequest)
     - skill_name, input_text, input_data (optional dict), work_item_id
     - input_data gets JSON-serialized into input_text prefix (line 423-425)
     - Creates SkillRun row (status=pending)
     - Returns run_id + stream_url

2. Job worker claims run -> execute_run(run) (skill_executor.py:485)
     - Circuit breaker check
     - Decrypts BYOK API key
     - Loads skill metadata from DB (_load_skill_from_db, line 122)
     - Creates ToolRegistry + RunContext

3. Engine dispatch (skill_executor.py:591-691)
     - IF engine_module or hardcoded engine skill -> dedicated Python engine
       (company-intel, meeting-prep, email-scorer, meeting-processor, flywheel)
     - ELSE -> _execute_with_tools() (line 3206) -- generic LLM tool_use loop

4. _execute_with_tools (line 3206-3399)
     - AsyncAnthropic client with tool_defs from registry
     - System prompt: DB override > SKILL.md filesystem fallback
     - Injects tenant context (positioning, ICPs, etc.)
     - Anti-extraction prefix for protected skills
     - Tool loop: max 25 iterations, calls registry.execute() for tool_use
     - Returns: (output_text, token_usage, tool_calls)

5. Post-execution (skill_executor.py:703-858)
     - Render HTML: render_output(skill_name, output, attribution)
     - Save to SkillRun: output + rendered_html + tokens + cost
     - Create Document row linked to SkillRun (line 756-786)
     - Build attribution + reasoning trace
     - Emit SSE "done" event

6. Frontend rendering (DocumentViewer.tsx -> SkillRenderer.tsx)
     - Fetches document detail (output + rendered_html)
     - SkillRenderer dispatches by type:
       a. JSON parse attempt -> isOnePagerData() -> OnePagerRenderer
       b. meeting-prep/flywheel -> MeetingPrepRenderer (pre-built HTML)
       c. Everything else -> GenericRenderer (react-markdown)
```

### Key Models

| Model | Table | Key Fields | Role |
|-------|-------|-----------|------|
| SkillDefinition | skill_definitions | name, system_prompt, engine_module, parameters, web_tier, protected | Skill metadata (seeded from SKILL.md) |
| SkillRun | skill_runs | skill_name, input_text, output (Text), rendered_html (Text), attribution (JSONB), events_log (JSONB) | Execution record + content store |
| Document | documents | title, document_type, skill_run_id (FK), storage_path, tags, account_id, share_token | Library artifact, links to SkillRun for content |
| UploadedFile | uploaded_files | filename, mimetype, extracted_text, storage_path | File upload with text extraction |

### Tool Registry (tools/__init__.py)

Currently registered tools: `context_read`, `context_write`, `context_query`, `web_search` (Anthropic built-in), `web_fetch`, `file_read`, `file_write`, `python_execute`, `browser_*` (5 tools, agent-only).

All tools receive `RunContext(tenant_id, user_id, run_id, budget, session_factory, focus_id)`.

### Output Rendering Pipeline

```
output_renderer.py:
  1. detect_output_type(skill_name) -> TYPE_MAP lookup -> template name
  2. Structured JSON check: starts with "{" + has schema_version -> structured_data
  3. parse_output_sections(raw) -> sections from ## headings
  4. extract_key_facts(sections) -> key-value pairs for sidebars
  5. Jinja2 template render with all data
  
render_output_standalone() wraps fragment in full HTML doc for PDF export
```

### Existing Structured Output (One-Pager Precedent)

The one-pager skill already implements the full structured JSON pattern:

- **Backend**: `output_renderer.py` line 507-514 detects `schema_version` in JSON output, passes as `structured_data` to Jinja2 template
- **Backend template**: `outputs/one_pager.html` has two paths: `{% if structured_data %}` (JSON) and fallback (markdown sections)
- **Frontend**: `SkillRenderer.tsx` line 39-48 tries `JSON.parse(output)`, uses `isOnePagerData()` type guard, routes to `OnePagerRenderer`
- **Export**: `document_export.py` has `_try_parse_structured()` (line 343) checking for `schema_version`, dedicated `_build_one_pager_docx()`
- **Types**: `one-pager.ts` defines TypeScript interfaces + type guard

This is the **proven pattern** -- new structured skills should follow it exactly.

---

## Integration Points for New Features

### 1. Structured JSON Output (Extending the Pattern)

**Where detection happens (3 layers, all must be extended):**

| Layer | File | Line | Current Logic | What to Add |
|-------|------|------|---------------|-------------|
| Backend renderer | `output_renderer.py` | 507-514 | Checks `schema_version` + `isinstance(dict)` -> `structured_data` | No change needed -- already generic |
| Backend template | `templates/outputs/one_pager.html` | 2 | `{% if structured_data %}` branch | New template per skill type, OR extend TYPE_MAP |
| Frontend dispatch | `SkillRenderer.tsx` | 39-48 | `JSON.parse()` -> `isOnePagerData()` | Add new type guards: `isDealTapeData()`, etc. |
| Export DOCX | `document_export.py` | 96 | `document_type == "value-prop-one-pager"` | Add new document_type branches |
| Export PDF | `document_export.py` | 39 | Uses `render_output_standalone()` which already handles structured_data | Likely works out of the box via template |

**New files needed per structured skill:**
1. `frontend/src/features/documents/types/{skill-type}.ts` -- TypeScript interface + type guard
2. `frontend/src/features/documents/components/renderers/{SkillType}Renderer.tsx` -- React component
3. `backend/src/flywheel/engines/templates/outputs/{skill_type}.html` -- Jinja2 template (for HTML rendering + PDF)
4. Extension in `document_export.py` `_build_{type}_docx()` -- if DOCX export needed

**No changes needed:**
- `output_renderer.py` already passes `structured_data` to templates generically
- `TYPE_MAP` in `output_renderer.py` just needs a new entry (one line)
- `SkillRenderer.tsx` just needs new type guard + import (3-5 lines)

### 2. File Upload Integration with Skills

**Current state:** File upload already exists (`api/files.py`). The `company-intel` engine already consumes uploaded files via `DOCUMENT_FILE:{file_id}` prefix in `input_text` (skill_executor.py line 913-974).

**Pattern for file-aware skills:**

```
Current flow (company-intel):
  1. Frontend uploads file via POST /files/upload -> gets file_id
  2. Frontend sends skill run with input_text = "DOCUMENT_FILE:{file_id}"
  3. Executor detects prefix, loads UploadedFile.extracted_text from DB
  4. Passes text to LLM instead of crawled web content
```

**Integration approach for new file-aware skills:**

| Option | How | Pros | Cons |
|--------|-----|------|------|
| A. Reuse DOCUMENT_FILE prefix convention | Skills check input_text for prefix, load file text | Already proven, no API changes | Couples file handling to executor dispatch |
| **B. Add file_ids to StartRunRequest** | New `file_ids: list[UUID]` field | Clean API, generic, any skill can use | Needs API change + executor change |
| C. Separate upload-to-skill endpoint | POST /skills/runs/{id}/files | RESTful | Over-engineered for current needs |

**Recommendation: Option B** because:
- `StartRunRequest` already has `input_data: dict` for structured input
- Adding `file_ids: list[UUID]` is one field
- Executor resolves file_ids to extracted_text, injects into system prompt or input
- No `DOCUMENT_FILE:` string parsing needed
- Any skill can receive files without custom dispatch logic

**Files to modify:**
- `api/skills.py` -- Add `file_ids` to `StartRunRequest` (1 field)
- `skill_executor.py` -- After line 565, resolve file_ids and inject extracted_text
- Frontend skill input form -- Add file upload dropzone component

### 3. PII Redaction

**Current state:** Zero PII infrastructure. The `presidio` package is listed in CLAUDE.md as pre-installed system-wide, but no code uses it.

**Where PII redaction fits in the execution flow:**

```
Option A: Pre-processing (before LLM call)
  input_text -> PII_REDACT -> sanitized_input -> LLM -> output
  Problem: LLM cannot use names/emails that skills need (meeting prep, outreach)

Option B: Post-processing (after LLM output, before storage)  
  LLM -> output -> PII_REDACT -> sanitized_output -> DB
  Problem: Loses original data, breaks re-rendering

Option C: On-demand redaction (at export/share time) [RECOMMENDED]
  LLM -> output -> DB (full data)
  Export/Share -> PII_REDACT -> sanitized export
  Preserves data for owner, redacts for external consumers

Option D: Tool available to skills (skill decides when to redact)
  Register pii_redact as a tool in ToolRegistry
  Skills call it when generating external-facing content
  Problem: Skills must remember to call it, inconsistent
```

**Recommendation: Option C (on-demand at export/share)** because:
- Skills NEED PII to function (meeting prep needs names, outreach needs emails)
- Owner viewing their own document should see full data
- Redaction makes sense at the boundary: PDF export, DOCX export, share link
- Can be implemented as a middleware/utility without touching executor

**Integration points:**

| File | Change | Purpose |
|------|--------|---------|
| NEW `services/pii_redactor.py` | Presidio-based redaction service | Core redaction logic |
| `api/documents.py` export_document() | Add `redact_pii: bool` query param | PDF/DOCX export with optional redaction |
| `api/documents.py` get_shared_document() | Apply PII redaction by default | Shared links auto-redact |
| `services/document_export.py` | Accept `redact_pii` flag, call redactor | Export pipeline integration |

**PII redactor service design:**

```python
# services/pii_redactor.py
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Entity types to redact
DEFAULT_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]

def redact_text(text: str, entities: list[str] = None) -> str:
    """Replace PII entities with [REDACTED] placeholders."""
    
def redact_html(html: str, entities: list[str] = None) -> str:
    """Redact PII in HTML content while preserving markup."""
    
def redact_structured(data: dict, entities: list[str] = None) -> dict:
    """Redact PII in structured JSON output (walks string values)."""
```

### 4. Document Export (Already Partially Built)

**Current state:** Export endpoint exists at `GET /documents/{id}/export?format=pdf|docx` (documents.py line 631-706). Both PDF and DOCX work. Structured JSON export exists for one-pager DOCX.

**What is missing:**
- PDF export for structured JSON (currently uses generic HTML wrapping)
- PII redaction option on export
- DOCX templates for new structured skill types

**Files already in place:**
- `api/documents.py` line 631 -- export endpoint
- `services/document_export.py` -- export_as_pdf(), export_as_docx()
- Frontend `DocumentViewer.tsx` line 226-258 -- export dropdown with PDF/DOCX buttons

---

## Recommended Architecture for New Components

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `SkillRenderer` (frontend) | Dispatch to type-specific renderers | DocumentViewer, type-specific renderers |
| `{Type}Renderer` (frontend) | Render structured JSON for a skill type | SkillRenderer (parent), design tokens |
| `output_renderer.py` (backend) | Text->HTML rendering, template dispatch | skill_executor.py, document_export.py |
| `document_export.py` (backend) | PDF/DOCX generation from output | documents API, pii_redactor |
| `pii_redactor.py` (backend) NEW | PII detection + anonymization | document_export, documents API |
| `api/files.py` (backend) | File upload + text extraction | Skills API (via file_ids on StartRunRequest) |

### Data Flow: Structured JSON Skill Run

```
SKILL.md defines output_schema in parameters JSONB
  |
  v
_execute_with_tools() -> LLM outputs JSON string
  |
  v
skill_executor.py stores raw JSON in SkillRun.output
  |
  v
render_output() detects structured_data, renders via Jinja2 template
  -> stored in SkillRun.rendered_html (for PDF/share/legacy)
  |
  v
Frontend: SkillRenderer.tsx JSON.parse() -> type guard -> dedicated renderer
  |                                                        |
  v                                                        v
Document library listing                           Rich React component
  |
  v
Export: document_export.py checks structured, builds branded PDF/DOCX
  |
  v (optional)
PII redactor strips sensitive data before export/share
```

### Data Flow: File Upload + Skill Execution

```
Frontend: File upload dropzone
  |
  v
POST /files/upload -> UploadedFile row (extracted_text stored)
  |
  v
POST /skills/runs { skill_name, input_text, file_ids: [uuid] }
  |
  v
skill_executor.py resolves file_ids:
  - Loads UploadedFile.extracted_text for each
  - Prepends to system prompt as "## Uploaded Documents\n{text}"
  |
  v
Normal execution flow (LLM sees document content as context)
```

---

## Patterns to Follow

### Pattern 1: Structured Output Type Registration

Every new structured skill type requires coordinated changes across 4 files. Follow the one-pager precedent exactly.

**Backend:**
```python
# output_renderer.py - Add to TYPE_MAP
TYPE_MAP = {
    ...
    "deal-tape": "deal_tape",
    "ctx-deal-tape": "deal_tape",
}
```

**Frontend:**
```typescript
// SkillRenderer.tsx - Add type guard check
if (isDealTapeData(parsed)) {
  return <DealTapeRenderer data={parsed} />
}
```

### Pattern 2: Export Extension

```python
# document_export.py - Add structured branch
if structured and structured.get("document_type") == "deal-tape":
    _build_deal_tape_docx(doc, structured, coral, dark, muted, light_gray)
```

### Pattern 3: File-Aware Skill Input

```python
# In execute_run(), after RunContext creation:
if file_ids:
    file_texts = await _resolve_file_texts(factory, tenant_id, file_ids)
    # Inject into system prompt or input_text
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Hardcoded Engine Dispatch
**What:** Adding more `is_xyz = run.skill_name == "xyz"` branches in execute_run()
**Why bad:** skill_executor.py lines 593-601 already have 6 hardcoded checks. Adding more makes the function unmaintainable.
**Instead:** Use `engine_module` field from SkillDefinition. Register engine modules that auto-dispatch. The one-pager approach (LLM outputs JSON via standard _execute_with_tools) avoids engine dispatch entirely.

### Anti-Pattern 2: PII Redaction in the Executor
**What:** Redacting PII before storing output
**Why bad:** Destroys data the user needs. Meeting prep showing "[REDACTED]" for attendee names is useless.
**Instead:** Store full data, redact at export/share boundary only.

### Anti-Pattern 3: Separate Content Storage for Structured Output
**What:** Storing structured JSON in a different field or table than SkillRun.output
**Why bad:** Breaks the existing Document -> SkillRun -> output chain. Frontend already handles JSON in the output field.
**Instead:** Keep structured JSON as a string in SkillRun.output. The renderer and frontend both already handle JSON detection.

### Anti-Pattern 4: Modifying SkillRun Model for File References
**What:** Adding `file_ids` column to skill_runs table
**Why bad:** Unnecessary schema migration. Files are input context, not run metadata.
**Instead:** Resolve file_ids at execution time, inject text into prompt. The SkillRun.input_text already stores a summary of what was provided.

---

## Scalability Considerations

| Concern | Current (100 users) | At 10K users | At 1M users |
|---------|---------------------|--------------|-------------|
| Structured JSON output | String in TEXT column, fine | Consider JSONB column for querying | JSONB + separate output_data table |
| File upload storage | Supabase Storage | Supabase Storage with CDN | S3 + CloudFront, presigned URLs |
| PII redaction | Presidio in-process | Presidio in-process (fast) | Dedicated redaction microservice |
| PDF generation | WeasyPrint in-process | WeasyPrint with async worker | Dedicated PDF service (Gotenberg) |
| DOCX generation | python-docx in-process | In-process (fast, memory only) | Same, no scaling issue |

---

## Pre-Existing One-Pager Code Assessment

The one-pager implementation is **complete and production-ready** across all layers:

| Layer | File | Status | Gaps |
|-------|------|--------|------|
| TypeScript types | `types/one-pager.ts` | Complete | None |
| Frontend renderer | `renderers/OnePagerRenderer.tsx` | Complete, 415 lines | None |
| SkillRenderer dispatch | `renderers/SkillRenderer.tsx` | Complete | None |
| Backend TYPE_MAP | `output_renderer.py` line 91-92 | Complete | None |
| Backend template | `templates/outputs/one_pager.html` | Complete, 166 lines | None |
| DOCX export | `document_export.py` line 142-335 | Complete | None |
| PDF export | `document_export.py` line 29-63 | Works via HTML template | Could be improved with direct structured PDF |

**This is the template to copy for every new structured skill type.** The pattern is proven, handles all three rendering contexts (web, PDF, DOCX), and has proper fallback for non-JSON output.

---

## Suggested Build Order (Dependency-Aware)

```
Phase 1: Structured JSON foundation (no new deps)
  - Generalize the type registration pattern (utility function?)
  - Add deal-tape or next skill type following one-pager pattern
  - Extends: TYPE_MAP, SkillRenderer, templates, export
  
Phase 2: File upload for skills (builds on existing upload infra)
  - Add file_ids to StartRunRequest
  - File resolution in executor
  - Frontend file picker component
  - Requires: Phase 1 (new skills may need file input)
  
Phase 3: PII redaction (independent, can parallelize with Phase 2)
  - Create pii_redactor.py service
  - Wire into export endpoint
  - Wire into share endpoint
  - No executor changes needed
  
Phase 4: New skills using all infrastructure
  - Each new skill: SKILL.md + type def + renderer + template + export
  - Can use file input if needed
  - Exports auto-redact via Phase 3
```

---

## Sources

All findings from direct codebase analysis:
- `backend/src/flywheel/services/skill_executor.py` (3400+ lines) -- full execution flow
- `backend/src/flywheel/engines/output_renderer.py` (630 lines) -- rendering pipeline
- `backend/src/flywheel/api/skills.py` -- API layer, StartRunRequest, input validation
- `backend/src/flywheel/api/documents.py` (849 lines) -- document CRUD + export endpoint
- `backend/src/flywheel/services/document_export.py` (410 lines) -- PDF/DOCX generation
- `backend/src/flywheel/db/models.py` -- SkillRun, Document, UploadedFile, SkillDefinition
- `backend/src/flywheel/db/seed.py` -- SKILL.md parsing, frontmatter -> DB
- `backend/src/flywheel/tools/__init__.py` -- tool registry, 12 tools registered
- `backend/src/flywheel/tools/registry.py` -- RunContext, ToolDefinition, execute()
- `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` -- dispatch
- `frontend/src/features/documents/components/renderers/OnePagerRenderer.tsx` -- structured renderer
- `frontend/src/features/documents/types/one-pager.ts` -- TypeScript schema + type guard
- `frontend/src/features/documents/components/DocumentViewer.tsx` -- viewer with export
- `backend/src/flywheel/api/files.py` -- file upload endpoint
