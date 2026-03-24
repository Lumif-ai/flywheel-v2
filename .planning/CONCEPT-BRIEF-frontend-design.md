# Concept Brief: Frontend Design Language & UX Overhaul

> Generated: 2026-03-24
> Mode: Deep (3 rounds)
> Rounds: 3
> Active Advisors: 10 core + Schoger (visual design), Norman (interaction), Frost (component systems), Tufte (information design), Drasner (animation)
> Artifacts Ingested: All frontend source code (40+ components), design-guidelines.md, brand tokens, current onboarding flow, briefing page, sidebar, mobile nav

## Problem Statement

Flywheel v2 has a functionally complete frontend with proper architecture (React + Vite + Tailwind + shadcn/ui, responsive layouts, SSE streaming, state management). But the visual execution is rated 0.5/10 by the founder. The gap: a warm, intelligent brand system exists on paper (`#E94D35` coral, Inter font, gradient CTAs, generous whitespace) but is completely absent from the implementation. Components are uniformly flat, cold, and generic. There is no visual identity, no animation language, no card type differentiation, and no design system enforcement.

The target emotional response: **calm precision + effortless intelligence** — the product feels like it knows what it's doing and never wastes your time. Think Linear's calm confidence meets Granola's effortless intelligence.

**Sharpened from brainstorm:** This is not a reskin. It's the implementation of a design language that makes compounding intelligence VISIBLE. Every card, every animation, every layout decision should communicate: "this product is getting smarter."

## Target User

Small startup founding teams (2-10 people). Zero patience, infinite ambition. Won't read instructions. Need to see magic in the first 60 seconds. Expands to literally anyone — the product compounds knowledge, not restricted to a domain.

## Design Language: Calm Precision

### Color System

| Token | Value | Usage Rule |
|-------|-------|-----------|
| Page background | `#F9FAFB` | Base |
| Card background | `#FFFFFF` | Cards, modals, inputs |
| Heading text | `#121212` | Page titles, card titles |
| Body text | `#374151` | Paragraphs, descriptions |
| Secondary text | `#6B7280` | Captions, metadata, timestamps |
| Border | `rgba(229,231,235,0.6)` | Cards, dividers (subtle) |
| Brand coral | `#E94D35` | ONE primary CTA per screen, active nav, progress |
| Brand gradient | `#E94D35 → #D4432E` | Primary button fill |
| Brand tint | `rgba(233,77,53,0.04)` | Alternating section backgrounds for warmth |
| Brand light | `rgba(233,77,53,0.1)` | Badge backgrounds, selected states |
| Success | `#22C55E` | Completed items, health indicators |
| Warning | `#F59E0B` | Attention needed, stale data |
| Error | `#EF4444` | Failures, destructive actions |

**Rule:** Coral appears in exactly ONE place per viewport — the primary action. Everything else is grayscale + warm tints. This creates calm with a clear focal point.

### Typography

| Level | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| Page title | 28px | Semibold (600) | 1.2 | One per page |
| Section title | 18px | Medium (500) | 1.4 | Section headers within pages |
| Body | 15px | Regular (400) | 1.6 | All body text, card content |
| Caption | 13px | Regular (400) | 1.4 | Metadata, timestamps, labels |

**Rule:** No other sizes. Consistency creates calm. Font: Inter everywhere.

### Spacing (8px Grid)

| Context | Value | Usage |
|---------|-------|-------|
| Section gap | 48px | Between major sections on a page |
| Card padding | 24px | Internal padding of all cards |
| Element gap | 16px | Between elements within a card |
| Tight gap | 8px | Between label and input, badge and text |
| Page padding | 24px (mobile) / 48px (desktop) | Page-level horizontal padding |
| Max content width | 720px (reading) / 1120px (grid) | Content containers |

### Cards

```
Base: bg-white, border border-gray-200/60, rounded-xl, shadow-sm
Hover: shadow-md + translateY(-1px), transition 200ms ease-out

Type differentiation via left border (4px):
- Action needed: border-l-coral (#E94D35)
- Complete: border-l-green (#22C55E)
- Warning/stale: border-l-amber (#F59E0B)
- Informational: no left border
```

### Buttons

```
Primary: bg-gradient-to-r from-[#E94D35] to-[#D4432E], text-white, rounded-lg
         hover: brightness-110, active: brightness-95, transition 200ms
Secondary: bg-gray-100, text-gray-700, hover bg-gray-200, rounded-lg
Ghost: transparent, hover bg-gray-50, rounded-lg
```

### Animation Language

```
Duration: 200ms (all interactions)
Easing: ease-out (all)
Content enter: translateY(12px) + opacity(0) → translateY(0) + opacity(1)
Stagger: 50ms between siblings
Skeleton: shimmer animation (not spinners)
Card hover: translateY(-1px) + shadow-md
Page transition: cross-fade 150ms
Long operations only: spinner (Loader2 animate-spin)
```

**Onboarding gets progressive reveal** — same visual language, but content animates in (cascading categories, building briefing sections). Workspace is the same design, content is static. Energy comes from motion during first experience, then settles into calm.

## Revised Onboarding Flow

### 5 Moments (Not Steps)

Users don't see step numbers. They see things happening.

```
1. ARRIVE
   ┌──────────────────────────────────┐
   │                                  │
   │     Paste your company URL       │
   │     ┌─────────────────────┐      │
   │     │ https://...         │ [→]  │
   │     └─────────────────────┘      │
   │                                  │
   │     Nothing else on screen.      │
   │     Clean. Confident. One CTA.   │
   └──────────────────────────────────┘

2. DISCOVER
   ┌──────────────────────────────────┐
   │  Intelligence cascades in...      │
   │                                  │
   │  🏢 Company  ░░░░░░ 3 items     │
   │  📦 Products ░░░░ 4 items       │
   │  👤 Customers ░░░ 3 items       │
   │  📊 Market   ░░░░░ 5 items      │
   │                                  │
   │  Items animate in with stagger.  │
   │  User watches their company      │
   │  being understood. ~30 seconds.  │
   └──────────────────────────────────┘

3. ALIGN
   ┌──────────────────────────────────┐
   │                                  │
   │  What's top of mind for your     │
   │  team right now?                 │
   │  ┌─────────────────────────┐     │
   │  │ Hiring engineers and    │     │
   │  │ closing Series A...     │     │
   │  └─────────────────────────┘     │
   │                    [Continue →]  │
   │                                  │
   │  One question. Free text.        │
   │  System auto-creates focus       │
   │  areas from answer + crawl data. │
   │                                  │
   │  → "Created: Hiring, Fundraising,│
   │     Competitive Intel"           │
   └──────────────────────────────────┘

4. EXPERIENCE
   ┌──────────────────────────────────┐
   │                                  │
   │  Prepare for your next meeting   │
   │  ┌─────────────────────────┐     │
   │  │ LinkedIn URL            │     │
   │  └─────────────────────────┘     │
   │  ┌─────────────────────────┐     │
   │  │ Brief agenda (optional) │     │
   │  └─────────────────────────┘     │
   │              [Prepare briefing →]│
   │                                  │
   │  → Briefing builds section by    │
   │    section (progressive reveal)  │
   └──────────────────────────────────┘

5. LAND
   ┌──────────────────────────────────┐
   │                                  │
   │  Your first briefing is ready.   │
   │                                  │
   │  ┌──────────────────────────┐    │
   │  │  [Full briefing display] │    │
   │  │  Sections revealed       │    │
   │  │  sequentially            │    │
   │  └──────────────────────────┘    │
   │                                  │
   │  This is your first document.    │
   │  Every meeting, every contact,   │
   │  smarter over time.              │
   │                                  │
   │         [Enter workspace →]      │
   └──────────────────────────────────┘
```

### Key UX Decisions

| Decision | Direction | Reasoning |
|----------|-----------|-----------|
| Rename streams → focus areas | Yes | Matches founder mental model ("I'm focused on hiring") and data model (Focus table) |
| Remove manual stream creation | Yes — auto-create from one question + crawl data | Effortless > explicit. Founders don't want to organize on day one. |
| Progress indicator | Subtle dot progression (current) is fine | Don't label steps — let things happen |
| Skip links | Keep but de-emphasize | Founding teams are impatient, let them skip |

## Document Library Design

### Timeline Feed (Not File Grid)

**Tufte's direction:** The library is a reverse-chronological intelligence feed, not a file manager.

```
┌──────────────────────────────────────────────────┐
│  Documents                          [Search] [Filter▾]  │
│                                                          │
│  TODAY                                                   │
│  ┌────────────────────────────────────────────────┐     │
│  │ 📋 Meeting Prep: Cheok Yen Kwan               │     │
│  │    PETRONAS · Discovery call · 2 min ago       │     │
│  │    "GM Marketing Strategy, 15yr FMCG exp..."   │     │
│  │                                    [Share] [→] │     │
│  └────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────┐     │
│  │ 🏢 Company Intel: Moving Walls                 │     │
│  │    OOH Advertising · 5 pages crawled · 1hr ago │     │
│  │    "Connected media platform, 47 insights..."  │     │
│  │                                    [Share] [→] │     │
│  └────────────────────────────────────────────────┘     │
│                                                          │
│  YESTERDAY                                               │
│  ┌────────────────────────────────────────────────┐     │
│  │ 📋 Meeting Prep: Sarah Chen                    │     │
│  │    Sequoia · Partner meeting · shared with 2   │     │
│  │    "Early-stage partner, climate tech focus..." │     │
│  │                                    [Share] [→] │     │
│  └────────────────────────────────────────────────┘     │
│                                                          │
│  THIS WEEK (3 more)                                      │
└──────────────────────────────────────────────────────────┘
```

**Filter options:** All | Meeting Preps | Company Intel | (future types)
**Search:** Full-text across document content, contacts, companies
**Each card shows:** Type icon, title, key entities, time, preview, share status

### Document Viewer

Full-width reader layout (max-width 720px centered). Rendered HTML with brand typography. Share button generates a public link. Export dropdown (future: PDF, DOCX).

### Share Flow

1. User clicks Share → generates `share_token`
2. URL: `app.lumif.ai/d/{share_token}`
3. Shared view: read-only, branded, no auth required
4. Shows: "Prepared by [user] using Lumif.ai" at bottom

## Workspace Home (Briefing Page)

### Revised Layout

```
┌──────────────────────────────────────────────────┐
│  Good morning, Sharan.                    Mar 24 │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ 🧠 Intelligence Health                      │ │
│  │ ██████████████████░░░░  73%                 │ │
│  │ 47 entries · 12 contacts · 3 focus areas    │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  YOUR FOCUS AREAS                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Hiring   │ │ Series A │ │ Product  │        │
│  │ ██████░░ │ │ ████░░░░ │ │ ██░░░░░░ │        │
│  │ 12 items │ │ 8 items  │ │ 3 items  │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                   │
│  RECENT DOCUMENTS                                 │
│  ┌─────────────────────────────────────────────┐ │
│  │ 📋 Meeting Prep: Cheok Yen Kwan  · 2hr ago │ │
│  │ 🏢 Company Intel: Moving Walls   · today   │ │
│  │ 📋 Meeting Prep: Sarah Chen      · yesterday│ │
│  │                            View all docs →  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  SUGGESTED ACTIONS                                │
│  ┌─────────────────────────────────────────────┐ │
│  │ ⚡ Prep for tomorrow's call with James Lee  │ │
│  │ 📊 3 competitors have new funding rounds    │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

## Key Decisions Made

| Decision | Chosen Direction | Reasoning | Advisory Influence |
|----------|-----------------|-----------|-------------------|
| Emotional tone | Calm precision + effortless intelligence | Matches founding team mental model: confident, not flashy | Ive, Schoger |
| Animation approach | One visual language, progressive reveal in onboarding only | Energy from motion, not different styling. Seamless transition to calm workspace | Tufte (synthesis) |
| Onboarding steps | 5 moments: Arrive → Discover → Align → Experience → Land | Founding teams need magic in 60s. Remove friction, show value. | Norman, PG, Chesky |
| Stream → Focus Area | Rename throughout | Matches how founders think ("focused on hiring") and data model | Norman, user decision |
| Focus area creation | Auto-create from one question + crawl data | Effortless > explicit. Don't make users organize before seeing value. | PG, Rams |
| Color application | Coral accent on ONE primary CTA per screen, grayscale everything else | Creates calm with clear focal point | Schoger, Ive |
| Card differentiation | Left border accent by type (coral/green/amber/none) | Glanceable type identification without visual noise | Frost |
| Document library | Timeline feed, not file grid | Intelligence is chronological. Users think "when" not "where" | Tufte |
| Typography | 4 sizes only (28/18/15/13) | Consistency creates calm. No visual chaos. | Schoger |
| Spacing | Strict 8px grid (48/24/16/8) | Generous whitespace = perceived quality | Schoger |

## Tensions Surfaced

### Tension 1: Remove stream creation vs keep it
- **Rams:** Remove. Three steps, not four. Show value first.
- **Frost:** Streams are core. Onboarding is the only guaranteed attention.
- **Resolution:** Auto-create from one question. User sees organization without effort.
- **User's reasoning:** "We need input on what matters to them. If we take this then we can auto-create."

### Tension 2: Warm coral vs calm precision
- **Schoger:** Use coral boldly (gradients, icons, accents)
- **Ive:** Restraint. One accent per screen.
- **Resolution:** Ive wins. Coral is focal point, not decoration. Warmth comes from tints and spacing, not color volume.

### Tension 3: Energetic onboarding vs calm consistency
- **Schoger:** Two emotional modes (energetic onboarding, calm workspace)
- **Ive:** One mode everywhere for trust
- **Resolution (Tufte):** One visual language. Onboarding gets progressive reveal animation. Workspace is same design, static. Energy from motion, not from different styling.

## Open Questions

- [ ] Focus area auto-creation — what LLM prompt maps "hiring engineers and closing Series A" to focus area names?
- [ ] Document viewer — inline in workspace or dedicated route?
- [ ] Share page branding — how much product info on shared doc page?
- [ ] Mobile-first or desktop-first for the design pass?
- [ ] Dark mode — design now or defer?
- [ ] Accessibility audit — WCAG AA compliance level target?

## Implementation Scope

This concept brief feeds into **Phase 43: Document Library & Frontend Experience**:

### Backend (from documents concept brief)
1. Alembic migration for `documents` table
2. Supabase Storage bucket setup
3. Skill executor integration (write documents after each run)
4. API endpoints: documents CRUD + share

### Frontend
5. Design token implementation (Tailwind config + CSS variables)
6. Component library polish (buttons, cards, inputs, badges per design language)
7. Onboarding flow rewrite (5 moments, focus area auto-creation)
8. Document library page (timeline feed + search/filter)
9. Document viewer (full-width reader + share flow)
10. Workspace home redesign (intelligence health, focus areas, recent docs, suggestions)
11. Sidebar polish (logo, focus areas instead of streams, visual hierarchy)
12. Animation system (fadeSlideUp, stagger, skeleton shimmer)

## Recommendation

**Proceed to `/gsd:plan-phase 43`.** The concept briefs (documents architecture + frontend design) provide clear direction. Estimated: 5-6 plans across backend and frontend work.

## Artifacts Referenced

- Frontend source code: 40+ components in `/Users/sharan/Projects/flywheel-v2/frontend/src/`
- Design guidelines: `~/.claude/design-guidelines.md`
- Documents architecture brief: `.planning/CONCEPT-BRIEF-documents-architecture.md`
- Advisor files: Schoger, Norman, Frost, Tufte, Drasner + 10 core advisors
