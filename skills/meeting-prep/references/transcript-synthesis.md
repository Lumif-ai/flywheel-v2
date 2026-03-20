# Cross-Meeting Transcript Synthesis

Reference for Steps 2.5 in the main pipeline. Handles discovery, depth
determination, extraction, and synthesis of prior meeting transcripts to
produce relationship intelligence.

---

## 2.5.1 Discover Transcripts

Call the engine function to find prior meeting transcripts:
```python
from meeting_prep import discover_transcripts, determine_synthesis_depth, extract_transcript_sections
transcripts = discover_transcripts(company_name=COMPANY, person_name=PERSON)
```

If `transcripts` is empty, skip to Step 3. This is graceful degradation (context store entries only, no transcript synthesis). Print: "No prior transcripts found. Proceeding with context store intelligence only."

---

## 2.5.2 Determine Synthesis Depth

```python
# Get relationship and role from contacts.md (already loaded in Step 0)
# Parse the contact entry for this person/company from the context snapshot
relationship = "unknown"  # from contacts.md Relationship field
role = "unknown"  # from contacts.md Role field

# Check if user's original request contained an override
user_override = ""  # e.g., "deep dive on Philips" -> "deep dive on Philips"

tier = determine_synthesis_depth(
    transcript_count=len(transcripts),
    relationship=relationship,
    role=role,
    user_override=user_override,
)
```

Print the tier: "Synthesis tier: {tier} ({len(transcripts)} transcripts, {relationship} relationship)"

If tier is "none", skip to Step 3.

---

## 2.5.3 Extract and Read Transcripts

For each transcript, extract structured sections:
```python
for t in transcripts:
    sections = extract_transcript_sections(t["path"])
    # sections has: raw, metadata, key_insights, full_notes, date
```

**For quick tier:** Read only `key_insights` from each transcript. Ignore full_notes.
**For pattern tier:** Read `key_insights` + first 100 lines of `full_notes` from each.
**For deep tier:** Read all sections from each transcript. For transcripts over 300 lines, focus on key_insights + quotable moments + first/last 100 lines of full_notes.

---

## 2.5.4 Synthesize by Tier

**QUICK RECAP (tier == "quick"):**
Produce a bullet summary for each meeting:
- Date and person met
- 3-5 key takeaways from key_insights
- Topics covered
- Last interaction date

**PATTERN SYNTHESIS (tier == "pattern"):**
Everything from quick recap, PLUS:
- **Pain evolution timeline:** How their stated pain/needs changed across meetings (trace the progression)
- **Commitment tracker:** What was promised by each side, and current status (delivered/pending/dropped)
- **Recurring themes:** Topics that came up in 2+ meetings
- **Relationship arc:** How the relationship evolved (cold -> warm -> engaged, or engaged -> stalled, etc.)

**DEEP DIVE (tier == "deep"):**
Everything from pattern synthesis, PLUS:
- **Full narrative arc:** Tell the story of this relationship from first meeting to now
- **Decision-maker influence map:** Who said what across meetings, who has authority, who influences
- **Deal momentum signal:** Is this accelerating, stalling, or stuck? Evidence from meeting cadence and content
- **Objection history:** What they pushed back on, how it was resolved or persists
- **Strategic recommendation:** Based on the full arc, what should be the approach for THIS meeting

Store the synthesis output as `relationship_intelligence_html` for use in Step 8.

---

## 2.5.5 Write Relationship Summary (Compounding)

Immediately after synthesizing, write the relationship summary back to contacts.md. This is co-located with synthesis so the writeback cannot be skipped:

```python
from meeting_prep import complete_synthesis

result = complete_synthesis(
    company_name=COMPANY,
    synthesis_lines=[
        "Relationship arc summary (1-2 sentences from your synthesis above)",
        "Key themes: theme1, theme2, theme3",
        "Last discussed: topic from most recent transcript",
    ],
    transcripts=transcripts,
)
print(f"Relationship writeback: {result}")
```

This compounds: next time meeting-prep runs for this company, the relationship summary is already in contacts.md.
