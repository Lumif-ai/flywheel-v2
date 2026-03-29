---
phase: 60-meeting-data-model-and-granola-adapter
verified: 2026-03-28T00:55:07Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 60: Meeting Data Model and Granola Adapter Verification Report

**Phase Goal:** The meetings table exists with split-visibility RLS, Granola is connected as an integration with encrypted API key, and meetings can be synced from Granola into the database with dedup. No processing yet — just the data foundation and sync pipeline.
**Verified:** 2026-03-28T00:55:07Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | meetings table exists with all 20 columns from MDE-01 | VERIFIED | `032_create_meetings_table.py` creates all 20 columns; `Meeting` ORM has all 20 `Mapped[]` fields |
| 2 | Dedup unique index prevents duplicate external_id per tenant+provider | VERIFIED | `idx_meetings_dedup` UNIQUE on (tenant_id, provider, external_id) WHERE external_id IS NOT NULL — in both migration and ORM `__table_args__` |
| 3 | RLS enforces tenant-read (SELECT) and owner-write (ALL) | VERIFIED | `meetings_tenant_read FOR SELECT` and `meetings_owner_write FOR ALL` with both `USING` and `WITH CHECK` using `current_setting('app.tenant_id/user_id', true)` |
| 4 | Meeting ORM model is importable and matches table schema | VERIFIED | `class Meeting(Base)` at line 1245 of `models.py`; 20 columns + 4 index definitions + 2 relationships (account, skill_run) |
| 5 | GranolaAdapter can test, list, and fetch full meeting content | VERIFIED | `granola_adapter.py` has `test_connection`, `list_meetings`, `get_meeting_content` using real base URL `https://public-api.granola.ai/v1` |
| 6 | User can connect Granola via POST /integrations/granola/connect with encrypted API key | VERIFIED | Endpoint at line 612 of `integrations.py`: validates key, calls `encrypt_api_key`, upserts Integration row, returns `{"status": "connected"}` |
| 7 | POST /meetings/sync pulls meetings from Granola with dedup by external_id | VERIFIED | `meetings.py` queries existing external_ids before insert; skips duplicates without error |
| 8 | New meetings created with processing_status='pending' (or 'skipped') | VERIFIED | `_apply_processing_rules()` returns "pending" or "skipped"; Meeting row uses `processing_status=status` |
| 9 | Integration.last_synced_at updated after successful sync | VERIFIED | Line 164 of `meetings.py`: `integration.last_synced_at = datetime.now(timezone.utc)` before commit |
| 10 | meetings_router registered in main.py at /api/v1 prefix | VERIFIED | Line 50 imports `meetings_router`; line 199 calls `app.include_router(meetings_router, prefix="/api/v1")` |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/032_create_meetings_table.py` | Migration: meetings table, indexes, split-visibility RLS, GRANT | VERIFIED | 159 lines; creates table, 4 partial indexes, 2 RLS policies, GRANT to app_user; downgrade drops all |
| `backend/src/flywheel/db/models.py` | Meeting ORM class in CRM TABLES section | VERIFIED | `class Meeting(Base)` at line 1245; all 20 Mapped[] fields; 4 index definitions in `__table_args__` |
| `backend/src/flywheel/services/granola_adapter.py` | Granola adapter with test_connection, list_meetings, get_meeting_content | VERIFIED | 176 lines; correct real API URL; `RawMeeting`/`MeetingContent` dataclasses; all 3 async functions |
| `backend/src/flywheel/api/integrations.py` | POST /integrations/granola/connect endpoint | VERIFIED | `connect_granola` at line 612; validates, encrypts, upserts; "granola" in `_PROVIDER_DISPLAY` |
| `backend/src/flywheel/api/meetings.py` | POST /meetings/sync endpoint with dedup pipeline | VERIFIED | 175 lines; full pipeline: find integration, decrypt key, fetch, dedup, insert, update cursor, return stats |
| `backend/src/flywheel/main.py` | meetings router registered | VERIFIED | Import at line 50; include_router at line 199 with `/api/v1` prefix |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `032_create_meetings_table.py` | `031_user_level_rls` | `down_revision` chain | WIRED | `down_revision = "031_user_level_rls"` confirmed; 031 file exists; no other migration branches from 031 (single head) |
| `models.py Meeting` | `accounts`, `skill_runs` | ForeignKey references | WIRED | `ForeignKey("accounts.id", ondelete="SET NULL")` and `ForeignKey("skill_runs.id")` present |
| `integrations.py` | `granola_adapter.py` | `import test_connection` | WIRED | Line 631: `from flywheel.services.granola_adapter import test_connection` (local import inside endpoint) |
| `integrations.py` | `auth/encryption.py` | `encrypt_api_key` | WIRED | Line 31: `from flywheel.auth.encryption import encrypt_api_key`; used at line 637 |
| `meetings.py` | `granola_adapter.py` | `import list_meetings, RawMeeting` | WIRED | Line 19: `from flywheel.services.granola_adapter import RawMeeting, list_meetings`; `list_meetings` called at line 119 |
| `meetings.py` | `models.py` | `import Meeting, Integration` | WIRED | Line 18: `from flywheel.db.models import Integration, Meeting`; both used in sync pipeline |
| `meetings.py` | `auth/encryption.py` | `decrypt_api_key` | WIRED | Line 16: `from flywheel.auth.encryption import decrypt_api_key`; called at line 116 |
| `main.py` | `meetings.py` | `include_router` | WIRED | Import at line 50; `app.include_router(meetings_router, prefix="/api/v1")` at line 199 |

### Requirements Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| meetings table with tenant-level RLS for metadata, transcript stored in Supabase Storage | SATISFIED | tenant_read FOR SELECT for metadata; transcript_url column stores Supabase Storage URL path (upload not in scope for phase 60) |
| User can connect Granola via API key — key encrypted in Integration table | SATISFIED | POST /integrations/granola/connect validates, encrypts with AES-256-GCM, upserts Integration row |
| POST /meetings/sync pulls from Granola, dedup by external_id, creates rows with processing_status='pending' | SATISFIED | Full pipeline implemented; dedup via SELECT external_id IN (fetched_ids) before insert |
| Synced meetings show title, date, attendees, provider | SATISFIED | Meeting row set with provider="granola", title=raw.title, meeting_date=raw.meeting_date, attendees=raw.attendees |

### Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER comments, no stub return values, no empty implementations found in any of the four new files.

### Assumptions Made (Need Confirmation)

No SPEC-GAPS.md exists in this project. No open assumptions flagged.

### Human Verification Required

#### 1. Granola API key validation (live API)

**Test:** Obtain a real Granola API key, POST to `/api/v1/integrations/granola/connect` with `{"api_key": "<key>"}`.
**Expected:** Returns `{"status": "connected"}`; Integration row created in DB with encrypted credentials.
**Why human:** Cannot call the live `https://public-api.granola.ai/v1` API in static analysis.

#### 2. End-to-end sync with real data

**Test:** After connecting Granola, POST to `/api/v1/meetings/sync`.
**Expected:** Returns `{"synced": N, "skipped": 0, "already_seen": 0, "total_from_provider": N}`; Meeting rows appear in DB with title, meeting_date, attendees, provider="granola", processing_status="pending".
**Why human:** Requires live Granola account with meeting data.

#### 3. Dedup on second sync

**Test:** POST to `/api/v1/meetings/sync` a second time without any new meetings.
**Expected:** Returns `{"synced": 0, "skipped": 0, "already_seen": N, "total_from_provider": N}`; no duplicate Meeting rows.
**Why human:** Requires live state from first sync.

#### 4. RLS split-visibility behavior

**Test:** Two users in same tenant; user A creates a meeting. User B (same tenant) queries meetings table directly.
**Expected:** User B can SELECT the meeting (tenant_read policy). User B cannot INSERT/UPDATE/DELETE the meeting (owner_write policy checks user_id).
**Why human:** Requires running PostgreSQL with RLS-enforcing session variables set.

### Gaps Summary

No gaps. All four success criteria from the phase goal are satisfied:

1. meetings table exists with 20 columns, 4 partial indexes, and split-visibility RLS (2 policies: tenant_read FOR SELECT + owner_write FOR ALL).
2. Granola connect endpoint encrypts API key with AES-256-GCM and upserts the Integration row.
3. POST /meetings/sync implements the full pipeline: fetch from Granola, dedup by (tenant_id, provider, external_id), insert new rows with processing_status='pending' or 'skipped'.
4. Synced Meeting rows contain title, meeting_date, attendees, and provider="granola".

All commits verified in git log: `7243b71` (plan 01), `e0fe408` (plan 02), `86c0d9f` (plan 03).

---

_Verified: 2026-03-28T00:55:07Z_
_Verifier: Claude (gsd-verifier)_
