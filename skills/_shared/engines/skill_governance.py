"""
Skill governance utilities for headless execution.

Provides git-based skill versioning (init, commit, rollback, history),
token budget enforcement (soft limits -- advisory only, never blocks),
contract violation logging (JSONL), and graceful empty context handling.

Lightweight governance for an internal developer team: no approval
workflows, no hard blocks.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# DEPRECATED (Phase 152 — 2026-04-19): legacy ~/.claude/skills/ path; skills are served via flywheel_fetch_skill_assets. Retained for developer tooling only; no runtime impact.
SKILLS_DIR = Path.home() / ".claude" / "skills"

DEFAULT_TOKEN_BUDGET = 50000

TOKEN_BUDGETS: Dict[str, int] = {
    "meeting-prep": 50000,
    "gtm-company-fit-analyzer": 100000,
    "social-media-manager": 30000,
}

VIOLATION_LOG = Path.home() / ".claude" / "logs" / "contract_violations.jsonl"

# Known context files mapped to population suggestions
_EMPTY_CONTEXT_SUGGESTIONS: Dict[str, str] = {
    "positioning.md": "Use the gtm-my-company skill",
    "contacts.md": "Process a meeting transcript with meeting-processor",
    "competitive-intel.md": "Run meeting-prep for a competitor's customer",
}


# ---------------------------------------------------------------------------
# Git versioning
# ---------------------------------------------------------------------------

def _run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command, returning CompletedProcess. Raises on failure."""
    env = dict(os.environ)
    # Ensure git has author/committer identity for commits
    env.setdefault("GIT_AUTHOR_NAME", "flywheel")
    env.setdefault("GIT_AUTHOR_EMAIL", "flywheel@local")
    env.setdefault("GIT_COMMITTER_NAME", "flywheel")
    env.setdefault("GIT_COMMITTER_EMAIL", "flywheel@local")
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )


def init_skills_repo(skills_dir: Optional[Path] = None) -> bool:
    """Initialize a git repo in the skills directory if one doesn't exist.

    Args:
        skills_dir: Directory to initialize. Defaults to SKILLS_DIR.

    Returns:
        True if newly initialized, False if already a git repo.
    """
    skills_dir = skills_dir or SKILLS_DIR
    skills_dir.mkdir(parents=True, exist_ok=True)

    if (skills_dir / ".git").exists():
        return False

    try:
        _run_git(["init"], cwd=skills_dir)
        _run_git(["add", "-A"], cwd=skills_dir)
        # Allow empty initial commit if directory has no files yet
        _run_git(
            ["commit", "--allow-empty", "-m", "initial: track skills directory"],
            cwd=skills_dir,
        )
    except subprocess.CalledProcessError:
        return False

    return True


def commit_skill_update(
    skill_name: str,
    message: Optional[str] = None,
    skills_dir: Optional[Path] = None,
) -> str:
    """Commit changes for a specific skill.

    Args:
        skill_name: Name of the skill subdirectory.
        message: Commit message. Defaults to "skill: update {skill_name}".
        skills_dir: Skills directory. Defaults to SKILLS_DIR.

    Returns:
        Commit hash string, or empty string if nothing to commit.
    """
    skills_dir = skills_dir or SKILLS_DIR
    message = message or f"skill: update {skill_name}"

    try:
        _run_git(["add", f"{skill_name}/"], cwd=skills_dir)
    except subprocess.CalledProcessError:
        return ""

    # Check if there's anything staged
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(skills_dir),
        capture_output=True,
    )
    if result.returncode == 0:
        # Nothing staged
        return ""

    try:
        _run_git(["commit", "-m", message], cwd=skills_dir)
        result = _run_git(["log", "-1", "--format=%H"], cwd=skills_dir)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def rollback_skill(
    skill_name: str,
    commit_hash: str,
    skills_dir: Optional[Path] = None,
) -> bool:
    """Rollback a skill's SKILL.md to a previous commit.

    Args:
        skill_name: Name of the skill subdirectory.
        commit_hash: The commit hash to restore from.
        skills_dir: Skills directory. Defaults to SKILLS_DIR.

    Returns:
        True on success, False on failure.
    """
    skills_dir = skills_dir or SKILLS_DIR

    try:
        _run_git(
            ["checkout", commit_hash, "--", f"{skill_name}/SKILL.md"],
            cwd=skills_dir,
        )
        _run_git(
            ["commit", "-m", f"skill: rollback {skill_name} to {commit_hash[:7]}"],
            cwd=skills_dir,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_skill_history(
    skill_name: str,
    limit: int = 10,
    skills_dir: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Get commit history for a skill's SKILL.md.

    Args:
        skill_name: Name of the skill subdirectory.
        limit: Maximum number of entries to return.
        skills_dir: Skills directory. Defaults to SKILLS_DIR.

    Returns:
        List of {"hash": str, "message": str} dicts, newest first.
    """
    skills_dir = skills_dir or SKILLS_DIR

    try:
        result = _run_git(
            ["log", "--oneline", f"-n{limit}", "--", f"{skill_name}/SKILL.md"],
            cwd=skills_dir,
        )
    except subprocess.CalledProcessError:
        return []

    entries = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            entries.append({"hash": parts[0], "message": parts[1]})
    return entries


# ---------------------------------------------------------------------------
# Token budget enforcement (advisory only)
# ---------------------------------------------------------------------------

def check_token_budget(skill_name: str, tokens_used: int) -> Dict:
    """Check token usage against the skill's budget.

    This is purely informational -- it NEVER raises or blocks execution.

    Args:
        skill_name: Name of the skill.
        tokens_used: Number of tokens consumed.

    Returns:
        Dict with skill, budget, used, exceeded (bool), overage (int).
    """
    budget = TOKEN_BUDGETS.get(skill_name, DEFAULT_TOKEN_BUDGET)
    exceeded = tokens_used > budget
    overage = max(0, tokens_used - budget)

    return {
        "skill": skill_name,
        "budget": budget,
        "used": tokens_used,
        "exceeded": exceeded,
        "overage": overage,
    }


# ---------------------------------------------------------------------------
# Contract violation logging
# ---------------------------------------------------------------------------

def log_contract_violation(
    skill_name: str,
    operation: str,
    target_file: str,
    user_id: str = "",
) -> None:
    """Log a contract violation to the JSONL violation log.

    Silent on IOError -- logging must never block execution.

    Args:
        skill_name: The skill that violated its contract.
        operation: The operation attempted (e.g. "write", "read").
        target_file: The context file targeted.
        user_id: Optional user identifier.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill_name": skill_name,
        "operation": operation,
        "target_file": target_file,
        "user_id": user_id,
    }

    try:
        VIOLATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(VIOLATION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError:
        pass


# ---------------------------------------------------------------------------
# Empty context handling
# ---------------------------------------------------------------------------

def handle_empty_context(content: str, file_name: str) -> Tuple[str, str]:
    """Handle potentially empty context file content.

    If the content is empty or whitespace-only, returns an empty string
    and a helpful suggestion for populating the file.

    Args:
        content: The raw content from the context file.
        file_name: The name of the context file (e.g. "positioning.md").

    Returns:
        Tuple of (content, suggestion). If content is non-empty,
        suggestion is empty. If content is empty, content is empty
        string and suggestion explains how to populate.
    """
    if not content or not content.strip():
        specific = _EMPTY_CONTEXT_SUGGESTIONS.get(file_name)
        if specific:
            suggestion = (
                f"Context file '{file_name}' is empty. {specific}."
            )
        else:
            suggestion = (
                f"Context file '{file_name}' is empty. "
                "Check _catalog.md for which skills write to this file."
            )
        return ("", suggestion)

    return (content, "")
