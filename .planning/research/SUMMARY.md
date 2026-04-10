# Project Research Summary

**Project:** Flywheel V2 — Structured Skill Output + Export + Upload + PII
**Domain:** AI-powered document generation with structured output, multi-format export, file input, and PII redaction
**Researched:** 2026-04-10
**Confidence:** HIGH

## Executive Summary

This milestone completes the output pipeline for Flywheel's skill engine: getting rich structured documents out of LLM skills and into user hands as polished PDFs, editable DOCX files, and interactive web views. The underlying infrastructure is largely in place — file upload, text extraction, HTML rendering, and export endpoints all exist. The primary work is wiring these systems together, filling dependency gaps, and extending the one-pager structured output pattern to additional skill types such as legal review.

The recommended approach is to follow the one-pager precedent precisely for every new structured skill. This pattern is proven end-to-end across backend rendering (Jinja2 templates), frontend display (typed React renderers with type guards), and export (PDF via WeasyPrint, DOCX via python-docx). The biggest infrastructure gap is that WeasyPrint — already imported by the export service — is missing from pyproject.toml and from the Docker image's system libraries. This must be fixed before PDF export can reach production. PII redaction is the most complex new capability, requiring a service port from the archived pii-redactor skill plus an on-demand architecture that redacts at export/share time rather than before storage.

The key risk is fragile JSON parsing throughout the stack. The one-pager skill currently relies on prompt-only JSON enforcement, with bare JSON.parse in the frontend and startswith("{") detection on the backend. Upgrading to Anthropic's structured outputs API (output_config) eliminates this class of bug at the token level and should be the first architectural improvement. PII redaction carries a secondary risk of false positives destroying business-critical content (company names misidentified as PERSON entities); mitigation requires a restricted entity list, a score threshold, and a user preview before redaction is finalized.

## Key Findings

### Recommended Stack

Most required technology is already installed. The only new pip dependencies are WeasyPrint (PDF generation), presidio-analyzer + presidio-anonymizer + spaCy (PII redaction), and an Anthropic SDK version bump from 0.84.0 to >=0.93.0 to enable native structured outputs. The SDK upgrade is the highest-leverage change: it replaces brittle prompt-only JSON enforcement with constrained decoding that guarantees schema-valid output.

WeasyPrint requires system C libraries (Cairo, Pango, GDK-Pixbuf, libffi) that must be added to the Dockerfile before deployment — missing these causes a silent runtime ImportError that the export endpoint catches and converts to HTTP 501. For PII, the small spaCy model (en_core_web_sm, ~12MB) is recommended over en_core_web_lg (~560MB): Presidio's regex-based recognizers handle most structured PII (email, phone, SSN), and spaCy NER is only needed for names/organizations where the accuracy delta is negligible.

**Core technologies:**
- `anthropic>=0.93.0`: Structured outputs via `output_config` — eliminates JSON parse failures
- `weasyprint>=68.0`: HTML-to-PDF using existing Jinja2 templates — only viable option with full CSS3 support
- `presidio-analyzer + presidio-anonymizer>=2.2.362`: Local PII detection and anonymization — avoids external API cost and data egress
- `spacy>=3.7` with `en_core_web_sm`: NLP engine for Presidio — small model, negligible accuracy tradeoff
- `python-docx>=1.2.0`: Already installed; write path generates DOCX from structured JSON

### Expected Features

**Must have (table stakes):**
- PDF and DOCX export working end-to-end — code exists, dependencies missing; highest ROI fix
- Export formatting that matches the web view — PDF path is solid; generic DOCX needs markdown heading/list parsing
- File upload as skill input — backend pipeline complete; frontend file picker is the missing piece
- Upload progress feedback — three-phase UX: uploading → extracting text → running skill
- Structured JSON output for skills requiring typed rendering — one-pager pattern established; extend to legal review
- Legal review renderer with risk visualization — severity badges, clause breakdown; backend template exists, React renderer does not

**Should have (differentiators):**
- PII redaction as a service before skill output is shared externally
- PII audit trail surfaced in legal review viewer — "we protected 12 entities"
- Intent-based export labels — "Share as PDF" vs "Edit in Word" instead of format names
- Multi-file upload for skill input — infrastructure supports it; frontend and prompt framing needed
- Inline PII preview before skill runs — show highlighted spans, user confirms

**Defer (v2+):**
- Multi-file upload (single-file first, multi-file is Phase 2)
- Inline PII highlighting (show summary count first)
- Schema registry for structured outputs (needed at 4+ structured skills, not 2)
- Brand customization on exports (enterprise tier)
- Shareable one-pager as standalone branded web page

### Architecture Approach

The system follows a layered pipeline: skills execute via a tool_use loop in skill_executor.py, producing raw output stored in SkillRun.output; the output renderer converts this to HTML stored in SkillRun.rendered_html; the export service converts rendered HTML to PDF (via WeasyPrint) or structured JSON to DOCX (via python-docx); and the frontend's SkillRenderer dispatches to typed React renderers based on JSON type guards. Every new structured skill type requires coordinated additions across exactly four locations: TypeScript types + type guard, React renderer component, Jinja2 HTML template, and DOCX export branch in document_export.py. PII redaction belongs at the export/share boundary only — inserting it pre-storage destroys data that skills need (attendee names in meeting prep, emails in outreach).

**Major components:**
1. `skill_executor.py` — tool_use loop, file_ids resolution, structured output config injection
2. `output_renderer.py` — TYPE_MAP dispatch, Jinja2 template rendering, HTML standalone wrapping for PDF
3. `document_export.py` — PDF (WeasyPrint) and DOCX (python-docx) generation with structured data branches
4. `pii_redactor.py` (new) — Presidio-based service called at export/share time, not during execution
5. `SkillRenderer.tsx` — frontend dispatch hub via type guards to dedicated renderers
6. `{Type}Renderer.tsx` components — rich interactive display of typed structured JSON

### Critical Pitfalls

1. **WeasyPrint not in dependencies + missing Docker system libs** — Add `weasyprint>=68.0` to pyproject.toml AND add `libpango1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev` to Dockerfile before pip install. Failure mode is a silent runtime ImportError → HTTP 501 in production.

2. **LLM JSON output is prompt-only enforced** — Migrate skills that require structured output to Anthropic's `output_config` API. Add a robust `_extract_json()` utility (strip markdown fences, find outermost `{}`/`[]`) as fallback. Never use bare JSON.parse without extraction preprocessing.

3. **PDF export blocks the async event loop** — Wrap `export_as_pdf()` in `asyncio.to_thread()`. WeasyPrint is CPU-bound and will stall all concurrent requests for 2-10 seconds per export.

4. **XSS via unsanitized HTML in export** — `_wrap_fragment_as_document()` in `document_export.py` skips the existing `sanitize_html()` function before serving HTML to browsers. Import and apply it consistently.

5. **Presidio false positives destroy business content** — Start with a restricted entity list (EMAIL_ADDRESS, PHONE_NUMBER, US_SSN only), set `score_threshold=0.7`, and build a domain allow-list for company/product names from the context store. Never redact silently — always show users a preview count and offer a review step.

## Implications for Roadmap

Based on combined research, the dependency graph and code readiness point to four natural phases:

### Phase 1: Foundation Fixes + Export Working
**Rationale:** The highest ROI work is making already-written code actually work in production. WeasyPrint dependency gaps and JSON fragility are blocking issues that affect everything downstream. Fix infrastructure before building features on top of it.
**Delivers:** Working PDF export, working DOCX export, structured JSON output enforced by API (not prompt), hardened JSON extraction utility
**Addresses:** PDF/DOCX export table stakes, export formatting fidelity
**Avoids:** Pitfall 1 (WeasyPrint deps), Pitfall 2 (fragile JSON), Pitfall 4 (async blocking), Pitfall 5 (XSS)
**Stack:** `anthropic>=0.93.0` upgrade, WeasyPrint system deps in Dockerfile, `asyncio.to_thread` for export
**Research flag:** SKIP — all patterns are documented and code exists; no unknowns

### Phase 2: Structured Legal Review Skill
**Rationale:** Extending the one-pager pattern to a second skill type proves the pattern scales and delivers user value. Legal review is the natural second structured skill: backend Jinja2 template already exists, only the React renderer and TypeScript types are missing.
**Delivers:** `LegalReviewData` TypeScript interface + type guard, `LegalReviewRenderer.tsx` with severity badges and clause breakdown, legal review DOCX export branch
**Addresses:** Legal review structured rendering (table stakes), structured JSON schema extensibility
**Avoids:** Pitfall 13 (optional fields must be marked optional in types), Pitfall 6 (dynamic DOCX column count), Pitfall 14 (centralized JSON extraction)
**Uses:** Structured outputs API from Phase 1
**Research flag:** SKIP — follows one-pager pattern exactly, all patterns documented in ARCHITECTURE.md

### Phase 3: File Upload for Skill Input
**Rationale:** Backend file upload, extraction, and executor wiring all exist. The only missing piece is a frontend file picker in the skill run UI. This unblocks users from running legal review and competitive analysis on their own documents.
**Delivers:** File upload dropzone in skill input form, `file_ids` field on `StartRunRequest`, file text injection into skill system prompt, three-phase progress UX (uploading → extracting → running)
**Addresses:** File upload table stakes, upload progress feedback
**Avoids:** Pitfall 8 (file security: magic byte validation, size limits, tenant-scoped storage, temp file cleanup)
**Uses:** Existing `api/files.py`, `UploadedFile` model, executor's `extracted_text` resolution
**Research flag:** SKIP — backend infrastructure complete, pattern is Option B from ARCHITECTURE.md

### Phase 4: PII Redaction Service
**Rationale:** Most complex new capability, deliberately deferred until the simpler features are stable. PII redaction at export/share boundary is architecturally clean and doesn't require touching the execution path. Port from the archived pii-redactor skill which has 560 lines of production-ready Presidio code.
**Delivers:** `services/pii_redactor.py` service module, `redact_pii` query param on export endpoint, auto-redaction on shared document links, PII audit trail section in legal review renderer
**Addresses:** PII redaction differentiator, PII audit trail, user trust for legal document processing
**Avoids:** Pitfall 9 (false positives — restricted entity list, score threshold, allow-list), Pitfall 10 (model size — use en_core_web_sm, lazy-load singleton)
**Uses:** `presidio-analyzer`, `presidio-anonymizer`, `spacy en_core_web_sm`
**Research flag:** NEEDS PHASE RESEARCH — Presidio entity configuration for B2B sales context (company names, deal terminology) needs calibration against real Flywheel documents before finalizing the allow-list and score thresholds

### Phase Ordering Rationale

- Phase 1 first because broken dependencies and fragile JSON parsing cascade into all other phases. Building on a cracked foundation wastes effort.
- Phase 2 before Phase 3 because legal review is the primary use case for file upload. Having the renderer ready means file upload immediately surfaces rich output rather than markdown fallback.
- Phase 3 before Phase 4 because PII redaction is most valuable on user-uploaded documents (contracts, NDAs). Without file upload, PII redaction has limited real-world testing surface.
- Phase 4 last because it's the only phase with genuine unknowns (Presidio calibration) and requires Phases 2+3 to have meaningful test documents.

### Research Flags

Phases needing deeper research during planning:
- **Phase 4 (PII Redaction):** Presidio false positive rate in B2B sales context needs empirical calibration. Need to run against real Flywheel meeting prep output, company intel, and legal review documents to tune entity list and score thresholds. The archived `redact.py` has the scaffolding but entity configuration was CLI-oriented, not service-oriented.

Phases with standard patterns (skip research-phase):
- **Phase 1:** All changes are dependency additions and known async patterns. Official docs exist for all.
- **Phase 2:** Exact copy of one-pager pattern, fully documented in codebase.
- **Phase 3:** Option B architecture (file_ids on StartRunRequest) is well-specified in ARCHITECTURE.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified on PyPI. Anthropic SDK structured output API verified against official docs. WeasyPrint system deps verified from official installation docs. |
| Features | HIGH | Based on direct codebase analysis. Existing code status verified line-by-line. Feature priorities derived from concrete code gaps, not speculation. |
| Architecture | HIGH | Based entirely on reading the actual codebase (skill_executor.py, output_renderer.py, document_export.py, SkillRenderer.tsx). One-pager pattern is proven in production. |
| Pitfalls | HIGH | Critical pitfalls verified by reading specific file + line numbers in the pre-GSD code. WeasyPrint Docker issue verified via GitHub issues. Presidio false positive rate cited from official evaluation docs. |

**Overall confidence:** HIGH

### Gaps to Address

- **Structured outputs + tool_use interaction in production:** The Anthropic docs confirm these are compatible, but behavior when `output_config` is set and the model makes multiple tool_use rounds before `end_turn` needs empirical verification in the executor. Test this early in Phase 1 implementation.
- **WeasyPrint Docker image size:** Adding system libs adds 150-250MB to the image. Whether this is acceptable for Railway deployment tiers needs a check against the current image size and Railway limits.
- **Presidio entity calibration:** The specific allow-list and score thresholds for Flywheel's B2B domain cannot be determined from research alone — they require testing against real documents. Phase 4 must include a calibration step before final wiring.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/skill_executor.py` — execution flow, tool_use loop, file handling
- `backend/src/flywheel/engines/output_renderer.py` — rendering pipeline, TYPE_MAP, structured data detection
- `backend/src/flywheel/services/document_export.py` — PDF/DOCX generation, structured branches
- `backend/src/flywheel/api/documents.py` — export endpoint, HTML content serving
- `backend/src/flywheel/api/files.py` — file upload, text extraction pipeline
- `frontend/src/features/documents/components/renderers/SkillRenderer.tsx` — frontend dispatch
- `frontend/src/features/documents/components/renderers/OnePagerRenderer.tsx` — structured renderer pattern
- `frontend/src/features/documents/types/one-pager.ts` — TypeScript type + type guard pattern
- `skills/_archived/pii-redactor/scripts/redact.py` — Presidio implementation (560 lines)
- [Anthropic Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — structured output API
- [Anthropic Python SDK PyPI](https://pypi.org/project/anthropic/) — v0.93.0 confirmed
- [WeasyPrint PyPI](https://pypi.org/project/weasyprint/) — v68.1 confirmed
- [WeasyPrint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) — system deps
- [Presidio analyzer PyPI](https://pypi.org/project/presidio-analyzer/) — v2.2.362 confirmed
- [Presidio installation docs](https://microsoft.github.io/presidio/installation/) — setup
- [python-docx docs](https://python-docx.readthedocs.io/en/latest/user/quickstart.html) — write API

### Secondary (MEDIUM confidence)
- [spaCy models page](https://spacy.io/models) — sm vs lg accuracy comparison
- [Presidio false positive analysis](https://anonym.legal/blog/false-positive-tax-pii-detection-precision-2025) — 22.7% precision in enterprise datasets
- [WeasyPrint Docker GitHub issues](https://github.com/Kozea/WeasyPrint/issues/2221) — Railway-specific gobject dependency

---
*Research completed: 2026-04-10*
*Ready for roadmap: yes*
