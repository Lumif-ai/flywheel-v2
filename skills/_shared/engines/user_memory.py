"""
Per-user memory management for headless execution.

Each Slack user gets a personal memory directory (~/.claude/users/{id}/memory/)
that stores skill preferences. Enables Mode 2 (guided) execution where previously
used parameters are auto-filled.

Also provides parameter resolution: given a skill's parameter declarations and a
user's saved preferences, determine which params are filled and which need asking.
"""

import re
from pathlib import Path

# Configurable roots for test isolation (patch these in tests)
USERS_ROOT = Path.home() / ".claude" / "users"
SHARED_CONTEXT_ROOT = Path.home() / ".claude" / "context"

# Pattern for parsing preference lines: - **key:** value
_PREF_PATTERN = re.compile(r"^- \*\*(.+?):\*\*\s*(.+)$")


def get_user_memory_dir(slack_user_id: str) -> Path:
    """Create and return the memory directory for a Slack user.

    Args:
        slack_user_id: Non-empty Slack user ID string.

    Returns:
        Path to ~/.claude/users/{slack_user_id}/memory/

    Raises:
        ValueError: If slack_user_id is empty or not a string.
    """
    if not isinstance(slack_user_id, str) or not slack_user_id.strip():
        raise ValueError("slack_user_id must be a non-empty string")

    memory_dir = USERS_ROOT / slack_user_id / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def load_user_preferences(slack_user_id: str, skill_name: str) -> dict:
    """Load saved preferences for a user+skill combination.

    Args:
        slack_user_id: Slack user ID.
        skill_name: Name of the skill whose preferences to load.

    Returns:
        Dict of {key: value} pairs. Empty dict if no preferences file exists.
    """
    memory_dir = get_user_memory_dir(slack_user_id)
    pref_file = memory_dir / f"{skill_name}.md"

    if not pref_file.exists():
        return {}

    prefs = {}
    content = pref_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        match = _PREF_PATTERN.match(line.strip())
        if match:
            prefs[match.group(1)] = match.group(2)

    return prefs


def save_user_preference(slack_user_id: str, skill_name: str, key: str, value: str):
    """Save or update a single preference for a user+skill combination.

    If the file exists and the key is already present, updates in-place.
    If the file exists but key is new, appends. If file doesn't exist,
    creates it with a header.

    Args:
        slack_user_id: Slack user ID.
        skill_name: Name of the skill.
        key: Preference key.
        value: Preference value.
    """
    memory_dir = get_user_memory_dir(slack_user_id)
    pref_file = memory_dir / f"{skill_name}.md"
    new_line = f"- **{key}:** {value}"

    if pref_file.exists():
        content = pref_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Check if key already exists and update in-place
        updated = False
        for i, line in enumerate(lines):
            match = _PREF_PATTERN.match(line.strip())
            if match and match.group(1) == key:
                lines[i] = new_line
                updated = True
                break

        if updated:
            content = "\n".join(lines) + "\n"
        else:
            # Append new preference
            if content and not content.endswith("\n"):
                content += "\n"
            content += new_line + "\n"

        pref_file.write_text(content, encoding="utf-8")
    else:
        # Create new file with header
        content = f"# {skill_name} preferences\n\n{new_line}\n"
        pref_file.write_text(content, encoding="utf-8")


def save_preferences_batch(slack_user_id: str, skill_name: str, prefs: dict):
    """Save multiple preferences at once.

    Convenience wrapper that calls save_user_preference for each key-value pair.
    Useful after a guided mode session completes.

    Args:
        slack_user_id: Slack user ID.
        skill_name: Name of the skill.
        prefs: Dict of {key: value} pairs to save.
    """
    for key, value in prefs.items():
        save_user_preference(slack_user_id, skill_name, key, str(value))


def resolve_parameters(
    parameters: list, provided_args: dict, slack_user_id: str, skill_name: str
) -> tuple:
    """Resolve parameters from provided args and user memory.

    For each parameter declaration:
    1. If param name in provided_args -> use provided value (Mode 1)
    2. If param has memory_key and user memory has value -> auto-fill (Mode 2)
    3. Otherwise -> add to missing list

    Args:
        parameters: List of parameter dicts, each with keys:
            - name (str): Parameter name
            - prompt (str, optional): Question to ask user
            - memory_key (str, optional): Key to look up in user preferences
            - required (bool, optional): Whether parameter is required (default True)
        provided_args: Dict of {param_name: value} from CLI/Slack command.
        slack_user_id: Slack user ID for memory lookup.
        skill_name: Skill name for memory lookup.

    Returns:
        Tuple of (resolved_params: dict, missing_params: list[dict])
        - resolved_params: {name: value} for all resolved parameters
        - missing_params: list of dicts with name, prompt, default for unresolved params
    """
    if not parameters:
        return {}, []

    user_prefs = load_user_preferences(slack_user_id, skill_name)
    resolved = {}
    missing = []

    for param in parameters:
        name = param.get("name", "")
        if not name:
            continue

        # Priority 1: Explicitly provided args
        if name in provided_args:
            resolved[name] = provided_args[name]
            continue

        # Priority 2: Memory auto-fill
        memory_key = param.get("memory_key", "")
        if memory_key and memory_key in user_prefs:
            resolved[name] = user_prefs[memory_key]
            continue

        # Unresolved -- add to missing
        missing_entry = {
            "name": name,
            "prompt": param.get("prompt", f"Please provide {name}"),
        }
        # Include default from memory if available (even if memory_key didn't match,
        # check if param name itself is in prefs)
        if name in user_prefs:
            missing_entry["default"] = user_prefs[name]
        elif memory_key and memory_key in user_prefs:
            missing_entry["default"] = user_prefs[memory_key]

        missing.append(missing_entry)

    return resolved, missing


def is_onboarding_complete(slack_user_id: str) -> bool:
    """Check if user has completed onboarding.

    Args:
        slack_user_id: Slack user ID.

    Returns:
        True if user has completed onboarding, False otherwise.
    """
    prefs = load_user_preferences(slack_user_id, "_onboarding")
    return prefs.get("complete", "").lower() == "true"


def ensure_user_initialized(slack_user_id: str) -> bool:
    """Initialize user directory, returning whether this is a new user.

    Args:
        slack_user_id: Slack user ID.

    Returns:
        True if this was a NEW user (directory just created),
        False if directory already existed.
    """
    user_dir = USERS_ROOT / slack_user_id
    is_new = not user_dir.exists()
    get_user_memory_dir(slack_user_id)  # Creates the directory structure
    return is_new
