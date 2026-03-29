---
phase: 58-unified-company-intelligence-engine
verified: 2026-03-27T15:29:45Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 58: Unified Company Intelligence Engine Verification Report

**Phase Goal:** Document uploads and URL crawls flow through a single skill engine with intelligence-driven enrichment. The document upload parallel path is eliminated. Founders can refresh or reset their company profile from the profile page.
**Verified:** 2026-03-27T15:29:45Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_execute_company_intel()` accepts `DOCUMENT_FILE:{uuid}` input and skips crawl, goes straight to structuring | VERIFIED | `DOCUMENT_FILE_PREFIX = "DOCUMENT_FILE:"` at line 843 of skill_executor.py; `is_document` branch at line 864 skips the crawl_company call entirely and fetches `extracted_text` from DB with RLS |
| 2 | `POST /profile/analyze-document` creates a SkillRun and routes through the company-intel engine — no more background enrichment side path | VERIFIED | profile.py lines 339–351: creates `SkillRun(skill_name="company-intel", input_text=f"DOCUMENT_FILE:{body.file_id}", status="pending")`, returns `{"run_id": ...}`. `_run_background_enrichment` confirmed absent (0 matches). |
| 3 | Enrichment prompt reads existing profile entries and focuses research on gaps — not the same 10 generic searches every time | VERIFIED | `_get_existing_profile_keys` at company_intel.py line 84 queries `context_entries` for populated `file_name` values; `enrich_with_web_research` at line 445 accepts `existing_profile_keys` and emits `(SKIP - already have)` prefixes (line 487) and a `gap_notice` block (lines 497–503) |
| 4 | `POST /profile/refresh` re-runs the skill with tenant URL + all linked document content, dedup merges with existing data | VERIFIED | profile.py lines 359–410: aggregates `https://{tenant.domain}` + `DOCUMENT_FILE:{id}` for every `profile_linked` file into a single SkillRun `input_text`; skill_executor SUPPLEMENTARY_DOCS parsing handles the multi-line format |
| 5 | `POST /profile/reset` soft-deletes all `company-intel-onboarding` entries, then runs the same refresh flow | VERIFIED | profile.py lines 418–445: `sa_update(ContextEntry).values(deleted_at=datetime.datetime.now(...))` where `source == "company-intel-onboarding"`, then calls `refresh_profile()` directly |
| 6 | Frontend profile page shows Refresh and Reset buttons — both display the existing SSE discovery streaming UI during execution | VERIFIED | CompanyProfilePage.tsx line 718–774: Refresh + Reset buttons rendered when `hasGroups`; lines 848–860: `LiveCrawl` overlay shown when `refresh.phase === 'refreshing' \| 'complete'`; `useProfileRefresh` hook connects to `/api/v1/skills/runs/{run_id}/stream` via `useSSE` |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/flywheel/services/skill_executor.py` | URL vs document discriminator, SUPPLEMENTARY_DOCS parsing, gap-aware enrichment call | VERIFIED | `DOCUMENT_FILE_PREFIX` constant at line 843; `is_document` flag; `supplementary_file_ids` loop; `_get_existing_profile_keys` called at line 988; `existing_profile_keys=existing_keys` passed to `enrich_with_web_research` at line 997 |
| `backend/src/flywheel/engines/company_intel.py` | Gap-aware enrichment helper that reads existing profile before researching | VERIFIED | `_get_existing_profile_keys` at line 84; `enrich_with_web_research` signature accepts `existing_profile_keys: set \| None = None` at line 445; `(SKIP - already have)` prefix logic at line 487 |
| `backend/src/flywheel/api/profile.py` | Unified SkillRun-routed analyze-document, refresh, and reset endpoints | VERIFIED | `analyze_document` at line 314, `refresh_profile` at line 360, `reset_profile` at line 419; all confirmed substantive (not stubs); dead code `_run_background_enrichment`, `_build_enrichment_section_map`, `retry-enrichment`, `RetryEnrichmentRequest` all absent (0 grep matches) |
| `frontend/src/features/profile/hooks/useProfileRefresh.ts` | Hook with startRefresh(), startReset(), startFromRunId(), dismiss() | VERIFIED | File created (184 lines); all four actions implemented; POSTs to `/profile/refresh` and `/profile/reset`; SSE URL set to `/api/v1/skills/runs/{run_id}/stream`; handles `discovery`, `stage`, `done`, `crawl_error`, `error` event types |
| `frontend/src/features/profile/components/CompanyProfilePage.tsx` | Refresh and Reset buttons, inline reset confirmation, SSE overlay | VERIFIED | `useProfileRefresh` imported at line 3 and wired at line 621; Refresh button at line 720 calls `startRefresh()`; Reset button at line 733 opens inline confirmation; `resetConfirm` block at lines 814–845 calls `startReset()` on confirm; `LiveCrawl` overlay at lines 848–860 |
| `frontend/src/lib/sse.ts` | `discovery` event type in SSEEventType union and listener registration | VERIFIED | `'discovery'` added to `SSEEventType` union at line 4 and to `eventTypes` array at line 35 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `skill_executor._execute_company_intel` | `enrich_with_web_research` | `existing_profile_keys` kwarg | WIRED | Line 997: `api_key=api_key, existing_profile_keys=existing_keys` |
| `skill_executor._execute_company_intel` | `UploadedFile.extracted_text` | DB lookup when input starts with `DOCUMENT_FILE:` | WIRED | Lines 866–903: extracts UUID from prefix, opens factory session with RLS, fetches `UploadedFile`, reads `.extracted_text` |
| `POST /profile/analyze-document` | `SkillRun(input_text=DOCUMENT_FILE:{id})` | creates pending SkillRun | WIRED | Line 343: `input_text=f"DOCUMENT_FILE:{body.file_id}"` |
| `POST /profile/refresh` | `SkillRun(input_text=url + DOCUMENT_FILE refs)` | multi-line input aggregation | WIRED | Lines 387–396: builds `input_lines` list with URL + per-file `DOCUMENT_FILE:{id}` entries |
| `POST /profile/reset` | `ContextEntry.deleted_at` | soft-delete UPDATE then calls refresh_profile | WIRED | Line 434: `.values(deleted_at=datetime.datetime.now(datetime.timezone.utc))`; line 440: `await refresh_profile(user=user, db=db)` |
| `useProfileRefresh.startRefresh` | `POST /profile/refresh` | `api.post` returning run_id | WIRED | Line 119: `api.post<{ run_id: string }>('/profile/refresh', {})` |
| `useProfileRefresh.startReset` | `POST /profile/reset` | `api.post` returning run_id | WIRED | Lines 139–142: `api.post<{ run_id: string; deleted_count?: number }>('/profile/reset', {})` |
| `useProfileRefresh SSE` | `/api/v1/skills/runs/{run_id}/stream` | `setSseUrl` after getting run_id | WIRED | Lines 120, 143, 160: all three actions set `setSseUrl(\`/api/v1/skills/runs/${...}/stream\`)` |
| `CompanyProfilePage` | `LiveCrawl` | renders LiveCrawl when refreshPhase is active | WIRED | Lines 848–860: `{(refresh.phase === 'refreshing' \|\| refresh.phase === 'complete') ? <LiveCrawl ...>}` |
| `DocumentAnalyzePanel` | `useProfileRefresh.startFromRunId` | `onRunStarted` callback | WIRED | Line 548: `onRunStarted?.(result.run_id)`; line 876: `<DocumentAnalyzePanel onRunStarted={(runId) => refresh.startFromRunId(runId)} />` |

---

## Requirements Coverage

All 6 success criteria from the ROADMAP.md are satisfied:

| Requirement | Status | Notes |
|-------------|--------|-------|
| `_execute_company_intel()` accepts both URLs and document text | SATISFIED | Three input formats handled: DOCUMENT_FILE (skips crawl), URL+SUPPLEMENTARY_DOCS, plain URL |
| `POST /profile/analyze-document` routes through company-intel engine | SATISFIED | No inline structuring — pure SkillRun creation |
| Enrichment prompt reads existing profile entries and focuses on gaps | SATISFIED | `_get_existing_profile_keys` + gap notice + SKIP prefixes in prompt |
| `POST /profile/refresh` re-runs with tenant URL + all linked docs | SATISFIED | Aggregated multi-line input_text; uses existing SUPPLEMENTARY_DOCS parsing |
| `POST /profile/reset` soft-deletes then refreshes | SATISFIED | `deleted_at` soft-delete + direct `refresh_profile()` call |
| Frontend Refresh and Reset buttons with SSE streaming | SATISFIED | Buttons gated on `hasGroups`; LiveCrawl overlay; inline reset confirmation |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `skill_executor.py` | 2139 | `TODO: Remove filesystem fallback after confirming all skills are seeded` | Info | Pre-existing; unrelated to phase 58 changes |

No anti-patterns in the phase 58 modified code.

---

## Assumptions Made (Need Confirmation)

No SPEC-GAPS.md found in the project. No unresolved assumptions logged.

---

## Human Verification Required

### 1. End-to-end Refresh flow

**Test:** On the profile page with existing company data, click Refresh. Confirm the LiveCrawl overlay appears with real-time discovery events streaming in. Confirm profile data is updated after completion.
**Expected:** SSE `discovery` events render as CrawlItem cards in LiveCrawl. On `done` event the overlay shows a completion state with a Continue button. Clicking Continue returns to the normal profile view with refreshed data.
**Why human:** SSE event rendering, animation quality, and post-completion data refresh require a live browser session.

### 2. End-to-end Reset flow

**Test:** Click Reset, observe the inline confirmation banner, click Confirm Reset. Confirm the LiveCrawl overlay appears. After completion, confirm that old profile data was cleared and new data has been rebuilt.
**Expected:** Previous profile entries (leadership, tech stack, etc.) are gone immediately on confirmation; the rebuilt profile reflects only what the current run found.
**Why human:** The soft-delete + rebuild sequence involves timing-sensitive DB state that can only be confirmed visually in the app.

### 3. Document-only profile (no URL)

**Test:** For a tenant with no domain but a linked PDF, trigger Refresh. Confirm the engine picks up the `DOCUMENT_FILE:` input on the first line and skips crawl.
**Expected:** No crawl attempt; profile populated from document text only.
**Why human:** Requires a test tenant with no domain configured, and observing the SSE stream events to confirm absence of crawl stage events.

---

## Summary

Phase 58 goal is fully achieved. All six success criteria from the ROADMAP verify against actual code:

- The document upload parallel path (inline `structure_intelligence` + `_run_background_enrichment`) has been eliminated. Dead code confirmed absent (0 matches for `_run_background_enrichment`, `retry_enrichment`, `RetryEnrichmentRequest`, `categories_written`).
- The unified `_execute_company_intel` engine now handles three input formats via a discriminator at function entry (`DOCUMENT_FILE:` prefix detection).
- Gap-aware enrichment is fully wired: `_get_existing_profile_keys` queries the DB before every enrichment call; the prompt skips already-populated categories and reduces `max_uses` when the profile is already rich.
- Three new API endpoints (`analyze-document` rewrite, `refresh`, `reset`) all create pending SkillRuns and return `run_id` — no inline processing.
- The frontend `useProfileRefresh` hook and CompanyProfilePage UI are substantive (not stubs): buttons are conditionally rendered, the inline reset confirmation is implemented, and the LiveCrawl SSE overlay replaces the profile body during execution.
- The `discovery` event type fix to `sse.ts` ensures SSE events from the skills/runs stream are not silently dropped — this was a critical auto-fix caught and committed in plan 03.

All three commits (`398f790`, `174c0f2`, `8ca2ad7`) are verified present in git history.

---

_Verified: 2026-03-27T15:29:45Z_
_Verifier: Claude (gsd-verifier)_
