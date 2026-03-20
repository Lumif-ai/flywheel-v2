"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def verify_rls(tables: list[str]) -> None:
    """Verify RLS is enabled on all specified tables. Call at end of upgrade()."""
    for table in tables:
        op.execute(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='{table}' AND relrowsecurity) "
            f"THEN RAISE EXCEPTION 'RLS not enabled on table: {table}'; "
            f"END IF; END $$;"
        )


def upgrade() -> None:
    """Upgrade schema."""
    # REMINDER: Enable RLS on new tenant-scoped tables:
    # op.execute("ALTER TABLE tablename ENABLE ROW LEVEL SECURITY")
    # verify_rls(["tablename"])
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
