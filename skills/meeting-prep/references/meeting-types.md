# Meeting Type Routing

Reference for how each meeting type modifies the core pipeline. The main
SKILL.md defines the backbone (Steps 0-10). This file defines per-type
overrides for Steps 5, 6, 7, and 8.

Read this file at the start of Step 5 to determine which overrides apply.

---

## Type: DISCOVERY / DEMO

**When:** `meeting_type == "discovery"`. First or early meeting with a prospect.

### Step 5 Override: Full orbit mapping
- Run the complete orbit mapping pipeline (5a-5e) as documented in SKILL.md
- No changes -- this is the default behavior

### Step 6 Override: Sales hypothesis
- Run the complete hypothesis synthesis (6 + 6b) as documented in SKILL.md
- No changes -- this is the default behavior

### Step 7 Override: Demo-led questions
- Run the standard question generation as documented in SKILL.md
- Questions should be demo-led (assume product has been seen)
- No changes -- this is the default behavior

### Step 8 Override: Full 10-section briefing
- Render all sections as documented in SKILL.md
- No changes -- this is the default behavior

---

## Type: FOLLOW-UP SALE

**When:** `meeting_type == "follow-up"`. Subsequent meeting with a known prospect.

### Step 5 Override: Targeted orbit mapping
- Skip 5a-5b (entity extraction and first-pass screen) -- already done in prior prep
- Run 5c only for NEW entities discovered since last meeting (role changes, new board seats)
- Focus on 5d (person fit update) -- has anything changed?

### Step 6 Override: Deal advancement hypothesis
- Replace the standard hypothesis block with:
```
DEAL STATUS
-- Stage: [Where are we in the pipeline?]
-- Momentum: [Accelerating / Steady / Stalling / Stuck -- with evidence]
-- Blockers: [What's preventing next stage? Technical / Budget / Champion / Timing]
-- Champion status: [Active / Distracted / Left / Unknown]
-- Next milestone: [What specifically needs to happen in THIS meeting?]
-- Open threads: [From prior meetings + call intelligence]
-- Risk signals: [Anything suggesting deal is at risk]
```
- Skip 6b (Exposure & Value) unless the meeting includes new stakeholders who haven't heard the pitch

### Step 7 Override: Thread-resolution questions
- Replace Block 1 with "Open Thread Resolution" (3-4 questions):
  - Each open thread from prior calls gets a status-check question
  - Each commitment (yours and theirs) gets a follow-up
- Replace Block 2 with "Blocker Probing" (3-4 questions):
  - Target the specific blocker identified in Step 6
  - Budget: "Has the budget conversation happened? What did they say?"
  - Technical: "Did the team review the architecture? What concerns came up?"
  - Champion: "Who else needs to be involved to move forward?"
- Keep Block 3 as "Next Steps" (2-3 questions):
  - Specific next action proposal
  - Timeline commitment
  - Expansion signal probe

### Step 8 Override: Deal-focused briefing
- Section 1 becomes "Deal Status" (not "Executive Summary")
- Section 2 becomes "Open Threads & Blockers" (not "Why This Matters")
- Section 5 (Entity Map) is omitted unless new entities found
- Add "Section 2.5 -- Meeting History Timeline" (chronological list of all prior meetings with 1-line summaries)

---

## Type: INVESTOR

**When:** `meeting_type == "investor"`. Fundraising meeting or investor update.

### Step 5 Override: Investor orbit mapping
- 5a: Map investor's portfolio companies, board seats, co-investments
- 5b: Screen portfolio for **conflicts** (companies that compete with you) and **synergies** (companies you could partner with or that validate your market)
- 5c: Deep research on conflicting portfolio companies only
- 5d: Replace "person fit" with "investor fit" -- check size, stage preference, thesis alignment
- 5e: Replace persona categories with investor categories: `LEAD_PARTNER`, `ASSOCIATE`, `SCOUT`, `ANGEL`, `STRATEGIC`

### Step 6 Override: Fundraise hypothesis
- Replace the standard hypothesis block with:
```
INVESTOR ANGLE
-- Thesis fit: [How does our company fit their stated investment thesis?]
-- Portfolio conflicts: [Companies in their portfolio that compete or overlap]
-- Portfolio synergies: [Companies we could partner with or cross-sell to]
-- Check size fit: [Does our raise match their typical check size?]
-- Stage fit: [Are we at the stage they typically invest?]
-- Key proof points: [2-3 metrics/milestones that matter most to this investor type]
-- Anticipated hard questions: [3-5 specific questions based on their background]
-- The ask: [Amount, terms, use of funds -- specific]
```
- Skip 6b (Exposure & Value) entirely -- not relevant for investor meetings

### Step 7 Override: Answer bank, not question list
- **Flip the paradigm.** For investor meetings, you're preparing ANSWERS, not questions.
- Generate two blocks:

**Block 1 -- "Anticipated Questions & Answers" (8-12):**
Based on investor's background, portfolio, and common VC questions:
- Market size / TAM
- Why now?
- Why you / team?
- Competition / defensibility
- Unit economics / path to profitability
- Use of funds
- Current traction / pipeline
- Portfolio-specific: "How do you differ from [portfolio company X]?"
Each answer: 2-3 sentences, specific, with numbers where possible.

**Block 2 -- "Questions FOR the Investor" (3-5):**
- "What would make you pass on this?"
- "How do you typically help companies at our stage?"
- Portfolio-specific questions showing you did homework
- Fund-specific: stage of fund, follow-on strategy, board involvement

### Step 8 Override: Investor briefing
- Section 1 becomes "Investor Angle" (from Step 6)
- Section 2 becomes "Portfolio Analysis" (conflicts + synergies)
- Section 3 becomes "Proof Points & Metrics" (the numbers you need to know cold)
- Section 5 (Entity Map) becomes "Portfolio Map" (their investments, grouped by relevance)
- Section 6 becomes "Q&A Bank" (answers first, then your questions)
- Section 7 becomes "Hard Question Prep" (the 3-5 toughest questions with rehearsed answers)
- Omit: Conversation Hooks (too casual for investor meetings), Exposure & Value (wrong frame)

---

## Type: ADVISORY / MENTOR

**When:** `meeting_type == "advisory"`. Meeting with an advisor, mentor, or board member.

### Step 5 Override: Minimal orbit mapping
- Skip full orbit mapping. Advisors are not prospects.
- Only run 5a to understand their background for context -- which of their experiences is most relevant to your current question?
- Skip 5b-5e entirely.

### Step 6 Override: Decision/dilemma framing
- Replace the standard hypothesis block with:
```
ADVISORY CONTEXT
-- Current dilemma: [What you're stuck on -- framed as options with trade-offs]
-- Your current leaning: [Which option you're leaning toward and why]
-- What you need from them: [Specific: "Your read on whether X is viable" / "Help choosing between A and B"]
-- Why THEM: [What in their background makes them uniquely positioned to advise on this?]
-- Context they need: [What do they need to know to give useful advice? Prepare a 2-min verbal summary]
-- Last interaction recap: [What you discussed last time, what's changed since]
```
- Skip 6b entirely.

### Step 7 Override: Specific advisory questions
- **No generic questions.** Every question should be:
  - Specific enough that only this advisor could answer it well
  - Framed as a choice or evaluation, not open-ended
  - Connected to their specific experience

**Block 1 -- "Context & Update" (2-3):**
- What's changed since last meeting
- Quick wins or failures since last advice

**Block 2 -- "Core Questions" (3-5):**
- The main dilemma/decision
- Each question references their specific experience: "When you were at [Company], how did you think about [X]?"
- Probe trade-offs: "What am I not seeing?" / "What's the biggest risk if we go with Option A?"

**Block 3 -- "Forward-Looking" (1-2):**
- "What should I be reading/watching/talking to?"
- "Who else should I be talking to about this?"

### Step 8 Override: Advisory briefing
- Section 1 becomes "What I Need" (the dilemma + options + current leaning)
- Section 2 becomes "Context Dump" (what they need to know to advise well)
- Section 4 becomes "Their Relevant Experience" (not full background -- only what's relevant to your question)
- Omit: Entity Map, Exposure & Value, Objection Prep, Conversation Hooks
- Add: "Key Decision Points" section -- the specific choices you're bringing to the meeting

---

## Type: PARTNERSHIP

**When:** `meeting_type == "partnership"`. Exploring mutual value with a potential partner.

### Step 5 Override: Partner orbit mapping
- 5a: Map their company's products, channels, customer segments, tech stack
- 5b: Screen for **integration points** (technical, commercial, strategic) instead of ICP fit
- 5c: Deep research on integration feasibility and competitive dynamics
- 5d: Replace "person fit" with "partner champion assessment" -- can this person drive the partnership internally?
- Skip 5e (persona categories not applicable)

### Step 6 Override: Partnership hypothesis
```
PARTNERSHIP ANGLE
-- Mutual value: [What each side gets. Must be two-sided.]
-- Integration model: [Technical (API/data), Commercial (co-sell/referral/white-label), Strategic (market access)]
-- Their alternatives: [Who else could they partner with? Why us?]
-- Our alternatives: [Who else could we partner with? Why them?]
-- Champion: [Who internally is pushing for this? What do they need?]
-- Deal structure options: [Revenue share, referral fee, licensing, co-development]
-- Risks: [Dependency, competitive dynamics, execution complexity]
```

### Step 7 Override: Mutual discovery questions
**Block 1 -- "Value Validation" (3-4):**
- Validate that the value prop is real from their side
- "How do your customers currently handle [overlap area]?"
- "What's the gap your team hears most about?"

**Block 2 -- "Integration Feasibility" (3-4):**
- Technical: API readiness, data sharing, timeline
- Commercial: channel conflict, pricing alignment, go-to-market
- "What would need to be true for this to work on your end?"

**Block 3 -- "Structure & Next Steps" (2-3):**
- How they've structured similar partnerships
- Decision process and timeline on their side
- Pilot/proof-of-concept scoping

### Step 8 Override: Partnership briefing
- Section 1 becomes "Partnership Angle" (mutual value)
- Section 2 becomes "Integration Analysis" (technical + commercial + strategic)
- Section 5 becomes "Their Product & Channel Map" (not entity orbit)
- Add "Comparable Partnerships" section -- similar deals in their industry or ours

---

## Type: CUSTOMER SUCCESS / RENEWAL

**When:** `meeting_type == "customer-success"`. QBR, health check, renewal, or expansion discussion.

### Step 5 Override: Skip orbit mapping
- Not applicable. They're already a customer.
- Instead, build an **account health map**: usage signals, support tickets, champion status, renewal date, expansion opportunities.

### Step 6 Override: Account hypothesis
```
ACCOUNT STATUS
-- Health: [Green/Yellow/Red -- with evidence]
-- Usage signals: [If available: adoption, feature usage, last login]
-- Champion status: [Still in role? Still engaged? New stakeholders?]
-- Renewal: [Date, risk level, competitive threat]
-- Expansion: [Other teams/departments/use cases identified in prior calls]
-- Value delivered: [Quantified outcomes since deployment -- what they can take to leadership]
-- Risk signals: [Declining usage, champion departure, budget pressure, competitor evaluation]
```

### Step 7 Override: Health & expansion questions
**Block 1 -- "Health Check" (3-4):**
- How's it going? Open-ended, let them lead.
- Adoption questions: "Which teams are using it most?"
- Friction questions: "What's not working as well as you'd hoped?"

**Block 2 -- "Value Validation" (2-3):**
- "Can you quantify the impact? What would you tell your CFO?"
- "What would you miss most if you didn't have it?"

**Block 3 -- "Expansion" (2-3):**
- "Are there other teams that could benefit?"
- Reference specific use cases from prior calls
- Specific next step / expansion proposal

### Step 8 Override: Account briefing
- Section 1 becomes "Account Status" (health, usage, renewal)
- Section 2 becomes "Value Delivered" (quantified outcomes)
- Omit: Entity Map, Exposure & Value, Conversation Hooks
- Add: "Expansion Opportunity Map" -- other teams/departments identified

---

## Type: INTERNAL (BOARD / TEAM)

**When:** `meeting_type == "internal"`. Board meeting, team alignment, or internal decision.

### Step 5 Override: Stakeholder position mapping
- Skip orbit mapping.
- Instead, map **stakeholder positions**: who supports what option, who's undecided, where are the disagreements?

### Step 6 Override: Decision framing
```
DECISION BRIEF
-- Decision required: [State it in one sentence]
-- Options: [2-3 options with trade-offs]
-- Recommendation: [Your recommended option and why]
-- Stakeholder positions: [Who supports what? Where's disagreement?]
-- Data needed: [What information would change minds?]
-- Success criteria: [What does a good outcome look like?]
```

### Step 7 Override: Discussion questions (not discovery)
- Questions you'll pose to drive the discussion
- "If we go with Option A, what's the biggest risk?"
- "What information would make this decision easier?"
- Anticipate objections to your recommendation

### Step 8 Override: Decision briefing
- Section 1 becomes "Decision Required" (the one sentence)
- Section 2 becomes "Options Analysis" (structured trade-offs)
- Section 6 becomes "Discussion Guide" (questions to drive alignment)
- Omit: Everything sales-related (Entity Map, Exposure, Objection Prep, Conversation Hooks)
- Add: "Pre-Read Summary" -- what was sent in advance, what to reference

---

## Type: HIRING / INTERVIEW

**When:** `meeting_type == "hiring"`. Candidate interview (you interviewing or being interviewed).

### Step 5 Override: Candidate background mapping
- If interviewing a candidate: Map their career arc, projects, skills
- If being interviewed: Map the company, team, role, interviewer background

### Step 6 Override: Fit hypothesis
```
CANDIDATE FIT (if interviewing them)
-- Must-haves: [Role requirements -- technical and cultural]
-- Red flags to probe: [Gaps, short tenures, skill claims needing validation]
-- Sell points: [If we want them -- why this company, role, stage?]
-- Assessment rubric: [What specifically are we scoring on?]

COMPANY FIT (if being interviewed)
-- Why this role: [Your honest reason -- be prepared to articulate]
-- Their likely concerns: [Based on your background, what will they question?]
-- Your differentiators: [What makes you uniquely suited?]
-- Questions to evaluate fit: [Culture, growth, leadership, product]
```

### Step 7 Override: Interview questions
- If interviewing: Candidate-specific questions based on their actual background. Never generic.
- If being interviewed: Prepare answers to likely questions + your questions about the role/company.

### Step 8 Override: Interview briefing
- Simplified format: background, fit analysis, questions, assessment rubric
- Omit all sales-related sections

---

## Fallback: GENERAL

**When:** `meeting_type` doesn't match any specific type.

- Run the standard pipeline as documented in SKILL.md
- Flag to user: "Using general meeting prep. If this is a specific type (investor, advisory, etc.), let me know and I'll tailor the approach."
