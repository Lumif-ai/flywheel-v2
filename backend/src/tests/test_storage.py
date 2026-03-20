"""Comprehensive tests for storage.py: Postgres-backed context API.

Tests cover: CRUD operations, full-text search, evidence deduplication,
visibility model, soft delete, cross-tenant RLS isolation, and enrichment cache.

All tests require Docker Postgres on port 5434 and are marked with
@pytest.mark.postgres so they can be skipped when Postgres is unavailable.
"""

import datetime

import pytest
from sqlalchemy import text as sa_text

from flywheel.storage import (
    append_entry,
    batch_context,
    get_cached_enrichment,
    query_context,
    read_context,
    set_cached_enrichment,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.postgres,
]


# ---------------------------------------------------------------------------
# TestReadContext
# ---------------------------------------------------------------------------


class TestReadContext:
    """Tests for read_context: reading formatted entries from Postgres."""

    async def test_read_empty_file(self, tenant_a_session):
        """read_context for nonexistent file returns empty string."""
        result = await read_context(tenant_a_session, "nonexistent-file")
        assert result == ""

    async def test_read_single_entry(self, tenant_a_session):
        """Insert one entry, read_context returns correctly formatted v1 string."""
        await append_entry(
            tenant_a_session,
            "company-intel",
            {"detail": "Founded in 2020", "confidence": "high", "content": "Founded in San Francisco"},
            "research-skill",
        )
        await tenant_a_session.commit()

        result = await read_context(tenant_a_session, "company-intel")
        assert "source: research-skill" in result
        assert "Founded in 2020" in result
        assert "confidence: high" in result
        assert "evidence: 1" in result
        assert "- Founded in San Francisco" in result

    async def test_read_multiple_entries_ordered(self, tenant_a_session):
        """Entries ordered by date ASC, then created_at ASC."""
        # Insert two entries (same date, different times via sequential insert)
        await append_entry(
            tenant_a_session,
            "timeline",
            {"detail": "First event", "content": "Event 1"},
            "source-a",
        )
        await append_entry(
            tenant_a_session,
            "timeline",
            {"detail": "Second event", "content": "Event 2"},
            "source-b",
        )
        await tenant_a_session.commit()

        result = await read_context(tenant_a_session, "timeline")
        # Both entries should be present
        assert "First event" in result
        assert "Second event" in result
        # First should appear before second
        pos_first = result.index("First event")
        pos_second = result.index("Second event")
        assert pos_first < pos_second

    async def test_read_excludes_soft_deleted(self, tenant_a_session, admin_session, tenant_ids):
        """Soft-deleted entries not returned by read_context."""
        await append_entry(
            tenant_a_session,
            "deletable",
            {"detail": "Will be deleted", "content": "Temporary data"},
            "test-source",
        )
        await tenant_a_session.commit()

        # Verify it's readable
        result = await read_context(tenant_a_session, "deletable")
        assert "Temporary data" in result

        # Soft-delete via admin session (bypass RLS)
        await admin_session.execute(
            sa_text(
                "UPDATE context_entries SET deleted_at = now() "
                "WHERE file_name = 'deletable' AND tenant_id = :tid"
            ),
            {"tid": tenant_ids["a"]},
        )
        await admin_session.commit()

        # Should no longer appear
        result = await read_context(tenant_a_session, "deletable")
        assert result == ""

    async def test_read_respects_visibility(
        self, tenant_a_session, admin_session, tenant_ids, user_ids
    ):
        """Private entries only visible to their author."""
        # Insert a private entry via admin session (to set visibility=private)
        await admin_session.execute(
            sa_text(
                "INSERT INTO context_entries "
                "(tenant_id, user_id, file_name, source, detail, content, visibility) "
                "VALUES (:tid, :uid, 'private-file', 'test', 'secret', 'Secret data', 'private')"
            ),
            {"tid": tenant_ids["a"], "uid": user_ids["a"]},
        )
        # Insert a private entry by a different user in same tenant
        # Create a temporary user for this test
        import uuid

        other_user = str(uuid.uuid4())
        await admin_session.execute(
            sa_text("INSERT INTO users (id, email) VALUES (:id, :email)"),
            {"id": other_user, "email": f"other-{other_user[:8]}@test.com"},
        )
        await admin_session.execute(
            sa_text(
                "INSERT INTO context_entries "
                "(tenant_id, user_id, file_name, source, detail, content, visibility) "
                "VALUES (:tid, :uid, 'private-file', 'test', 'other secret', 'Other secret', 'private')"
            ),
            {"tid": tenant_ids["a"], "uid": other_user},
        )
        await admin_session.commit()

        # User A should see their own private entry but not the other user's
        result = await read_context(tenant_a_session, "private-file")
        assert "Secret data" in result
        assert "Other secret" not in result

        # Cleanup temp user
        await admin_session.execute(
            sa_text("DELETE FROM context_entries WHERE user_id = :uid"),
            {"uid": other_user},
        )
        await admin_session.execute(
            sa_text("DELETE FROM users WHERE id = :uid"),
            {"uid": other_user},
        )
        await admin_session.commit()


# ---------------------------------------------------------------------------
# TestAppendEntry
# ---------------------------------------------------------------------------


class TestAppendEntry:
    """Tests for append_entry: creating entries with deduplication."""

    async def test_append_basic(self, tenant_a_session, admin_session, tenant_ids):
        """Creates new context_entry row with correct fields."""
        await append_entry(
            tenant_a_session,
            "test-file",
            {"detail": "Test detail", "confidence": "high", "content": "Test content"},
            "test-source",
        )
        await tenant_a_session.commit()

        # Verify via admin session
        result = await admin_session.execute(
            sa_text(
                "SELECT file_name, source, detail, confidence, content, evidence_count "
                "FROM context_entries WHERE tenant_id = :tid AND file_name = 'test-file'"
            ),
            {"tid": tenant_ids["a"]},
        )
        row = result.fetchone()
        assert row is not None
        assert row.source == "test-source"
        assert row.detail == "Test detail"
        assert row.confidence == "high"
        assert row.content == "Test content"
        assert row.evidence_count == 1

    async def test_append_returns_formatted_string(self, tenant_a_session):
        """Return value matches v1 entry format."""
        result = await append_entry(
            tenant_a_session,
            "fmt-test",
            {"detail": "Format test", "confidence": "medium", "content": "Some content here"},
            "fmt-source",
        )
        await tenant_a_session.commit()

        assert "source: fmt-source" in result
        assert "Format test" in result
        assert "confidence: medium" in result
        assert "evidence: 1" in result
        assert "- Some content here" in result

    async def test_append_evidence_dedup(self, tenant_a_session, admin_session, tenant_ids):
        """Same source+detail increments evidence_count instead of creating duplicate."""
        await append_entry(
            tenant_a_session,
            "dedup-test",
            {"detail": "Same detail", "content": "First observation"},
            "dedup-source",
        )
        await tenant_a_session.commit()

        result_str = await append_entry(
            tenant_a_session,
            "dedup-test",
            {"detail": "Same detail", "content": "Second observation"},
            "dedup-source",
        )
        await tenant_a_session.commit()

        # Should show evidence: 2
        assert "evidence: 2" in result_str

        # Only one row in DB
        result = await admin_session.execute(
            sa_text(
                "SELECT count(*) FROM context_entries "
                "WHERE tenant_id = :tid AND file_name = 'dedup-test'"
            ),
            {"tid": tenant_ids["a"]},
        )
        assert result.scalar() == 1

    async def test_append_updates_catalog(self, tenant_a_session, admin_session, tenant_ids):
        """context_catalog status changes to 'active' after append."""
        await append_entry(
            tenant_a_session,
            "catalog-test",
            {"detail": "Catalog update", "content": "Data"},
            "catalog-source",
        )
        await tenant_a_session.commit()

        result = await admin_session.execute(
            sa_text(
                "SELECT status FROM context_catalog "
                "WHERE tenant_id = :tid AND file_name = 'catalog-test'"
            ),
            {"tid": tenant_ids["a"]},
        )
        row = result.fetchone()
        assert row is not None
        assert row.status == "active"

    async def test_append_logs_event(self, tenant_a_session, admin_session, tenant_ids):
        """context_events row created with event_type='entry_added'."""
        await append_entry(
            tenant_a_session,
            "event-test",
            {"detail": "Event logging", "content": "Data"},
            "event-source",
        )
        await tenant_a_session.commit()

        result = await admin_session.execute(
            sa_text(
                "SELECT event_type, file_name FROM context_events "
                "WHERE tenant_id = :tid AND file_name = 'event-test' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"tid": tenant_ids["a"]},
        )
        row = result.fetchone()
        assert row is not None
        assert row.event_type == "entry_added"

    async def test_append_default_confidence(self, tenant_a_session, admin_session, tenant_ids):
        """Confidence defaults to 'medium' when not provided."""
        await append_entry(
            tenant_a_session,
            "default-conf",
            {"detail": "No confidence specified", "content": "Data"},
            "default-source",
        )
        await tenant_a_session.commit()

        result = await admin_session.execute(
            sa_text(
                "SELECT confidence FROM context_entries "
                "WHERE tenant_id = :tid AND file_name = 'default-conf'"
            ),
            {"tid": tenant_ids["a"]},
        )
        assert result.scalar() == "medium"


# ---------------------------------------------------------------------------
# TestQueryContext
# ---------------------------------------------------------------------------


class TestQueryContext:
    """Tests for query_context: filtering and full-text search."""

    async def _seed_entries(self, session):
        """Helper to seed multiple entries for query tests."""
        entries = [
            {"detail": "Revenue growth", "confidence": "high", "content": "Revenue grew 30% YoY"},
            {"detail": "Team size", "confidence": "medium", "content": "Engineering team of 50"},
            {"detail": "Product launch", "confidence": "low", "content": "New product launched Q4"},
        ]
        for e in entries:
            await append_entry(session, "query-file", e, "research")
        await session.commit()

    async def test_query_no_filters(self, tenant_a_session):
        """Returns all entries for file when no filters specified."""
        await self._seed_entries(tenant_a_session)
        results = await query_context(tenant_a_session, "query-file")
        assert len(results) == 3

    async def test_query_since(self, tenant_a_session):
        """Filters by date >= since."""
        await self._seed_entries(tenant_a_session)
        # All entries have today's date, so tomorrow should return nothing
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        results = await query_context(tenant_a_session, "query-file", since=tomorrow)
        assert len(results) == 0

        # Today should return all
        today = datetime.date.today().isoformat()
        results = await query_context(tenant_a_session, "query-file", since=today)
        assert len(results) == 3

    async def test_query_source(self, tenant_a_session):
        """Filters by source (case-insensitive partial match)."""
        await self._seed_entries(tenant_a_session)
        results = await query_context(tenant_a_session, "query-file", source="Research")
        assert len(results) == 3

        results = await query_context(tenant_a_session, "query-file", source="nonexistent")
        assert len(results) == 0

    async def test_query_keyword(self, tenant_a_session):
        """Filters by content keyword (case-insensitive)."""
        await self._seed_entries(tenant_a_session)
        results = await query_context(tenant_a_session, "query-file", keyword="revenue")
        assert len(results) == 1
        assert results[0]["detail"] == "Revenue growth"

    async def test_query_min_confidence(self, tenant_a_session):
        """High >= medium >= low filtering."""
        await self._seed_entries(tenant_a_session)

        # min_confidence=high should only return high
        results = await query_context(tenant_a_session, "query-file", min_confidence="high")
        assert len(results) == 1
        assert results[0]["confidence"] == "high"

        # min_confidence=medium should return high + medium
        results = await query_context(tenant_a_session, "query-file", min_confidence="medium")
        assert len(results) == 2

        # min_confidence=low should return all
        results = await query_context(tenant_a_session, "query-file", min_confidence="low")
        assert len(results) == 3

    async def test_query_full_text_search(self, tenant_a_session):
        """Full-text search via tsvector returns ranked results."""
        await self._seed_entries(tenant_a_session)
        results = await query_context(tenant_a_session, "query-file", search="revenue growth")
        assert len(results) >= 1
        # The revenue entry should rank highest
        assert results[0]["detail"] == "Revenue growth"

    async def test_query_combined_filters(self, tenant_a_session):
        """Multiple filters applied together."""
        await self._seed_entries(tenant_a_session)
        results = await query_context(
            tenant_a_session,
            "query-file",
            source="research",
            min_confidence="medium",
        )
        # Should return high + medium entries from "research" source
        assert len(results) == 2


# ---------------------------------------------------------------------------
# TestBatchContext
# ---------------------------------------------------------------------------


class TestBatchContext:
    """Tests for batch_context: atomic batch writes."""

    async def test_batch_writes_atomically(self, tenant_a_session):
        """All writes succeed together."""
        async with batch_context(tenant_a_session, "batch-source") as batch:
            batch.append_entry("batch-file", {"detail": "Entry 1", "content": "Data 1"})
            batch.append_entry("batch-file", {"detail": "Entry 2", "content": "Data 2"})
        await tenant_a_session.commit()

        result = await read_context(tenant_a_session, "batch-file")
        assert "Entry 1" in result
        assert "Entry 2" in result

    async def test_batch_rollback_on_error(self, tenant_a_session, admin_session, tenant_ids):
        """Exception rolls back all writes."""
        try:
            async with batch_context(tenant_a_session, "rollback-source") as batch:
                batch.append_entry(
                    "rollback-file", {"detail": "Should not persist", "content": "Data"}
                )
                raise ValueError("Intentional error")
        except ValueError:
            await tenant_a_session.rollback()

        # Nothing should have been written
        result = await admin_session.execute(
            sa_text(
                "SELECT count(*) FROM context_entries "
                "WHERE tenant_id = :tid AND file_name = 'rollback-file'"
            ),
            {"tid": tenant_ids["a"]},
        )
        assert result.scalar() == 0

    async def test_batch_multiple_files(self, tenant_a_session):
        """Writes to different files in one transaction."""
        async with batch_context(tenant_a_session, "multi-source") as batch:
            batch.append_entry("file-alpha", {"detail": "Alpha", "content": "Alpha data"})
            batch.append_entry("file-beta", {"detail": "Beta", "content": "Beta data"})
        await tenant_a_session.commit()

        alpha = await read_context(tenant_a_session, "file-alpha")
        beta = await read_context(tenant_a_session, "file-beta")
        assert "Alpha data" in alpha
        assert "Beta data" in beta


# ---------------------------------------------------------------------------
# TestCrossTenantIsolation
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    """Tests for cross-tenant RLS isolation."""

    async def test_tenant_a_cannot_read_tenant_b(
        self, tenant_a_session, tenant_b_session
    ):
        """Tenant A's read_context returns nothing for Tenant B's data."""
        # Tenant B writes an entry
        await append_entry(
            tenant_b_session,
            "tenant-b-file",
            {"detail": "Tenant B secret", "content": "B's data"},
            "b-source",
        )
        await tenant_b_session.commit()

        # Tenant A should see nothing
        result = await read_context(tenant_a_session, "tenant-b-file")
        assert result == ""

    async def test_tenant_a_cannot_write_to_tenant_b(
        self, tenant_a_session, admin_session, tenant_ids
    ):
        """Tenant A cannot insert with Tenant B's tenant_id (RLS blocks)."""
        # Try to insert directly with Tenant B's ID via Tenant A's session
        try:
            await tenant_a_session.execute(
                sa_text(
                    "INSERT INTO context_entries "
                    "(tenant_id, user_id, file_name, source, content) "
                    "VALUES (:tid, :uid, 'hack-attempt', 'hacker', 'Injected')"
                ),
                {
                    "tid": tenant_ids["b"],
                    "uid": tenant_ids["a"],  # Doesn't matter
                },
            )
            await tenant_a_session.commit()
            # If we get here, RLS didn't block -- fail the test
            pytest.fail("RLS should have blocked cross-tenant INSERT")
        except Exception:
            await tenant_a_session.rollback()

        # Verify nothing was inserted
        result = await admin_session.execute(
            sa_text(
                "SELECT count(*) FROM context_entries "
                "WHERE file_name = 'hack-attempt'"
            ),
        )
        assert result.scalar() == 0

    async def test_cross_tenant_query(self, tenant_a_session, tenant_b_session):
        """query_context only returns current tenant's entries."""
        # Both tenants write to same file name
        await append_entry(
            tenant_a_session,
            "shared-name",
            {"detail": "A's data", "content": "Tenant A info"},
            "a-source",
        )
        await tenant_a_session.commit()

        await append_entry(
            tenant_b_session,
            "shared-name",
            {"detail": "B's data", "content": "Tenant B info"},
            "b-source",
        )
        await tenant_b_session.commit()

        # Tenant A only sees their own
        results = await query_context(tenant_a_session, "shared-name")
        assert len(results) == 1
        assert results[0]["detail"] == "A's data"

        # Tenant B only sees their own
        results = await query_context(tenant_b_session, "shared-name")
        assert len(results) == 1
        assert results[0]["detail"] == "B's data"

    async def test_all_tables_have_rls(self, admin_session):
        """Verify all 9 tenant-scoped tables have relrowsecurity=true."""
        result = await admin_session.execute(
            sa_text(
                "SELECT relname FROM pg_class "
                "WHERE relname IN ("
                "  'context_entries', 'context_catalog', 'context_events', "
                "  'enrichment_cache', 'skill_runs', 'uploaded_files', "
                "  'work_items', 'onboarding_sessions', 'user_tenants'"
                ") AND relrowsecurity = true"
            ),
        )
        rows = result.fetchall()
        rls_tables = {r.relname for r in rows}
        expected = {
            "context_entries",
            "context_catalog",
            "context_events",
            "enrichment_cache",
            "skill_runs",
            "uploaded_files",
            "work_items",
            "onboarding_sessions",
            "user_tenants",
        }
        assert rls_tables == expected, f"Missing RLS on: {expected - rls_tables}"


# ---------------------------------------------------------------------------
# TestEnrichmentCache
# ---------------------------------------------------------------------------


class TestEnrichmentCache:
    """Tests for enrichment cache: TTL, dedup, get/set."""

    async def test_cache_set_and_get(self, tenant_a_session, tenant_ids):
        """Store and retrieve within TTL."""
        data = {"companies": ["Acme", "Globex"]}
        await set_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "find tech companies", data
        )
        await tenant_a_session.commit()

        result = await get_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "find tech companies"
        )
        assert result is not None
        assert result["companies"] == ["Acme", "Globex"]

    async def test_cache_expired(self, tenant_a_session, admin_session, tenant_ids):
        """Entry older than 24h returns None."""
        data = {"old": True}
        await set_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "expired query", data
        )
        await tenant_a_session.commit()

        # Backdate the entry via admin session
        await admin_session.execute(
            sa_text(
                "UPDATE enrichment_cache SET created_at = now() - interval '25 hours' "
                "WHERE tenant_id = :tid"
            ),
            {"tid": tenant_ids["a"]},
        )
        await admin_session.commit()

        result = await get_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "expired query"
        )
        assert result is None

    async def test_cache_dedup(self, tenant_a_session, tenant_ids):
        """Same query text (case-insensitive) returns same cached entry."""
        data1 = {"version": 1}
        data2 = {"version": 2}

        await set_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "Find Companies", data1
        )
        await tenant_a_session.commit()

        # Same query, different case -- should upsert
        await set_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "find companies", data2
        )
        await tenant_a_session.commit()

        result = await get_cached_enrichment(
            tenant_a_session, tenant_ids["a"], "FIND COMPANIES"
        )
        assert result is not None
        assert result["version"] == 2


# ---------------------------------------------------------------------------
# TestSoftDelete
# ---------------------------------------------------------------------------


class TestSoftDelete:
    """Tests for soft delete behavior."""

    async def test_soft_delete_entry(self, tenant_a_session, admin_session, tenant_ids):
        """Setting deleted_at hides from read_context."""
        await append_entry(
            tenant_a_session,
            "soft-del",
            {"detail": "To delete", "content": "Will be soft-deleted"},
            "del-source",
        )
        await tenant_a_session.commit()

        # Soft delete
        await admin_session.execute(
            sa_text(
                "UPDATE context_entries SET deleted_at = now() "
                "WHERE tenant_id = :tid AND file_name = 'soft-del'"
            ),
            {"tid": tenant_ids["a"]},
        )
        await admin_session.commit()

        result = await read_context(tenant_a_session, "soft-del")
        assert result == ""

    async def test_soft_delete_still_in_db(self, tenant_a_session, admin_session, tenant_ids):
        """Admin session can see soft-deleted entries."""
        await append_entry(
            tenant_a_session,
            "preserved",
            {"detail": "Still there", "content": "Preserved data"},
            "preserve-source",
        )
        await tenant_a_session.commit()

        # Soft delete and verify in one transaction
        update_result = await admin_session.execute(
            sa_text(
                "UPDATE context_entries SET deleted_at = now() "
                "WHERE tenant_id = :tid AND file_name = 'preserved'"
            ),
            {"tid": tenant_ids["a"]},
        )
        assert update_result.rowcount == 1, "UPDATE should have affected 1 row"

        # Admin can still see it (same transaction, before commit)
        result = await admin_session.execute(
            sa_text(
                "SELECT content, deleted_at FROM context_entries "
                "WHERE tenant_id = :tid AND file_name = 'preserved'"
            ),
            {"tid": tenant_ids["a"]},
        )
        row = result.fetchone()
        assert row is not None, "Superuser should see soft-deleted entries"
        assert row.content == "Preserved data"
        assert row.deleted_at is not None, "deleted_at should be set"
        await admin_session.commit()

    async def test_soft_delete_hides_from_query(
        self, tenant_a_session, admin_session, tenant_ids
    ):
        """query_context excludes soft-deleted entries."""
        await append_entry(
            tenant_a_session,
            "query-del",
            {"detail": "Queryable", "content": "Active entry"},
            "qdel-source",
        )
        await append_entry(
            tenant_a_session,
            "query-del",
            {"detail": "Hidden", "content": "Deleted entry"},
            "qdel-source-2",
        )
        await tenant_a_session.commit()

        # Soft delete the second entry
        await admin_session.execute(
            sa_text(
                "UPDATE context_entries SET deleted_at = now() "
                "WHERE tenant_id = :tid AND file_name = 'query-del' AND detail = 'Hidden'"
            ),
            {"tid": tenant_ids["a"]},
        )
        await admin_session.commit()

        results = await query_context(tenant_a_session, "query-del")
        assert len(results) == 1
        assert results[0]["detail"] == "Queryable"


# ---------------------------------------------------------------------------
# TestVisibilityModel
# ---------------------------------------------------------------------------


class TestVisibilityModel:
    """Tests for visibility: shared/team/private."""

    async def test_shared_visible_to_all(self, admin_session, tenant_a_session, tenant_ids, user_ids):
        """Shared entries visible to all tenant members."""
        await admin_session.execute(
            sa_text(
                "INSERT INTO context_entries "
                "(tenant_id, user_id, file_name, source, detail, content, visibility) "
                "VALUES (:tid, :uid, 'vis-shared', 'test', 'Shared item', 'Shared data', 'shared')"
            ),
            {"tid": tenant_ids["a"], "uid": user_ids["a"]},
        )
        await admin_session.commit()

        result = await read_context(tenant_a_session, "vis-shared")
        assert "Shared data" in result

    async def test_team_visible_to_all(self, admin_session, tenant_a_session, tenant_ids, user_ids):
        """Team entries visible to all tenant members."""
        await admin_session.execute(
            sa_text(
                "INSERT INTO context_entries "
                "(tenant_id, user_id, file_name, source, detail, content, visibility) "
                "VALUES (:tid, :uid, 'vis-team', 'test', 'Team item', 'Team data', 'team')"
            ),
            {"tid": tenant_ids["a"], "uid": user_ids["a"]},
        )
        await admin_session.commit()

        result = await read_context(tenant_a_session, "vis-team")
        assert "Team data" in result

    async def test_private_only_visible_to_author(
        self, admin_session, tenant_a_session, tenant_ids, user_ids, pg_session_factory
    ):
        """Private entries only visible to the user who created them."""
        import uuid

        other_user = str(uuid.uuid4())
        await admin_session.execute(
            sa_text("INSERT INTO users (id, email) VALUES (:id, :email)"),
            {"id": other_user, "email": f"vis-{other_user[:8]}@test.com"},
        )
        await admin_session.execute(
            sa_text(
                "INSERT INTO user_tenants (user_id, tenant_id, role, active) "
                "VALUES (:uid, :tid, 'member', true) ON CONFLICT DO NOTHING"
            ),
            {"uid": other_user, "tid": tenant_ids["a"]},
        )

        # Insert private entry owned by other_user
        await admin_session.execute(
            sa_text(
                "INSERT INTO context_entries "
                "(tenant_id, user_id, file_name, source, detail, content, visibility) "
                "VALUES (:tid, :uid, 'vis-private', 'test', 'Private item', 'Private data', 'private')"
            ),
            {"tid": tenant_ids["a"], "uid": other_user},
        )
        await admin_session.commit()

        # User A should NOT see other_user's private entry
        result = await read_context(tenant_a_session, "vis-private")
        assert "Private data" not in result

        # But the other user (same tenant) CAN see their own private entry
        from flywheel.db.session import get_tenant_session

        other_session = await get_tenant_session(pg_session_factory, tenant_ids["a"], other_user)
        try:
            result = await read_context(other_session, "vis-private")
            assert "Private data" in result
        finally:
            await other_session.close()

        # Cleanup
        await admin_session.execute(
            sa_text("DELETE FROM context_entries WHERE user_id = :uid"),
            {"uid": other_user},
        )
        await admin_session.execute(
            sa_text("DELETE FROM user_tenants WHERE user_id = :uid"),
            {"uid": other_user},
        )
        await admin_session.execute(
            sa_text("DELETE FROM users WHERE id = :uid"),
            {"uid": other_user},
        )
        await admin_session.commit()
