# Extraction Schema Reference

Field definitions and extraction weights per meeting type for ctx-meeting-processor.

## Meeting Type Weights

Each meeting type has primary and secondary write targets. Primary targets should receive thorough extraction; secondary targets capture incidental mentions.

### Discovery Call

**Primary:** pain-points.md, icp-profiles.md, contacts.md, competitive-intel.md
**Secondary:** insights.md, action-items.md, product-feedback.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Pain points | pain-points.md | Problems described, severity ("spend 15-20 hrs/week"), current workarounds, impact quantification |
| ICP signals | icp-profiles.md | Company size, segment, decision-maker title, budget signals, buying timeline |
| Contacts | contacts.md | All attendees: name, role, company, email/phone if mentioned |
| Competitors | competitive-intel.md | Tools currently used, competitors mentioned, pricing references, switching triggers |
| Action items | action-items.md | Follow-ups committed to, demo scheduling, document requests |
| Sentiment | insights.md | Overall call outcome, engagement level, next steps probability |

### Expert/Industry Interview

**Primary:** pain-points.md, competitive-intel.md, insights.md
**Secondary:** contacts.md, icp-profiles.md, action-items.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Industry pain | pain-points.md | Market-level problems, industry trends, structural challenges |
| Competitive landscape | competitive-intel.md | Tool comparisons, market positioning, feature gaps |
| Strategic insights | insights.md | Cross-cutting observations, market dynamics, timing signals |
| Expert contact | contacts.md | Expert name, affiliation, domain expertise |

### Advisor Session

**Primary:** insights.md, action-items.md
**Secondary:** competitive-intel.md, contacts.md, product-feedback.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Strategic advice | insights.md | Recommendations, strategic pivots, priority shifts |
| Action items | action-items.md | Commitments made, introductions promised, deadlines |
| Market intel | competitive-intel.md | Competitive insights shared by advisor |
| Product direction | product-feedback.md | Product suggestions, feature prioritization advice |

### Investor Pitch

**Primary:** insights.md, action-items.md, product-feedback.md
**Secondary:** contacts.md, competitive-intel.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Investor feedback | insights.md | Investment thesis alignment, concerns raised, interest level |
| Follow-ups | action-items.md | Materials requested, next meeting, due diligence items |
| Product questions | product-feedback.md | Product-specific questions, feature interest, scalability concerns |
| Investor contact | contacts.md | Investor name, firm, partner status, check size |

### Internal/Standup

**Primary:** action-items.md, insights.md
**Secondary:** product-feedback.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Action items | action-items.md | Tasks assigned, blockers, deadlines, owners |
| Team insights | insights.md | Key decisions made, strategic shifts, team sentiment |
| Product ideas | product-feedback.md | Internal feature requests, technical debt flagged |

### Customer Feedback

**Primary:** product-feedback.md, pain-points.md, contacts.md
**Secondary:** insights.md, action-items.md, competitive-intel.md

| Field | Target File | What to Extract |
|-------|------------|----------------|
| Feature requests | product-feedback.md | Specific feature asks, UX feedback, demo reactions |
| Pain points | pain-points.md | Problems with current solution, unmet needs |
| Contact info | contacts.md | Customer name, role, company, account status |
| Competitive mentions | competitive-intel.md | Alternative tools mentioned, switching considerations |
| Follow-ups | action-items.md | Bug reports to file, features to scope, follow-up calls |

### Team Meeting

**Primary:** action-items.md, insights.md
**Secondary:** product-feedback.md

Same as Internal/Standup but typically longer-form with broader strategic context.

---

## Content Line Format

All content lines should follow speaker-attributed format when speaker is known:

```
Speaker-Role: insight or data point
```

**Speaker roles:**
- `Prospect:` -- External person being sold to
- `Customer:` -- Existing customer providing feedback
- `Expert:` -- Domain expert or industry interviewee
- `Advisor:` -- Board member, mentor, advisor
- `Investor:` -- VC, angel, or fund representative
- `Team:` -- Internal team member
- `CEO:` / `CTO:` / `CoS:` -- Specific team roles when relevant

**Examples:**
```
Prospect: frustrated with manual rule config -- spending 15-20 hrs/week
Team: committed to sending demo environment by Friday
Advisor: recommended focusing on GC segment before expanding to brokers
Investor: interested in construction vertical traction metrics
```

When speaker is unknown, omit the prefix -- just write the content directly.

## Size Guidance

- Keep entries under **15-20 content lines** per context file per meeting
- Total entry size must stay under **4000 characters** (headroom below 5000 MAX_ENTRY_SIZE)
- If a meeting has extensive content for one file, prioritize the most actionable/specific items
- Use concise, information-dense lines -- avoid filler words
