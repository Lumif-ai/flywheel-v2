"""Tests for flywheel.utils.normalize.normalize_company_name."""

import pytest
from flywheel.utils.normalize import normalize_company_name

test_cases = [
    # Basic normalization
    ("Acme Corp., Inc.", "acme"),
    ("acme corp", "acme"),
    ("The Acme Corporation", "acme"),
    ("ACME", "acme"),
    # Suffix stripping
    ("Stripe, Inc.", "stripe"),
    ("stripe inc", "stripe"),
    ("Stripe Inc.", "stripe"),
    ("OpenAI, LLC", "openai"),
    ("DeepMind Technologies", "deepmind"),
    ("Boston Consulting Group", "boston consulting"),
    # Whitespace handling
    ("  Acme   Corp  ", "acme"),
    # Dots removal
    ("A.I. Solutions Inc.", "ai"),
    ("S.A.P.", "sap"),
    # Edge cases
    ("", ""),
    ("   ", ""),
    ("The Company", "company"),
    ("Inc.", ""),  # only suffix, nothing left
    # Dedup equivalence
    ("Notion Labs", "notion"),
    ("notion", "notion"),
]


@pytest.mark.parametrize("input_name,expected", test_cases)
def test_normalize_company_name(input_name, expected):
    assert normalize_company_name(input_name) == expected


def test_dedup_equivalence():
    """Names that should resolve to the same normalized form."""
    group = [
        "Acme Corp., Inc.",
        "acme corp",
        "The Acme Corporation",
        "ACME",
        "Acme, Inc.",
        "  acme  ",
    ]
    normalized = {normalize_company_name(n) for n in group}
    assert len(normalized) == 1, f"Expected 1 unique value, got {normalized}"
