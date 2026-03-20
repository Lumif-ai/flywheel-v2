"""
recipe_store.py - Recipe store for execution recipes (RECP-01).

Provides a Python API and CLI for saving, loading, matching, and managing
execution recipes. Recipes are YAML files stored at ~/.claude/context/_recipes/
that cache working scraping/automation patterns (code snapshots + strategy
metadata + behavioral knowledge).

Imports locking and atomic-write primitives from context_utils.py (no
reimplementation) and logs recipe lifecycle events to the shared _events.jsonl.

Public API:
  - find_recipe(domain, task) -> Optional[dict]
  - save_recipe(domain, task, recipe, _skip_event=False) -> str
  - delete_recipe(domain, task) -> bool
  - list_recipes(status=None) -> List[dict]
  - log_visit(domain, task, success=True) -> None
  - get_visit_count(domain, task, success_only=True) -> int
  - should_create_recipe(domain, task) -> bool
  - mark_stale(domain, task, reason) -> None
  - mark_suspect(domain, task, reason) -> None
  - update_verified(domain, task) -> None
  - get_recipe_health() -> dict
"""

import json
import os
import re
import tempfile
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Import flywheel infrastructure
from context_utils import (
    CONTEXT_ROOT,
    acquire_lock,
    release_lock,
    log_event,
    logger,
)

RECIPES_DIR = CONTEXT_ROOT / "_recipes"
VISITS_LOG = RECIPES_DIR / "_visits.jsonl"
VALID_STATUSES = {"active", "suspect", "stale", "broken"}
MAX_VISIT_LOG_LINES = 10000  # Rotate when exceeded

# Staleness thresholds
COUNT_DEVIATION_THRESHOLD = 0.40  # 40% deviation from expected
FIELD_FILL_RATE_DROP_THRESHOLD = 0.50  # 50% relative drop in fill rate


# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------

def _ensure_recipes_dir() -> Path:
    """Create _recipes/ directory if it doesn't exist. Returns the path."""
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    return RECIPES_DIR


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------

def _enforce_recipe_containment(path: Path) -> None:
    """Reject paths that escape RECIPES_DIR. Prevents path traversal."""
    resolved = path.resolve()
    recipes_resolved = RECIPES_DIR.resolve()
    if not str(resolved).startswith(str(recipes_resolved)):
        raise ValueError(
            "Path traversal attempt detected: %s escapes %s" % (path, RECIPES_DIR)
        )


# ---------------------------------------------------------------------------
# Recipe file naming
# ---------------------------------------------------------------------------

def _recipe_filename(domain: str, task: str) -> str:
    """Generate recipe filename from domain+task. Double underscore separator."""
    # Sanitize: replace non-alphanumeric (except dots/hyphens) with underscores
    safe_domain = re.sub(r'[^a-zA-Z0-9.\-]', '_', domain)
    safe_task = re.sub(r'[^a-zA-Z0-9\-]', '_', task)
    return "%s__%s.yaml" % (safe_domain, safe_task)


def _recipe_path(domain: str, task: str) -> Path:
    """Get the path for a recipe file, with containment enforcement."""
    path = RECIPES_DIR / _recipe_filename(domain, task)
    _enforce_recipe_containment(path)
    return path


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------

def find_recipe(domain: str, task: str) -> Optional[dict]:
    """Load a recipe by domain+task. Returns parsed YAML dict or None."""
    path = _recipe_path(domain, task)
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            recipe = yaml.safe_load(f)
        return recipe if isinstance(recipe, dict) else None
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Failed to load recipe %s: %s", path.name, e)
        return None


def save_recipe(domain: str, task: str, recipe: dict,
                _skip_event: bool = False) -> str:
    """Atomically save a recipe. Returns the file path.

    Uses file locking + tmp+rename for atomicity (same pattern as context_utils).
    Logs a recipe_create or recipe_update event unless _skip_event=True
    (used by status functions that log their own specific events).
    """
    _ensure_recipes_dir()
    path = _recipe_path(domain, task)
    is_update = path.exists()

    # Ensure required metadata
    recipe.setdefault("domain", domain)
    recipe.setdefault("task", task)
    recipe.setdefault("created", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
    recipe["last_verified"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    recipe.setdefault("use_count", 0)
    recipe.setdefault("status", "active")

    # Atomic write with lock
    lock_fd = acquire_lock(path, timeout=5.0)
    try:
        # Write to temp file first
        fd, tmp_path = tempfile.mkstemp(
            dir=str(RECIPES_DIR), suffix=".yaml.tmp"
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                yaml.dump(recipe, f, default_flow_style=False,
                          sort_keys=False, allow_unicode=True)
            os.replace(tmp_path, str(path))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    finally:
        release_lock(lock_fd)

    # Log event (skipped when called from status functions to avoid double logging)
    if not _skip_event:
        event_type = "recipe_update" if is_update else "recipe_create"
        log_event(event_type, "_recipes/%s" % path.name, "recipe-store",
                  detail="%s:%s" % (domain, task))

    return str(path)


def delete_recipe(domain: str, task: str) -> bool:
    """Delete a recipe file. Returns True if deleted, False if not found."""
    path = _recipe_path(domain, task)
    if not path.exists():
        return False
    lock_fd = acquire_lock(path, timeout=5.0)
    try:
        path.unlink()
    finally:
        release_lock(lock_fd)
    log_event("recipe_delete", "_recipes/%s" % _recipe_filename(domain, task),
              "recipe-store", detail="%s:%s" % (domain, task))
    return True


def list_recipes(status: Optional[str] = None) -> List[dict]:
    """List all recipes, optionally filtered by status.
    Returns list of dicts with domain, task, status, use_count, last_verified."""
    if not RECIPES_DIR.exists():
        return []
    results = []
    for path in sorted(RECIPES_DIR.glob("*.yaml")):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                recipe = yaml.safe_load(f)
            if not isinstance(recipe, dict):
                continue
            if status and recipe.get("status") != status:
                continue
            results.append({
                "domain": recipe.get("domain", ""),
                "task": recipe.get("task", ""),
                "status": recipe.get("status", "unknown"),
                "use_count": recipe.get("use_count", 0),
                "last_verified": recipe.get("last_verified", ""),
                "created": recipe.get("created", ""),
                "file": path.name,
            })
        except (yaml.YAMLError, OSError):
            continue
    return results


# ---------------------------------------------------------------------------
# Status management
# ---------------------------------------------------------------------------

def mark_stale(domain: str, task: str, reason: str) -> None:
    """Mark a recipe as stale with a reason."""
    recipe = find_recipe(domain, task)
    if recipe is None:
        return
    recipe["status"] = "stale"
    recipe["stale_reason"] = reason
    recipe["stale_since"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_recipe(domain, task, recipe, _skip_event=True)
    log_event("recipe_stale", "_recipes/%s" % _recipe_filename(domain, task),
              "recipe-store", detail=reason)


def mark_suspect(domain: str, task: str, reason: str) -> None:
    """Mark a recipe as suspect (possible staleness)."""
    recipe = find_recipe(domain, task)
    if recipe is None:
        return
    prev_status = recipe.get("status", "active")
    if prev_status == "suspect":
        # Second consecutive suspect -> escalate to stale
        mark_stale(domain, task, "consecutive suspect: %s" % reason)
        return
    recipe["status"] = "suspect"
    recipe["suspect_reason"] = reason
    save_recipe(domain, task, recipe, _skip_event=True)
    log_event("recipe_suspect", "_recipes/%s" % _recipe_filename(domain, task),
              "recipe-store", detail=reason)


def update_verified(domain: str, task: str) -> None:
    """Update last_verified timestamp and increment use_count. Clears suspect status."""
    recipe = find_recipe(domain, task)
    if recipe is None:
        return
    recipe["last_verified"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    recipe["last_used"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    recipe["use_count"] = recipe.get("use_count", 0) + 1
    recipe["status"] = "active"  # Clear suspect on successful use
    # Clear suspect/stale fields
    recipe.pop("suspect_reason", None)
    recipe.pop("stale_reason", None)
    recipe.pop("stale_since", None)
    save_recipe(domain, task, recipe)


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


def check_count_deviation(actual_count: int, recipe: dict) -> Optional[str]:
    """Check if actual record count deviates significantly from baseline.

    Returns a reason string if deviation exceeds threshold, None otherwise.
    """
    baseline = recipe.get("quality_baseline", {})
    expected = baseline.get("expected_records_per_page")
    if expected is None or expected == 0:
        return None  # No baseline to compare against

    deviation = abs(actual_count - expected) / expected
    if deviation > COUNT_DEVIATION_THRESHOLD:
        return ("count deviation %.0f%% (expected %d, got %d)"
                % (deviation * 100, expected, actual_count))
    return None


def check_field_completeness(actual_fill_rates: dict, recipe: dict) -> Optional[str]:
    """Check if any field's fill rate dropped significantly from baseline.

    Args:
        actual_fill_rates: dict of field_name -> fill_rate (0.0 to 1.0)
        recipe: the recipe dict with quality_baseline.field_fill_rates

    Returns a reason string if any field dropped >50% relatively, None otherwise.
    """
    baseline = recipe.get("quality_baseline", {})
    expected_rates = baseline.get("field_fill_rates", {})
    if not expected_rates:
        return None

    for field, expected_rate in expected_rates.items():
        if expected_rate <= 0:
            continue
        actual_rate = actual_fill_rates.get(field, 0.0)
        relative_drop = (expected_rate - actual_rate) / expected_rate
        if relative_drop > FIELD_FILL_RATE_DROP_THRESHOLD:
            return ("field '%s' fill rate dropped %.0f%% (expected %.0f%%, got %.0f%%)"
                    % (field, relative_drop * 100, expected_rate * 100, actual_rate * 100))
    return None


def check_staleness(
    domain: str,
    task: str,
    actual_count: int,
    actual_fill_rates: dict,
    extraction_error: Optional[str] = None,
) -> dict:
    """Run all staleness checks and take appropriate action.

    Args:
        domain: recipe domain
        task: recipe task
        actual_count: number of records extracted
        actual_fill_rates: dict of field_name -> fill_rate (0.0-1.0)
        extraction_error: error message if extraction code threw

    Returns dict with:
        - status: "ok", "suspect", "stale"
        - reason: explanation string (empty if ok)
        - action_taken: what was done (e.g., "marked suspect", "marked stale")
    """
    recipe = find_recipe(domain, task)
    if recipe is None:
        return {"status": "ok", "reason": "no recipe to check", "action_taken": "none"}

    # Layer 1: Zero results or extraction error -> immediate STALE
    if extraction_error or actual_count == 0:
        reason = extraction_error or "zero results extracted"
        mark_stale(domain, task, reason)
        return {"status": "stale", "reason": reason, "action_taken": "marked stale"}

    # Layer 2: Count deviation -> SUSPECT
    count_reason = check_count_deviation(actual_count, recipe)
    if count_reason:
        mark_suspect(domain, task, count_reason)
        # Re-read to check if it escalated to stale (consecutive suspect)
        updated = find_recipe(domain, task)
        final_status = updated.get("status", "suspect") if updated else "suspect"
        return {
            "status": final_status,
            "reason": count_reason,
            "action_taken": "marked %s" % final_status,
        }

    # Layer 3: Field completeness -> SUSPECT
    field_reason = check_field_completeness(actual_fill_rates, recipe)
    if field_reason:
        mark_suspect(domain, task, field_reason)
        updated = find_recipe(domain, task)
        final_status = updated.get("status", "suspect") if updated else "suspect"
        return {
            "status": final_status,
            "reason": field_reason,
            "action_taken": "marked %s" % final_status,
        }

    # All checks passed
    return {"status": "ok", "reason": "", "action_taken": "none"}


def mark_broken(domain: str, task: str, reason: str) -> None:
    """Mark a recipe as broken (stale + regeneration failed).

    Called when: recipe was stale, skill fell back to fresh DOM exploration,
    and fresh exploration ALSO failed. This is the terminal failure state.
    """
    recipe = find_recipe(domain, task)
    if recipe is None:
        return
    recipe["status"] = "broken"
    recipe["broken_reason"] = reason
    recipe["broken_since"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_recipe(domain, task, recipe, _skip_event=True)
    log_event("recipe_broken", "_recipes/%s" % _recipe_filename(domain, task),
              "recipe-store", detail=reason)


# ---------------------------------------------------------------------------
# Visit log tracking with rotation
# ---------------------------------------------------------------------------

def _rotate_visit_log_if_needed() -> None:
    """Rotate visit log if it exceeds MAX_VISIT_LOG_LINES.
    Keeps the most recent half of entries. Same pattern as context_utils
    event log rotation."""
    if not VISITS_LOG.exists():
        return
    try:
        with open(VISITS_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) <= MAX_VISIT_LOG_LINES:
            return
        # Keep the most recent half
        keep_from = len(lines) // 2
        lock_fd = acquire_lock(VISITS_LOG, timeout=5.0)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(RECIPES_DIR), suffix=".jsonl.tmp"
            )
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.writelines(lines[keep_from:])
            os.replace(tmp_path, str(VISITS_LOG))
        finally:
            release_lock(lock_fd)
        logger.info("Rotated visit log: kept %d of %d entries",
                     len(lines) - keep_from, len(lines))
    except OSError as e:
        logger.warning("Failed to rotate visit log: %s", e)


def log_visit(domain: str, task: str, success: bool = True) -> None:
    """Log a site visit to the visits log. Used for 'second hit' recipe creation."""
    _ensure_recipes_dir()
    entry = {
        "domain": domain,
        "task": task,
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "success": success,
    }
    # Atomic append with lock
    lock_fd = acquire_lock(VISITS_LOG, timeout=5.0)
    try:
        with open(VISITS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
    finally:
        release_lock(lock_fd)
    # Check rotation (outside lock to avoid holding it too long)
    _rotate_visit_log_if_needed()


def get_visit_count(domain: str, task: str, success_only: bool = True) -> int:
    """Count visits for a domain+task pair."""
    if not VISITS_LOG.exists():
        return 0
    count = 0
    try:
        with open(VISITS_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if (entry.get("domain") == domain
                            and entry.get("task") == task):
                        if success_only and not entry.get("success", True):
                            continue
                        count += 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        return 0
    return count


def should_create_recipe(domain: str, task: str) -> bool:
    """Check if we should create a recipe (second hit heuristic).
    Returns True if: no recipe exists AND visit count >= 1
    (meaning this is the 2nd+ visit).
    """
    if find_recipe(domain, task) is not None:
        return False  # Recipe already exists
    return get_visit_count(domain, task) >= 1


# ---------------------------------------------------------------------------
# Health metrics
# ---------------------------------------------------------------------------

def get_recipe_health() -> dict:
    """Return recipe store health metrics for the health dashboard."""
    recipes = list_recipes()
    total = len(recipes)
    by_status = {}
    oldest_unverified = None
    most_used = None

    for r in recipes:
        status = r.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

        verified = r.get("last_verified", "")
        if verified and (oldest_unverified is None
                         or verified < oldest_unverified):
            oldest_unverified = verified

        use_count = r.get("use_count", 0)
        if most_used is None or use_count > most_used.get("use_count", 0):
            most_used = r

    # Visit log size
    visit_count = 0
    if VISITS_LOG.exists():
        try:
            with open(VISITS_LOG, 'r') as f:
                visit_count = sum(1 for line in f if line.strip())
        except OSError:
            pass

    return {
        "total_recipes": total,
        "by_status": by_status,
        "oldest_unverified": oldest_unverified,
        "most_used": most_used,
        "visit_log_entries": visit_count,
    }


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _cli_arg(args: list, flag: str, required: bool = True) -> Optional[str]:
    """Extract a --flag value from args list."""
    try:
        idx = args.index(flag)
        return args[idx + 1]
    except (ValueError, IndexError):
        if required:
            print("Missing required argument: %s" % flag)
            import sys
            sys.exit(1)
        return None


def _cli():
    """CLI entry point for recipe_store."""
    import sys
    args = sys.argv[1:]
    if not args:
        print("Usage: recipe_store.py <command> [options]")
        print("Commands: lookup, list, save, delete, log-visit, check-visits,")
        print("          check-staleness, mark-broken, update-verified, health")
        sys.exit(1)

    cmd = args[0]

    if cmd == "lookup":
        # --domain X --task Y
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        recipe = find_recipe(domain, task)
        if recipe:
            print(yaml.dump(recipe, default_flow_style=False, sort_keys=False))
        else:
            print("No recipe found for %s:%s" % (domain, task))
            sys.exit(1)

    elif cmd == "list":
        status = _cli_arg(args, "--status", required=False)
        recipes = list_recipes(status=status)
        if not recipes:
            print("No recipes found.")
        for r in recipes:
            print("%s:%s  status=%s  uses=%d  verified=%s" % (
                r["domain"], r["task"], r["status"],
                r["use_count"], r["last_verified"]))

    elif cmd == "save":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        file_path = _cli_arg(args, "--file")
        with open(file_path, 'r') as f:
            recipe = yaml.safe_load(f)
        path = save_recipe(domain, task, recipe)
        print("Saved: %s" % path)

    elif cmd == "delete":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        if delete_recipe(domain, task):
            print("Deleted recipe for %s:%s" % (domain, task))
        else:
            print("No recipe found for %s:%s" % (domain, task))

    elif cmd == "log-visit":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        log_visit(domain, task)
        print("Visit logged for %s:%s" % (domain, task))

    elif cmd == "check-visits":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        count = get_visit_count(domain, task)
        should = should_create_recipe(domain, task)
        print("Visits for %s:%s: %d (create recipe: %s)" % (
            domain, task, count, should))

    elif cmd == "check-staleness":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        count = int(_cli_arg(args, "--count"))
        fill_rates_str = _cli_arg(args, "--fill-rates", required=False)
        error = _cli_arg(args, "--error", required=False)
        fill_rates = json.loads(fill_rates_str) if fill_rates_str else {}
        result = check_staleness(domain, task, count, fill_rates, extraction_error=error)
        print(json.dumps(result))

    elif cmd == "mark-broken":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        reason = _cli_arg(args, "--reason")
        mark_broken(domain, task, reason)
        print("Marked broken: %s:%s (%s)" % (domain, task, reason))

    elif cmd == "update-verified":
        domain = _cli_arg(args, "--domain")
        task = _cli_arg(args, "--task")
        update_verified(domain, task)
        print("Updated verified for %s:%s" % (domain, task))

    elif cmd == "health":
        health = get_recipe_health()
        print("Total recipes: %d" % health["total_recipes"])
        for status, count in health["by_status"].items():
            print("  %s: %d" % (status, count))
        if health["most_used"]:
            mr = health["most_used"]
            print("Most used: %s:%s (%d uses)" % (
                mr["domain"], mr["task"], mr["use_count"]))
        print("Visit log entries: %d" % health["visit_log_entries"])

    else:
        print("Unknown command: %s" % cmd)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
