# Technology Stack: Structured Output, Export, Upload, PII Redaction

**Project:** Flywheel V2 - Milestone: Structured Skill Output + Export + Upload + PII
**Researched:** 2026-04-10
**Overall confidence:** HIGH

## Context: What Already Exists

These are already in `pyproject.toml` and working. DO NOT re-add or change:

| Existing Dep | Version | Current Use |
|---|---|---|
| `anthropic` | >=0.86.0 (installed: 0.84.0) | Skill executor tool_use loop via `AsyncAnthropic` |
| `python-docx` | >=1.2.0 | Read-only DOCX text extraction in `file_extraction.py` |
| `pdfplumber` | >=0.11.9 | PDF text extraction in `file_extraction.py` |
| `python-multipart` | >=0.0.22 | FastAPI `UploadFile` support (already used in `api/files.py`) |
| `pydantic` | >=2.0 | Request/response models, settings |
| `jinja2` | (via FastAPI) | HTML template rendering in `output_renderer.py` |
| `beautifulsoup4` | >=4.12 | HTML sanitization in `output_renderer.py` |
| `markdown` | >=3.10.2 | Markdown processing |

**Key finding:** File upload infrastructure is already complete (`api/files.py`, `file_extraction.py`, `document_storage.py`, `UploadedFile` model). The skill executor already handles `DOCUMENT_FILE:` prefixed inputs for uploaded documents. No new upload work needed at the API layer.

---

## NEW Dependencies Required

### 1. Anthropic SDK Upgrade (structured JSON output)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `anthropic` | **>=0.93.0** | Structured output via `output_config.format` | Current 0.84.0 predates structured outputs (GA in SDK ~0.77.0+). Need `client.messages.create(output_config=...)` and `client.messages.parse()` with Pydantic models. |

**Integration point:** `skill_executor.py` line ~3306 (`_execute_with_tools`). The tool_use loop calls `client.messages.create()`. For structured output skills, the FINAL call (after all tools resolve, on `end_turn`) should use `output_config` to guarantee JSON schema compliance.

**Critical nuance:** Structured JSON output (`output_config.format`) and tool_use (`tools=`) CAN be combined in the same request. Claude will use tools normally and produce structured JSON on the final `end_turn`. This means the existing tool_use loop works -- just add `output_config` to the `messages.create()` call for skills that declare structured output.

**How it works with Pydantic:**
```python
from pydantic import BaseModel

class SkillOutput(BaseModel):
    title: str
    sections: list[dict]
    metadata: dict

# SDK auto-converts Pydantic to JSON schema
response = await client.messages.parse(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    output_format=SkillOutput,  # SDK translates to output_config internally
    messages=messages,
)
parsed = response.parsed_output  # typed SkillOutput
```

**Schema limitations to know:**
- No recursive schemas
- `additionalProperties` must be `false` for objects
- No `minimum`/`maximum`/`minLength`/`maxLength` constraints
- `minItems` only supports 0 or 1
- Required properties appear first in output (reordered)

**Confidence:** HIGH -- verified from official Anthropic docs (platform.claude.com)

---

### 2. WeasyPrint (PDF generation from HTML)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `weasyprint` | **>=68.0** | Convert rendered HTML to PDF | Best Python HTML-to-PDF library. Full CSS3 support (flexbox, grid, media queries). No browser engine needed. Uses pydyf for PDF generation (since v53). Existing Jinja2 HTML templates can be reused directly. |

**System dependencies (macOS):**
```bash
brew install cairo pango gdk-pixbuf libffi
```

**System dependencies (Linux/Docker):**
```bash
apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

**Integration point:** New `services/export_service.py` that takes rendered HTML (already stored in `SkillRun.rendered_html`) and converts to PDF bytes via `weasyprint.HTML(string=html).write_pdf()`. The existing `output_renderer.py` templates already produce standalone HTML with embedded CSS -- these are ready for PDF conversion.

**Why not alternatives:**
- **xhtml2pdf**: Pure Python (no system deps) but limited to CSS 2.1. No flexbox/grid. Existing templates use modern CSS.
- **pdfkit/wkhtmltopdf**: Requires headless WebKit binary. wkhtmltopdf is archived (Jan 2023), no longer maintained.
- **reportlab**: Low-level PDF builder. Would require rewriting all templates as Python code instead of reusing HTML.

**Confidence:** HIGH -- WeasyPrint 68.1 verified on PyPI, system deps verified from official docs.

---

### 3. python-docx (write path -- already installed)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `python-docx` | **>=1.2.0** (already in deps) | Generate DOCX from structured skill output | Already installed for read. Write path uses same library: `Document()`, `add_heading()`, `add_paragraph()`, `add_table()`. No new dependency needed. |

**Integration point:** New `services/export_service.py` alongside PDF export. Takes structured JSON output (from structured output feature) and builds DOCX programmatically. Unlike PDF (which converts existing HTML), DOCX generation maps structured data to Word elements directly.

**Key capabilities already available in 1.2.0:**
- Headings (levels 1-9)
- Paragraphs with bold/italic/underline runs
- Tables with cell spanning and built-in styles
- Page breaks
- Document properties (title, author)
- Styles (built-in Word styles like "Heading 1", "List Bullet", table styles)

**Why not HTML-to-DOCX conversion:**
- No reliable HTML-to-DOCX converter exists in Python
- `mammoth` goes DOCX-to-HTML only (wrong direction)
- `htmldocx` is unmaintained and produces poor output
- Building from structured JSON gives full control over Word formatting

**Confidence:** HIGH -- python-docx 1.2.0 docs verified, already in pyproject.toml.

---

### 4. Presidio (PII redaction)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| `presidio-analyzer` | **>=2.2.362** | Detect PII entities in text | Microsoft's open-source PII detection. Supports 30+ entity types (names, emails, SSNs, phone numbers, credit cards, etc.). Pluggable recognizer architecture. |
| `presidio-anonymizer` | **>=2.2.362** | Redact/mask/encrypt detected PII | Companion to analyzer. Supports mask, replace, encrypt, hash operators. |
| `spacy` | **>=3.7** | NLP engine for Presidio | Required by presidio-analyzer for NER. |

**spaCy model choice: `en_core_web_sm` (not `en_core_web_lg`)**

Use the small model because:
- NER accuracy difference is negligible (0.85 vs 0.86 recall on standard benchmarks)
- `en_core_web_sm` is ~12MB vs `en_core_web_lg` at ~560MB
- Presidio's pattern-based recognizers (regex for emails, SSNs, credit cards) do most of the heavy lifting -- spaCy NER only handles names/locations/organizations
- For a founder-facing product processing business documents, the entity types are predictable (names, emails, phone numbers, addresses) -- not edge-case NLP

**Installation:**
```bash
pip install presidio-analyzer presidio-anonymizer spacy
python -m spacy download en_core_web_sm
```

**Integration point:** New `services/pii_service.py` that wraps Presidio. Called from:
1. **Pre-LLM:** Optionally redact PII from uploaded documents before sending to Claude (privacy-preserving processing)
2. **Post-LLM:** Redact PII from skill output before storage/display (contract review, legal docs)
3. **Export:** Redact PII in exported PDF/DOCX on demand

**Presidio usage pattern:**
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()  # loads spaCy model once
anonymizer = AnonymizerEngine()

results = analyzer.analyze(text=content, language="en")
redacted = anonymizer.anonymize(text=content, analyzer_results=results)
```

**Why Presidio over alternatives:**
- **regex-only**: Misses names, organizations, context-dependent PII
- **AWS Comprehend / Google DLP**: External API calls, cost per request, data leaves your infra
- **spaCy NER alone**: No anonymization layer, no pattern recognizers for structured PII (SSN, credit card)
- **Presidio**: Local, free, combines regex + NER, built-in anonymization operators

**Confidence:** HIGH -- presidio-analyzer 2.2.362 verified on PyPI, spaCy model tradeoffs verified from spaCy docs and Presidio docs.

---

## No New Dependencies Needed For

| Feature | Why No New Dep |
|---|---|
| **File upload** | `python-multipart` + `UploadFile` already in place. `api/files.py` handles upload, extraction, storage. Skill executor already processes `DOCUMENT_FILE:` inputs. |
| **Multipart upload to skill** | Frontend already sends file IDs. Backend `_execute_with_tools()` already fetches `UploadedFile.extracted_text` from DB. |
| **HTML rendering** | `output_renderer.py` + Jinja2 templates already handle this. Structured JSON output just changes the data source (JSON dict instead of parsed markdown sections). |
| **Frontend markdown/HTML** | `react-markdown` + `DOMPurify` already handle display. |

---

## Recommended Stack (all additions)

### pip install

```bash
# Upgrade existing
pip install "anthropic>=0.93.0"

# New: PDF generation
pip install "weasyprint>=68.0"

# New: PII redaction
pip install "presidio-analyzer>=2.2.362" "presidio-anonymizer>=2.2.362" "spacy>=3.7"
python -m spacy download en_core_web_sm
```

### pyproject.toml changes

```toml
dependencies = [
    # ... existing ...
    "anthropic>=0.93.0",          # was >=0.86.0 -- upgrade for structured outputs
    "weasyprint>=68.0",           # NEW: HTML-to-PDF export
    "presidio-analyzer>=2.2.362", # NEW: PII detection
    "presidio-anonymizer>=2.2.362", # NEW: PII anonymization
    "spacy>=3.7",                 # NEW: NLP engine for Presidio
]
```

### System dependencies (CI/Docker)

```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# After pip install
RUN python -m spacy download en_core_web_sm
```

### macOS dev setup

```bash
brew install cairo pango gdk-pixbuf libffi
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| PDF generation | WeasyPrint | xhtml2pdf | CSS 2.1 only, no flexbox/grid. Existing templates use modern CSS. |
| PDF generation | WeasyPrint | pdfkit (wkhtmltopdf) | wkhtmltopdf archived Jan 2023, no longer maintained. |
| PDF generation | WeasyPrint | reportlab | Low-level API, can't reuse HTML templates. |
| PII detection | Presidio | regex-only | Misses names, orgs, context-dependent PII. |
| PII detection | Presidio | AWS Comprehend | External API, per-request cost, data leaves infra. |
| PII detection | Presidio | Custom spaCy NER | No built-in anonymization, no pattern recognizers. |
| spaCy model | en_core_web_sm | en_core_web_lg | 50x larger (560MB vs 12MB), negligible accuracy gain for PII use case. |
| DOCX generation | python-docx | docxtpl | Template-based, less control. python-docx already installed. |
| Structured output | Anthropic native | instructor lib | Extra dependency. Anthropic SDK now has native `messages.parse()` with Pydantic. |

---

## Version Compatibility Matrix

| Package | Min Version | Python | Notes |
|---|---|---|---|
| anthropic | 0.93.0 | >=3.9 | GA structured outputs, `output_config` param |
| weasyprint | 68.0 | >=3.10 | Requires system libs (cairo, pango) |
| presidio-analyzer | 2.2.362 | >=3.10, <3.14 | Requires spaCy + model download |
| presidio-anonymizer | 2.2.362 | >=3.10, <3.14 | Companion to analyzer |
| spacy | 3.7+ | >=3.8 | NLP engine |
| python-docx | 1.2.0 | >=3.7 | Already installed |

**Project Python:** >=3.12 (per pyproject.toml). All packages compatible.

---

## Sources

- [Anthropic Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- HIGH confidence
- [WeasyPrint PyPI](https://pypi.org/project/weasyprint/) -- v68.1, HIGH confidence
- [WeasyPrint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) -- system deps, HIGH confidence
- [Presidio analyzer PyPI](https://pypi.org/project/presidio-analyzer/) -- v2.2.362, HIGH confidence
- [Presidio installation docs](https://microsoft.github.io/presidio/installation/) -- HIGH confidence
- [Presidio spaCy/Stanza docs](https://microsoft.github.io/presidio/analyzer/nlp_engines/spacy_stanza/) -- model choice, HIGH confidence
- [spaCy models page](https://spacy.io/models) -- en_core_web_sm vs lg accuracy, MEDIUM confidence
- [python-docx docs](https://python-docx.readthedocs.io/en/latest/user/quickstart.html) -- write API, HIGH confidence
- [Anthropic Python SDK PyPI](https://pypi.org/project/anthropic/) -- v0.93.0 latest, HIGH confidence
