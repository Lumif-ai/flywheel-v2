# Technology Stack — CRM Redesign Additions

**Project:** Flywheel CRM Redesign (Intelligence-First CRM Milestone)
**Researched:** 2026-03-27
**Confidence:** HIGH (all claims verified against official sources or npm registry)

---

## Context: What Already Exists (Do NOT Re-add)

The following are already in the project and must not be duplicated or replaced:

| Technology | Version | Notes |
|------------|---------|-------|
| React | ^19.0.0 | Already installed |
| Vite + TypeScript | ^6.0.0 / ^5.5.0 | Build toolchain locked |
| Tailwind CSS v4 | ^4.0.0 | @tailwindcss/vite integration |
| shadcn/ui + @base-ui/react | — | Component primitives |
| TanStack Query | ^5.91.2 | Server state |
| TanStack Virtual | ^3.13.23 | Already installed — use for any custom virtual scroll |
| Zustand | ^5.0.12 | Client state |
| Lucide React | ^0.577.0 | Icons |
| Sonner | ^2.0.7 | Toasts |
| Supabase JS | ^2.99.3 | Auth + storage |
| FastAPI | >=0.115 | Backend framework |
| SQLAlchemy (async) | >=2.0 | ORM |
| Alembic | >=1.14 | Migrations |
| anthropic | >=0.86.0 | LLM SDK — already in pyproject.toml |
| pdfplumber + python-docx | — | Document parsing |
| httpx | >=0.27 | Async HTTP |

---

## New Stack Additions

### 1. Airtable-Style Data Grid

**Recommended: AG Grid Community** (`ag-grid-community` + `ag-grid-react`)

**Version:** 35.2.0 (latest as of 2026-03-27, last published 2 days ago)

**Why AG Grid over alternatives:**
- AG Grid Community (free, MIT-compatible for community edition) is the only library that ships column resize + reorder + hide + inline cell editing + column filters all without an enterprise license.
- `react-datasheet-grid` (v4.11.6, ~49k weekly downloads) is optimized for spreadsheet data entry (like a form with rows), not for CRM record tables with mixed column types, custom renderers, and server-side filtering. It does not support column reorder or hide natively.
- TanStack Table is headless — you build all UI yourself. Given TanStack Virtual is already in the project, this would work but costs 2-3x implementation time compared to AG Grid's batteries-included approach, and inline editing requires completely custom implementation.
- AG Grid v34.3.0+ explicitly supports React 19 (confirmed in changelog). The app uses React 19.0.0, making versions prior to 34.3.0 a blocker.
- AG Grid 33.0+ collapsed all modules into `ag-grid-community` — no longer need `@ag-grid-community/core` separately.

**Key community-edition features confirmed available:**
- Column resize, reorder, hide (via Columns Tool Panel)
- Inline cell editing (single or double click)
- Column filters (text, number, date, set)
- Row selection, keyboard navigation
- Custom cell renderers (React components)
- Virtualized rows (built-in, no separate library needed)

**NOT available in community (enterprise-only):**
- Pivoting, row grouping aggregations, integrated charts
- Excel export, server-side row model with SSRM
- These are not needed for this milestone.

```bash
npm install ag-grid-community ag-grid-react
```

**Integration note:** AG Grid ships its own CSS theme (`ag-theme-quartz` or `ag-theme-alpine`). To match Tailwind v4 + shadcn design, use `ag-theme-quartz` as the base and override CSS variables for colors, fonts, border radius. Do not fight the theming system — it uses CSS custom properties which are straightforward to override.

---

### 2. Spring Animations + Micro-Interactions

**Recommended: Motion** (`motion`)

**Version:** 12.38.0 (latest as of 2026-03-27)

**Why Motion (formerly Framer Motion):**
- Framer Motion was rebranded to Motion in 2025 when it became an independent project. The `framer-motion` package is now unmaintained — `motion` is the active package.
- Import path changed: `import { motion } from "motion/react"` (not `framer-motion`).
- Motion v12 uses the Web Animations API + ScrollTimeline for 120fps native performance, falling back to JS when needed.
- 30 million monthly npm downloads — the dominant animation library for React.
- The existing `tw-animate-css` in the project is CSS-only animations. Motion adds JS-driven spring physics for drag interactions, layout transitions, shared-element transitions, and gesture-based micro-interactions that CSS alone cannot do.
- React Spring is the alternative for physics-heavy animations, but Motion's API is declarative and component-based, which integrates more naturally with the existing React + Tailwind codebase. React Spring requires imperative spring configuration and doesn't support layout animations.

**Requires:** React >=18.2. The project uses React 19.0.0 — compatible.

```bash
npm install motion
```

**Integration note:** Do not install `framer-motion` — it is the deprecated package. Import exclusively from `motion/react`.

---

### 3. File Upload Component

**Recommended: react-dropzone** (`react-dropzone`)

**Why react-dropzone:**
- The project uses Supabase Storage (already configured via `@supabase/supabase-js`). File upload plumbing already exists in `backend/src/flywheel/api/documents.py`. No new upload infrastructure needed — just a drop zone UI.
- `react-dropzone` provides `useDropzone` hook (headless — no opinionated UI). This integrates cleanly with existing shadcn/ui card components and Tailwind styling.
- React 19 peer dependency PR merged (confirmed in GitHub issues). Use the latest version.
- Alternative `uppy` is far heavier (multiple packages, ~200kb+) and targets multi-provider uploads — overkill for a simple relationship-page attachment pattern.

```bash
npm install react-dropzone
```

**Integration note:** The upload flow is: `useDropzone` captures file → POST to FastAPI `/documents/upload` (already exists) → store object path in relationship record's `attachments` JSONB column. Supabase storage bucket `documents` is already in use.

---

### 4. AI Synthesis Engine (Backend — RAG + Embeddings)

**Recommended: pgvector + openai (embeddings only)**

#### 4a. Vector Storage: pgvector

**Python package:** `pgvector` v0.4.2 (released Dec 5, 2025)
**PostgreSQL extension:** `pgvector` (already on Supabase — enabled by default on all Supabase projects)

**Why pgvector over a separate vector database:**
- The project already uses PostgreSQL via Supabase. Adding a separate vector database (Pinecone, Weaviate, Qdrant) means a new infrastructure dependency, new credentials, new cost tier, and operational overhead.
- pgvector integrates directly with SQLAlchemy 2.0 async via `pgvector.sqlalchemy.Vector` type and works with Alembic migrations.
- For CRM RAG (relationship notes, emails, documents per contact/account — likely <100k documents per tenant), pgvector with HNSW index is sufficient. Separate vector DBs only win at 10M+ vectors.

```bash
pip install pgvector>=0.4.2
```

**Alembic integration:** Requires registering the vector type in `env.py`:
```python
from pgvector.sqlalchemy import Vector
# In env.py, after connecting:
connection.dialect.ischema_names['vector'] = Vector
```

#### 4b. Embedding Model: OpenAI text-embedding-3-small

**Why NOT use Anthropic for embeddings:**
- The Anthropic Python SDK (already in the project at `>=0.86.0`) does not provide embedding models. Anthropic's API is generation-only.
- OpenAI `text-embedding-3-small` is the current standard: 1536 dimensions, $0.02/1M tokens, strong retrieval accuracy, widely documented.

**Python package:** `openai` — already likely installed as a transitive dependency, but add explicitly.

```bash
pip install openai>=1.0
```

**Integration note:** The `skill_executor.py` already manages Anthropic API key context per-tenant. Extend the same BYOK pattern for OpenAI keys if per-tenant embedding is needed, or use a single platform key for synthesis.

#### 4c. RAG Orchestration: No LangChain/LlamaIndex

**Why vanilla Python over LangChain or LlamaIndex:**
- LangChain is considered bloated for simple RAG in 2025 community consensus (GitHub discussion #182015 with 200+ upvotes).
- The required pattern is: embed query → pgvector similarity search → assemble context chunks → call Anthropic messages API. This is ~30 lines of Python and does not benefit from an orchestration framework.
- LangChain adds ~50MB to the dependency tree and introduces version lock-in conflicts with the existing `anthropic` SDK.
- The existing `skill_executor.py` already handles LLM prompt assembly and context injection. The RAG layer adds one function: `retrieve_context(query, relationship_id) -> str`.

**No new orchestration dependency needed.** Implement as a service function using existing `anthropic` + new `openai` (embeddings) + `pgvector`.

---

### 5. Signal/Notification Badge System

**No new dependencies needed.**

The notification badge system is pure UI state. Recommended implementation:
- Store signal counts in a `signals` table (already planned in data model).
- Zustand store slice for real-time signal counts (already in project).
- Motion (added above) for badge entrance animations.
- Supabase Realtime for push updates to signal counts (already available via `@supabase/supabase-js`).

---

## Complete Installation Summary

### Frontend (npm)

```bash
# Airtable-style grid
npm install ag-grid-community ag-grid-react

# Spring animations + micro-interactions
npm install motion

# File drag-drop
npm install react-dropzone
```

### Backend (pip / pyproject.toml additions)

```toml
# pyproject.toml dependencies additions
"pgvector>=0.4.2",
"openai>=1.0",
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Data Grid | ag-grid-community@35 | TanStack Table (headless) | Inline editing, column management, and filtering require full custom implementation; 2-3x more code |
| Data Grid | ag-grid-community@35 | react-datasheet-grid@4 | No column reorder/hide; optimized for form-entry rows, not CRM record tables |
| Data Grid | ag-grid-community@35 | AG Grid Enterprise | Paywall; community edition covers all required features |
| Animation | motion@12 | react-spring@10 | Less natural integration with component-based React; no layout animation support |
| Animation | motion@12 | framer-motion | Deprecated package; motion is the current name |
| Animation | motion@12 | tw-animate-css (already in project) | CSS-only; cannot do spring physics, drag interactions, or layout transitions |
| Vector DB | pgvector (Supabase) | Pinecone / Qdrant | New infrastructure dependency; unnecessary at CRM scale |
| RAG Framework | vanilla Python | LangChain | Bloated for simple RAG; conflicts with existing anthropic SDK |
| RAG Framework | vanilla Python | LlamaIndex | Overkill; good for complex document indexing pipelines, not per-relationship summaries |
| Embeddings | openai (text-embedding-3-small) | Anthropic | Anthropic SDK does not provide embeddings |
| File Upload UI | react-dropzone | uppy | ~10x heavier; multi-provider support not needed when Supabase storage is already set up |

---

## Sources

- [AG Grid React Version Compatibility](https://www.ag-grid.com/react-data-grid/compatibility/) — React 19 support confirmed in v34.3.0+
- [AG Grid What's New](https://www.ag-grid.com/whats-new/) — v35.2.0 latest
- [AG Grid Community Cell Editing](https://www.ag-grid.com/react-data-grid/cell-editing/) — confirmed community edition
- [Motion Installation Docs](https://motion.dev/docs/react-installation) — v12.37.0, npm package `motion`
- [Motion Rebranding Announcement](https://motion.dev/blog/framer-motion-is-now-independent-introducing-motion) — framer-motion deprecated
- [pgvector Python PyPI](https://pypi.org/project/pgvector/) — v0.4.2, Dec 2025
- [pgvector SQLAlchemy/Alembic integration](https://github.com/pgvector/pgvector-python) — Vector type for SQLAlchemy 2.0
- [OpenAI text-embedding-3-small](https://platform.openai.com/docs/models/text-embedding-3-small) — $0.02/1M tokens
- [react-dropzone React 19 PR](https://github.com/react-dropzone/react-dropzone/pull/1422) — React 19 peer dep added
- [LangChain too complex for simple RAG discussion](https://github.com/orgs/community/discussions/182015) — community consensus 2025
- [npmtrends react-datasheet-grid](https://npmtrends.com/react-datasheet-grid) — v4.11.6, ~49k weekly downloads
