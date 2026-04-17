#!/usr/bin/env python3
"""Input validation for broker skills. Call before any API request."""
import uuid
from pathlib import Path
from typing import Any


def validate_required(data: dict, required_fields: list[str]) -> None:
    """Raise ValueError if any required field is missing or empty."""
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def validate_types(data: dict, type_map: dict[str, type]) -> None:
    """Raise ValueError if any field has wrong type. type_map = {field: expected_type}."""
    for field, expected in type_map.items():
        if field in data and not isinstance(data[field], expected):
            raise ValueError(
                f"Field '{field}' must be {expected.__name__}, "
                f"got {type(data[field]).__name__}"
            )


def validate_project_id(project_id: Any) -> str:
    """Validate and return project_id as string. Raises ValueError if invalid."""
    if not project_id:
        raise ValueError("project_id is required")
    return str(project_id)


def validate_uuid(value: Any, field_name: str = "value") -> str:
    """Validate value is a valid UUID and return as string. Raises ValueError if invalid."""
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name} must be a valid UUID, got: {value}")


def validate_file_path(path: Any, field_name: str = "path") -> str:
    """Validate file path exists and return as string. Raises ValueError if invalid."""
    if not path:
        raise ValueError(f"{field_name} is required")
    p = Path(str(path)).expanduser()
    if not p.exists():
        raise ValueError(f"{field_name} file not found: {p}")
    if not p.is_file():
        raise ValueError(f"{field_name} is not a file: {p}")
    return str(p)
