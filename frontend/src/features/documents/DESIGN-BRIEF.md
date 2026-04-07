# Design Brief: Library Page Overhaul

> Generated: 2026-03-31
> Theme: Light + Dark (via CSS custom properties)
> Accessibility: WCAG AA
> Current Rubric Score: 5.25/10
> Target Rubric Score: 9/10
> Advisors: Schoger (visual), Norman (usability), Frost (components)

## Current State

- Pages audited: DocumentLibrary, DocumentCard, DocumentViewer
- Current rubric score: 5.25/10
- Components found: 5 total, 2 in library (BrandedCard, Toast), 3 inline
- Accessibility violations: 4 (no focus on filters, no aria-labels on filters, no search landmark, no skip nav)
- Key problems: flat vertical list, no search, no grid view, all cards identical weight, no stats, inline empty state ignores library EmptyState component

## Design Vision

Transform the library from a basic chronological feed into a **polished knowledge base** — like Notion's sidebar meets Linear's list density. The page should feel like opening a curated intel vault, not scrolling through a feed.

---

## Page: DocumentLibrary (Main)

### Layout
- Max-width: 1120px (spacing.maxGrid)
- Horizontal padding: 48px desktop, 24px mobile
- Three zones stacked vertically:
  1. **Header zone** — title + stats row + search/view controls
  2. **Content zone** — document cards in list or grid
  3. **Pagination zone** — load more with count context

### Visual Hierarchy
- **Primary:** Page title "Library" + document count badge
- **Secondary:** Search bar + filter tabs + view toggle
- **Tertiary:** Date group labels + individual cards

---

### Header Zone

```
┌─────────────────────────────────────────────────────────┐
│  Library  (42)                                          │
│                                                         │
│  ┌──────────────────────────────┐  [All] [Preps] [Intel]│
│  │ 🔍 Search documents...       │         [≡] [⊞]      │
│  └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

**Title row:**
- "Library" — 28px, weight 700, color: headingText, letterSpacing: -0.02em
- Count badge — pill badge next to title showing total count
  - Background: brandTint, color: secondaryText, font: 13px weight 500
  - Format: "(42)" or "(42 documents)"

**Controls row** (flex, items-center, justify-between, gap-3, mt-6):
- **Left: Search input** — 320px max-width, 44px height
  - Uses InputGroup component with Search icon addon
  - Placeholder: "Search documents..."
  - Debounced 300ms (match existing pattern in PipelineFilterBar)
  - Clear button (X) when text present
  - border: 1px solid subtleBorder, borderRadius: 12px
  - Focus: outline 2px solid brandCoral, outline-offset 2px
  - aria-label: "Search documents"

- **Center: Filter tabs** — use existing Tabs component (variant="line")
  - Tabs: All (count) | Meeting Preps (count) | Company Intel (count)
  - Each tab shows count in a subtle badge
  - Active: brandCoral underline via Tabs "line" variant
  - Accessible: TabsList with proper aria-labels

- **Right: View toggle** — 2-button group
  - List view (≡ icon) / Grid view (⊞ icon)
  - Active: brandCoral bg with white icon
  - Inactive: transparent bg, secondaryText icon
  - 36x36px buttons, border-radius: 8px
  - Grouped with 1px shared border
  - aria-label: "Switch to list view" / "Switch to grid view"
  - Keyboard: arrow keys to toggle between views

---

### Content Zone — List View (Default)

Compact rows instead of tall cards. Each row is a single horizontal line.

```
┌──────────────────────────────────────────────────────────┐
│  TODAY                                                    │
│                                                          │
│  [📄] Meeting Prep: Acme Corp Q2 Review    Meeting Prep  │
│       Acme Corp · John Smith               2h ago    [→] │
│                                                          │
│  [🏢] Competitive Analysis: TechStart      Company Intel │
│       TechStart Inc                        5h ago    [→] │
└──────────────────────────────────────────────────────────┘
```

**Document row** (replaces DocumentCard for list view):
- Height: auto, min ~64px. Single row with 2 text lines.
- Layout: flex, items-center, gap-3, px-4, py-3
- Background: transparent, hover: rgba(233,77,53,0.04), border-radius: 12px
- Transition: background 200ms ease
- **Left icon** — 40x40px rounded-lg, background: type-specific tint
  - meeting-prep: blue tint (#3B82F6 at 10%), FileText icon in #3B82F6
  - company-intel: purple tint (#A855F7 at 10%), Building2 icon in #A855F7
  - default: brandTint, FileText icon in brandCoral
- **Content** (flex-1, min-w-0):
  - Title: 15px, weight 600, color: headingText, truncate
  - Meta line: 13px, weight 400, color: secondaryText
    - Entities (companies/contacts, max 2) + relative time
    - Separator: " · " between entities
- **Type badge** — pill, 12px, weight 500
  - meeting-prep: bg rgba(59,130,246,0.1), text #2563EB
  - company-intel: bg rgba(168,85,247,0.1), text #7C3AED
  - default: bg brandTint, text brandCoral
- **Chevron** — ChevronRight, 16px, color: secondaryText, opacity: 0 -> 1 on row hover
- **Share button** — hidden by default, appears on hover
  - Icon button, 32x32px with padding for 44px touch target
  - aria-label: "Share document"

**Date group headers:**
- 12px, weight 600, uppercase, letterSpacing: 0.05em, color: secondaryText
- Left padding: 16px (align with card content)
- margin-top: 32px (first group: 0), margin-bottom: 12px
- Subtle left border: 2px solid brandCoral at 20% opacity

---

### Content Zone — Grid View

2-column grid on desktop (gap: 20px), 1-column on mobile.

**Grid card:**
- Background: cardBg, border: 1px solid subtleBorder, borderRadius: 12px
- Padding: 20px
- Hover: translateY(-2px) + shadow-md + border-color rgba(233,77,53,0.2)
- Transition: all 200ms cubic-bezier(0.2, 0, 0, 1)
- Layout:
  - **Top row:** Type icon (40x40 rounded-lg) + title (16px, weight 600, 2-line clamp)
  - **Middle:** Entity tags as small pills (max 3)
  - **Bottom row** (flex, justify-between, items-center, mt-auto):
    - Relative time (13px, secondaryText)
    - Type badge (pill)
- Min-height: 160px for visual consistency
- Cursor: pointer
- Focus-visible: outline 2px solid brandCoral, outline-offset 2px

---

### Pagination Zone

Replace "Load more" with contextual pagination:

```
Showing 20 of 42 documents          [Load more]
```

- Left: "Showing X of Y documents" — 13px, secondaryText
- Right: Load more button
  - Style: secondary button (border, not filled)
  - Text: "Load more" or "Show next 20"
  - Disabled + loading spinner when fetching
- Centered, max-width matches content
- margin-top: 32px

---

### Empty State

Use the library `EmptyState` component:
- Icon: FileText (from lucide-react)
- Title: "Your library is empty"
- Description: "Intelligence documents from skills like meeting prep and company research will appear here."
- No CTA needed (documents are auto-generated by skills)

---

### Search Empty State

When search returns no results:
- Icon: Search
- Title: "No documents found"
- Description: "Try a different search term or clear filters"
- CTA: "Clear search" button that resets search + filters

---

## New Component Specifications

### 1. ViewToggle

- **Purpose:** Toggle between list and grid layout
- **Atomic level:** Atom
- **Location:** `frontend/src/components/ui/view-toggle.tsx`
- **Props:** `view: 'list' | 'grid'`, `onViewChange: (view) => void`
- **States:**
  - Default: inactive button has transparent bg, secondaryText icon
  - Active: brandCoral bg with white icon
  - Hover (inactive): bg rgba(0,0,0,0.06)
  - Focus: outline 2px solid brandCoral
  - Disabled: opacity 0.5
- **Accessibility:** role="radiogroup", each button role="radio", aria-checked, aria-label
- **CSS custom properties for dark mode:**
  - Active bg stays brandCoral
  - Inactive hover: rgba(255,255,255,0.08) in dark mode
- **Reduced motion:** No transforms, instant color changes
- **Responsive:** Same on mobile

### 2. DocumentRow (List View Item)

- **Purpose:** Compact document display for list view
- **Atomic level:** Molecule
- **Location:** `frontend/src/features/documents/components/DocumentRow.tsx`
- **Props:** `document: DocumentListItem`, `onView`, `onShare`
- **States:**
  - Default: transparent bg
  - Hover: warm tint bg + show share button + show chevron
  - Active: scale(0.99)
  - Focus-visible: outline ring
  - Loading: skeleton (2 lines + icon placeholder)
- **Accessibility:**
  - role="button" (or use <button> wrapper)
  - aria-label: "View document: {title}"
  - Share button: aria-label: "Share {title}"
  - Keyboard: Enter/Space to view, Tab to share button
- **Dark mode:** hover bg rgba(233,77,53,0.08)
- **Reduced motion:** No hover slide effects

### 3. DocumentGridCard (Grid View Item)

- **Purpose:** Richer document card for grid layout
- **Atomic level:** Molecule
- **Location:** `frontend/src/features/documents/components/DocumentGridCard.tsx`
- **Props:** `document: DocumentListItem`, `index`, `onView`, `onShare`
- **States:**
  - Default: flat card with subtle border
  - Hover: lift + shadow + border color shift
  - Active: scale(0.98)
  - Focus-visible: outline ring
  - Loading: skeleton card (160px height)
- **Accessibility:**
  - Same as DocumentRow
  - Keyboard: Enter/Space to view
- **Dark mode:** card bg var(--card-bg), hover uses elevated surface color
- **Reduced motion:** No translateY on hover, shadow only

---

## Type-Specific Styling

Each document type gets its own visual identity:

| Type | Icon | Icon Color | Badge BG | Badge Text | Icon BG Tint |
|------|------|-----------|----------|-----------|-------------|
| meeting-prep | FileText | #3B82F6 | rgba(59,130,246,0.1) | #2563EB | rgba(59,130,246,0.08) |
| company-intel | Building2 | #A855F7 | rgba(168,85,247,0.1) | #7C3AED | rgba(168,85,247,0.08) |
| account-research | Globe | #14B8A6 | rgba(20,184,166,0.1) | #0D9488 | rgba(20,184,166,0.08) |
| call-intelligence | Phone | #F97316 | rgba(249,115,22,0.1) | #EA580C | rgba(249,115,22,0.08) |
| default | FileText | var(--brand-coral) | var(--brand-tint) | var(--brand-coral) | var(--brand-tint) |

Update `utils.ts` to include these mappings.

---

## Interaction Specs

| Action | Feedback | Transition |
|--------|----------|-----------|
| Click filter tab | Active tab underline slides, content fades | 200ms ease |
| Type in search | Results filter live after 300ms debounce | Content cross-fade 200ms |
| Clear search | All results restore | Fade 200ms |
| Toggle list/grid | Layout morphs with content fade | Cross-fade 300ms |
| Hover list row | Warm bg tint + share/chevron appear | 200ms ease |
| Hover grid card | Lift + shadow | 200ms cubic-bezier(0.2, 0, 0, 1) |
| Click document | Navigate to /documents/:id | Page transition |
| Click share | Copy to clipboard + toast | Toast slide-in |
| Load more | New items stagger in (50ms between) | fadeUp 300ms |

**Reduced motion alternatives:**
- No translateY transforms
- No stagger delays
- Instant opacity changes
- Background color changes only

---

## Accessibility Requirements

1. **Search input:** aria-label="Search documents", role="search" on container
2. **Filter tabs:** Use Tabs component which provides proper ARIA
3. **View toggle:** role="radiogroup" with role="radio" buttons
4. **Document rows:** role="button", tabIndex=0, Enter/Space to activate
5. **Share buttons:** aria-label="Share {document title}"
6. **Date group headers:** Use h2 for proper heading hierarchy
7. **Skip navigation:** Already handled at app level
8. **Focus order:** Search -> Filters -> View toggle -> First document -> Load more
9. **Screen reader:** Announce "Showing X of Y documents" as live region on filter/search changes

---

## Component Library Updates

- **New:** ViewToggle (atom, `components/ui/view-toggle.tsx`)
- **New:** DocumentRow (molecule, `features/documents/components/DocumentRow.tsx`)
- **New:** DocumentGridCard (molecule, `features/documents/components/DocumentGridCard.tsx`)
- **Use existing:** EmptyState (replace inline EmptyDocumentsIllustration)
- **Use existing:** Tabs (variant="line" for filters)
- **Use existing:** InputGroup (for search with icon)
- **Remove:** DocumentCard.tsx (replaced by DocumentRow + DocumentGridCard)
- **Update:** utils.ts (add type-specific colors and expanded icon map)

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `DocumentLibrary.tsx` | **Rewrite** | New layout with search, tabs, view toggle, list/grid views |
| `DocumentCard.tsx` | **Delete** | Replaced by DocumentRow + DocumentGridCard |
| `DocumentRow.tsx` | **Create** | Compact list-view row component |
| `DocumentGridCard.tsx` | **Create** | Rich grid-view card component |
| `utils.ts` | **Update** | Type-specific colors, expanded icon map |
| `components/ui/view-toggle.tsx` | **Create** | Reusable list/grid toggle |
| `api.ts` | **No change** | API stays the same |
| `DocumentViewer.tsx` | **No change** | Detail view stays the same (separate overhaul) |

---

## Skeleton Loading States

### List View Skeleton
- 6 rows with shimmer animation
- Each row: 40x40 circle + 2 text lines (60%, 40% width) + badge placeholder + time placeholder
- Stagger delay: 50ms per row

### Grid View Skeleton
- 4 cards (2x2 grid) with shimmer
- Each card: 160px height, icon placeholder + title lines + badge + time
- Stagger delay: 80ms per card

---

## Implementation Notes for GSD

1. All CSS must use `var()` tokens from design-tokens.ts — no hardcoded hex
2. Import from component library — never rebuild
3. Search uses existing debounce pattern (300ms, see PipelineFilterBar)
4. View preference should persist in localStorage (key: "library-view-mode")
5. Filter + search state should sync with URL search params for shareable URLs
6. Type-specific colors should be defined in utils.ts as a single source of truth
7. Reduced motion: wrap all animations in `@media (prefers-reduced-motion: no-preference)`
