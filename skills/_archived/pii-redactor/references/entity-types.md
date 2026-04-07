# PII Entity Types Reference

## Default Entities (Always On)

These are detected by default unless explicitly excluded.

| Entity Type | Description | Examples |
|---|---|---|
| `PERSON` | Full names detected via NER | John Smith, Dr. Jane Doe, Mr. Johnson |
| `EMAIL_ADDRESS` | Email addresses | john@example.com, support@acme.co.uk |
| `PHONE_NUMBER` | Phone numbers (US format primarily) | (555) 123-4567, +1-555-123-4567, 555.123.4567 |
| `US_SSN` | US Social Security Numbers | 123-45-6789, 123 45 6789 |
| `CREDIT_CARD` | Credit/debit card numbers | 4111 1111 1111 1111, 5500-0000-0000-0004 |
| `IBAN_CODE` | International Bank Account Numbers | GB29 NWBK 6016 1331 9268 19 |
| `US_PASSPORT` | US passport numbers | 123456789 (9-digit format in context) |
| `US_DRIVER_LICENSE` | US driver's license numbers | Varies by state; detected contextually |

## Optional Entities

These are NOT detected by default. Enable with `--entities` flag or by telling the skill to include them.

| Entity Type | Description | Why Optional | Examples |
|---|---|---|---|
| `LOCATION` | Addresses, cities, countries | May over-redact geographic references needed for context | 123 Main St, San Francisco, CA 94105 |
| `DATE_TIME` | Dates and times | Will redact contract dates, deadlines — often harmful to document meaning | January 15, 2026; 3:00 PM EST |
| `ORGANIZATION` | Company and organization names | Often needed for document context (party names in contracts) | Acme Corp, Google LLC, Stanford University |
| `IP_ADDRESS` | IPv4 and IPv6 addresses | Primarily relevant for technical/log documents | 192.168.1.1, 2001:0db8:85a3::8a2e:0370:7334 |
| `URL` | Web addresses | May over-redact references needed for context | https://example.com/path |
| `MEDICAL_LICENSE` | Medical license numbers | Domain-specific; only relevant for healthcare documents | |
| `US_BANK_NUMBER` | US bank account/routing numbers | Less common in general documents | 021000021 (routing), account numbers in context |
| `CRYPTO` | Cryptocurrency wallet addresses | Domain-specific | 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa |

## Customization Examples

### Detect everything
```bash
python3 redact.py doc.pdf --entities PERSON,EMAIL_ADDRESS,PHONE_NUMBER,US_SSN,CREDIT_CARD,IBAN_CODE,US_PASSPORT,US_DRIVER_LICENSE,LOCATION,DATE_TIME,ORGANIZATION,IP_ADDRESS,URL,CRYPTO
```

### Detect only names and contact info
```bash
python3 redact.py doc.pdf --entities PERSON,EMAIL_ADDRESS,PHONE_NUMBER
```

### Default types but skip names (keep names visible)
```bash
python3 redact.py doc.pdf --exclude-entities PERSON
```

### For a legal contract (keep org names and dates)
```bash
python3 redact.py contract.pdf --exclude-entities ORGANIZATION,DATE_TIME
```

### For a healthcare document (add medical entities)
```bash
python3 redact.py report.pdf --entities PERSON,EMAIL_ADDRESS,PHONE_NUMBER,US_SSN,MEDICAL_LICENSE,LOCATION,DATE_TIME
```

## Confidence Scores

Each detection includes a confidence score (0.0 to 1.0):

| Score Range | Meaning |
|---|---|
| 0.95–1.0 | Very high confidence — regex match or strong NER signal |
| 0.85–0.95 | High confidence — likely PII |
| 0.70–0.85 | Moderate confidence — probable PII but could be false positive |
| 0.50–0.70 | Low confidence — might be PII, review recommended |
| Below 0.50 | Not detected at default threshold |

### Threshold Recommendations by Use Case

| Use Case | Threshold | Rationale |
|---|---|---|
| Sharing externally | 0.5 | Better to over-redact than leak |
| Internal review | 0.7 | Balanced |
| Legal document prep | 0.7 + exclude ORGANIZATION,DATE_TIME | Keep party names and dates |
| Code/technical docs | 0.85 | Avoid false positives on variable names |
| Quick scan | 0.85 | Fast check, high confidence only |

## Adding Custom Recognizers

Presidio supports custom recognizers for domain-specific PII. To add one, modify `redact.py` and register a new `PatternRecognizer`:

```python
from presidio_analyzer import PatternRecognizer, Pattern

# Example: detect internal employee IDs (format: EMP-XXXXX)
emp_id_pattern = Pattern(
    name="employee_id",
    regex=r"EMP-\d{5}",
    score=0.9,
)
emp_recognizer = PatternRecognizer(
    supported_entity="EMPLOYEE_ID",
    patterns=[emp_id_pattern],
)
analyzer.registry.add_recognizer(emp_recognizer)
```

This is an advanced feature — most users won't need it. But it's available for organizations with proprietary ID formats, internal codes, or industry-specific identifiers.

---

*Reference for PII Redactor Skill v1.0*
