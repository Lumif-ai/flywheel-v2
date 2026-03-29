# Concept Brief: Flywheel OS — Intelligence Operating System for Founders

> Generated: 2026-03-28
> Mode: Deep (4 rounds)
> Rounds: 4 deliberation rounds + fresh perspective review
> Active Advisors: 14 (10 core + Christensen, Goldratt, Slootman, Ohno)
> Artifacts Ingested: Full codebase context (Phases 1-63), live conversation with founder

## Problem Statement

Founders have conversations all day — calls, meetings, emails — and make commitments in every one. "We'll send a one-pager." "Let me loop in legal." "I'll follow up with pricing." These commitments live in the founder's head, scattered across notes apps, and die in to-do lists that go stale.

The current Flywheel product (v1.0-v3.0) has built the intelligence layer: emails are scored and drafted, meetings are transcribed and processed, context is accumulated, relationships are tracked. But the **action layer** is missing. The system observes conversations but doesn't act on them.

The gap: **no product turns conversation commitments into executed deliverables.** Salesforce tracks that you said you'd send something. Flywheel should send it.

*Sharpened from original framing: User initially described "meetings page redesign" but through deliberation, the real need emerged as a three-layer operating system where meetings are just one input source.*

## Proposed Approach

### Three-Layer Architecture

```
Layer 3: RITUAL        /flywheel command + /brief page
                       Daily operating rhythm — review, confirm, go
                            │
Layer 2: AUTOPILOT     Task detection + auto-execution via skills
                       Detect commitments → confirm → execute → deliver
                            │
Layer 1: INTELLIGENCE  Meetings + Emails + (future: Slack)
                       Ingest → Enrich → Store in context store
```

**Layer 1 (Intelligence)** exists today (Phases 1-63). It ingests from Gmail and Granola, processes transcripts, extracts insights, writes to context store, enriches relationship surfaces.

**Layer 2 (Autopilot)** is new. It watches the intelligence layer's outputs and detects actionable commitments — "send one-pager," "schedule follow-up," "intro to CISO." Each detected task is mapped to a Flywheel skill that can execute it. The founder confirms, the skill runs with auto-assembled context (context store + web research), and the output awaits review.

**Layer 3 (Ritual)** is new. The `/flywheel` CLI command and `/brief` web page are the founder's daily cockpit. One surface showing: upcoming meetings (with prep status), pending tasks (from conversations), unprocessed meetings (need extraction), and outreach quota. The founder runs `/flywheel`, reviews everything, approves in batch, and moves on.

### Key Insight

The flywheel metaphor becomes literal:
- Better prep → more productive meetings → richer transcripts
- Richer transcripts → more detected tasks → more auto-executed deliverables
- Better deliverables → stronger relationships → more meetings
- More meetings → deeper context store → even better prep

Each revolution of the flywheel makes the next one more valuable. The moat is the accumulated context that no competitor can replicate.

## Key Decisions Made

| # | Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|---|----------|-----------------|------------------|-------------------|---------------------|
| 1 | Meeting data model | Unified table with lifecycle status (scheduled → recorded → complete) | "Upcoming meetings should be linked to processed meetings" | Hickey: "caterpillar and butterfly are the same organism" | Separate WorkItem + Meeting tables (current state) |
| 2 | Calendar + Granola dedup | Match by time window (±30min) + attendee email overlap; Granola enriches existing scheduled row | Natural — same meeting shouldn't appear twice | Torvalds: "dead simple matching" | Separate rows with FK link |
| 3 | Auto-prep filter | Auto-prep external meetings with linked accounts only; skip internal | "Feels right" — no waste on standups and 1:1s | Ohno: prepping for internal meetings is pure waste | Prep all meetings; permission-based prep |
| 4 | Unknown contact discovery | Web search for company + LinkedIn, ask user to confirm or fill in; high confidence = default yes, low confidence = prompt | "Edge case — we may not know the company" | Bezos: first-contact moment matters | Skip unknown contacts; require manual entry |
| 5 | Email sending policy | NEVER send email without approval. GTM outreach has its own approval flow within the pipeline. No exceptions. | "This is a must have" | N/A — founder's hard constraint | Auto-send low-risk emails |
| 6 | Context assembly for tasks | Context store + deep web research (gap-aware), cached per account per 24h | "Should also do deep web research, not just context store" | Vogels/Carmack: cache to avoid cost bomb | Context store only; per-task web research (expensive) |
| 7 | Task extraction accuracy | Err toward over-detection (more false positives). Dismissed task costs 1 second, missed commitment costs a deal. | Implicit — confirmed by approving the trust ladder | PG: "70% accuracy on skill detection is transformative" | Conservative detection (fewer false positives) |
| 8 | Outreach in /flywheel | Separate section in daily view, not mixed into task list. Daily quota/habit, not a detected task. | "I want to reach out to 30 people everyday without fail" | Helmer: outreach is proactive, tasks are reactive — different mental models | Mixed into task queue; separate product |
| 9 | /brief vs /tasks pages | Keep separate — /brief is ephemeral (today's snapshot), /tasks persist | "Keep separate" | Ive: separate concerns; Rams: argued for merge (overruled) | Merge into one page |
| 10 | Slack extraction | Both DMs and channels, but deferred to later phase | "We can hold onto it for now" | Slootman: scope discipline | Build now; never build |
| 11 | Email vs meeting extraction | Same prompt template, different confidence calibration. Email = higher confidence (written). Meeting = lower (verbal). Same tasks table. | Makes sense — ship meeting first, email follows same pattern | Board consensus | Separate extraction systems |
| 12 | Granola sync frequency | On-demand for now, added to /flywheel ritual | "Can keep it on demand for now" | Carmack: simple first | Polling/webhooks |

## Advisory Analysis

### Theme 1: Product Identity — Operating System, Not Feature

The strongest advisory signal: this is not a "meetings redesign" or a "task tracker." It's a **founder's daily operating system** that happens to use meetings, emails, and conversations as input. The three-layer framing (Intelligence → Autopilot → Ritual) emerged from Bezos working backward ("the founder thinks 'what do I need to be ready for today?'") and Chesky's 11-star version (system auto-executes commitments). The `/flywheel` command is the product — everything else is plumbing.

### Theme 2: The Moat Is Accumulated Context

Helmer's 7 Powers analysis identified **cornered resource** as the achievable power. The context store accumulates intelligence from every conversation, every email, every meeting. After 6 months of use, the auto-generated one-pagers are better, the prep briefings are richer, the task context is deeper. No competitor can replicate this without the same 6 months of conversations. PG validated demand: "No CRM does this. Salesforce tracks that you SAID you'd send something. This SENDS it. That's a category difference."

### Theme 3: Waste Elimination Is the Value Proposition

Ohno's 7 wastes analysis quantified the current founder workflow: 7 steps and 5 context switches to follow up after a single call (close Granola → open notes → write to-do → open CRM → update deal → open email → draft follow-up). The Flywheel OS workflow: 2 steps, 0 context switches (run `/flywheel` → review and approve). That's a 70% reduction in post-meeting overhead. The value prop isn't "better meetings" — it's "your conversations automatically become executed deliverables."

### Theme 4: Scope Discipline

Slootman challenged the scope repeatedly: "You're describing 9 features." The resolution was phased execution (A through H) with clear dependencies. Each phase ships standalone value. The full vision requires all layers, but a founder gets value from Phase A (unified meetings) on day one. Carmack reinforced: "Start simple. A tasks table with source, context, suggested_skill, status. Don't over-engineer."

### Theme 5: Trust and Safety

The trust ladder emerged from Bezos ("there's a middle ground between auto-execute and ask permission") refined by the founder's hard constraint on email sending. Five levels ensure the system never oversteps:

| Level | Action | UX |
|-------|--------|-----|
| **Silent** | Context updates, meeting dedup, enrichment | No notification |
| **Inform** | Prep generated, task detected, intel extracted | Shown in /flywheel |
| **Review** | Draft created, research complete | "Review → approve / edit / dismiss" |
| **Confirm** | Send email, create account | "Run this? y/n" |
| **Never auto** | GTM outreach batch, destructive ops | User initiates explicitly |

## Tensions Surfaced

### Tension 1: Scope Ambition vs Shipping Speed
- **Chesky** argues: The vision must be complete to be compelling. A half-built intelligence OS is worse than no system.
- **Slootman** argues: 9 features at once is a recipe for shipping nothing. Each phase must deliver standalone value.
- **Why both are right:** The complete vision is the product story. The phased execution is the engineering reality.
- **User's resolution:** Phased execution order (A through H), each phase ships independently.
- **User's reasoning:** Implicit — approved the phased plan without pushback.

### Tension 2: Extraction Accuracy vs User Annoyance
- **PG** argues: "Can the LLM reliably detect commitments and map them to skills?" False positives waste founder time.
- **Goldratt** argues: A missed commitment costs a deal. Over-detection is far cheaper than under-detection.
- **Why both are right:** Too many false positives → founder ignores the system. Too few → commitments slip.
- **User's resolution:** Over-detect, let user dismiss cheaply.
- **User's reasoning:** Dismissing a false positive costs 1 second. Missing "send the one-pager" costs a deal.

### Unresolved Tensions
- None — all tensions resolved during deliberation.

## Data Models

### Unified Meetings Table (Evolution of Current)

```
meetings table:
  ── Identity ──
  id, tenant_id, user_id

  ── Source tracking ──
  calendar_event_id    -- from Google Calendar (gcal:{event_id})
  granola_note_id      -- from Granola (note ID)
  provider             -- "google-calendar" | "granola" | "manual"

  ── Core data ──
  title, meeting_date, duration_mins
  attendees            -- JSONB [{email, name, is_external}]
  location, description  -- from calendar

  ── Lifecycle ──
  status: "scheduled" | "recorded" | "processing" | "complete" | "skipped"

  ── Enrichment (populated after processing) ──
  transcript_url, ai_summary, summary (JSONB)
  meeting_type, account_id, skill_run_id, processed_at

  ── Prep ──
  prep_status: null | "queued" | "ready"
  prep_run_id          -- links to SkillRun for prep briefing
```

**Lifecycle flow:**
- Google Calendar sync → creates row with `status=scheduled`
- Granola sync → matches existing scheduled row (dedup) → enriches with transcript → `status=recorded`
- Intelligence pipeline → processes → `status=complete`
- Unmatched calendar events past their date → auto-archived

**Dedup logic:**
1. Granola note has calendar_event metadata → exact match on calendar_event_id
2. Time window (±30min) + >=1 attendee email overlap → fuzzy match
3. No match → Granola creates new row (recording-only meeting)

### Tasks Table (New)

```
tasks table:
  ── Identity ──
  id, tenant_id, user_id

  ── Source ──
  source: "meeting" | "email" | "slack" | "manual" | "system"
  source_id: UUID          -- meeting_id, email_id, etc.
  account_id: UUID         -- linked account (if detected)

  ── Task ──
  title: text              -- "Send security one-pager to Acme"
  description: text        -- fuller context from transcript
  task_type: text          -- "collateral" | "follow-up" | "intro" | "research" | "outreach" | "custom"

  ── Automation ──
  suggested_skill: text    -- "sales-collateral" | "email-draft" | null
  skill_context: JSONB     -- {account_id, product, vertical, angle, ...}
  trust_level: text        -- "silent" | "inform" | "review" | "confirm" | "never_auto"

  ── Lifecycle ──
  status: "detected" | "confirmed" | "queued" | "in_progress" | "review" | "complete" | "dismissed"
  priority: 1-5
  due_date: timestamp

  ── Output ──
  skill_run_id: UUID       -- links to SkillRun that executed
  output_type: text        -- "document" | "email_draft" | "briefing" | null
  output_ref: text         -- file path, draft ID, URL

  ── Timestamps ──
  created_at, updated_at, completed_at
```

**Task commitment classification (from transcripts):**

| Category | Example | Action |
|----------|---------|--------|
| Your commitment | "We'll send the one-pager" | Task for you, skill suggested |
| Their commitment | "I'll send the requirements" | Track as "owed to you" (commitments tab) |
| Mutual next step | "Let's schedule a follow-up" | Task for you, type: scheduling |
| Soft signal | "Would be great to see a demo" | Signal, not task — feeds relationship intel |
| Idle speculation | "We should grab coffee" | Ignore |

### Context Assembly Cache (New)

```
context_bundles table:
  id, tenant_id, account_id
  bundle: JSONB            -- assembled context (store + web research)
  researched_at: timestamp -- cache expiry (24h TTL)
  sources: JSONB           -- what was included {context_files: [...], web_searches: [...]}
```

Assembled once per account per 24h. All skills for that account reuse the same bundle. Cuts web research API costs by ~60-70%.

## The /flywheel CLI Command

### Design

```
$ /flywheel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FLYWHEEL BRIEF — Friday, March 28
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

UPCOMING (3 meetings today)
  ✓ 10:00am  Acme Corp — Sarah Chen (VP Eng)
    Briefing ready · 3 pain points, 2 open action items
  ⚡ 2:00pm  NewDomain — mike@newdomain.io
    Unknown contact · Found: Mike Torres, CTO @ NewDomain Inc
    → Correct? (y) / Edit (n) / Skip (s)
  ○ 4:00pm  Team standup
    Internal · Skipped

PENDING TASKS (5 from conversations)
  1. Send security one-pager to Acme
     Source: yesterday's call · Skill: sales-collateral · (run / edit / dismiss)
  2. Intro Sarah Chen to your CISO
     Source: yesterday's call · Skill: email-draft · (run / dismiss)
  3. Follow up with Beta Corp re: pricing
     Source: email thread · Skill: email-draft · (run / dismiss)
  4. Research Competitor X positioning
     Source: Acme call · Skill: account-research · (run / dismiss)
  5. Schedule demo with NewCo
     Source: email · Manual · (mark done / snooze)

UNPROCESSED (2 meetings from yesterday)
  Acme Corp call — 45min, transcript ready
  Beta Corp intro — 20min, transcript ready
  → Process all? (y/n)

OUTREACH (daily target: 30)
  12/30 contacted today · 18 remaining
  → Run pipeline for next batch? (y/n)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 (a) Run all with smart defaults
 (r) Refresh
 (q) Quit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Subcommands

| Command | What It Does |
|---------|-------------|
| `/flywheel` | Full daily brief (all sections) |
| `/flywheel prep` | Upcoming meetings only — prep briefings |
| `/flywheel tasks` | Pending tasks only — review and execute |
| `/flywheel process` | Unprocessed meetings only — run intelligence pipeline |
| `/flywheel outreach` | Outreach quota only — run GTM pipeline |
| `/flywheel sync` | Pull latest from Granola + process pending |

### Web App: /brief Page

The `/brief` web page mirrors the CLI output as a visual dashboard — the founder's landing page when they open Flywheel in the browser. Same four sections (Upcoming, Tasks, Unprocessed, Outreach), interactive cards instead of CLI text, same actions (run/dismiss/confirm). Always shows today's state, refreshes on page load.

### Web App: /tasks Page

Persistent task management view:
- **To Do** — detected + confirmed tasks, not yet executed
- **In Review** — skill has run, output awaiting founder approval
- **Done** — completed tasks with output links (one-pager PDF, sent email, etc.)
- **Dismissed** — tasks the founder skipped (recoverable)
- Manual "Add task" button for ad-hoc to-dos

### Web App: /meetings Page (Redesigned)

Unified meeting timeline replacing current Granola-only view:
- **Upcoming tab** — from Google Calendar, with prep status indicators, prep buttons
- **Past tab** — processed meetings with intelligence, status badges
- Unified data source (single meetings table, lifecycle status)

## Auto-Execution Chain (Example)

```
Call with Acme ends
        │
        ▼
Granola sync (via /flywheel sync or on-demand)
        │
        ▼
Dedup: matches to 10am calendar event → status: "recorded"
        │
        ▼
Intelligence pipeline extracts from transcript:
  ├── Pain point: "SOC2 compliance is blocking their procurement"
  ├── Competitor: "Also evaluating Vendor X"
  ├── Your commitment: "We'll send a security one-pager by Friday"
  ├── Their commitment: "Sarah will send requirements doc"
  └── Next step: "Follow-up call next week"
        │
        ▼
Task auto-detection:
  ├── Task 1: "Send security one-pager"
  │   ├── skill: sales-collateral
  │   ├── context: {account: Acme, vertical: FinTech, angle: security/SOC2}
  │   ├── trust_level: review (generates draft, doesn't send)
  │   └── status: detected → (user confirms) → queued
  │
  ├── Task 2: "Follow-up call next week"
  │   ├── skill: null (manual scheduling)
  │   ├── trust_level: inform
  │   └── status: detected
  │
  └── Commitment tracked: "Sarah will send requirements doc"
      └── Added to Acme's commitments tab (What They Owe)
        │
        ▼
User runs /flywheel:
  "Send security one-pager to Acme" → (run)
        │
        ▼
Context assembly (cached per account per 24h):
  ├── Context store: Acme profile, pain points, competitor intel, contacts
  ├── Web research (gap-aware): recent Acme news, SOC2 market trends
  └── Cached bundle ready
        │
        ▼
sales-collateral skill executes with pre-assembled context:
  Output: security-one-pager-acme.pdf
  Status: "review"
        │
        ▼
Next /flywheel run:
  "Security one-pager for Acme ready — view / send via email / edit"
        │
        ▼
User approves → email-draft skill creates send-ready email
  → User confirms send (NEVER auto-sent) → delivered
```

## Moat Assessment

**Achievable power(s):** Cornered Resource (accumulated context store)
**Moat status:** Emerging → Strong (deepens with every conversation)

The context store is the moat. After 6 months:
- Prep briefings draw from 50+ processed meetings per account
- One-pagers include real pain points from real conversations (not generic)
- Task context assembly is richer (knows which products matter to which accounts)
- Commitment tracking catches patterns ("they always delay on legal review")

No competitor can replicate this without the same 6 months of conversations. Switching cost is the accumulated intelligence — not the software.

## Phased Execution Plan

| Phase | What Ships | Dependencies | Standalone Value |
|-------|-----------|-------------|-----------------|
| **A** | Unified meetings table + calendar→meetings migration + dedup | None | See all meetings (calendar + Granola) in one view |
| **B** | Tasks data model + meeting transcript task extraction | A (needs processed meetings) | Commitments auto-detected from calls |
| **C** | `/flywheel` CLI with upcoming + tasks + unprocessed + sync | A + B | Daily operating rhythm |
| **D** | Contact discovery (web research + user confirmation in CLI) | C (part of /flywheel flow) | Prep for meetings with unknown contacts |
| **E** | Auto-skill execution (sales-collateral, email-draft, etc.) | B + context assembly cache | Detected tasks auto-generate deliverables |
| **F** | Email task extraction | B (same tasks table, different source) | Commitments from emails feed same pipeline |
| **G** | GTM outreach integration in /flywheel | C (outreach section in CLI) | Daily outreach quota as part of ritual |
| **H** | Web UI (/brief page, /tasks page, /meetings redesign) | A + B + C (all backends) | Visual surface for the full system |

**Later phases (deferred):**
- Slack extraction (DMs + channels → tasks)
- Mobile/push notifications
- Multi-user task assignment
- Granola webhook polling (replace on-demand sync)

## Open Questions

- [ ] **Granola calendar_event metadata** — Does Granola's API return the Google Calendar event ID in its response? This determines whether dedup can use exact matching or must fall back to fuzzy time+attendee matching. Needs API investigation.
- [ ] **Task extraction prompt engineering** — The commitment classification (your commitment vs their commitment vs idle speculation) needs prompt iteration. Plan for 2-3 rounds of tuning with real transcripts.
- [ ] **Context assembly cache invalidation** — 24h TTL is a starting point. Should a new meeting with an account invalidate the cache immediately? Or is staleness acceptable for non-prep tasks?
- [ ] **Offline-first for mobile** — If mobile surfaces are built later, does the tasks table need offline sync support? Deferred but worth noting for schema design.
- [ ] **Multi-tenant task visibility** — Are tasks user-private (Zone 1) or team-visible (Zone 2)? The trust ladder implies user-private, but team leads may want visibility into team commitments.

## Recommendation

**Proceed to spec.** The vision is clear, the phasing is sound, and the moat is real. Start with a spec for Phases A-C (unified meetings + tasks + /flywheel CLI) as a single milestone. This delivers the core loop: meetings flow in → tasks get detected → founder reviews and acts. Phases D-H extend the system but A-C is the minimum viable operating system.

Recommended next step: `/spec` with this concept brief as input.

## Artifacts Referenced

- Flywheel v2 codebase (Phases 1-63, all complete)
- Live founder conversation (4 rounds of deliberation)
- Existing data models: WorkItem, Meeting, ContextEntry, SkillRun, Account, AccountContact
- Existing skills: sales-collateral, email-draft, account-research, meeting-prep, gtm-outbound-messenger
- Backend services: calendar_sync.py, google_calendar.py, granola_adapter.py, skill_executor.py, meeting_processor_web.py
