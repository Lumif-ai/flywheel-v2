# Concept Brief: Email-to-Tasks — Extract Commitments from Emails

> Generated: 2026-03-29
> Mode: Deep (3 rounds)
> Rounds: 3 deliberation rounds
> Active Advisors: 13 (10 core + Christensen, DJ Patil, Slootman)
> Artifacts Ingested: Full codebase (email_scorer.py, flywheel_ritual.py, meeting_processor_web.py, Task model), CONCEPT-BRIEF-flywheel-os.md

## Problem Statement

The Flywheel OS extracts tasks from meeting transcripts but ignores the other major source of founder commitments: email. A founder replies "I'll send pricing by Thursday" — that commitment exists only in Gmail. The system scores the email (priority 4, `action_required`) but doesn't track the commitment.

The infrastructure is ready: emails are synced, scored with priority/category/suggested_action, and the Task model already supports `source="email"`. The gap is the extraction logic — converting scored email metadata into tracked tasks.

*Sharpened from original framing: User initially considered a full LLM-based body extraction pipeline. Through deliberation, we identified that the email scorer already does the heavy lifting — Layer A (score-metadata conversion) ships value immediately, Layer B (ephemeral body fetch + Haiku extraction) follows later.*

## Proposed Approach

### Two-Layer Architecture (Layer A now, Layer B later)

```
Layer A (this phase):                    Layer B (future phase):
Score metadata → Task                    Ephemeral body fetch → Haiku extraction

EmailScore                               Gmail API (ephemeral)
  ├── category: action_required          ├── Fetch body at extraction time
  ├── priority: 4-5                      ├── Run TASK_EXTRACTION_PROMPT
  ├── suggested_action: draft_reply      ├── Extract commitment_direction,
  └── sender_entity_id                   │   task_type, suggested_skill, due_date
       │                                 ├── Discard body (never persist)
       ▼                                 └── Richer tasks with full context
Task row created:                              │
  source="email"                               ▼
  title=email subject                    Task row created:
  trust_level="review"                     source="email"
  status="detected"                        title=extracted commitment
                                           trust_level varies by type
```

### New Ritual Stage: "Stage 3: Channel Task Extraction"

```
Stage 1: Granola Sync
Stage 2: Process Unprocessed Meetings (includes meeting task extraction)
Stage 3: Channel Task Extraction  ← NEW
  ├── Email → tasks (this phase)
  ├── Slack → tasks (future)
  └── [future channels]
Stage 4: Execute Confirmed Tasks
Stage 5: Compose Daily Brief
```

This stage is channel-agnostic by design. Email is the first channel; Slack and others plug into the same stage.

### Dedup Guard (at creation time)

```
For each candidate email task:
  1. Query open tasks for same account_id
  2. Fuzzy match: title similarity > 0.7 AND created within 48h
  3. If match found:
     ├── Create the task anyway (over-detect principle)
     ├── Set duplicate_of_task_id = matched task ID
     ├── Add "possible duplicate" flag in metadata
     └── UI shows grouped/linked duplicates
  4. If no match: create normally
```

### Volume Control

- **Steady state:** Only emails received since last ritual run
- **First run:** Last 7 days, capped at top 15 by priority
  - Show message: "Found N actionable emails from the last 7 days. Showing top 15."
- **Filter:** `category IN ('action_required', 'meeting_followup')` AND `priority >= 4`
- **Exclude:** Emails already linked to tasks (idempotent re-runs)

### Task Resolution Metadata (schema enhancement)

```
tasks table additions:
  resolved_by: text       -- "user" | "system"
  resolution_source: UUID -- email_id or meeting_id that triggered resolution
  resolution_note: text   -- why (user-provided or system-generated)
  duplicate_of_task_id: UUID  -- links to potential duplicate
```

This enables the commitment ledger: every task carries its full history — who created it, from which channel, how it was resolved, and why.

## Key Decisions Made

| # | Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|---|----------|-----------------|------------------|-------------------|---------------------|
| 1 | Extraction approach | Layer A (score metadata → task) now, Layer B (body extraction) later | "Start minimal" — ship value from existing scoring | Slootman: "Layer A ships in a day. Layer B is a different phase." | Full body extraction pipeline from the start |
| 2 | Email body access | Ephemeral fetch allowed (for Layer B) — fetch at extraction time, extract, discard | "Yes, I am open to it" — privacy-consistent with no persistence | Vogels: ephemeral access preserves PII posture | Snippet-only forever; persist bodies |
| 3 | Ritual placement | New Stage 3 "Channel Task Extraction" — channel-agnostic | "This is not just meeting processing, also involves Slack, emails" — future-proof | Hickey: compose channel extractors into one stage | Embed in Stage 2 (meeting-specific); separate stages per channel |
| 4 | Dedup strategy | Build dedup check now — fuzzy match at creation time, link but don't suppress | "We need to build dedup check now" | Hickey over Carmack: "composable check now prevents trust erosion" | Defer dedup to Layer B; silent suppression |
| 5 | Volume control | Since last ritual + 7-day cap on first run (top 15) | "For 1st time, just run it for last 7 days... need to inform users" | PG: first-run inbox-shock kills trust | Full history scan; no cap |
| 6 | Task history | Full audit trail — resolved_by, resolution_source, resolution_note | "Should be able to view dismissed, resolved tasks with sources, who took action, why" | Rams: the commitment ledger IS the product surface | Status-only tracking (done/dismissed without context) |
| 7 | API key | Uses subsidy key (backend pipeline, not user-initiated) | Confirmed: runs inside ritual, no user API key needed | N/A — architectural clarification | Require user API key |

## Advisory Analysis

### Theme 1: The Signal Already Exists — Don't Rebuild It

The strongest insight: the email scorer already answers "does this email need action?" with category classification and priority scoring. Layer A is not building a new extraction engine — it's converting an existing signal into a tracked object. DJ Patil's "data as product" lens: the scoring pipeline is producing actionable data that's being thrown away. Converting `action_required` + `priority >= 4` into Task rows is the cheapest possible way to close the loop.

### Theme 2: Channel-Agnostic Stage Design

Hickey's composability principle drove the Stage 3 design. Email task extraction is the first channel, but Slack DMs, Slack channels, and future inputs will follow the same pattern: scan channel → detect commitments → create tasks with source attribution. Building a channel-specific stage would require refactoring when Slack arrives. The channel-agnostic stage accepts any extractor that produces `(title, source, source_id, account_id, metadata)` tuples.

### Theme 3: Trust Through Transparency

Christensen's JTBD analysis revealed two jobs: (1) "help me not forget commitments" and (2) "show me my commitment history." The founder's insistence on viewing dismissed/resolved tasks with full attribution confirms job #2 is first-class. The dedup guard (link but don't suppress) and resolution metadata serve both jobs — nothing is hidden, everything is traceable. This builds the trust that PG flagged as the make-or-break factor.

### Theme 4: The Flywheel Tightens

Helmer's moat analysis: this feature closes a second flywheel loop. Currently: meetings → context → prep → better meetings. With email-to-tasks: emails → tasks → action → replies → richer email threads → more context. Every correctly tracked email commitment is another unit of accumulated context that competitors can't replicate. The cost of Layer A is near-zero (no new LLM calls), but the moat contribution is significant.

### Theme 5: First-Run Experience Is the Highest Risk

PG and Slootman converged: the 7-day backlog on first run could produce 30-50 tasks at once. Even capped at 15, that's a wall of items the founder hasn't seen before. The mitigation: clear messaging ("Found N actionable emails from the last 7 days. Showing top 15 by priority. Run another ritual to surface more.") and trust_level="review" on all email-sourced tasks so nothing auto-executes.

## Tensions Surfaced

### Tension 1: Dedup Now vs Dedup Later
- **Carmack** argues: Layer A tasks (from score metadata) look nothing like meeting tasks (from transcripts). Different titles, different descriptions. You don't have a dedup problem yet. Don't build machinery for a problem that doesn't exist.
- **Hickey** argues: A founder says "I'll send the proposal" in a meeting → meeting task. Email arrives with the proposal → scored `action_required` → email task. Same commitment, two tasks. Build the composable check now.
- **Why both are right:** The literal text won't match (meeting title ≠ email subject). But the semantic overlap is real and will erode trust.
- **User's resolution:** Build dedup now.
- **User's reasoning:** "We need to build dedup check now" — trust preservation is worth the upfront cost, even if early matches are imperfect.

### Tension 2: Minimal vs Rich Task Output
- **Slootman** argues: Layer A tasks from subject lines ("Re: Q2 proposal") are low-information. Ship it, learn, iterate.
- **Bezos** argues: A task the founder can't understand at a glance is worse than no task. The subject line alone may not convey the commitment.
- **Resolution:** Layer A tasks include subject + snippet + sender + score reasoning as description. Not as rich as body extraction, but enough context to act on. The scorer's `reasoning` field often contains the "why this matters" that makes the task actionable.

### Unresolved Tensions
- **Layer B timing:** When does ephemeral body extraction become worth the added latency and cost? Deferred until Layer A usage data shows whether subject+snippet+reasoning is sufficient.

## Scope Definition

### In Scope (This Phase)
- New ritual Stage 3: Channel Task Extraction (email channel)
- Email → task conversion from score metadata (Layer A)
- Dedup guard with fuzzy matching and task linking
- Volume control (since-last-ritual + 7-day first-run cap)
- Task resolution metadata (resolved_by, resolution_source, resolution_note, duplicate_of_task_id)
- First-run user messaging

### Out of Scope (Future Phases)
- Layer B: Ephemeral body fetch + Haiku extraction prompt
- Slack channel task extraction
- Auto-resolution of meeting tasks from email signals
- Cross-channel dedup (email task resolves meeting task)
- Push notifications for detected email tasks

## Data Flow

```
Gmail Sync (5-min loop, existing)
        │
        ▼
Email Scoring (existing) → EmailScore row
        │                    category: action_required
        │                    priority: 4
        │                    suggested_action: draft_reply
        │                    reasoning: "Sender asks for pricing..."
        │
        ▼
Flywheel Ritual Stage 3 (NEW)
        │
        ├── Query: emails scored since last ritual run
        │   WHERE category IN ('action_required', 'meeting_followup')
        │   AND priority >= 4
        │   AND NOT already linked to a task
        │
        ├── For each qualifying email:
        │   ├── Build task title from subject (strip Re:/Fwd:)
        │   ├── Build description from snippet + reasoning
        │   ├── Link to account via sender_entity_id
        │   ├── Run dedup check against open tasks
        │   └── Create Task row:
        │       source="email", trust_level="review"
        │       status="detected"
        │
        └── First-run path:
            ├── Detect: no prior ritual run with email extraction
            ├── Lookback: 7 days, cap at top 15 by priority
            └── Message: "Found N actionable emails..."
        │
        ▼
Stage 5: Daily Brief (existing)
        └── Email-sourced tasks appear in PENDING TASKS section
```

## Open Questions

- [ ] **Fuzzy title matching algorithm** — What similarity metric for dedup? Levenshtein on normalized titles? Or keyword overlap? Needs testing with real email subjects vs meeting task titles.
- [ ] **First-run detection** — How to detect "first run with email extraction"? Check for any existing tasks with `source="email"`? Or a metadata flag on the ritual run record?
- [ ] **Score reasoning quality** — Is the scorer's `reasoning` field consistently useful as task description context? Need to audit a sample of real scored emails.
- [ ] **Backfill UX** — The "Found N actionable emails, showing top 15" message — where does it render? In the daily brief HTML? As a Stage 3 output message? Both?
- [ ] **Layer B trigger criteria** — What signal from Layer A usage would indicate it's time to build Layer B? Task dismissal rate > X%? User feedback?

## Recommendation

**Proceed to spec.** The scope is tight (one new ritual stage, one schema migration, dedup guard), the risk is low (no new LLM calls, builds on existing scoring), and the value is clear (closes the email→task loop in the flywheel). Layer A is a natural extension of the existing pipeline — the hardest engineering is already done in the email scorer.

Recommended next step: `/spec` with this concept brief as input. Single-phase implementation targeting the flywheel ritual pipeline.

## Artifacts Referenced

- Flywheel v2 codebase: `email_scorer.py`, `flywheel_ritual.py`, `meeting_processor_web.py`, `models.py` (Task, Email, EmailScore)
- `CONCEPT-BRIEF-flywheel-os.md` — parent concept brief establishing the three-layer architecture
- Email scoring prompt: `SCORE_SYSTEM_PROMPT` in email_scorer.py
- Task extraction prompt: `TASK_EXTRACTION_PROMPT` in meeting_processor_web.py
- Live founder conversation (3 rounds of deliberation)
