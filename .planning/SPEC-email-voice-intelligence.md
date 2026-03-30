# Email Voice & Intelligence Overhaul — Specification

> Status: Draft
> Created: 2026-03-29
> Last updated: 2026-03-30
> Source: CONCEPT-BRIEF-email-voice-intelligence.md (brainstorm, 4 rounds, 15 advisors)

## Overview

Transform the email system from a siloed draft engine with shallow voice learning into a bidirectional intelligence source that sounds like the user, shares voice across all skills, and feeds relationship/deal/contact intelligence back into the context store. Three tracks: (A) voice profile overhaul, (B) voice as shared context store asset, (C) email as context store source.

## Core Value

Drafts must sound like the user wrote them — not AI-polished prose. Everything else (settings UI, context store writes, shared voice) supports this.

## Users & Entry Points

| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| Founder/operator | Email inbox → draft review | Approve drafts that sound like them without editing |
| Founder/operator | Settings → Voice Profile tab | See what the system learned, correct tone/sign-off |
| Founder/operator | Any text-generating skill | Get output in their voice (outreach, social, meeting prep) |
| System (background) | Gmail sync loop | Extract intelligence from emails into context store |

## Requirements

### Track A: Voice Profile Overhaul

#### Must Have

- **A-01**: Switch voice profile initialization from Haiku to Sonnet
  - **Current:** `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` in `gmail_sync.py:759`
  - **Change:** Read model from tenant settings config, default to `claude-sonnet-4-6`
  - **Acceptance Criteria:**
    - [ ] `voice_profile_init()` reads model from `email_engine_models` config (see A-07)
    - [ ] Default model is `claude-sonnet-4-6` when config is absent
    - [ ] Existing voice profiles are NOT re-extracted (idempotency guard unchanged)

- **A-02**: Switch incremental voice updater from Haiku to Sonnet
  - **Current:** `_HAIKU_MODEL = "claude-haiku-4-5-20251001"` in `email_voice_updater.py:35`
  - **Change:** Read model from tenant settings config, default to `claude-sonnet-4-6`
  - **Acceptance Criteria:**
    - [ ] `update_from_edit()` reads model from `email_engine_models` config
    - [ ] Default model is `claude-sonnet-4-6` when config is absent

- **A-03**: Richer initial voice extraction — more samples, deeper signals
  - **Current:** Analyzes top 20 substantive sent emails, extracts 4 fields (tone, avg_length, sign_off, phrases)
  - **Change:** Analyze top 50 substantive emails (up from 20), extract expanded field set
  - **New fields to extract:**
    - `formality_level`: string enum — `"formal"` | `"conversational"` | `"casual"`
    - `greeting_style`: string — e.g., `"Hi {name},"`, `"Hey,"`, `"No greeting"`
    - `question_style`: string — e.g., `"direct"`, `"embedded"`, `"rare"`
    - `paragraph_pattern`: string — e.g., `"short single-line"`, `"2-3 sentence blocks"`, `"long form"`
    - `emoji_usage`: string — e.g., `"never"`, `"occasional"`, `"frequent"`
    - `avg_sentences`: integer — average sentences per email
  - **Acceptance Criteria:**
    - [ ] `_extract_voice_profile()` sends 50 bodies to LLM (up from 20)
    - [ ] `max_results=200` for sent message fetch unchanged (already fetches 200, filters to substantive)
    - [ ] LLM prompt requests all 10 fields (4 existing + 6 new)
    - [ ] Response parsed into expanded `EmailVoiceProfile` model
    - [ ] Graceful fallback: if LLM omits new fields, use defaults (see schema defaults below)

- **A-04**: Database migration — expand `email_voice_profiles` table
  - **New columns:**
    - `formality_level TEXT DEFAULT 'conversational'`
    - `greeting_style TEXT DEFAULT 'Hi {name},'`
    - `question_style TEXT DEFAULT 'direct'`
    - `paragraph_pattern TEXT DEFAULT 'short single-line'`
    - `emoji_usage TEXT DEFAULT 'never'`
    - `avg_sentences INTEGER DEFAULT 3`
  - **Acceptance Criteria:**
    - [ ] Alembic migration adds 6 new nullable columns with defaults
    - [ ] Existing rows get defaults applied (not null)
    - [ ] Migration is reversible (downgrade drops columns)
    - [ ] `EmailVoiceProfile` SQLAlchemy model updated with new `Mapped` columns

- **A-05**: Update `DRAFT_SYSTEM_PROMPT` to use expanded voice profile
  - **Current prompt** (lines 70-92 of `email_drafter.py`) uses: tone, avg_length, sign_off, phrases
  - **Change:** Inject all 10 voice fields into system prompt
  - **New prompt section:**
    ```
    VOICE PROFILE (match this exactly):
    - Tone: {tone}
    - Formality: {formality_level}
    - Greeting style: {greeting_style}
    - Typical length: {avg_length} words, ~{avg_sentences} sentences
    - Paragraph style: {paragraph_pattern}
    - Question style: {question_style}
    - Emoji usage: {emoji_usage}
    - Sign-off: Always end with "{sign_off}"
    - Characteristic phrases to weave in naturally: {phrases_list}
    ```
  - **Acceptance Criteria:**
    - [ ] `_build_draft_prompt()` injects all 10 fields
    - [ ] Missing fields fall back to defaults (never crash on partial profile)
    - [ ] Draft output observably reflects formality_level and greeting_style

- **A-06**: Update incremental voice updater to learn expanded fields
  - **Current `_UPDATE_VOICE_SYSTEM`** (lines 37-53 of `email_voice_updater.py`) returns: tone, avg_length, sign_off, phrases_to_add, phrases_to_remove
  - **Change:** Add 6 new returnable fields to the update prompt
  - **New allowed return fields:**
    - `formality_level`, `greeting_style`, `question_style`, `paragraph_pattern`, `emoji_usage`, `avg_sentences`
  - **Merge logic for new fields:** Direct replacement (same as tone/sign_off), only if present in LLM response
  - **Acceptance Criteria:**
    - [ ] `_UPDATE_VOICE_SYSTEM` prompt lists all new fields as allowed returns
    - [ ] Merge function handles new fields with direct replacement
    - [ ] `samples_analyzed` still incremented by 1 per edit

- **A-07**: Configurable model per email engine
  - **New config structure** (stored in tenant settings JSONB or app config):
    ```json
    {
      "email_engine_models": {
        "scoring": "claude-sonnet-4-6",
        "voice_extraction": "claude-sonnet-4-6",
        "voice_learning": "claude-sonnet-4-6",
        "drafting": "claude-sonnet-4-6",
        "context_extraction": "claude-sonnet-4-6"
      }
    }
    ```
  - **Default:** All engines default to `claude-sonnet-4-6` when config absent
  - **Implementation:** Each engine reads its model key at call time, not at import time. Replace module-level `_HAIKU_MODEL` / `_SONNET_MODEL` constants with a helper:
    ```python
    async def _get_engine_model(db, tenant_id, engine_key, default="claude-sonnet-4-6"):
        # Read from tenant settings or return default
    ```
  - **Acceptance Criteria:**
    - [ ] All 5 engines (scorer, voice_extraction, voice_learning, drafter, context_extraction) read model from config
    - [ ] No hardcoded model constants remain in email engine files
    - [ ] Changing config takes effect on next sync cycle (no restart needed)
    - [ ] Invalid model strings fall back to default with warning log

- **A-08**: Voice Profile Settings page — read-mostly mirror card
  - **New component:** `VoiceProfileSettings.tsx` in `frontend/src/features/settings/components/`
  - **New tab** in `SettingsPage.tsx`: "Voice Profile" (visible to all authenticated users)
  - **Layout:**
    - Header: "Your Writing Voice" with description "Learned from {samples_analyzed} sent emails"
    - Read-only card showing all 10 voice fields as descriptive text (not form inputs)
    - Two editable fields: **tone** (text input) and **sign_off** (text input) — with Save button
    - "Reset & Relearn" button — triggers `voice_profile_init()` with `force=True` (deletes existing profile, re-extracts from sent emails)
    - Last updated timestamp
  - **API endpoints needed (user-scoped — each user sees/edits their own profile):**
    - `GET /email/voice-profile` — returns current user's voice profile (all fields + samples_analyzed + updated_at). Scoped by `user.id` from auth token, not tenant-wide.
    - `PATCH /email/voice-profile` — updates tone and/or sign_off only (other fields not user-editable). Scoped by `user.id`.
    - `POST /email/voice-profile/reset` — deletes current user's profile and triggers re-extraction. Scoped by `user.id`.
  - **Acceptance Criteria:**
    - [ ] Settings page shows "Voice Profile" tab
    - [ ] All 10 voice fields displayed as read-only descriptive text
    - [ ] Tone and sign_off are editable with inline save
    - [ ] "Reset & Relearn" shows confirmation dialog before executing
    - [ ] Loading state shown while profile loads (skeleton pattern matching existing settings)
    - [ ] Empty state if no profile exists: "No voice profile yet. Connect Gmail to get started."
    - [ ] Toast notification on save success/failure (using `sonner`)

- **A-09**: "Voice influence" annotation on drafts
  - **Change to DraftReview.tsx:** Add collapsible "Voice applied" section below draft textarea
  - **Pattern:** Reuse the existing collapsible reasoning pattern from `ThreadDetail.tsx` MessageRow
  - **Content:** Show which voice profile fields influenced this draft:
    ```
    Voice applied: professional and direct tone, ~80 words, greeting "Hi {name},",
    sign-off "Best,", phrases: "happy to help", "let me know"
    ```
  - **Data source:** Include `voice_profile_snapshot` in draft creation (stored in `context_used` JSONB)
  - **Acceptance Criteria:**
    - [ ] DraftReview shows collapsible "Voice applied" section (collapsed by default)
    - [ ] Section shows tone, avg_length, greeting_style, sign_off, and phrases used
    - [ ] Clicking expands to show all 10 fields
    - [ ] No additional API call needed — data comes from existing `context_used` field on draft

- **A-10**: Manual tone override per draft
  - **Change to DraftReview.tsx:** Add "Regenerate" dropdown with quick actions:
    - "Make shorter" — regenerates with `avg_length` halved
    - "Make longer" — regenerates with `avg_length` doubled
    - "More casual" — regenerates with `tone: "casual and friendly"`, `formality_level: "casual"`
    - "More formal" — regenerates with `tone: "professional and formal"`, `formality_level: "formal"`
  - **New API endpoint:** `POST /email/drafts/{draft_id}/regenerate`
    - Request body: `{ overrides: { tone?: string, avg_length?: int, formality_level?: string } }`
    - Process: Re-runs `draft_email()` with overridden voice profile fields, replaces `draft_body`
    - Does NOT update the persistent voice profile (one-time override)
  - **Acceptance Criteria:**
    - [ ] "Regenerate" dropdown appears next to Edit button on pending drafts
    - [ ] Each option triggers regeneration with specific overrides
    - [ ] Original draft is replaced (not appended)
    - [ ] Loading spinner shown during regeneration
    - [ ] Override does NOT persist to voice profile (confirmed by checking profile after)
    - [ ] Custom override option: user types free-form tone instruction

### Track B: Voice as Shared Context Store Asset

#### Must Have

- **B-01**: Write voice profile to context store as `sender-voice.md`
  - **When:** After initial voice extraction AND after every incremental update
  - **Format:** Follow context store entry format from `context-protocol.md`:
    ```
    [YYYY-MM-DD | source: email-voice-engine | voice-profile] confidence: high | evidence: {samples_analyzed}
    - Tone: {tone}
    - Formality: {formality_level}
    - Greeting style: {greeting_style}
    - Avg length: {avg_length} words, ~{avg_sentences} sentences
    - Paragraph pattern: {paragraph_pattern}
    - Question style: {question_style}
    - Emoji usage: {emoji_usage}
    - Sign-off: {sign_off}
    - Characteristic phrases: {phrases as comma-separated}
    ```
  - **Write mechanism:** Direct file I/O via shared `context_store_writer` (same as C-02). Writes to `sender-voice.md` at configured context store path.
  - **Dedup:** Single entry per user, overwrites on each update (not append — voice profile is singular)
  - **Acceptance Criteria:**
    - [ ] `sender-voice.md` created in context store after first voice extraction
    - [ ] File updated after every `update_from_edit()` call that returns `True`
    - [ ] Other skills can read `sender-voice.md` via `flywheel_read_context`
    - [ ] File follows standard context store entry format

- **B-02**: Update context store catalog with `sender-voice.md`
  - **File:** `~/.claude/context/_catalog.md`
  - **New entry:**
    ```
    | sender-voice.md | User's writing voice profile | email-voice-engine | tone, formality, greeting, length, phrases |
    ```
  - **Acceptance Criteria:**
    - [ ] Catalog entry exists and is discoverable
    - [ ] Entry format matches existing catalog rows

### Track C: Email as Context Store Source

#### Must Have

- **C-01**: Email context extractor engine — new file `email_context_extractor.py`
  - **Location:** `backend/src/flywheel/engines/email_context_extractor.py`
  - **Purpose:** Extract contacts, topics, relationship signals, deal intelligence, and sentiment from email bodies and write to context store
  - **Trigger:** Called during gmail sync loop, after scoring, for emails with priority >= 3
  - **Input:** Email metadata (sender, subject, labels) + body (fetched on-demand, same as drafter)
  - **Model:** Configurable via `email_engine_models.context_extraction`, default Sonnet
  - **Function signature:**
    ```python
    async def extract_email_context(
        db: AsyncSession,
        tenant_id: UUID,
        email: Email,
        score: EmailScore,
        integration,
        api_key: str | None = None,
    ) -> dict | None:
    ```
  - **Extraction prompt — request these from the LLM:**
    ```json
    {
      "contacts": [
        {
          "name": "string",
          "email": "string",
          "title": "string or null",
          "company": "string or null",
          "relationship_signal": "new_contact | existing_warm | existing_cold | existing_hot",
          "context": "string - what this email reveals about them"
        }
      ],
      "topics": [
        {
          "topic": "string - what's being discussed",
          "detail_tag": "string - slug for context store",
          "relevance": "high | medium"
        }
      ],
      "deal_signals": [
        {
          "signal": "string - what deal-related event happened",
          "stage_hint": "string or null - e.g., 'contract sent', 'scheduling demo', 'pricing discussion'",
          "confidence": "high | medium | low"
        }
      ],
      "relationship_signals": {
        "sender_sentiment": "positive | neutral | negative | urgent",
        "response_urgency": "high | medium | low",
        "relationship_direction": "warming | stable | cooling | new"
      },
      "action_items": [
        {
          "action": "string",
          "owner": "them | us",
          "due_hint": "string or null"
        }
      ]
    }
    ```
  - **Guard rails:**
    - Only process emails with `score.priority >= 3`
    - Max tokens: 2000 (email bodies can be longer than drafts)
    - Skip if body < 20 chars (same threshold as drafter)
    - Non-fatal: return `None` on any error, sync loop continues
    - Body fetched on-demand and discarded after extraction (PII posture maintained)
  - **Acceptance Criteria:**
    - [ ] Engine file exists at specified path
    - [ ] Only processes priority >= 3 emails
    - [ ] Returns structured extraction result or None
    - [ ] Body is never stored — fetched and discarded within function scope
    - [ ] Model is configurable via `email_engine_models.context_extraction`

- **C-02**: Shared context store writer — new file `context_store_writer.py`
  - **Location:** `backend/src/flywheel/engines/context_store_writer.py`
  - **Purpose:** Uniform write/merge/dedup logic for writing extracted intelligence to context store files. Used by email extractor now, meeting-processor refactored to use later.
  - **Core functions:**
    ```python
    async def write_contact(
        name: str, email: str, title: str | None, company: str | None,
        relationship_signal: str, context: str, source: str, date: str,
    ) -> dict:
        """Write or update contact in contacts.md. Dedup on name+company+date."""

    async def write_insight(
        detail_tag: str, content_lines: list[str],
        source: str, date: str, confidence: str = "medium",
    ) -> dict:
        """Append insight to insights.md. Dedup on source+detail_tag+date."""

    async def write_action_item(
        action: str, owner: str, due_hint: str | None,
        source: str, date: str, detail_tag: str,
    ) -> dict:
        """Append action item to action-items.md."""

    async def write_deal_signal(
        signal: str, stage_hint: str | None, confidence: str,
        source: str, date: str, detail_tag: str,
    ) -> dict:
        """Write deal intelligence to insights.md with deal-specific detail-tag."""
    ```
  - **Entry format:** Standard context store format:
    ```
    [YYYY-MM-DD | source: {source} | {detail_tag}] confidence: {level} | evidence: {N}
    - Content line 1
    - Content line 2
    ```
  - **Dedup:** Composite key = `source + detail_tag + date`. If duplicate found, skip write.
  - **Evidence increment:** When corroborating existing insight, increment evidence count.
  - **Write mechanism — dual interface:**
    - **Primary:** Direct file I/O (like meeting-processor's `context_utils.py`) for backend engine calls during gmail sync. Reads/writes context store files directly at the configured context store path.
    - **Secondary:** Thin MCP wrapper that calls the same write functions, so Claude Code skills can invoke the shared writer via `flywheel_write_context` or a new `flywheel_write_context_structured` tool. This ensures both backend engines and Claude Code skills use identical write/dedup/merge logic.
    - **Implementation:** Core logic in `context_store_writer.py` uses direct file I/O. MCP tool delegates to the same functions.
  - **Acceptance Criteria:**
    - [ ] All write functions follow standard context store entry format
    - [ ] Dedup prevents duplicate entries (same source + detail_tag + date)
    - [ ] Evidence count incremented on corroboration
    - [ ] Each function returns `{"status": "written" | "duplicate", "path": str}`
    - [ ] Max entry size: 4000 chars (truncate with `[truncated]` note)
    - [ ] Backend engines call writer directly (no MCP dependency during sync)
    - [ ] Claude Code skills can invoke the same writer via MCP tool

- **C-03**: Confidence-based routing — human review queue for low-confidence extractions
  - **New database table:** `email_context_reviews`
    ```sql
    CREATE TABLE email_context_reviews (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        email_id UUID NOT NULL REFERENCES emails(id),
        extraction_type TEXT NOT NULL,  -- 'contact' | 'deal_signal' | 'action_item' | 'insight'
        extracted_data JSONB NOT NULL,
        confidence TEXT NOT NULL,  -- 'low' | 'medium'
        target_file TEXT NOT NULL,  -- 'contacts.md' | 'insights.md' | etc
        status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    ```
  - **Routing logic in email_context_extractor:**
    - `confidence: "high"` → auto-write to context store via `context_store_writer`
    - `confidence: "medium"` → auto-write to context store (medium is acceptable signal)
    - `confidence: "low"` → insert into `email_context_reviews` for human review
  - **API endpoints:**
    - `GET /email/context-reviews` — list pending reviews (paginated)
    - `POST /email/context-reviews/{id}/approve` — write to context store and set status=approved
    - `POST /email/context-reviews/{id}/reject` — set status=rejected, no write
  - **Acceptance Criteria:**
    - [ ] High/medium confidence extractions auto-write to context store
    - [ ] Low confidence extractions queued in `email_context_reviews`
    - [ ] Approve endpoint writes the extraction to context store
    - [ ] Reject endpoint discards without writing
    - [ ] Pending reviews visible via API (frontend TBD — not in this spec)

- **C-04**: Wire email context extraction into gmail sync loop
  - **File:** `backend/src/flywheel/services/gmail_sync.py`
  - **Change:** After scoring, for emails with `score.priority >= 3`, call `extract_email_context()`
  - **Sequencing:** Score → Draft (if `suggested_action == "draft_reply"`) → Extract context (if `priority >= 3`)
  - **Daily cap:** Share the existing 500/day scoring cap or add separate cap for extraction (recommend: separate 200/day cap for context extraction to control costs)
  - **Acceptance Criteria:**
    - [ ] `extract_email_context()` called in sync loop after scoring
    - [ ] Only for emails with `score.priority >= 3`
    - [ ] Extraction failure does not block drafting or scoring
    - [ ] Daily extraction cap enforced (200/day per tenant)
    - [ ] Extracted context visible in context store files after sync

- **C-05**: Track which emails have been context-extracted
  - **Change to `emails` table or `email_scores` table:** Add `context_extracted_at TIMESTAMPTZ` column
  - **Set:** After successful extraction (or after review queue insertion)
  - **Purpose:** Prevent re-extraction on subsequent sync cycles
  - **Acceptance Criteria:**
    - [ ] Column added via migration
    - [ ] Set after extraction completes
    - [ ] Sync loop skips emails where `context_extracted_at IS NOT NULL`

### Should Have

- **A-11**: "Reset & Relearn" triggers re-extraction with expanded prompt
  - When user clicks "Reset & Relearn" in settings, delete existing profile and run `voice_profile_init()` with `force=True` parameter
  - `force=True` skips the idempotency guard (existing profile check)
  - **Acceptance Criteria:**
    - [ ] `voice_profile_init()` accepts `force: bool = False` parameter
    - [ ] When `force=True`, deletes existing profile before re-extracting
    - [ ] Re-extraction uses expanded prompt (10 fields, 50 samples)
    - [ ] Context store `sender-voice.md` updated after re-extraction

- **A-12**: Email scoring model configurable (currently Haiku)
  - **Current:** `_HAIKU_MODEL` in `email_scorer.py`
  - **Change:** Read from `email_engine_models.scoring` config
  - Same pattern as A-07
  - **Acceptance Criteria:**
    - [ ] Scorer reads model from config
    - [ ] Default is `claude-sonnet-4-6`

### Won't Have (this version)

- Voice drift detection and periodic re-anchoring — Deferred per user decision
- PII retention policy for email-derived context — Deferred per user decision
- Frontend UI for context review queue — API only in this version
- Slack as a context store source — Future track, same architecture
- Voice profile per recipient (adapting tone based on who you're writing to) — Future enhancement
- Meeting-processor refactor to use shared context writer — Separate task, not blocking

## Edge Cases & Error States

| Scenario | Expected Behavior |
|----------|-------------------|
| Voice profile init finds < 3 substantive emails | Log warning, return False, no profile created. Settings shows "No voice profile yet" |
| LLM returns partial voice profile (missing new fields) | Use column defaults for missing fields. Never crash on partial response |
| User edits draft but changes are trivial (whitespace only) | Voice updater returns `{}`, no profile update, no context store write |
| Email body fetch fails (401/403) during context extraction | Use `email.snippet` as fallback input. If snippet < 20 chars, skip extraction |
| Context store write fails (MCP tool error) | Log error, continue sync. Context extraction marked as attempted (`context_extracted_at` set) to avoid retry loops |
| User resets voice profile while sync is running | Race condition: sync may use stale profile for in-flight drafts. Acceptable — next sync cycle uses new profile |
| Email scored priority 3 but body is a one-line "Thanks!" | Extractor returns empty/minimal extraction. Nothing written to context store. Not an error |
| Duplicate contact extracted from multiple emails same day | Dedup on `source + detail_tag + date` prevents duplicate writes |
| Context review queue grows large (100+ pending) | No auto-cleanup. User reviews manually. Future: add batch approve/reject |
| Model string in config is invalid/deprecated | Fall back to `claude-sonnet-4-6` with warning log |

## Constraints

- **PII posture unchanged:** Email bodies fetched on-demand and discarded after processing. Never stored in DB. Context store entries derived from emails are persistent but contain extracted intelligence, not raw email text. (Brainstorm decision: PII retention policy deferred)
- **Caller-commits pattern:** All DB modules do NOT call `db.commit()`. Sync loop commits.
- **Non-fatal pattern:** All engines return `None` on error. Sync loop never crashes.
- **Context store format:** All writes must follow the standard entry format defined in `context-protocol.md`. Dedup key: `source + detail_tag + date`.
- **No body storage:** The `emails` table stores metadata only. This constraint is not changed.

## Anti-Requirements

- This is NOT a general-purpose email client — no compose-from-scratch, no inbox management
- This is NOT real-time — extraction happens on the 5-minute sync loop, not on email arrival
- This does NOT replace the meeting-processor — email extracts different (often thinner) signals
- The voice profile settings page is NOT a "prompt engineering" UI — users edit tone and sign-off, not system prompts
- The context review queue is NOT a task management system — approve/reject only, no editing of extracted data

## Open Questions

- [ ] Should the configurable model setting live in tenant settings (JSONB on tenants table) or in a separate `email_engine_config` table?
- [ ] Should context extraction cap (200/day) be configurable per tenant or global?
- [ ] Should "Reset & Relearn" also clear incremental learning history (reset `samples_analyzed` to 0)?
- [ ] What's the right UX for the context review queue in a future version — settings tab, separate page, or inline in email view?

## Artifacts Referenced

- `CONCEPT-BRIEF-email-voice-intelligence.md` — brainstorm output with 4 rounds of advisory deliberation, key decisions, tensions resolved
- `backend/src/flywheel/engines/email_drafter.py` — current drafter engine (DRAFT_SYSTEM_PROMPT lines 70-92, model at line 59)
- `backend/src/flywheel/engines/email_voice_updater.py` — current voice updater (UPDATE_VOICE_SYSTEM lines 37-53, Haiku at line 35)
- `backend/src/flywheel/engines/email_scorer.py` — current scorer
- `backend/src/flywheel/services/gmail_sync.py` — sync loop + voice_profile_init (lines 839-928)
- `backend/src/flywheel/db/models.py` — EmailVoiceProfile (lines 1050-1083), EmailDraft (1016-1048), Email (932-978)
- `backend/src/flywheel/api/email.py` — draft lifecycle endpoints
- `frontend/src/pages/SettingsPage.tsx` — current settings page (4 tabs)
- `frontend/src/features/email/components/DraftReview.tsx` — draft display component
- `frontend/src/features/email/components/ThreadDetail.tsx` — collapsible reasoning pattern
- `~/.claude/skills/_shared/context-protocol.md` — context store write protocol
- `~/.claude/skills/meeting-processor/SKILL.md` — extraction patterns and 7 context store files
