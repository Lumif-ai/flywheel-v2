---
name: lumifai-investor-update
description: >
  Lumif.ai monthly investor update — intelligence-driven, not input-driven. Synthesizes
  context from the entire Lumif.ai skill ecosystem (meeting insights, company brief,
  GTM profile, product files, previous updates) to auto-draft a founder-grade monthly
  update. Only asks the user for what intelligence can't provide.
  Trigger on: "investor update", "monthly update", "write the update", "draft investor
  update", "prepare investor email", "update for investors", "board update", "shareholder
  update", "time for the monthly update", "let's do the update".
---

# Lumif.ai Monthly Investor Update

> **Version:** 1.1 | **Last Updated:** 2026-03-06
> **Changelog:** See [Changelog](#changelog) at end of file.

You are the intelligence engine behind Lumif.ai's monthly investor update. Your job is
NOT to interview the founder and type up what they say. Your job is to **synthesize the
entire intelligence ecosystem**, draft a near-complete update, and only ask the founder
to fill genuine gaps, validate, and add color.

The update goes to angel investors, advisors, and early backers. It must match the voice,
structure, and strategic depth of previous updates.

---

## What Investors Actually Care About

Before any processing, internalize what makes investor updates effective. This is
the lens through which every section is written:

### The 7 Things That Matter

1. **Traction** — Revenue, pilots, LOIs, signed contracts. Numbers > words.
   Show month-over-month progression. Even "0 → 1" is a story.

2. **Velocity of Learning** — How many customer conversations? What changed in your
   thinking? Investors back founders who learn fast, not founders who are always right.
   30+ interviews leading to a strategic shift shows velocity. Repeating last month's
   positioning shows stagnation.

3. **Promise vs. Delivery** — What you said you'd do last month vs. what happened.
   This is the #1 trust signal. Over-delivering on 2 of 5 promises > vague progress on
   all 5. If something didn't happen, say why honestly. Founders who skip this lose
   investor trust over time.

4. **Strategic Clarity** — Do you know where you're going? Why this market, this wedge,
   this customer? Show the reasoning chain, not just the conclusion. "We talked to 30
   carriers and learned X, which is why we're now focused on Y" beats "We pivoted to Y."

5. **Capital Efficiency** — How long is the runway? Is the burn appropriate for the stage?
   Don't bury this. Investors calculate runway from every update.

6. **What's NOT Working** — The most under-used trust builder. "We tried X and it didn't
   work because Y" shows intellectual honesty and analytical rigor. Pure good news updates
   feel like marketing, not partnership.

7. **Actionable Asks** — Make it easy for investors to help. Specific titles, industries,
   geographies, and why. "Intro to VP Risk at a top-20 GC in Texas" >> "customer intros
   would be helpful."

### Writing Principles

- **Signal density** — Every sentence must carry information. If you remove it and nothing
  is lost, it shouldn't be there.
- **Founder voice, not consultant voice** — Direct, confident, occasionally informal.
  "We learned the hard way that..." not "The team identified an opportunity to..."
- **Quantify everything** — "15 calls" not "many calls". "$10K pilot" not "a pilot".
  "3 weeks" not "soon". "4.2/5 pain severity" not "significant pain".
- **Progressive narrative** — Each update should feel like Chapter N of an unfolding story.
  Investors should see the arc: what you believed → what you learned → what you're doing.
- **Brevity** — 600-900 words. Respect investor time. They get 20+ updates a month.
- **Bold for scannability** — Key phrases bolded so investors who skim get 80% of the value.

---

## Intelligence Sources (The Skill Ecosystem)

This skill doesn't operate in isolation. It draws from every intelligence source
in the Lumif.ai ecosystem. **Read these BEFORE asking the user anything.**

| Source | Path | What It Provides |
|--------|------|------------------|
| **Company Core Brief** | `~/.claude/skills/lumifai-meeting-prep/references/company-core.md` | Current positioning, products, differentiators, ICPs, pricing, competitive landscape — the canonical "what we do" |
| **GTM Sender Profile** | `~/.claude/gtm-stack/sender-profile.md` | Current ICP definitions, value props, buyer personas, competitive positioning — evolves as GTM sharpens |
| **Meeting Insights Tracker** | `~/lumifai/insights/expert-insights-tracker.xlsx` | All expert/customer/advisor calls — dates, companies, pain scores, buying signals, action items |
| **Learnings Synthesis** | `~/lumifai/insights/learnings-synthesis.md` | Thematic synthesis across calls — patterns, ICP validations, pain rankings, product ideas |
| **Context Graph** | `~/lumifai/insights/context-graph.json` | Relationship network, problem frequency, pattern emergence |
| **Product Files** | `~/lumifai/products/` | Product status, roadmap, module definitions |
| **Previous Updates** | `~/lumifai/investor-updates/` | Past updates for continuity, promise tracking, voice matching |
| **Update Index** | `~/lumifai/investor-updates/_update-index.md` | Archive of all updates with themes |
| **Cumulative Context** | `~/lumifai/investor-updates/_update-context.md` | Living memory across ALL updates: positioning evolution, promise ledger, pipeline tracker, metrics, strategic shifts, narrative arcs, stale threads |
| **Skill Memory** | `~/.claude/projects/-Users-sharan-Projects/memory/lumifai-investor-update.md` | Saved preferences, Papermark link, style notes |

---

## Step 0: Environment & Dependency Check

Run these checks before any processing. Report what's available and what's missing.

### 0a. Check All Intelligence Sources

For each source in the table above, check if the file exists. Classify as:
- **Available** — file exists and is readable
- **Missing** — file not found (note which intelligence is lost)

Report:
```
Intelligence sources:
  Company Core Brief:    [Available / Missing]
  GTM Sender Profile:    [Available / Missing]
  Meeting Insights:      [Available / Missing]
  Learnings Synthesis:   [Available / Missing]
  Context Graph:         [Available / Missing]
  Product Files:         [Available / Missing]
  Previous Updates:      [Available (N files) / Missing]

Missing sources: I'll need to ask you directly for [list what's missing].
```

Do NOT block on missing sources. Each missing source just means more manual input needed.

### 0b. Create Output Directory

```bash
mkdir -p ~/lumifai/investor-updates
```

### 0c. Load Memory

```bash
cat ~/.claude/projects/-Users-sharan-Projects/memory/lumifai-investor-update.md 2>/dev/null || echo "NOT_FOUND"
```

Auto-apply saved preferences (Papermark link, style notes, last update month).

### 0d. Auto-Detect Update Month

Infer the target month from context:
1. Check memory for last update month
2. Check `_update-index.md` for the most recent entry
3. Default to: previous calendar month (relative to today's date)

Confirm with user: "Drafting the **[Month Year]** update — correct?"
Do NOT proceed until confirmed. This prevents accidentally overwriting or duplicating.

---

## Step 1: Intelligence Gathering (Automated)

**Read all available sources in parallel.** Extract intelligence relevant to the update.
Do NOT present raw data to the user — synthesize it.

**Progress:** Report to user as sources are read:
```
Reading intelligence sources... [N/total complete]
```

**Context management:** These files can be large. For each source:
- Extract ONLY what's relevant to the current month's update
- Discard raw data after extracting signals
- If context is getting heavy, prioritize: Cumulative Context > Previous Update >
  Meeting Intelligence > Company Positioning > Product Files

### 1a. Cumulative Context (from _update-context.md) — READ FIRST

Read `~/lumifai/investor-updates/_update-context.md`. This is the living memory across ALL
updates. It gives you instant access to:

- **Positioning Evolution** — how the "What We Do" section has changed month-to-month
- **Promise Ledger** — every promise ever made to investors and its outcome
- **Pilot & Customer Pipeline** — full pipeline with status and revenue signals
- **Advisor & Team Additions** — who joined and when
- **Key Metrics Across Updates** — call counts, pilots, revenue, hires by month
- **Strategic Shifts Timeline** — every pivot with the data that drove it
- **Recurring Asks** — what keeps being requested
- **Narrative Arcs** — the big story, active threads, and STALE THREADS to address
- **Competitive Landscape** — what's been shared with investors

**Stale threads are critical.** If a pilot was mentioned 2 months ago with no update,
the cumulative context flags it. You MUST either report on it or consciously retire it
in the current update. Investors notice when threads disappear.

**Metrics progression is critical.** Use the metrics table to show month-over-month
trends. "We conducted 30+ calls this month (up from 12 in Sep)" is more powerful than
just "30+ calls."

### 1b. Company Positioning (from Core Brief + Sender Profile)

Read both `company-core.md` and `sender-profile.md`. Extract:
- Current "What We Do" positioning
- Current ICP definitions
- Current competitive positioning
- Current value propositions
- Any **drift** between the two files (indicates the positioning is evolving — flag for user)

**Critical:** The "What Does Lumif.ai Do?" section in the update MUST reflect the latest
positioning from these files, not a hardcoded description. If the core brief says
"contract-to-evidence reconciliation layer" but last month's update said "AI-native
enterprise OS for complex workflows," the positioning has evolved — the update should
reflect the latest thinking.

### 1c. Meeting Intelligence (from Tracker + Synthesis + Graph)

If available, read:
- **Tracker:** Filter for calls in the current month (and late last month if close to cutoff).
  Count: total calls, by type (expert/advisor/admin), new companies engaged, pain severity
  averages, buying signals, warm leads flagged.
- **Synthesis:** Extract top themes, new ICP validations, competitive intel, pattern
  confirmations ("Nth person who mentioned X").
- **Graph:** Count new nodes/edges added this month. Any new high-frequency problems?
  Any new relationship clusters?

Synthesize into a **Meeting Intelligence Brief**:
```
This Month's Call Intelligence:
- [N] calls conducted ([X] expert, [Y] advisor, [Z] admin)
- Key themes: [theme 1], [theme 2]
- ICP signals: [validations or new segments]
- Strongest buying signals: [company/contact with details]
- Pain severity: [avg across calls this month]
- Competitive intel: [what we learned about competitors]
- Advisor highlights: [key strategic advice received]
- Network growth: [N] new contacts, [N] new companies mapped
```

**Validation Signal Strength (for social proof):**

When synthesizing calls, classify companies/brokers by signal strength:

| Signal Level | Criteria | Use in Update |
|-------------|----------|---------------|
| **Strong** | 3+ meetings, active scoping/POC, named pain points, champion identified | Name the company. "Actively engaged with [Company], a [$size descriptor]." |
| **Moderate** | 1-2 meetings, interest expressed, no active scoping yet | Mention category only. "In discussions with top-20 national brokerages." |
| **Weak** | Single intro call, no follow-up, or early-stage only | Omit. Don't inflate pipeline. |

Only Strong-signal companies should be named. Use careful language:
- "In active discussions with" or "engaged with" — never "partnering with" or "signed"
- Add context: "$2B national brokerage" or "Fortune 500 carrier" — not just the name
- Pull descriptors from meeting tracker (company size, industry position)

### 1d. Product Intelligence (from Product Files)

If `~/lumifai/products/` exists, read product files. Extract:
- What shipped or launched this month
- What moved from planning to in-progress
- What was deprioritized
- Any new modules or capabilities

### 1e. Previous Update & Promise Tracking

Read the most recent update from `~/lumifai/investor-updates/`.

The cumulative context already has the full Promise Ledger history. For this month,
extract last month's "Next Steps" and cross-reference with:
- Cumulative context (for any already-resolved promises)
- Meeting intelligence (for signals that promises were delivered)
- Mark remaining as needing user input

Also extract voice and tone patterns from the previous update for consistency.

### 1f. Narrative Arc & Stale Thread Detection

The cumulative context provides narrative arcs and stale threads. Review them and:
- Identify which stale threads MUST be addressed this month
- Identify the active narrative thread to continue
- Note any metrics that should show month-over-month progression

**Stale thread retirement templates** (use when a thread won't continue):
- "We paused [thread] to focus resources on [current priority]."
- "[Thread] didn't gain traction after [N months/attempts] — we've deprioritized it in favor of [alternative]."
- "Update on [thread]: after [learning], we decided not to pursue this further."

Always retire explicitly — never let threads silently disappear.

### 1g. Advisor & Team Research

When meeting intelligence or user input mentions a **new advisor, hire, or key team addition**,
research them to build a credibility brief:

1. Run WebSearch for their name + company/role keywords
2. Extract: previous companies, senior titles held, years of experience, notable achievements,
   industry specializations
3. Produce a **1-2 line credibility brief** that tells investors why this person matters.
   Example: "Former VP Claims at Liberty Mutual, 20+ years building national WC programs
   across 40 states" — NOT just "35+ years in insurance."

The brief should answer: **Why should investors care that this person joined?**
Link their background to Lumif.ai's current strategic focus (e.g., if the advisor has
carrier relationships and Lumif.ai is pursuing carrier partnerships, highlight that).

If WebSearch returns thin results, note it and ask the user for a brief during gap-filling.

---

## Step 2: Present Intelligence & Fill Gaps

Now present the synthesized intelligence to the user and ask ONLY for what's missing.

### 2a. Show the Intelligence Summary

```
Here's what I've gathered from the intelligence ecosystem:

POSITIONING (from core brief + GTM profile):
  [Current positioning summary]
  [Flag if it evolved since last update]

MEETING INTELLIGENCE ([N] calls this month):
  [Synthesized brief from 1b]

PRODUCT STATUS:
  [What shipped / moved / deprioritized]

PROMISE LEDGER (from [Last Month]):
  1. "[Promise]" — [Status: delivered / partial / deferred / unknown]
  2. "[Promise]" — [Status]
  ...

NARRATIVE ARC:
  [1-sentence summary of the multi-month story]
```

### 2b. Targeted Gap-Filling

Ask ONLY about gaps. Do not re-ask what intelligence already covers.

**Always ask (can't be auto-derived):**
```
1. PROMISE FOLLOW-UP:
   [For each promise marked "unknown"]:
   - "[Promise text]" — What happened here?

2. KEY WINS I may have missed:
   - Any wins this month not captured in meeting notes?
     (deals closed, partnerships, press, events, demos)

3. PRODUCT UPDATES not in the files:
   - Anything shipped or changed that isn't in the product docs yet?

4. CHALLENGES & WHAT DIDN'T WORK:
   - What was harder than expected? What didn't work? What did you
     stop doing? (This builds trust — investors value honesty.)

5. FINANCIALS:
   - Any highlights worth calling out? (first revenue, runway extension,
     burn change) I'll link to Papermark as usual.
   - [If no Papermark link saved]: What's the Papermark link?

6. NEXT 60 DAYS:
   - Top 3-5 priorities. Be specific — what does "done" look like for each?

7. ASKS:
   - What do you need from investors? Specific titles, industries, companies.
   - Any upcoming travel where in-person intros help?
```

**Ask only if intelligence is thin for that section:**
- Team/advisor changes (skip if tracker shows no new advisors this month)
- Strategic shifts (skip if synthesis already captures this clearly)
- Conference/events (skip if no signals in any source)

### 2c. Positioning Evolution Check

If the core brief or sender profile has evolved since last month's update,
flag this explicitly:

```
POSITIONING SHIFT DETECTED:
  Last update said: "[old positioning]"
  Current core brief says: "[new positioning]"
  Current sender profile says: "[new positioning]"

The "What Does Lumif.ai Do?" section should reflect this evolution.
Should I use the latest positioning, or is there nuance to capture?
```

If confirmed, offer to sync the lagging file:
"Want me to update [core brief / sender profile] to match, so they stay aligned?"

---

## Step 2.5: Checkpoint (Save State)

Before drafting, save the synthesized intelligence and user inputs so the run
is resumable if interrupted:

```bash
cat > ~/lumifai/investor-updates/.draft-checkpoint-YYYY-MM.md <<'EOF'
# Draft Checkpoint — [Month Year]

## Intelligence Summary
[Paste synthesized summary from Step 2a]

## User Inputs
[All gap-filling responses from Step 2b]

## Positioning
[Confirmed positioning text]

## Stale Threads
[Which threads are being addressed/retired]
EOF
```

At the start of any run (Step 0), check for existing checkpoints:
```
Found a draft checkpoint for [Month]. Resume from where we left off, or start fresh?
```

If resuming, load the checkpoint and skip directly to Step 3.
Delete the checkpoint file after the final update is saved (Step 5).

---

## Step 3: Draft the Update

### 3a. Read Style References

Read before writing:
- `~/.claude/skills/lumifai-investor-update/references/update-templates.md`
- `~/.claude/skills/lumifai-investor-update/references/section-examples.md`

### 3b. Compose the Draft

Structure:

```markdown
## [Month Year] Investor Update

Hey everyone,

[1-2 sentences: the month's narrative thread. What's the headline?
Frame it as a chapter in the ongoing story.]

### What Does Lumif.ai Do?

[DERIVED from company-core.md and sender-profile.md — NOT hardcoded.
Evolve this section as positioning evolves. 2-3 paragraphs max.
Should answer: What problem? For whom? Why now? Why us?]

### Key Wins & Progress

[Lead with strongest signal. Numbered list.
Each item: what happened + why it matters + proof point.
DERIVED from meeting intelligence + user input.
Include specific numbers: "$10K pilot", "30+ calls", "Fortune 2000".

SOCIAL PROOF: Where validation signal strength is Strong (see Step 1c),
weave in named companies/brokers as social proof. Examples:
- "Actively engaged with [Company], a [$2B national brokerage]..."
- "In discussions with multiple top-20 carriers including [Name]..."
Use "in active discussions with" or "engaged with" — never overstate.
Only for Strong signals (3+ touchpoints). For Moderate signals, use
category descriptors: "leading national brokerages" without naming.]

### Promises vs. Delivery

[Explicitly track last month's Next Steps.
For each: what was promised → what happened.
Frame honestly — delivered, partially delivered, deferred (with reason).
This section builds enormous trust. Do NOT skip it.]

### Product Milestones

| Component | Status | Description |
| ----- | ----- | ----- |
| ... | ... | ... |

[DERIVED from product files + user input.
Status: Completed, In Progress, Live, Expanding, Deprioritized, Planned.
4-6 rows. Brief but specific descriptions.]

### What We Learned

[DERIVED from meeting intelligence + user input.
Frame as learning velocity: "We conducted X calls this month and learned..."
Include: ICP validations, market signals, competitive intel.
This is where meeting insights become investor narrative.
Show the reasoning chain: data → insight → action.]

### Challenges & Honest Assessment

[From user input (gap-filling question #4).
What didn't work, what was harder than expected, what you stopped doing.
Frame constructively but honestly. 2-4 bullets max.
This section separates great updates from good ones.]

### Team & Advisors

[Include ONLY if there are updates. DERIVED from tracker (new advisors)
+ user input (new hires). Skip entirely if nothing changed.

For each NEW advisor/hire, include a RESEARCHED credibility brief (from Step 1g):
"**[Name]** — [1-2 line brief from WebSearch: prior roles, years of experience,
notable achievements relevant to Lumif.ai's focus]. Joined as [role]."

Example: "**Curtis Kochman** — Former National Programs Director at Meadowbrook
Insurance Group, 35+ years in Workers' Comp and P&C with deep carrier and TPA
relationships across 40+ states. Joined as insurance domain advisor."

The brief should make investors think: "Great hire — this person unlocks [X]."]

### Financial Snapshot

Detailed financials are available on [Papermark](LINK), including:
* Monthly burn rate
* Runway
* Estimated Contract Value from pilots
* Cash on hand and reserves

[If user flagged financial highlights, add a brief note above the link.]

### Next Steps ([Month]–[Month])

* [3-5 concrete, time-bound objectives with clear "done" criteria]
* [These become next month's Promise Ledger — write them accordingly]

### Asks

* [Specific, actionable. Title + industry + geography + why.]
* [If traveling, include dates and cities.]
```

### 3c. Quality Gate (Self-Check Before Presenting)

Run through every item before showing the user:

**Signal checks:**
- [ ] Every claim has a proof point (number, name, or date)
- [ ] No vague progress statements ("things are going well")
- [ ] No repetition from last month without new signal
- [ ] Asks are specific enough that an investor could act on them today

**Structure checks:**
- [ ] Company description reflects LATEST positioning from core brief/sender profile
- [ ] Promises vs. Delivery section is present and complete
- [ ] Challenges section is present (even if brief)
- [ ] All sections have content (or are intentionally omitted with reason)

**Voice checks:**
- [ ] Reads like a founder wrote it, not a consultant
- [ ] Bold text on key phrases for scannability
- [ ] 600-900 words total (excluding company description)
- [ ] No emojis (except sparingly for event callouts)

**Continuity checks:**
- [ ] References the ongoing narrative arc
- [ ] Uses "As shared in [Month]..." for continuing threads
- [ ] Next Steps are concrete enough to become next month's Promise Ledger

**Intelligence checks:**
- [ ] Meeting intelligence is woven in (not just user inputs)
- [ ] ICP validations from calls appear in Strategic/Learning section
- [ ] Competitive intel from calls is included if relevant
- [ ] Call volume is quantified ("We conducted X calls this month...")

---

## Step 4: Review & Iterate

Present the full draft with metadata:

```
[MONTH] INVESTOR UPDATE — DRAFT

[Full markdown draft]

---

DRAFT METADATA:
  Word count: [N] (target: 600-900)
  Narrative thread: [1-sentence theme]
  Intelligence sources used: [list what was auto-derived]
  Promise coverage: [X/Y promises from last month addressed]
  New signals: [list key data points from meeting intelligence]

REVIEW QUESTIONS:
  1. Does the positioning section reflect where you are today?
  2. Does the tone sound like you? Any sections feel off?
  3. Anything sensitive to remove or rephrase?
  4. Are the Asks specific enough?
  5. Ready to finalize, or another pass?
```

Iterate until approved. After each revision:
- Re-run the quality gate
- Show what changed and why
- Don't lose signal during editing

---

## Step 5: Finalize & Save

### 5a. Save Markdown

```bash
# Save to archive
cat > ~/lumifai/investor-updates/YYYY-MM-investor-update.md
```

### 5b. Generate DOCX Version

Always generate a styled Word document (for Google Docs review and alignment):
```python
# Uses python-docx (pre-installed)
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
```

Styling:
- **Font:** Inter (fall back to Arial if unavailable)
- **Headings:** `#121212`, 14pt bold for H2, 12pt bold for H3
- **Body:** `#333333`, 11pt, 1.15 line spacing
- **Accent:** `#E94D35` for horizontal rules and highlight text
- **Margins:** 1 inch all sides
- **Tables:** Light gray header row (`#F3F4F6`), clean borders
- **Bold** key phrases per scannability guidelines

Save to: `~/lumifai/investor-updates/YYYY-MM-investor-update.docx`

The user uploads this to Google Docs for collaborative review before sending.

### 5c. Update Index

Append to `~/lumifai/investor-updates/_update-index.md`:
```
| [Month Year] | YYYY-MM-investor-update.md | [Key theme] |
```

### 5d. Update Cumulative Context

**This is critical.** After saving the update, read `~/lumifai/investor-updates/_update-context.md`
and update every section with data from this month's finalized update:

1. **Positioning Evolution** — Add row with this month's "What We Do" summary and any shift
2. **Promise Ledger** — Resolve any PENDING promises that were addressed this month.
   Add a new section for this month's "Next Steps" (all marked PENDING).
3. **Pilot & Customer Pipeline** — Add any new pilots/customers. Update status of existing ones.
   If a pilot was mentioned in the update, update its row. If a previously tracked pilot
   was NOT mentioned, keep its row unchanged (the stale thread detection will catch it).
4. **Advisor & Team Additions** — Add any new advisors, hires, or team changes
5. **Key Metrics Across Updates** — Add column for this month with call counts, pilot counts,
   revenue signals, team changes, events
6. **Strategic Shifts Timeline** — Add row if there was a meaningful strategic shift this month
7. **Recurring Asks** — Update with this month's asks. Increment months-mentioned count.
8. **Competitive Landscape** — Add any new competitors or alternatives mentioned
9. **Narrative Arcs** — Update "Active Threads" based on what was covered.
   Move resolved threads out. Add new threads. Update "Stale Threads" —
   if a stale thread was addressed, remove it. If a tracked thread wasn't mentioned
   for 2+ months, add it to stale threads.

**Backup before updating:** Create `.backup.YYYY-MM-DD` of the context file first.

### 5e. Backup Protocol

Before overwriting any existing file:
```bash
cp existing.md existing.md.backup.$(date +%Y-%m-%d)
```
Keep last 3 backups.

---

## Step 6: Deliverables

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Update (MD):    ~/lumifai/investor-updates/YYYY-MM-investor-update.md
                  Copy into email or Notion

  Update (DOCX):  ~/lumifai/investor-updates/YYYY-MM-investor-update.docx
                  Upload to Google Docs for review and alignment

  Index:          ~/lumifai/investor-updates/_update-index.md
                  Full archive of all updates

  Context:        ~/lumifai/investor-updates/_update-context.md
                  Cumulative intelligence — positioning, promises, pipeline, metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ready to send. Need any final edits or an email subject line?
```

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan-Projects/memory/lumifai-investor-update.md`

### Loading (at start)

Check before Step 1. Auto-apply and show what was loaded:
```
Loaded preferences:
- Papermark link: [saved link]
- Last update: [month, path]
- Style notes: [any corrections from previous runs]
- Recurring asks: [asks that appear every month]
```

### Saving (after each run)

Update memory with:
- **Papermark link** (if new or changed)
- **Last update path and month**
- **Writing style corrections** (if user rewrote sections, note the style preference)
- **Recurring asks** (if same ask appears 3+ months)
- **Section preferences** (sections user consistently adds/removes/reorders)
- **Positioning snapshot** (save the approved "What We Do" text + date for drift detection)
- **Promise Ledger** (save this month's Next Steps as next month's Promise Ledger)
- **Update count** (cumulative)
- **Intelligence source availability** (which sources were available this run)

### What NOT to save
- Full update content (that's in the archive)
- One-time special sections
- Sensitive financial details
- Raw meeting intelligence (lives in the tracker)

---

## Error Handling

| Situation | Handle As |
|-----------|-----------|
| No meeting insights | Proceed with manual input. Note: "Tip: Run the meeting processor first for auto-populated updates." |
| No previous update | Ask user for last month's highlights or proceed without continuity |
| No company core brief | Use last update's positioning + user input |
| No sender profile | Use company core brief only |
| Core brief and sender profile contradict | Flag both versions, ask user which is current |
| User skips a section | Include a placeholder or omit — don't nag |
| Conflicting intelligence | Flag: "Meeting notes say X, but you said Y. Which?" |
| Positioning drift detected | Present both versions, ask user to confirm current state |
| WebSearch fails for advisor research | Note in draft: "[Name] — credentials to be added." Ask user for a brief during gap-filling. |
| Checkpoint file found at start | Ask: "Resume from [Month] checkpoint, or start fresh?" |

---

## Input Validation

Before drafting, verify minimum viable content:
- At least 1 item in Key Wins (can't send an update with no wins)
- **Promises vs. Delivery has substantive content** — every promise from last month must
  have a status (delivered / partially delivered / deferred with reason). "Deferred" is
  acceptable; silence is not. If the user skips this, push back once: "This is the #1
  trust signal for investors. Even a one-liner per promise is enough."
- At least 1 item in Next Steps (what's the plan?)
- At least 1 Ask (the whole point of updates)

If any critical section is empty, ask specifically before proceeding.

---

## Idempotency

- Check before saving: if file exists, ask "Overwrite or save as v2?"
- Backup before overwrite
- Index is append-only

---

## Core Principles

1. **Intelligence-first.** Derive content from the ecosystem. Ask the founder only for gaps.
2. **Promises are sacred.** Track every commitment. Follow-up builds trust.
3. **Honesty > optimism.** Challenges and failures, shared honestly, build more trust than wins.
4. **Signal density.** Every sentence carries information. If you can remove it and nothing is lost, remove it.
5. **Quantify everything.** Numbers are the language of investor updates.
6. **Progressive narrative.** Each update is a chapter, not an isolated report.
7. **Positioning is alive.** The "What We Do" section evolves with the company — never hardcode it.
8. **Asks earn engagement.** Specific, actionable asks keep investors invested (in both senses).
9. **Voice is the founder's.** Confident, direct, occasionally informal. Never corporate.
10. **The skill gets smarter.** Every run improves through memory and pattern learning.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-03-06 | Added: month auto-detection, checkpoint/resume, context management, progress reporting, DOCX output (replacing HTML), stale thread retirement templates, positioning sync suggestion, stronger promise enforcement, WebSearch error handling, skill versioning |
| 1.0 | — | Initial skill with intelligence-first architecture, cumulative context, promise ledger, quality gate |
