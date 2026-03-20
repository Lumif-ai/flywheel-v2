---
name: content-critic
description: >
  Quality gate for social media drafts before they get finalized. Runs a systematic
  critique across voice authenticity, AI-smell detection, structural issues, vocabulary
  density, PII exposure, and platform fit. Produces a scored report with specific line-level
  fixes. Use AFTER drafting, BEFORE user review. Trigger on: "critique this post",
  "review my draft", "is this post ready", "vet this post", "run the critic",
  "check this draft", "content QA", "post quality check", "does this sound like me",
  "AI smell check", "ready to publish?". Also auto-triggers when social-media-manager
  produces a draft and the user says "review" or "how does it look".
---

> **Version:** 1.0 | **Last Updated:** 2026-03-15
> **Changelog:** See [Changelog](#changelog) at end of file.

# Content Critic

A systematic quality gate for founder thought leadership posts. Not a grammar checker.
A "does this sound like a real person wrote it between meetings" detector.

**Core principle:** Find problems, fix them, show your work. The user sees the best version
of the draft plus a change log of what was fixed and why. No back-and-forth.

**The loop:**
1. Critique: Run all 8 lenses
2. Auto-fix: Apply fixes to ALL findings (HARD, SOFT, NOTE)
3. Present: Revised draft + change log (before → after for each fix)
4. User: Approves, tweaks, or kills

**Fix philosophy:** Fixes must make the draft MORE raw/authentic, not more polished.
When fixing AI-smell, replace with rougher alternatives. When reducing concept density,
cut, don't compress. When fixing parallel structures, break the symmetry rather than
rewriting elegantly.

---

## When to Run

- After any draft is produced by social-media-manager (or manually written)
- Before the user does their final review
- On individual posts or full series (batch mode)
- Can be re-run after edits to verify fixes landed

---

## Step 0: Load Context

### 0a. Load Voice Profile
Read the user's voice profile from memory:
`~/.claude/projects/{current-project}/memory/social-media-manager.md`

Extract: polish_level, preferred_registers, ai_tells_banned, hook_preference, role.

### 0b. Load Skill Memory
Check for saved critic calibration at the memory file path (see Memory section below).
This tracks: which checks the user cares about most, which they've overridden, false
positive patterns to suppress.

### 0c. Load Draft
Accept input as:
- A file path to a draft markdown file
- Pasted text in the conversation
- "Critique all posts in [series]" for batch mode

---

## The Critique Framework: 8 Lenses

Run every draft through all 8 lenses. Each lens produces a severity rating and specific
line-level findings.

### Lens 1: Voice Authenticity (weight: HIGH)

Does this sound like the user, or like an AI doing an impression?

**Check against polish_level from voice profile:**
- Polish 1-2: Should feel typed on phone. Fragments. Rough edges. Incomplete thoughts.
- Polish 3: Cleaned up but still conversational.
- Polish 4-5: Polished thought piece. (Not this user's style.)

**Specific checks:**
- Sentence length variance: flag if most sentences are 10-15 words (AI default). Real
  posts mix 3-word fragments with 25-word run-ons.
- Rhythm: flag if paragraphs are evenly sized. Real posts have jagged rhythm, one-line
  paragraphs next to dense blocks.
- Register consistency: does the post stay in the declared register (bar_conversation,
  honest_retrospective, etc.) or drift into "conference talk" energy?
- Ending: does it land with a genuine question or abrupt stop? Or does it wrap up too neatly?

**Scoring:**
- PASS: reads like the user could have typed this
- SOFT FAIL: mostly authentic, 2-3 lines feel too polished
- HARD FAIL: reads like a professional writer's approximation of raw

### Lens 2: AI-Smell Detection (weight: HIGH)

Reference `~/.claude/skills/social-media-manager/references/content_patterns.md` for the
full anti-pattern list.

**Structural tells:**
- Perfect three-part framework with alliteration
- Numbered list where every item starts with a verb
- Intro > 3 points > conclusion > CTA (too neat)
- Every sentence roughly the same length
- Clean parallel structures ("Not X. Y." repeated)

**Language tells:**
- Em dashes used more than zero times (BANNED for this user)
- "Here's the thing" / "Let me break it down" / "The truth is" (BANNED)
- Semicolons (BANNED)
- Abstract nouns: "innovation", "transformation", "disruption", "journey"
- "Leverage", "synergy", "ecosystem", "paradigm"
- "It's not about X. It's about Y." (parallelism tell)
- "I used to think X. Then I realized Y." (too clean an arc)
- Perfect grammar in every sentence (real people make minor errors)

**Scoring:**
- PASS: 0 tells detected
- SOFT FAIL: 1-2 tells, easily fixable
- HARD FAIL: 3+ tells, needs significant rework

### Lens 3: Concept Density (weight: MEDIUM)

How many new ideas is the reader asked to absorb?

**Rule:** One new coined term per post. Maximum two new concepts.

**Check:**
- Count new vocabulary terms introduced (defined/explained for first time)
- Count new frameworks or mental models introduced
- If >1 coined term: flag with "Split this or cut one. Reader can absorb one new term."
- If >2 new concepts: flag with "Pick the strongest. Save the rest for another post."

**Exception:** A series finale can reference multiple previously-coined terms without
re-explaining them. That's callbacks, not density.

### Lens 4: Thought Leadership Framing (weight: MEDIUM)

Is this thought leadership or a company blog post?

**Check the ratio:**
- Company name should appear at most 1x, late in the post
- The reader's problem should be the opening frame, not the company's solution
- "At [company], we..." pattern = HARD FAIL
- "We built..." as the main narrative = SOFT FAIL (should be insight-first)
- Would someone who's never heard of the company find this valuable? If no, reframe.

**Scoring:**
- PASS: company is footnote, reader's pain is subject
- SOFT FAIL: company mentioned 2x or appears before midpoint
- HARD FAIL: reads like a company blog post

### Lens 5: Hook Strength (weight: HIGH)

The first line is 80% of the post on LinkedIn.

**Check:**
- Does it start mid-story, with a specific number, or a contrarian statement?
- Does it create an open loop the reader needs to close?
- Would you stop scrolling for this?
- Generic opener = HARD FAIL ("In today's...", "I've been thinking about...", "As a founder...")
- Leading with the conclusion = SOFT FAIL (the hook should create tension, not resolve it)

**Also check hook variants if provided:**
- Rank the variants from strongest to weakest
- Flag if the draft uses a weaker hook than the best variant

### Lens 6: Platform Fit (weight: LOW)

**LinkedIn checks:**
- Character count (target 1200-1800 for best engagement, max ~3000)
- Line breaks after every thought (forces "see more" click)
- No external links in body (kills reach)
- Ends with question or soft CTA (not "like and share")
- No more than 2 hashtags

**X/Twitter checks:**
- Under 280 characters (hard limit for free accounts)
- Works as standalone (doesn't require reading the LinkedIn post)
- Punchy, not a compressed version of the LinkedIn post

### Lens 7: Series Coherence (weight: MEDIUM, series posts only)

Only runs when the post is part of a series.

**Check:**
- Does it reference coined vocabulary from previous posts correctly?
- Does it use a term before it's been coined in the series? (out-of-order)
- Does it work standalone for someone joining mid-series?
- Does the cross-reference feel natural or forced?
- Is the series arc progressing (problem > solution > insight > payoff)?

### Lens 8: Fabrication Detection (weight: CRITICAL)

Flag any specific detail that was not provided by the user or sourced from context store/
meeting notes/git history/public data.

**HARD FAIL on ANY of these if not user-supplied:**
- Specific numbers ("37 hours", "14 spreadsheets", "47 hours saved per month")
- Anecdotes about other people ("I talked to a VP who...", "A fintech founder told me...")
- Stories presented as personal experience that weren't provided by the user
- Quotes attributed to real or fictional people
- Tool inventories ("9 Slack channels, 3 Notion databases")
- Statistics presented as data ("73% of knowledge is lost")

**PASS on these (can be created by AI):**
- The framing, angle, and coined term
- Hook variants and structure
- Definitions of concepts
- General observations about patterns (without fabricated specifics)
- Questions to the audience

**Auto-fix:** Replace fabricated specifics with [PLACEHOLDER: ask user] tags. The draft
should NOT be presented as complete if it contains fabricated details. Instead, present
it as a skeleton with interview questions for the user to fill in the real details.

This lens overrides all others. A beautifully written post with fabricated details is
worse than a rough skeleton with real ones.

---

### Lens 9: PII & Reputation (weight: HIGH)

**Check:**
- Real company names (should be anonymized: "a mid-size GC in Texas")
- Real person names (should be role descriptors)
- Specific revenue/ARR figures (should be ranges)
- Forward-looking statements ("we're launching...", "coming soon...")
- Claims language ("ensures compliance", "guarantees", "eliminates risk")
- Made-up statistics presented as real (flag any % or number that isn't sourced)

---

## Output Format

The critic produces TWO outputs: a revised draft file and a change log shown to the user.

### 1. Revised Draft File

Overwrite the original draft file with the fixed version. Same format (hooks, LinkedIn
draft, X version), but with all fixes applied.

### 2. Change Log (shown to user)

Present with the revised draft:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT CRITIC: [title]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Findings: [N] fixed | Platform: [linkedin / x / both]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHANGES MADE:

1. [LENS] — [one-line description]
   Before: "[original text]"
   After:  "[fixed text]"
   Why:    [brief reason]

2. [LENS] — [one-line description]
   Before: "[original text]"
   After:  "[fixed text]"
   Why:    [brief reason]

...

HOOK RANKING:
1. Hook [X] — [why it's strongest] ← SELECTED
2. Hook [Y] — [why it's second]
...

STRONGEST MOMENT: "[quote the best line]"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Severity levels (internal, used for prioritizing fixes)
- HARD: AI tells, PII exposure, company-blog framing. Always fix.
- SOFT: Polish issues, density, weak hooks. Always fix.
- NOTE: Optional improvements. Fix if they improve without over-polishing.

---

## Batch Mode (Series Critique)

When critiquing a full series:

1. Run all 8 lenses on each post individually
2. Then run series-level checks:
   - **Vocabulary rollout order:** Are terms coined before they're referenced?
   - **Arc progression:** Does problem > fix > insight > payoff hold?
   - **Tone consistency:** Do all posts feel like the same person wrote them?
   - **Concept distribution:** Is any post overloaded while another is thin?
   - **Cross-reference balance:** Are callbacks natural or forced?
3. Present individual reports + a series summary

---

## Calibration Over Time

### False Positive Tracking
If the user overrides a finding ("no, that's fine, leave it"), save the pattern to memory:
- What was flagged
- What the user said
- The pattern to suppress in future

### Severity Tuning
If the user consistently ignores a lens, lower its weight. If they consistently agree
with a lens, confirm its weight. Track in memory.

### Voice Drift Detection
Compare the draft against the user's edit patterns stored in social-media-manager memory.
If the user always adds fragments, always removes transitions, always shortens
conclusions, apply those patterns to the critique proactively.

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/{current-project}/memory/content-critic.md`

### What to Save
- False positive patterns the user has overridden
- Lens weight adjustments (which checks matter most to this user)
- Recurring fix patterns (if the same issue appears 3+ times, note it)
- Voice calibration signals from user edits

### What NOT to Save
- Draft content or post text
- Specific findings from individual critiques

---

## Input Validation

- Verify draft file exists before reading
- Verify voice profile memory exists (if not, warn: "No voice profile loaded. Critique
  will use defaults. Run social-media-manager first-time setup for calibrated results.")
- If batch mode, verify series overview file exists for series-level checks

---

## Error Handling

- If voice profile can't be loaded, run with conservative defaults (flag more, not less)
- If a lens can't complete (e.g., no series overview for series checks), skip it and note
- Never block the critique because one lens failed

---

## Dependency Check

No scripts required. No external packages. This skill is pure Claude reasoning against
the voice profile and content pattern references.

**Reference files loaded as needed:**
- `~/.claude/skills/social-media-manager/references/content_patterns.md`
- `~/.claude/skills/social-media-manager/references/voice_system.md`
- `~/.claude/skills/social-media-manager/references/pii_reputation.md`
- `~/.claude/skills/social-media-manager/data/vocabulary.md` (for series coherence checks)
- `~/.claude/skills/social-media-manager/data/blocklist.md` (for PII checks)

---

## Version Roadmap

- **v1.0 (current):** 8-lens critique framework, batch mode, calibration tracking
- **v1.1:** Comparative analysis (compare draft against user's best-performing published posts)
- **v2.0:** A/B hook testing suggestions, engagement prediction based on post history patterns

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-15 | Initial version: 8-lens critique framework (voice authenticity, AI-smell, concept density, thought leadership framing, hook strength, platform fit, series coherence, PII/reputation), full auto-fix loop (critique → fix → present revised draft + change log), batch mode for series, calibration tracking |
