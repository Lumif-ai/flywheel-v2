# pii-redactor

A Claude Code skill that detects and removes Personally Identifiable Information (PII) from documents using Microsoft Presidio — running entirely locally with no cloud dependencies.

## What it does
- Detects PII in PDF, DOCX, and text files using NER + regex + rule-based logic
- Shows you exactly what was found before redacting (dry-run first, always)
- Replaces PII with consistent numbered type tags: `John Smith` → `<PERSON_1>`
- Produces a full PII audit log with confidence scores
- Optionally saves a reverse mapping file for reconstruction
- Runs 100% locally via spaCy — no data leaves your machine

## Supported PII types (default)
- Names (PERSON)
- Email addresses
- Phone numbers
- US Social Security Numbers
- Credit card numbers
- IBAN codes
- US passport numbers
- US driver's license numbers

Optional: locations, dates, organizations, IP addresses, URLs, crypto wallets, and more.

## Installation
```bash
mkdir -p ~/.claude/skills
cp -r pii-redactor ~/.claude/skills/
```

First run will auto-install: `presidio-analyzer`, `presidio-anonymizer`, and spaCy's `en_core_web_lg` model (~560MB one-time download).

## Usage

### Direct invocation
```
/pii-redactor
```

### Natural language triggers
- "Remove PII from this document"
- "Redact personal information"
- "Anonymize this file"
- "Strip sensitive data"

### CLI (standalone script)
```bash
# Dry run — see what would be redacted
python3 scripts/redact.py document.pdf --dry-run

# Full redaction with reverse mapping
python3 scripts/redact.py document.pdf --save-mapping

# Custom: only names and emails, higher threshold
python3 scripts/redact.py document.pdf --entities PERSON,EMAIL_ADDRESS --threshold 0.85

# Mask mode instead of type tags
python3 scripts/redact.py document.pdf --mode mask
```

## Output
Every run produces:
- **`[name]_redacted.md`** — Redacted document with PII replaced
- **`[name]_pii_audit.md`** — Full audit log: what was found, confidence, line numbers
- **`[name]_mapping.json`** (opt-in) — Reverse map to reconstruct original

## Redaction modes
| Mode | Example | Use case |
|---|---|---|
| `replace` (default) | `<PERSON_1>` | Sharing, analysis, legal review |
| `mask` | `J********h` | Light anonymization |
| `hash` | `[a1b2c3d4e5f6]` | Data processing pipelines |
| `redact` | `[REDACTED]` | Maximum privacy |

## Requirements
- Python 3.9+
- Claude Code
- ~600MB disk for spaCy model (first run only)
