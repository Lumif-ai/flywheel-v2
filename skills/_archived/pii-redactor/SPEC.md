# PII Redactor Skill — Specification

## Overview

A standalone Claude Code skill that detects and removes Personally Identifiable Information (PII) from documents using Microsoft Presidio, running entirely locally with no cloud dependencies.

---

## Core Workflow

```
User provides document (PDF, DOCX, URL, pasted text)
        ↓
Install dependencies (one-time: presidio-analyzer, presidio-anonymizer, spaCy model)
        ↓
Extract text from document
        ↓
Run Presidio Analyzer → detect all PII entities with confidence scores
        ↓
Present PII Summary to user:
  - Count by entity type (e.g., 4 PERSON, 2 EMAIL_ADDRESS, 1 PHONE_NUMBER)
  - Sample matches (first 2-3 per type) so user can verify detection quality
  - Confidence threshold used (default: 0.7)
        ↓
User confirms or adjusts (e.g., "skip company names", "lower threshold")
        ↓
Run Presidio Anonymizer → produce redacted text
        ↓
Output:
  1. Redacted document (same format as input where possible, otherwise .txt/.md)
  2. PII Audit Log (.md) — what was found, what was redacted, confidence scores
```

---

## Default Redaction Style

**Type-tag replacement** (configurable per-run):

| Original | Redacted |
|---|---|
| John Smith | `<PERSON_1>` |
| john@acme.com | `<EMAIL_ADDRESS_1>` |
| 555-123-4567 | `<PHONE_NUMBER_1>` |
| 123 Main St, SF | `<LOCATION_1>` |
| 123-45-6789 | `<US_SSN_1>` |

Numbered tags (`_1`, `_2`) so the same entity gets the same tag throughout the document (consistency for downstream analysis).

---

## Supported PII Entity Types

### Default (always on)
- PERSON (names)
- EMAIL_ADDRESS
- PHONE_NUMBER
- US_SSN
- CREDIT_CARD
- IBAN_CODE
- US_PASSPORT
- US_DRIVER_LICENSE

### Optional (user can enable)
- LOCATION / ADDRESS
- DATE_TIME (risky — may over-redact contract dates)
- ORGANIZATION (risky — may redact party names needed for context)
- IP_ADDRESS
- URL
- MEDICAL_LICENSE
- US_BANK_NUMBER
- CRYPTO (bitcoin wallets)

### Custom recognizers
- Support adding regex-based custom recognizers via the skill (e.g., internal employee IDs, project codes)

---

## Dependencies

All installed locally, no cloud calls:

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg  # NER model (~560MB, one-time)
```

**Alternative lighter model:** `en_core_web_sm` (~12MB) for faster setup but lower accuracy. Skill should default to `en_core_web_lg` but fall back to `sm` if user wants speed.

---

## File Structure

```
pii-redactor/
├── SKILL.md                    # Main skill instructions
├── README.md                   # User-facing documentation
├── references/
│   └── entity-types.md         # Full entity type reference & customization guide
└── scripts/
    └── redact.py               # Presidio wrapper — handles detection + anonymization
```

---

## scripts/redact.py — Design

Single Python script that handles the full pipeline:

```
Usage:
  python redact.py <input_file> [options]

Options:
  --threshold FLOAT       Confidence threshold (default: 0.7)
  --output PATH           Output file path (default: <input>_redacted.<ext>)
  --audit PATH            Audit log path (default: <input>_pii_audit.md)
  --entities TYPES        Comma-separated entity types to detect (default: all default types)
  --exclude-entities TYPES  Entity types to skip
  --mode MODE             replace|mask|hash|redact (default: replace)
  --spacy-model MODEL     en_core_web_lg or en_core_web_sm (default: lg)
  --dry-run               Show what would be redacted without modifying anything
  --json                  Output detection results as JSON (for programmatic use)
```

**Key behaviors:**
- Auto-installs dependencies if missing (with user confirmation)
- Handles PDF text extraction (via pdfplumber or PyPDF2)
- Handles DOCX extraction (via python-docx)
- Plain text passthrough
- Consistent entity numbering across the document (same "John Smith" → `<PERSON_1>` everywhere)
- Outputs both the redacted document and an audit log

---

## SKILL.md — Outline

### Trigger
- `/pii-redactor`
- "Remove PII from this document"
- "Redact personal information"
- "Anonymize this file"
- "Strip sensitive data"

### Step 0: Intake
- Request document if not provided
- Ask: "Should I use default PII types, or do you want to customize what gets redacted?"

### Step 1: Setup
- Check if presidio + spaCy model are installed
- Install if needed (with user confirmation for the ~560MB spaCy model download)

### Step 2: Extract & Analyze
- Extract text from document
- Run Presidio Analyzer
- Present summary table of findings

### Step 3: User Confirmation
- Show what will be redacted (dry-run summary)
- User confirms or adjusts settings

### Step 4: Redact & Output
- Run Presidio Anonymizer
- Save redacted document
- Save PII audit log
- Present both files

---

## PII Audit Log Format

```markdown
# PII Audit Log
**Source:** contract_draft.pdf
**Date:** 2026-03-04
**Threshold:** 0.7
**Model:** en_core_web_lg

## Summary
| Entity Type | Count | Action |
|---|---|---|
| PERSON | 4 | Replaced with <PERSON_N> |
| EMAIL_ADDRESS | 2 | Replaced with <EMAIL_ADDRESS_N> |
| PHONE_NUMBER | 1 | Replaced with <PHONE_NUMBER_N> |

## Detailed Findings
| # | Entity Type | Original | Replacement | Confidence | Location |
|---|---|---|---|---|---|
| 1 | PERSON | John Smith | <PERSON_1> | 0.95 | Line 3 |
| 2 | PERSON | Jane Doe | <PERSON_2> | 0.92 | Line 7 |
| ... | ... | ... | ... | ... | ... |

## Settings Used
- Mode: replace
- Entities detected: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN
- Entities excluded: ORGANIZATION, DATE_TIME
```

---

## Integration with legal-doc-advisor (future)

Not built now, but designed for easy integration later:

```
# In legal-doc-advisor SKILL.md, add optional Step 0.5:
# "Would you like me to redact PII before analysis? (uses /pii-redactor)"
# If yes → run pii-redactor → feed redacted output into legal review pipeline
```

The legal-doc-advisor would pass the redacted text to its analysis steps, and the PII audit log would be appended to the legal review output.

---

## Open Questions

1. **Should the redacted document preserve original formatting (PDF→PDF, DOCX→DOCX)?**
   - Recommendation: Start with text output only (`.txt` or `.md`). PDF/DOCX preservation adds significant complexity (manipulating PDF objects, DOCX XML). Can add later.

2. **Multi-language support?**
   - Presidio supports multiple languages via different spaCy models. Start with English only, document how to add others.

3. **Should there be a "reverse map" file?**
   - A mapping file (`<PERSON_1>` → `John Smith`) saved separately, so the original can be reconstructed if needed. Useful but creates a security artifact. Recommendation: off by default, opt-in flag `--save-mapping`.

---

## Next Steps

1. Review this spec
2. Build `scripts/redact.py`
3. Write `SKILL.md` with full instructions
4. Write `references/entity-types.md`
5. Write `README.md`
6. Test with a sample document
