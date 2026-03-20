# Enriched Output Template

Template for the standalone enriched output produced by ctx-meeting-processor.
This output replaces legacy meeting summaries with flywheel-enriched reports.

---

## Template Structure

```markdown
# Meeting Intelligence Report

**Date:** {YYYY-MM-DD}
**Type:** {meeting_type}
**Attendees:** {comma-separated names}
**Sentiment:** {positive/neutral/negative/mixed}

## Summary

{2-3 sentence overview of the meeting, key outcome, and next steps}

## Key Insights Extracted

### Pain Points
- {Speaker}: {pain point with severity/impact}

### Competitive Intelligence
- {Speaker}: {competitor mention, tool comparison, pricing}

### ICP Signals
- {company profile signals, segment fit, buying indicators}

### Contacts
- {Name, Role, Company, contact info if available}

### Product Feedback
- {Speaker}: {feature request, product reaction, demo feedback}

### Strategic Insights
- {cross-cutting observation, market dynamic, strategic takeaway}

## Context Store Cross-References

*The following connections were found by cross-referencing this meeting's
data against the compounded context store:*

- **Returning Contact:** {Name} -- appeared in {N} previous entries. {details}
- **Known Company:** {Company} -- referenced in {N} previous entries. {details}
- **Recurring Pain Point:** "{pain point}" -- {N} evidence count across context store. {details}
- **Tracked Competitor:** {Competitor} -- previously recorded in context store. {details}

## Action Items

- [ ] {Owner}: {action item with due date if specified}
- [ ] {Owner}: {action item}

## Context Store Writes

| File | Result |
|------|--------|
| {filename} | {OK/DEDUP/ERROR} |

## What the Flywheel Added

This report includes **{N} cross-references** from the compounded context store
that would not appear in a standalone meeting summary. Each processed meeting
makes future reports smarter.

---
*Processed by ctx-meeting-processor v1.0 at {timestamp}*
```

---

## Key Section: Cross-References

The **Context Store Cross-References** section is the primary value proof.
It must be visually prominent and clearly demonstrate that compounded data
makes this output smarter than a standalone meeting summary.

**Cross-reference types:**

| Type | What It Proves |
|------|---------------|
| Returning Contact | This person has been seen before -- continuity tracking |
| Known Company | This company has prior context -- relationship depth |
| Recurring Pain Point | This problem keeps coming up -- market signal strength |
| Tracked Competitor | This competitor is already in our intelligence -- competitive awareness |

**When no cross-references exist:** Show a message explaining this is an early run
and future meetings will benefit from today's data. Never leave the section empty.

## Comparison: Legacy vs Flywheel

| Aspect | Legacy Output | Flywheel Output |
|--------|--------------|-----------------|
| Data destination | Excel tracker, JSON, HTML | Context store (7 files) |
| Cross-references | None | Automatic from compounded data |
| Entity tracking | Per-meeting only | Across all meetings |
| Evidence counting | Manual | Automatic via dedup |
| Format | Spreadsheet rows | Markdown entries with attribution |
| Reusability | Read by humans | Read by all skills |
