# Confidential Legal Review

Privacy-first legal document review. Redacts all PII locally (Presidio + spaCy), then runs a full founder-first legal analysis on the anonymized text. No confidential information ever leaves your machine.

## How It Works

1. **PII Redaction (local):** Presidio detects names, emails, company names, etc. and replaces them with tags (`<PERSON_1>`, `<ORGANIZATION_1>`)
2. **Legal Review (on redacted text):** Full 8-section founder-first analysis -- Claude only sees the tagged version
3. **Entity Reference Table:** Appended locally from the mapping file so you can map tags back to real entities

## Prerequisites

- `pii-redactor` skill installed at `~/.claude/skills/pii-redactor/`
- `legal-doc-advisor` skill installed at `~/.claude/skills/legal-doc-advisor/`
- Python 3 with pip access (for Presidio + spaCy installation on first run)

## Usage

```
/confidential-legal-review
```

Or say: "review this document confidentially", "redact and review", "secure legal review"

## Output Files

| File | Description |
|------|-------------|
| `confidential_legal_review_[name].md` | Full legal analysis with entity reference table |
| `confidential_legal_review_[name].html` | Polished HTML report |
| `[name]_pii_audit.md` | What PII was detected and redacted |
| `[name]_mapping.json` | Tag-to-original mapping (keep secure or delete) |

## Privacy Guarantee

- PII redaction runs entirely locally (Presidio + spaCy, zero network calls)
- Only the redacted text (with `<PERSON_1>` style tags) is sent for legal analysis
- The mapping file stays on your local disk
- Caveat: Presidio is highly accurate but not 100%. The dry-run step lets you catch gaps.

---

*Confidential Legal Review v1.0*
