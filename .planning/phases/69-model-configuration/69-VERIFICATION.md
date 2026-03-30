---
phase: 69-model-configuration
verified: 2026-03-29T00:00:00Z
status: gaps_found
score: 3.5/4 must-haves verified
gaps:
  - truth: "An invalid model string in config logs a warning and falls back to the default model — the sync loop does not crash"
    status: partial
    reason: "model_config.py logs a warning for non-claude- strings, and the sync loop does not crash (per-email try/except in each engine handles Anthropic API failures). However the function returns the invalid model string to the caller rather than falling back to ENGINE_DEFAULTS. The Anthropic API call then fails, is caught by each engine's outer exception handler, that email is skipped, and get_engine_model returns None-worthy on the next iteration — so the loop survives but the individual email silently fails every time instead of recovering with the default model."
    artifacts:
      - path: "backend/src/flywheel/engines/model_config.py"
        issue: "Lines 78-85: warning is logged but return model.strip() executes unconditionally; should return ENGINE_DEFAULTS.get(engine_key, default) when model does not start with 'claude-'"
    missing:
      - "Change the non-claude- branch to return ENGINE_DEFAULTS.get(engine_key, default) after logging the warning, instead of returning the invalid string"
---

# Phase 69: Model Configuration Verification Report

**Phase Goal:** Every email engine reads its LLM model from a configurable setting rather than hardcoded constants. Switching from Haiku to Sonnet must be a config change, not a code change.
**Verified:** 2026-03-29
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `get_engine_model(db, tenant_id, "voice_extraction")` returns the configured model string, or `claude-sonnet-4-6` when no config exists | VERIFIED | `model_config.py:44-97` — reads `Tenant.settings["email_engine_models"][engine_key]`, falls back to `ENGINE_DEFAULTS` (all keys default to `"claude-sonnet-4-6"`). Exception path also falls back to `ENGINE_DEFAULTS`. |
| 2 | All 5 email engine files use the shared helper — no `_HAIKU_MODEL` or `_SONNET_MODEL` module-level constants remain | VERIFIED | All four active engine files import and call `get_engine_model`. No hardcoded `_HAIKU_MODEL` or `_SONNET_MODEL` constants in scorer, drafter, voice_updater, or gmail_sync. The 5th "engine" (context_extraction) is a future placeholder — its key is registered in `ENGINE_DEFAULTS` and no engine file yet exists, which is consistent with the phase goal stating "placeholder". |
| 3 | Changing the model config for a specific engine takes effect on the next sync cycle without requiring a server restart | VERIFIED | `get_engine_model` is called inside each sync cycle's per-email or per-integration path with a live DB session. There is no module-level caching of model strings. Next iteration reads fresh from DB. |
| 4 | An invalid model string in config logs a warning and falls back to the default model — the sync loop does not crash | PARTIAL | **Sync loop does not crash**: correct — per-email try/except in score_email, draft_email, and update_from_edit catch Anthropic API errors and return None. The sync loop outer `gather(return_exceptions=True)` also protects the loop. **Warning is logged**: correct — `model_config.py:78-84` logs a warning for strings that do not start with `"claude-"`. **Fallback to default**: NOT correct — after logging the warning, line 85 unconditionally returns `model.strip()` (the invalid string), which is then passed to the Anthropic client. The client raises an API error; that email's processing fails silently on every cycle. |

**Score:** 3.5/4 truths verified (Truth 4 is partial)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/engines/model_config.py` | New shared helper with `get_engine_model` and `ENGINE_DEFAULTS` | VERIFIED | File exists, 97 lines, substantive implementation with DB query, fallback logic, and warning path. |
| `backend/src/flywheel/engines/email_scorer.py` | Imports `get_engine_model`, no `_HAIKU_MODEL` constant | VERIFIED | Line 46: `from flywheel.engines.model_config import get_engine_model`. Line 539: `model = await get_engine_model(db, tenant_id, "scoring")`. No `_HAIKU_MODEL` or `_SONNET_MODEL` constants. |
| `backend/src/flywheel/engines/email_drafter.py` | Imports `get_engine_model`, no `_SONNET_MODEL` constant | VERIFIED | Line 53: `from flywheel.engines.model_config import get_engine_model`. Line 455: `model = await get_engine_model(db, tenant_id, "drafting")`. No hardcoded model constants. |
| `backend/src/flywheel/engines/email_voice_updater.py` | Imports `get_engine_model`, no `_HAIKU_MODEL` constant | VERIFIED | Line 32: `from flywheel.engines.model_config import get_engine_model`. Line 180: `model = await get_engine_model(db, tenant_id, "voice_learning")`. No hardcoded model constants. |
| `backend/src/flywheel/services/gmail_sync.py` | Uses `get_engine_model` for voice extraction | VERIFIED | Line 37: `from flywheel.engines.model_config import get_engine_model`. Line 893: `model = await get_engine_model(db, integration.tenant_id, "voice_extraction")`. Line 896 passes resolved model to `_extract_voice_profile`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `email_scorer.py` | `model_config.get_engine_model` | import + call | WIRED | Imported at line 46, called at line 539 with result passed to `client.messages.create(model=model, ...)` |
| `email_drafter.py` | `model_config.get_engine_model` | import + call | WIRED | Imported at line 53, called at line 455 with result passed to `client.messages.create(model=model, ...)` |
| `email_voice_updater.py` | `model_config.get_engine_model` | import + call | WIRED | Imported at line 32, called at line 180 with result passed to `client.messages.create(model=model, ...)` |
| `gmail_sync.py` | `model_config.get_engine_model` | import + call | WIRED | Imported at line 37, called at line 893, result passed to `_extract_voice_profile(..., model=model)` at line 896 |
| `model_config.py` | `Tenant.settings["email_engine_models"]` | SQLAlchemy select | WIRED | `select(Tenant.settings).where(Tenant.id == tenant_id)` reads from JSONB column confirmed on `Tenant` model at `models.py:56` |
| Invalid model string | `ENGINE_DEFAULTS` fallback | conditional return | NOT WIRED | Warning logged but invalid string is returned, not the default. The fallback branch is missing. |

---

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| MODEL-01: Shared helper with per-tenant config lookup | SATISFIED | `get_engine_model` implemented and wired in all 4 active engines |
| MODEL-02: Invalid config falls back gracefully without crashing sync | PARTIAL | Sync loop survives (non-fatal per-email error handling), but falls back via exception propagation rather than clean default-model substitution in `get_engine_model` |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `model_config.py` | 78-85 | Invalid model returned to caller instead of fallback | Warning | Every sync cycle for that engine will invoke Anthropic API with invalid model, fail, and silently skip all affected emails — defeating the "graceful degradation" intent |

Note: `flywheel_ritual.py:41` (`_HAIKU_MODEL`) and `meeting_processor_web.py:48-49` (`_HAIKU_MODEL`, `_SONNET_MODEL`) retain hardcoded constants but are explicitly OUT OF SCOPE for this phase per the phase brief.

---

### Human Verification Required

None. All checks are programmatic for this phase.

---

### Gaps Summary

One gap: the invalid-model fallback behavior in `model_config.py` is incomplete. The function warns on non-`claude-` model strings but then returns the invalid string to the caller (line 85: `return model.strip()` is unconditional). The stated criterion requires falling back to the default. The fix is a one-line change: move the `return model.strip()` inside an `else` clause and add `return ENGINE_DEFAULTS.get(engine_key, default)` in the non-claude branch.

The sync loop not crashing is correctly implemented — the per-email exception handlers in each engine catch Anthropic API errors. But the cleaner behavior (pass a valid model, never reach the API error) requires the fallback fix in `model_config.py`.

---

_Verified: 2026-03-29_
_Verifier: Claude (gsd-verifier)_
