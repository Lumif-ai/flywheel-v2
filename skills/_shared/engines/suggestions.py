"""
Rule-based suggestion engine for the Flywheel agenda MAINTAIN section.

Provides contextual suggestions based on:
  1. Stale context files (not updated in 30+ days)
  2. Uncaptured meeting notes (done meetings without notes flag)
  3. Idle leads (old leads without follow-up work items)
  4. Empty context store (fewer than 5 entries total)

All imports are lazy (inside function body) for graceful degradation.
Never raises exceptions -- returns empty list on any error.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STALE_THRESHOLD_DAYS = 30
IDLE_LEAD_DAYS = 14
MIN_CONTEXT_ENTRIES = 5
MAX_SUGGESTIONS = 5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_suggestions(user_id: str) -> list:
    """Return up to MAX_SUGGESTIONS rule-based suggestions for the user.

    Each suggestion is a dict with:
      - type: str (stale_context | uncaptured_notes | idle_leads | empty_context)
      - title: str
      - description: str
      - action_url: str
      - priority: int (1 = highest)

    Args:
        user_id: The user to generate suggestions for.

    Returns:
        List of suggestion dicts, ordered by priority. Empty on any error.
    """
    suggestions = []
    try:
        suggestions.extend(_check_stale_context())
        suggestions.extend(_check_uncaptured_notes(user_id))
        suggestions.extend(_check_idle_leads(user_id))
        suggestions.extend(_check_empty_context())
    except Exception as e:
        logger.debug("Suggestion engine error: %s", e)
        return []

    # Sort by priority, return up to MAX_SUGGESTIONS
    suggestions.sort(key=lambda s: s.get("priority", 99))
    return suggestions[:MAX_SUGGESTIONS]


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _check_stale_context() -> list:
    """Rule 1: Find context files not updated in STALE_THRESHOLD_DAYS days."""
    try:
        import context_utils as _cu
    except ImportError:
        return []

    suggestions = []
    try:
        manifest_path = _cu.CONTEXT_ROOT / "_manifest.md"
        if not manifest_path.exists():
            return []

        content = manifest_path.read_text(encoding="utf-8")
        now = datetime.now()
        cutoff = now - timedelta(days=STALE_THRESHOLD_DAYS)

        # Parse manifest table rows: | filename | entries | last_modified |
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith("| ---") or line.startswith("| File"):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 3:
                continue

            filename = parts[0]
            if filename.startswith("_"):
                continue  # Skip system files

            last_modified_str = parts[-1]
            try:
                last_modified = datetime.fromisoformat(
                    last_modified_str.replace("Z", "+00:00").replace("+00:00", "")
                )
                if last_modified < cutoff:
                    display_name = filename.replace(".md", "").replace("-", " ").title()
                    suggestions.append({
                        "type": "stale_context",
                        "title": "Refresh %s" % display_name,
                        "description": "Last updated %d days ago. Run a skill to bring it current."
                        % (now - last_modified).days,
                        "action_url": "/skills",
                        "priority": 1,
                    })
            except (ValueError, TypeError):
                continue

    except Exception as e:
        logger.debug("Stale context check error: %s", e)

    return suggestions


def _check_uncaptured_notes(user_id: str) -> list:
    """Rule 2: Find done meetings without captured notes."""
    try:
        import work_items as _wi
    except ImportError:
        return []

    suggestions = []
    try:
        items = _wi.list_work_items(user_id)
        for item in items:
            if (
                item.status == "done"
                and item.type == "meeting"
                and not item.skill_params.get("notes_captured")
            ):
                suggestions.append({
                    "type": "uncaptured_notes",
                    "title": "Capture notes from %s" % item.title,
                    "description": "Meeting is done but notes haven't been captured yet.",
                    "action_url": "/api/work-items/%s" % item.id,
                    "priority": 2,
                })
    except Exception as e:
        logger.debug("Uncaptured notes check error: %s", e)

    return suggestions


def _check_idle_leads(user_id: str) -> list:
    """Rule 3: Find old leads without corresponding outreach work items."""
    try:
        import context_utils as _cu
    except ImportError:
        return []

    suggestions = []
    try:
        leads_path = _cu.CONTEXT_ROOT / "outreach-leads.md"
        if not leads_path.exists():
            return []

        content = leads_path.read_text(encoding="utf-8")
        if not content.strip():
            return []

        # Check if file has entries older than IDLE_LEAD_DAYS
        now = datetime.now()
        cutoff = now - timedelta(days=IDLE_LEAD_DAYS)
        has_old_entries = False

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[") and "|" in line:
                # Entry header format: [YYYY-MM-DD | source: ... | detail]
                try:
                    date_str = line.split("|")[0].strip("[ ")
                    entry_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if entry_date < cutoff:
                        has_old_entries = True
                        break
                except (ValueError, IndexError):
                    continue

        if has_old_entries:
            suggestions.append({
                "type": "idle_leads",
                "title": "Follow up on leads",
                "description": "Some leads are over %d days old without follow-up." % IDLE_LEAD_DAYS,
                "action_url": "/skills",
                "priority": 3,
            })

    except Exception as e:
        logger.debug("Idle leads check error: %s", e)

    return suggestions


def _check_empty_context() -> list:
    """Rule 4: Check if context store has very few entries."""
    try:
        import context_utils as _cu
    except ImportError:
        return []

    suggestions = []
    try:
        manifest_path = _cu.CONTEXT_ROOT / "_manifest.md"
        if not manifest_path.exists():
            suggestions.append({
                "type": "empty_context",
                "title": "Add more intelligence",
                "description": "Your context store is empty. Start with onboarding to seed initial data.",
                "action_url": "/onboarding",
                "priority": 4,
            })
            return suggestions

        # Count total entries from manifest
        content = manifest_path.read_text(encoding="utf-8")
        total_entries = 0
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("|") or line.startswith("| ---") or line.startswith("| File"):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                try:
                    total_entries += int(parts[1])
                except (ValueError, IndexError):
                    continue

        if total_entries < MIN_CONTEXT_ENTRIES:
            suggestions.append({
                "type": "empty_context",
                "title": "Add more intelligence",
                "description": "Only %d entries in your context store. Add more to unlock smarter skills."
                % total_entries,
                "action_url": "/onboarding",
                "priority": 4,
            })

    except Exception as e:
        logger.debug("Empty context check error: %s", e)

    return suggestions
