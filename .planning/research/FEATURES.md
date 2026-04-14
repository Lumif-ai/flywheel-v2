# Feature Landscape — Broker Frontend MVP

**Domain:** Insurance broker comparison tools, dashboard task management, project workflow visualization
**Researched:** 2026-04-14
**Context:** Subsequent milestone building frontend UI on existing complete backend (28 endpoints, 6 tables, 7 AI engines, 17 working components)

## Table Stakes

Features users expect from any broker placement tool. Missing = broker goes back to Excel.

| Feature | Why Expected | Complexity | Existing Code | Notes |
|---------|--------------|------------|---------------|-------|
| Side-by-side quote comparison matrix | Every broker compares quotes in a spreadsheet. Rows = coverage lines, columns = carriers. This is the universal mental model. Without it, the tool has no value proposition. | Med | `ComparisonMatrix.tsx` exists with basic HTML table, `QuoteCell` renderer, color-coded cells, critical exclusion badges. Backend `quote_comparator` engine returns structured comparison data. | Current implementation is functional but lacks: frozen columns, two-row cell layout, insurance/surety tabs, horizontal scroll for 5+ carriers. Needs rebuild with sticky headers and proper cell structure. |
| Coverage gap and exclusion visibility | Brokers carry E&O liability. Missing an exclusion that conflicts with a contract requirement is a career-ending mistake. Red flags must be unmissable. | Low | `GapAnalysis.tsx` exists with red/yellow/green color mapping. `ComparisonMatrix.tsx` has critical exclusion badges. Backend `gap_detector` engine produces gap data. | Existing gap analysis works. New requirement: critical exclusion alerts box ABOVE the matrix with contract-clause-vs-quote citations. This is the single most important safety feature. |
| Excel export of comparison | Brokers send comparison to clients as Excel. Not PDF, not email — .xlsx with two sheets (Insurance + Surety), formatted cells, color coding. This is the deliverable. | Med | No Excel export exists. ag-grid Enterprise (which has built-in Excel export) is NOT installed — only Community edition. Backend has no Excel endpoint. | Must use backend-generated xlsx (xlsxwriter or openpyxl — both available system-wide). Cannot rely on ag-grid Enterprise export. Backend endpoint returns formatted .xlsx binary. |
| Task list ordered by urgency | Broker opens app 2x/day. Needs to know: what requires my attention, in what order? Not KPI cards (current state) — action items. "Review this extraction", "Approve these solicitations", "Export this comparison". | Med | `BrokerDashboard.tsx` exists with KPI cards + basic project table. No task list component. No dashboard aggregation endpoint for gate counts + tasks. | Complete redesign of dashboard. Replace KPI cards with urgency-ordered task list. Each task: project name, what happened, days waiting, one action button. Backend needs aggregation endpoint. |
| Project status tracking | With 10-50 active projects, broker needs to see where each one stands at a glance. Status must be scannable without clicking into each project. | Low | `ProjectTable.tsx` exists as HTML table. `StatusBadge.tsx` exists with status colors. | Current table works but is basic HTML. Needs: sort, filter by status chips, search by name/client. ag-grid adoption gives this for free. |
| Carrier selection with match ranking | Broker needs to see which carriers are best-matched for each project's coverage needs, ranked by overlap. Manually figuring this out across 10+ carriers is the old way. | Low | `CarrierSelection.tsx` exists. Backend `carrier_matching` engine ranks by coverage overlap. | Existing component works. Needs refinement: show routing method (portal vs email), pre-select top matches. |
| Solicitation email review and approval | Broker must review AI-drafted solicitation emails before they go out. Professional reputation is at stake. But they should NOT write from scratch. | Low | `SolicitationPanel.tsx` and `EmailApproval.tsx` exist. Backend `solicitation_drafter` engine generates carrier-specific emails. | Existing components work. Gate 2 pattern (review + approve) is functional. Polish: edit mode toggle for email body, "Send All" button. |
| Insurance vs Surety separation | Construction projects always require BOTH insurance policies AND surety bonds (fianzas). These are fundamentally different products quoted by different carriers. Mixing them in one table is confusing. | Med | Current `ComparisonMatrix.tsx` has no tab separation. Backend data includes `category` field on coverages. | Must implement tabbed comparison: "Insurance (N quotes)" and "Surety Bonds (N quotes)". Filter data by category. Excel export produces two sheets. This is domain-critical for Mexico construction. |

## Differentiators

Features that separate this from "just another spreadsheet" and make a broker choose this tool.

| Feature | Value Proposition | Complexity | Existing Code | Notes |
|---------|-------------------|------------|---------------|-------|
| Two-row cell layout in comparison matrix | Premium bold on top, limit + deductible muted below. Packs 3 data points into one cell without clutter. Excel comparison spreadsheets do this — the tool should match. No broker tool does this as elegantly in a web UI. | Med | Current `QuoteCell` component shows premium, deductible, and limit as separate stacked lines. Close but not the spec'd layout (premium top, "Limit: $1M . Ded: $10K" combined bottom). | Implement as spec'd: top row `text-sm font-semibold` premium, bottom row `text-xs text-muted-foreground` combined limit + deductible. Min 140px column width. |
| "Show Differences Only" toggle | Default ON. Hides rows where all carriers are within 15% on premium AND all limits meet requirements AND no exclusion differences. Broker sees ONLY the rows requiring judgment. Cuts noise by 40-60% on typical 15-coverage projects. | Med | Not implemented. Backend comparison data includes all required fields to compute differences. | Frontend computation: for each row, check premium variance, limit adequacy, exclusion matches. Show "N matching rows hidden — Show all" link. This is Tufte-inspired: remove everything that doesn't inform a decision. |
| Critical exclusion alert box with citations | Above the matrix: "Zurich EXCLUDES vibration damage — Contract clause 9.1 REQUIRES this coverage (Quote page 12, Exclusion 4.2 vs Contract 9.1)". Cross-references quote text against contract text. No other broker tool does AI-powered exclusion-to-contract-clause mapping. | Low | Backend `gap_detector` and `quote_comparator` produce critical exclusion data with `critical_exclusion_detail`. Alert box is new UI, data exists. | High-impact, low-effort feature. Render as prominent warning box above matrix tabs. Each alert: carrier name + what's excluded + contract clause reference + source citations. |
| "Highlight Best Values" toggle | Off by default. When ON: green text on lowest premium per row, blue text on highest limit per row. Tufte principle: safety colors (red/amber) always visible; competitive colors (green/blue) opt-in. Broker focuses on gaps first, pricing second. | Low | Current `QuoteCell` has `is_best_price` and `is_best_coverage` badges. | Refactor from badges to text color styling. Add toggle control. When off, no green/blue — only red/amber safety colors. |
| Persistent gate strip | Visible on every broker page: `Review: 3 | Approve: 1 | Export: 2`. Clickable counts navigate to oldest pending project. Eliminates dashboard round-trips. Broker always knows their queue depth. | Low | Not implemented. No gate count endpoint. | New component rendered in broker layout wrapper. Backend endpoint returns counts per gate. Updates on navigation (React Query cache). This is the primary awareness mechanism. |
| Horizontal step indicator on project detail | Shows: Overview > Coverage > Carriers > Quotes > Compare with status dots (grey/amber/green). At a glance: where is this project in its lifecycle? Replaces the current vertical scroll-through-everything layout. | Med | `BrokerProjectDetail.tsx` currently renders all sections vertically with status-based conditional visibility. No tabs, no step indicator. | Redesign to tabbed layout with step indicator above tabs. Each step maps to a tab. Status dot computed from project data (e.g., Coverage tab green when coverages extracted AND approved). |
| Carrier selection checkboxes in matrix headers | Sticky checkboxes in column headers let broker select which carriers to include in Excel export. Deselect a carrier = column disappears from export. Useful when 1 of 5 carriers is clearly non-competitive. | Low | Not implemented. | Add checkbox to each carrier column header. Maintain selection state. Pass to Excel export. Sticky positioning during horizontal scroll. |
| Total premium row | Sticky at bottom during vertical scroll. Sums all coverage premiums per carrier. The bottom-line number brokers and clients care about most. | Low | Not implemented. Backend comparison data could include totals. | Compute on frontend from cell data. Sticky positioning. Bold formatting. Include in Excel export. |

## Anti-Features

Features to explicitly NOT build. Each was considered and rejected with rationale.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Kanban board for project pipeline | Brokers manage 10-50 projects. Kanban is visual sugar for 5-10 items. At 30+ projects, a sortable/filterable table is 3x faster to scan. The spec explicitly calls this out. | ag-grid table with status filter chips. Sort by days-in-stage to surface stuck projects. |
| In-browser PDF viewer for quotes | Scope explosion. PDF.js is complex, and brokers already have PDF viewers. The value is in the EXTRACTED data, not viewing the raw PDF. | Show extracted data in structured UI. Link to original PDF for download if broker wants to verify. |
| Real-time quote arrival notifications | Push notifications require WebSocket infrastructure, service workers, notification permissions. Overkill when broker checks 2x/day. | Gate strip counts update on page navigation. Task list on dashboard shows new arrivals. Polling on dashboard page (30s interval) is sufficient. |
| Head-to-head comparison mode | Comparing exactly 2 carriers side-by-side sounds useful but fragments the UX. The matrix already IS the comparison tool. | Matrix with checkbox selection. Deselect all but 2 carriers = head-to-head. No separate mode needed. |
| Commission tracking | Different product, different data model, different regulatory requirements (Mexico CNSF). Not in the placement workflow. | Defer to a future module. Placement workflow ends at "Export comparison to client". |
| Drag-and-drop row reordering in matrix | Coverage rows have a logical domain ordering (General Liability before Professional Liability). Custom ordering adds state complexity for minimal value. | Fixed ordering: match contract clause order. Group by insurance vs surety. |
| Proposal builder / branded report | Broker exports Excel, adds their own cover letter, sends via their own email. Building a proposal template engine is a separate product. | Clean Excel export. Professional formatting. Two sheets. Broker handles the last mile. |
| Mobile-responsive comparison matrix | The comparison matrix with 5+ carrier columns cannot work on a phone. Broker's workflow is desktop/laptop. Mobile optimization is wasted effort. | Desktop-first. Responsive down to tablet (landscape). Below that, degrade gracefully with a message. |
| Analytics / reporting dashboard | Win rates, average placement time, carrier performance — all valuable but NOT part of the placement workflow. Mixing analytics with operations creates a cluttered dashboard. | Defer to analytics module. Dashboard stays operational: "what needs my attention now?" |
| TCOR (Total Cost of Risk) calculation | Complex actuarial concept requiring loss history, retention analysis, risk transfer costs. Entire InsurTech companies are built around TCOR. | Simple total premium row. TCOR is a Phase 3+ differentiator if there's demand. |

## Feature Dependencies

```
Gate Strip (new component)
  <- Dashboard aggregation endpoint (new backend)
  <- Gate count computation (project status + approval_status + quote counts)

Dashboard Task List (new component)
  <- Dashboard aggregation endpoint (same as above)
  <- Task priority logic (urgency scoring: days waiting + gate type)

Tabbed Project Detail (redesign)
  <- Step indicator component (new)
  <- Tab state management (URL param or local state)
  <- Existing components refactored into tab content:
     Coverage tab: CoverageTable + GapAnalysis (exist)
     Carriers tab: CarrierSelection + SolicitationPanel (exist)
     Quotes tab: QuoteTracking (exists)
     Compare tab: ComparisonMatrix (needs rebuild)

Comparison Matrix Rebuild
  <- Insurance/Surety tab separation (filter by category)
  <- Two-row cell renderer (new component)
  <- Critical exclusion alert box (new component)
  <- "Show Differences Only" toggle (new logic)
  <- "Highlight Best Values" toggle (refactor existing badges)
  <- Carrier selection checkboxes (new in headers)
  <- Frozen first column + sticky headers (CSS position: sticky)
  <- Total premium row (compute + sticky)

Excel Export
  <- Backend .xlsx generation endpoint (new — use openpyxl)
  <- Two-sheet format (Insurance + Surety)
  <- Carrier selection state (which columns to include)
  <- Formatted cells matching matrix layout
  <- Critical exclusion summary section below matrix

ag-grid Adoption for Broker Tables
  <- Project pipeline table (replace HTML ProjectTable)
  <- Reuse pipeline ag-grid patterns (theme, cell renderers, column defs)
  <- Status filter chips (custom filter component)
  <- Sort by days-in-stage
  NOTE: ag-grid Community only. No Enterprise features (Excel export, etc.)
```

## MVP Recommendation

Prioritize (in dependency order):

1. **Gate strip + dashboard aggregation endpoint** — This is the broker's primary awareness mechanism. Without it, they have to navigate to dashboard to know what needs attention. Backend endpoint returns gate counts + task list. Frontend renders persistent strip in broker layout. Task list replaces KPI cards on dashboard. Unblocks everything else because it defines the urgency model.

2. **Tabbed project detail with step indicator** — The current vertical scroll layout doesn't scale to 5 workflow stages. Tab redesign reorganizes existing components (which all work) into a navigable structure. No new backend work. Unblocks the comparison matrix rebuild because Compare becomes its own focused tab.

3. **Comparison matrix rebuild** — The core deliverable. Insurance/surety tabs, two-row cells, frozen columns, critical exclusion alerts, difference-only toggle. This is Gate 3 — the moment the broker produces the deliverable they send to their client. Must feel professional and information-dense without clutter.

4. **Excel export** — Backend-generated .xlsx with openpyxl. Two sheets, formatted cells, color coding, exclusion summary. This is the ACTUAL output the client receives. Without it, the comparison matrix is view-only and the broker still builds the spreadsheet manually.

5. **ag-grid adoption for broker tables** — Replace HTML `ProjectTable` with ag-grid using existing pipeline patterns (theme, custom cell renderers). Gives sort, filter, search for free. Consistent with GTM pipeline UX.

Defer:
- **Carrier roster management improvements**: Existing `CarrierSettings.tsx` is adequate for MVP. Polish later.
- **"Link to Project" modal for unlinked emails**: Edge case for automated email processing. Build when email sync is live.
- **Client profile section on Overview tab**: Nice to have. Project info sidebar already shows key metadata.
- **Empty states**: Important for onboarding polish but not blocking core workflow. Add in final polish pass.

## Domain-Specific Insights

### What makes a great broker tool vs adequate

Research into Applied Epic, HawkSoft, AMS360, BrokerEdge, and Mexican broker platforms (SEKURA, Howden, Surexs) reveals these patterns:

**Great tools adapt to the broker's existing workflow.** They don't force a new process — they accelerate the one the broker already follows. The 3-gate model (review extractions, approve solicitations, export comparison) maps exactly to the broker's existing decision points but removes all the mechanical work between them.

**Great tools surface risk, not just data.** The critical exclusion alert box with contract-clause citations is the most differentiated feature. No major AMS (Applied Epic, HawkSoft, AMS360) does AI-powered exclusion-to-contract-clause mapping. They show quote data; they don't cross-reference it against contract requirements. This is where E&O liability lives.

**Great tools respect information density.** Insurance brokers are power users who process dense tabular data daily. They don't want wizard-style UX with one field per page. They want the comparison matrix — all data visible, differences highlighted, noise removed. The "Show Differences Only" toggle (Tufte-inspired data reduction) is the right UX for this user.

**Adequate tools are just prettier Excel.** If the tool shows the same data as a spreadsheet but takes more clicks to navigate, brokers go back to Excel. The differentiator is: (a) the data was GENERATED automatically (no manual entry), (b) the analysis was DONE automatically (gap detection, exclusion flagging), (c) the spreadsheet was BUILT automatically (Excel export). The broker adds professional judgment at 3 gates. Everything else happened without them.

### Mexico construction insurance specifics

- Construction projects require BOTH insurance (seguros) and surety bonds (fianzas). Always separate tracks.
- Major Mexican carriers: Chubb, Zurich, Mapfre, GNP, Qualitas, AXA for insurance. Afianzadora Insurgentes, Fianzas Monterrey for surety.
- Surety bonds have different data fields: bond amount, rate, term — not premium/limit/deductible like insurance.
- The comparison matrix MUST handle both data shapes in separate tabs. The Excel export MUST have two sheets.
- Howden Mexico specifically offers "customized bonding management systems" — confirms that broker-specific tooling for fianzas is a real market need.

## Sources

- Spec: `SPEC-BROKER-FRONTEND-MVP.md` in project root (approved v2, post board review)
- Existing components: 17 broker components in `frontend/src/features/broker/components/`
- ag-grid patterns: `frontend/src/features/pipeline/components/PipelinePage.tsx` (Community edition, Quartz theme)
- [Insurance UX Design Trends 2025](https://www.g-co.agency/insights/insurance-ux-design-trends-industry-analysis) — personalization, data-driven dashboards
- [BrokerEdge — Insurance Broker Software](https://www.damcogroup.com/insurance/brokeredge-broker-management-software) — task management, workflow automation
- [AMS Comparison 2026: Epic vs HawkSoft vs AMS360](https://www.quotesweep.com/blog/ams-comparison-2026) — feature comparison of major broker management systems
- [AI Agents for Insurance Policy Comparison](https://datagrid.com/blog/ai-agents-automate-insurance-policy-comparison-document-control-managers) — AI-powered gap analysis patterns
- [Coverage Gap Analysis with AI for Brokers](https://www.datagrid.com/blog/ai-agents-automate-coverage-gap-analysis) — exclusion detection patterns
- [Insurance Comparison Table Examples](https://ninjatables.com/insurance-comparison-table/) — side-by-side layout patterns
- [Stepper UI Design Patterns](https://medium.com/@david.pham_1649/beyond-the-progress-bar-the-art-of-stepper-ui-design-cfa270a8e862) — horizontal vs vertical, enterprise dashboard patterns
- [Howden Mexico Surety Solutions](https://www.howdengroup.com/mx-es/world-class-surety-insurance-solutions) — Mexico construction fianza market
- [AG Grid Cell Components](https://www.ag-grid.com/react-data-grid/component-cell-renderer/) — custom cell renderer patterns
- [AG Grid Excel Export](https://www.ag-grid.com/react-data-grid/excel-export/) — Enterprise-only feature (NOT available in Community)
- [Step-by-Step Insurance Procurement Checklist](https://insurancecurator.com/step-by-step-procurement-checklist-from-coverage-needs-analysis-to-final-policy-bind/) — commercial placement workflow
- [Brokerage Workflow Management](https://www.expertinsured.com/key-features/workflow-and-task-management/brokerage-workflow) — intake to bind workflow
