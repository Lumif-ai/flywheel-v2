"""One-off script to create saved_views table on Supabase.

Supabase PgBouncer silently rolls back multi-statement DDL in a single
transaction, so we run each DDL statement as its own commit.

Usage:
    cd backend && .venv/bin/python scripts/049_apply_saved_views.py

After success, stamp alembic:
    cd backend && .venv/bin/alembic stamp 049_saved_views
"""

import asyncio
import sys
import os

# Add src to path so we can import flywheel modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import text
from flywheel.db.session import get_session_factory


DDL_STATEMENTS = [
    # 1. Create table
    """
    CREATE TABLE IF NOT EXISTS saved_views (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID NOT NULL REFERENCES tenants(id),
        owner_id UUID,
        name TEXT NOT NULL,
        filters JSONB NOT NULL DEFAULT '{}'::jsonb,
        sort JSONB,
        columns JSONB,
        is_default BOOLEAN NOT NULL DEFAULT false,
        position INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # 2. Create index
    """
    CREATE INDEX IF NOT EXISTS idx_saved_views_tenant_owner
    ON saved_views (tenant_id, owner_id)
    """,
    # 3. Enable RLS
    "ALTER TABLE saved_views ENABLE ROW LEVEL SECURITY",
    # 4. Force RLS
    "ALTER TABLE saved_views FORCE ROW LEVEL SECURITY",
    # 5. Tenant isolation policy
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'saved_views'
            AND policyname = 'saved_views_tenant_isolation'
        ) THEN
            EXECUTE 'CREATE POLICY saved_views_tenant_isolation ON saved_views
                USING (tenant_id = current_setting(''app.tenant_id'')::uuid)';
        END IF;
    END
    $$
    """,
    # 6. Grant permissions
    "GRANT SELECT, INSERT, UPDATE, DELETE ON saved_views TO authenticated",
]


async def main():
    factory = get_session_factory()

    for i, stmt in enumerate(DDL_STATEMENTS, 1):
        async with factory() as session:
            print(f"[{i}/{len(DDL_STATEMENTS)}] Executing DDL...")
            await session.execute(text(stmt))
            await session.commit()
            print(f"  -> committed.")

    print("\nAll DDL statements applied successfully.")
    print("Now run: cd backend && .venv/bin/alembic stamp 049_saved_views")


if __name__ == "__main__":
    asyncio.run(main())
