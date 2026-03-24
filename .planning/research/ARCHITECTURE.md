# Architecture Research

**Domain:** Email Copilot integration into Flywheel V2
**Researched:** 2026-03-24
**Confidence:** HIGH — direct codebase inspection, no guesswork required

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          GMAIL API (external)                         │
│           gmail.readonly + gmail.modify + gmail.send scopes           │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ poll every 5 min
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│              BACKGROUND WORKERS (asyncio tasks in lifespan)           │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────┐  │
│  │  email_sync_loop   │  │ calendar_sync_loop │  │ job_queue_loop │  │
│  │  (NEW — 5 min)     │  │ (existing — 5 min) │  │ (existing—5s)  │  │
│  └────────┬───────────┘  └────────────────────┘  └───────┬────────┘  │
└───────────┼──────────────────────────────────────────────┼───────────┘
            │ upserts                                       │ dispatches
            ▼                                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL (RLS-isolated per tenant)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │    emails    │  │ email_scores │  │ email_drafts │                │
│  │  (NEW)       │  │  (NEW)       │  │   (NEW)      │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                 │                  │                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  email_voice_profiles (NEW)  │  context_entries (existing)       │ │
│  │  context_entities (existing) │  skill_runs (existing)            │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ reads / writes
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 SKILL EXECUTOR (skill_executor.py — existing)         │
│  ┌────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │   email_scorer skill   │  │       email_drafter skill           │  │
│  │  reads context store   │  │  fetches Gmail body on-demand       │  │
│  │  entity graph lookup   │  │  loads voice profile                │  │
│  │  outputs EmailScore    │  │  outputs EmailDraft                 │  │
│  └────────────────────────┘  └─────────────────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FASTAPI REST LAYER (main.py)                        │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  /api/v1/email/threads   /api/v1/email/drafts/{id}/approve   │     │
│  │  /api/v1/email/drafts/{id}/dismiss  /api/v1/email/voice      │     │
│  └──────────────────────────────────────────────────────────────┘     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  REACT FRONTEND (Vite + Zustand)                       │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  EmailPage (NEW)  — scored thread list + draft review UI       │    │
│  │  ActPage (existing) — receives email alerts as act cards       │    │
│  └───────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `google_gmail.py` | Gmail OAuth, credential management, send | Exists — needs scope expansion |
| `gmail_read.py` | List messages, fetch headers, fetch body on-demand | NEW |
| `email_sync_loop()` | Background 5-min poll, upsert Email rows | NEW (service file) |
| `email_scorer` skill | Score emails via context store, output EmailScore | NEW (skill + SkillDefinition seed) |
| `email_drafter` skill | Draft replies using voice profile + context | NEW (skill + SkillDefinition seed) |
| `email_dispatch.py` | Route send via Gmail/Outlook/Resend | Exists — already handles send path |
| `api/email.py` | REST endpoints for review UI | NEW |
| `EmailPage.tsx` | Review UI — threads, scores, draft approval | NEW |
| `context_entries` table | FTS + entity graph (emails contribute entries here) | Existing — email scorer writes to it |
| `skill_runs` table | Audit trail for all scorer + drafter runs | Existing — reused unchanged |

---

## New vs. Modified Components

### New Files

```
backend/src/flywheel/
├── services/
│   ├── gmail_read.py              # List/fetch Gmail messages (read-only)
│   └── email_sync.py              # email_sync_loop() background worker
├── api/
│   └── email.py                   # REST endpoints for review UI
└── alembic/versions/
    └── 020_email_copilot.py       # Email, EmailScore, EmailDraft, EmailVoiceProfile

frontend/src/
├── pages/
│   └── EmailPage.tsx              # Scored thread list + draft review
├── features/
│   └── email/
│       ├── components/
│       │   ├── ThreadList.tsx     # Priority-grouped thread list
│       │   ├── ThreadCard.tsx     # Per-thread score + actions
│       │   └── DraftReview.tsx    # Approve / edit / dismiss draft
│       └── hooks/
│           └── useEmailThreads.ts # Data fetching hook
└── stores/
    └── email.ts                   # Zustand store for email state

skills/
├── email-scorer/
│   └── SKILL.md                   # Skill definition for DB seed
└── email-drafter/
    └── SKILL.md                   # Skill definition for DB seed
```

### Modified Files

```
backend/src/flywheel/
├── services/google_gmail.py       # Add gmail.readonly + gmail.modify scopes
│                                  # Add separate Integration row for read scope
├── db/models.py                   # Add Email, EmailScore, EmailDraft, EmailVoiceProfile
├── main.py                        # Register email_sync_loop() as asyncio task
│                                  # Include email router
└── config.py                      # No changes needed (google_client_id reused)

frontend/src/
└── app/ or router file            # Add /email route to app routing
```

---

## Architectural Patterns

### Pattern 1: Separate Integration Row for Read Scope

**What:** The existing `google_gmail.py` uses a `gmail` Integration row with only `gmail.send` scope. The read capability requires `gmail.readonly` (and `gmail.modify` for labeling). These must be SEPARATE Integration rows with separate OAuth grants.

**Why it matters:** The existing architecture note in `google_gmail.py` explicitly states: "Gmail and Calendar are SEPARATE Integration rows with SEPARATE credentials. Do NOT merge scopes." Merging read+send into one row would break the existing send flow if the user only wants reading, and would require re-consent from existing users.

**Implementation:**
```python
# google_gmail.py — existing
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
# provider stored as: "gmail"

# gmail_read.py — NEW
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.modify"]
# provider stored as: "gmail-read"
```

**OAuth flow:** New `/integrations/gmail-read/authorize` and `/integrations/gmail-read/callback` endpoints in `api/integrations.py`. The existing Gmail send integration is untouched.

### Pattern 2: Clone calendar_sync_loop() for email_sync_loop()

**What:** The email sync worker follows the exact pattern of `calendar_sync.py`:
- Queries `Integration` table for `provider == "gmail-read"` and `status == "connected"`
- Creates short-lived DB sessions (not persistent connection per integration)
- Uses `asyncio.sleep(SYNC_INTERVAL)` with 300 seconds (5 min)
- Marks integration `disconnected` on `TokenRevokedException`
- Stores `last_synced_at` and sync watermark in `integration.settings`

**The sync watermark:** Gmail uses `historyId` for incremental sync (similar to Calendar's `sync_token`). Store `{"history_id": "...", "initial_sync_done": true}` in `integration.settings`. On first run, use `messages.list` with `q="-label:sent"` and date range; on subsequent runs, use `history.list` for delta.

**Implementation sketch:**
```python
# services/email_sync.py
SYNC_INTERVAL = 300

async def email_sync_loop() -> None:
    while True:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Integration).where(
                    and_(
                        Integration.provider == "gmail-read",
                        Integration.status == "connected",
                    )
                )
            )
            for integration in result.scalars().all():
                try:
                    await sync_inbox(session, integration)
                except TokenRevokedException:
                    integration.status = "disconnected"
                    await session.commit()
                except Exception:
                    logger.exception("Error syncing integration %s", integration.id)
        await asyncio.sleep(SYNC_INTERVAL)
```

### Pattern 3: Skill-as-Worker via job_queue

**What:** The email scorer and email drafter run as `SkillRun` jobs dispatched through the existing `job_queue_loop`. The sync worker creates `SkillRun` rows with `skill_name="email-scorer"`, one per new email batch. The job queue worker picks these up and routes through `skill_executor.py`.

**Why this pattern:** The skill executor already handles the async Anthropic tool_use loop, token budgeting, cost tracking, circuit breaking, and event streaming. There is no reason to build a separate execution path for email skills.

**Data passed to skill:** The `SkillRun.input_text` field carries a JSON payload:
```python
{
    "email_ids": ["uuid1", "uuid2", ...],   # batch of Email IDs to score
    "tenant_id": "...",
    "user_id": "..."
}
```

The email scorer skill reads `Email` rows via its own context tool (or direct DB read via a new `email_tool`), then writes `EmailScore` rows.

### Pattern 4: On-Demand Body Fetch (No Body Storage)

**What:** The email drafter does NOT receive the email body from the sync worker. The body is fetched from the Gmail API only when drafting is needed (priority >= 3 and action == "draft_reply").

**Why:** Privacy minimization decision from the concept brief. Raw email bodies are PII-dense and ephemeral. The intelligence (scoring) is derived from metadata + snippet + context store cross-reference. The body is only needed for drafting.

**Implementation:**
```python
# Inside email_drafter skill execution
async def fetch_body_for_draft(
    integration,        # the gmail-read Integration row
    gmail_message_id: str,
) -> str:
    # calls gmail_read.get_message_body(integration, gmail_message_id)
    # returns plain text extracted from MIME parts
    pass
```

**Failure handling:** If Gmail API is unavailable during drafting, the `EmailDraft` row is created with `status="pending"` and `error="body_fetch_failed"`. The system shows the score and extracted summary; the draft surfaces when body becomes available on retry.

### Pattern 5: Thread Grouping as View, Not Storage

**What:** Email rows are stored at the message level (one row per Gmail message). Thread grouping happens in the API query layer, not in the database.

**Why:** The concept brief decision was "score at message level, display at thread level (highest score wins)." Storing threads as entities would require updating a parent record on every new message and add write complexity. The query is simple:

```sql
SELECT DISTINCT ON (gmail_thread_id)
    e.gmail_thread_id,
    e.subject,
    e.sender_email,
    MAX(es.priority) as thread_priority,
    MAX(e.received_at) as last_received_at
FROM emails e
LEFT JOIN email_scores es ON es.email_id = e.id
WHERE e.tenant_id = $1
GROUP BY e.gmail_thread_id, e.subject, e.sender_email
ORDER BY thread_priority DESC, last_received_at DESC;
```

### Pattern 6: Voice Profile as JSONB, Not Structured Columns

**What:** `EmailVoiceProfile` stores learned patterns in JSONB rather than separate columns for each phrase type.

**Why:** Voice patterns are open-ended. Phrases, greetings, sign-offs, and style signals are heterogeneous. JSONB allows the drafter skill to update the profile structure as patterns evolve without migrations.

**Schema:**
```python
class EmailVoiceProfile(Base):
    __tablename__ = "email_voice_profiles"
    id: UUID
    tenant_id: UUID
    user_id: UUID  # unique per user
    profile: dict  # JSONB: {tone, avg_length, sign_off, phrases[], samples_analyzed}
    updated_at: datetime
```

---

## Data Flow

### Flow 1: Inbox Sync to Score

```
email_sync_loop (every 5 min)
    → gmail_read.list_messages(integration, since=last_history_id)
    → for each new message:
        → upsert Email row (message_id, thread_id, sender, subject, snippet, labels)
    → create SkillRun(skill_name="email-scorer", input={"email_ids": [...]})
    → commit
    ↓
job_queue_loop picks up SkillRun
    → skill_executor.execute_run(run)
    → email_scorer system prompt executes with tool_use loop
    → context_tools.handle_context_read("contacts") → sender entity lookup
    → context_tools.handle_context_search(sender domain / topics)
    → for each email: outputs EmailScore (priority, category, action, reasoning)
    → if action == "draft_reply":
        → creates SkillRun(skill_name="email-drafter", input={"email_id": ...})
    → writes context_entries for high-signal emails (meeting followup, deal-related)
    → SkillRun.status = "completed"
```

### Flow 2: Drafting

```
job_queue_loop picks up email-drafter SkillRun
    → skill_executor.execute_run(run)
    → email_drafter skill fetches:
        1. EmailScore (context: category, reasoning, context_refs)
        2. EmailVoiceProfile (learned tone, sign_off, phrases)
        3. Gmail body on-demand via gmail_read.get_message_body()
        4. Relevant context entries via context_tools
    → LLM generates draft reply
    → writes EmailDraft(status="pending", visible_after=now+delay_days)
    → SkillRun.status = "completed"
```

### Flow 3: Review and Send

```
User opens EmailPage
    → GET /api/v1/email/threads
    → returns scored threads (visible drafts surfaced)
    ↓
User approves draft
    → POST /api/v1/email/drafts/{id}/approve
    → EmailDraft.status = "approved"
    → email_dispatch.send_email_as_user(db, tenant_id, to=sender, body=draft_body)
    → EmailDraft.status = "sent"
    → Email.is_replied = True
    ↓
Voice learning (on approval + edit)
    → if user edited: store diff in EmailDraft.user_edits
    → background job updates EmailVoiceProfile from approved/edited drafts
```

### Flow 4: Context Entry Generation from Emails

```
email_scorer encounters high-signal email (meeting followup, deal update, action item)
    → storage.append_entry(session, ContextEntry(
        file_name="meeting-intel" | "company-intel" | "contacts",
        source=f"email:{gmail_message_id}",
        content=extracted_intelligence,
        detail=sender_name,
      ))
    → entity_extraction.process_entry_for_graph() runs automatically
    → context_entities updated (sender linked to entity)
```

This is the flywheel: emails feed context, context improves scoring, better scoring produces better drafts, users approve more drafts.

---

## Integration Points with Existing Code

### Points That Require Zero Changes

| Existing Component | How Email Uses It | Confidence |
|-------------------|-------------------|------------|
| `auth/encryption.py` | `gmail_read.py` reuses `encrypt_api_key` / `decrypt_api_key` for credential storage | HIGH |
| `db/models.Integration` | New `gmail-read` integration stored as another Integration row, same schema | HIGH |
| `services/email_dispatch.py` | `send_email_as_user()` already handles Gmail send — approval flow calls this directly | HIGH |
| `services/skill_executor.py` | Email scorer/drafter are standard skills, no executor changes needed | HIGH |
| `services/job_queue.py` | `SkillRun` rows created by sync worker, picked up by existing queue | HIGH |
| `tools/context_tools.py` | Scorer uses existing `handle_context_read`, `handle_context_search` tools | HIGH |
| `tools/registry.py` | Skills registered via `SkillDefinition` seed, no registry code changes | HIGH |
| `api/deps.py` | `get_tenant_db`, `require_tenant` used unchanged in new `api/email.py` | HIGH |
| `db/session.py` | `get_session_factory`, `get_tenant_session` reused unchanged | HIGH |
| `services/entity_extraction.py` | Called automatically from `storage.append_entry()` — email entries auto-extract entities | HIGH |

### Points That Require Modification

| Existing Component | Change Required | Risk |
|-------------------|----------------|------|
| `services/google_gmail.py` | Add new `_create_oauth_flow_read()` with expanded scopes. Do NOT modify existing `SCOPES` — this breaks send for existing users. Add as parallel function. | LOW |
| `api/integrations.py` | Add `/gmail-read/authorize` and `/gmail-read/callback` endpoints. Map `provider="gmail-read"` in `_PROVIDER_DISPLAY`. | LOW |
| `db/models.py` | Add 4 new model classes (Email, EmailScore, EmailDraft, EmailVoiceProfile). No changes to existing models. | LOW |
| `main.py` | Add `email_sync_task = asyncio.create_task(email_sync_loop())` in lifespan startup. Include email router. | LOW |
| `config.py` | Add `draft_visibility_delay_days: int = 3` setting. No other config changes. | LOW |

### The Gmail Scope Decision

The existing `google_gmail.py` has a hard-coded comment: "Send-only scope — NOT gmail.modify or full access." This was an intentional security constraint. The read scope must be a **separate OAuth grant** stored as a separate `Integration` row with `provider="gmail-read"`.

This means the integration settings page shows two Gmail entries:
- "Gmail (Send)" — existing, unchanged
- "Gmail (Inbox)" — new, requires separate authorization

This is architecturally cleaner than merging scopes: users who want email sending without the read/copilot feature don't need to re-consent, and the expanded scope is opt-in.

---

## Recommended File Structure (New Files Only)

```
backend/src/flywheel/
├── services/
│   ├── gmail_read.py              # Gmail list/fetch (read-only operations)
│   │                              # list_messages(integration, since_history_id)
│   │                              # get_message_body(integration, message_id) -> str
│   │                              # get_sent_messages(integration, limit=200) -> list
│   └── email_sync.py              # email_sync_loop() + sync_inbox() + upsert_email()
│                                  # voice_profile_init() for initial 100-sent extraction
├── api/
│   └── email.py                   # GET /email/threads
│                                  # GET /email/threads/{thread_id}
│                                  # POST /email/drafts/{id}/approve
│                                  # POST /email/drafts/{id}/dismiss
│                                  # POST /email/drafts/{id}/edit
│                                  # GET /email/voice-profile
└── alembic/versions/
    └── 020_email_copilot.py       # emails, email_scores, email_drafts,
                                   # email_voice_profiles tables + RLS policies

frontend/src/
├── pages/
│   └── EmailPage.tsx              # Main email copilot page
├── features/
│   └── email/
│       ├── components/
│       │   ├── ThreadList.tsx
│       │   ├── ThreadCard.tsx     # Score badge, preview, action buttons
│       │   └── DraftReview.tsx    # Draft text + approve/edit/dismiss
│       └── hooks/
│           └── useEmailThreads.ts
└── stores/
    └── email.ts                   # Zustand store

skills/
├── email-scorer/
│   └── SKILL.md                   # System prompt + contract for seed
└── email-drafter/
    └── SKILL.md                   # System prompt + voice profile injection
```

---

## Build Order (Dependency-Aware)

The dependency chain enforces a specific build order. Each phase is unblockable only after its predecessors.

### Step 1: Data Layer Foundation (unblocks everything)
- `alembic/versions/020_email_copilot.py` — create all 4 tables
- `db/models.py` — add Email, EmailScore, EmailDraft, EmailVoiceProfile models
- RLS policies for all new tables (follow `002_enable_rls_policies.py` pattern)

**Why first:** All backend services and skills depend on these models. Nothing can be built or tested without them.

### Step 2: Gmail Read Service (unblocks sync + drafter)
- `services/gmail_read.py` — list_messages, get_message_body, get_sent_messages
- `services/google_gmail.py` — add `_create_oauth_flow_read()` with expanded scopes
- `api/integrations.py` — add `gmail-read` OAuth endpoints
- `config.py` — add `draft_visibility_delay_days`

**Why second:** The sync worker, drafter skill, and voice profile init all depend on the Gmail read service. The OAuth endpoints must exist before users can connect the integration.

### Step 3: Email Sync Worker (unblocks scorer)
- `services/email_sync.py` — `email_sync_loop()`, `sync_inbox()`, `upsert_email()`
- `main.py` — register `email_sync_loop()` as asyncio task

**Why third:** The scorer needs Email rows to exist. The sync worker creates them. Voice profile init also runs here (pull 100 sent emails on first connect).

### Step 4: Email Scorer Skill (unblocks drafter + frontend)
- `skills/email-scorer/SKILL.md` — system prompt defining scoring logic
- Seed `SkillDefinition` row for `email-scorer`
- Post-sync: sync worker creates `SkillRun(skill_name="email-scorer")` rows

**Why fourth:** The scorer produces EmailScore rows. The drafter depends on scores to decide which emails need drafts. The frontend needs scores to display the thread list.

### Step 5: Email Drafter Skill
- `skills/email-drafter/SKILL.md` — system prompt with voice profile injection
- Seed `SkillDefinition` row for `email-drafter`
- Voice profile loading in skill input context

**Why fifth:** Depends on EmailScore existing. Voice profile must be populated (from Step 3 init) for useful drafts.

### Step 6: Review API Endpoints
- `api/email.py` — all REST endpoints
- `main.py` — include email router

**Why sixth:** Depends on Email, EmailScore, EmailDraft rows existing (from steps 3-5).

### Step 7: Frontend Review UI
- `EmailPage.tsx`, `ThreadList.tsx`, `ThreadCard.tsx`, `DraftReview.tsx`
- `stores/email.ts`, `hooks/useEmailThreads.ts`
- Router update for `/email` route

**Why last:** Depends on REST API being complete.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-50 users | Current approach is fine. Single `email_sync_loop` asyncio task handles all users sequentially in one loop iteration. At 5-min interval and <1 sec/user sync, 50 users = ~50 sec per cycle, well within budget. |
| 50-500 users | Loop iteration may take >5 min. Add worker count (run 2-3 asyncio tasks with user shard split), or batch users with pagination. Per-integration error isolation already exists. |
| 500+ users | Consider Gmail Pub/Sub push notifications (replace polling). Separate the scorer into a dedicated worker process. Partition skill_runs by type to avoid scorer/drafter jobs competing with interactive skill runs. |

### First Bottleneck

The Anthropic API (claude-sonnet-4-6) will be the first constraint, not DB or Gmail API. Scoring 50 emails per user per sync cycle at batched API calls will exhaust token budgets quickly. Mitigation: batch emails by token budget per SkillRun, limit scoring to unscored emails only (idempotency on Email.id), and set a per-tenant daily scoring cap.

---

## Anti-Patterns

### Anti-Pattern 1: Merging gmail.send and gmail.readonly into One Scope

**What people do:** Add `gmail.readonly` to the existing `SCOPES` list in `google_gmail.py`.

**Why it's wrong:** Existing users have already granted only `gmail.send`. Expanding the scope requires re-consent (Google returns "insufficient permissions" on the next token refresh). Worse, it bundles the high-trust action (sending) with the expanded-access scope (reading inbox), making it harder for privacy-sensitive users to use send-only.

**Do this instead:** Create a separate `gmail_read.py` service with its own `SCOPES = [gmail.readonly, gmail.modify]` and store as `provider="gmail-read"` Integration row.

### Anti-Pattern 2: Storing Raw Email Bodies

**What people do:** Add a `body_text` column to the `emails` table and populate it during sync.

**Why it's wrong:** Creates a permanent PII archive (names, financial details, personal conversations). Violates the privacy minimization principle established in the concept brief. Creates GDPR/CCPA liability. The value is in extracted intelligence, not raw storage.

**Do this instead:** Store only the Gmail `snippet` (Google's pre-truncated 200-char preview) in the `emails` table. Fetch the full body on-demand from Gmail API only when drafting. Discard immediately after draft generation.

### Anti-Pattern 3: Scoring Per Email in Separate API Calls

**What people do:** After sync, trigger one `SkillRun` per email (N emails = N runs).

**Why it's wrong:** N separate LLM calls at full token overhead per email. Scoring benefits from cross-email context ("3 emails from this sender this week = escalating urgency"). Context tools can be loaded once for a batch.

**Do this instead:** Batch emails in one SkillRun (e.g., 20 emails per run). Pass all email metadata together. The LLM scores all 20 in one response, can reason about patterns across the batch.

### Anti-Pattern 4: Blocking the Sync Worker on Skill Execution

**What people do:** Call `execute_run(skill_run)` directly inside `email_sync_loop()` (synchronously awaiting LLM response before syncing the next integration).

**Why it's wrong:** One slow Anthropic API call (5-15 seconds) blocks all other integrations in the loop. Gmail sync should be <1 second per user; scoring should be async.

**Do this instead:** `email_sync_loop()` only creates `SkillRun` rows (fast DB insert). `job_queue_loop()` picks them up independently. The two workers are fully decoupled.

### Anti-Pattern 5: Thread as First-Class DB Entity

**What people do:** Create an `email_threads` table with a one-to-many relationship to `emails`.

**Why it's wrong:** Thread metadata (latest sender, combined labels, highest priority) is derived. Maintaining a denormalized thread row requires transactional updates on every new message in the thread and creates write contention.

**Do this instead:** Store at message level. Compute thread view at query time with a GROUP BY query on `gmail_thread_id`. This is fast with the right index on `(tenant_id, gmail_thread_id, received_at DESC)`.

---

## Integration Points Summary

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Gmail API (read) | `google-auth-oauthlib` + `googleapiclient`, same as existing send integration | Separate OAuth grant from send scope |
| Gmail API (send) | Already handled by `email_dispatch.py` → `google_gmail.py` | No changes |
| Anthropic API | Existing `skill_executor.py` tool_use loop | Email skills are standard skills |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `email_sync_loop` → `job_queue_loop` | DB (SkillRun insert) | Clean decoupling, no direct function call |
| `email_scorer` skill → context store | Via `context_tools` in tool_use loop | Standard skill pattern, no special casing |
| `email_drafter` skill → Gmail read | Direct function call to `gmail_read.get_message_body()` | Body fetch inside skill execution, not sync |
| `api/email.py` → `email_dispatch.py` | Direct function call on draft approval | Existing dispatch handles provider routing |
| Frontend → backend | REST (no SSE needed for email review) | Unlike skills, email review is request/response |

---

## Sources

- Codebase inspection: `backend/src/flywheel/services/` (calendar_sync.py, google_gmail.py, job_queue.py, email_dispatch.py, skill_executor.py)
- Codebase inspection: `backend/src/flywheel/db/models.py` (Integration, SkillRun, ContextEntry, ContextEntity patterns)
- Codebase inspection: `backend/src/flywheel/main.py` (lifespan worker registration pattern)
- Codebase inspection: `backend/src/flywheel/api/integrations.py` (OAuth flow pattern)
- Codebase inspection: `backend/src/flywheel/config.py` (settings pattern)
- Concept brief: `.planning/CONCEPT-BRIEF-email-copilot.md` (architecture decisions, data model)

---

*Architecture research for: Email Copilot integration into Flywheel V2*
*Researched: 2026-03-24*
