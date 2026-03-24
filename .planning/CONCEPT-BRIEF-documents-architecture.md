# Concept Brief: Documents Architecture — The Artifact Layer

> Generated: 2026-03-24
> Mode: Deep (4 rounds)
> Rounds: 4
> Active Advisors: Hickey (simplicity), Vogels (failure), Carmack (shipping), Hightower (infra pragmatism), Thompson (strategy), Bezos (customer obsession), Rams (reductive design), Slootman (execution intensity)
> Artifacts Ingested: Current codebase (skill_executor.py, storage.py, models.py, engine.py, session.py), database schema, Supabase config

## Problem Statement

Flywheel's core promise is **compounding intelligence** — every interaction makes every future interaction smarter. Currently, skill executions generate rich artifacts (14KB+ HTML briefings, company intel reports) but only store atomic facts in `context_entries`. The complete artifact lives buried in `skill_runs.output` — an execution log not designed for retrieval, sharing, or reuse.

This means:
- Users can't find past briefings ("show me the PETRONAS prep from last week")
- Artifacts can't be shared with colleagues (viral distribution blocked)
- Skills can't reference prior complete outputs (only atomic fragments)
- The product has no "library" — the most tangible proof of compounding value is invisible

**Sharpened from brainstorm:** This started as a storage question but is actually a **product feature**. Documents are the unit of value exchange — every shared document demonstrates Flywheel's value to a non-user. The document library is where users SEE the flywheel effect.

## Proposed Approach

Three-layer separation of concerns:

```
┌──────────────────────────────────────────────────────────────┐
│                      SKILL EXECUTION                          │
│                (meeting-prep, company-intel, etc.)             │
└────────┬───────────────────┬────────────────┬────────────────┘
         │                   │                │
    EXTRACT facts       CREATE document    LOG execution
         │                   │                │
         v                   v                v
┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│ context_entries  │  │  documents   │  │  skill_runs  │
│ (Postgres+RLS)  │  │ (Postgres)   │  │ (Postgres)   │
│                  │  │              │  │              │
│ Atomic facts     │  │ Metadata     │  │ Execution log│
│ Deduped          │  │ Title, type  │  │ Status/error │
│ Compounding      │  │ share_token  │  │ Token usage  │
│ Cross-skill      │  │ storage_path │  │ Events log   │
│                  │  │      │       │  │              │
│  THE FLYWHEEL    │  │      v       │  │   THE LOG    │
│ (intelligence)   │  │  Supabase    │  │ (operations) │
│                  │  │  Storage     │  │              │
│                  │  │  (S3 bucket) │  │  Can be      │
│                  │  │  HTML, PDF,  │  │  cleaned up  │
│                  │  │  PPTX, etc.  │  │  over time   │
│                  │  │              │  │              │
│                  │  │ THE LIBRARY  │  │              │
│                  │  │ (artifacts)  │  │              │
└─────────────────┘  └──────────────┘  └──────────────┘
```

**Why this way (Hickey):** Three concepts that change at different rates and for different reasons — facts compound (mutable), documents are immutable snapshots, execution logs are ephemeral. Separating them prevents complection.

## Key Decisions Made

| Decision | Chosen Direction | User's Reasoning | Advisory Influence | Alternative Rejected |
|----------|-----------------|------------------|-------------------|---------------------|
| Separate documents table | Yes — first-class product concept | Documents are shareable, user-facing. "We need a history view" | Thompson (value accrual), Bezos (work backward from share moment) | Enhance skill_runs — conflates ops and product |
| Content storage | Supabase Storage (S3-compatible) | Already provisioned, RLS-aware, supports binary formats | Hightower (use managed), Vogels (durability) | Postgres blob — breaks at PDF/PPTX scale |
| File format support | Store any format (mime_type column) | "Can save as markdown, pdf, json, xlsx, doc, pptx" | Carmack (flexible now, convert later) | Enum of allowed types — too restrictive |
| DocumentDB | No | Adds second database engine for no gain | Hightower, Vogels, Hickey (unanimous) | Adds AWS bill, separate auth, zero Supabase integration |
| Metadata model | JSONB column | Flexible for contacts, companies, tags without schema changes | Hickey (data over structure) | Separate junction tables — over-engineering for V1 |
| V1 scope | Minimal viable | Ship the table, storage integration, and share URL | Carmack, Slootman (execution intensity) | Full-featured document management |

## Advisory Analysis

### Simplicity & Separation of Concerns (Hickey, Rams)
The three-table separation maps cleanly to three distinct concepts: facts (mutable, compounding), artifacts (immutable, shareable), and execution logs (ephemeral, operational). Each changes independently. A document is an immutable snapshot produced by a skill run. Context entries are mutable, deduped facts extracted from documents. The skill_run is the process that produced both. No bidirectional dependencies.

### Infrastructure Pragmatism (Hightower, Vogels)
Supabase Storage is S3-compatible object storage already provisioned in the user's stack. It supports RLS bucket policies, signed URLs for sharing, and handles binary formats natively. Adding AWS DocumentDB or raw S3 would introduce a separate bill, separate auth, and zero integration with existing Supabase RLS. Storage is cheap at current scale (1GB free, 100GB on Pro). Revisit only if hitting 100K+ documents.

### Strategic Value (Thompson, Bezos)
Documents are the unit of value exchange. A shared briefing demonstrates Flywheel's compounding intelligence to non-users — viral distribution of product value. The document library is where users tangibly SEE the flywheel effect. Conflating documents with execution logs makes it impossible to build this product experience. First-class document concept enables: search, share, export, reference in future skills.

### Shipping Pragmatism (Carmack, Slootman)
V1 is a migration, a table, a Supabase Storage bucket, and a write in the skill executor after each run. No folders, no tags, no versioning, no collaborative editing, no format conversion. The skill produces HTML; store it as HTML. PDF/PPTX export is a future feature. Share is a nullable token generated on first share request.

### Failure & Durability (Vogels)
Documents own their content in Supabase Storage — not a reference to skill_runs. If a skill_run is deleted (retention policy, cleanup), the document persists. Copy on finalization: when the skill completes successfully, upload content to Storage and create the documents row. Failed runs never create documents.

## Tensions Surfaced

### Tension 1: Content in Postgres vs Object Storage
- **Rams** argued: Don't duplicate — reference the skill_run
- **Vogels** argued: Documents must survive skill_run deletion
- **Resolution:** Content goes to Supabase Storage (durable, supports binary). Documents table stores metadata + storage_path. Skill_runs can be cleaned up independently.
- **User's reasoning:** Documents should be permanent artifacts, not tied to execution log lifecycle.

### Tension 2: Flexible metadata vs Structured schema
- **Hickey** argued: Structured relations (junction tables for contacts, companies)
- **Carmack** argued: JSONB now, structure later if needed
- **Resolution:** JSONB metadata for V1. Contains contacts[], companies[], tags. Migrate to junction tables if query patterns demand it.
- **User's reasoning:** Ship fast, iterate on structure.

### Unresolved Tensions
- **Format conversion pipeline** — When users want PDF from HTML, PPTX from analysis. Deferred to future phase.
- **Document versioning** — Re-prepping for same contact: new document or update existing? Deferred (V1: always new document).

## V1 Schema

```sql
-- Migration: add documents table
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         UUID NOT NULL REFERENCES users(id),

    -- Identity
    title           TEXT NOT NULL,
    document_type   VARCHAR(50) NOT NULL,   -- 'meeting-prep', 'company-intel', etc.
    mime_type       VARCHAR(100) NOT NULL DEFAULT 'text/html',

    -- Storage
    storage_path    TEXT NOT NULL,           -- Supabase Storage path
    file_size_bytes INTEGER,

    -- Provenance
    skill_run_id    UUID REFERENCES skill_runs(id) ON DELETE SET NULL,

    -- Sharing
    share_token     VARCHAR(64) UNIQUE,     -- generated on first share

    -- Flexible metadata
    metadata        JSONB DEFAULT '{}',
    -- Example: {"contacts": ["Cheok Yen Kwan"], "companies": ["PETRONAS"],
    --           "meeting_type": "discovery", "agenda": "Partnership discussion"}

    -- Lifecycle
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

-- RLS policy (matches context_entries pattern)
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Indexes
CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_type ON documents(tenant_id, document_type);
CREATE INDEX idx_documents_share ON documents(share_token) WHERE share_token IS NOT NULL;
CREATE INDEX idx_documents_metadata ON documents USING GIN(metadata);
```

## Supabase Storage Bucket

```
Bucket: "documents" (private, RLS-enabled)

Path convention: {tenant_id}/{document_type}/{document_id}.{ext}
Example: 8425c316-.../meeting-prep/a1b2c3d4-...html

Policies:
- SELECT: tenant_id matches auth.uid() or share_token is valid
- INSERT: authenticated users, tenant_id matches
- DELETE: authenticated users, tenant_id matches
```

## Skill Executor Integration

After each successful skill run:

```python
# In execute_run(), after skill completes successfully:
if output and rendered_html:
    # 1. Upload to Supabase Storage
    storage_path = f"{tenant_id}/{skill_name}/{run_id}.html"
    await upload_to_storage("documents", storage_path, rendered_html)

    # 2. Create documents row
    doc = Document(
        tenant_id=tenant_id,
        user_id=user_id,
        title=_generate_title(skill_name, context),
        document_type=skill_name,
        mime_type="text/html",
        storage_path=storage_path,
        file_size_bytes=len(rendered_html.encode()),
        skill_run_id=run_id,
        metadata=_extract_metadata(skill_name, input_text, output),
    )
    session.add(doc)
```

## What Each Skill Produces (Post-Implementation)

| Skill | Context Entries (facts) | Document (artifact) |
|-------|------------------------|-------------------|
| **meeting-prep** | contacts, meeting-history, positioning, competitive-intel, product-modules, market-signals, relationship-intel | Full HTML briefing |
| **company-intel** | positioning, icp-profiles, competitive-intel, product-modules, market-taxonomy | Company intel report |
| **Future: deal-review** | deal-terms, risk-flags | Deal analysis report |
| **Future: legal-review** | contract-clauses, risk-flags | Legal review report |

## Open Questions

- [ ] Document title generation — template per skill type or LLM-generated?
- [ ] Share URL format — `/d/{share_token}` public page or require auth?
- [ ] Retention policy — do documents expire? (Probably not — they're the value)
- [ ] Full-text search on document content — FTS on Supabase Storage content or separate index?
- [ ] Export pipeline — HTML → PDF/DOCX conversion engine (wkhtmltopdf, Puppeteer, or python-docx?)

## Recommendation

**Proceed to implementation.** This is a clear, well-scoped V1 with strong advisory consensus. Create as a new GSD phase:

1. Alembic migration for `documents` table
2. Supabase Storage bucket setup
3. Wire into skill executor (company-intel + meeting-prep)
4. API endpoints: `GET /documents`, `GET /documents/{id}`, `POST /documents/{id}/share`
5. Frontend: document library view, share flow

Estimated scope: 1 phase, 3-4 plans.
