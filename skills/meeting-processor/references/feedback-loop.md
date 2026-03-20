# Feedback & Self-Improvement Loop

The system gets better with every run through structured user feedback.

## Collecting Feedback

After every processing summary (Step 9), always ask:

> "Quick feedback on this run — anything I should fix or do differently?
> - Extraction errors (wrong category, missed insight, etc.)
> - Missing data points you wish I'd captured
> - Process suggestions (different order, more/less detail, etc.)
> - New categories or fields needed
>
> Even a quick 'looks good' helps. Your feedback trains the system."

## Recording Feedback

When the user provides feedback:

1. Add a row to the "Feedback & Changelog" sheet:
   - Date: today
   - Feedback Type: best match from dropdown
   - Details: user's feedback verbatim or summarized
   - Source: which call/run this relates to
   - Status: "Open"
   - Resolution: blank (filled when applied)

2. If feedback is about a specific call's extraction:
   - Also update that call's "Notes" column: "USER CORRECTION: [what was wrong and what's correct]"

3. If feedback suggests a structural change (new field, new category):
   - Flag clearly: "You've suggested adding [X]. Want me to update the tracker structure now?"
   - Only apply structural changes with user confirmation

## Applying Feedback (Before Each Run)

Before processing new calls, read the "Feedback & Changelog" sheet:

1. Check for "Open" items — any patterns?
2. If the same type of error has been corrected 2+ times:
   - Note it explicitly in your approach
   - Apply the correction proactively going forward
   - Example: if user corrected "audit firms should be Adjuster/Auditor not Carrier" twice,
     always use "Adjuster/Auditor" for audit firms from now on
3. If new categories were added, include them in your extraction
4. If process suggestions were made, adjust your flow accordingly

## Changelog

When changes are made based on feedback, update the Feedback sheet:
- Set Status to "Applied"
- Fill Resolution with what was changed and when

This creates a visible history of system evolution:
```
[2026-03-15] Applied:
- Added "Insurance — TPA" category (requested 2x)
- Improved severity scoring for broker calls
- Now capturing "regulatory state" field
```

## "Looks Good" Responses

If the user says "looks good" or similar positive feedback:
- Don't add a row to the Feedback sheet (no noise)
- Just acknowledge and move on
- This is a signal the system is working correctly

## Handling Disagreements

If the user disagrees with a classification but you believe your extraction was accurate:
- Apply the user's preference (they know their business better)
- Log it as feedback so the pattern is captured
- Don't push back — the founder's judgment on their own domain is authoritative
