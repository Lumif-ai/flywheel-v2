"""Company name normalization utilities.

normalize_company_name produces a canonical form of a company name for
deduplication — two names that refer to the same company will produce the
same normalized string.
"""

from __future__ import annotations

import re


# Corporate suffixes to strip, comma-separated (e.g. ", inc.").
# Longer patterns listed first to avoid partial matches.
_COMMA_SUFFIXES = [
    ", pty. ltd.",
    ", pty ltd",
    ", corp.",
    ", corp",
    ", inc.",
    ", inc",
    ", llc",
    ", ltd.",
    ", ltd",
    ", co.",
    ", llp",
    ", plc",
    ", gmbh",
    ", s.a.",
]

# Corporate suffixes to strip when they appear at the end preceded by a space.
# Longer patterns listed first to avoid partial matches.
_SPACE_SUFFIXES = [
    " incorporated",
    " corporation",
    " international",
    " technologies",
    " technology",
    " enterprises",
    " consulting",
    " solutions",
    " holdings",
    " partners",
    " services",
    " limited",
    " company",
    " group",
    " labs",
    " pty. ltd.",
    " pty ltd",
    " inc.",
    " inc",
    " llc",
    " ltd.",
    " ltd",
    " co.",
    " co",
    " corp.",
    " corp",
    " llp",
    " plc",
    " gmbh",
    " s.a.",
]

# Bare suffix words — used only after period removal changed the string.
# When a name consists solely of one of these words (e.g. "Inc." → "inc"),
# the result is treated as empty.
_BARE_SUFFIXES = frozenset({
    "inc", "llc", "ltd", "corp", "co", "llp", "plc", "gmbh", "sa",
    "incorporated", "corporation", "limited", "company", "holdings",
    "group", "international", "technologies", "technology", "solutions",
    "enterprises", "consulting", "partners", "services", "labs",
})


def normalize_company_name(name: str) -> str:
    """Return a canonical normalized form of a company name.

    The output is suitable for deduplication: two names that refer to the
    same company will produce the same string.

    Algorithm:
    1. Strip leading/trailing whitespace.
    2. Lowercase.
    3. Remove "the " prefix.
    4. Remove common comma-separated corporate suffixes (one match).
    5. Remove common space-separated corporate suffixes (single pass).
    6. Remove all periods.
    7. If period removal changed the string: apply space-suffix stripping
       in a loop until stable, then check for bare-suffix-only result.
    8. Collapse multiple spaces; final strip.

    Returns an empty string for blank input.
    """
    if not name or not name.strip():
        return ""

    result = name.strip().lower()

    # Remove "the " prefix
    if result.startswith("the "):
        result = result[4:]

    # Remove comma-separated suffixes (e.g. ", inc.", ", llc") — one pass.
    for suffix in _COMMA_SUFFIXES:
        if result.endswith(suffix):
            result = result[: -len(suffix)]
            break

    # Remove space-separated suffixes at end — single pass.
    # A single pass avoids over-stripping meaningful words like "Consulting" in
    # "Boston Consulting Group" when no period-based abbreviations are present.
    for suffix in _SPACE_SUFFIXES:
        if result.endswith(suffix):
            result = result[: -len(suffix)]
            break

    # Remove all periods (handles "A.I.", "S.A.P.", trailing "Inc.", etc.)
    period_removed = result.replace(".", "")
    periods_changed = period_removed != result
    result = period_removed

    if periods_changed:
        # Period removal may expose additional suffix words (e.g. "ai solutions"
        # after "a.i. solutions inc." processing).  Apply space-suffix loop.
        changed = True
        while changed:
            changed = False
            for suffix in _SPACE_SUFFIXES:
                if result.endswith(suffix):
                    result = result[: -len(suffix)]
                    changed = True
                    break

        # If the entire remaining string is a bare suffix abbreviation
        # (e.g. "Inc." → "inc"), return empty string.
        if result in _BARE_SUFFIXES:
            result = ""

    # Collapse multiple spaces and final strip.
    result = re.sub(r" {2,}", " ", result)
    return result.strip()
