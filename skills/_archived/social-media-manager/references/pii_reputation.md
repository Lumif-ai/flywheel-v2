# PII Guard & Reputation Layer

## PII Scrubbing Rules

Every draft must pass PII screening before being shown to the user.

### Entity Types to Catch

| Entity | Replace With | Example |
|--------|-------------|---------|
| Customer company name | "a mid-size GC in Texas" / "a customer" | "Buildcore Inc" → "a GC we work with" |
| Person name (external) | Role descriptor | "John Smith" → "their VP of Safety" |
| Person name (internal team) | "our team" / "my cofounder" | Unless user explicitly approves |
| Revenue/ARR figures | Range or vague | "$127K MRR" → "six-figure MRR" |
| Specific headcount | Range | "23 employees" → "~20 people" |
| Email addresses | Remove entirely | Never include in posts |
| Phone numbers | Remove entirely | Never include in posts |
| Internal tool/system names | Generic descriptor | "our Jira board" → "our project tracker" |
| Contract values | Range | "$450K deal" → "mid-six-figure deal" |

### Blocklist

User maintains a blocklist at `~/.claude/skills/social-media-manager/data/blocklist.md`:
```
# PII Blocklist — entities that must NEVER appear in posts
## Companies
- [customer names]
## People
- [person names]
## Metrics
- [specific numbers to protect]
```

Check blocklist on every draft. If a blocklisted entity appears, replace it and flag: "Replaced [entity] per your blocklist."

---

## Reputation Layer

Beyond PII, check for reputational risks:

### 1. Claims Checker (Regulatory Language)

In regulated industries (insurance, fintech, healthcare), casual language can be construed as legal guarantees.

**Flag these patterns:**
- "ensures compliance" → suggest "helps manage compliance workflows"
- "guarantees" → suggest "designed to support"
- "eliminates risk" → suggest "reduces risk exposure"
- "certified" / "approved" (unless actually true) → remove or qualify
- "100% accurate" → suggest "high accuracy" with context

**Template flag:** "This sentence could be read as a warranty or guarantee. In [industry], this may have legal implications. Suggested revision: [softer version]"

### 2. Competitor Mentions

Flag any direct competitor mention and ask for intent:
- **Comparison:** Acceptable if factual, risky if subjective. Suggest: frame as category comparison, not company comparison
- **Criticism:** High risk. Suggest: make the point without naming them
- **Praise:** Low risk but can send traffic to competitor. Note this tradeoff
- **General:** Usually fine, but note it

### 3. Forward-Looking Statements

Flag any public commitment:
- "We're launching X next month"
- "Our roadmap includes..."
- "Coming soon: ..."
- "We plan to..."

**Template flag:** "This is a forward-looking statement. Are you comfortable with this public commitment? Consider: 'We're exploring...' or 'We're working on...'"

### 4. Emotional Sentiment Detection (Bad Day Safeguard)

Detect high negative sentiment in drafts:

**Trigger words/patterns:**
- Frustration: "sick of", "tired of", "can't believe", "ridiculous"
- Anger at specific entities: naming VCs, customers, competitors negatively
- Venting: excessive exclamation marks, ALL CAPS sections, sarcasm
- Desperation: "does anyone else struggle with", "why is everything broken"

**Response when detected:**
"This draft reads emotionally charged. Options:
(a) Post now — you know your audience best
(b) Schedule for tomorrow — review with fresh eyes (recommended)
(c) Save to private drafts — revisit later
(d) Rewrite — keep the core insight, remove the heat"

**24-hour cooling period:** If user selects (b), schedule for next day and set a reminder: "Ready to review yesterday's draft? Here it is with fresh eyes."

### 5. Screenshot/Visual PII Check

When generating visual assets or user provides screenshots:
- Flag: dashboards with customer data visible
- Flag: Slack messages with names/channels
- Flag: code with API keys, URLs, internal hostnames
- Flag: email threads with addresses visible

**Template flag:** "This visual may contain [type of PII]. Review before posting."

---

## Pre-Publish Checklist

Run this on every draft before presenting to user:

```
[ ] PII scan — no real names, companies, or sensitive numbers
[ ] Blocklist check — no blocklisted entities
[ ] Claims check — no regulatory language that implies guarantees
[ ] Competitor check — flag any named competitors
[ ] Forward-looking check — flag any public commitments
[ ] Sentiment check — flag emotionally charged content
[ ] Visual PII check — if post includes images/screenshots
[ ] Authenticity check — could user defend this in conversation?
```
