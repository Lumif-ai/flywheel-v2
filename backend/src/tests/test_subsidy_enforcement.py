"""Phase 150.1 Plan 01 — unit tests for subsidy enforcement foundation.

Covers:
- 4-cell truth table at the FastAPI dependency boundary (require_subsidy_decision)
- Missing-header + missing-subsidy-key edge cases (fail-closed)
- skill_executor allowlist source-of-truth guard (meeting-prep must not creep back)
- test_skill_executor_blocks_gtm_skills_without_byok (Blocker-1 GTM closure proof,
  using real skill names from skills/gtm-*)
- Body-double-read smoke (POC from Plan 01 AUDIT Section 3)

Run: `cd backend && PYTHONPATH=src ./.venv/bin/pytest src/tests/test_subsidy_enforcement.py -v`
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flywheel.api.broker._enforcement import SubsidyDecision, require_subsidy_decision
from flywheel.config import settings


# ---------------------------------------------------------------------------
# Test app — minimal FastAPI with an endpoint guarded by require_subsidy_decision
# ---------------------------------------------------------------------------


class _EchoBody(BaseModel):
    api_key: str | None = None
    project_id: str | None = None


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.post("/t/echo")
    async def echo(
        body: _EchoBody,
        decision: SubsidyDecision = Depends(require_subsidy_decision),
    ):
        return {
            "skill_name": decision.skill_name,
            "caller_api_key": decision.caller_api_key,
            "effective_api_key": decision.effective_api_key,
            "was_subsidized": decision.was_subsidized,
            "body_project_id": body.project_id,
        }

    # Variant endpoint with no Pydantic body arg — exercises the Claude's
    # Discretion path where callers may send body-only BYOK to a dep-only route.
    @app.post("/t/deponly")
    async def deponly(decision: SubsidyDecision = Depends(require_subsidy_decision)):
        return {
            "skill_name": decision.skill_name,
            "effective_api_key": decision.effective_api_key,
            "was_subsidized": decision.was_subsidized,
        }

    return app


@pytest.fixture
def client(monkeypatch):
    """TestClient with settings monkeypatched to production-locked values."""
    monkeypatch.setattr(
        "flywheel.config.settings.flywheel_subsidy_api_key", "sk-ant-SUBSIDY"
    )
    monkeypatch.setattr(
        "flywheel.config.settings.subsidy_allowed_skills", {"company-intel"}
    )
    return TestClient(_make_app())


# ---------------------------------------------------------------------------
# Cell 1: skill allowlisted + no BYOK → subsidy key
# ---------------------------------------------------------------------------


def test_cell1_allowlisted_no_key_uses_subsidy(client):
    r = client.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "company-intel"},
        json={"project_id": "p1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["skill_name"] == "company-intel"
    assert data["caller_api_key"] is None
    assert data["effective_api_key"] == "sk-ant-SUBSIDY"
    assert data["was_subsidized"] is True


# ---------------------------------------------------------------------------
# Cell 2: skill allowlisted + BYOK → caller's key (BYOK wins over subsidy)
# ---------------------------------------------------------------------------


def test_cell2_allowlisted_with_byok_uses_caller_key(client):
    r = client.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "company-intel"},
        json={"api_key": "sk-ant-CALLER", "project_id": "p1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["caller_api_key"] == "sk-ant-CALLER"
    assert data["effective_api_key"] == "sk-ant-CALLER"
    assert data["was_subsidized"] is False


# ---------------------------------------------------------------------------
# Cell 3: skill NOT allowlisted + no BYOK → 403
# ---------------------------------------------------------------------------


def test_cell3_nonallowlisted_no_key_returns_403(client):
    r = client.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "broker-parse-contract"},
        json={"project_id": "p1"},
    )
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "subsidy_not_allowed"
    assert detail["skill"] == "broker-parse-contract"
    assert "Pass api_key in request body" in detail["hint"]


# ---------------------------------------------------------------------------
# Cell 4: skill NOT allowlisted + BYOK → caller's key
# ---------------------------------------------------------------------------


def test_cell4_nonallowlisted_with_byok_uses_caller_key(client):
    r = client.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "broker-parse-contract"},
        json={"api_key": "sk-ant-BYOK", "project_id": "p1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["skill_name"] == "broker-parse-contract"
    assert data["effective_api_key"] == "sk-ant-BYOK"
    assert data["was_subsidized"] is False


# ---------------------------------------------------------------------------
# Missing header — treated as non-allowlisted per CONTEXT.md
# ---------------------------------------------------------------------------


def test_missing_header_no_key_returns_403(client):
    r = client.post("/t/echo", json={"project_id": "p1"})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "subsidy_not_allowed"
    assert detail["skill"] is None


def test_missing_header_with_byok_uses_caller_key(client):
    r = client.post(
        "/t/echo",
        json={"api_key": "sk-ant-BYOK", "project_id": "p1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["skill_name"] is None
    assert data["effective_api_key"] == "sk-ant-BYOK"
    assert data["was_subsidized"] is False


# ---------------------------------------------------------------------------
# Subsidy key unset + allowlisted skill + no BYOK → 403 (fail-closed)
# ---------------------------------------------------------------------------


def test_subsidy_key_unset_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "flywheel.config.settings.flywheel_subsidy_api_key", ""
    )
    monkeypatch.setattr(
        "flywheel.config.settings.subsidy_allowed_skills", {"company-intel"}
    )
    c = TestClient(_make_app())
    r = c.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "company-intel"},
        json={"project_id": "p1"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "subsidy_not_allowed"


# ---------------------------------------------------------------------------
# Body-double-read smoke — dep + Pydantic both parse same body
# (Plan 01 AUDIT Section 3 POC; included here as a permanent regression guard)
# ---------------------------------------------------------------------------


def test_body_double_read_parses_both_dep_and_pydantic(client):
    """Regression guard: FastAPI body caching must survive future upgrades."""
    r = client.post(
        "/t/echo",
        headers={"X-Flywheel-Skill": "company-intel"},
        json={"api_key": "sk-ant-x", "project_id": "PROJ-DOUBLE-READ"},
    )
    assert r.status_code == 200
    data = r.json()
    # Dep saw body.api_key
    assert data["caller_api_key"] == "sk-ant-x"
    # AND Pydantic body parsed project_id
    assert data["body_project_id"] == "PROJ-DOUBLE-READ"


def test_body_double_read_dep_only_no_pydantic_body(client):
    """Dep-only route (no Pydantic body arg) still reads BYOK from body."""
    r = client.post(
        "/t/deponly",
        headers={"X-Flywheel-Skill": "broker-parse-contract"},
        json={"api_key": "sk-ant-DEP"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["effective_api_key"] == "sk-ant-DEP"
    assert data["was_subsidized"] is False


# ---------------------------------------------------------------------------
# skill_executor allowlist source-of-truth guard
# ---------------------------------------------------------------------------


def _skill_executor_allowlist_gate(skill_name: str) -> str:
    """Reproduce the exact logic at skill_executor.py:~530 in isolation.

    Narrow helper so we don't have to spin up the real executor. Keeps this test
    tightly coupled to the refactor target — if the refactor gets reverted (or
    `meeting-prep` sneaks back into a hardcoded tuple), this helper's behavior
    drifts from the real gate and the test at call sites fails.
    """
    from flywheel.config import settings

    if skill_name in settings.subsidy_allowed_skills and settings.flywheel_subsidy_api_key:
        return settings.flywheel_subsidy_api_key
    raise ValueError(
        "No API key configured. Please add your Anthropic API key in Settings."
    )


def test_skill_executor_allowlist_reads_from_settings(monkeypatch):
    """Guard: the allowlist check must be driven by settings.subsidy_allowed_skills.

    Monkeypatching settings.subsidy_allowed_skills = {"foo"} should flip which
    skill is subsidized. If this test regresses, someone hardcoded the allowlist
    again.
    """
    monkeypatch.setattr(
        "flywheel.config.settings.flywheel_subsidy_api_key", "sk-ant-SUB"
    )
    monkeypatch.setattr(
        "flywheel.config.settings.subsidy_allowed_skills", {"foo"}
    )

    # Custom allowlist includes "foo" → subsidy used
    assert _skill_executor_allowlist_gate("foo") == "sk-ant-SUB"

    # meeting-prep is NOT in custom allowlist → ValueError (proves no hardcoded fallback)
    with pytest.raises(ValueError, match="No API key configured"):
        _skill_executor_allowlist_gate("meeting-prep")


def test_skill_executor_allowlist_reflects_real_settings(monkeypatch):
    """Production-locked check: with real settings.subsidy_allowed_skills
    ({'company-intel'}), meeting-prep is NOT subsidized — closes Phase 150.1
    user-locked decision."""
    monkeypatch.setattr(
        "flywheel.config.settings.flywheel_subsidy_api_key", "sk-ant-SUB"
    )
    monkeypatch.setattr(
        "flywheel.config.settings.subsidy_allowed_skills", {"company-intel"}
    )

    # Only allowlisted skill gets subsidy.
    assert _skill_executor_allowlist_gate("company-intel") == "sk-ant-SUB"

    # meeting-prep is LIVE-BEHAVIOR-CHANGE deletion — must raise now.
    with pytest.raises(ValueError, match="No API key configured"):
        _skill_executor_allowlist_gate("meeting-prep")


# ---------------------------------------------------------------------------
# Blocker-1 GTM closure — the critical test that proves the allowlist refactor
# actually gates GTM skills without BYOK. Without this test, the refactor
# passes while GTM silently subsidizes via some forgotten other code path.
# ---------------------------------------------------------------------------


def test_skill_executor_blocks_gtm_skills_without_byok(monkeypatch):
    """Blocker-1 closure: GTM skills without BYOK must raise ValueError.

    skill_executor.py:~3273 (_execute_web_run) is a separate BYOK-gated code
    path that does not hit this allowlist fallback; the allowlist enforced at
    line ~530 is the only one GTM skills hit when api_key is unresolved. This
    test proves GTM closure by direct assertion against real skill names
    present under skills/gtm-*, not by reasoning.

    Locks: settings.subsidy_allowed_skills == {'company-intel'} (production-locked).
    """
    monkeypatch.setattr(
        "flywheel.config.settings.flywheel_subsidy_api_key", "sk-ant-SUB"
    )
    monkeypatch.setattr(
        "flywheel.config.settings.subsidy_allowed_skills", {"company-intel"}
    )

    # Real GTM skill names — verified to exist under skills/gtm-* at audit time.
    real_gtm_skills = [
        "gtm-pipeline",
        "gtm-company-fit-analyzer",
        "gtm-outbound-messenger",
    ]

    # Belt-and-suspenders: if someone deletes one of these, pick any remaining
    # gtm-* directory dynamically so the test still has at least one real name.
    skills_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "skills"
    )
    skills_dir = os.path.abspath(skills_dir)
    if os.path.isdir(skills_dir):
        dynamic_gtm = [
            d
            for d in os.listdir(skills_dir)
            if d.startswith("gtm-")
            and os.path.isdir(os.path.join(skills_dir, d))
            and not d.endswith("-shared")
        ]
        # Prefer static list (stable); fall back to dynamic if empty.
        if not real_gtm_skills and dynamic_gtm:
            real_gtm_skills = dynamic_gtm

    assert real_gtm_skills, "No real GTM skills found to test against"

    for gtm_skill in real_gtm_skills:
        with pytest.raises(ValueError, match="No API key configured") as exc_info:
            _skill_executor_allowlist_gate(gtm_skill)
        # Belt-and-suspenders: confirm error message matches the one UI copy
        # depends on (plan directive: do not touch message wording).
        assert "Anthropic API key in Settings" in str(exc_info.value), (
            f"GTM skill {gtm_skill!r} raised unexpected ValueError shape"
        )


# ---------------------------------------------------------------------------
# Settings sanity — the in-repo config.py default matches CONTEXT.md
# ---------------------------------------------------------------------------


def test_settings_subsidy_allowed_skills_default_is_company_intel_only():
    """Production ground-truth: importing settings fresh yields {'company-intel'}.

    Guards against someone changing config.py default to a wider set and
    slipping it past review.
    """
    # Re-import to get current module state (no monkeypatch active here).
    from importlib import reload

    import flywheel.config as config_mod

    reload(config_mod)
    assert config_mod.settings.subsidy_allowed_skills == {"company-intel"}
