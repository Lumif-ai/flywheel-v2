# Phase 54: Data Model Foundation - Research

**Researched:** 2026-03-27
**Domain:** PostgreSQL schema evolution via Alembic + SQLAlchemy 2.0 ORM
**Confidence:** HIGH

## Summary

Phase 54 adds four schema changes to the `accounts` table: a `relationship_type text[]` array
column with a GIN index (DM-01), an `entity_level text` column (DM-02), a two-phase status
rename where Phase A adds `relationship_status` and `pipeline_stage` and copies data from
`status` (DM-03), and `ai_summary` + `ai_summary_updated_at` cache fields (DM-04).

All changes are purely additive — new columns on an existing table using `op.add_column`.
The codebase already uses Alembic with the naming convention `NNN_description.py`, uses
`ARRAY(Text)` with `postgresql_using="gin"` for GIN indexes, and uses SQLAlchemy 2.0
mapped-column style ORM. All patterns needed for this phase already exist in the repo;
this phase is applying established conventions to a new table.

The two-phase status rename (DM-03) is the highest-risk item: Phase A adds NEW columns
and copies data while keeping `status` alive. APIs continue reading `status` throughout
Phase A. Phase B (a later migration) drops `status`. The split ensures zero API outage
during the live deployment window.

**Primary recommendation:** Write two Alembic migration files following the existing
`NNN_description.py` naming convention: `028_relationship_type_entity_level_ai_summary.py`
for DM-01 + DM-02 + DM-04, and `029_status_rename_phase_a.py` for DM-03. Update the
`Account` ORM model in `models.py` to reflect the new columns after both migrations.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alembic | >=1.14 (in pyproject.toml) | Schema migrations | Already in use for all 27+ migrations |
| sqlalchemy | >=2.0 (in pyproject.toml) | ORM + column types | Mapped/mapped_column style throughout models.py |
| asyncpg | >=0.29 | Async PostgreSQL driver | Already configured in alembic/env.py |
| PostgreSQL ARRAY(Text) | — | text[] column type | Already imported: `from sqlalchemy.dialects.postgresql import ARRAY` in models.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy.dialects.postgresql | — | ARRAY, JSONB, TIMESTAMP types | When creating PostgreSQL-specific columns |
| sqlalchemy.text() | — | Raw SQL expressions for defaults/indexes | When Alembic cannot express the DDL natively |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| text[] ARRAY | JSONB array | JSONB is heavier; text[] + GIN is the correct choice for simple string membership queries |
| server_default with ARRAY cast | application-side default | Server defaults are safer for backfill — existing rows get the value automatically at migration time |

**Installation:**
No new packages needed. All required libraries are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── alembic/versions/
│   ├── 028_relationship_type_entity_level_ai_summary.py   # DM-01, DM-02, DM-04
│   └── 029_status_rename_phase_a.py                       # DM-03 (Phase A only)
└── src/flywheel/db/
    └── models.py    # Account class — add new Mapped columns after both migrations
```

### Pattern 1: Adding a NOT NULL Array Column with GIN Index

**What:** Add a `text[] NOT NULL DEFAULT '{prospect}'` column and its GIN index in a single
migration. The server_default backfills all existing rows atomically.
**When to use:** DM-01 (relationship_type)
**Example:**
```python
# Source: alembic/versions/010_context_graph_tables.py (lines 89-95)
# and alembic/versions/009_add_reasoning_trace.py (lines 35-41)
# Pattern: op.add_column + op.create_index with postgresql_using="gin"

def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "relationship_type",
            sa.ARRAY(sa.Text()),
            server_default=sa.text("'{prospect}'::text[]"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_account_relationship_type",
        "accounts",
        ["relationship_type"],
        postgresql_using="gin",
    )

def downgrade() -> None:
    op.drop_index("idx_account_relationship_type", table_name="accounts")
    op.drop_column("accounts", "relationship_type")
```

**Key detail:** The `server_default=sa.text("'{prospect}'::text[]")` syntax is the correct
PostgreSQL literal for an array default. This backfills all 206 existing rows to `{prospect}`
automatically — no separate UPDATE statement is needed.

### Pattern 2: Adding a Simple NOT NULL Text Column with Default

**What:** Add a text column that is NOT NULL with a server-side default.
**When to use:** DM-02 (entity_level), DM-04 (ai_summary_updated_at would be nullable,
ai_summary nullable)
**Example:**
```python
# Source: alembic/versions/023_tenant_company_link.py (line 27)
# Pattern: op.add_column with nullable column; for NOT NULL use server_default

def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "entity_level",
            sa.Text(),
            server_default=sa.text("'company'"),
            nullable=False,
        ),
    )

def downgrade() -> None:
    op.drop_column("accounts", "entity_level")
```

### Pattern 3: Two-Phase Column Rename — Phase A (Add + Copy)

**What:** Add new columns alongside old column, copy all data, leave old column alive.
Zero API downtime because old column continues to be read by existing API code.
**When to use:** DM-03 (relationship_status + pipeline_stage from status)
**Example:**
```python
# Phase A migration (028 or 029)
def upgrade() -> None:
    # Step 1: Add new columns (nullable initially, to allow the ADD COLUMN to succeed)
    op.add_column(
        "accounts",
        sa.Column("relationship_status", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("pipeline_stage", sa.Text(), nullable=True),
    )

    # Step 2: Copy data from old column to both new columns
    op.execute(sa.text("""
        UPDATE accounts
        SET relationship_status = status,
            pipeline_stage = status
    """))

    # Step 3: Set NOT NULL constraint now that all rows have values
    op.alter_column("accounts", "relationship_status", nullable=False)
    op.alter_column("accounts", "pipeline_stage", nullable=False)

    # Do NOT drop 'status' — that is Phase B (deferred)

def downgrade() -> None:
    op.drop_column("accounts", "pipeline_stage")
    op.drop_column("accounts", "relationship_status")
```

**CRITICAL:** Do NOT set `server_default` on the new columns permanently — they should
mirror the value from `status`, not have an independent default. The pattern is:
add nullable → UPDATE → set NOT NULL.

### Pattern 4: ORM Model Update After Migration

**What:** After both migrations are written, add the new columns to the `Account` class
in `models.py`. The model must match the DB schema or SQLAlchemy will raise errors on
queries that touch those fields.
**Example:**
```python
# Source: backend/src/flywheel/db/models.py — existing Account class (line 1091+)
# Add these after the existing status column:

relationship_type: Mapped[list[str]] = mapped_column(
    ARRAY(Text), server_default=text("'{prospect}'::text[]")
)
entity_level: Mapped[str] = mapped_column(
    Text, server_default=text("'company'")
)
# Phase A: add alongside existing status
relationship_status: Mapped[str | None] = mapped_column(Text, nullable=True)
pipeline_stage: Mapped[str | None] = mapped_column(Text, nullable=True)
ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
ai_summary_updated_at: Mapped[datetime.datetime | None] = mapped_column(
    TIMESTAMP(timezone=True), nullable=True
)
```

**Note on `__table_args__`:** The GIN index for `relationship_type` should be added to the
Account `__table_args__` tuple in models.py:
```python
Index("idx_account_relationship_type", "relationship_type", postgresql_using="gin"),
```

### Anti-Patterns to Avoid

- **Single migration for DM-03 that also drops `status`:** Never do Phase A and Phase B in the
  same migration. APIs in production read `status` — dropping it with Phase A causes an outage.
- **NOT NULL without server_default for backfill:** Adding a NOT NULL column without a
  `server_default` fails on a non-empty table in PostgreSQL. Always use `server_default` or
  the add-nullable → UPDATE → set-NOT-NULL dance.
- **Separate migration for GIN index (DM-01):** The requirement explicitly states the GIN index
  ships in the same migration as the column — never as a follow-up.
- **Using `nullable=False` + `server_default` on the new rename columns (DM-03):** Setting
  `server_default='prospect'` on `relationship_status` would silently give all future rows
  'prospect' rather than the correct value from `status`. Use the three-step pattern instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GIN index creation | Raw `op.execute("CREATE INDEX USING gin")` | `op.create_index(..., postgresql_using="gin")` | Alembic's `op.create_index` is idiomatic, handles dialect differences, and correctly tracks the index in migration history |
| Array column type | `sa.Text()` with manual `[]` suffix | `sa.ARRAY(sa.Text())` | SQLAlchemy handles the PostgreSQL ARRAY DDL correctly including asyncpg type coercion |
| Data backfill for Phase A | Python loop over all accounts | `op.execute(sa.text("UPDATE accounts SET ..."))` | Single SQL UPDATE is atomic, fast, and avoids N+1 round-trips; works even with 206 rows and will scale |
| Downgrade logic | Omitting `downgrade()` | Implement `downgrade()` with `op.drop_column` / `op.drop_index` | Existing project convention: every migration in this codebase has a downgrade function |

**Key insight:** Every pattern needed for this phase already exists in this repo. Use the
existing migration files as direct templates — don't invent new patterns.

## Common Pitfalls

### Pitfall 1: Array Default Syntax
**What goes wrong:** `server_default="'{prospect}'"` (Python string without explicit cast)
may work but is fragile; PostgreSQL may not infer the `text[]` type correctly.
**Why it happens:** PostgreSQL literal syntax for arrays is not the same as Python list syntax.
**How to avoid:** Always cast explicitly: `sa.text("'{prospect}'::text[]")`.
**Warning signs:** Migration applies but `EXPLAIN SELECT ... WHERE 'x' = ANY(relationship_type)`
shows a seq scan — index is not being used.

### Pitfall 2: NOT NULL on ADD COLUMN Without Default on Non-Empty Table
**What goes wrong:** `op.add_column` with `nullable=False` and no `server_default` raises
`ERROR: column contains null values` in PostgreSQL.
**Why it happens:** PostgreSQL cannot add a NOT NULL column to a table that already has rows
unless it knows the value to assign to existing rows.
**How to avoid:** Always provide `server_default` when adding a NOT NULL column, OR use the
add-nullable → UPDATE → ALTER COLUMN NOT NULL pattern (required for DM-03).
**Warning signs:** Migration fails with `NotNullViolation` error.

### Pitfall 3: down_revision Chain Breakage
**What goes wrong:** Setting `down_revision` to the wrong migration ID causes Alembic to
fail with "Can't locate revision" or creates a migration branch.
**Why it happens:** The latest migration is `027_crm_tables`. The next migration must set
`down_revision = "027_crm_tables"`. If writing two migrations, the second must point to the first.
**How to avoid:** Check the latest migration file before writing the new one. Set:
- Migration 028: `down_revision = "027_crm_tables"`
- Migration 029: `down_revision = "028_..."`
**Warning signs:** `alembic upgrade head` says "Multiple head revisions" or fails to find the chain.

### Pitfall 4: ORM Model Out of Sync
**What goes wrong:** Migration runs successfully but the `Account` ORM model in `models.py`
doesn't have the new columns — any SQLAlchemy query that selects `Account` objects will
silently omit the new fields.
**Why it happens:** Alembic migrations and the ORM model are separate artifacts.
**How to avoid:** Update `models.py` in the same plan step as the migration that adds the columns.
**Warning signs:** `account.relationship_type` raises `AttributeError`.

### Pitfall 5: Two-Phase Race Condition in Production
**What goes wrong:** Phase A migration is running (UPDATE accounts SET ...) while the API
is concurrently inserting new accounts with `status = 'prospect'` but without
`relationship_status` values — the new columns are nullable during the window.
**Why it happens:** The three-step pattern has a window between ADD COLUMN and SET NOT NULL.
**How to avoid:** This is acceptable by design — the columns are nullable during migration,
the UPDATE backfills existing rows, and SET NOT NULL completes within a single migration
transaction. New API inserts during Phase A that don't set the new columns will get NULL,
which is fine because Phase B is deferred. The critical path is that `status` still works.
**Warning signs:** Not really a warning sign — this is expected behavior for zero-downtime deploys.

### Pitfall 6: Forgetting the Index on `idx_account_tenant_status`
**What goes wrong:** After Phase A, queries that filter by `relationship_status` won't use
an index — causing full table scans.
**Why it happens:** Adding a column doesn't add an index automatically.
**How to avoid:** Add `idx_account_relationship_status` and `idx_account_pipeline_stage`
indexes in migration 029 alongside the new columns. Verify with EXPLAIN.
**Warning signs:** Slow queries on the accounts list endpoint after Phase A deploys.

## Code Examples

Verified patterns from official sources (within this codebase):

### ARRAY Column with GIN Index in Migration
```python
# Source: alembic/versions/010_context_graph_tables.py lines 89-95
op.create_index(
    "idx_entities_aliases",
    "context_entities",
    ["aliases"],
    postgresql_using="gin",
)
```

### ARRAY Column in ORM Model
```python
# Source: backend/src/flywheel/db/models.py line 561
aliases: Mapped[list[str] | None] = mapped_column(
    ARRAY(Text), server_default=text("'{}'::text[]")
)
```

### NOT NULL Array Column with Non-Empty Default
```python
# Pattern for relationship_type — analogous to existing usage
# Source: models.py line 547, alembic/versions/010 lines 40-80
sa.Column(
    "relationship_type",
    sa.ARRAY(sa.Text()),
    server_default=sa.text("'{prospect}'::text[]"),
    nullable=False,
)
```

### op.add_column for Nullable Column
```python
# Source: alembic/versions/023_tenant_company_link.py line 27
op.add_column("tenants", sa.Column("company_id", sa.Uuid(), nullable=True))
```

### Alembic Migration File Template (from existing files)
```python
# Source: alembic/versions/009_add_reasoning_trace.py — minimal clean structure
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "028_relationship_type_entity_level_ai_summary"
down_revision: Union[str, None] = "027_crm_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    ...

def downgrade() -> None:
    ...
```

### EXPLAIN Query to Verify GIN Index Scan
```sql
-- Run after migration to confirm index is used:
EXPLAIN SELECT id FROM accounts WHERE 'advisor' = ANY(relationship_type);
-- Expected: "Bitmap Index Scan on idx_account_relationship_type"
-- NOT: "Seq Scan on accounts"
```

### Verify Migration Backfill (206 accounts)
```sql
-- Run after migration 028 to confirm no accounts lost:
SELECT COUNT(*) FROM accounts;                          -- should be 206
SELECT COUNT(*) FROM accounts WHERE relationship_type = '{prospect}';  -- should be 206
SELECT COUNT(*) FROM accounts WHERE entity_level != 'company';         -- should be 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw `op.execute("CREATE INDEX USING gin")` | `op.create_index(..., postgresql_using="gin")` | Used both in this repo | Prefer `op.create_index` for tracked indexes; use raw SQL only when op.create_index can't express partial conditions |
| No explicit type cast on array default | `sa.text("'{prospect}'::text[]")` | Current practice | Explicit cast avoids PostgreSQL type inference ambiguity |

**Deprecated/outdated:**
- `op.execute("CREATE INDEX ... USING gin")` without `IF NOT EXISTS`: Migration 009 uses raw
  `op.execute` for a partial GIN index (JSONB with WHERE clause). For simple array GIN indexes,
  use `op.create_index` with `postgresql_using="gin"` — it is idiomatic and Alembic-tracked.

## Open Questions

1. **Migration numbering for 028 and 029**
   - What we know: Latest migration is `027_crm_tables`. Phase 54 needs two migrations.
   - What's unclear: Whether DM-01/02/04 should be one migration and DM-03 a second, or all four in one migration.
   - Recommendation: Split into two files — `028_relationship_type_entity_level_ai_summary.py`
     (additive columns with no data copy) and `029_status_rename_phase_a.py` (the DM-03 two-step
     with UPDATE). This keeps the riskier DM-03 isolated and independently revertible.

2. **Should relationship_status and pipeline_stage start as NOT NULL?**
   - What we know: Phase B (dropping `status`) is deferred. During the Phase A window, the API
     reads `status`, not the new columns. So the new columns do not need to be NOT NULL yet.
   - What's unclear: Whether the API for Phase 54 should already start reading `relationship_status`
     or continue using `status`.
   - Recommendation: Leave new columns nullable in Phase A (simpler migration). Phase B converts
     to NOT NULL after the API has been updated to read the new columns. This is consistent with
     the "zero API outage" constraint.

3. **How many accounts will exist in production at migration time?**
   - What we know: Success criteria mentions "206 existing accounts" — but this is dev/seed data.
   - What's unclear: Production row count. The migration must be safe for any row count.
   - Recommendation: The server_default approach for DM-01/02/04 is safe regardless of row count.
     The UPDATE in DM-03 is also fine for 206 rows or more; add a comment noting the UPDATE
     is expected to affect N rows.

## Sources

### Primary (HIGH confidence)
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/010_context_graph_tables.py` — GIN index on ARRAY column via `op.create_index(postgresql_using="gin")`
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/009_add_reasoning_trace.py` — Partial GIN index via raw `op.execute`
- `/Users/sharan/Projects/flywheel-v2/backend/alembic/versions/027_crm_tables.py` — Current latest migration (down_revision target)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/db/models.py` — Account ORM class (lines 1091-1139), ARRAY+GIN usage (lines 547-562, 251-253)
- `/Users/sharan/Projects/flywheel-v2/backend/src/flywheel/api/accounts.py` — Live API reading `status` column — confirms `status` must stay alive through Phase A
- `/Users/sharan/Projects/flywheel-v2/backend/pyproject.toml` — alembic>=1.14, sqlalchemy>=2.0

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 dialect docs: `postgresql_using="gin"` is the documented keyword argument for `Index` and `op.create_index` to specify the index access method
- PostgreSQL docs: `text[] NOT NULL DEFAULT '{prospect}'::text[]` is valid DDL for adding an array column with a non-empty default

### Tertiary (LOW confidence)
- None — all claims are directly verified in the codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — alembic, sqlalchemy, asyncpg versions confirmed in pyproject.toml
- Architecture (migration patterns): HIGH — 27 prior migrations; array/GIN patterns verified in 010_context_graph_tables.py and models.py
- Two-phase rename pattern: HIGH — pattern is mechanically straightforward; verified against API code that reads `status`
- Pitfalls: HIGH — all pitfalls are based on observable patterns in the codebase or verified PostgreSQL behavior

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable stack; Alembic/SQLAlchemy APIs don't change frequently)
