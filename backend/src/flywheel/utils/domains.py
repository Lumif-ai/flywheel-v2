"""Shared generic-domain constants for tenant naming and entity extraction."""

from __future__ import annotations

GENERIC_DOMAINS: frozenset[str] = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "protonmail.com",
    "aol.com",
    "mail.com",
    "live.com",
    "msn.com",
    "ymail.com",
    "googlemail.com",
})


def is_generic_domain(domain: str) -> bool:
    """Return True if *domain* is a free/personal email provider."""
    return domain.lower() in GENERIC_DOMAINS
