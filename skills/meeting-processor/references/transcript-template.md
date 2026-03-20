# Transcript Template Reference

## Folder Structure
```
lumifai/transcripts/
├── _interview-index.md
├── 2026-03-03-john-smith-abc-insurance.md
├── 2026-03-05-jane-doe-buildcorp.md
└── ...
```

## File Naming
`YYYY-MM-DD-firstname-lastname-company.md` (all lowercase, hyphens, no spaces)

Dedup: if file already exists, skip creation.

## Individual Interview Template

```markdown
# Interview: [Person Name] — [Company]

## Metadata
| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Person | [Name], [Title] |
| Company | [Company] ([Category]) |
| Company Size | [if known] |
| Decision Maker | Buyer / Influencer / End User / Expert |
| Meeting Source | [how this call happened] |
| Product Relevance | P1 / P2 / P3 |
| Severity | X/5 |
| Painkiller/Vitamin | [classification] |
| Confidence | High / Medium / Low |
| Previous Calls | [link to prior transcript, or "First call"] |

## Key Insights (TL;DR)
- [Top 3-5 bullet points — the gold]

## Hair on Fire Problem
[Detailed description in their words]

## Quotable Moments
[Exact phrases useful for pitch decks, investor conversations]

## Full Transcript / Notes
[Complete unedited content as provided by Granola or user.
 Raw source — do not summarize or edit. Preserve exactly as received.]
```

Structured analysis (workflow, buying signals, objections, etc.) lives in the tracker,
not duplicated here. The transcript doc is for raw preservation + quick highlights.

## Master Index (`_interview-index.md`)

```markdown
# Lumif.ai — Interview Archive Index

| # | Date | Person | Company | Category | Severity | P/V | Product | Warm | File |
|---|------|--------|---------|----------|:--------:|:---:|---------|:----:|------|
```

Sort newest first. Update on every processing run.

## Export Options

Transcripts can be exported to PDF, Google Docs, or other formats on demand.
Source of truth is always the local markdown files.
