"""Validation and augmentation of Antigravity permission settings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PERMISSION_CATEGORIES = ("allow", "deny", "ask")


class PermissionConfigError(ValueError):
    """Raised when a permissions document has an invalid shape."""


def parse_permission_document(document: Any) -> dict[str, list[str]]:
    """Validate and normalize a permissions document."""
    if not isinstance(document, Mapping):
        raise PermissionConfigError("permissions document must be an object")
    permissions = document.get("permissions", document)
    if not isinstance(permissions, Mapping):
        raise PermissionConfigError("permissions must be an object")
    unknown = set(permissions) - set(PERMISSION_CATEGORIES)
    if unknown:
        raise PermissionConfigError(
            f"unknown permission categories: {', '.join(sorted(unknown))}"
        )

    result: dict[str, list[str]] = {}
    for category in PERMISSION_CATEGORIES:
        values = permissions.get(category, [])
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            raise PermissionConfigError(f"permissions.{category} must be a list of strings")
        result[category] = list(dict.fromkeys(values))
    return result


def augment_permissions(settings: Mapping[str, Any], additions: Mapping[str, list[str]]) -> dict[str, Any]:
    """Return settings with unique temporary rules appended to each category."""
    result = dict(settings)
    current = settings.get("permissions", {})
    if not isinstance(current, Mapping):
        raise PermissionConfigError("settings.permissions must be an object")
    merged = dict(current)
    for category in PERMISSION_CATEGORIES:
        existing = current.get(category, [])
        if not isinstance(existing, list) or not all(
            isinstance(value, str) for value in existing
        ):
            raise PermissionConfigError(f"settings.permissions.{category} must be a list of strings")
        merged[category] = list(dict.fromkeys([*existing, *additions[category]]))
    result["permissions"] = merged
    return result