"""Phase 147 Seed Pipeline Extension — end-to-end tests.

Locks in all five ROADMAP success criteria:
  SC1: assets: globs produce a valid DEFLATE zip with correct entries.
  SC2: Re-seed with no file changes emits 'bundle skipped (sha256 match)' and
       performs zero UPDATE statements on skill_assets.
  SC3: _shared and gtm-shared seeded with enabled=false, tags @> ['library'];
       SKIP_DIRS == {'_archived'}.
  SC4: Unknown depends_on raises UnknownDependencyError BEFORE any DB write.
  SC5: skill_assets UPSERT runs BEFORE skill_definitions.system_prompt UPDATE
       (verified by log order within a single transaction).

Plus one pure-unit determinism test for _build_bundle.

Requires Docker Postgres on port 5434 (admin_session fixture + @pytest.mark.postgres).

Phase 147 — v22.0 Skill Platform Consolidation.
"""
import io
import logging
import zipfile

import pytest
from sqlalchemy import text as sa_text

from flywheel.db.seed import (
    SKIP_DIRS,
    UnknownDependencyError,
    _build_bundle,
    seed_skills,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(
    root,
    name: str,
    frontmatter: str,
    body: str = "",
    files: dict | None = None,
):
    """Create a skill directory with SKILL.md and optional extra files."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}\n")
    for rel, data in (files or {}).items():
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            target.write_text(data)


async def _fetch_bundle(session, skill_name: str) -> bytes:
    row = (
        await session.execute(
            sa_text(
                "SELECT sa.bundle FROM skill_assets sa "
                "JOIN skill_definitions sd ON sa.skill_id = sd.id "
                "WHERE sd.name = :n"
            ),
            {"n": skill_name},
        )
    ).fetchone()
    return bytes(row.bundle) if row else b""


# ---------------------------------------------------------------------------
# Pure-unit tests (no DB) — _build_bundle determinism + filtering
# ---------------------------------------------------------------------------


def test_build_bundle_is_deterministic(tmp_path):
    """Two consecutive builds of the same inputs produce byte-identical output."""
    (tmp_path / "a.py").write_text("a = 1\n")
    (tmp_path / "b.py").write_text("b = 2\n")
    b1, h1, s1 = _build_bundle(str(tmp_path), ["*.py"])
    b2, h2, s2 = _build_bundle(str(tmp_path), ["*.py"])
    assert b1 == b2
    assert h1 == h2
    assert s1 == s2


def test_build_bundle_filters_skip_set(tmp_path):
    """tests/, __pycache__/, .DS_Store, auto-memory/ are excluded even if matched."""
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("# test\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "keep.cpython.pyc").write_bytes(b"\x00")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")
    (tmp_path / "auto-memory").mkdir()
    (tmp_path / "auto-memory" / "foo.py").write_text("# mem\n")
    # Use a greedy glob that would otherwise pick everything up.
    data, _, _ = _build_bundle(str(tmp_path), ["**/*"])
    names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
    assert names == {"keep.py"}, names


def test_build_bundle_uses_relative_archive_paths(tmp_path):
    """Archive entries use paths RELATIVE to skill_dir, not absolute."""
    (tmp_path / "helper.py").write_text("x = 1\n")
    (tmp_path / "portals").mkdir()
    (tmp_path / "portals" / "mapfre.py").write_text("# mapfre\n")
    data, _, _ = _build_bundle(str(tmp_path), ["*.py", "portals/*.py"])
    names = sorted(zipfile.ZipFile(io.BytesIO(data)).namelist())
    assert names == ["helper.py", "portals/mapfre.py"], names


# ---------------------------------------------------------------------------
# SC3: SKIP_DIRS narrowed to {"_archived"}
# ---------------------------------------------------------------------------


def test_skip_dirs_is_narrowed():
    """SC3 (static): SKIP_DIRS in seed.py contains only {'_archived'}."""
    assert SKIP_DIRS == {"_archived"}, SKIP_DIRS


# ---------------------------------------------------------------------------
# DB-backed end-to-end tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_sc1_bundle_matches_globs(admin_session, tmp_path):
    """SC1: assets: ['*.py', 'portals/*.py'] produces a DEFLATE zip whose
    entries match the globbed files exactly (tests/ excluded)."""
    _write_skill(
        tmp_path,
        "demo-sc1",
        frontmatter='name: demo-sc1\nversion: "1.0"\nassets: ["*.py", "portals/*.py"]',
        body="hello",
        files={
            "helper.py": "print('hello')\n",
            "portals/mapfre.py": "# mapfre\n",
            "tests/test_x.py": "# should NOT be in bundle\n",
        },
    )
    try:
        await seed_skills(admin_session, skills_dir=str(tmp_path))
        bundle = await _fetch_bundle(admin_session, "demo-sc1")
        assert bundle, "no bundle written"
        names = sorted(zipfile.ZipFile(io.BytesIO(bundle)).namelist())
        assert names == ["helper.py", "portals/mapfre.py"], names
        # Validate it's a real DEFLATE zip (not STORE)
        zinfo = zipfile.ZipFile(io.BytesIO(bundle)).getinfo("helper.py")
        assert zinfo.compress_type == zipfile.ZIP_DEFLATED
    finally:
        await admin_session.execute(
            sa_text("DELETE FROM skill_definitions WHERE name = 'demo-sc1'")
        )
        await admin_session.commit()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_sc2_reseed_skips_unchanged(admin_session, tmp_path, caplog):
    """SC2: Re-seed with no file changes emits 'bundle skipped (sha256 match)'
    and skill_assets.updated_at is NOT advanced (zero writes)."""
    _write_skill(
        tmp_path,
        "demo-sc2",
        frontmatter='name: demo-sc2\nversion: "1.0"\nassets: ["*.py"]',
        body="x",
        files={"a.py": "a = 1\n"},
    )
    try:
        # First seed — writes a fresh bundle.
        with caplog.at_level(logging.INFO, logger="flywheel.db.seed"):
            await seed_skills(admin_session, skills_dir=str(tmp_path))
        assert "bundle updated" in caplog.text
        first_updated_at = (
            await admin_session.execute(
                sa_text(
                    "SELECT sa.updated_at FROM skill_assets sa "
                    "JOIN skill_definitions sd ON sa.skill_id = sd.id "
                    "WHERE sd.name = 'demo-sc2'"
                )
            )
        ).scalar_one()

        caplog.clear()

        # Second seed — same bytes → skip path.
        with caplog.at_level(logging.INFO, logger="flywheel.db.seed"):
            await seed_skills(admin_session, skills_dir=str(tmp_path))
        assert "bundle skipped (sha256 match)" in caplog.text, caplog.text

        # updated_at unchanged (no UPDATE statement ran).
        second_updated_at = (
            await admin_session.execute(
                sa_text(
                    "SELECT sa.updated_at FROM skill_assets sa "
                    "JOIN skill_definitions sd ON sa.skill_id = sd.id "
                    "WHERE sd.name = 'demo-sc2'"
                )
            )
        ).scalar_one()
        assert second_updated_at == first_updated_at, (
            "skill_assets.updated_at advanced despite sha256 match"
        )
    finally:
        await admin_session.execute(
            sa_text("DELETE FROM skill_definitions WHERE name = 'demo-sc2'")
        )
        await admin_session.commit()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_sc3_library_skills_seeded_disabled(admin_session, tmp_path):
    """SC3: _shared and gtm-shared appear with enabled=false and tags @> ['library']."""
    _write_skill(
        tmp_path,
        "_shared",
        frontmatter='name: _shared\nversion: "1.0"\nassets: ["*.py"]',
        body="",
        files={"helper.py": "h = 1\n"},
    )
    _write_skill(
        tmp_path,
        "gtm-shared",
        frontmatter='name: gtm-shared\nversion: "1.0"\nassets: ["*.py"]',
        body="",
        files={"g.py": "g = 1\n"},
    )
    try:
        await seed_skills(admin_session, skills_dir=str(tmp_path))
        rows = (
            await admin_session.execute(
                sa_text(
                    "SELECT name, enabled, tags FROM skill_definitions "
                    "WHERE name IN ('_shared', 'gtm-shared') "
                    "ORDER BY name"
                )
            )
        ).fetchall()
        assert len(rows) == 2, rows
        by = {r.name: r for r in rows}
        assert by["_shared"].enabled is False
        assert "library" in by["_shared"].tags
        assert by["gtm-shared"].enabled is False
        assert "library" in by["gtm-shared"].tags
    finally:
        await admin_session.execute(
            sa_text(
                "DELETE FROM skill_definitions "
                "WHERE name IN ('_shared', 'gtm-shared')"
            )
        )
        await admin_session.commit()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_sc4_unknown_depends_on_raises_no_writes(admin_session, tmp_path):
    """SC4: depends_on referencing a nonexistent library raises
    UnknownDependencyError BEFORE any DB write — zero rows created."""
    _write_skill(
        tmp_path,
        "consumer-sc4",
        frontmatter='name: consumer-sc4\nversion: "1.0"\ndepends_on: ["ghost"]',
        body="x",
    )

    # Snapshot row count before
    before = (
        await admin_session.execute(
            sa_text("SELECT COUNT(*) AS c FROM skill_definitions "
                    "WHERE name = 'consumer-sc4'")
        )
    ).scalar_one()

    with pytest.raises(UnknownDependencyError) as exc_info:
        await seed_skills(admin_session, skills_dir=str(tmp_path))
    assert exc_info.value.skill == "consumer-sc4"
    assert exc_info.value.missing == ["ghost"]

    # Rollback the aborted transaction so subsequent SELECTs work.
    await admin_session.rollback()

    after = (
        await admin_session.execute(
            sa_text("SELECT COUNT(*) AS c FROM skill_definitions "
                    "WHERE name = 'consumer-sc4'")
        )
    ).scalar_one()
    assert after == before, (
        f"UnknownDependencyError should leave zero partial writes: "
        f"before={before} after={after}"
    )


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_sc5_assets_written_before_prompt_update(admin_session, tmp_path, caplog):
    """SC5: skill_assets UPSERT log line precedes skill_definitions UPDATE log line."""
    _write_skill(
        tmp_path,
        "order-sc5",
        frontmatter='name: order-sc5\nversion: "1.0"\nassets: ["*.py"]',
        body="prompt body",
        files={"a.py": "a = 1\n"},
    )
    try:
        with caplog.at_level(logging.INFO, logger="flywheel.db.seed"):
            await seed_skills(admin_session, skills_dir=str(tmp_path))
        # Extract ordered log records for this skill.
        lines = [
            r.getMessage() for r in caplog.records
            if "order-sc5" in r.getMessage()
        ]
        bundle_idx = next(
            (i for i, m in enumerate(lines) if "bundle updated" in m), None
        )
        prompt_idx = next(
            (i for i, m in enumerate(lines) if "definition upserted" in m), None
        )
        assert bundle_idx is not None, f"no bundle log for order-sc5: {lines}"
        assert prompt_idx is not None, f"no definition log for order-sc5: {lines}"
        assert bundle_idx < prompt_idx, (
            f"skill_assets must be written BEFORE skill_definitions update: "
            f"{lines}"
        )
    finally:
        await admin_session.execute(
            sa_text("DELETE FROM skill_definitions WHERE name = 'order-sc5'")
        )
        await admin_session.commit()
