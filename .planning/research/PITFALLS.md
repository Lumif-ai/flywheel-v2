# Domain Pitfalls

**Domain:** Structured skill output, document export (PDF/DOCX), file upload, PII redaction for Flywheel V2
**Researched:** 2026-04-10
**Confidence:** HIGH for pre-GSD code review and WeasyPrint/DOCX issues (direct code analysis + official docs). MEDIUM for Presidio (web research verified by official docs). HIGH for structured JSON output (verified via Anthropic official docs).

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or production outages.

---

### Pitfall 1: WeasyPrint Not in Dependencies and Missing System Libraries in Docker

**What goes wrong:** The `document_export.py` service imports WeasyPrint at runtime (line 57) but WeasyPrint is NOT listed in `backend/pyproject.toml`. The export endpoint will crash with `ImportError` in production. Even after adding the pip dependency, WeasyPrint requires system-level C libraries (Cairo, Pango, GDK-Pixbuf, libffi, gobject) that do not exist in the `python:3.12-slim` Docker image used by `backend/Dockerfile`.

**Why it happens:** WeasyPrint is a Python binding to C rendering libraries, not a pure-Python package. The `pip install weasyprint` succeeds but the library fails at import time when the system libraries are missing. The `python:3.12-slim` base image strips these out.

**Consequences:**
- PDF export returns HTTP 501 (the code catches `ImportError` and raises `RuntimeError`)
- Docker image build succeeds but export fails at runtime -- hard to catch without integration tests
- Adding the system deps to `python:3.12-slim` adds 150-250MB to the Docker image

**Evidence in pre-GSD code:**
- `backend/pyproject.toml` lines 6-39: WeasyPrint not listed in dependencies
- `backend/src/flywheel/services/document_export.py` line 57: `from weasyprint import HTML as WeasyprintHTML`
- `backend/Dockerfile` line 1: `FROM python:3.12-slim AS base` -- no `apt-get install` for system libs

**Prevention:**
1. Add `weasyprint>=63` to `pyproject.toml` dependencies
2. Add system dependency installation to Dockerfile BEFORE pip install:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends \
       libpango1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
       libcairo2 libgdk-pixbuf2.0-0 libgobject-2.0-0 libffi-dev \
       && rm -rf /var/lib/apt/lists/*
   ```
3. Consider a multi-stage build to keep image size down
4. Alternative: use a WeasyPrint microservice (Docker sidecar) to isolate the heavy dependencies from the main API image

**Detection:** Export endpoint returns 501 or 500 in staging. CI integration test for PDF export.

---

### Pitfall 2: LLM JSON Output is Prompt-Requested, Not Schema-Enforced

**What goes wrong:** The one-pager SKILL.md (line 251-323) instructs Claude to output raw JSON as its final message: "Do not wrap in markdown code fences. Do not include any text before or after the JSON." This is a prompt-level instruction only. Claude will sometimes:
- Wrap JSON in ```json code fences
- Prepend conversational text ("Here's the one-pager:")
- Produce invalid JSON (unclosed strings, trailing commas)
- Omit optional fields that the renderer expects to exist

The current parsing in both frontend (`SkillRenderer.tsx` line 41: `JSON.parse(output)`) and backend (`document_export.py` line 345-353: `json.loads(output)`) will throw on any of these failure modes.

**Why it happens:** Flywheel uses a tool_use loop (`execution_gateway.py`). The final LLM response is `stop_reason: "end_turn"` with text content blocks. Text content has no schema enforcement. Anthropic now offers structured outputs (`output_config.format.type: "json_schema"`) which guarantees schema-valid JSON via constrained decoding, but this is NOT being used.

**Consequences:**
- Frontend shows "No content available" when `JSON.parse` fails silently in the catch block (`SkillRenderer.tsx` line 44)
- Backend renders the JSON as markdown sections instead of structured document (fallback path)
- DOCX export falls through to plain-text conversion instead of the branded one-pager builder
- Users see broken output with no error message explaining what went wrong

**Evidence in pre-GSD code:**
- `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` lines 39-48: bare `JSON.parse` with empty catch
- `backend/src/flywheel/services/document_export.py` lines 343-353: `_try_parse_structured` only checks `startswith("{")` and `json.loads`
- `backend/src/flywheel/engines/output_renderer.py` lines 508-514: same fragile JSON detection
- `skills/one-pager/SKILL.md` line 254: "Do not wrap in markdown code fences" -- prompt-only enforcement

**Prevention:**
1. Use Anthropic's structured outputs API (`output_config.format.type: "json_schema"`) for skills that require JSON output. This guarantees valid JSON at the token level. GA on Claude Sonnet 4.5+, Opus 4.5+, Haiku 4.5+.
2. If structured outputs can't be used (tool_use loop incompatibility), add robust JSON extraction: strip markdown fences, find first `{` to last `}`, retry parse
3. Add a Pydantic model for one-pager schema on the backend for server-side validation after parsing
4. Frontend type guard `isOnePagerData` (line 72-82 in `one-pager.ts`) only checks 5 fields -- should validate all required fields and array element shapes
5. Always show a fallback error message, not silent failure

**Detection:** LLM output doesn't start with `{`. Parse failure rate in logs. Add structured output validation metrics.

---

### Pitfall 3: Structured Output Incompatibility with Tool_Use Loop

**What goes wrong:** Flywheel's execution gateway runs skills through a multi-turn tool_use loop (context store reads, web search, etc.). Anthropic's structured outputs (`output_config.format`) apply to the FINAL response. But in a tool_use loop, the model may need to produce tool_use blocks in intermediate turns, and structured output formatting only applies when `stop_reason` is `end_turn`. If the skill prompt asks for JSON output AND the model needs to call tools, the structured output constraint may conflict with the tool calling behavior.

**Why it happens:** Structured outputs and tool_use are designed to work together, but the interaction is nuanced. The `output_config` applies to the final text response. The execution_gateway collects text from `end_turn` responses (lines 396-410). The structured output constraint needs to be set from the first API call, but intermediate calls produce tool_use, not text.

**Consequences:**
- Setting `output_config` on the first call is correct (Anthropic applies it to the final turn), but the implementation needs to handle the case where the model decides to end early
- If the schema is too restrictive, the model may be unable to express error conditions or ask clarifying questions

**Prevention:**
1. Set `output_config` on EVERY call in the loop (Anthropic ignores it on tool_use turns, applies on end_turn)
2. Include an `error` field in the JSON schema so the model can report failures within the structured format
3. Test with multi-turn tool_use conversations to verify JSON output is produced on the final turn
4. Consider a two-phase approach: run the tool_use loop normally, then make a final "format as JSON" call with structured outputs

**Detection:** Monitor `stop_reason` on final turn. Log cases where output is not valid JSON after structured output is requested.

---

### Pitfall 4: PDF Export Runs Synchronously on API Thread

**What goes wrong:** The export endpoint (`documents.py` line 631-706) calls `export_as_pdf()` synchronously in the FastAPI async handler. WeasyPrint's HTML-to-PDF conversion is CPU-intensive and can take 2-10 seconds for complex documents. This blocks the async event loop, degrading throughput for all concurrent requests.

**Why it happens:** `export_as_pdf()` and `export_as_docx()` are synchronous functions called with `await` indirectly through the sync-to-async bridge. But WeasyPrint internally does blocking I/O and CPU-bound rendering.

**Consequences:**
- All other API requests stall while PDF is being generated
- Timeout errors for other users during export
- Railway/deployment health checks may fail during heavy exports

**Evidence in pre-GSD code:**
- `backend/src/flywheel/api/documents.py` lines 678-679: `content = export_as_pdf(doc.document_type, run_output, run_html)` -- synchronous call in async handler

**Prevention:**
1. Run export in a thread pool: `content = await asyncio.to_thread(export_as_pdf, ...)`
2. Add a timeout (30s) to prevent runaway rendering
3. For large documents, consider a background job with polling
4. Add `Content-Length` header to the response so clients can show download progress

**Detection:** Slow response times on other endpoints during export. Event loop blocking warnings in uvicorn logs.

---

### Pitfall 5: XSS via HTML Injection in Export

**What goes wrong:** The `_wrap_text_as_html` function (document_export.py lines 356-364) uses `html.escape` for plain text. But the `_wrap_fragment_as_document` function (lines 367-378) wraps an HTML fragment WITHOUT any sanitization. If `rendered_html` from the skill run contains malicious JavaScript, it will be embedded in the PDF generation pipeline. While WeasyPrint doesn't execute JS, the HTML is also served via the `/content` endpoint (documents.py line 548: `HTMLResponse(content=html)`) where it IS rendered in a browser.

**Why it happens:** The rendered_html is assumed safe because it comes from the LLM, but LLM output can contain script tags, especially if the skill prompt or user input is crafted to produce them.

**Evidence in pre-GSD code:**
- `backend/src/flywheel/engines/output_renderer.py` line 49-73: `sanitize_html()` exists and is used during template rendering
- `backend/src/flywheel/services/document_export.py` lines 367-378: `_wrap_fragment_as_document` does NOT call `sanitize_html`
- `backend/src/flywheel/api/documents.py` line 548: serves HTML directly to browser

**Prevention:**
1. Always run `sanitize_html()` on any HTML before serving it to browsers or embedding in exports
2. The sanitizer already exists in `output_renderer.py` -- import and use it in `document_export.py`
3. Set `Content-Security-Policy` header on the HTML content endpoint to prevent script execution

**Detection:** Security audit. Test with `<script>alert(1)</script>` in skill output.

---

## Moderate Pitfalls

---

### Pitfall 6: DOCX One-Pager Builder Has Hardcoded Column Assumptions

**What goes wrong:** The `_build_one_pager_docx` function assumes `comparison_table.columns` is always exactly 2 columns (document_export.py line 254: `table = doc.add_table(rows=len(rows) + 1, cols=3)` -- hardcoded 3 cols for Metric + 2 columns). But the TypeScript type defines `columns` as a tuple `[string, string]` while the JSON schema in SKILL.md shows `"columns": ["Manual Process", "With ProductName"]` -- what if the LLM produces 3 comparison columns?

**Prevention:**
1. Make the table column count dynamic: `cols=len(col_names) + 1`
2. Add server-side validation of the structured data before building the DOCX
3. Guard against `IndexError` when accessing column data

**Evidence:**
- `backend/src/flywheel/services/document_export.py` line 254: hardcoded `cols=3`
- `frontend/src/features/documents/types/one-pager.ts` line 32: `columns: [string, string]` -- enforces tuple of exactly 2

---

### Pitfall 7: Font Rendering Differences Between React, WeasyPrint, and DOCX

**What goes wrong:** The one-pager renders in three different contexts:
1. **React** (OnePagerRenderer.tsx): Uses browser-installed Inter font
2. **WeasyPrint PDF**: Uses system-installed fonts in Docker container (Inter is NOT installed in `python:3.12-slim`)
3. **python-docx DOCX**: Uses fonts available on the recipient's machine (Inter may not be installed)

The visual output will look completely different across formats.

**Prevention:**
1. Embed Inter font in the PDF HTML as a base64 `@font-face` or install it in the Docker image
2. For DOCX, set `run.font.name = "Calibri"` as fallback (universally available on Windows/Mac)
3. Test all three output formats with the same data to verify visual consistency
4. Accept that pixel-perfect consistency across formats is impossible -- aim for "professional in each"

---

### Pitfall 8: File Upload Security (Future Phase)

**What goes wrong:** When adding file upload for skill processing:
- Malicious PDFs can exploit PDF parsing libraries (pdfplumber is already a dependency)
- Zip bombs or extremely large files can exhaust memory/disk
- Uploaded files stored in temp directories may persist indefinitely
- Multi-tenant: one tenant's uploaded file accessible to another tenant

**Prevention:**
1. Enforce file size limits at the reverse proxy level (nginx/Railway) AND in FastAPI
2. Validate file type by magic bytes, not just extension
3. Store uploads in tenant-scoped Supabase storage paths
4. Clean up temp files in a `finally` block or use `tempfile.NamedTemporaryFile(delete=True)`
5. Never pass user-uploaded file paths to shell commands
6. Set timeouts on PDF parsing to prevent decompression bombs

---

### Pitfall 9: Presidio False Positives Will Redact Business-Critical Content

**What goes wrong:** Presidio's default recognizers are tuned for high recall, low precision. In a B2B sales context:
- Company names get flagged as PERSON entities ("Baker Hughes", "Johnson Controls")
- Product codes and SKUs get flagged as identifiers
- Phone number formats in meeting notes get partially redacted
- Email addresses in competitive intel get redacted when they should be kept
- Industry statistics and financial figures get flagged as SSN or credit card patterns

A 2025 study found 22.7% precision in mixed-language enterprise datasets -- for every real PII entity, 3.4 false positives.

**Prevention:**
1. Build a domain-specific allow-list: company names, product names, industry terms from context store
2. Use custom recognizers instead of defaults -- start with EMAIL, PHONE, SSN only
3. Set `score_threshold=0.7` minimum (default is 0.0 which catches everything)
4. Show redacted content to the user for review BEFORE finalizing (preview mode)
5. Store the original and redacted versions so redaction is reversible
6. Test with real Flywheel documents (meeting prep output, company intel) to calibrate

**Detection:** Log redaction counts per document. Alert on documents where >20% of content is redacted (likely false positives).

---

### Pitfall 10: Presidio Model Download Size and Cold Start

**What goes wrong:** Presidio's NLP engine (spaCy `en_core_web_lg`) is ~560MB. First import triggers a download. In a Docker container:
- Image size balloons by 500-600MB
- Cold start adds 5-15 seconds for model loading
- Railway free tier may hit memory limits

**Prevention:**
1. Install the spaCy model in the Dockerfile: `RUN uv run python -m spacy download en_core_web_lg`
2. Consider `en_core_web_sm` (~12MB) for initial implementation -- lower accuracy but much faster
3. Lazy-load Presidio only when PII redaction is requested, not on app startup
4. Cache the analyzer instance as a module-level singleton

---

## Minor Pitfalls

---

### Pitfall 11: Export Filename Sanitization is Incomplete

**What goes wrong:** The filename sanitization in `documents.py` line 675 uses `re.sub(r"[^\w\s\-]", "", doc.title)`. This allows spaces and underscores but:
- Unicode characters in titles may produce garbled filenames on Windows
- Very long titles get truncated to 60 chars which may cut mid-word
- The `Content-Disposition` header doesn't use RFC 5987 encoding for non-ASCII

**Prevention:**
1. Use `filename*=UTF-8''...` encoding in Content-Disposition for non-ASCII support
2. Truncate at word boundaries, not character count
3. Add a fallback `filename="document.pdf"` alongside the encoded version

---

### Pitfall 12: Jinja2 Template Autoescape Strips Structured Data

**What goes wrong:** The Jinja2 environment in `output_renderer.py` line 395 sets `autoescape=True`. When `structured_data` is passed to the one-pager template, any HTML entities in the structured JSON values (like `&amp;` in company names or `<` in comparison text) get double-escaped.

**Evidence:**
- `backend/src/flywheel/engines/output_renderer.py` line 395: `autoescape=True`
- `backend/src/flywheel/engines/templates/outputs/one_pager.html` line 9: `{{ d.headline }}` -- autoescaped

**Prevention:** This is actually correct for XSS protection. But if structured data contains intentional HTML (like `<strong>`), use `{{ d.field | safe }}` selectively. The current template does NOT use `| safe` on structured fields, which is the safe default.

---

### Pitfall 13: OnePagerRenderer Assumes All Arrays are Non-Empty

**What goes wrong:** The React renderer (`OnePagerRenderer.tsx`) checks `.length > 0` for stats_banner (line 62), problem_columns (line 106), and outcomes (line 164). But it does NOT null-check `comparison_table` before accessing `.rows` -- if the LLM omits the comparison_table entirely, `data.comparison_table.rows.length` will throw.

**Evidence:**
- `frontend/src/features/documents/types/one-pager.ts` line 57: `comparison_table: OnePagerComparisonTable` -- NOT optional in the type
- `frontend/src/features/documents/components/renderers/OnePagerRenderer.tsx` line 207: `data.comparison_table && data.comparison_table.rows.length > 0` -- has the null check here, but...
- The TypeScript type says it's required, while the LLM may not always produce it

**Prevention:**
1. Make `comparison_table` optional in the TypeScript type: `comparison_table?: OnePagerComparisonTable`
2. Also make `audit_trail`, `capability_hint`, `cta`, and `footnotes` optional since LLMs may omit them
3. The type guard `isOnePagerData` should match what the renderer actually requires, not what the ideal schema specifies

---

### Pitfall 14: Backend JSON Detection is Fragile

**What goes wrong:** Both `_try_parse_structured` (document_export.py line 345) and the output_renderer (line 508) detect structured JSON by checking if `output.strip().startswith("{")`. This fails when:
- The LLM outputs JSON wrapped in markdown fences: ` ```json\n{...}\n``` `
- The LLM prepends text: "Here is the one-pager:\n{...}"
- The output is a JSON array `[...]` instead of object

**Prevention:**
1. Add a `_extract_json` helper that strips markdown fences, finds the outermost `{...}` or `[...]`, then parses
2. Centralize JSON detection in one function used by both renderer and export service
3. Log extraction failures with the raw output prefix for debugging

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Structured JSON output | Pitfall 2, 3: LLM produces invalid JSON or structured outputs conflict with tool_use | Use Anthropic structured outputs API. Test with real multi-turn tool_use conversations. Add robust JSON extraction fallback. |
| PDF export with WeasyPrint | Pitfall 1, 4, 7: Missing deps, blocks event loop, font differences | Add system deps to Dockerfile. Run in thread pool. Embed fonts. Budget 200MB Docker image increase. |
| DOCX export | Pitfall 6, 7: Hardcoded columns, font mismatch | Make column count dynamic. Use Calibri fallback. Test with real data. |
| File upload | Pitfall 8: Security, size limits, temp file cleanup, multi-tenant isolation | Validate magic bytes. Enforce size limits. Tenant-scoped storage. Temp file cleanup. |
| PII redaction | Pitfall 9, 10: False positives destroy content, model download bloats image | Start with minimal recognizers. Domain allow-list. Preview mode. Use small spaCy model initially. |
| Integration testing | All pitfalls | Need end-to-end tests covering: JSON parse -> render -> export for each format. Mock LLM output with known-good and known-bad JSON. |

---

## Pre-GSD Code Issues Summary

Concrete issues found in the existing code that must be fixed:

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| `backend/pyproject.toml` | deps | WeasyPrint not listed as dependency | CRITICAL -- PDF export will crash |
| `backend/Dockerfile` | 1 | No system library installation for WeasyPrint | CRITICAL -- runtime ImportError |
| `backend/src/flywheel/services/document_export.py` | 57 | Runtime import of missing dependency | CRITICAL |
| `backend/src/flywheel/services/document_export.py` | 367-378 | `_wrap_fragment_as_document` skips HTML sanitization | HIGH -- XSS risk |
| `backend/src/flywheel/services/document_export.py` | 254 | Hardcoded `cols=3` in comparison table | MEDIUM |
| `backend/src/flywheel/services/document_export.py` | 345 | Fragile JSON detection (`startswith("{")`) | MEDIUM |
| `backend/src/flywheel/api/documents.py` | 678-679 | Sync PDF generation blocks async event loop | HIGH |
| `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` | 41-44 | Silent JSON.parse failure with empty catch | MEDIUM |
| `frontend/src/features/documents/types/one-pager.ts` | 52-67 | Required fields that LLM may omit (comparison_table, audit_trail, etc.) | MEDIUM |
| `skills/one-pager/SKILL.md` | 251-254 | Relies on prompt-only JSON enforcement instead of structured outputs API | HIGH |

---

## Sources

- [Anthropic Structured Outputs Documentation (official, GA)](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- HIGH confidence
- [WeasyPrint Installation Docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) -- HIGH confidence
- [WeasyPrint Docker Issues](https://github.com/Kozea/WeasyPrint/issues/2221) -- Railway-specific gobject dependency issue
- [WeasyPrint Alpine Installation](https://github.com/Kozea/WeasyPrint/issues/699) -- system deps list
- [Presidio PII Evaluation](https://microsoft.github.io/presidio/evaluation/) -- HIGH confidence
- [Presidio False Positive Analysis](https://anonym.legal/blog/false-positive-tax-pii-detection-precision-2025) -- MEDIUM confidence (third-party analysis)
- [Presidio FAQ](https://microsoft.github.io/presidio/faq/) -- HIGH confidence
- Direct codebase analysis of all pre-GSD files listed in milestone context -- HIGH confidence
