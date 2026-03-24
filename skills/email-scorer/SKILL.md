---
name: email-scorer
version: "1.0"
description: >
  Background email priority scorer. Scores each synced email 1-5 using
  sender entity lookup, context store full-text search, and LLM reasoning.
  Writes EmailScore rows. Called by the sync worker after upsert.
web_tier: 1
engine: email_scorer
contract_reads:
  - context_entities
  - context_entries
contract_writes:
  - email_scores
tags:
  - email
  - background
token_budget: 10000
---

# email-scorer

Background skill that scores every synced email on a 1-5 priority scale. Invoked
programmatically by the Gmail sync worker (`gmail_sync.py`) after each email upsert.
Not user-interactive — all scoring is automated.

The live scoring logic (prompt, DB queries, upsert) lives in
`backend/src/flywheel/engines/email_scorer.py`. This file is the seed-compatible
skill definition used by `seed.py` to register the skill in `skill_definitions`.

---

## Scoring Overview

Each email is scored using a three-step pipeline:

1. **Pre-LLM enrichment (Python layer)**
   - Look up `sender_email` domain and address in `context_entities` to get entity
     name, type, and `mention_count`
   - Run subject keywords through PostgreSQL `plainto_tsquery` FTS on
     `context_entries.search_vector` to fetch top-3 matching context entries

2. **LLM scoring (Claude Haiku)**
   - Pass pre-fetched entity + context entries as structured context to the LLM
   - LLM returns a JSON object: `{priority, category, suggested_action, reasoning,
     context_refs}`
   - Scoring bias: **when uncertain, score UP** (SCORE-09 — false negatives are
     critical product failures)

3. **Upsert (idempotent)**
   - `pg_insert(EmailScore).on_conflict_do_update(constraint="uq_email_score_email")`
   - Re-scoring an already-scored email updates the row in-place

---

## Priority Scale

| Score | Label    | Definition                                                   |
|-------|----------|--------------------------------------------------------------|
| 5     | CRITICAL | Requires same-day action; known key contact or active deal   |
| 4     | IMPORTANT| Requires response within 24h; known contact or relevant topic|
| 3     | NORMAL   | Warrants attention; no urgency signal                        |
| 2     | LOW      | FYI only; no action needed                                   |
| 1     | NOISE    | Marketing, auto-notifications, or clearly irrelevant         |

---

## Signal Hierarchy

The scoring prompt uses these signals (embedded as a rubric + few-shot examples):

| Signal                                                        | Direction  |
|---------------------------------------------------------------|------------|
| Sender in `context_entities`, `mention_count >= 5`           | Score UP   |
| Sender entity with `entity_type="company"` + context match   | Score UP   |
| Subject matches context entry (FTS hit)                       | Score UP   |
| Label includes `IMPORTANT`                                    | Boost      |
| Urgency words: "urgent", "deadline", "ASAP", "closing"       | Boost      |
| Thread stale: `is_replied=False`, received > 7 days ago      | Boost      |
| Label includes `CATEGORY_PROMOTIONS` or `CATEGORY_UPDATES`   | Score DOWN |
| No context available (new tenant)                            | Baseline 3 |

---

## Output Schema

Each `EmailScore` row written to the DB:

```json
{
  "priority": 4,
  "category": "deal_related",
  "suggested_action": "draft_reply",
  "reasoning": "Sender matches context entity 'Acme Corp'. Subject implies closing urgency.",
  "context_refs": [
    {"type": "entity", "id": "<uuid>", "name": "Acme Corp"},
    {"type": "entry", "id": "<uuid>", "file": "deal-pipeline.md", "snippet": "Series A..."}
  ]
}
```

Valid categories: `meeting_followup`, `deal_related`, `action_required`,
`informational`, `marketing`, `personal`

Valid suggested actions: `notify`, `draft_reply`, `file`, `archive`

---

## Thread Priority

Thread priority = `MAX(priority)` across all `EmailScore` rows in a thread where
`is_replied = FALSE`. Computed at read time — no denormalized column needed for Phase 3.

---

## Architecture Notes

- No email body accessed — scoring uses sender + subject + snippet + labels only (PII minimization)
- Zero PII in log output — only `email.id`, `tenant_id`, priority result
- Caller commits the session — the engine does NOT call `db.commit()`
- Subsidy API key default — `settings.flywheel_subsidy_api_key` (same as voice profile)
- Engine bypasses `execute_run()` — called directly from sync loop for background automation
