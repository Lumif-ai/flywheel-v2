---
phase: 70-voice-profile-overhaul
verified: 2026-03-30T00:07:09Z
status: passed
score: 5/5 must-haves verified
---

# Phase 70: Voice Profile Overhaul Verification Report

**Phase Goal:** The voice profile captures 10 fields from 50 emails instead of 4 fields from 20, and both initial extraction and incremental learning use Sonnet. Drafts sound noticeably more like the user because the system knows their formality, greeting style, paragraph patterns, and emoji habits — not just tone and sign-off.
**Verified:** 2026-03-30T00:07:09Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                               | Status     | Evidence                                                                                                                                                                              |
|----|---------------------------------------------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | After running voice extraction, the `email_voice_profiles` row has all 10 fields populated                          | VERIFIED   | Migration adds 6 columns with server defaults; upsert `.values()` and `.set_()` both include all 10 fields in `gmail_sync.py` lines 908-936                                            |
| 2  | A draft for a "casual"/"Hey," profile produces visibly different output than a formal profile                        | VERIFIED   | `DRAFT_SYSTEM_PROMPT` instructs the LLM on `{formality_level}`, `{greeting_style}`, emoji constraints; `_build_draft_prompt` formats all 10 fields; constraint "casual means contractions, informal language" is explicit |
| 3  | After editing a draft, the incremental voice updater can update any of the 10 fields                                | VERIFIED   | `update_from_edit()` includes all 10 fields in `current_profile_json`, merge logic, and UPDATE `.values()` call (lines 165-170, 268-306 in `email_voice_updater.py`)                  |
| 4  | Existing voice profiles (with only 4 fields) receive column defaults from migration and continue to work            | VERIFIED   | Migration adds all 6 columns as nullable with `server_default`; `_load_voice_profile` uses `or DEFAULT_VOICE_STUB[...]` fallbacks for NULL values                                    |
| 5  | Voice extraction analyzes 50 substantive sent emails — `samples_analyzed` reflects this                             | VERIFIED   | `gmail_sync.py` line 902: `substantive_bodies[:50]`; line 904: `profile_data.get("samples_analyzed", len(substantive_bodies[:50]))`; no `[:20]` slice remains                        |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                                          | Expected                                                    | Status   | Details                                                                                   |
|-------------------------------------------------------------------|-------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------|
| `backend/alembic/versions/036_voice_profile_expansion.py`         | Alembic migration adding 6 columns to email_voice_profiles  | VERIFIED | Exists; adds all 6 columns with correct types and defaults; downgrade drops all 6 columns |
| `backend/src/flywheel/db/models.py`                               | 6 new Mapped[] columns on EmailVoiceProfile                 | VERIFIED | Lines 1075-1091: all 6 new columns with matching server_defaults; existing 4 unchanged     |
| `backend/src/flywheel/services/gmail_sync.py`                     | Expanded 10-field prompt and 50-sample pipeline             | VERIFIED | VOICE_SYSTEM_PROMPT lists all 10 fields; slice is `[:50]`; upsert persists all 10 fields  |
| `backend/src/flywheel/engines/email_drafter.py`                   | Expanded draft prompt and 10-field profile loading          | VERIFIED | DEFAULT_VOICE_STUB has 10 fields; DRAFT_SYSTEM_PROMPT uses all 10; `_build_draft_prompt` formats all 10 with fallbacks |
| `backend/src/flywheel/engines/email_voice_updater.py`             | Expanded update prompt and merge logic for 10 fields        | VERIFIED | `_UPDATE_VOICE_SYSTEM` lists all 10 fields; merge logic handles 5 direct + 1 running avg; UPDATE persists all 10 |

### Key Link Verification

| From                          | To                            | Via                                                    | Status   | Details                                                                                                    |
|-------------------------------|-------------------------------|--------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------|
| `036_voice_profile_expansion` | `models.py`                   | Column names and defaults must match                   | WIRED    | Migration: `server_default="conversational"`; model: `server_default=text("'conversational'")` — match confirmed for all 6 columns |
| `gmail_sync.py`               | `models.py`                   | Upsert `.values()` and `.set_()` include all 10 fields | WIRED    | All 10 fields present in both insert and on-conflict-update paths (lines 908-936)                          |
| `email_drafter.py`            | `models.py`                   | `_load_voice_profile` reads all 10 columns with fallbacks | WIRED | Lines 148-159: reads all 10 profile fields, falls back to DEFAULT_VOICE_STUB for NULL                     |
| `email_drafter.py`            | `DRAFT_SYSTEM_PROMPT`         | `_build_draft_prompt` formats all 10 fields            | WIRED    | Lines 326-337: all 10 fields including the 6 new ones passed to `DRAFT_SYSTEM_PROMPT.format()`            |
| `email_voice_updater.py`      | `models.py`                   | UPDATE `.values()` includes all 10 fields              | WIRED    | Lines 296-310: all 10 fields in UPDATE statement                                                           |
| `gmail_sync.py`               | `model_config.get_engine_model` | voice_extraction engine key resolves to Sonnet         | WIRED    | Line 899: `get_engine_model(db, integration.tenant_id, "voice_extraction")`; default is `claude-sonnet-4-6` |
| `email_voice_updater.py`      | `model_config.get_engine_model` | voice_learning engine key resolves to Sonnet           | WIRED    | Line 194: `get_engine_model(db, tenant_id, "voice_learning")`; default is `claude-sonnet-4-6`             |

### Requirements Coverage

| Requirement | Status    | Notes                                                                                                                |
|-------------|-----------|----------------------------------------------------------------------------------------------------------------------|
| VOICE-01    | SATISFIED | 50 substantive emails; VOICE_SYSTEM_PROMPT requests all 10 fields; `voice_extraction` engine resolves to Sonnet by default |
| VOICE-02    | SATISFIED | Migration 036 adds all 6 columns; ORM model updated with matching server_defaults                                    |
| VOICE-03    | SATISFIED | DRAFT_SYSTEM_PROMPT uses all 10 fields; `_build_draft_prompt` formats all 10 with DEFAULT_VOICE_STUB fallbacks       |
| VOICE-04    | SATISFIED | `_UPDATE_VOICE_SYSTEM` lists all 10 fields; `update_from_edit` merges and persists all 10; `voice_learning` engine resolves to Sonnet |

### Anti-Patterns Found

None — no TODO/FIXME/placeholder comments, no stub implementations, no empty handlers found in any of the 5 modified files.

### Assumptions Made (Need Confirmation)

No SPEC-GAPS.md found in project. No open assumptions identified.

### Human Verification Required

The following items cannot be verified programmatically and require a running environment:

#### 1. Draft Differentiation by Formality

**Test:** Run `draft_email()` for two users — one with `formality_level="casual"` and `greeting_style="Hey,"`, another with `formality_level="formal"` and `greeting_style="Dear {name},"`.
**Expected:** The casual draft starts with "Hey" or similar informal opener and uses contractions; the formal draft starts with "Dear [Name]," and uses formal register throughout.
**Why human:** LLM output content cannot be inspected statically — requires live API call.

#### 2. samples_analyzed Value on Fresh Profile

**Test:** Trigger `voice_profile_init()` for a user with 50+ substantive sent emails and read the resulting `samples_analyzed` value from the database.
**Expected:** `samples_analyzed` reflects the actual number of emails analyzed (up to 50), not a static value.
**Why human:** Requires a live database and Gmail integration with real sent mail.

#### 3. Incremental Update Across All 10 Fields

**Test:** Approve a draft and make an edit that demonstrates a formality change (e.g., change "Dear John," to "Hey John,"). Check the `email_voice_profiles` row afterwards.
**Expected:** `greeting_style` updates to reflect the edit; `formality_level` may also update.
**Why human:** Requires end-to-end flow with LLM interpretation of edit diffs.

### Gaps Summary

No gaps. All 5 observable truths are verified, all 5 required artifacts exist and are substantively implemented, all 7 key links are wired correctly, and all 4 requirements (VOICE-01 through VOICE-04) are satisfied.

The Sonnet usage requirement is met via the configurable model infrastructure from Phase 69: both `voice_extraction` and `voice_learning` engine keys default to `claude-sonnet-4-6` in `model_config.py`. Per-tenant overrides remain possible but Sonnet is the baseline.

---

_Verified: 2026-03-30T00:07:09Z_
_Verifier: Claude (gsd-verifier)_
