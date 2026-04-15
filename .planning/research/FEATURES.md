# Feature Landscape: Broker Frontend Redesign

**Domain:** Insurance broker placement workflow UI -- redesign to Alaya Demo v2 quality
**Researched:** 2026-04-15
**Source:** Alaya Demo v2 (16-beat demo at `/tmp/alaya-demo-v2/src/App.tsx`), SPEC-BROKER-REDESIGN.md, existing codebase (42 broker components)

---

## Table Stakes

Features users expect. Missing = product feels incomplete or broken relative to the demo standard.

### Foundation (Wave 0 -- blocks everything)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Fix 4 API path mismatches (solicitation edit/send, recommendation edit/send) | Currently silently 404. Emails cannot be sent, recommendations cannot be edited. | Low | `broker.ts` API file | N/A -- bug fix |
| Remove stale types (5 from BrokerProject, 6 from CarrierQuote) | Type confusion causes incorrect data binding across all broker pages | Low | `types/broker.ts` | N/A -- cleanup |
| Add missing fields to ProjectCoverage (10 fields: gap_amount, current_limit, contract_clause, source_excerpt, etc.) | Blocks gap analysis dollar amounts, clause references, and analysis view entirely | Low | `types/broker.ts`, backend schema already has them | Beat 6 |
| Update flywheelGridTheme (coral hover `rgba(233,77,53,0.03)`, no column separators) | Visual baseline. Every ag-grid in broker module uses this theme. Demo uses coral hover everywhere. | Low | `shared/grid/theme.ts` | All beats |
| Add SolicitationDraft type + useSolicitationDrafts hook | Email approval currently derives data from stale CarrierQuote fields being removed | Low | Types + hooks | Beat 9 |

### Shared Components

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| CurrencyCell renderer (right-aligned, `Mex$X,XXX,XXX` format, red `#EF4444` for gaps, green `#22C55E` for covered) | Used on 4+ pages: gap analysis, quote tracking, comparison matrix, dashboard pipeline. Demo formats all amounts this way. | Low | Shared grid renderers dir | Beats 6, 11, 14 |
| ClauseLink renderer (coral `#E94D35` text, underline on hover, click scrolls document viewer) | Links coverage rows to contract clause. Core UX pattern in the demo -- clicking "7.1" scrolls to clause 7.1 in the contract viewer. | Low | Document viewer scroll target (data-clause attribute) | Beats 4-6 |
| CarrierCell renderer (28px colored initials circle from name hash + carrier name text) | Replaces plain text carrier names. Demo uses colored circles everywhere -- Mapfre, GNP, Chubb, Zurich all get unique colors. | Low | Name hash color algorithm | Beats 7, 9, 14 |
| ToggleCell renderer (coral pill toggle, on=`#E94D35`, off=`#E5E7EB`) | Carrier include/exclude on selection page. Demo shows clean toggles per carrier. | Low | Toggle callback | Beat 7 |
| DaysCell renderer (number + "days" suffix, orange `#F97316` when > 7) | Days-in-stage on dashboard, response timing on quotes. Demo colors stale items orange. | Low | None | Beats 0, 11 |
| RunInClaudeCodeButton (dark `#121212` bg, terminal icon, copy-to-clipboard + "Copied!" toast) | Central UX paradigm -- replaces all AI trigger buttons. Used on 5+ pages. This IS the interaction model for Claude Code intelligence. | Low | Clipboard API, toast system (sonner already in project) | Beats 4, 8, 11 |
| Three-layer Airbnb shadow CSS class (`0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)`) | Visual consistency. Demo uses this shadow on every card and grid wrapper. Currently the codebase uses flat borders. | Low | CSS utility or Tailwind class | All beats |

### Dashboard (Beat 0)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| 4 KPI MetricCards above pipeline (Active Projects, Pipeline Premium `Mex$120M`, Carriers Configured, Pending Actions) | Demo opens with these. Sets professional "command center" tone. Current dashboard is just TaskList + pipeline grid. | Med | Backend: `total_premium` field in dashboard-stats response (new endpoint addition needed) | Beat 0 |
| MetricCard design: white bg, 12px radius, Airbnb shadow, 11px uppercase label, 32px bold value, 12px trend line | Demo specifies exact visual treatment. Without this, cards look generic. | Low | MetricCard component | Beat 0 |
| Pipeline table coral left-border (`3px solid #E94D35`) on action-needed rows | Visual urgency indicator. Demo highlights "Constructora del Pacifico" row with coral accent. Current grid has no row-level urgency signals. | Low | `getRowStyle` callback, `data-action-needed` attribute | Beat 0 |
| Premium column in pipeline grid | Shows business value per project. Demo has this column. Currently missing. | Low | CurrencyCell, quote premium data | Beat 0 |
| Days-in-stage column with orange > 7 days | Shows staleness at a glance. Demo shows "18d" with timing context. | Low | DaysCell renderer | Beat 0 |
| "Needs Attention" filter badge (red pill above grid, filters to action-needed rows) | Demo has this filter. Immediate focus on what matters. | Low | Grid filter state + badge button | Beat 0 |

### Gap Analysis / Coverage Tab (Beat 6)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Current Limit column | Shows what client currently has vs what contract requires. Gap analysis is meaningless without it -- "you need Mex$50M but have Mex$0" vs just "you need Mex$50M". | Low | ProjectCoverage.current_limit field (add to frontend type, already in backend) | Beat 6 |
| Gap Amount column (red `#dc2626` dollar amounts) | The entire point of gap analysis. Demo shows `Mex$50,000,000` in bold red for missing coverage, dashes for covered items. | Low | CurrencyCell with red text variant | Beat 6 |
| Clause column (coral ClauseLink -- "7.1", "8.2", "AI" for AI-discovered) | Links each coverage to its contract clause. Core traceability. Demo shows clause refs in coral, "AI" for AI-discovered requirements (Professional Liability, Environmental). | Low | ClauseLink renderer | Beat 6 |
| Section group rows ("INSURANCE COVERAGES" / "SURETY BONDS" -- uppercase, `#9CA3AF`, letter-spacing 0.08em) | Demo cleanly separates insurance and surety with styled group headers. Current `GapAnalysis.tsx` uses category arrays but renders flat. | Med | ag-grid rowGrouping or manual group header dividers | Beat 6 |
| Row coloring by gap status (missing: `rgba(239,68,68,0.02)` red tint, insufficient: `rgba(249,115,22,0.04)` orange tint) | Demo tints "No Coverage" rows. Visual scanning without reading every cell. Existing GapAnalysis has no row coloring. | Low | ag-grid `getRowStyle` callback keyed on gap_status | Beat 6 |
| Urgency banner when project starts within 30 days ("Project starts in 18 days -- June 1, 2026") | Demo shows amber accent card with urgency. Drives action. | Low | Project start_date date math | Beat 6 |

### Email Approval (Beat 9)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Full email body display (no truncation, `white-space: pre-wrap`) | Current EmailApproval.tsx truncates body content. Demo shows full formal Spanish solicitation emails. Brokers must read the full email before approving. | Low | Remove character limit, use pre-wrap | Beat 9 |
| Prominent "To:" address in card header (e.g., "suscripcion@zurich.com.mx") | Who the email goes to. Currently not shown prominently. Demo makes this a first-class header element. | Low | SolicitationDraft.sent_to_email | Beat 9 |
| Carrier identity in card header (CarrierCell with colored circle + name) | Which carrier this email targets. Demo shows `[ZM] Zurich Mexico` with colored circle. | Low | CarrierCell renderer reuse | Beat 9 |
| Separate editable subject field (`<input>` full width) and body field (`<textarea>` min-height 300px) | Current edit mode doesn't properly separate subject from body. Demo has distinct editable regions. | Low | Separate controlled inputs | Beat 9 |
| Attachments list below body (paperclip icon + file names) | Shows what files are attached to the solicitation. Currently missing entirely. Demo lists "MSA Contract.pdf, Existing Policies.pdf". | Low | Document list from project | Beat 9 |

### Carrier Selection (Beat 7)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Replace checkbox card grid with ag-grid table (Carrier, Method, Routing Rule, Include toggle) | Demo uses a clean table. Current CarrierSelection.tsx uses card grid with match score bars -- visually cluttered, scores lack clear methodology. | Med | CarrierCell, StatusBadge ("Portal" green / "Email" blue), ToggleCell renderers | Beat 7 |
| Remove match score bar entirely | Demo has no match scores. Routing rule text ("CAR > Mex$30M requires email submission") is more honest and actionable than a 78% score. | Low | Delete existing match score component | Beat 7 |
| Section headers for Insurance vs Surety carriers | Demo groups these distinctly with uppercase styled headers. | Low | ag-grid group headers or manual section dividers | Beat 7 |
| "Proceed to Submission (N carriers)" button with included count | Clear transition CTA. Demo shows count of selected carriers. Triggers draft creation for included carriers. | Low | Button + navigation + `POST /projects/{id}/draft-solicitations` | Beat 7 |

### Quote Tracking (Beats 11, 13)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Summary badges at top ("4 of 6 received" green dot, "2 pending" pulsing orange dot) | Demo shows these prominently. Instant status without scanning the list. | Low | Badge components, CSS `pulse 2s infinite` animation | Beat 11 |
| Premium column per quote (CurrencyCell) | Shows the money. Currently missing from quote rows. | Low | CurrencyCell renderer | Beat 11 |
| Type badge per quote (Insurance = coral, Surety = blue StatusBadge) | Distinguishes quote categories visually. | Low | StatusBadge | Beat 11 |
| Received timing column (days since solicited, orange via DaysCell if > 7) | Shows carrier responsiveness. "3 days" vs "14 days" matters for carrier evaluation. | Low | DaysCell renderer | Beat 11 |
| Completion card when all quotes received ("All quotes received" -- green accent, "Extract & Compare" RunInClaudeCodeButton) | Clear transition point from collecting to comparing. Demo shows this as a prominent green card at Beat 13. | Low | Conditional card render | Beat 13 |

### Comparison Matrix (Beats 12, 14, 15)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Migrate from custom HTML table to ag-grid | Current `ComparisonGrid.tsx` (115 lines) uses a plain HTML `<table>`. Rest of module uses ag-grid. Creates visual inconsistency, missing native sticky headers, no column show/hide, no pinned rows. | High | Custom ComparisonCellRenderer (two-row: premium bold 14px + limit/deductible muted 12px in one cell), `rowHeight: 64` | Beat 14 |
| Expandable coverage groups (collapsible sections with toggle headers) | Demo groups rows: "General Liability Coverage (3 rows)", "Equipment & CAR (2 rows)", "Professional & Environmental (3 rows)", "Surety Bonds (3 rows)". Expand/collapse per group. | Med | ag-grid groupRowRenderer or manual accordion pattern | Beat 14 |
| Critical exclusion alert row (red border card, full-width, alert icon) | Demo's signature UX moment: "Zurich Mexico -- Critical Exclusion: Vibration not covered without Endoso 014. This project requires earthwork." Red `2px solid rgba(239,68,68,0.4)` border, `rgba(239,68,68,0.03)` background. | Med | `has_critical_exclusion` field, conditional row rendering between coverage groups | Beat 14 |
| Recommended carrier column styling (coral `3px` left border on all cells, "BEST OPTION" badge on header, `9px bold #E94D35`) | Demo highlights Mapfre column distinctly. Visual recommendation at a glance. | Low | Column-specific styling via ag-grid cellStyle callback | Beat 14 |
| Total premium pinned bottom row (sticky at bottom of scrollable grid) | Demo shows total premium per carrier. ag-grid's `pinnedBottomRowData` is designed for exactly this. | Med | `pinnedBottomRowData` configuration, totals computation | Beat 14 |
| Partial comparison banner ("4 of 6 quotes received, waiting for: GNP, Chubb" -- amber accent) | Demo shows this at Beat 12. Prevents confusion about incomplete data. | Low | Comparison partial flag from API | Beat 12 |
| Surety comparison view (separate section or tab) | Demo dedicates Beat 15 to surety bonds: performance, quality, advance payment bonds with two carriers (Aserta, Dorama). Different column structure from insurance. | Med | Separate data source, different column layout | Beat 15 |

### Portal Submission (Beat 8)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Replace Python script display with RunInClaudeCodeButton | Current PortalSubmission.tsx shows a Python script. New paradigm: "Run `/broker:fill-portal`" button copies command to clipboard. | Med | RunInClaudeCodeButton component | Beat 8 |
| Data preview table per portal carrier (Portal Field / Value mapping) | Demo shows exactly which fields will be auto-filled before running. User verification before automation. | Med | Field map data from backend/carrier config, table layout | Beat 8 |
| Screenshot display after automation completes | Show portal screenshot for user to verify submission correctness. "Confirm Submission" / "Retry" buttons. | Med | `GET /broker/quotes/{id}/portal-screenshot` endpoint, image rendering | Beat 11 |

### Recommendation & Delivery (Beat 16)

| Feature | Why Expected | Complexity | Dependencies | Demo Ref |
|---------|-------------|------------|--------------|----------|
| Fix recommendation API paths (editRecommendation, sendRecommendation) | Currently broken -- silently 404. | Low | broker.ts one-line fixes | N/A -- bug fix |
| Package summary card (Insurance carrier + premium, Surety carrier + premium, Total) | Demo shows "Insurance: Mapfre Mex$847,875 + Surety: Aserta Mex$127,500 = Total Mex$975,375". Clear bottom-line. | Low | Comparison data, CurrencyCell | Beat 16 |
| "Draft Recommendation" RunInClaudeCodeButton when none exists | CTA to generate recommendation via Claude Code when no BrokerRecommendation record exists yet. | Low | RunInClaudeCodeButton | Beat 16 |

---

## Differentiators

Features that set the product apart. Not expected, but create signature moments.

### Document Analysis Split Pane (Beats 4-5) -- NEW TAB

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| Split-pane view: contract text (left, `flex: 1`) + extracted requirements (right, `width: 420px`) | The demo's most visually striking screen. Contract text with highlighted clauses + requirement cards side-by-side. No broker tool does this -- they show either the document OR the extracted data, never together. | High | New Analysis tab in project detail, document viewer component, requirement card component, independent scroll per pane | Beats 4-5 |
| Highlighted contract clauses (coral `3px` left border + `rgba(233,77,53,0.08)` for insurance clauses 7.x, blue for surety clauses 8.x) with `data-clause` attributes | Clauses light up after analysis. Clicking a requirement card scrolls the left pane to the matching clause via `scrollIntoView`. Bidirectional context linking. | Med | data-clause attributes on clause sections, scrollIntoView smooth behavior, CSS clause highlighting | Beats 4-5 |
| Requirement cards with confidence progress bars, "AI" sparkle badges, "Critical Finding" badges | Each extracted requirement shows: confidence (coral progress bar, e.g. "87%"), source type ("AI" badge with sparkle for skill-extracted), and critical findings (for requirements found in non-standard clause locations like clause 14.3.2). Rich metadata per coverage. | Med | ProjectCoverage fields: confidence (0.0-1.0), source ("ai"/"manual"), ai_critical_finding boolean | Beats 4-5 |
| Shimmer loading animation during analysis (coral gradient sweep: `#FFF5F3` -> `rgba(233,77,53,0.15)` -> `#FFF5F3`) | Premium loading state while Claude Code parses contract. React Query polls every 10s until `analysis_status` transitions from "running" to "completed". Cards then appear with staggered fadeUp reveal (60ms delay per card). | Low | CSS shimmer keyframe, React Query `refetchInterval` conditional on analysis_status | Beats 4-5 |
| Document type tabs within viewer ("MSA Contract" = coral active, "Surety Requirements" = blue active) | Switch between document types. Each tab renders different contract content with its own highlighted clauses. | Low | Tab state, coverages filtered by category (insurance/surety) | Beats 4-5 |
| Serif font for contract text (Georgia/Times New Roman on `#FAFAF8` cream background, `line-height: 1.8`) | Contracts feel legible and authentic in serif. Distinguishes legal text from UI chrome. Subtle but professional. | Low | CSS font-family on document viewer only | Beats 4-5 |

### AI Insight Card

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| AI recommendation summary below comparison matrix (coral `4px` left border, sparkle icon, natural language) | "Mapfre lowest at Mex$847,000 vs average Mex$941,500. Full coverage including Endoso 014. No critical exclusions." Synthesized judgment, not just data. | Low | BrokerRecommendation.body field, fallback: generate template text from is_best_price/is_recommended flags | Beat 14 |

### Interactive/PDF Toggle on Comparison Matrix

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| PDF Preview mode (print-friendly static table with company letterhead, signature line, reference number) | Toggle between interactive ag-grid and PDF-ready layout. Demo shows a formal "Cuadro Comparativo" with Alaya letterhead, date, reference number, and signature line. Enables "save as PDF" for client delivery. | Med | Static HTML table renderer (no ag-grid), letterhead component, print CSS, `#525659` dark background preview wrapper | Beat 14 |

### "Generated by Claude Code" Badge

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| Coral badge at 10% opacity with sparkle icon on AI-generated content (emails, requirements, recommendations) | Transparency about what was AI-generated vs manual. Trust-building with the broker. "This email was drafted by AI" is both honest and a feature showcase. | Low | source field check (`source === 'ai'` or `auto_generated === true`), reusable badge component | Beats 5, 9, 14 |

### Quote Detail Expansion

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| Expandable inline detail panel per quote (premium breakdown: net + expedition + IVA = total, deductibles per coverage, endorsement green pills, exclusion red pills with alert icon) | Deep-dive without page navigation. Endorsement pills (Endoso 014, CG 20 10, Waiver of Subrogation) show coverage quality at a glance. Critical exclusions as red pills immediately flag problems. | Med | CarrierQuote detail fields (net_premium, expedition_costs, vat_amount, endorsements[], exclusions[]), inline expansion or modal | Beat 11 |

### Left Navigation Phase Stepper

| Feature | Value Proposition | Complexity | Dependencies | Demo Ref |
|---------|-------------------|------------|--------------|----------|
| Phase-aware left sidebar (200px, `#FAFAFA` bg) showing workflow progress: green checkmark = done, coral square = active, gray circle = pending | Demo's `LumifNav` component. 7 phases: Client Profile, Document Analysis, Gap Assessment, Carrier Selection, Submission, Quotes & Comparison, Send to Client. Orients broker in complex workflow. Clickable to jump between phases. | Med | Project status-to-phase mapping, sidebar layout within project detail, phase click navigation | All Lumif beats (3-16) |

---

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Backend AI engines as primary path | SPEC-BROKER-REDESIGN shifts ALL AI to Claude Code skills. Backend engines (`contract_analyzer`, `quote_extractor`, `solicitation_drafter`, `recommendation_drafter`, `followup_drafter`) become API-triggered fallbacks only. Building them as primary duplicates intelligence. | Claude Code skills are primary. Backend engines stay as-is. Frontend shows "Run in Claude Code" buttons, not "Analyze" buttons. |
| Match score bars on carrier selection | Arbitrary numeric scores (e.g., "78% match") without clear methodology. Demo removed them entirely. Routing rule text ("CAR > Mex$30M requires email") is more honest and actionable. | Show routing rule text as a table column and portal/email method badge. Simple, clear, no magic numbers. |
| Character truncation on email bodies | Current EmailApproval truncates body content. Insurance solicitations are formal business communications -- brokers must read the full text before approving. Demo shows full content. | Full body with `white-space: pre-wrap`, vertical scroll if extremely long. No character limit. |
| Custom HTML table for comparison matrix | Current `ComparisonGrid.tsx` uses a plain `<table>`. Every other table in the broker module uses ag-grid with `flywheelGridTheme`. Creates visual inconsistency, duplicates scroll logic, misses native features (column show/hide, pinned rows, sticky headers). | Use ag-grid with custom `ComparisonCellRenderer` (two-row cells for premium + limit/deductible), `pinnedBottomRowData` for totals, `groupRowRenderer` for expandable groups. |
| Inline AI trigger buttons (`POST /projects/{id}/analyze`) | Old paradigm where frontend triggers backend AI jobs. New paradigm: "Run in Claude Code" copies command to clipboard, user pastes into Claude Code terminal. Backend AI endpoints remain as API but are not the primary UX. | `RunInClaudeCodeButton` component everywhere. One consistent interaction pattern. |
| Gmail/email view in broker module | Demo shows Gmail as a separate browser tab (it's a demo concept). The product already has a separate email module (`features/email/`). Don't duplicate email UI inside broker. | Broker module handles placement workflow only. Email module handles email. Broker project can link to email threads via `broker_project_emails`. |
| Client portal view | Demo implies clients see a portal. Out of scope for broker redesign. Adds authentication, permission, and UX complexity for a separate persona. | Broker-facing workflow only. Client gets PDF export via comparison matrix PDF preview mode + recommendation email. |
| Framer Motion heavy animations | Demo uses Framer Motion for every transition (it's a 260KB single-file demo app). Production needs lightweight CSS animations for performance and bundle size. Demo's `motion.div` + `AnimatePresence` on every row is excessive for production. | CSS `@keyframes` for fadeUp, shimmer, pulse, highlightSweep. Reserve Framer Motion only if already used in the app for page-level transitions. |
| Real carrier logo SVGs now | Premature polish. Demo has custom SVGs for Mapfre, GNP, Chubb, Zurich but the product needs to support arbitrary carriers. | CarrierCell with colored initials circle (color from name hash). Add real logos as optional image overrides in a future polish pass. |
| Full i18n / Spanish-first UI | Demo is bilingual (ES/EN toggle) because it demos for a Mexican brokerage. The product UI is English-first. | English UI. Currency formatting handles MXN. Insurance domain terms (Endoso, fianza, prima) appear in DATA (entered by broker or extracted by AI), not in UI chrome labels. |
| Step indicator redesign | Current `StepIndicator.tsx` exists. Updating from 5 to 6 steps is trivial. A full redesign (like demo's left nav) is separate work. | Update step count from 5 to 6 (add Analysis tab). Visual treatment can match existing style. Left nav is a differentiator, not table stakes. |

---

## Feature Dependencies

```
Wave 0: Foundation (blocks everything)
  |
  +-- Fix 4 API paths -----------> Email send/edit, Recommendation send/edit work
  +-- Fix types ------------------> All components render correct fields
  +-- Grid theme update ----------> All grids get coral hover, no col separators
  +-- 7 shared renderers ---------> CurrencyCell, ClauseLink, CarrierCell, ToggleCell,
  |                                 DaysCell, RunInClaudeCodeButton, Airbnb shadow CSS
  +-- Batch coverage endpoint ----> parse-contract skill can create 8+ records
  +-- Dashboard stats premium ----> MetricCards show real data

Wave 1: Skills Infrastructure (parallel with frontend)
  |
  +-- Skill directory structure --> All skills need ~/.claude/skills/broker/
  +-- Hook scripts --------------> Auto gap-analysis after coverage write,
                                    auto comparison after quote write

Wave 2: High-Impact Frontend (depends on Wave 0)
  |
  +-- Dashboard MetricCards + highlighted rows (depends: CurrencyCell, DaysCell)
  +-- Gap Analysis upgrades (depends: CurrencyCell, ClauseLink, types fix)
  +-- Comparison Matrix overhaul (depends: CurrencyCell, CarrierCell, grid theme)

Wave 3: Remaining Frontend (depends on Wave 0, benefits from Wave 1 skills)
  |
  +-- Document Analysis NEW tab (depends: types fix for ProjectCoverage fields)
  +-- Email Approval (depends: SolicitationDraft type, API path fixes)
  +-- Quote Tracking (depends: CurrencyCell, DaysCell, RunInClaudeCodeButton)
  +-- Carrier Selection (depends: CarrierCell, ToggleCell)
  +-- Portal Submission (depends: RunInClaudeCodeButton)
  +-- Recommendation (depends: API path fixes, CurrencyCell)

Wave 4: Animation & Polish (depends on Waves 2-3 being built)
  |
  +-- CSS animations: fadeUp, shimmer, pulse, greenFlash, highlightSweep
  +-- Staggered requirement card reveals in Analysis tab
  +-- Completion state animations
```

**Critical path insight:** RunInClaudeCodeButton and CurrencyCell are used by 5+ downstream features. They MUST land in Wave 0 shared components, not in Wave 2/3 page work.

---

## MVP Recommendation

### Prioritize (maximum demo-quality impact per day):

1. **Wave 0: Foundation** -- All 8 items. Without these, downstream work hits type errors, visual inconsistency, and 404 API failures. Estimated: 1-2 days. Non-negotiable.

2. **Dashboard MetricCards + pipeline upgrades** -- First screen users see. 4 cards + premium column + days column + coral left-border on action rows transforms dashboard from generic "data dump" to professional "command center." Estimated: half day.

3. **Gap Analysis upgrades** -- Add current_limit, gap_amount (red), clause links, row coloring, section groups, urgency banner. This is the most-used daily screen for active projects. Estimated: 1 day.

4. **Comparison Matrix overhaul** -- Expandable groups, critical exclusion alerts, recommended column styling, AI insight card, pinned total row, Interactive/PDF toggle, partial comparison banner. Most complex but highest-impact screen -- this is what clients see. Estimated: 2-3 days.

5. **Email Approval full content** -- Quick win. Remove truncation, add carrier identity header, separate subject field, attachments list, AI badge. Estimated: half day.

### Defer:

- **Document Analysis split pane (NEW tab)**: Highest differentiator value but highest complexity. Requires entirely new component tree (document viewer, requirement cards, scroll sync, shimmer loading). Schedule for Wave 3 -- it's a new tab, not a fix to existing functionality, so nothing is broken without it. The data still renders on the Coverage tab.

- **Portal Submission redesign**: Depends on Claude Code skills being built and working. The current Python script display functions as a placeholder. Redesign when skills are ready.

- **Left Navigation Phase Stepper**: Nice-to-have differentiator. Current step indicator works. Phase stepper is additive polish.

- **Animation polish (Wave 4)**: Ship functional UX first, animate second. CSS keyframes can be added incrementally.

- **PDF Preview mode on comparison**: Useful for client presentations but not blocking daily workflow. Can ship after comparison matrix core is done.

---

## Sources

- Alaya Demo v2: `/tmp/alaya-demo-v2/src/App.tsx` -- 3816 lines, 16-beat interactive demo, single-file React + Framer Motion
- Redesign spec: `.planning/SPEC-BROKER-REDESIGN.md` -- comprehensive per-page specification with CSS values, component props, API mappings
- Existing broker components: `frontend/src/features/broker/` -- 42 `.tsx` files across components/, pages/, comparison/
- Existing `ComparisonGrid.tsx` -- 115 lines, custom HTML table (needs ag-grid migration)
- Existing `GapAnalysis.tsx` -- 120 lines, HTML table with basic status badges (missing gap_amount, current_limit, clause columns)
- Existing `BrokerDashboard.tsx` -- 43 lines, TaskList + ProjectPipelineGrid (no MetricCards)
- Existing `EmailApproval.tsx` -- truncated body display (needs full content)
- Demo fixtures: `/tmp/alaya-demo-v2/src/fixtures.ts` -- insurance/surety data structures, comparison matrix grouped format, carrier quotes with premium breakdowns
