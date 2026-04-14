# Technology Stack

**Project:** Broker Data Model Restructuring (Clients, Contacts, Context Store, Solicitation Workflow)
**Researched:** 2026-04-14

## Recommended Stack

### No New Dependencies Required

This milestone requires **zero new libraries**. Every capability needed is already available in the existing stack. The work is purely structural: new models, new service functions, expanded normalization logic, and PostgreSQL constraints.

| Capability Needed | Already Available Via | Version | Notes |
|---|---|---|---|
| Partial unique indexes | SQLAlchemy `Index(..., unique=True, postgresql_where=text(...))` | SQLAlchemy >=2.0 | Already used 20+ times in models.py |
| CHECK constraints | SQLAlchemy `CheckConstraint` | SQLAlchemy >=2.0 | **Import needed** -- not currently imported in models.py |
| Normalized name dedup | `entity_normalization.py` | Custom | Exists, needs suffix list expansion |
| Context entity creation | `entity_normalization.find_or_create_entity()` | Custom | Exists, pattern proven |
| Enum validation | PostgreSQL CHECK + Pydantic `Literal` | Built-in | No enum library needed |
| Contact tables | SQLAlchemy ORM mapped classes | SQLAlchemy >=2.0 | Same pattern as all existing models |
| Solicitation drafts | New ORM model + relationship | SQLAlchemy >=2.0 | Standard FK pattern |
| DDL migrations | Alembic >=1.14 | Alembic >=1.14 | One-statement-per-commit workaround for Supabase |

### Core Framework (Unchanged)

| Technology | Version | Purpose | Status |
|---|---|---|---|
| SQLAlchemy | >=2.0 (async) | ORM, model definitions | Already installed |
| Alembic | >=1.14 | Database migrations | Already installed |
| FastAPI | Current | API endpoints | Already installed |
| Pydantic v2 | Current | Request/response schemas | Already installed |
| PostgreSQL | 15+ (Supabase) | Database | Already running |

## What Changes in Existing Code

### 1. models.py Import Addition

```python
# Current import (line 18):
from sqlalchemy import (
    BigInteger, Boolean, Computed, Date, ForeignKey,
    Index, Integer, LargeBinary, Numeric, Text,
    UniqueConstraint, text,
)

# Add CheckConstraint:
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, ForeignKey,
    Index, Integer, LargeBinary, Numeric, Text,
    UniqueConstraint, text,
)
```

**Confidence: HIGH** -- `CheckConstraint` is a core SQLAlchemy class, available in all 2.x versions. Not currently used anywhere in the codebase, but this is standard SQLAlchemy, not a new dependency.

### 2. Entity Normalization Suffix Expansion

The existing `entity_normalization.py` regex (line 24) handles US suffixes only:

```python
# Current:
_COMPANY_SUFFIXES = re.compile(
    r"\s*\b(corporation|company|corp|inc|llc|ltd|co)\.?\s*$",
    re.IGNORECASE,
)
```

The spec requires MX/LATAM legal suffixes: `S.A. de C.V.`, `S.A.S.`, `S. de R.L.`, `GmbH`, `S.A.`. These have dots and spaces that the current word-boundary regex cannot match. The function needs a two-pass approach: first strip multi-word suffixes by exact match (longest first), then apply the existing single-word regex.

Recommended suffix list (longest first to avoid partial matches):

```python
_LEGAL_SUFFIXES = [
    "s.a.p.i. de c.v.",
    "s. de r.l. de c.v.",
    "s.a. de c.v.",
    "s. de r.l.",
    "s.a.s.",
    "s.a.",
    "corporation",
    "company",
    "corp.",
    "corp",
    "inc.",
    "inc",
    "llc",
    "ltd.",
    "ltd",
    "gmbh",
    "co.",
    "co",
]
```

**Confidence: HIGH** -- This is pure string manipulation. No library needed. The existing `normalize_entity_name()` function signature stays the same; only the internal logic changes.

### 3. CheckConstraint Pattern for Enum Fields

The codebase currently uses zero CHECK constraints. The spec requires 15 of them across tables. SQLAlchemy pattern:

```python
__table_args__ = (
    CheckConstraint(
        "status IN ('draft', 'pending', 'approved', 'sent', 'expired')",
        name="ck_solicitation_draft_status",
    ),
    # ... other constraints
)
```

**Confidence: HIGH** -- Standard SQLAlchemy. Verified via codebase pattern: `__table_args__` tuples already contain `Index` and `UniqueConstraint` throughout.

### 4. Partial Unique Index Pattern

Already proven in the codebase (20+ instances). The spec needs two new ones:

```python
# One active solicitation per project+carrier
Index(
    "uq_solicitation_draft_active",
    "broker_project_id", "carrier_config_id",
    unique=True,
    postgresql_where=text("status IN ('draft', 'pending', 'approved')"),
),

# One approved recommendation per project
Index(
    "uq_recommendation_approved",
    "broker_project_id",
    unique=True,
    postgresql_where=text("status = 'approved'"),
),
```

**Confidence: HIGH** -- Identical pattern to `idx_quote_source_dedup` (models.py line 2200) and library document dedup indexes (lines 911-921).

### 5. Context Store Integration Pattern

The existing `find_or_create_entity()` in `entity_normalization.py` handles the core pattern. For broker entities (clients, carriers, projects), a thin wrapper is needed in `context_store_writer.py`:

```python
async def create_context_entity(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    entity_type: str,  # "company" for clients, "carrier" for carriers, "project" for projects
) -> UUID:
    """Eager-create a context entity. Returns entity ID. Raises on failure."""
    entity = await find_or_create_entity(session, tenant_id, name, entity_type)
    return entity.id
```

**Confidence: HIGH** -- `find_or_create_entity()` already uses `SELECT ... FOR UPDATE` for race condition safety and is idempotent.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Enum validation | CHECK constraints + Pydantic Literal | Python `enum.Enum` mapped to DB | CHECK constraints enforce at DB level regardless of application path. Python enums add ORM complexity with no benefit for simple string enums |
| Name normalization | Expanded regex in existing module | `python-nameparser` or `company-name-normalizer` | External dep for a 20-line function. MX/LATAM suffixes are not well-supported in English-centric libraries. Custom list is more controllable |
| Contact dedup | Application-layer normalized name + UNIQUE constraint | `dedupe` library / fuzzy matching | Overkill. The spec calls for exact normalized_name dedup, not probabilistic matching. UniqueConstraint on (tenant_id, normalized_name) is sufficient |
| Solicitation state machine | String field + ALLOWED_TRANSITIONS dict | `transitions` or `python-statemachine` library | The codebase already has an ALLOWED_TRANSITIONS pattern for broker projects/quotes. Adding a state machine library for one more entity is overhead |
| Context entity FK | Nullable UUID column (no FK constraint) | Actual FK to context_entities table | Consistent with existing pattern -- `*_user_id` columns throughout codebase use UUID without FK constraint because Alembic cannot reference all tables through the pooler connection. Application-layer enforcement |

## What NOT to Add

| Package | Why Not |
|---|---|
| Any ORM migration tool beyond Alembic | Alembic works fine, the Supabase workaround is execution-level, not tooling-level |
| Any name normalization library | 20 lines of custom code handles MX/US suffixes better than generic libraries |
| Any state machine library | ALLOWED_TRANSITIONS dict pattern is already established |
| Any fuzzy matching library | Exact normalized_name dedup is the spec requirement |
| PostgreSQL enum types (CREATE TYPE) | String columns with CHECK constraints are simpler to migrate and modify |

## Installation

```bash
# Nothing to install. All dependencies are already in pyproject.toml.
# Zero new Python packages.
# Zero new npm packages.
```

## Migration Execution Notes (Supabase-Specific)

Per established project convention (CLAUDE.md, MEMORY.md), Supabase PgBouncer silently rolls back multi-statement DDL. Each DDL statement must be a separate commit:

```python
# Each CREATE TABLE, CREATE INDEX, ALTER TABLE, ADD CONSTRAINT is its own commit:
async with factory() as session:
    await session.execute(text("CREATE TABLE broker_clients (...)"))
    await session.commit()

async with factory() as session:
    await session.execute(text("CREATE INDEX idx_broker_client_tenant ON broker_clients (tenant_id)"))
    await session.commit()

# After all statements: alembic stamp <revision>
```

This affects how the 6 new tables + RLS policies + indexes + CHECK constraints are deployed. Expect 40-50 individual DDL statements across the two migration phases.

## Key Implementation Details

### CheckConstraint Naming Convention

Follow the existing naming pattern (`uq_` for unique, `idx_` for index). Use `ck_` prefix:

- `ck_broker_client_country` -- validates country code values
- `ck_solicitation_draft_status` -- validates solicitation status enum
- `ck_broker_recommendation_status` -- validates recommendation status enum
- `ck_carrier_quote_status` -- validates quote status enum (adding to existing table)
- `ck_broker_activity_type` -- validates activity type enum

### Context Entity Failure Handling

The spec says: "If context store fails, fail client creation (surface error)." The existing `find_or_create_entity` calls `session.flush()` (not `session.commit()`), so it participates in the caller's transaction. If it raises, the entire transaction rolls back including the client INSERT. This is the correct pattern -- no change needed to transaction handling.

### Relationship Back-Population

New relationships follow the existing pattern:
- `cascade="all, delete-orphan"` for owned children (contacts, solicitation drafts, recommendations)
- `back_populates=` on both sides
- No `lazy=` specified (SQLAlchemy 2.0 defaults to `lazy="select"`, consistent with rest of codebase)

### FK Constraints on context_entity_id

Per MEMORY.md: "Alembic cannot reference profiles table in FK constraints." The same limitation applies broadly -- use plain UUID columns for `context_entity_id` on broker_clients, carrier_configs, and broker_projects. Application-layer enforcement via the `create_context_entity` wrapper guarantees the entity exists.

## Sources

- Codebase: `backend/src/flywheel/db/models.py` lines 18-33 (imports), 550-565 (ContextEntity model), 1951-2380 (broker models) -- HIGH confidence
- Codebase: `backend/src/flywheel/services/entity_normalization.py` (existing normalization logic, find_or_create_entity) -- HIGH confidence
- Codebase: `backend/pyproject.toml` (dependency versions: `sqlalchemy[asyncio]>=2.0`, `alembic>=1.14`) -- HIGH confidence
- Codebase: `SPEC-BROKER-DATA-MODEL.md` (full spec for this milestone, suffix list, CHECK constraints, partial unique indexes) -- HIGH confidence
- Project memory: Supabase DDL workaround, FK constraint limitations (MEMORY.md, CLAUDE.md) -- HIGH confidence
