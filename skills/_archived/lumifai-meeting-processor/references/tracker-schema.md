# Tracker Schema Reference

Full specification for the Lumif.ai Expert Insights Tracker.

## Sheet 1: "Expert Calls" (33 columns)

| Col | Field | Validation / Formatting |
|-----|-------|------------------------|
| A | Date | YYYY-MM-DD |
| B | Person Name | — |
| C | Title/Role | — |
| D | Email | — |
| E | Phone | — |
| F | Company | — |
| G | Company URL | — |
| H | LinkedIn | — |
| I | Meeting Type | Dropdown: Expert, Advisor. Expert=default, Advisor=blue(#BDD7EE). Determines which fields are populated (advisor calls skip pain/ICP/WTP fields). |
| J | Category | Dropdown: Insurance (Carrier, Broker/Agent, MGA/MGU, Adjuster/Auditor, Wholesaler), Construction (GC, Sub, Owner/Developer, Safety/Risk Manager), Real Estate (Developer, Property Manager, Investor), Energy, Infrastructure, Advisor/Consultant, Technology/SaaS, Investor/VC, Other |
| K | Sub-category | Free text |
| L | Company Size | Free text (e.g., "~200 employees", "$50M revenue") |
| M | Decision Maker Type | Dropdown: Buyer, Influencer, End User, Expert (no buying power), Advisor |
| N | Meeting Source | Dropdown: Warm Intro, Cold Outreach, Conference, LinkedIn, Referral, Advisor Network, Other |
| O | Meeting Summary | Wrap text, 42 width |
| P | Key Insights | Wrap text, 45 width |
| Q | Hair on Fire Problem | Wrap text, 45 width. For Advisor type: leave blank ("—") |
| R | Vitamin vs Painkiller | Dropdown: Painkiller, Vitamin, Unclear. Painkiller=orange(#F4B084), Vitamin=yellow(#FFF2CC). For Advisor type: leave blank ("—") |
| S | Problem Severity (1-5) | Dropdown: 1-5. 5=red(#FF6B6B), 4=orange(#FCE4D6). For Advisor type: leave blank ("—") |
| T | ICP Signals | Wrap text. For Advisor type: leave blank ("—") |
| U | New ICP Identified | Wrap text. For Advisor type: leave blank ("—") |
| V | Willingness to Pay | Wrap text. For Advisor type: leave blank ("—") |
| W | Current Spend / Tools | Wrap text |
| X | Competitors Mentioned | Free text |
| Y | Action Items | Wrap text |
| Z | Research Needed | Wrap text |
| AA | Product Relevance | Dropdown: P1 (WC Audit), P2 (GC Compliance), P3 (Broker), P1+P2, P1+P3, P2+P3, All, General |
| AB | Sentiment | Dropdown: Positive, Neutral, Skeptical, Negative |
| AC | Warm Lead | Dropdown: Yes, Maybe, No. Yes=green(#C6EFCE). For Advisor type: leave blank ("—") |
| AD | Follow-up Date | Date |
| AE | Referrals | Wrap text |
| AF | Confidence Score | Dropdown: High, Medium, Low. Low=red(#FFC7CE) |
| AG | Notes | Wrap text |

### Advisor-Specific Fields (stored in Notes column AG for advisor rows)

For `Advisor` meeting type rows, the Notes column (AG) should contain a structured block:
```
Advisory Focus: [domain/topic]
Strategic Advice: [key recommendations]
Introductions Made: [who they connected the team with]
Market Intel: [industry knowledge shared]
Advisor Engagement: Active/Occasional/One-time
Follow-up Cadence: [how often]
```

## Sheet 2: "Action Items"

Cols: Date Added | Source Call (Person — Company) | Action Item | Owner | Due Date | Status (Open/In Progress/Done/Cancelled) | Notes
Formatting: Open=orange, Done=green.

## Sheet 3: "Research Queue"

Cols: Date Flagged | Topic | Why It Matters | Source Call | Priority (High/Med/Low) | Status (Queued/In Progress/Done) | Findings | Product Relevance

## Sheet 4: "ICP Tracker" (tab color: #E2725B)

Cols: Date First Identified | ICP Segment | Description | # Calls Validating | Key Characteristics | Est. Market Size | Avg Pain (1-5) | Painkiller or Vitamin (Painkiller/Vitamin/Mixed/Unclear) | Which Product | Status (Hypothesis/Partially Validated/Validated/Invalidated) | Notes
Formatting: Validated=green, Invalidated=red.
Pre-populate: Mid-size GCs (P2), Regional Construction Brokers (P3), WC Carriers (P1), Premium Audit Firms (P1).

## Sheet 5: "Competitors" (tab color: #4472C4)

Cols: Competitor Name | Category (Direct/Indirect/Adjacent/Incumbent Process) | Times Mentioned | Who Mentioned | What They Do | Strengths | Weaknesses | Pricing | Competes With (P1/P2/P3/Multiple) | Our Differentiation | Last Updated
When mentioned again: increment count, append to "Who Mentioned" — never duplicate rows.
Pre-populate: myCOI, TrustLayer, Jones, BCS (Bickmore), Spreadsheets/Email.

## Sheet 6: "Feedback & Changelog" (tab color: #70AD47)

Cols: Date | Feedback Type (Extraction Error/Missing Field/Process Suggestion/New Category/Other) | Details | Source | Status (Open/Applied/Won't Fix) | Resolution
Formatting: Open=orange, Applied=green.

## Sheet 7: "Dashboard" (tab color: #1F3864)

Key Metrics formulas:
- Total Calls: `=COUNTA('Expert Calls'!A:A)-1`
- Expert Calls: `=COUNTIF('Expert Calls'!I:I,"Expert")`
- Advisor Calls: `=COUNTIF('Expert Calls'!I:I,"Advisor")`
- Warm Leads: `=COUNTIF('Expert Calls'!AC:AC,"Yes")`
- Painkillers: `=COUNTIF('Expert Calls'!R:R,"Painkiller")`
- Avg Severity: `=IFERROR(AVERAGE('Expert Calls'!S2:S500),"—")`
- Open Actions: `=COUNTIF('Action Items'!F:F,"Open")`
- Research Queued: `=COUNTIF('Research Queue'!F:F,"Queued")`
- ICPs: `=COUNTA('ICP Tracker'!A:A)-1`
- Competitors: `=COUNTA(Competitors!A:A)-1`
- Admin Entries: `=COUNTA('Admin Log'!A:A)-1`
- Open Feedback: `=COUNTIF('Feedback & Changelog'!E:E,"Open")`

Breakdowns: By Meeting Type (col I), By Category (col J), By Product (col AA), Pain Analysis (col R), Sentiment (col AB), Confidence (col AF), Meeting Source (col N).

## Sheet 8: "Admin Log" (tab color: #A9A9A9)

For administrative/operational calls (lawyers, accountants, ops vendors, tooling demos).

Cols: Date | Contact Name | Title/Role | Company | Purpose | Key Outcomes | Action Items | Owner | Next Steps | Status (Open/Done) | Notes
Formatting: Open=orange, Done=green.

This sheet is intentionally lightweight — no deep insight extraction.

## Sheet 9: "Customer Calls" (tab color: #2E86AB)

For calls with active customers, pilots, and engaged partners about ongoing work,
product usage, feature requests, project delivery, or partnership execution.

Cols: Date | Person Name | Title/Role | Email | Company | Account Name | Product(s) in Use |
Meeting Type (always "Customer") | Account Health (Green/Yellow/Red) | Satisfaction Indicators |
Concerns / Blockers | Escalations | Feature Requests | Product Feedback | Usage Patterns |
Integration Needs | Deliverables Discussed | Milestones / Timeline | Decisions Made |
Blockers for Lumif | Expansion Signals | Competitive Mentions | Referral Potential |
Contract / Commercial | Action Items (Lumif) | Action Items (Customer) | Next Meeting | Notes

Formatting: Health Green=#C6EFCE, Yellow=#FFF2CC, Red=#FFC7CE.

Dedup: Same as Expert Calls — (Person Name + Company + Date).

## Formatting Standards

- Header: Bold, white(#FFFFFF), dark blue fill(#1F3864), center, wrap
- Freeze panes row 1, auto-filter on all sheets
- Font: Arial 10 (data), Arial 11 (dashboard)
- Use openpyxl for creation. Run `scripts/recalc.py` after adding formulas.

## Deduplication

Before adding any row:
1. Build set of (Person Name, Company, Date) from existing rows
2. Exact match all 3 → SKIP (already processed)
3. Person+Company match, different Date → ADD (follow-up call)
4. Person matches, different Company → ADD (note it)

Always report: `Skipped: X | Added: X | Updated: X`
