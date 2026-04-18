#!/usr/bin/env python3
"""Phase 151 dogfood harness — programmatic probes for SCs 1-4.

Exercises the 5 core broker steps end-to-end on a machine where
``~/.claude/skills/broker/`` is renamed to ``.broker.bak`` (auto-handled
by this harness unless ``--skip-rename``). For each Pattern 3a step
(parse-contract, parse-policies, draft-emails):

    (a) ``materialize_skill_bundle`` succeeds — SC1 mechanical proof
        (temp root exists, ``sys.path[0]`` points there, spot-check Python
        files surface for skills that bundle them).
    (b) ``POST /api/v1/broker/extract/<operation>`` returns the Pattern
        3a ``{prompt, tool_schema, documents, metadata}`` envelope.
    (c) ``POST /api/v1/broker/save/<operation>`` persists a *canned*
        tool_use fixture (structural stand-in, NOT a real Claude
        inference — we are probing the wire, not the extraction
        quality).
    (d) ``GET /api/v1/broker/projects/<id>`` verifies the row landed.

For non-Pattern-3a steps (gap-analysis, select-carriers) the backend
computes the answer deterministically — we materialize the skill bundle
(SC1 proof) plus hit the relevant endpoint once.

``--offline-sim`` flag simulates SC2 (Flywheel backend unreachable)
by warming the cache against the live backend, then flipping
``FLYWHEEL_API_URL=http://127.0.0.1:1`` (RST-ing port) and re-invoking
``fetch_skill_assets_bundle`` — Plan 01's ConnectError handler should
emit the locked ``WARN: Backend unreachable.`` stderr line and serve
from cache.

Usage:
    # Full SC1 + SC4 probes (requires live backend + preset project-id)
    python scripts/dogfood_harness.py --project-id <UUID>

    # Offline simulation (SC2) — requires populated cache from prior run
    python scripts/dogfood_harness.py --project-id <UUID> --offline-sim

    # CI mode (skip .broker.bak rename — for non-dogfood-machine CI)
    python scripts/dogfood_harness.py --project-id <UUID> --skip-rename

    # Single step (debug)
    python scripts/dogfood_harness.py --project-id <UUID> \
        --only broker-parse-contract

Exit 0 = all probed steps pass. Non-zero = first failure + reason.

Note: the full dogfood EXECUTION (fresh Claude Code session,
``/broker:parse-contract``, MSA PDF upload) lives in
``DOGFOOD-RUNBOOK.md``. This harness covers the mechanical parts a
programmatic probe can verify; the human-in-the-loop parts are the
runbook's job.
"""
from __future__ import annotations

import argparse
import atexit
import os
import secrets
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Callable


# ------------------------------- constants -------------------------------

BROKER_DIR = Path.home() / ".claude" / "skills" / "broker"
BROKER_BAK = Path.home() / ".claude" / "skills" / ".broker.bak"
OFFLINE_API_URL = "http://127.0.0.1:1"

# Added by the harness at startup so the `flywheel_mcp` package resolves
# when this script is invoked from the repo root. Must be absolute to
# survive `os.chdir` from test harnesses.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_PATH = _REPO_ROOT / "cli"
if _CLI_PATH.exists() and str(_CLI_PATH) not in sys.path:
    sys.path.insert(0, str(_CLI_PATH))


# ------------------------- broker dir rename + restore -------------------

_rename_done = False


def _restore_broker() -> None:
    """Idempotent restore — safe to call multiple times."""
    global _rename_done
    if BROKER_BAK.exists() and not BROKER_DIR.exists():
        shutil.move(str(BROKER_BAK), str(BROKER_DIR))
        print(f"[harness] restored {BROKER_DIR}", file=sys.stderr)
    _rename_done = False


def _rename_broker_away() -> None:
    """Move ~/.claude/skills/broker -> .broker.bak and register atexit restore.

    Idempotent — re-invoking when ``.broker.bak`` already exists prints
    a notice and re-registers the atexit hook so the restore still
    fires on this process exit (handles the case where a prior harness
    run Ctrl-C'd during the rename window)."""
    global _rename_done
    if BROKER_DIR.exists() and not BROKER_BAK.exists():
        shutil.move(str(BROKER_DIR), str(BROKER_BAK))
        print(f"[harness] renamed {BROKER_DIR} -> {BROKER_BAK}", file=sys.stderr)
        _rename_done = True
    elif BROKER_BAK.exists():
        print(f"[harness] {BROKER_BAK} already renamed; reusing", file=sys.stderr)
        _rename_done = True
    else:
        print(f"[harness] no broker skill dir at {BROKER_DIR} — nothing to rename", file=sys.stderr)
        return

    atexit.register(_restore_broker)

    def _sig_handler(sig_num: int, _frame) -> None:
        _restore_broker()
        # Conventional shell exit codes for signal death (128+signo)
        sys.exit(128 + sig_num)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)


# ----------------------------- lazy importers ---------------------------

def _client():
    """Fresh FlywheelClient for each step (mirrors Phase 150 per-tool pattern)."""
    from flywheel_mcp.api_client import FlywheelClient
    return FlywheelClient()


# ----------------------------- probe helpers ----------------------------

def _materialize_and_probe(skill_name: str) -> None:
    """(a) MCP materialize proof — assert bundle extracts + sys.path prepend works.

    ``materialize_skill_bundle`` is a context manager that internally
    constructs a :class:`FlywheelClient`, calls
    ``fetch_skill_assets_bundle(name)``, verifies SHAs, safe-extracts
    every bundle in topological order, prepends the temp root to
    ``sys.path``, and yields the temp :class:`Path`. On exit the temp
    root is removed and ``sys.path`` is restored.
    """
    from flywheel_mcp.bundle import materialize_skill_bundle

    with materialize_skill_bundle(skill_name) as tmp:
        assert tmp.exists(), f"materialize returned non-existent dir for {skill_name}"
        assert str(tmp) == sys.path[0], (
            f"sys.path[0] not prepended to temp root: expected {tmp}, got {sys.path[0]}"
        )
        py_files = list(tmp.rglob("*.py"))
        if py_files:
            print(f"  [materialize] {skill_name}: OK ({len(py_files)} .py files)", file=sys.stderr)
        else:
            print(f"  [materialize] {skill_name}: OK (no .py — prompt-only skill)", file=sys.stderr)


def _probe_extract(endpoint: str, project_id: str, correlation_id: str, skill: str) -> dict:
    """(b) Extract endpoint reachability — POST + assert Pattern 3a envelope."""
    client = _client()
    resp = client._request(
        "post",
        f"/api/v1/broker/extract/{endpoint}",
        json={"project_id": project_id},
        headers={
            "X-Flywheel-Correlation-ID": correlation_id,
            "X-Flywheel-Skill": skill,
        },
    )
    # Pattern 3a extract contract: {prompt, tool_schema, documents[], metadata}
    for field in ("prompt", "tool_schema", "documents"):
        assert field in resp, f"extract/{endpoint} missing {field}"
    print(f"  [extract] {endpoint}: OK", file=sys.stderr)
    return resp


def _probe_save(
    endpoint: str,
    project_id: str,
    correlation_id: str,
    skill: str,
    tool_use: dict,
) -> dict:
    """(c) Save endpoint persistence — POST canned tool_use fixture."""
    client = _client()
    resp = client._request(
        "post",
        f"/api/v1/broker/save/{endpoint}",
        json={
            "project_id": project_id,
            "tool_use": tool_use,
            "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        },
        headers={
            "X-Flywheel-Correlation-ID": correlation_id,
            "X-Flywheel-Skill": skill,
        },
    )
    print(f"  [save] {endpoint}: OK (status={resp.get('status', 'ok')})", file=sys.stderr)
    return resp


def _verify_db_rows(project_id: str, expected_counts: dict[str, int]) -> None:
    """(d) DB verification — GET /projects/{id}, assert list fields have >= expected rows."""
    client = _client()
    detail = client._request("get", f"/api/v1/broker/projects/{project_id}")
    for field, min_count in expected_counts.items():
        actual = len(detail.get(field, []) or [])
        assert actual >= min_count, (
            f"field {field} has {actual} rows, expected >= {min_count}"
        )
    print(f"  [db] project {project_id}: {expected_counts} verified", file=sys.stderr)


# ---------------------- canned tool_use fixtures -----------------------
# NOT real Claude inference — structural stand-ins that match each
# operation's tool_schema.input_schema so the save endpoint's Pydantic
# validator accepts them. These prove the wire + persistence layer.

CANNED_CONTRACT_TOOL_USE = {
    "name": "extract_coverage_requirements",
    "input": {
        "coverages": [
            {
                "coverage_type": "general_liability",
                "required_limit": 1_000_000,
                "currency": "USD",
            }
        ]
    },
}

CANNED_POLICY_TOOL_USE = {
    "name": "extract_policy_coverage",
    "input": {
        "policies": [
            {
                "coverage_type": "general_liability",
                "current_limit": 500_000,
                "carrier": "Synthetic",
            }
        ]
    },
}

CANNED_SOLICITATION_TOOL_USE = {
    "name": "draft_solicitation_email",
    "input": {
        "subject": "Quote Request — Synthetic Project",
        "body": "Please provide quote for synthetic coverages.",
        "recipients": [{"email": "test@example.com", "carrier_name": "Synthetic"}],
    },
}


# ------------------------------- step fns -------------------------------

def step_parse_contract(project_id: str, correlation_id: str) -> None:
    """Pattern 3a: materialize + extract + save + DB."""
    _materialize_and_probe("broker-parse-contract")
    _probe_extract("contract-analysis", project_id, correlation_id, "broker-parse-contract")
    _probe_save(
        "contract-analysis",
        project_id,
        correlation_id,
        "broker-parse-contract",
        CANNED_CONTRACT_TOOL_USE,
    )
    _verify_db_rows(project_id, {"coverages": 1})


def step_parse_policies(project_id: str, correlation_id: str) -> None:
    """Pattern 3a: materialize + extract + save + DB."""
    _materialize_and_probe("broker-parse-policies")
    _probe_extract("policy-extraction", project_id, correlation_id, "broker-parse-policies")
    _probe_save(
        "policy-extraction",
        project_id,
        correlation_id,
        "broker-parse-policies",
        CANNED_POLICY_TOOL_USE,
    )
    _verify_db_rows(project_id, {"policies": 1})


def step_gap_analysis(project_id: str, correlation_id: str) -> None:
    """Non-Pattern-3a: server-side deterministic. Single POST."""
    _materialize_and_probe("broker-gap-analysis")
    client = _client()
    resp = client._request(
        "post",
        f"/api/v1/broker/projects/{project_id}/analyze-gaps",
        json={},
        headers={
            "X-Flywheel-Correlation-ID": correlation_id,
            "X-Flywheel-Skill": "broker-gap-analysis",
        },
    )
    assert "gaps" in resp or "analysis" in resp, (
        f"analyze-gaps response missing expected 'gaps' or 'analysis' key: {list(resp.keys())}"
    )
    print(f"  [gap-analysis] OK", file=sys.stderr)


def step_select_carriers(project_id: str, correlation_id: str) -> None:
    """Non-Pattern-3a: matching logic on backend. GET matches."""
    _materialize_and_probe("broker-select-carriers")
    client = _client()
    resp = client._request(
        "get",
        f"/api/v1/broker/projects/{project_id}/carrier-matches",
        headers={
            "X-Flywheel-Correlation-ID": correlation_id,
            "X-Flywheel-Skill": "broker-select-carriers",
        },
    )
    assert isinstance(resp, (list, dict)), (
        f"carrier-matches returned unexpected type: {type(resp).__name__}"
    )
    print(f"  [select-carriers] OK", file=sys.stderr)


def step_draft_emails(project_id: str, correlation_id: str) -> None:
    """Pattern 3a: materialize + extract + save + DB."""
    _materialize_and_probe("broker-draft-emails")
    _probe_extract("solicitation-draft", project_id, correlation_id, "broker-draft-emails")
    _probe_save(
        "solicitation-draft",
        project_id,
        correlation_id,
        "broker-draft-emails",
        CANNED_SOLICITATION_TOOL_USE,
    )
    _verify_db_rows(project_id, {"solicitations": 1})


STEPS: list[tuple[str, Callable[[str, str], None]]] = [
    ("broker-parse-contract", step_parse_contract),
    ("broker-parse-policies", step_parse_policies),
    ("broker-gap-analysis", step_gap_analysis),
    ("broker-select-carriers", step_select_carriers),
    ("broker-draft-emails", step_draft_emails),
]


# -------------------------- offline simulation --------------------------

def _offline_sim(project_id: str, correlation_id: str) -> None:
    """SC2 evidence: warm cache, switch FLYWHEEL_API_URL, expect WARN + serve.

    Two-phase probe:
        1. Warm cache — call ``fetch_skill_assets_bundle(broker-parse-contract)``
           once against the live backend so the cache is populated.
        2. Flip ``FLYWHEEL_API_URL`` to ``http://127.0.0.1:1`` (RST-ing
           port that httpx resolves to ConnectError) and re-invoke the
           fetch. Plan 01's offline-fallback path should emit the
           locked ``WARN: Backend unreachable.`` stderr line and serve
           cached bytes.

    Restores the original ``FLYWHEEL_API_URL`` env var on exit (even
    on exception) so a subsequent run isn't left in offline mode."""
    from flywheel_mcp.api_client import FlywheelClient

    print("\n=== SC2: Offline cache fallback ===", file=sys.stderr)

    print("  [warmup] fetching broker-parse-contract to populate cache...", file=sys.stderr)
    FlywheelClient().fetch_skill_assets_bundle("broker-parse-contract", correlation_id=correlation_id)

    original = os.environ.get("FLYWHEEL_API_URL")
    os.environ["FLYWHEEL_API_URL"] = OFFLINE_API_URL
    try:
        print(f"  [offline] FLYWHEEL_API_URL={OFFLINE_API_URL}", file=sys.stderr)
        metadata, bundles = FlywheelClient().fetch_skill_assets_bundle(
            "broker-parse-contract",
            correlation_id=correlation_id,
        )
        assert metadata and bundles, "offline cache fallback did NOT return bundle tuple"
        print(
            f"  [offline] bundle served from cache — SC2 evidence captured",
            file=sys.stderr,
        )
        print(
            f"  [offline] NOTE: watch stderr above for 'WARN: Backend unreachable.' line",
            file=sys.stderr,
        )
    finally:
        if original is not None:
            os.environ["FLYWHEEL_API_URL"] = original
        else:
            os.environ.pop("FLYWHEEL_API_URL", None)


# --------------------------------- main ---------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Phase 151 dogfood harness — programmatic probes for SCs 1-4.",
    )
    ap.add_argument(
        "--project-id",
        required=True,
        help="UUID of a broker project to probe against (must have PDFs uploaded).",
    )
    ap.add_argument(
        "--skip-rename",
        action="store_true",
        help="Skip ~/.claude/skills/broker -> .broker.bak rename (CI mode).",
    )
    ap.add_argument(
        "--offline-sim",
        action="store_true",
        help="Run ONLY the SC2 offline simulation (assumes cache is populated).",
    )
    ap.add_argument(
        "--only",
        default=None,
        help="Run only one step (e.g. broker-parse-contract).",
    )
    args = ap.parse_args()

    if not args.skip_rename:
        _rename_broker_away()

    cid = secrets.token_hex(4)
    print(f"Dogfood correlation_id={cid}", file=sys.stderr)

    if args.offline_sim:
        _offline_sim(args.project_id, cid)
        print("\nSC2 offline-sim run complete. Verify WARN: line appeared above.")
        return

    steps_to_run = STEPS if args.only is None else [
        (n, f) for n, f in STEPS if n == args.only
    ]
    if not steps_to_run:
        known = ", ".join(n for n, _ in STEPS)
        print(f"ERROR: --only={args.only} matched no known step. Known: {known}", file=sys.stderr)
        sys.exit(2)

    total_start = time.perf_counter_ns()
    for name, fn in steps_to_run:
        print(f"\n=== {name} ===", file=sys.stderr)
        t0 = time.perf_counter_ns()
        try:
            fn(args.project_id, cid)
        except Exception as exc:
            print(f"FAIL {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)
        dt_ms = (time.perf_counter_ns() - t0) / 1e6
        print(f"PASS {name} ({dt_ms:.0f}ms)", file=sys.stderr)

    total_ms = (time.perf_counter_ns() - total_start) / 1e6
    print(f"\nAll {len(steps_to_run)} steps PASS ({total_ms:.0f}ms total)")


if __name__ == "__main__":
    main()
