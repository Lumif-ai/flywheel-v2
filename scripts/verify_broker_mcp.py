#!/usr/bin/env python3
"""Phase 152.1 verification — prove all 11 broker triggers dispatch correctly via MCP.

Usage:
    scripts/verify_broker_mcp.py                # simple pre-flight: just fetch bodies
    scripts/verify_broker_mcp.py --rename-away  # rename ~/.claude/skills/broker/ → .broker.bak during run (PRE-DELETE)
    scripts/verify_broker_mcp.py --post-delete  # assert mirror has ONLY SKILL.md remaining
    scripts/verify_broker_mcp.py --verbose

Flow order (BLOCKER 3 resolution — alias-check-before-rename):
  1. Alias assertion runs FIRST (while router file is in place), result captured into
     variable. Previous design called this AFTER rename, which false-failed.
  2. If --rename-away: mirror dir moved aside (alias file no longer present — OK, we
     already captured). atexit + SIGINT/SIGTERM handlers restore on exit.
  3. If --post-delete: assert only SKILL.md remains under ~/.claude/skills/broker/.
  4. Iterate 10 slugs, fetch from MCP, assert body invariants.
  5. Summary prints: 10 MCP-fetched slugs + alias status (already computed in step 1).
  6. atexit restores mirror if it was renamed away.

Exit 0 = all green. Non-zero = aggregated failure list printed.
"""
from __future__ import annotations

import argparse
import atexit
import shutil
import signal
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "cli"))

from flywheel_mcp.api_client import FlywheelClient  # noqa: E402

BROKER_DIR = Path.home() / ".claude" / "skills" / "broker"
BROKER_BAK = Path.home() / ".claude" / "skills" / ".broker.bak"

# 10 distinct MCP slugs covering 11 triggers (gap-analysis shared by /broker:gap-analysis
# and /broker:analyze-gaps alias per router table).
BROKER_SLUGS = [
    "broker-parse-contract",
    "broker-parse-policies",
    "broker-gap-analysis",
    "broker-select-carriers",
    "broker-fill-portal",
    "broker-draft-emails",
    "broker-extract-quote",
    "broker-draft-recommendation",
    "broker-process-project",
    "broker-compare-quotes",
]

# Slugs expected NOT to contain "from flywheel.broker" — pipeline wrappers (no direct
# helper use; orchestrate via /broker:<slug> slash triggers instead).
SLUGS_WITHOUT_FW_IMPORT = {"broker-process-project"}

# Error-string prefixes that flywheel_fetch_skill_prompt returns on failure instead of
# raising — mirror the router template's detection rules (Dispatch Flow step 6).
ERROR_STRING_PREFIXES = (
    "No prompt found",
    "Error fetching",
    "API error",
    "Authentication expired",
)


# ---------------- rename-away + restore plumbing (Phase 151 dogfood-harness pattern) ----------------


def _restore_broker() -> None:
    """Restore ~/.claude/skills/broker/ if we moved it aside. Idempotent."""
    if BROKER_BAK.exists() and not BROKER_DIR.exists():
        shutil.move(str(BROKER_BAK), str(BROKER_DIR))
        print(f"  [rename-away] Restored {BROKER_DIR}")


def _rename_broker_away() -> None:
    """Move ~/.claude/skills/broker/ aside to .broker.bak. Register restore on exit."""
    if BROKER_DIR.exists() and not BROKER_BAK.exists():
        shutil.move(str(BROKER_DIR), str(BROKER_BAK))
        print(f"  [rename-away] Moved {BROKER_DIR} -> {BROKER_BAK}")
    atexit.register(_restore_broker)
    signal.signal(signal.SIGINT, lambda s, f: (_restore_broker(), sys.exit(128 + s)))
    signal.signal(signal.SIGTERM, lambda s, f: (_restore_broker(), sys.exit(128 + s)))


# ---------------- assertions ----------------


def assert_alias_in_router() -> list[str]:
    """Router SKILL.md must declare /broker:analyze-gaps among its triggers.

    IMPORTANT: call this BEFORE any rename-away so the router file is still in place.
    BLOCKER 3 resolution — previous version called this after rename, which false-failed.
    """
    router = BROKER_DIR / "SKILL.md"
    if not router.exists():
        return [
            f"Router {router} missing (call assert_alias_in_router BEFORE rename-away)"
        ]
    text = router.read_text(encoding="utf-8")
    if "/broker:analyze-gaps" not in text:
        return ["Router does not declare /broker:analyze-gaps alias"]
    return []


def assert_body(slug: str, body: str) -> list[str]:
    """Check a single MCP-fetched body against the Phase 152.1 invariants."""
    failures: list[str] = []
    if not isinstance(body, str):
        failures.append(f"{slug}: body is not a string (type={type(body).__name__})")
        return failures
    if len(body) < 500:
        failures.append(f"{slug}: body too short ({len(body)} chars)")
        return failures
    for prefix in ERROR_STRING_PREFIXES:
        if body.startswith(prefix):
            failures.append(f"{slug}: MCP returned an error string: {body[:200]}")
            return failures
    if "sys.path.insert" in body and "~/.claude/skills/broker/" in body:
        failures.append(f"{slug}: body still has legacy sys.path.insert header")
    if "auto-memory/broker.md" in body:
        failures.append(f"{slug}: body still references auto-memory/broker.md")
    if "from flywheel_broker import" in body:
        failures.append(
            f"{slug}: body uses flat form 'from flywheel_broker' — must use dot "
            f"form 'from flywheel.broker' (CONTEXT.md locked)"
        )
    if slug not in SLUGS_WITHOUT_FW_IMPORT and "from flywheel.broker import" not in body:
        failures.append(f"{slug}: body missing 'from flywheel.broker' import")
    return failures


def assert_post_delete_state() -> list[str]:
    """After mirror delete, BROKER_DIR must contain ONLY SKILL.md."""
    if not BROKER_DIR.exists():
        return [
            f"{BROKER_DIR} does not exist — Claude Code will have no /broker:* "
            f"triggers registered!"
        ]
    children = list(BROKER_DIR.iterdir())
    survivors = [c.name for c in children if c.name != "SKILL.md"]
    if survivors:
        return [f"Mirror not fully cleaned: {sorted(survivors)} survived under {BROKER_DIR}"]
    return []


# ---------------- main ----------------


def _extract_body(resp: object) -> str:
    """Normalise fetch_skill_prompt's response shape to a string body.

    FlywheelClient.fetch_skill_prompt() returns the decoded JSON body from
    /api/v1/skills/{name}/prompt. That payload can be a dict with a
    ``system_prompt`` key, a raw string (some error paths), or a dict with a
    top-level ``prompt`` / ``body`` key. Coerce to a single string.
    """
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        for key in ("system_prompt", "prompt", "body", "content"):
            val = resp.get(key)
            if isinstance(val, str) and val:
                return val
        # Last-resort: stringify the whole dict so assert_body can flag it.
        return str(resp)
    return str(resp)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--rename-away",
        action="store_true",
        help="Move ~/.claude/skills/broker/ to .broker.bak during the run "
        "(pre-delete verification — proves MCP path is the only source).",
    )
    ap.add_argument(
        "--post-delete",
        action="store_true",
        help="Assert ~/.claude/skills/broker/ contains ONLY SKILL.md (post-delete state).",
    )
    ap.add_argument("--verbose", action="store_true", help="Print extra diagnostics.")
    args = ap.parse_args()

    # -------- STEP 1: alias check runs FIRST, BEFORE any destructive moves (BLOCKER 3 fix) --------
    alias_errs = assert_alias_in_router()
    alias_ok = not alias_errs
    if alias_ok:
        print("  OK: /broker:analyze-gaps alias declared in local router (captured pre-rename)")
    else:
        for e in alias_errs:
            print(f"  FAIL: {e}")

    # -------- STEP 2: now safe to rename mirror away if requested --------
    if args.rename_away:
        _rename_broker_away()

    # -------- STEP 3: post-delete filesystem assertion --------
    post_delete_errs: list[str] = []
    if args.post_delete:
        post_delete_errs = assert_post_delete_state()
        for e in post_delete_errs:
            print(f"  FAIL: {e}")

    # -------- STEP 4: MCP-fetch loop --------
    client = FlywheelClient()
    failures: list[str] = list(alias_errs) + list(post_delete_errs)
    for slug in BROKER_SLUGS:
        try:
            resp = client.fetch_skill_prompt(slug)
            body = _extract_body(resp)
            if args.verbose:
                print(f"  [verbose] {slug}: response type={type(resp).__name__}, body len={len(body)}")
            errs = assert_body(slug, body)
            if errs:
                failures.extend(errs)
                for e in errs:
                    print(f"  FAIL: {e}")
            else:
                print(f"  OK: {slug} ({len(body)} chars)")
        except Exception as exc:  # pragma: no cover — network / auth path
            failures.append(f"{slug}: fetch_skill_prompt raised — {exc!r}")
            print(f"  FAIL: {slug}: fetch_skill_prompt raised — {exc!r}")

    # -------- STEP 5: summary --------
    print("\n--- Summary ---")
    print(f"  MCP-fetched slugs: {len(BROKER_SLUGS)} distinct "
          f"(broker-parse-contract, …, broker-compare-quotes)")
    print(f"  Alias verified in router: {'yes' if alias_ok else 'no'}")
    print("  Acceptance bar: 10 distinct broker skill slugs resolved via")
    print("                  flywheel_fetch_skill_prompt, covering all 11 triggers")
    print("                  (gap-analysis shared by /broker:gap-analysis and")
    print("                  /broker:analyze-gaps alias — verified by router table).")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nALL PASS — acceptance bar met.")


if __name__ == "__main__":
    main()
