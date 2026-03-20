"""
oauth_store.py - OAuth credential storage per user per service.

Stores OAuth tokens securely at ~/.flywheel/oauth/{user_id}/{service}_token.json
with chmod 600 file permissions. NOT in the context store (credentials are secrets).

Public API:
    save_credentials(user_id, service, creds_data) -> None
    load_credentials(user_id, service) -> Optional[dict]
    delete_credentials(user_id, service) -> None
    has_credentials(user_id, service) -> bool
    list_connected_services(user_id) -> list[str]
"""

import json
import logging
import os
import stat
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# OAuth credentials stored OUTSIDE context store (per research anti-pattern)
OAUTH_DIR = Path.home() / ".flywheel" / "oauth"


def _get_token_path(user_id: str, service: str) -> Path:
    """Get the path for a user's service token file."""
    return OAUTH_DIR / user_id / f"{service}_token.json"


def _ensure_user_dir(user_id: str) -> Path:
    """Create user's OAuth directory with restricted permissions."""
    user_dir = OAUTH_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to owner-only (0o700)
    try:
        os.chmod(str(user_dir), 0o700)
    except OSError as e:
        logger.warning("Could not set directory permissions for %s: %s", user_dir, e)
    return user_dir


def save_credentials(user_id: str, service: str, creds_data: dict) -> None:
    """Save OAuth credentials for a user and service.

    Creates parent directories with mode 0o700, writes token file
    with chmod 600.

    Args:
        user_id: User identifier.
        service: Service name (e.g., 'calendar', 'gmail').
        creds_data: Dict of credential data to store.
    """
    _ensure_user_dir(user_id)
    token_path = _get_token_path(user_id, service)

    # Write via temp file + rename to avoid window with wrong permissions
    import tempfile
    tmp_dir = token_path.parent
    try:
        fd = os.open(
            str(token_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)
    except OSError as e:
        logger.warning("Could not write credentials for %s: %s", token_path, e)
        return

    logger.info("Saved credentials for user %s, service %s", user_id, service)


def load_credentials(user_id: str, service: str) -> Optional[dict]:
    """Load OAuth credentials for a user and service.

    Args:
        user_id: User identifier.
        service: Service name.

    Returns:
        Dict of credential data, or None if no credentials exist.
    """
    token_path = _get_token_path(user_id, service)

    if not token_path.exists():
        return None

    try:
        return json.loads(token_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Failed to load credentials for %s/%s: %s", user_id, service, e)
        return None


def delete_credentials(user_id: str, service: str) -> None:
    """Delete OAuth credentials for a user and service.

    Args:
        user_id: User identifier.
        service: Service name.
    """
    token_path = _get_token_path(user_id, service)

    if token_path.exists():
        try:
            token_path.unlink()
            logger.info("Deleted credentials for user %s, service %s", user_id, service)
        except OSError as e:
            logger.error("Failed to delete credentials for %s/%s: %s", user_id, service, e)


def has_credentials(user_id: str, service: str) -> bool:
    """Check if a user has credentials for a service.

    Args:
        user_id: User identifier.
        service: Service name.

    Returns:
        True if credentials file exists.
    """
    return _get_token_path(user_id, service).exists()


def list_connected_services(user_id: str) -> list:
    """List services with saved credentials for a user.

    Args:
        user_id: User identifier.

    Returns:
        List of service name strings.
    """
    user_dir = OAUTH_DIR / user_id

    if not user_dir.exists():
        return []

    services = []
    try:
        for token_file in user_dir.iterdir():
            if token_file.is_file() and token_file.name.endswith("_token.json"):
                service = token_file.name.replace("_token.json", "")
                services.append(service)
    except (PermissionError, OSError) as e:
        logger.error("Failed to list services for %s: %s", user_id, e)

    return sorted(services)
