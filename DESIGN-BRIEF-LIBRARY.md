# Design Brief: Library Redesign

> Generated: 2026-04-08
> Revised: 2026-04-08 (post advisory board + founder input on scalability)
> Theme: Light (dark mode deferred)
> Accessibility: WCAG AA
> Rubric Score: Target 8+/10
> Advisors: Schoger (visual), Norman (usability), Frost (components)

## Current State

### Problems Identified
1. **Unreadable titles**: Documents show raw UUIDs ("DOCUMENT_FILE:9566444a-...") or raw URLs
2. **Duplicates**: Same URL appears 3x as separate cards — no dedup
3. **Single category**: Only "Company Intel" tab — no organization for different document types
4. **No company context**: Flat dump with no way to find "all docs for Acme Corp"
5. **No cross-cutting organization**: No way to group by initiative ("Series A", "Q2 board prep")
6. **Not scalable**: Current design breaks at 200+ docs, multiple team members, or multiple modules

### Current Rubric Score: 4/10

## Design Vision

### Scale Context
Flywheel is not just a solo founder CRM. The platform vision includes:
- **Multiple modules**: CRM, Product, HR, Legal, Finance — each generating documents
- **Team collaboration**: Multiple team members creating and consuming documents
- **Thousands of documents**: Accumulated over months/years across companies and initiatives

The Library must work for a solo founder with 20 docs AND a 20-person team with 5,000 docs across 4 modules.

### Data Model

```
Document
  ├── document_type: string       (auto-set by skill — "meeting-prep", "research", etc.)
  ├── account_id: FK → accounts   (auto-resolved — which company this is about)
  ├── tags: string[]              (flexible — both auto-applied and user-defined)
  ├── module: string              (future — "crm", "product", "hr", "legal", "finance")
  ├── created_by: FK → profiles   (who created — for team filtering)
  └── title: string               (human-readable, derived at write time by skill)
```

### Three Filtering Axes

| Axis | Source | UI Element | Example |
|------|--------|------------|---------|
| **Type** (what it is) | `document_type`, auto-set by skill | Tabs across top | "Meeting Prep", "Research", "Sales Collateral" |
| **Company** (who it's about) | `account_id`, auto-resolved from context | Dropdown filter | "Acme Corp", "TrustLayer", "All Companies" |
| **Tags** (everything else) | `tags[]`, auto-suggested + user-defined | Clickable pill bar | "series-a", "board-prep", "compliance", "q2" |

**Key principle:** Type and Company are structured and automatic (zero user effort). Tags are the escape hatch for cross-cutting concerns that the system can't predict.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Library  (42)                                    [Search]   ≡ ⊞ │
├──────────────────────────────────────────────────────────────────┤
│ All (42)  Meeting Prep (8)  Research (6)  Collateral (4)  ...   │  ← type tabs
│                                                                  │
│ Company ▾    Tags: [series-a ×] [+ Add tag]                     │  ← filters
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ── TODAY ────────────────────────────────────────────────────── │
│                                                                  │
│ 📋  Discovery Call Prep          Acme Corp        2h ago   [⋯] │
│     [meeting-prep] [series-a]                                    │
│                                                                  │
│ 🔍  Account Research             Acme Corp        2h ago   [⋯] │
│     [research]                                                   │
│                                                                  │
│ 📄  Value Prop One-Pager         Acme Corp        3h ago   [⋯] │
│     [sales-collateral] [series-a]                                │
│                                                                  │
│ ── THIS WEEK ───────────────────────────────────────────────── │
│                                                                  │
│ 🏢  Company Intelligence         Lumif.ai         2d ago   [⋯] │
│     [company-intel]                                              │
│                                                                  │
│ 📊  March Investor Update         —               3d ago   [⋯] │
│     [investor-update] [board-prep]                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions (Post Advisory Board)

1. **Flat time-grouped list** — not company-grouped sections. Norman: three-level nesting (time → company → doc) causes cognitive overload. Time grouping + company filter achieves the same result with simpler scanning.

2. **Structured fields for the predictable, tags for the surprising** — `document_type` and `account_id` handle 90% of filtering automatically. Tags handle cross-cutting concerns ("series-a", "board-prep", "compliance-audit") that span types and companies.

3. **Auto-tagging at write time** — skills tag documents based on context. Users can add/remove tags manually. No tag management overhead unless the user wants it.

4. **Fix titles at the backend** — Frost: client-side title derivation masks bad data. Fix at write time (skills generate readable titles) + migration for existing bad titles. Frontend displays `doc.title` as-is.

5. **Fix dedup at the backend** — Frost: client-side dedup masks duplicate creation. Add dedup-on-save (same title + type + account within 1 hour = update, not create) + migration for existing dupes.

6. **Tags as pills on cards** — show only when tags exist. Cards without tags stay clean (just icon + title + company + time). Tags appear as small muted pills below the title.

7. **Tag filter as clickable pill bar** — tags that exist in the current document set appear as clickable pills below the type tabs. Click to filter. No tag management page — tags are emergent from usage.

## Component Specifications

### DocumentTypeConfig (constant)

```typescript
const DOC_TYPE_CONFIG: Record<string, {
  icon: LucideIcon
  color: string
  label: string
}> = {
  'meeting-prep':     { icon: ClipboardList, color: '#3B82F6', label: 'Meeting Prep' },
  'meeting-summary':  { icon: MessageSquare, color: '#7c3aed', label: 'Meeting Summary' },
  'account-research': { icon: Search,        color: '#14B8A6', label: 'Account Research' },
  'sales-collateral': { icon: FileText,      color: '#F97316', label: 'Sales Collateral' },
  'company-intel':    { icon: Building2,     color: '#E94D35', label: 'Company Intel' },
  'investor-update':  { icon: TrendingUp,    color: '#22C55E', label: 'Investor Update' },
  'account-strategy': { icon: Target,        color: '#6366F1', label: 'Account Strategy' },
  'competitive-intel':{ icon: Swords,        color: '#F59E0B', label: 'Competitive Intel' },
  'custom':           { icon: File,          color: '#6B7280', label: 'Document' },
}
```

### DocumentRow (list view)

**Layout:** Single flex row, min-height 56px, hover bg change

```
[TypeIcon 16px in 28px circle] [Title + Tags row] [Company name] [TimeAgo] [⋯]
```

- **Icon**: 16px icon in 28px circular background at type color × 0.08 opacity (Schoger)
- **Title**: 14px, weight 500, headingText color. Truncate with ellipsis.
- **Tags row**: Below title, only if tags exist. Small pills (11px, muted bg, secondary text color). Max 3 visible + "+N more" overflow.
- **Company**: 13px, secondaryText. Right-aligned. Shows account name or "—" if no association.
- **Time**: 13px, secondaryText. Relative format.
- **⋯ menu**: Appears on hover. Actions: Open, Add tag, Delete.
- **Entire row clickable**: navigates to document detail (Norman: don't hide primary action in menu).

**States:**
- Default: no background
- Hover: `rgba(0,0,0,0.02)` background + show ⋯ menu
- Active: navigate to detail

### DocumentGridCard (grid view)

**Layout:** BrandedCard, padding 20px

```
┌──────────────────────────────┐
│ [TypeIcon in circle]         │
│ Title of Document            │
│ Company Name                 │
│ [tag1] [tag2]                │
│                              │
│ 2h ago                       │
└──────────────────────────────┘
```

- Resting shadow: `0 1px 3px rgba(0,0,0,0.08)` (Schoger)
- Hover: coral border `rgba(233,77,53,0.3)` + lift shadow `0 4px 12px rgba(0,0,0,0.1)`
- Transition: `all 150ms ease`

### TagPill (atom)

- Background: `rgba(0,0,0,0.04)`, border-radius pill (9999px)
- Text: 11px, weight 500, secondaryText color
- Padding: 2px 8px
- Interactive variant (in filter bar): hover darkens bg, active shows coral border
- Removable variant (in detail view): shows × on hover

### TagFilterBar

- Horizontal scrollable row of TagPills
- Shows all unique tags from current filtered document set
- Click to toggle filter (active = coral bg at 0.1 + coral text)
- Multiple tags combine with AND logic
- Only visible when tags exist in the dataset (Norman: don't show empty filter controls)

### CompanyFilter (dropdown)

- Button: "Company ▾" or "Acme Corp ▾" when selected
- Popover: searchable list of companies derived from documents
- Each company shows doc count
- "All Companies" at top to clear
- Companies sorted by doc count descending

### TimeGroupHeader

- Uppercase, 11px, weight 600, letter-spacing 0.05em, secondaryText color
- Horizontal rule extending right (Schoger: distinct from other headers)
- Labels: TODAY, YESTERDAY, THIS WEEK, LAST WEEK, THIS MONTH, EARLIER

## Tagging System

### Auto-tagging (at document creation)

Skills auto-apply tags based on context:
- `meeting-prep` skill: tags with meeting title, attendee company names
- `account-research` skill: tags with company name, industry
- `sales-collateral` skill: tags with collateral type ("one-pager", "case-study")
- `investor-update` skill: tags with month/quarter ("march-2026", "q1-2026")

### User-defined tags

- Add from document detail view (tag input with autocomplete from existing tags)
- Add from ⋯ menu on document row ("Add tag")
- Remove by clicking × on tag pill in detail view

### Team tag conventions (future)

- Admin can define "pinned tags" that appear prominently in the tag filter bar
- Shared tag namespace across team members
- Tag-based views: save filter combinations as named views ("Series A Docs", "Board Materials")

## Interaction Specs

| Action | Feedback | Transition |
|--------|----------|------------|
| Click document row | Navigate to detail | Instant |
| Hover row | Tint bg + show ⋯ | 150ms ease |
| Click type tab | Filter list, update counts | Instant (client-side) |
| Click company dropdown | Show popover with search | 150ms ease |
| Click tag pill (filter bar) | Toggle filter, update list | Instant |
| Click "Add tag" (⋯ menu) | Show tag input with autocomplete | 150ms |
| Type in tag input | Autocomplete from existing tags | Debounced 200ms |
| Press Enter on tag input | Apply tag to document | Instant + toast |
| Click × on tag pill (detail) | Remove tag | Instant + undo toast |
| Click Delete (⋯ menu) | Confirm dialog → soft delete | 200ms fade |

## Accessibility

- Type tabs: role="tablist" with aria-selected
- Tag filter bar: role="toolbar" with aria-label="Filter by tag"
- Tag pills: role="button" with aria-pressed for active state
- Company dropdown: aria-haspopup, aria-expanded
- ⋯ menu: role="menu" with keyboard nav (Enter/Space to open, Escape to close)
- Document rows: keyboard navigable (Tab + Enter to open)
- Search: aria-label="Search documents"

## Backend Changes Required

### Schema
1. Add `tags` column to documents table: `TEXT[] DEFAULT '{}'`
2. Add GIN index on tags for fast array contains queries: `CREATE INDEX idx_documents_tags ON documents USING GIN (tags)`
3. Add `module` column (nullable, for future): `TEXT DEFAULT 'crm'`

### API
1. `GET /documents/` — add `tags` filter param (array), add `account_id` filter param
2. `GET /documents/tags` — return unique tags with counts for the tag filter bar
3. `PATCH /documents/{id}/tags` — add/remove tags on a document
4. `POST /documents/from-content` — accept `tags[]` param, auto-apply skill-derived tags

### Write Path Fixes
1. **Smart titles**: Skills must generate readable titles at creation. "Meeting Prep: Acme Corp — Discovery Call" not "DOCUMENT_FILE:uuid"
2. **Dedup on save**: Same `title + document_type + account_id` within 1 hour = update existing, not create new
3. **Auto account resolution**: `flywheel_save_document` accepts `company_name`, resolves to `account_id` via fuzzy match on accounts table
4. **Auto-tagging**: Each skill appends context-appropriate tags at save time

### Migration
1. Clean up existing bad titles (UUID-prefixed, raw URLs)
2. Merge duplicate documents (keep newest, soft-delete others)
3. Backfill `account_id` on existing company-intel docs from metadata
4. Add `tags` column with empty default

## Empty States

**Library empty:**
```
[FileText icon, 40px, coral 0.8]
"Your library is empty"
"Documents from meeting prep, account research, and skills will appear here automatically."
```

**Filter yields no results:**
```
"No documents match your filters"
"Try removing a filter or search term."
[Clear filters] button
```

**No tags exist yet:**
Tag filter bar hidden entirely (Norman: don't show empty controls).

## Future Considerations

- **Module tabs**: When Product/HR/Legal modules ship, add top-level module nav above type tabs
- **Saved views**: "Series A Docs" = saved filter combination (type + company + tags)
- **Team permissions**: Document visibility by team role
- **Document versioning**: Track changes to living documents (company profiles, investor updates)
- **Smart collections**: Auto-generated collections like "Board prep for April" based on tags + time

---

## Advisory Board Sign-off

| Advisor | Verdict | Key Input |
|---------|---------|-----------|
| Don Norman | Approved | Flat list with filters (not nested groups). Tags optional, not primary nav. Auto-derive context. |
| Steve Schoger | Approved | Icon in tinted circle. Time headers distinct from content. Muted tag pills. Hover polish. |
| Brad Frost | Approved | Fix titles and dedup at backend. Tags as `string[]` column with GIN index. Proper account FK. |
| Founder (Sharan) | Revised scope | Tags are infrastructure, not escape hatch. Platform scales to modules + teams. |

---

*Ready for GSD consumption. Implementation: 2 plans — Plan 01 (backend: schema, smart titles, dedup, auto-tagging API) and Plan 02 (frontend: new components, filters, tag UI).*
