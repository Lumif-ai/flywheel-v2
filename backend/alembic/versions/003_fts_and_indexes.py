"""FTS indexes and moddatetime trigger on context_entries

Revision ID: 003_fts
Revises: 002_rls
Create Date: 2026-03-20

Hand-written migration -- triggers are not supported by Alembic autogenerate.

The tsvector generated column and GIN index were already created in 001_create_schema.py.
This migration adds the updated_at trigger (moddatetime or PL/pgSQL fallback)
and verifies the FTS column exists.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_fts"
down_revision: Union[str, Sequence[str], None] = "002_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at trigger and verify FTS column exists."""

    # 1. Try moddatetime extension first; fall back to PL/pgSQL trigger
    # moddatetime is not available in vanilla Postgres 16 Alpine,
    # so we use the PL/pgSQL fallback directly for portability.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON context_entries
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # 2. Verify search_vector column exists (created in 001)
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'context_entries'
                  AND column_name = 'search_vector'
            ) THEN
                -- Fallback: add if autogenerate missed it
                EXECUTE 'ALTER TABLE context_entries ADD COLUMN
                    search_vector tsvector GENERATED ALWAYS AS (
                        to_tsvector(''english'', coalesce(detail, '''') || '' '' || content)
                    ) STORED';
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_context_search
                    ON context_entries USING GIN(search_vector)';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Remove trigger and function."""
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON context_entries")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
