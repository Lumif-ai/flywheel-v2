# Feature Landscape: Library Redesign

**Domain:** Document library with tagging, filtering, pagination, dedup for AI-produced content
**Researched:** 2026-04-08
**Overall confidence:** HIGH (based on codebase analysis + established SaaS patterns)

## Current State (What Exists)

Before mapping new features, here is what the library already has:

| Existing | Implementation | Notes |
|----------|---------------|-------|
| Flat document list | `DocumentLibrary.tsx` — fetches all docs, client-side tab filter | Works but loads everything up front |
| Type tabs | Dynamic tabs built from `document_type` field | Client-side only, counts from loaded docs |
| Client-side search | Filters on title, companies, contacts in memory | No server-side search |
| List/grid toggle | `ViewToggle` component with localStorage persistence | Already polished |
| Date grouping | Today/Yesterday/This Week/Earlier buckets | Good UX, keep it |
| Manual "Load More" | Button-based pagination, PAGE_SIZE=50 | Not infinite scroll — cursor-based offset |
| Share via token | Generate share_token, copy link | Working |
| Smart title cleanup | `displayTitle()` strips prefixes, resolves URLs, fallback to metadata | Already handles bad titles somewhat |
| Document type styles | Color-coded icons per type (meeting-prep, company-intel, etc.) | Extensible via `TYPE_STYLES` map |

**Key gaps the redesign addresses:** No tags. No company filter. No server-side search. No dedup. Titles still bad at source. No account linkage on the Document model (only loose `metadata_.companies` JSON array).

---

## Table Stakes

Features users expect in any modern document library. Missing = product feels broken or amateur.

| # | Feature | Why Expected | Complexity | Dependencies | Real-World Reference |
|---|---------|-------------|------------|-------------|---------------------|
| T1 | **Type tab filtering (server-side)** | Users already see tabs — but they only filter client-loaded docs. At 500+ docs, tabs must query server with counts from the full dataset. | Low | Existing `document_type` column + index `idx_documents_type` | Notion database views, Linear issue type filter |
| T2 | **Company/Account dropdown filter** | Founders think in accounts ("show me everything on Acme"). Docs already have `metadata_.companies` but no filter UI or proper FK. | Medium | Account resolution (D4) adds `account_id` FK on documents, account list endpoint already exists | Salesforce files-per-account, HubSpot document associations |
| T3 | **Text search (server-side)** | Current client-side search breaks at scale. Users type a company name or keyword and expect results. ILIKE on title + metadata is sufficient for <10K docs — no need for full-text search engine. | Medium | Backend endpoint changes, debounced input already exists at 300ms | Google Drive search bar, Notion quick search |
| T4 | **Server-side pagination with cursor** | Current offset-based pagination works but gets slower as offset grows. Cursor-based (keyset on `created_at, id`) is the standard for sorted lists. | Medium | Backend: change from offset to `created_at < cursor` keyset pattern | Every modern SaaS list: Linear, Notion, Slack |
| T5 | **Infinite scroll (hybrid)** | Users expect content to load as they scroll, not click "Load More." Hybrid = auto-load on scroll + show count ("Showing 150 of 2,341"). Keep "Load More" as accessibility fallback. | Medium | Frontend: IntersectionObserver trigger, backend: cursor pagination (T4) | Google Drive, Dropbox, Notion |
| T6 | **Dedup on save** | Skills re-run and create duplicates. Users see "Meeting Prep: Acme" four times. Atomic dedup = hash(tenant_id + skill_name + normalized_title + date_bucket) with UPSERT. | Medium | Backend: content hash column, unique constraint, upsert logic in `create_from_content` endpoint | Gmail dedup, Slack message dedup |
| T7 | **Smart title generation at source** | Current titles are "Company Intel: https://lumif.ai/" or "Meeting Prep: DOCUMENT_FILE:uuid". Frontend `displayTitle()` patches this but the source data is bad. Fix at write time in the save endpoint. | Low | Backend: title generation logic in `create_from_content`, skill_name + metadata heuristics | Notion auto-title from content, Google Docs "Untitled document" |
| T8 | **Empty & loading states for filter combos** | Already exist but need updating for new filter combinations. "No documents match these filters" with clear-all action per active filter. | Low | None — already partially built | Linear empty states, Notion filtered-view empty |

---

## Differentiators

Features that set the library apart. Not expected, but valued. These move Flywheel from "document dump" to "intelligence hub."

| # | Feature | Value Proposition | Complexity | Dependencies | Real-World Reference |
|---|---------|-------------------|------------|-------------|---------------------|
| D1 | **Tag system (auto + manual)** | Skills auto-tag on save (e.g., "investor-update", "competitor", "pricing"). Users can add/remove tags. Tags become a powerful cross-cutting filter axis orthogonal to type and company. | High | New `tags` JSONB array column on documents, GIN index, tag CRUD API, pill bar UI, skill ecosystem updates | Notion multi-select property, Dropbox tags, Gmail labels |
| D2 | **Tag pill bar (horizontal filter)** | Clickable colored pills showing all tags in use, with counts. Click to filter, click again to remove. Multi-select OR logic. Sits below type tabs, above search. | Medium | D1 (tag system exists), tag aggregation query to get distinct tags with counts | Linear label pills, GitHub issue labels, Notion multi-select filter |
| D3 | **Multi-axis filter composition** | All three axes (type tabs + company dropdown + tag pills) compose together with AND logic. "Show me Meeting Prep docs for Acme tagged investor-update." Active filters shown as removable chips. | Medium | T1 + T2 + D1 + D2 all working, backend must accept all filter params in one query | Linear compound filters, Notion combined database filters |
| D4 | **Account resolution on save** | When a skill saves a document, it resolves the company to an Account record and sets `account_id` FK. This enables T2 (company filter) to use a proper FK join instead of slow JSONB search. Option C = skills call ensure_account first. | Medium | New `account_id` column on documents, account resolution logic, MCP tool updates | CRM document association (Salesforce, HubSpot) |
| D5 | **Skill compliance / ecosystem updates** | All skills that save documents must: (1) provide meaningful titles, (2) include tags in metadata, (3) ensure account exists before save. This is an ecosystem change, not a UI feature. | Medium | Audit all skills, update save calls, update SKILL.md specs | Internal — no external reference |
| D6 | **Keyboard shortcuts** | `/` to focus search, `Escape` to clear, `G` then `L` for grid/list toggle. Power users (founders) live in keyboard shortcuts. | Low | Frontend only, no backend changes | Linear (extensive shortcuts), Notion (`/` commands), Gmail |
| D7 | **Bulk operations** | Select multiple docs, bulk tag, bulk delete, bulk export. Not MVP but becomes essential at 1K+ docs. | High | Multi-select UI, batch API endpoints, confirmation dialogs | Google Drive multi-select, Notion bulk operations |
| D8 | **Saved views / smart filters** | Save a filter combination as a named view ("My Investor Docs", "Acme War Room"). Persistent per-user. | High | New `saved_views` table, view CRUD API, view switcher UI | Notion saved views, Linear custom views, Salesforce list views |

---

## Anti-Features

Features to explicitly NOT build. These are traps that waste effort or harm the product.

| # | Anti-Feature | Why Avoid | What to Do Instead |
|---|-------------|-----------|-------------------|
| A1 | **Folder hierarchy** | Documents are skill outputs, not user-created files. Folders create organizational burden and conflict with tags. Notion moved away from pure folders toward databases for this reason. | Use tags + type tabs + company filter as the three axes. Flat list with powerful filtering beats nested folders for AI-generated content. |
| A2 | **Full-text search on content (day 1)** | PostgreSQL full-text search on document content requires indexing rendered HTML/markdown, adds significant complexity, and founders search by title/company 95% of the time. | Start with ILIKE on title + metadata fields. Add pg_trgm or tsvector later if search becomes a top user complaint. |
| A3 | **Document versioning** | Skills produce new runs, not edits. Version control implies editing workflows that don't exist. Dedup with upsert handles the "re-run same skill" case. | Dedup on save (T6) handles the primary use case. If a skill re-runs, the old doc is updated in place, not versioned. |
| A4 | **Drag-and-drop reordering** | Library items are time-ordered intelligence artifacts. Manual reordering implies curation effort that conflicts with the "automatic intelligence" value prop. | Keep time-based grouping (Today/Yesterday/etc). Let filtering handle "find what I need." |
| A5 | **Inline document editing** | Documents are rendered skill outputs (HTML from markdown). Editing means either raw markdown editing (bad UX) or WYSIWYG on generated content (massive complexity, low value). | Documents are read-only artifacts. If content needs updating, re-run the skill. |
| A6 | **Tag hierarchy / nested tags** | Adds complexity without proportional value at <5K docs. Notion offers it but most users don't use nested tags. | Flat tags with good naming conventions ("investor-q1", "investor-q2") cover the use case. |
| A7 | **Real-time collaboration on filters** | Multi-user filter state sync. Massive complexity, minimal value for a founder tool. | Each user has their own filter state in URL params or localStorage. |
| A8 | **Complex boolean filter builder** | Linear/Jira-style query builders with AND/OR/NOT nesting. Overkill for a document library with three filter axes. | Three fixed axes (type + company + tags) with implicit AND between axes, implicit OR within tags. Simple, predictable, fast. |

---

## Feature Dependencies

```
T4 (cursor pagination) --> T5 (infinite scroll)
T1 (server-side type filter) --\
T2 (company filter) ----------- --> D3 (multi-axis composition)
D1 (tag system) --> D2 (pill bar) -/
D4 (account resolution) --> T2 (company filter uses account_id FK)
D5 (skill compliance) --> D1 (skills must send tags)
D5 (skill compliance) --> T7 (skills must send good titles)
D5 (skill compliance) --> D4 (skills must ensure account exists)
T6 (dedup) -- standalone, no deps
T7 (smart titles) -- standalone, no deps (backend-only)
T8 (empty states) -- standalone, update as filters land
D6 (keyboard shortcuts) -- standalone, add anytime
D7 (bulk operations) -- after multi-axis filtering works
D8 (saved views) -- after multi-axis filtering works
```

**Critical path:** D4 (account resolution) + D5 (skill compliance) are prerequisites for T2 and D1 to have good data. Without skills sending proper tags and account IDs, the filtering UI has nothing to filter on.

---

## MVP Recommendation

### Phase 1 — Backend Foundation + Data Quality (build first)
1. **T6 — Dedup on save** (stop the bleeding — no more duplicate docs)
2. **T7 — Smart title generation** (fix titles at source, not just display)
3. **D4 — Account resolution** (add `account_id` FK to documents)
4. **T4 — Cursor pagination** (backend prerequisite for everything else)

### Phase 2 — Filtering UI (build second)
5. **T1 — Server-side type tabs** (upgrade existing tabs to query server)
6. **T2 — Company dropdown** (using account_id FK from Phase 1)
7. **T3 — Server-side search** (ILIKE on title + metadata)
8. **T5 — Infinite scroll** (hybrid with IntersectionObserver)

### Phase 3 — Tags + Polish (build third)
9. **D1 — Tag system** (JSONB array + GIN index + CRUD)
10. **D2 — Tag pill bar** (filter UI)
11. **D3 — Multi-axis composition** (all three axes working together)
12. **D5 — Skill ecosystem updates** (all skills send tags + account + good titles)
13. **T8 — Empty state updates** (polish for new filter combinations)

### Defer
- **D6 — Keyboard shortcuts**: Nice-to-have, add in any phase
- **D7 — Bulk operations**: Wait for user demand at scale
- **D8 — Saved views**: Wait for multi-axis filtering to prove its value

---

## Tag Management UX Patterns (Deep Dive)

Since tags are the highest-complexity differentiator, here are the specific patterns to follow:

### Auto-Tagging by Skills (Write Path)
- Skills include `tags: ["meeting-prep", "acme", "q2-review"]` in metadata on save
- Backend validates tags (lowercase, alphanumeric + hyphens, max 50 chars)
- Auto-tags are not special — users can remove them
- **Pattern:** Notion auto-assigns properties on creation; same concept for skill-generated tags

### User Tag Editing (Read Path)
- **Inline pill display:** Tags shown as colored pills on document row/card
- **Click-to-edit:** Click a tag area to open a popover with autocomplete input
- **Autocomplete from existing:** As user types, show matching tags from the tenant's tag pool (max 10 suggestions)
- **Create new:** If no match, show "Create tag: [typed-input]" option at bottom of dropdown
- **Remove:** X button on each pill, or backspace in the edit popover
- **Keyboard:** Arrow keys to navigate suggestions, Enter to select, Escape to close
- **Pattern:** Notion multi-select property editor — popover with search + create + remove

### Tag Pill Filter Bar (Filter Path)
- Horizontal scrollable row of pills showing tags in use (with doc counts)
- Click to toggle filter on/off (pill fills with color when active)
- Multiple tags = OR logic ("show docs tagged investor OR competitor")
- Combined with type tabs and company = AND logic
- Show max ~8 pills visible, overflow indicator (" +12 more") with expand
- **Pattern:** GitHub issue label filter, Linear label pills

### Tag Color Assignment
- Auto-assign from a palette of 8-10 colors based on deterministic hash of tag name
- Same tag always gets same color across all views and sessions
- Users do NOT manually pick colors (anti-feature: too much config overhead for a founder tool)
- **Pattern:** Notion auto-colors for multi-select options

---

## Infinite Scroll UX Patterns (Deep Dive)

The hybrid approach is the consensus for SaaS document lists:

### Implementation Pattern
1. **Initial load:** Fetch first 50 docs with cursor pagination
2. **Scroll trigger:** IntersectionObserver on a sentinel div ~200px before list end
3. **Auto-load:** Fetch next 50 when sentinel becomes visible
4. **Progress indicator:** "Showing 150 of 2,341" pinned at bottom
5. **Loading state:** Skeleton rows/cards appear while fetching (already built)
6. **End state:** "You've seen all documents" message when no more pages
7. **Fallback:** If IntersectionObserver unavailable, "Load More" button remains (already built)

### Preserving Scroll Position
- When user navigates to a document detail and comes back, restore scroll position
- Use React Router's `scrollRestoration` or manual position tracking via ref
- **Critical for UX:** Losing scroll position after viewing a doc is the #1 complaint with infinite scroll lists

### Filter Reset Behavior
- When any filter changes, reset to first page (new cursor)
- Show loading skeleton, not empty state, during filter transition
- Preserve scroll position only within same filter set

---

## Multi-Axis Filter Composition (Deep Dive)

### Three Axes
1. **Type tabs** (horizontal, top): Mutually exclusive single-select (All / Meeting Prep / Company Intel / ...)
2. **Company dropdown** (left of search bar): Single-select dropdown with typeahead search, shows accounts with doc counts
3. **Tag pills** (horizontal bar below tabs): Multi-select, OR within tags

### Composition Logic
- Between axes: AND (`type = meeting-prep AND account_id = X AND (tag = a OR tag = b)`)
- Within tags: OR (selecting "investor" and "competitor" shows docs with either tag)
- Type "All" tab = no type filter applied

### Active Filter Chips
- When company or tags are active, show removable chips below the filter bar
- "Acme Corp x" | "investor x" | "competitor x" | "Clear all"
- Chip removal resets that single axis, not all filters
- **Pattern:** Google Drive active filter chips, Amazon product filter breadcrumbs

### URL State
- Encode filters in URL query params: `?type=meeting-prep&account=uuid&tags=investor,competitor`
- Enables sharing filtered views and browser back/forward navigation
- Debounce URL updates to avoid history spam during rapid filter changes
- **Pattern:** Linear encodes filter state in URL (good); Notion does not (worse — can't share or bookmark views)

---

## Dedup Strategy (Deep Dive)

### Hash-Based Inline Dedup
- **Hash key:** `sha256(tenant_id + skill_name + normalized_title + date_bucket)`
- **Date bucket:** Truncate `created_at` to date (same skill + same title on same day = duplicate)
- **Operation:** UPSERT — if hash exists, update content + metadata + updated_at; if not, insert
- **Normalization:** Lowercase title, strip prefixes ("Meeting Prep: " etc.), collapse whitespace
- **Column:** Add `content_hash TEXT` to documents table with unique constraint per tenant

### Edge Cases
- Different skill re-run same day = UPDATE (desired: latest output wins)
- Same skill different day = INSERT (desired: separate docs for different dates)
- User manually renames a doc = hash changes, no longer dedup-eligible (acceptable)
- Bulk re-run of all skills = all docs updated in place, no new rows (desired)

---

## Sources

- [Notion tagging guide](https://www.thebricks.com/resources/how-to-use-tags-in-notion-a-comprehensive-guide) — MEDIUM confidence
- [How to add tags in Notion (2026)](https://super.so/blog/how-to-add-tags-in-notion) — MEDIUM confidence
- [Linear filters documentation](https://linear.app/docs/filters) — HIGH confidence
- [Linear custom views](https://linear.app/docs/custom-views) — HIGH confidence
- [Filter UX patterns for SaaS (Eleken)](https://www.eleken.co/blog-posts/filter-ux-and-ui-for-saas) — MEDIUM confidence
- [Filter UX Design Patterns (Pencil & Paper)](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-filtering) — MEDIUM confidence
- [Pagination UI in 2026 (Eleken)](https://www.eleken.co/blog-posts/pagination-ui) — MEDIUM confidence
- [Pagination vs infinite scroll (LogRocket)](https://blog.logrocket.com/ux-design/pagination-vs-infinite-scroll-ux/) — MEDIUM confidence
- [Dropbox tags](https://help.dropbox.com/organize/dropbox-tags) — HIGH confidence
- [Google Drive labels](https://help.folgo.com/article/330-what-are-google-drive-labels) — MEDIUM confidence
- [Tag UX to implementation](https://schof.co/tags-ux-to-implementation/) — MEDIUM confidence
- [Autocomplete UX best practices (Baymard)](https://baymard.com/blog/autocomplete-design) — HIGH confidence
- [Complex filters UX (Smart Interface Design Patterns)](https://smart-interface-design-patterns.com/articles/complex-filtering/) — MEDIUM confidence
- [AI-driven UX patterns SaaS 2026 (Orbix)](https://www.orbix.studio/blogs/ai-driven-ux-patterns-saas-2026) — LOW confidence
- [Data deduplication (Wikipedia)](https://en.wikipedia.org/wiki/Data_deduplication) — HIGH confidence
- [Hash-based dedup internals](https://pibytes.wordpress.com/2013/02/09/deduplication-internals-hash-based-part-2/) — MEDIUM confidence
