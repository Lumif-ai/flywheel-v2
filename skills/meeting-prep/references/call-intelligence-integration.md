# Call Intelligence Integration

Reference for Step 2.6 in the main pipeline. Handles loading cached call
intelligence, auto-running inline extraction for deep tier, and routing
CI data into the briefing.

---

## 2.6.1 Check for Cached Call Intelligence

```python
import json, os
from datetime import datetime, timedelta

ci_dir = os.path.expanduser("~/Documents/call-intelligence")
ci_file = None
ci_stale_or_missing = True

if os.path.isdir(ci_dir):
    company_slug = COMPANY.lower().replace(" ", "-")
    candidates = sorted(
        [f for f in os.listdir(ci_dir) if f.endswith(".json") and company_slug in f],
        reverse=True
    )
    if candidates:
        path = os.path.join(ci_dir, candidates[0])
        age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
        if age < timedelta(days=7):
            with open(path) as f:
                ci_file = json.load(f)
            ci_stale_or_missing = False
            print(f"Loaded call intelligence: {candidates[0]} ({ci_file['meetings_analyzed']} meetings, {len(ci_file.get('decisions', []))} decisions)")
```

---

## 2.6.2 Auto-Run Call Intelligence (Deep Tier)

**Trigger conditions** -- run inline extraction automatically when ALL of:
1. `ci_stale_or_missing` is true (no fresh JSON cache)
2. `transcripts` is non-empty (from Step 2.5.1)
3. ANY of these is true:
   - `tier == "deep"` (from Step 2.5.2)
   - User's request contains "deep dive", "call intelligence", "decisions", "what was discussed", or "discussion log"

When triggered:
```
Print: "Running call intelligence extraction inline (deep tier, {len(transcripts)} transcripts)..."
```

Execute the full call-intelligence extraction protocol (all 8 categories from the call-intelligence skill):
1. Parse all transcripts (already loaded in Step 2.5.3)
2. Extract: Decisions, Technical Specifications, Scope Changes, Open Threads, Action Items, Data Points, Discussion Evolution, Stakeholder Map
3. Cross-meeting synthesis: Decision Timeline, Scope Evolution Map, Unresolved Items, Knowledge Gaps
4. Save JSON to `~/Documents/call-intelligence/YYYY-MM-DD-{company-slug}.json`
5. Save HTML report to `~/Documents/call-intelligence/YYYY-MM-DD-{company-slug}.html`
6. Load the JSON as `ci_file` for use in the briefing

This is the same extraction the standalone `/call-intelligence` skill performs. The output is cached, so subsequent meeting-prep runs (within 7 days) skip re-extraction.

---

## 2.6.3 Non-Deep Tier Behavior

When the trigger conditions are NOT met (quick/pattern tier with no explicit deep dive request):
- If `ci_file` was loaded from cache: use it (free intelligence)
- If no cache exists: skip gracefully. Print: "Call intelligence not available. Run /call-intelligence for granular decision/discussion data."
- Do NOT run inline extraction for quick/pattern tiers (too expensive for lighter preps)

---

## 2.6.4 Using Call Intelligence Data

**If `ci_file` is loaded** (from cache or inline extraction), use it throughout the briefing:
- Decisions feed into Section 1.9 (Call Intelligence Summary)
- Open threads inform question generation (Step 7) -- ask about unresolved items
- Technical specifications sharpen the hypothesis (Step 6)
- Action items highlight overdue commitments for follow-up questions
- Stakeholder map enriches the entity map (Step 5)
