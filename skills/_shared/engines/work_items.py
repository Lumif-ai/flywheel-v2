"""
Work item data layer for Flywheel agenda.

Provides a Pydantic model, CRUD operations, and JSON persistence per user.
Work items represent meetings, outreach tasks, reviews, demos, and other
agenda items that can trigger skill execution.

Storage: ~/.claude/users/{user_id}/work_items.json (atomic writes via temp+rename).
"""

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable root for test isolation (patch in tests, same as user_memory.py)
# ---------------------------------------------------------------------------

WORK_ITEMS_ROOT = Path.home() / ".claude" / "users"

# ---------------------------------------------------------------------------
# Work-type to skill mapping
# ---------------------------------------------------------------------------

WORK_TYPE_SKILLS = {
    "meeting": "meeting-prep",
    "outreach": "gtm-outbound-messenger",
    "legal_review": "legal-review",
    "demo": "demo-script",
    "collateral": "sales-collateral",
    "analysis": "company-fit-analyzer",
    "custom": None,
}

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS = {
    ("upcoming", "preparing"),
    ("preparing", "ready"),
    ("ready", "needs_review"),
    ("needs_review", "done"),
    ("upcoming", "done"),  # skip shortcut
    ("ready", "done"),  # capture complete
}

# Any status can reset to upcoming
_RESET_TARGET = "upcoming"

# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class WorkItem(BaseModel):
    """A single work item on the user's agenda."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    type: str  # "meeting" | "outreach" | "legal_review" | "demo" | "collateral" | "analysis" | "custom"
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string
    status: str = "upcoming"  # upcoming | preparing | ready | needs_review | done
    skill_name: str
    skill_params: dict = Field(default_factory=dict)
    skill_output_id: Optional[str] = None
    captured: bool = False
    capture_data: Optional[dict] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _items_path(user_id: str) -> Path:
    """Return the path to a user's work_items.json file."""
    return Path(WORK_ITEMS_ROOT) / user_id / "work_items.json"


def _load_items(user_id: str) -> list:
    """Load work items from JSON file.

    Returns empty list if file doesn't exist or has invalid JSON.
    """
    path = _items_path(user_id)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
        logger.warning("work_items.json for %s is not a list, returning empty", user_id)
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load work_items.json for %s: %s", user_id, e)
        return []


def _save_items(user_id: str, items: list) -> None:
    """Atomic write of items list to JSON file.

    Uses temp file + os.replace for atomic write. Creates parent dirs if needed.
    """
    path = _items_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = json.dumps(items, indent=2, default=str)

    # Write to temp file in same directory, then atomic rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix="work_items_"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(path))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CRUD functions
# ---------------------------------------------------------------------------


def create_work_item(
    user_id: str,
    type: str,
    title: str,
    skill_name: str,
    **kwargs,
) -> WorkItem:
    """Create and persist a new work item.

    Args:
        user_id: User identifier.
        type: Work item type (meeting, outreach, etc.).
        title: Human-readable title.
        skill_name: Skill to execute for this item.
        **kwargs: Additional WorkItem fields (description, due_date, skill_params, etc.).

    Returns:
        The newly created WorkItem.
    """
    item = WorkItem(
        user_id=user_id,
        type=type,
        title=title,
        skill_name=skill_name,
        **kwargs,
    )

    items = _load_items(user_id)
    items.append(item.model_dump())
    _save_items(user_id, items)

    return item


def list_work_items(
    user_id: str,
    status: Optional[str] = None,
    type: Optional[str] = None,
) -> list:
    """List work items with optional filters.

    Items with due_date sort first (by due_date ascending),
    then items without due_date (by created_at ascending).

    Args:
        user_id: User identifier.
        status: Optional status filter.
        type: Optional type filter.

    Returns:
        List of WorkItem objects matching filters.
    """
    raw_items = _load_items(user_id)
    result = []

    for data in raw_items:
        if status and data.get("status") != status:
            continue
        if type and data.get("type") != type:
            continue
        try:
            result.append(WorkItem(**data))
        except Exception as e:
            logger.warning("Skipping invalid work item: %s", e)

    # Sort: items with due_date first (ascending), then by created_at
    def sort_key(item: WorkItem):
        if item.due_date:
            return (0, item.due_date, item.created_at)
        return (1, "", item.created_at)

    result.sort(key=sort_key)
    return result


def get_work_item(user_id: str, item_id: str) -> Optional[WorkItem]:
    """Retrieve a single work item by ID.

    Args:
        user_id: User identifier.
        item_id: Work item ID.

    Returns:
        WorkItem if found, None otherwise.
    """
    raw_items = _load_items(user_id)
    for data in raw_items:
        if data.get("id") == item_id:
            try:
                return WorkItem(**data)
            except Exception:
                return None
    return None


def update_work_item(user_id: str, item_id: str, **updates) -> Optional[WorkItem]:
    """Update fields on a work item.

    Sets updated_at automatically.

    Args:
        user_id: User identifier.
        item_id: Work item ID.
        **updates: Fields to update.

    Returns:
        Updated WorkItem if found, None otherwise.
    """
    raw_items = _load_items(user_id)

    for i, data in enumerate(raw_items):
        if data.get("id") == item_id:
            data.update(updates)
            data["updated_at"] = datetime.now().isoformat()
            raw_items[i] = data
            _save_items(user_id, raw_items)
            try:
                return WorkItem(**data)
            except Exception:
                return None

    return None


def delete_work_item(user_id: str, item_id: str) -> bool:
    """Remove a work item by ID.

    Args:
        user_id: User identifier.
        item_id: Work item ID.

    Returns:
        True if found and deleted, False otherwise.
    """
    raw_items = _load_items(user_id)
    original_len = len(raw_items)
    raw_items = [d for d in raw_items if d.get("id") != item_id]

    if len(raw_items) < original_len:
        _save_items(user_id, raw_items)
        return True
    return False


# ---------------------------------------------------------------------------
# Status transition helper
# ---------------------------------------------------------------------------


def transition_status(
    user_id: str, item_id: str, new_status: str
) -> Optional[WorkItem]:
    """Transition a work item to a new status with validation.

    Valid transitions:
        upcoming -> preparing
        preparing -> ready
        ready -> needs_review
        needs_review -> done
        upcoming -> done (skip shortcut)
        any -> upcoming (reset)

    Args:
        user_id: User identifier.
        item_id: Work item ID.
        new_status: Target status.

    Returns:
        Updated WorkItem if transition valid and item found.

    Raises:
        ValueError: If the transition is not allowed.
    """
    item = get_work_item(user_id, item_id)
    if item is None:
        return None

    current = item.status

    # Reset to upcoming is always allowed
    if new_status == _RESET_TARGET and current != _RESET_TARGET:
        return update_work_item(user_id, item_id, status=new_status)

    # Check valid transitions
    if (current, new_status) not in _VALID_TRANSITIONS:
        raise ValueError(
            "Invalid status transition: %s -> %s" % (current, new_status)
        )

    return update_work_item(user_id, item_id, status=new_status)
