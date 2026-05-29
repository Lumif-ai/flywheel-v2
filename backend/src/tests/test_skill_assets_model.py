"""Round-trip and cascade regression tests for skill_assets table.

Locks in Phase 146 success criteria 2 (bytea round-trip: inserted
bundle + sha256 + size read back intact) and 3 (FK ON DELETE CASCADE
from skill_definitions to skill_assets).

Requires Docker Postgres on port 5434. The @pytest.mark.postgres
marker makes these tests skip cleanly on machines without Docker,
so CI environments without the test DB don't false-fail.

Phase 146 — v22.0 Skill Platform Consolidation.
"""
import hashlib
import uuid

import pytest
from sqlalchemy import text as sa_text


pytestmark = [pytest.mark.asyncio, pytest.mark.postgres]


async def test_bytea_round_trip(admin_session):
    """SC2: Insert a bundle, read it back, verify SHA-256 and size match."""
    skill_id = str(uuid.uuid4())
    await admin_session.execute(
        sa_text("INSERT INTO skill_definitions (id, name) VALUES (:id, :n)"),
        {"id": skill_id, "n": f"test-{skill_id[:8]}"},
    )

    payload = b"Hello, bundle!"
    digest = hashlib.sha256(payload).hexdigest()

    await admin_session.execute(
        sa_text(
            "INSERT INTO skill_assets "
            "(skill_id, bundle, bundle_sha256, bundle_size_bytes) "
            "VALUES (:sid, :b, :sha, :sz)"
        ),
        {"sid": skill_id, "b": payload, "sha": digest, "sz": len(payload)},
    )
    await admin_session.commit()

    row = (
        await admin_session.execute(
            sa_text(
                "SELECT bundle, bundle_sha256, bundle_size_bytes "
                "FROM skill_assets WHERE skill_id = :sid"
            ),
            {"sid": skill_id},
        )
    ).fetchone()

    assert bytes(row.bundle) == payload
    assert row.bundle_sha256 == digest
    assert row.bundle_size_bytes == len(payload)

    # Cleanup cascades via FK (also exercises SC3 indirectly).
    await admin_session.execute(
        sa_text("DELETE FROM skill_definitions WHERE id = :sid"),
        {"sid": skill_id},
    )
    await admin_session.commit()


async def test_cascade_delete_removes_asset(admin_session):
    """SC3: Deleting a skill_definitions row cascades to skill_assets."""
    skill_id = str(uuid.uuid4())
    await admin_session.execute(
        sa_text("INSERT INTO skill_definitions (id, name) VALUES (:id, :n)"),
        {"id": skill_id, "n": f"cascade-{skill_id[:8]}"},
    )
    await admin_session.execute(
        sa_text(
            "INSERT INTO skill_assets "
            "(skill_id, bundle, bundle_sha256, bundle_size_bytes) "
            "VALUES (:sid, :b, :sha, :sz)"
        ),
        {"sid": skill_id, "b": b"x", "sha": "a" * 64, "sz": 1},
    )
    await admin_session.commit()

    await admin_session.execute(
        sa_text("DELETE FROM skill_definitions WHERE id = :sid"),
        {"sid": skill_id},
    )
    await admin_session.commit()

    count = (
        await admin_session.execute(
            sa_text("SELECT COUNT(*) FROM skill_assets WHERE skill_id = :sid"),
            {"sid": skill_id},
        )
    ).scalar()
    assert count == 0


async def test_unique_skill_id_rejects_duplicate(admin_session):
    """SC4: Unique index on skill_id blocks a second row for the same skill."""
    from sqlalchemy.exc import IntegrityError

    skill_id = str(uuid.uuid4())
    await admin_session.execute(
        sa_text("INSERT INTO skill_definitions (id, name) VALUES (:id, :n)"),
        {"id": skill_id, "n": f"dup-{skill_id[:8]}"},
    )
    await admin_session.execute(
        sa_text(
            "INSERT INTO skill_assets "
            "(skill_id, bundle, bundle_sha256, bundle_size_bytes) "
            "VALUES (:sid, :b, :sha, :sz)"
        ),
        {"sid": skill_id, "b": b"a", "sha": "a" * 64, "sz": 1},
    )
    await admin_session.commit()

    # Second insert for the same skill_id must fail.
    with pytest.raises(IntegrityError):
        await admin_session.execute(
            sa_text(
                "INSERT INTO skill_assets "
                "(skill_id, bundle, bundle_sha256, bundle_size_bytes) "
                "VALUES (:sid, :b, :sha, :sz)"
            ),
            {"sid": skill_id, "b": b"b", "sha": "b" * 64, "sz": 1},
        )
        await admin_session.commit()
    await admin_session.rollback()

    # Cleanup
    await admin_session.execute(
        sa_text("DELETE FROM skill_definitions WHERE id = :sid"),
        {"sid": skill_id},
    )
    await admin_session.commit()
