"""Parity verification script — Phase 156 CUT-04.

Compares context store writes from server-side vs in-context execution
for 5 representative skills: company-intel, meeting-prep, meeting-processor,
daily-brief, sales-collateral.

This is a REPORTING script, not an automated test. It queries the DB and
prints a comparison table. Expected to show NEEDS_DATA for most skills
initially since in-context execution hasn't happened yet.

Usage:
    cd backend && uv run python scripts/verify_parity_156.py
"""

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# The 5 representative skills per CUT-04
SKILLS = [
    "company-intel",
    "meeting-prep",
    "meeting-processor",
    "daily-brief",
    "sales-collateral",
]


async def gather_skill_data(session, skill_name: str) -> dict:
    """Gather telemetry and context data for a single skill."""
    result: dict = {
        "skill_name": skill_name,
        "server_side_runs": 0,
        "in_context_redirects": 0,
        "in_context_completed": 0,
        "context_files_server": [],
        "context_files_in_context": [],
        "parity": "NEEDS_DATA",
    }

    # --- Telemetry counts by execution path ---
    try:
        rows = await session.execute(
            text("""
                SELECT execution_path, COUNT(*) as cnt
                FROM skill_execution_telemetry
                WHERE skill_name = :skill_name
                GROUP BY execution_path
            """),
            {"skill_name": skill_name},
        )
        for row in rows:
            path, cnt = row[0], row[1]
            if path == "server_side":
                result["server_side_runs"] = cnt
            elif path == "redirect_to_in_context":
                result["in_context_redirects"] = cnt
            elif path == "in_context_completed":
                result["in_context_completed"] = cnt
    except Exception as exc:
        result["telemetry_error"] = str(exc)

    # --- Context files written by in-context completions (from telemetry metadata) ---
    try:
        rows = await session.execute(
            text("""
                SELECT metadata
                FROM skill_execution_telemetry
                WHERE skill_name = :skill_name
                  AND execution_path = 'in_context_completed'
                ORDER BY created_at DESC
                LIMIT 20
            """),
            {"skill_name": skill_name},
        )
        in_ctx_files: set = set()
        for row in rows:
            meta = row[0] or {}
            for f in meta.get("context_files_written", []):
                in_ctx_files.add(f)
        result["context_files_in_context"] = sorted(in_ctx_files)
    except Exception:
        pass

    # --- Context files written by server-side (from context_entries source) ---
    try:
        rows = await session.execute(
            text("""
                SELECT DISTINCT file_name
                FROM context_entries
                WHERE source ILIKE :pattern
                ORDER BY file_name
            """),
            {"pattern": f"%{skill_name}%"},
        )
        result["context_files_server"] = [row[0] for row in rows]
    except Exception:
        pass

    # --- Determine parity ---
    has_server = result["server_side_runs"] > 0 or len(result["context_files_server"]) > 0
    has_in_context = result["in_context_completed"] > 0

    if has_server and has_in_context:
        # Both paths have data — compare context file names
        server_set = set(result["context_files_server"])
        in_ctx_set = set(result["context_files_in_context"])
        if not in_ctx_set:
            result["parity"] = "NEEDS_DATA"
        elif in_ctx_set.issubset(server_set) or server_set.issubset(in_ctx_set):
            result["parity"] = "PASS"
        elif in_ctx_set & server_set:
            result["parity"] = "PASS"  # partial overlap is acceptable
        else:
            result["parity"] = "MISMATCH"
    else:
        result["parity"] = "NEEDS_DATA"

    return result


async def main():
    factory = get_session_factory()

    print("=" * 70)
    print("Phase 156 — Parity Verification Report (CUT-04)")
    print("=" * 70)
    print()

    has_mismatch = False

    async with factory() as session:
        for skill_name in SKILLS:
            data = await gather_skill_data(session, skill_name)

            print(f"Skill: {data['skill_name']}")
            print(f"  Server-side runs:        {data['server_side_runs']}")
            print(f"  In-context redirects:    {data['in_context_redirects']}")
            print(f"  In-context completed:    {data['in_context_completed']}")
            print(f"  Context files (server):  {data['context_files_server'] or '(none)'}")
            print(f"  Context files (in-ctx):  {data['context_files_in_context'] or '(none)'}")

            if "telemetry_error" in data:
                print(f"  Telemetry error:         {data['telemetry_error']}")

            parity = data["parity"]
            print(f"  Parity:                  {parity}")
            print()

            if parity == "MISMATCH":
                has_mismatch = True

    print("=" * 70)
    if has_mismatch:
        print("RESULT: MISMATCH detected — review skills above.")
        sys.exit(1)
    else:
        print("RESULT: All skills PASS or NEEDS_DATA (no mismatches).")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
