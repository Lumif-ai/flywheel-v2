---
name: email-drafter
enabled: false
version: "1.0"
description: >
  Background email draft generator. Creates voice-matched reply drafts for
  emails scored priority 3+ with suggested_action=draft_reply. Uses context
  assembly from scorer's context_refs and voice profile injection. Called by
  the sync worker after scoring.
web_tier: 1
engine: email_drafter
contract_reads:
  - email_scores
  - email_voice_profiles
  - context_entities
  - context_entries
  - emails
contract_writes:
  - email_drafts
tags:
  - email
  - background
token_budget: 15000
---

# email-drafter

Background skill that generates voice-matched reply drafts for scored emails.
Invoked programmatically by the Gmail sync worker (`gmail_sync.py`) after the
scoring phase — specifically for emails with `priority >= 3` and
`suggested_action = "draft_reply"`. Not user-interactive — all drafting is
automated and asynchronous.

The live drafting logic (voice injection, context assembly, body fetch, upsert)
lives in `backend/src/flywheel/engines/email_drafter.py`. This file is the
seed-compatible skill definition used by `seed.py` to register the skill in
`skill_definitions`.

---

## Drafting Overview

Each draft is generated using a three-step pipeline:

1. **Pre-LLM assembly (Python layer)**
   - Load `EmailVoiceProfile` for the tenant+user (fall back to default stub if
     not yet populated)
   - Fetch email body on-demand via `gmail_read.get_message_body()` — NOT stored
     during sync (PII minimization)
   - Assemble context from `EmailScore.context_refs` — reuses the scorer's
     already-identified entries and entities, no FTS re-run

2. **LLM drafting (Claude Sonnet)**
   - Voice profile (tone, avg_length, sign_off, phrases) injected into system
     prompt as structured constraints
   - Email body + assembled context passed in user message
   - Sonnet returns raw reply body text — no JSON wrapping, no metadata
   - Response capped at `max_tokens=1000`; truncated at 2000 chars if exceeded

3. **Upsert (idempotent via caller guard)**
   - Simple `INSERT INTO email_drafts` — no `ON CONFLICT` (no unique constraint
     on `email_id` in the migration)
   - Caller guards against duplicates via `LEFT JOIN email_drafts ... IS NULL`
     before invoking `draft_email()`
   - `status = "pending"`, `visible_after` set per `draft_visibility_delay_days`
     config (default: 0 = immediately visible)

---

## Voice Profile Injection

The `EmailVoiceProfile` (populated by Phase 2's voice init) provides four fields
injected into the Sonnet system prompt as explicit constraints:

| Field         | Prompt role                                               |
|---------------|-----------------------------------------------------------|
| `tone`        | Writing tone instruction ("direct and concise", etc.)     |
| `avg_length`  | Target reply length in words (stay within 20%)            |
| `sign_off`    | Required closing line (always appended)                   |
| `phrases`     | Up to 5 characteristic phrases to weave in naturally      |

**Cold-start (no voice profile):** If `EmailVoiceProfile` does not yet exist for
the user, `_load_voice_profile()` returns `DEFAULT_VOICE_STUB`:

```python
DEFAULT_VOICE_STUB = {
    "tone": "professional and direct",
    "avg_length": 80,
    "sign_off": "Best,",
    "phrases": [],
}
```

A generic professional draft is generated. The stub is replaced automatically
once the voice profile is populated after the first sync cycle.

---

## Context Assembly

The scorer's `EmailScore.context_refs` already identifies which context entries
and entities are relevant. The drafter loads these by UUID — no second FTS pass.

- Up to **5 context entries** loaded from `context_entries` by UUID
- Up to **3 context entities** loaded from `context_entities` by UUID
- Formatted as structured text block for system prompt injection:

```
[Meeting note from deal-pipeline.md, 2026-03-20]: "Series A term sheet revision..."
[Entity: Acme Capital (company, 12 mentions)]: Key investor relationship...
```

If no context_refs exist or none match, the context block is "No relevant context
available." The draft still proceeds using voice profile only.

---

## Error Handling

**Body fetch 401/403:** If `get_message_body()` returns a 401 or 403 (revoked
token or permission issue), the drafter falls back to `email.snippet` and records
`{"fetch_error": "body_fetch_failed:401"}` in `EmailDraft.context_used`. A draft
is still generated using snippet instead of full body.

**Empty body skip:** If both `body_text` and `email.snippet` are under 10-20
characters (calendar invites, read receipts), `draft_email()` returns `None`
without creating a draft row. The sync loop is unaffected.

**Non-fatal pattern:** All exceptions are caught in the outer error boundary.
Only `email.id` and `tenant_id` are logged — no PII (no subject, sender, or
body in log output). `draft_email()` returns `None` on any failure. The sync
loop always completes regardless of draft outcome.

---

## Architecture Notes

- **On-demand body fetch:** Email body is never stored in the `emails` table
  (PII minimization, per DRAFT requirement). Body is fetched from Gmail API only
  at draft generation time and not persisted beyond the LLM call.
- **Caller-commits:** `email_drafter.py` does NOT call `db.commit()`. The sync
  worker (`gmail_sync.py`) is responsible for committing the session after
  drafting — consistent with Phase 2 and Phase 3 patterns.
- **Subsidy API key:** `settings.flywheel_subsidy_api_key` is used by default.
  Background draft generation has no user_id context and cannot use BYOK keys.
- **Bypasses `execute_run()`:** Like `email_scorer.py`, this engine is called
  directly from the sync loop — not via the generic skill execution framework.
  Background automation with subsidy key does not fit the `execute_run()` model.
- **Sonnet, not Haiku:** Draft quality is trust-sensitive. First drafts establish
  user expectations. Haiku is used for scoring (structured JSON); Sonnet is used
  for drafting (quality prose).
