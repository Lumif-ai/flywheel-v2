# Content Patterns & Anti-Patterns

## What Makes Founder Posts Compelling

### The 4 Pillars
1. **Specificity** — "We switched from Postgres to SQLite and our p99 dropped 40x" beats "Sometimes simpler is better"
2. **Narrative tension** — what you expected vs. what actually happened
3. **Decision transparency** — showing the tradeoffs, not just the outcome
4. **Authenticity** — contrarian takes, honest failures, real numbers

### The Unpolished Principle
The skill's job is NOT to write beautiful prose. It's to:
1. Extract the insight from messy thoughts
2. Structure it for the platform (hook, tension, payoff)
3. Keep the rough edges — that's the brand

The skill must resist the urge to polish. If the user's edit makes it rougher, that's a signal to calibrate further toward raw.

---

## AI-Smell Detector

Flag drafts that trigger these patterns:

### Structural Tells
- Perfect three-part framework with alliteration
- Numbered list where every item starts with a verb
- "Here's what I learned:" followed by exactly 5 bullet points
- Intro paragraph → 3 points → conclusion → CTA (too neat)
- Every sentence roughly the same length

### Language Tells
- Em dashes used more than once
- "Here's the thing:" / "Let me break it down:" / "The truth is:"
- "In today's [adjective] world..."
- "It's not about X. It's about Y." (parallelism tell)
- "I used to think X. Then I realized Y." (too clean a transformation arc)
- Perfect grammar in every sentence (real people make minor errors)
- Abstract nouns: "innovation", "transformation", "disruption", "journey"
- "Leverage", "synergy", "ecosystem", "paradigm"

### Structural Anti-Patterns
- Opening with a dictionary definition
- Closing with an inspirational quote
- "What do you think? Drop a comment below!"
- "If this resonated, please share"
- Tagging 10 people at the end

### The Fix
When AI-smell is detected, suggest:
- Break the symmetry — make one point longer than others
- Add a tangent or aside ("btw this reminds me of...")
- Remove the conclusion — just stop after the insight
- Add a specific detail that only you would know
- Lower the polish — contractions, fragments, lowercase

---

## Content Category Balance

Track and balance these categories across posts:

| Category | Description | Ideal Frequency |
|----------|-------------|-----------------|
| Technical | Architecture, code, tooling decisions | 25-30% |
| Product | Customer insights, feature decisions, PMF signals | 20-25% |
| Leadership | Hiring, culture, team building, founder journey | 15-20% |
| Industry | Market trends, regulatory changes, competitive landscape | 15-20% |
| Personal | Honest reflections, failures, behind-the-scenes | 10-15% |
| Engagement | Polls, questions, reactions to others | 5-10% |

Alert when a category exceeds 40% or drops below 5% over a 4-week window.

---

## Timeliness Tiers

### NOW (< 6 hours)
- Major industry news or regulatory changes
- Competitor product launches
- Viral conversations in your space
- Breaking tech news relevant to your domain

Action: "This has a short window. Draft ready in 2 minutes, post today."

### THIS WEEK
- Trend reactions, event recaps
- Responses to industry reports
- Follow-ups on trending conversations

Action: "Timely but not urgent. Slot into this week's calendar."

### EVERGREEN
- Frameworks, lessons learned, series content
- Personal stories, founder journey
- Technical deep-dives

Action: "Schedule freely. Use to fill gaps in calendar."

### Auto-Reprioritization
When a timely opportunity appears:
1. Check scheduled evergreen content
2. Bump the least-time-sensitive scheduled post
3. Notify: "I moved your Tuesday post to Thursday. Here's a draft on [breaking topic] instead."

---

## Series Management

### Series Health Checks
- Track engagement per episode vs. series average
- If episode N gets <50% of episode 1's engagement, suggest wrapping early
- Suggest shorter series (3-4 parts) over longer ones (7+)
- Include callbacks to previous episodes for continuity

### Series Pacing
- Max 2 series episodes per week (don't fatigue audience)
- Interleave series posts with standalone posts
- Each episode should work standalone (new followers join mid-series)

---

## Semantic Dedup

Before finalizing any draft, check against published post history:
- Load `~/.claude/skills/social-media-manager/data/post_history.csv`
- Compare core insight/theme of new draft against last 30 published posts
- If >70% thematic overlap: "This is similar to your [date] post about [topic]. Differentiate or skip?"
- Track topic recurrence to suggest new angles on familiar themes

---

## Content Mining Signals

When scanning context store and other sources, look for:

### From Meeting Notes
- Decisions made under pressure
- Customer quotes (anonymized)
- Objections raised and how they were handled
- "Aha moments" — when something clicked

### From Git History
- Significant architectural changes
- Milestone commits
- Bug fixes with interesting root causes
- Refactoring decisions

### From Industry Signals
- Regulatory changes affecting the user's domain
- Competitor moves worth reacting to
- Market trends the user is positioned to comment on

### From Personal Context
- Role transitions, team growth
- Fundraising milestones (if public)
- Conference talks or podcast appearances
- Anniversaries, launch dates
