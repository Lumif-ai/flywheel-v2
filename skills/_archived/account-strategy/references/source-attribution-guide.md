# Source Attribution Guide

Every factual claim, number, and assertion in the account strategy briefing must be attributed. No exceptions.

---

## Confidence Levels

| Level | Definition | Requirement | Inline Marker |
|-------|-----------|-------------|---------------|
| **Confirmed** | 2+ independent sources agree | Cite both sources | `[S1]` `[S2]` |
| **Single-source** | One credible source | Cite the source, note it's single-source | `[S3]` |
| **Inferred** | Deduced from indirect evidence | State reasoning chain + confidence % | `[I1]` |
| **From meetings** | Said by a named person in a meeting | Attribute: "Person Name, Date" | `[M1]` |
| **Unknown** | No data found despite research | Explicitly list in "What We Don't Know" | -- |

---

## Inline Marker Format

Place markers as superscript immediately after the claim:

```
Revenue estimated at $2.3B [S3]
"I don't think it can get any more manual" [M1]
Likely using SAP based on job postings [I1]
```

Markers are clickable links to the Sources appendix in the HTML output.

---

## Source Appendix Entry Formats

### Direct sources `[S]`
```
[S1] https://company.com/about — Company website, accessed 2026-03-17
[S2] context-store: competitive-intel.md (2026-03-10, evidence: 3) — Prior research
[S3] https://finance.yahoo.com/quote/RMR — Public financials, accessed 2026-03-17
```

### Inferred `[I]`
```
[I1] Inferred: SAP ERP likely in use
     Evidence: 3 job postings on careers page mention SAP (2 SAP FICO, 1 SAP BW)
     Confidence: 65% — could be legacy system being phased out
     Alternative: Oracle ERP also mentioned in 1 posting
```

### Meeting-sourced `[M]`
```
[M1] David Daido, VP Operations, March 12 2026
     Context: Describing current COI tracking workflow
     Transcript: ~/Projects/lumifai/transcripts/2026-03-12-david-daido-rmr.md
```

---

## Rules

1. **Every number must have a source.** Revenue, employee count, pricing, market size -- all sourced.
2. **Competitor pricing must link to the pricing page or source.** Not "competitors charge $X" without a URL.
3. **Inferred figures must explain the reasoning.** "We estimate 5,000 COIs based on..." not just "$5,000 COIs."
4. **Meeting quotes must name the person and date.** Not "the prospect said" but "David Daido, March 12."
5. **Context store entries count as sources.** Cite as `context-store: {filename} ({date})`.
6. **When sources conflict, show both.** "Website says 500 employees [S1], LinkedIn says 450 [S2]."
7. **Never present inferred data as confirmed.** Always mark with `[I]` and include reasoning.
8. **Source freshness matters.** Note access date. Flag data older than 6 months.

---

## Examples: Good vs Bad

**Bad:** "RMR manages $41B in assets"
**Good:** "RMR manages $41.3B in gross real estate assets [S1]"

**Bad:** "They probably use Yardi"
**Good:** "Uses Yardi Voyager for property management [M1], confirmed on company careers page [S2]"

**Bad:** "The market for COI tracking is $500M"
**Good:** "COI tracking market estimated at $500M [I1]" with appendix: "Inferred from: 3 competitor revenue disclosures totaling ~$120M at estimated 24% market share"
