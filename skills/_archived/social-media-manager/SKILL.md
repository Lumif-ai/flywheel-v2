---
name: social-media-manager
version: "1.1"
description: >
  Content pipeline for founders and operators to draft, manage, and publish social media posts
  on LinkedIn and X/Twitter. Mines context store and git history for "postable moments," drafts
  platform-native posts through role-based lenses (CEO, CTO, CPO, combined), enforces PII/reputation
  safety, manages a content backlog and calendar, and learns the user's voice over time.
  Now includes: thought leadership strategy, series management with narrative arcs, ownable
  vocabulary tracking, content pillar planning, and arc condensation.
  Trigger on: "draft a post", "write a LinkedIn post", "tweet about", "social media",
  "content calendar", "post about", "add to backlog", "content ideas", "what should I post",
  "schedule a post", "show my calendar", "draft a thread", "post ideas from this week",
  "write a tweet", "help me post about [topic]", "series on [topic]", "quick post about [topic]",
  "content strategy", "thought leadership series", "plan a series", "condense the series",
  "show my vocabulary", "content pillars".
  Also triggers on: "I want to post about my learnings", "draft something about [event]",
  "what's in my content backlog", "show content stats", "review my posting cadence".
triggers:
  - "draft a post"
  - "write a LinkedIn post"
  - "tweet about"
  - "social media"
  - "content calendar"
  - "what should I post"
  - "content strategy"
tags:
  - content
  - social-media
web_tier: 1
---

# Social Media Manager

A content pipeline for founders — not a polishing tool. Draft posts that sound like you typed
them on your phone between meetings. Mine your real work for stories worth telling.

**Core principle:** Human always reviews and publishes. No auto-posting. No AI disclosure. Posts
should feel authentically founder-written.

## Workflow Overview

```
STRATEGY → IDEA → BACKLOG → DRAFT → PII SCAN → CONTENT CRITIC → USER REVIEW → CALENDAR → REMIND → POST-MORTEM
```

**Modes:**
- **Content strategy** — design a thought leadership series with pillars, vocabulary, and narrative arc (v1.1)
- **Draft a post** — user provides topic, raw notes, or says "pick something for me"
- **Series draft** — draft posts within an active series, maintaining arc and vocabulary rollout (v1.1)
- **Condense series** — compress a series arc (e.g., 8 posts → 4) while preserving narrative (v1.1)
- **Add to backlog** — quick capture an idea for later
- **Show calendar** — view scheduled/upcoming posts
- **Show vocabulary** — display ownable vocabulary registry (v1.1)
- **Content mining** — scan context store for postable moments (v2)
- **Visual assets** — generate quote cards, carousels (v3)

---

## Step 0: Setup & Checks

### 0a. Dependency Check
- Verify `python3` is available
- Verify scripts exist: `scripts/pii_guard.py`, `scripts/calendar_manager.py`, `scripts/backlog_manager.py`
- Verify data directory exists: `~/.claude/skills/social-media-manager/data/`
  - If missing, create it and initialize `blocklist.md` template

### 0b. Context Store Pre-Read
This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md`.

Read `~/.claude/context/_catalog.md` and match tags: `content`, `voice`, `positioning`, `product`, `market`, `people`, `competitors`.
Load recent entries from matched files to inform content mining and topic suggestions.

### 0c. Memory Load
Check for saved preferences at the memory file path (see Memory section below).
Auto-apply: role, tone dials, preferred registers, platform preferences, posting cadence,
hook preference, AI tells to avoid. Show what was loaded.

### 0d. Voice Profile Check
If no voice profile exists in memory, run the **First-Time Setup** (see below).

---

## First-Time Setup (one-time, saved to memory)

Ask these questions (skip any already saved):

1. **Role:** "What's your primary role?" (CEO, CTO, CPO, COO, VP Eng)
   - "Any secondary hats?" (multi-hat founders)
   - "What stage?" (pre-seed, seed, Series A, growth)

2. **Voice Calibration:** "Share 2-3 posts you've written that you liked, or describe your style."
   - Analyze for: register preference, polish level, hook style, vocabulary patterns
   - If no samples: "Pick the register that feels most like you:"
     - Workshop Dispatch (texting a cofounder)
     - Bar Conversation (telling a story to a friend)
     - Honest Retrospective (journaling out loud)
     - Excited Builder (showing someone what you made)

3. **Platforms:** "LinkedIn, X, or both?" + posting frequency target

4. **Blocklist:** "Any customer names, companies, or metrics that should never appear in posts?"
   - Save to `data/blocklist.md`

Save all answers to memory. Never ask again unless user wants to recalibrate.

---

## Thought Leadership vs. Company Blog (v1.1)

All content defaults to thought leadership framing, not company updates.

| Company Blog | Thought Leadership |
|---|---|
| "At [company], we..." | Names the reader's pain |
| Feature announcements | Universal frameworks from earned experience |
| "Interesting, good for them" | "This is exactly what's happening to me" |
| Company = subject | Company = footnote proving the insight |

**The rule:** The company name should appear at most once per post, late in the body, as
proof of the insight. Never as the opening frame. The reader's problem is the subject,
not the company's solution.

**When drafting, ask:** Would someone who's never heard of the company still find this
valuable? If no, reframe.

---

## Content Strategy Mode (v1.1)

Use when: user wants to plan a thought leadership series, define content pillars, or
create a multi-post narrative arc.

### Step 1: Define Content Pillars (2-4)

Each pillar is a recurring theme the user has earned the right to talk about.

```
Pillar definition:
  name: "The Admin Tax"
  one_line: Why smart teams are still drowning
  target: founders, VPs of Ops, anyone busy but not productive
  core_insight: The admin tax isn't wasteful work, it's useful work done by the wrong person
  authority_signal: What gives you the right to say this?
```

Present pillars to user for approval before proceeding.

### Step 2: Create Ownable Vocabulary

Coin terms the user can own. These are names for problems the audience feels but can't
articulate. Each term needs:

```
Term:
  name: "The 60% Trap"
  definition: Spending most time on work that feels productive but isn't your job
  pillar: The Admin Tax
  introduced_in: (post # where it's first coined)
  referenced_in: (subsequent posts that use it)
```

Save vocabulary to: `data/vocabulary.md`

**Rules for good ownable vocabulary:**
- Names a feeling, not a solution
- Instantly recognizable to the target audience ("oh, that's what that is")
- Short enough to become a hashtag
- Not jargon, not acronyms

### Step 3: Design the Narrative Arc

Map posts to a story progression:

```
Arc phases:
  1. Problem recognition — name the pain, make the reader feel seen
  2. Obvious solution + its limit — show empathy for what they've tried
  3. Deeper insight — the thing most people miss
  4. Bringing it home — proof it works, full circle
```

Each phase gets 1-2 posts. Total arc length: 3-8 posts (recommend 4-6 for tightest narrative).

### Step 4: Generate Series Overview

Auto-generate `data/drafts/00_series_overview.md` containing:
- Series arc table (post #, title, week, pillar, status)
- Suggested cadence with specific dates
- Vocabulary rollout table (term, coined in, referenced in)
- Cross-references between posts
- Publishing protocol

### Step 5: Set Cadence

Determine posting rhythm:
- **Series posts:** How many per week? (recommend 1-2)
- **Standalone/reactive posts:** Fill remaining slots to hit weekly target
- **Series pacing:** Never post 3+ series posts in a row without a standalone break

Example for 3-4x/week target with 4-post series:
```
Mon: Series post
Wed: Standalone/reactive
Fri: Standalone/reactive (or skip)
```

---

## Series Arc Condensation (v1.1)

When user wants to reduce post count (e.g., "do 4 instead of 8"):

### Step 1: Identify the Minimum Viable Arc
The arc phases (problem → failed fix → insight → payoff) are the skeleton. Each phase
needs at least one post. Cut within phases, not across them.

### Step 2: Merge Strategy
For each cut post, identify:
- **Core insight:** Does another post in the same phase cover it?
- **Ownable vocabulary:** Does this post coin a term? If so, it must be absorbed by a surviving post.
- **Best elements:** What's the strongest hook, story, or proof point? Carry it forward.

### Step 3: Rewrite, Don't Edit
Condensed posts are NOT edits of originals. They're new drafts that absorb the best elements
from cut posts. The surviving post gets richer, not longer.

### Step 4: Update Series Overview
After condensation, regenerate the overview with new post count, updated vocabulary
rollout, and revised cross-references.

---

## Ownable Vocabulary Registry (v1.1)

Maintain a vocabulary file at `data/vocabulary.md`.

### Format
```markdown
# Ownable Vocabulary

## [Term Name]
- **Definition:** one-line definition
- **Pillar:** which content pillar it belongs to
- **Coined in:** post title + series name
- **Referenced in:** list of posts that use it after coining
- **Status:** coined | established (used 3+ times) | retired
```

### Operations
- **Show vocabulary:** Display the full registry
- **Add term:** When a new post coins a term, add it automatically
- **Track references:** When a draft uses an existing term, update its referenced_in list
- **Suggest usage:** When drafting a post in a pillar, suggest relevant existing vocabulary

### Rules
- A term should be coined (defined/explained) in exactly one post
- After coining, it can be referenced without re-explaining
- If a term isn't getting referenced, consider retiring it
- Vocabulary rollout should be sequential: don't reference a term before it's coined

---

## Drafting a Post

### Step 1: Understand the Input

Accept ANY input format — the user's raw material is the priority:
- **Specific topic:** "Post about our compliance automation approach"
- **Raw notes/rant:** Pasted text, bullet points, stream of consciousness
- **Event reaction:** "React to [news/event/announcement]"
- **"Pick for me":** Use context store + backlog to suggest 3 ideas
- **Series episode:** "Next episode of [series name]"

### Step 2: Choose Lens & Platform

Based on the topic and user's role profile:
- Select primary lens (CEO, CTO, CPO, or combination)
- Select platform (LinkedIn or X) if not specified
- If the topic spans multiple lenses, note: "This touches both [X] and [Y]. Want to combine
  or split into two posts?"

Reference `references/voice_system.md` for lens definitions and combination patterns.

### Step 2b: Interview for Real Details (v1.1 — MANDATORY)

**NEVER fabricate specifics.** No made-up numbers, anecdotes, stories, quotes, or scenarios.
Every concrete detail in a post must come from the user or from verifiable sources
(context store, meeting notes, git history, public data).

Before drafting, interview the user for the raw material:

**For a topic-based post:**
Ask 3-5 targeted questions to extract real details. Examples:
- "What's a specific example of [topic] from the last month?"
- "Do you have actual numbers? Hours spent, tasks counted, tools involved?"
- "Who was involved? (I'll anonymize them)"
- "What did you try first? What failed?"
- "What surprised you about this?"

**For a series post with a defined angle:**
Ask questions specific to that angle. For "Admin Tax":
- "What admin work did you actually do last week?"
- "How much time roughly?"
- "What tools were involved?"
- "What's the most absurd example of useful-but-wrong-person work you've done recently?"

**Rules:**
- Ask in a batch (3-5 questions), not one at a time
- If the user gives brief answers, that's fine. Work with what they give.
- If details are thin, write a shorter post. A real 800-char post beats a fabricated 1800-char one.
- Structural observations and frameworks (like "Admin Tax") are fine to create. Specific
  stories, numbers, and anecdotes are NOT fine to invent.
- Context store and meeting notes can supply details without asking (cite the source).

**What you CAN create without asking:**
- The framing/angle
- Hook variants
- The coined term and its definition
- The structure and flow
- Platform formatting

**What you CANNOT create without user input:**
- Specific numbers (hours, percentages, counts)
- Anecdotes ("I talked to a VP who...")
- Stories ("Last Tuesday I...")
- Quotes from other people
- Tool inventories ("14 spreadsheets, 9 Slack channels")

### Step 3: Draft the Post

**Write a ROUGH draft — intentionally imperfect.** Reference `references/voice_system.md` for style rules.
Draft ONLY from real details provided by the user or sourced from context store.

Key rules:
- Short sentences. Fragments. Line breaks.
- Start mid-story, not with preamble
- Use the user's preferred register
- Include specific details FROM THE USER (numbers, tools, real situations, anonymized)
- End abruptly or with a genuine question. Never motivational closer.
- NO em dashes, semicolons, "here's the thing", parallel lists, buzzwords
- If you don't have enough detail for a section, leave a [PLACEHOLDER: need X from user] tag

**For LinkedIn:** Follow `references/linkedin_guide.md` — hook-first, line breaks, 1200-1800 chars
**For X:** Follow `references/x_guide.md` — 280 chars or thread (5-8 tweets), punchy

Generate **3-5 hook variants** — the first line is 80% of the post. Present all hooks and
let the user pick.

### Step 4: PII & Reputation Scan

Run the PII guard on the draft:
```bash
python3 ~/.claude/skills/social-media-manager/scripts/pii_guard.py --draft "DRAFT TEXT"
```

Check results:
- **HIGH severity:** Block the draft. Show issues. Require fixes before presenting.
- **MEDIUM severity:** Show warnings inline with the draft. Suggest alternatives.
- **LOW severity:** Note at bottom. User can ignore.
- **Bad Day Safeguard triggered:** Present the cooling period options.

Also check `references/pii_reputation.md` for:
- Regulatory claims language (insurance/compliance especially)
- Competitor mentions — flag intent
- Forward-looking statements — flag commitment

### Step 4b: Content Critic Gate (v1.1)

After PII scan, automatically run the content-critic skill on the draft.

This is a **default gate** on every draft. Load and follow the full critique framework
defined in `~/.claude/skills/content-critic/SKILL.md`. Run all 8 lenses:
voice authenticity, AI-smell, concept density, thought leadership framing, hook strength,
platform fit, series coherence (if applicable), PII/reputation.

**Full auto-fix loop (default):**
1. Run all 8 lenses on the draft
2. Auto-fix ALL findings (HARD, SOFT, and NOTE) in a single pass
3. Present the user with:
   - The **revised draft** (clean, ready to publish)
   - A **change log** showing what was changed and why (before → after for each fix)
   - The **hook ranking** from the critic
4. User approves, tweaks, or kills

The user never sees a broken draft. They see the best version with full transparency
on what the critic caught and how it was fixed.

**Important:** The auto-fix must preserve the user's voice. Fixes should make the draft
MORE raw/authentic, not more polished. When fixing AI-smell, replace with rougher
alternatives. When reducing concept density, cut don't compress. When fixing parallel
structures, break the symmetry rather than rewriting.

### Step 5: Present Draft

Show:
1. The revised draft (post-critic, best hook selected)
2. Critic change log (what changed + why, collapsed/summary format)
3. Alternative hooks ranked by strength
4. Metadata: platform, lens, category, estimated character count
5. "Approve, tweak, or kill?"

### Step 6: Calendar & Backlog

On **approve:**
- Add to calendar via `scripts/calendar_manager.py`
- Tag with: date, platform, lens, category, intent, series (if applicable)
- Save draft text to `data/drafts/POST-XXX.md`

On **edit:**
- Apply user's changes
- Track edit patterns in memory (what they changed = voice calibration data)
- Re-run PII scan on edited version

On **kill:**
- Discard. Optionally save core idea to backlog.

---

## Backlog Management

### Adding Ideas
```bash
python3 ~/.claude/skills/social-media-manager/scripts/backlog_manager.py add \
  --idea "IDEA TEXT" --lens CEO --tier evergreen --tags "compliance,product"
```

Tier assignment:
- **now** — time-sensitive, post within 6 hours
- **this_week** — timely but not urgent
- **evergreen** — can be scheduled anytime

### Listing Ideas
```bash
python3 ~/.claude/skills/social-media-manager/scripts/backlog_manager.py list [--tier now]
```

### Promoting to Calendar
```bash
python3 ~/.claude/skills/social-media-manager/scripts/backlog_manager.py promote \
  --id IDEA-001 --date 2026-03-15 --platform linkedin
```

---

## Calendar Operations

### View Calendar
```bash
python3 ~/.claude/skills/social-media-manager/scripts/calendar_manager.py list [--week] [--month]
```

### Calendar Stats
```bash
python3 ~/.claude/skills/social-media-manager/scripts/calendar_manager.py stats
```

Shows: status breakdown, platform mix, category balance, lens distribution, upcoming posts, overdue items.

### Reschedule
```bash
python3 ~/.claude/skills/social-media-manager/scripts/calendar_manager.py reschedule \
  --id POST-001 --new-date 2026-03-17
```

### Calendar Intelligence (applied by Claude, not scripted)

When reviewing calendar, check and advise on:
- **Topic diversity:** Alert if >3 consecutive posts in same category
- **Lens balance:** Alert if >3 consecutive posts with same lens
- **Platform rotation:** Alert if neglecting one platform for >1 week
- **Posting cadence:** Compare actual vs. target frequency from memory
- **Overdue posts:** Suggest graceful reset: "You have N overdue posts. Clear backlog or reschedule?"

### Cadence Planning (v1.1)

When user sets a frequency target (e.g., "3-4x/week"), build a cadence plan:

**Slot types:**
- **Series slots:** Fixed days for series posts (e.g., every Monday)
- **Standalone slots:** For reactive, evergreen, or one-off posts
- **Buffer slots:** Optional posts that can be skipped without breaking rhythm

**Rules:**
- Series posts get priority scheduling on consistent days
- Never schedule 3+ series posts in a row without a standalone break
- Standalone posts should vary in category (don't do 3 product posts in a week)
- When a timely/reactive post comes up, bump the least-time-sensitive standalone post

**Example cadence for 3-4x/week with an active series:**
```
Mon: Series post (fixed)
Wed: Standalone/reactive
Fri: Standalone (optional, skip if nothing good)
```

Show the cadence plan when creating a series or when user asks "what should I post this week?"

---

## Content Mining (v2 — placeholder)

When context store has relevant data, scan for postable moments:
- Meeting decisions under pressure
- Customer quotes (anonymized)
- Industry signals worth reacting to
- Git history milestones (significant commits, architecture changes)

Surface as: "I found 3-5 post ideas from this week's activity. Want to see them?"

When mining for a series, tag each idea with which pillar and arc phase it fits.

---

## Series Management (v1.1)

### Creating a Series

When user says "series on [topic]" or "plan a series":

1. **Run Content Strategy Mode** (above) to define pillars, vocabulary, and arc
2. **Create series directory:** `data/drafts/` with files named `series_NN_slug.md`
3. **Generate overview:** `data/drafts/00_series_overview.md` (auto-generated, see format below)
4. **Draft all posts** in the arc, using parallel agents for speed (2 posts per agent)

### Series Overview Format (auto-generated)

Every series gets an overview file at `data/drafts/00_series_overview.md`:

```markdown
# [Series Name]: [N]-Post Thought Leadership Series

## Series Arc
| # | Title | Week | Pillar | Status |
|---|-------|------|--------|--------|

## Suggested Cadence
[Specific dates based on start date and frequency]

## Vocabulary Rollout
| Term | Coined In | Referenced In |
|------|-----------|---------------|

## Cross-References
[Which posts reference which]

## Publishing Protocol
[Platform order, scan requirements]

## Draft Files
[List of files]
```

### Series Drafting Rules

- Each post must work **standalone** (new followers join mid-series)
- Include **callbacks** to previous posts when referencing coined vocabulary
- First use of a term = define/explain it. Subsequent uses = reference without re-explaining.
- **Cross-platform:** Every series post gets both LinkedIn (full) and X (standalone hook tweet, LinkedIn link in reply)
- Each draft file contains: 3-5 hook variants, full LinkedIn draft, X version

### Series Pacing Rules

- Max **2 series posts per week** (don't fatigue the audience)
- Always **interleave** with standalone/reactive posts
- Series posts on consistent days (e.g., every Monday) for audience expectation
- If series is 4+ posts, consider a "previously on" callback in each post's first paragraph

### Series Health Checks
- Track engagement per episode vs. series average
- If episode N gets <50% of episode 1's engagement, suggest wrapping early
- Suggest shorter series (3-4 posts) over longer ones (7+)

---

## Post-Publish Tracking (v4 — placeholder)

After publishing, user provides engagement data:
- Impressions, likes, comments, reposts
- DMs generated
- Track performance by: lens, category, platform, time, intent
- Feed back into voice calibration and content strategy

---

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md`.

**Pre-read tags:** `content`, `voice`, `positioning`, `product`, `market`, `competitors`

**Post-write:** After creating content plans or publishing posts, write relevant insights to:
- Content-related context files (if they exist in catalog)
- `_inbox.md` for new content strategy patterns worth sharing across skills

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/{current-project}/memory/social-media-manager.md`

### Loading (at start)
Check for saved preferences. Auto-apply: role, voice profile, posting cadence,
blocklist updates, hook preferences. Show what was loaded.

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to Save
- Role (primary, secondary, stage)
- Voice profile: registers, polish level, tone dials, AI tells banned
- Hook preference (question, statement, mid-story, statistic)
- Platform preferences and posting frequency targets
- Posting days/times that work
- Edit patterns (what the user consistently changes = calibration signal)
- Category/lens balance preferences
- Blocklist additions

### What NOT to Save
- Draft content, post text, specific ideas
- Engagement numbers (those go in calendar/post-mortem tracking)
- Confidential details from context store

---

## Dependency Check (Step 0a)

```bash
# Verify scripts exist
ls ~/.claude/skills/social-media-manager/scripts/pii_guard.py
ls ~/.claude/skills/social-media-manager/scripts/calendar_manager.py
ls ~/.claude/skills/social-media-manager/scripts/backlog_manager.py

# Verify data directory
mkdir -p ~/.claude/skills/social-media-manager/data/drafts
```

No external Python packages required — all scripts use stdlib only.

---

## Input Validation

Before drafting:
- If user provides a topic, confirm platform if not specified
- If "pick for me" mode, verify backlog or context store has content to mine
- If series mode, verify series exists or offer to create one

Before calendar operations:
- Verify date format (YYYY-MM-DD)
- Verify platform is valid (linkedin, x, both)

---

## Error Handling

- If PII guard script fails, warn user and present draft with manual review note
- If calendar/backlog CSV is corrupted, attempt to read what's valid, report corruption
- If context store is empty, skip content mining gracefully — don't block drafting

---

## Deliverables

Every run that produces a draft or updates the calendar must end with:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Draft:     ~/.claude/skills/social-media-manager/data/drafts/POST-XXX.md
  Calendar:  ~/.claude/skills/social-media-manager/data/calendar.csv
  Backlog:   ~/.claude/skills/social-media-manager/data/backlog.csv
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Reference Files

Load these as needed during drafting:
- **Voice system:** `references/voice_system.md` — role lenses, registers, style rules, voice profile structure
- **LinkedIn guide:** `references/linkedin_guide.md` — platform formatting, algorithm, content types
- **X guide:** `references/x_guide.md` — thread mechanics, character limits, platform differences
- **PII & reputation:** `references/pii_reputation.md` — entity scrubbing, claims checker, sentiment detection
- **Content patterns:** `references/content_patterns.md` — anti-patterns, AI smell detector, category balance, timeliness tiers

---

## Version Roadmap

- **v1.0:** Voice setup, drafting, PII guard, reputation layer, backlog, calendar, bad day safeguard, AI-smell detector
- **v1.1 (current):** Thought leadership framing, content strategy mode, series management, ownable vocabulary registry, arc condensation, cadence planning
- **v2:** Context mining, timeliness engine, semantic dedup, fact-checking
- **v3:** Visual assets (quote cards, carousels), Slack reminders, approval workflow, polls
- **v4:** Performance tracking, intent-based measurement, memory-driven feedback loop, anti-abandonment features

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-03-15 | Thought leadership vs. company blog framing, content strategy mode (pillars + arc design), series management (full implementation replacing v2 placeholder), ownable vocabulary registry, series arc condensation workflow, cadence planning with series pacing rules, content-critic as default quality gate (Step 4b) |
| 1.0 | 2026-03-14 | Initial version: voice setup, drafting engine, PII guard, reputation layer, backlog manager, calendar manager, role-based lenses, AI-smell detector, bad day safeguard |
