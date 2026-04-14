# Architecture Patterns

**Domain:** Broker Data Model v2 -- Clients, Contacts & Structural Fixes
**Researched:** 2026-04-14
**Confidence:** HIGH (all recommendations derived from reading actual codebase + spec)

---

## Recommended Architecture

### System Overview

The milestone restructures the broker module's data layer (6 new tables, 6 modified tables) and splits responsibilities that were previously inlined on existing models (draft fields on CarrierQuote, recommendation columns on BrokerProject) into proper first-class tables. The backend introduces two new service classes and modifies three existing engines. The frontend adds two new pages and modifies four components.

```
                    +------------------+
                    | Frontend (React) |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  FastAPI Router   |
                    |  broker.py       |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
   +----------v--+  +--------v-------+  +--v-----------+
   | broker_client|  |broker_contact  |  | Existing     |
   | _service.py  |  |_service.py     |  | broker.py    |
   +----------+--+  +--------+-------+  | (inline svc) |
              |              |           +--+-----------+
              |              |              |
   +----------v--------------v--------------v----------+
   |                 context_store_writer.py            |
   |         (+ new create_context_entity())           |
   +----------+----------------------------------------+
              |
   +----------v-----------+
   |    SQLAlchemy Models  |
   |    models.py          |
   |  (6 new + 5 modified) |
   +----------+------------+
              |
   +----------v-----------+
   |  PostgreSQL/Supabase  |
   |  (PgBouncer + RLS)    |
   +-----------------------+
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `broker.py` (router) | HTTP request handling, Pydantic validation, response serialization | Services, Models, Engines |
| `broker_client_service.py` (NEW) | Client CRUD, name normalization, dedup, context entity linking | context_store_writer, Models |
| `broker_contact_service.py` (NEW) | Contact CRUD for both client contacts and carrier contacts, soft limits | Models |
| `context_store_writer.py` (MODIFIED) | Context entity creation (new) + existing entry writing | ContextEntity model |
| `solicitation_drafter.py` (engine) | AI email generation (pure function, no DB writes) | Anthropic API only |
| `recommendation_drafter.py` (engine) | AI recommendation generation (pure function, no DB writes) | Anthropic API only |
| `models.py` | ORM definitions for all 12 affected tables | PostgreSQL |
| `broker_data_model_migration.py` (NEW script) | DDL execution with PgBouncer workaround | PostgreSQL directly |

---

## Data Flow

### 1. Client Creation Flow (New)

```
POST /broker/clients
  -> broker.py validates input (BrokerClientCreate schema)
  -> broker_client_service.normalize_name(name)
  -> broker_client_service.create_client():
       1. Check uniqueness (tenant_id, normalized_name)
       2. create_context_entity(db, tenant_id, name, 'broker_client')  -- NEW
       3. If entity creation fails -> raise, no client created
       4. Insert BrokerClient(context_entity_id=entity.id)
       5. Return client (caller commits)
  -> broker.py commits and returns response
```

**Critical design decision:** Context entity creation is synchronous and within the same transaction. If `create_context_entity()` fails, the entire client creation rolls back. This is the correct choice for data integrity -- an orphaned client without a context entity would break intelligence linking.

### 2. Solicitation Workflow (Restructured)

**BEFORE (current -- broker.py:1571-1744):**
```
draft-solicitations -> creates CarrierQuote(status='pending', draft_subject=..., draft_body=...)
                       Also creates submission_documents linked to the quote
approve-send        -> reads CarrierQuote.draft_*, sends email, sets status='solicited'
                       Calls _check_all_solicited() which queries CarrierQuote rows
mark-received       -> updates existing CarrierQuote with quote data
```

**AFTER (new):**
```
draft-solicitations -> creates SolicitationDraft(status='draft', subject=..., body=...)
                       NO CarrierQuote created yet
                       Looks up carrier_contacts(role='submissions') for sent_to_email
                       submission_documents still linked to SolicitationDraft
approve-send        -> reads SolicitationDraft, sends email, sets status='sent'
                       Still NO CarrierQuote
mark-received       -> creates NEW CarrierQuote + links to SolicitationDraft via carrier_quote_id
```

**What this changes (5 specific code impacts):**

1. **`_check_all_solicited()` (broker.py:1525-1563):** Currently counts CarrierQuote rows where `status='solicited'`. Must change to count SolicitationDraft rows where `status='sent'`. The logic stays the same (if all sent, transition project to `soliciting`).

2. **Portal submission flow (broker.py:1697-1720):** Currently creates a CarrierQuote for portal track too. Must create a SolicitationDraft with `submission_method='portal'` instead. The `build_submission_package()` call links documents to the draft.

3. **`approve-send` route (broker.py:1798-1869):** Route changes from `/broker/quotes/{id}/approve-send` to `/broker/solicitations/{id}/approve-send`. Reads from SolicitationDraft instead of CarrierQuote. No longer sets CarrierQuote.status because no CarrierQuote exists yet.

4. **`_carrier_to_dict()` (broker.py:248-268):** Remove `email_address` field. Frontend carrier objects no longer have inline email.

5. **Carrier email lookup:** Replace `carrier_config.email_address` with a query to `carrier_contacts` table:
```python
contact_result = await db.execute(
    select(CarrierContact).where(
        CarrierContact.carrier_config_id == carrier_id,
        CarrierContact.role == 'submissions',
    ).order_by(CarrierContact.is_primary.desc()).limit(1)
)
contact = contact_result.scalar_one_or_none()
if not contact or not contact.email:
    skipped.append({"carrier_name": ..., "reason": "No submissions contact with email"})
    continue
```

### 3. Recommendation Flow (Restructured)

**BEFORE (broker.py:2652-2900):**
```
draft-recommendation      -> sets BrokerProject.recommendation_subject/body/status
approve-send-recommendation -> reads project.recommendation_*, sends, saves Document
```

**AFTER:**
```
draft-recommendation      -> creates BrokerRecommendation(status='draft')
approve-send-recommendation -> reads BrokerRecommendation, sends, saves Document, sets status='sent'
```

Multiple recommendations are allowed (audit trail). Partial unique index on `status='approved'` ensures only one is approved at a time.

**Important preservation:** The `approve-send-recommendation` endpoint (broker.py:2864-2877) creates a `Document` record in the library with metadata. This behavior MUST be preserved in the new implementation.

### 4. Context Store Entity Creation (New Function)

The existing `context_store_writer.py` provides `write_contact()`, `write_insight()`, etc. -- all write `ContextEntry` rows (the detail/evidence layer). None create `ContextEntity` rows (the entity/identity layer). These are different tables:

- `context_entities`: Unique entities (companies, people, projects) identified by `(tenant_id, name, entity_type)`
- `context_entries`: Individual evidence items (emails, meetings) linked to entities via `context_entity_entries` junction table

The new `create_context_entity()` function operates on the entity layer:

```python
async def create_context_entity(
    db: AsyncSession, tenant_id: UUID, name: str, entity_type: str,
    aliases: list[str] | None = None,
) -> ContextEntity:
    """Upsert a ContextEntity row. Returns existing if name+type match."""
    stmt = pg_insert(ContextEntity).values(
        tenant_id=tenant_id,
        name=name,
        entity_type=entity_type,
        aliases=aliases or [],
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_entity_tenant_name_type",
        set_={
            "mention_count": ContextEntity.mention_count + 1,
            "last_seen_at": text("now()"),
        },
    )
    stmt = stmt.returning(ContextEntity)
    result = await db.execute(stmt)
    return result.scalar_one()
```

This follows the same upsert pattern as the existing `_write_entry()` function (dedup by natural key, increment on match).

---

## Patterns to Follow

### Pattern 1: Service Layer for New Entity Domains

**What:** New entity domains (clients, contacts) get dedicated service classes instead of inline logic in the router.
**Why:** broker.py is already 2900 lines with 29 endpoints. Adding client CRUD inline would push it past 3500 lines. Service classes are testable without HTTP context.
**Where:** `backend/src/flywheel/services/broker_client_service.py` and `broker_contact_service.py`

```python
class BrokerClientService:
    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create_client(self, data: BrokerClientCreate, user_id: UUID) -> BrokerClient:
        normalized = self.normalize_name(data.name)
        existing = await self.db.execute(
            select(BrokerClient).where(
                BrokerClient.tenant_id == self.tenant_id,
                BrokerClient.normalized_name == normalized,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, f"Client '{data.name}' already exists")

        entity = await create_context_entity(
            self.db, self.tenant_id, data.name, 'broker_client'
        )
        client = BrokerClient(
            tenant_id=self.tenant_id,
            name=data.name,
            normalized_name=normalized,
            context_entity_id=entity.id,
            created_by_user_id=user_id,
            # ... other fields from data
        )
        self.db.add(client)
        await self.db.flush()
        return client
```

### Pattern 2: Partial Unique Indexes in SQLAlchemy

**What:** Two tables need partial unique indexes (one active solicitation per project+carrier, one approved recommendation per project).
**How:** Use `Index()` with `postgresql_where` in `__table_args__`.

```python
class SolicitationDraft(Base):
    __tablename__ = "solicitation_drafts"
    __table_args__ = (
        Index(
            "uq_solicitation_draft_active",
            "broker_project_id", "carrier_config_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'pending', 'approved')"),
        ),
        Index("idx_solicitation_draft_project", "broker_project_id"),
        Index("idx_solicitation_draft_carrier", "carrier_config_id"),
    )
```

**Important:** The partial unique index is declared in the model for documentation, but the actual DDL is executed via the migration script (PgBouncer workaround). SQLAlchemy will not auto-create these indexes.

### Pattern 3: Mapped Column Style Consistency

**What:** Use the existing `Mapped[]` / `mapped_column()` syntax (SQLAlchemy 2.0 style) for new models.
**Why:** All existing broker models (CarrierConfig, BrokerProject, CarrierQuote at models.py:1951-2342) use this pattern. The spec shows old-style `Column()` syntax -- convert to match codebase.

```python
# WRONG (spec shows this):
id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
name = Column(Text, nullable=False)

# RIGHT (match codebase pattern at models.py:1962-2007):
id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
name: Mapped[str] = mapped_column(Text, nullable=False)
```

### Pattern 4: Router Organization -- Keep Single File

**What:** Despite 17 new endpoints, keep broker.py as a single router file.
**Why:**
1. The codebase uses single-file routers everywhere (accounts.py, pipeline.py, context.py)
2. All endpoints share `require_module("broker")`, `ALLOWED_TRANSITIONS`, helper functions
3. With service classes extracting business logic, router methods are thin wrappers
4. Net growth is modest (~200 lines) because solicitation/recommendation endpoints are restructured, not added

**Organization within the file:**
```
# broker.py structure (post-change):
# 1. Imports + Pydantic schemas + transitions + helpers (~300 lines)
# 2. Projects endpoints (~800 lines)
# 3. Clients endpoints (NEW, ~300 lines -- thin service wrappers)
# 4. Carriers + carrier contacts endpoints (~400 lines)
# 5. Solicitations endpoints (RESTRUCTURED, ~300 lines)
# 6. Quotes endpoints (~500 lines)
# 7. Comparison + export endpoints (~300 lines)
# 8. Recommendations endpoints (RESTRUCTURED, ~200 lines)
# Total: ~3100 lines
```

### Pattern 5: Name Normalization (Application Layer)

**What:** `normalized_name` is computed in Python, not a database generated column.
**Why:** The normalization rules are business logic (strip legal suffixes like `S.A. de C.V.`, `S.A.S.`, `GmbH`) that will evolve. Application-layer is easier to test and change.

```python
_LEGAL_SUFFIXES = [
    "s.a. de c.v.", "s.a.s.", "s. de r.l.", "inc.", "llc",
    "ltd.", "corp.", "gmbh", "s.a.", "co.",
]

def normalize_name(name: str) -> str:
    result = name.lower().strip()
    for suffix in _LEGAL_SUFFIXES:
        if result.endswith(suffix):
            result = result[:-len(suffix)].strip()
    result = result.rstrip(".,")
    return " ".join(result.split())  # collapse multiple spaces
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Creating CarrierQuote at Solicitation Time

**What:** The current pattern (broker.py:1651-1662) creates a `CarrierQuote` row when drafting a solicitation, before any quote exists.
**Why bad:** Conflates "we asked for a quote" with "a quote exists." CarrierQuote rows represent actual received quotes with premium/deductible/terms data. Creating them early pollutes the quotes table with placeholder rows that have null premium, null limit, etc.
**Instead:** Create SolicitationDraft rows at solicitation time. Create CarrierQuote rows only when a quote is received.

### Anti-Pattern 2: Storing Draft Content on Parent Entity

**What:** Recommendation draft fields (5 columns) on BrokerProject; solicitation draft fields (3 columns) on CarrierQuote.
**Why bad:** No revision history, only one draft at a time, PII cleanup conflicts with audit requirements (broker.py:1845 clears draft_body after send, but regulated domain needs audit trail).
**Instead:** Dedicated tables (broker_recommendations, solicitation_drafts) with their own lifecycle.

### Anti-Pattern 3: Lazy Context Entity Creation (Background Task)

**What:** Creating context entities asynchronously after client/carrier creation.
**Why bad:** If the background task fails, the client exists without a context entity. The `context_entity_id` column would be NULL, breaking intelligence queries. No retry mechanism exists in the current codebase.
**Instead:** Synchronous creation within the same transaction. If it fails, the client creation fails with a clear error.

### Anti-Pattern 4: Splitting broker.py into Sub-Routers Prematurely

**What:** Creating `broker_clients.py`, `broker_solicitations.py` sub-router files.
**Why bad in this codebase:** All endpoints share `require_module("broker")`, `ALLOWED_TRANSITIONS`, and helper functions. Splitting creates import complexity. The service layer already extracts business logic. Net growth is only ~200 lines.
**When to reconsider:** If broker.py exceeds 4000 lines in a future milestone, split into sub-routers with a shared `broker_common.py` for transitions, helpers, and schemas.

---

## Integration Points: New vs Modified

### New Components

| Component | Type | Depends On |
|-----------|------|-----------|
| `broker_clients` table | Schema | tenants, context_entities |
| `broker_client_contacts` table | Schema | broker_clients |
| `carrier_contacts` table | Schema | carrier_configs |
| `broker_recommendations` table | Schema | broker_projects |
| `solicitation_drafts` table | Schema | broker_projects, carrier_configs, carrier_quotes (nullable FK) |
| `broker_project_emails` table | Schema | broker_projects |
| 6 new SQLAlchemy model classes | Model | Corresponding tables |
| `broker_client_service.py` | Service | Models, context_store_writer |
| `broker_contact_service.py` | Service | Models |
| `create_context_entity()` function | Function | ContextEntity model (models.py:550-588) |
| 9 client endpoints | Router | broker_client_service |
| 4 carrier contact endpoints | Router | broker_contact_service |
| 2 recommendation endpoints | Router | Models |
| 2 solicitation endpoints | Router | Models |

### Modified Components

| Component | What Changes | Risk Level |
|-----------|-------------|------------|
| `BrokerProject` model (models.py:2026) | +4 columns, -7 columns, +4 relationships | HIGH -- touches most endpoints |
| `CarrierConfig` model (models.py:1951) | +3 columns, -2 columns, +1 relationship | MEDIUM -- carrier CRUD + solicitation |
| `CarrierQuote` model (models.py:2192) | +2 columns, -6 columns | HIGH -- comparison, tracking |
| `ProjectCoverage` model (models.py:2119) | +3 columns | LOW -- additive only |
| `SubmissionDocument` model (models.py:2304) | +2 columns | LOW -- additive only |
| `ALLOWED_TRANSITIONS` (broker.py:150) | Add `binding` state between `delivered` and `bound` | MEDIUM -- state machine |
| `draft-solicitations` (broker.py:1571) | Write SolicitationDraft, not CarrierQuote | HIGH -- core workflow |
| `approve-send` (broker.py:1798) | Route change + operate on SolicitationDraft | HIGH -- core workflow |
| `_check_all_solicited()` (broker.py:1525) | Query SolicitationDraft not CarrierQuote | HIGH -- automated transition |
| `draft-recommendation` (broker.py:2652) | Write BrokerRecommendation, not project columns | MEDIUM |
| `approve-send-recommendation` (broker.py:2809) | Read BrokerRecommendation, preserve Document creation | MEDIUM |
| `_carrier_to_dict()` (broker.py:248) | Remove email_address field | LOW |
| `_project_to_dict()` (broker.py:181) | Remove recommendation_* fields, add client_name | LOW |
| `context_store_writer.py` | Add create_context_entity() | LOW -- additive |

---

## Recommended Build Order

### Phase 1: Schema -- New Tables (6 tables + RLS)

**Rationale:** Zero app dependency. Tables can exist without any code referencing them.

**Internal order:**
1. `broker_clients` (FK to tenants only)
2. `broker_client_contacts` (FK to broker_clients)
3. `carrier_contacts` (FK to carrier_configs -- already exists)
4. `solicitation_drafts` (FK to broker_projects, carrier_configs, carrier_quotes)
5. `broker_recommendations` (FK to broker_projects)
6. `broker_project_emails` (FK to broker_projects)
7. RLS policies for all 6 tables (standard tenant isolation pattern)

**Execution:** Single `broker_data_model_migration.py` script. Each CREATE TABLE and each RLS statement as its own `await session.execute() + await session.commit()` (PgBouncer workaround). Then `alembic stamp 059`.

### Phase 2: Schema -- Modifications (6 tables altered)

**Rationale:** Must happen after Phase 1 (references new tables). Must happen before Phase 3 (models must match schema).

**Internal order (critical):**
1. ADD columns to all 6 tables (broker_projects, carrier_quotes, project_coverages, carrier_configs, submission_documents, broker_activities)
2. ADD CHECK constraints
3. **Run carrier email seed script** (copies carrier_configs.email_address to carrier_contacts rows)
4. DROP columns (email_address, pipeline_entry_id, recommendation_*, draft_*, is_best_*)
5. DROP indexes (idx_broker_project_pipeline)

**The seed script MUST run between steps 2 and 4.** If email_address is dropped before seeding, data is lost.

### Phase 3: Backend -- Models, Services & Endpoints (Single Atomic Release)

**Rationale:** Column drops in Phase 2 mean the existing model code will crash on any column that was removed. Models, services, and endpoints must deploy together.

**Build order within phase:**

1. **Models** (foundation -- everything depends on these):
   - Add 6 new model classes (BrokerClient, BrokerClientContact, CarrierContact, BrokerRecommendation, SolicitationDraft, BrokerProjectEmail)
   - Modify 5 existing models (remove dropped columns, add new columns and relationships)
   - Use `Mapped[]` / `mapped_column()` syntax consistently

2. **create_context_entity()** in context_store_writer.py:
   - Upsert semantics with `pg_insert().on_conflict_do_update()`
   - Returns the entity (existing or new) -- caller links via context_entity_id

3. **Services** (business logic, testable independently):
   - `broker_client_service.py`: normalize_name, create_client (with context entity), update, list, get, get_projects
   - `broker_contact_service.py`: add/update/delete for both client contacts and carrier contacts, soft limits (20 per client, 10 per carrier)

4. **New endpoints** (thin router wrappers around services):
   - 9 client endpoints (CRUD + contacts + projects)
   - 4 carrier contact endpoints (CRUD)
   - 2 recommendation endpoints (list, create)
   - 2 solicitation endpoints (list, approve)

5. **Modified endpoints -- solicitation restructure** (highest risk):
   - Rewrite `draft-solicitations` to create SolicitationDraft rows
   - Rewrite `approve-send` to operate on SolicitationDraft
   - Rewrite `_check_all_solicited()` to query SolicitationDraft
   - Update carrier email lookup to use carrier_contacts table

6. **Modified endpoints -- recommendation restructure:**
   - Rewrite `draft-recommendation` to create BrokerRecommendation
   - Rewrite `PUT recommendation-draft` to update BrokerRecommendation
   - Rewrite `approve-send-recommendation` to read from BrokerRecommendation (preserve Document creation)

7. **Cleanup** (remove dead references):
   - Remove `email_address` from CreateCarrierBody, UpdateCarrierBody, `_carrier_to_dict()`
   - Remove `recommendation_*` from `_project_to_dict()`
   - Remove `pipeline_entry_id` references
   - Remove `draft_*`, `is_best_*` from CarrierQuote serialization
   - Update ALLOWED_TRANSITIONS: add `binding` state, update transitions

8. **Integration test:** Full workflow end-to-end

### Phase 4: Frontend -- Clients & Contacts

**Rationale:** Pure frontend, independently deployable after Phase 3.

**Build order:**
1. Types (`broker.ts` -- 4 new interfaces + modify BrokerProject)
2. API functions (`api.ts` -- 14 new functions)
3. Clients page + CreateClientDialog
4. Client detail page with contacts section
5. Sidebar navigation (add Clients link between Dashboard and Projects)
6. CreateProjectDialog (add client_id dropdown)
7. CarrierForm (add contacts section)

---

## Scalability Considerations

| Concern | Current State | Mitigation |
|---------|--------------|------------|
| broker.py file size (2900 -> ~3100 lines) | Manageable with section headers | Service layer keeps methods thin |
| models.py file size (2397 -> ~2700 lines) | Acceptable | All broker models are grouped together |
| Context entity upsert contention | Low volume | GIN index on aliases already exists (models.py:557) |
| Carrier contact lookup per solicitation | Single query per carrier | Composite index on (carrier_config_id, role) covers this |
| Partial unique indexes | PostgreSQL native | No application-layer enforcement needed |

---

## Sources

- **Codebase inspection** (HIGH confidence): broker.py (2900 lines, 29 endpoints), context_store_writer.py (373 lines, 5 public functions), models.py (2397 lines, ContextEntity at line 550, broker models at lines 1951-2397), solicitation_drafter.py (169 lines), recommendation_drafter.py
- **SPEC-BROKER-DATA-MODEL.md** (HIGH confidence): Full spec with 10 sections + review log, all SQL DDL, model definitions, endpoint tables, and risk mitigations
- **Existing patterns** (HIGH confidence): PgBouncer DDL workaround, context_store_writer dedup pattern, Mapped[] model syntax, router organization
