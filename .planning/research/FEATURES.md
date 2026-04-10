# Feature Landscape

**Domain:** Structured skill output, document export, file upload, PII redaction for AI-powered founder intelligence platform
**Researched:** 2026-04-10

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Existing Code | Notes |
|---------|--------------|------------|---------------|-------|
| PDF export that works | Every doc platform exports PDF. Users share with investors, partners, board. | Low | `document_export.py` exists with WeasyPrint. `DocumentViewer.tsx` has full export dropdown UI. Backend endpoint at `GET /documents/{id}/export?format=pdf`. | Wire is complete end-to-end. Needs WeasyPrint installed on prod + testing across skill types. |
| DOCX export that works | Users need editable versions for client/investor decks. Google Docs import requires DOCX. | Low | `document_export.py` has full DOCX builder using python-docx. One-pager gets branded structured DOCX. Others get markdown-to-text fallback. | Wire complete. Generic skills get ugly plain-text DOCX. Improve fallback quality. |
| Export preserves formatting | PDF/DOCX must look close to the web view. Broken formatting = "this tool is amateur". | Med | PDF uses `render_output_standalone()` which inlines CSS. DOCX has structured builder for one-pager only. | PDF path is solid via standalone HTML+CSS. DOCX generic path needs markdown heading/list/table parsing, not just `.split("\n")`. |
| File upload for skill input | Users have contracts, pitch decks, competitive docs they want analyzed. Typed-text-only input is limiting. | Low | Full file upload pipeline exists: `POST /files/upload`, text extraction (PDF/DOCX/TXT via pdfplumber+python-docx), Supabase Storage, `UploadedFile` model. Skill executor already handles `document:` prefix for file IDs. | Backend complete. Frontend needs file picker in skill run UI, not just text input. |
| Upload progress feedback | Users uploading 5MB PDFs need visual confirmation something is happening. | Low | None on frontend. | Indeterminate progress bar during upload, then "Extracting text..." state, then "Running skill..." state. Three-phase progress. |
| Structured JSON skill output | Skills producing typed data (one-pager, legal review) need pixel-perfect rendering, not markdown-to-HTML. | Med | One-pager has full pipeline: `OnePagerData` TypeScript interface, `isOnePagerData()` type guard, `OnePagerRenderer.tsx`, JSON detection in `SkillRenderer.tsx`. Pattern established. | Extend pattern to legal review. Schema: `document_type` discriminator + `schema_version` + typed fields. |
| Legal review with risk visualization | Legal doc reviews need severity colors, risk badges, clause-by-clause breakdown. Generic markdown is insufficient. | Med | Backend `legal_review.html` Jinja2 template exists with severity badges. No frontend React renderer yet (falls through to GenericRenderer). | Build `LegalReviewRenderer.tsx` following `OnePagerRenderer.tsx` pattern. Define `LegalReviewData` interface. |
| One-pager interactive viewer | Value prop one-pagers need stats banners, comparison tables, CTA buttons. Already partially built. | Low | `OnePagerRenderer.tsx` is fully built and rendering from structured JSON. | Already table stakes and delivered. Polish only. |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Existing Code | Notes |
|---------|-------------------|------------|---------------|-------|
| PII redaction before skill processing | Founders uploading NDAs/contracts expect confidentiality. Pre-processing strips PII before LLM sees it, then re-inserts in output. | High | Archived `pii-redactor` skill has full Presidio pipeline: detect, anonymize (4 modes), audit log, reverse mapping, seed mapping for cross-doc consistency. `redact.py` is 560 lines of production code. | Requires spaCy model download (~500MB `en_core_web_lg`). Move from archived CLI script to backend service. Pre-process flow: upload -> extract text -> detect PII -> anonymize -> run skill -> de-anonymize output. |
| PII audit trail | Show user exactly what was redacted and why. Builds trust. "We found 12 PII entities and protected them." | Low | `generate_audit_log()` in `redact.py` produces markdown audit with entity type, confidence, line numbers. | Surface as collapsible section in legal review viewer. |
| Smart export format selection | Auto-suggest PDF for sharing, DOCX for editing. Show "Share as PDF" vs "Edit in Word" labels. | Low | Export dropdown exists with both options. | Rename from "Download PDF" / "Download DOCX" to intent-based labels. |
| One-pager as shareable landing page | One-pagers should be shareable as branded web pages, not just downloads. Already have share URL infra. | Med | `shareDocument()` API exists. Share URLs work. But shared view uses same renderer as logged-in view. | Shared one-pager could be a standalone branded page with CTA button that actually links out. |
| Multi-file upload for skill input | Upload contract + amendment together. Legal review skill compares them. | Med | Skill executor already handles `supplementary_file_ids` for multi-file scenarios. `UploadedFile` model supports it. | Frontend needs multi-file picker. Skill prompt template needs to handle "primary doc" vs "supplementary docs" framing. |
| Structured output schema registry | Central registry of JSON schemas per skill type. Validates LLM output. Enables automatic renderer dispatch. | Med | Ad-hoc: `isOnePagerData()` type guard in TS, `_try_parse_structured()` in Python. No formal registry. | Define schemas in shared location. Use `document_type` + `schema_version` as discriminator. Zod on frontend, Pydantic on backend. |
| Export with brand customization | User uploads their logo, export uses it. | High | None. | Defer. Nice-to-have for enterprise tier. |
| Inline PII highlighting | Before submitting, show user highlighted PII in their uploaded document. "We detected these. Proceed?" | Med | Detection exists in `redact.py`. No frontend visualization. | Show uploaded text with highlighted spans. User confirms before skill runs. Builds trust significantly. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time collaborative editing of exports | Scope explosion. Google Docs already does this. Users export to edit elsewhere. | Export clean DOCX that opens well in Google Docs / Word. |
| Custom template builder | Users designing their own export templates is a product unto itself. | Ship good defaults. Iterate on templates based on feedback. |
| OCR for scanned PDFs | pdfplumber handles text-based PDFs. OCR (Tesseract) adds massive complexity and unreliable results. | Reject image-only PDFs with clear error: "Please upload a text-based PDF." |
| Client-side PII detection | Running spaCy/Presidio in-browser is infeasible (~500MB model). | Server-side only. Text never leaves your infra before redaction. |
| PII redaction as user-togglable feature | Letting users skip PII redaction on legal docs creates liability. | Always redact for legal-category skills. Optional for other skill types. |
| Universal file format support (XLS, PPT, images) | Each format is a rabbit hole. Start with the 80% case. | PDF + DOCX + TXT/MD only. Same as current `ALLOWED_MIMETYPES`. Expand later based on demand. |
| Drag-and-drop reordering of export sections | Over-engineering. Users want to download, not rearrange. | Fixed section order matching the web view. |

## Feature Dependencies

```
File Upload API (exists) -> File Picker UI (new) -> Skill Run with File Input (connect)
                                                  -> Multi-File Upload UI (new)

Text Extraction (exists) -> PII Detection Service (port from archived) -> PII Anonymization
                                                                       -> PII Audit Trail
                                                                       -> Inline PII Preview (frontend)

PII Anonymization -> Skill Execution -> PII De-anonymization -> Document Output
                                                              -> Legal Review Renderer

Structured JSON Schema (one-pager pattern) -> Legal Review Schema + Type Guard
                                            -> LegalReviewRenderer.tsx
                                            -> Legal Review DOCX Export
                                            -> Schema Registry (future)

render_output_standalone() (exists) -> WeasyPrint PDF (exists) -> PDF Export Endpoint (exists)
                                                                -> Test all skill types

python-docx builder (exists) -> Generic DOCX Improvement (markdown parsing)
                              -> Legal Review DOCX (structured builder)
```

## MVP Recommendation

Prioritize (in order):

1. **PDF/DOCX export working end-to-end** -- The code exists. Just need WeasyPrint in prod dependencies, test each skill type, improve generic DOCX quality. Highest ROI: zero new code, just integration + polish.

2. **File picker UI for skill input** -- Backend file upload + extraction + skill executor wiring all exist. Missing piece is a frontend file upload widget in the skill run flow. Users are blocked from using legal review and competitive analysis on their actual documents.

3. **Legal review structured JSON output + renderer** -- Follow the one-pager pattern exactly. Define `LegalReviewData` interface, build `LegalReviewRenderer.tsx`, update skill prompt to output JSON. This is the second structured skill, proving the pattern scales.

4. **PII redaction service** -- Port `redact.py` from archived CLI to a backend service module. Wire into skill executor as a pre-processing step for legal-category skills. This is the most complex feature but the most differentiated.

5. **PII audit trail in legal review viewer** -- Once PII redaction is a service, surface the audit data in the legal review renderer. Low effort, high trust signal.

Defer:
- **Multi-file upload**: Working single-file upload is the priority. Multi-file is a Phase 2 concern.
- **Inline PII highlighting**: Nice UX polish but not blocking. Ship "we redacted N entities" summary first.
- **Schema registry**: Two skills (one-pager + legal review) don't need a registry. Build it when there are 4+ structured skills.
- **Brand customization on exports**: Enterprise feature. Not needed for founder dogfooding.

## Sources

- Codebase analysis: `backend/src/flywheel/services/document_export.py`, `backend/src/flywheel/api/files.py`, `backend/src/flywheel/services/file_extraction.py`, `skills/_archived/pii-redactor/scripts/redact.py`
- Existing renderers: `frontend/src/features/documents/components/renderers/OnePagerRenderer.tsx`, `frontend/src/features/documents/types/one-pager.ts`
- Existing export UI: `frontend/src/features/documents/components/DocumentViewer.tsx` (lines 206-259)
- Existing skill executor file handling: `backend/src/flywheel/services/skill_executor.py` (supplementary_file_ids pattern)
- [Uploadcare UX Best Practices for File Upload](https://uploadcare.com/blog/file-uploader-ux-best-practices/)
- [Microsoft Presidio Documentation](https://microsoft.github.io/presidio/)
- [Eleken File Upload UI Tips](https://www.eleken.co/blog-posts/file-upload-ui)
