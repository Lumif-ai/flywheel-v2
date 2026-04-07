"""Normalize fit_tier values to canonical set.

Maps legacy values (Tier 1, Tier 2, Low Fit, etc.) to canonical:
Strong Fit, Good Fit, Moderate Fit, Weak Fit, No Fit, Disqualified.

Revision ID: 039_normalize_fit_tier_values
Revises: 038_add_invite_token_column
Create Date: 2026-03-31
"""

from alembic import op

revision = "039_normalize_fit_tier_values"
down_revision = "038_add_invite_token_column"


def upgrade() -> None:
    # Normalize all known fit_tier variants to canonical set
    mappings = [
        ("Tier 1", "Strong Fit"),
        ("Tier 2", "Good Fit"),
        ("Tier 3", "Moderate Fit"),
        ("Tier 4", "Weak Fit"),
        ("Tier 5", "No Fit"),
        ("Low Fit", "Weak Fit"),
        ("No Fit", "No Fit"),  # already canonical but ensure casing
        ("Excellent", "Strong Fit"),
        ("Strong", "Strong Fit"),
        ("Good", "Good Fit"),
        ("Moderate", "Moderate Fit"),
        ("Fair", "Moderate Fit"),
        ("Weak", "Weak Fit"),
        ("Low", "Weak Fit"),
        ("Poor", "No Fit"),
    ]
    for old, new in mappings:
        op.execute(
            f"UPDATE accounts SET fit_tier = '{new}' "
            f"WHERE lower(trim(fit_tier)) = lower('{old}')"
        )


def downgrade() -> None:
    # No-op: we can't know original values
    pass
