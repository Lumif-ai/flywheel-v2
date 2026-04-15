# Domain Pitfalls

**Domain:** Insurance broker frontend redesign + Claude Code skills + hook automation + portal automation
**Researched:** 2026-04-15
**Confidence:** HIGH (based on direct codebase analysis of 63 broker files, three spec documents, existing implementation patterns)

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Spec Drift Between Three Documents

**What goes wrong:** The redesign spec (SPEC-BROKER-REDESIGN.md) overrides parts of both parent specs (SPEC-BROKER-MVP.md, SPEC-BROKER-FRONTEND-TECHNICAL.md) but not all. Developers consult the wrong spec and build the wrong thing. Example already visible: the redesign spec section 4.9 overrides the comparison matrix from custom `<table>` to ag-grid, contradicting SPEC-BROKER-FRONTEND-TECHNICAL.md section 2.5 which explicitly argues against ag-grid for comparison. Another: redesign adds a 6th tab ("Analysis") changing the step indicator from 5 to 6 steps, but does not repeat the full step indicator spec.

**Why it happens:** Three specs with partial override relationships. The redesign says "this spec is additive" but then overrides 6+ decisions: comparison table technology, carrier selection layout, overview tab layout, step indicator count, API paths, type definitions.

**Consequences:** Components built to wrong spec, discovered during review, rewritten. This is exactly the pattern that produced the v15.0 frontend the user called "terrible."

**Prevention:**
1. Before each phase, explicitly list which spec section governs each component being built
2. When a redesign section says "Updates to SPEC-BROKER-FRONTEND-TECHNICAL.md section X," the redesign is authoritative for that section
3. Each phase plan must quote the exact spec section being implemented, not paraphrase
4. Build a reconciliation table in Wave 0 listing every conflict and which spec wins

**Detection:** Component looks different from the demo reference beats in Appendix A. Developer references "the spec" without specifying which one.

**Phase:** Wave 0 (Foundation). Create a reconciliation table before any code is written.

---

### Pitfall 2: Removing Stale Types Before Building Replacements

**What goes wrong:** The redesign spec says to delete 5 fields from `BrokerProject` (recommendation_*) and 6 fields from `CarrierQuote` (is_best_price, is_best_coverage, is_recommended, draft_subject, draft_body, draft_status). These fields are actively used in existing components. Verified in codebase:
- `ComparisonView.tsx` and `ComparisonGrid.tsx` use `is_best_price/is_best_coverage/is_recommended` via `ComparisonQuoteCell` type (which already has them correctly)
- `DeliveryPanel.tsx` reads `recommendation_*` fields from `BrokerProject`
- `CarrierQuote` type in `broker.ts` lines 205-221 has all 6 fields being removed
- `EmailApproval.tsx` uses `draft_subject/draft_body` from `CarrierQuote`

**Why it happens:** The redesign correctly identifies that these fields are on the wrong type (they belong on `ComparisonQuoteCell`, `BrokerRecommendation`, and `SolicitationDraft` respectively). But the spec does not account for the strict ordering needed: you must build the replacement data paths before removing the old ones.

**Consequences:** Deleting `draft_subject/draft_body` from `CarrierQuote` without first building `useSolicitationDrafts()` and updating `EmailApproval.tsx` breaks email approval. TypeScript will catch these at compile time, but the fix requires building entire new API integrations.

**Prevention:**
1. Run `grep -rn "recommendation_subject\|recommendation_body\|draft_subject\|draft_body\|is_best_price" frontend/src/features/broker/` before removing any field
2. Strict ordering: add `SolicitationDraft` type + `useSolicitationDrafts` hook FIRST, update `EmailApproval.tsx` to use it, THEN remove stale fields
3. For `ComparisonQuoteCell`: the fields `is_best_price/is_best_coverage/is_recommended` are already on this type correctly (broker.ts lines 230-232), so removing them from `CarrierQuote` is safe IF no component reads them from `CarrierQuote` directly
4. Phase order: add new types -> update consumers -> remove old types. Never invert this.

**Detection:** TypeScript build failures after type changes. Components rendering `undefined` values.

**Phase:** Wave 0 must be sequenced: add new types/hooks first, update consuming components second, remove old types last.

---

### Pitfall 3: ag-Grid Comparison Matrix Complexity Underestimated

**What goes wrong:** The redesign spec (section 4.9) overrides the parent spec's custom `<table>` decision and mandates ag-grid for the comparison matrix. This sounds like a consistency win, but the comparison matrix has 7 requirements that each need custom ag-grid work:
1. Two-row cells (premium + limit/deductible) -> custom `ComparisonCellRenderer` with `rowHeight: 64`
2. Expandable coverage groups -> `groupRowRenderer` with `groupDefaultExpanded: 1`
3. Total premium row -> `pinnedBottomRowData`
4. Per-cell color coding based on cross-row analysis -> `cellStyle` function with cross-data lookup
5. Carrier show/hide via column toggling -> `columnApi.setColumnVisible()`
6. "Show differences only" row filtering -> external filter + hidden row count display
7. "PDF Preview" toggle -> entirely separate non-ag-grid render path

**Why it happens:** Each feature is individually straightforward in ag-grid docs, but their interaction is not. What happens when `pinnedBottomRowData` needs to update after group rows collapse? When `setColumnVisible` hides a carrier, does the pinned bottom row's total update? When "Show differences only" hides rows, do group headers with 0 visible children auto-hide?

**Consequences:** 2-3x longer implementation than estimated. `ComparisonCellRenderer` becomes the most complex renderer in the codebase. Edge case bugs surface during demo.

**Prevention:**
1. Build a throwaway prototype with 3 carriers and 5 coverages testing: group expand/collapse + pinned bottom + column visibility + external filter. If it takes more than 1 day, pivot to custom `<table>` from parent spec.
2. The "PDF Preview" toggle is a completely separate component regardless -- do not try to make ag-grid render a print-friendly view
3. Test the existing `ComparisonView.tsx` component (107 lines, currently working with custom grid) before replacing it

**Detection:** Comparison matrix phase taking more than 2 days. Bugs where totals do not update after group collapse.

**Phase:** Wave 2 (task 26). Highest-risk frontend task. Prototype-first approach mandatory.

---

### Pitfall 4: Hook Scripts Matching Too Broadly During Pipeline Runs

**What goes wrong:** The `post-coverage-write.py` hook fires on `PostToolUse` for any Bash command matching `PATCH /broker/coverages/` or `POST /broker/projects/{id}/coverages`. During a `process-project` pipeline, coverages are written multiple times:
- Step 2: parse-contract for insurance coverages (6+ writes)
- Step 3: parse-contract for surety coverages (3+ writes)  
- Step 4: parse-policies updates current limits (6+ writes)

Each write triggers `POST /analyze-gaps`, meaning gap analysis runs 15+ times during one pipeline execution, each overwriting previous results.

**Why it happens:** Hooks operate at the tool-use level with no concept of workflow state. The hook cannot distinguish "single manual coverage edit" from "bulk writes during a pipeline run."

**Consequences:** Unnecessary API calls (15x gap analysis for one project), potential race conditions if writes and analysis calls overlap, misleading intermediate results shown to user, and wasted backend compute.

**Prevention:**
1. Pipeline-mode sentinel: when `process-project` starts, create `~/.claude/skills/broker/.pipeline-active-{project_id}`. Hook scripts check for this file and skip if present. Pipeline skill runs gap analysis once at the end.
2. Alternatively, debounce in the hook script: if gap analysis was called within the last 30 seconds for the same project, skip.
3. The `post-quote-write.py` hook has the same issue: comparison will re-run for each quote extracted during `compare-quotes`.

**Detection:** Console output showing "Auto-running gap analysis..." more than once per pipeline run. Backend logs showing repeated `analyze-gaps` calls within seconds.

**Phase:** Wave 1 (tasks 14-15). Hook scripts must be designed with pipeline awareness from day one.

---

### Pitfall 5: Recreating the "Generic CRUD Look"

**What goes wrong:** The previous implementation was called "terrible" and "looks like shit." Specific complaints: generic CRUD layout, no visual drama, no AI moments, default ag-grid theme, generic gray badges, no dollar amounts in gap analysis, no critical exclusion alerts. The redesign spec addresses all of these, but implementation pressure leads to building the data-correct version first and "adding polish later." The polish never arrives.

**Why it happens:** It is natural to build structure before style. But this redesign was motivated by visual quality. The previous implementation had correct data and correct structure -- it failed on visual execution. Building "functional first, pretty later" reproduces the exact failure.

**Consequences:** Another round of "this looks like the old version." User loses confidence. Third rewrite.

**Prevention:**
1. Every component must be built with its visual spec from day one -- three-layer Airbnb shadow, coral accents, semantic status colors, and card borders are the spec, not polish
2. Build one component to full visual spec (MetricCard is a good candidate: small, self-contained, spec is explicit) and get approval before proceeding
3. Each PR must include a screenshot comparison against the demo reference beat (Appendix A in redesign spec)
4. Explicit "What NOT to Do" checklist from the user must be verified for every component:
   - NOT default ag-grid theme -> verify `flywheelGridTheme` applied
   - NOT generic gray badges -> verify semantic `BROKER_STATUS_COLORS` used
   - NOT truncated email body -> verify `white-space: pre-wrap` on full content
   - NOT ActivityTimeline on every tab -> verify only on Overview sidebar
   - NOT match_score bars -> verify ToggleCell on carrier selection
   - NOT raw JSON/technical IDs -> verify formatted output
   - NOT purple/blue gradients -> verify coral-only accent
   - NOT flat borderless cards -> verify `border + shadow` on every card
   - NOT missing empty states -> verify contextual empty state per section
   - NOT browser default scrollbars -> verify styled scrollbars

**Detection:** Component does not visually match its demo reference beat. Any item from the "What NOT to Do" list present in the build.

**Phase:** Every wave. Cross-cutting concern that must be enforced in every PR review.

---

### Pitfall 6: Playwright Portal Scripts Breaking on DOM Changes

**What goes wrong:** The `fill-portal` skill uses Playwright scripts with exact DOM selectors for Mapfre, GNP, and Chubb portals. Carrier portals update their UIs without notice. A CSS class rename, form field ID change, or new modal/captcha breaks the script silently -- Playwright clicks the wrong element or throws a timeout.

**Why it happens:** Third-party web UIs are not under our control. Mexican carrier portals often use legacy form frameworks with generated class names. No SLA on DOM stability.

**Consequences:** Portal automation fails during a client demo. User fills form manually. Trust in automation erodes.

**Prevention:**
1. Use data attributes and ARIA labels as primary selectors, CSS classes as fallback
2. Each carrier script must have a `LAST_VERIFIED` date and a `verify()` function that checks portal structure
3. Add `--dry-run` mode: navigates and screenshots without filling fields
4. `pre-portal-validate.py` hook should run `verify()` before allowing fill
5. Build Mapfre ONLY first. GNP and Chubb scripts only after Mapfre is proven stable 2+ weeks
6. Every script action must be wrapped in try/except with screenshot-on-failure

**Detection:** Playwright timeouts on selectors. Screenshots showing unexpected modals or layout changes.

**Phase:** Wave 1 (task 13). Only Mapfre initially. Other carriers deferred.

---

## Moderate Pitfalls

### Pitfall 7: CSS Animations Causing Jank on Data-Heavy Pages

**What goes wrong:** The redesign spec calls for 6 CSS animations: `fadeUp` (requirement cards), `stagger` (60ms delays across 8+ cards), `shimmer` (loading gradient), `pulse` (pending badge), `greenFlash` (completion), `highlightSweep` (new rows). Applied alongside ag-grid tables with 20+ rows, these can trigger layout reflow and frame drops.

**Prevention:**
1. All animations must use `transform` and `opacity` only -- never animate `height`, `width`, `margin`, or `padding`
2. Add `will-change: transform, opacity` on animated elements
3. `shimmer` uses `background: linear-gradient` which is GPU-composited -- safe
4. `stagger` on requirement cards is fine (8-10 cards max), but NEVER apply stagger to ag-grid rows
5. `pulse` on pending badge must be pure CSS, not a React re-render interval
6. Test with Chrome DevTools Performance panel -- any frame > 16ms is a bug

**Phase:** Wave 4 (tasks 34-39). Animation is correctly the last wave.

---

### Pitfall 8: Skill Domain Knowledge Drifting from Reality

**What goes wrong:** Broker skills embed Mexican insurance domain knowledge (contract clause patterns, carrier routing rules, endorsement codes, portal URLs) directly in SKILL.md prompts. This is static text. If Mapfre changes their portal URL, if a carrier's response time changes, if new endorsement codes become standard, skills give wrong guidance.

**Prevention:**
1. Knowledge that changes (carrier details, portal URLs, response times, email addresses) must live in `CarrierConfig` database records, not skill prompts. The `select-carriers` skill must read `GET /broker/carriers`, not hardcoded text.
2. Knowledge that is stable (contract clause patterns, endorsement codes, premium formulas) can live in skill prompts but should be in separate `references/` files, not inline
3. Add `DOMAIN_KNOWLEDGE_VERSION` to skill prompts and a quarterly review process

**Phase:** Wave 1 (task 10) and Wave 2 (tasks 17-23). Prompt architecture decision.

---

### Pitfall 9: Hook Auth Token Unavailable or Expired

**What goes wrong:** Hook scripts call backend API using `FLYWHEEL_API_TOKEN` from environment. The token is set by the `SessionStart` hook (`pre-read-context.py`). Failure modes: (a) token expires during long pipeline runs, (b) `pre-read-context.py` fails silently so token is never set, (c) hook scripts exit silently on missing token (by design in spec), meaning gap analysis silently never runs.

**Prevention:**
1. Hook scripts that exit silently should log to `~/.claude/skills/broker/.hook-log` for debugging
2. `pipeline-check.py` Stop hook should verify gap analysis actually ran (check `gap_status` on coverages), not just that the hook was invoked
3. Consider returning a visible message to Claude Code context: "Warning: gap analysis hook skipped (no auth token)" rather than silent exit

**Phase:** Wave 1 (tasks 14-15). Hook error handling design.

---

### Pitfall 10: ag-Grid Row Grouping Conflicts with Inline Editing

**What goes wrong:** Coverage tab spec calls for ag-grid with section group rows ("INSURANCE COVERAGES", "SURETY BONDS") AND inline editing on `coverage_type` and `required_limit`. ag-grid row grouping changes how row data is structured -- grouped rows use `aggData` not direct field access. The `onCellValueChanged` callback may receive the group node instead of the leaf data, causing edits to silently fail or write to the wrong record.

**Prevention:**
1. Use ag-grid's `fullWidthRow` pattern for section headers instead of true row grouping -- keeps leaf rows as normal editable rows
2. Test inline editing on rows that appear below a section header
3. `onCellValueChanged` must verify `params.data.id` exists (not a group row) before calling `PATCH /broker/coverages/{id}`

**Phase:** Wave 2 (task 25). Coverage tab implementation.

---

### Pitfall 11: "Run in Claude Code" Button Confusing Users

**What goes wrong:** The redesign introduces buttons that copy commands to clipboard instead of performing actions. Users click, see "Copied!", and wait for something to happen in the browser. Nothing happens because they need to switch to Claude Code and paste.

**Prevention:**
1. Toast message must say: "Copied! Open Claude Code and paste this command" -- not just "Copied!"
2. Add one-time popover explaining the workflow on first use (store dismissal in localStorage)
3. The `prominent` variant includes a description line -- use it on every "Run in Claude Code" instance
4. Consider adding a visible helper text below each button: "This task runs in Claude Code"

**Phase:** Wave 3 (tasks 27-33). Every page with the button.

---

### Pitfall 12: Four API Path Mismatches Causing Silent 404s

**What goes wrong:** Redesign spec section 5.1 identifies 4 broken paths in `api.ts`:
- `editSolicitationDraft`: `PUT /broker/quotes/{quoteId}/draft` -> should be `PUT /broker/solicitation-drafts/{draftId}`
- `approveSendSolicitation`: `POST /broker/quotes/{quoteId}/approve-send` -> should be `POST /broker/solicitation-drafts/{draftId}/approve-send`
- `editRecommendation`: `PUT /broker/projects/{projectId}/recommendation-draft` -> should be `PUT /broker/recommendations/{recommendationId}`
- `sendRecommendation`: `POST /broker/projects/{projectId}/approve-send-recommendation` -> should be `POST /broker/recommendations/{recommendationId}/approve-send`

These are 404s. Core workflow actions (edit email, send email, edit recommendation, send recommendation) silently fail.

**Prevention:** Fix in Wave 0, task 1. After fixing, manually test each action. Add correct endpoint paths as comments in the API function file.

**Phase:** Wave 0 (task 1). Absolute first priority.

---

### Pitfall 13: Shared Grid Theme Changes Breaking GTM Pipeline

**What goes wrong:** The redesign updates `flywheelGridTheme` in `frontend/src/shared/grid/theme.ts` (coral hover, remove column separators). This theme is imported by both broker and GTM pipeline (`PipelinePage.tsx`). Changing it changes the pipeline appearance without testing.

**Prevention:**
1. After updating `theme.ts`, visually verify the pipeline at `/pipeline`
2. Coral hover (`rgba(233,77,53,0.03)`) is subtle, likely fine on both surfaces
3. Removing `headerColumnSeparatorDisplay` may look wrong on the pipeline which has more columns
4. If pipeline looks wrong: create `brokerGridTheme` extending `gridTheme` with broker-specific overrides instead of modifying shared theme

**Phase:** Wave 0 (task 5). Test pipeline immediately after theme change.

---

### Pitfall 14: New "Analysis" Tab Breaking Step Indicator Logic

**What goes wrong:** Redesign adds a 6th tab ("Analysis") between Overview and Coverage. The existing `StepIndicator.tsx` likely has hardcoded step definitions. Adding a step requires updating: step count, labels, status mapping (now depends on both `status` and `analysis_status`), active step derivation, and URL query param routing (`?tab=analysis`).

**Prevention:**
1. Step indicator must be data-driven (array of step configs), not hardcoded indexes
2. The status mapping in redesign spec section 4.3 introduces `analysis_status` as a separate dimension from `status` -- implement exactly
3. Tab routing must handle the new `?tab=analysis` query param
4. Default tab remains `overview`

**Phase:** Wave 3 (task 28). Requires updating `BrokerProjectDetail.tsx`.

---

## Minor Pitfalls

### Pitfall 15: Currency Formatting Inconsistency

**What goes wrong:** Redesign uses "Mex$X,XXX,XXX" format. Different renderers format differently: `CurrencyCell`, inline `ComparisonCell`, quote detail expansion. Inconsistent display undermines the premium feel.

**Prevention:** `CurrencyCell` renderer must export a standalone `formatCurrency(value: number, currency: string): string` function used everywhere. Single source of truth for formatting.

**Phase:** Wave 0 (task 6). Build once, use everywhere.

---

### Pitfall 16: Missing Empty States

**What goes wrong:** User explicitly listed "Do NOT skip empty states." Every section needs a contextual empty state (icon + message + CTA), not just "No data."

**Prevention:** Each PR must include a screenshot of the empty state. Empty states must say what to do next (e.g., "Upload a contract and run `/broker:process-project`").

**Phase:** Every wave. PR review checklist item.

---

### Pitfall 17: Polling Intervals Stacking

**What goes wrong:** GateStrip polls 30s, Analysis tab polls 10s during analysis, QuoteTracking polls 10s during extraction. All active simultaneously on project detail page creates unnecessary API load.

**Prevention:** Use React Query's `refetchInterval` (already in codebase) with `refetchIntervalInBackground: false`. Verify navigating away from a tab stops its polling.

**Phase:** Wave 2-3. Integration testing.

---

### Pitfall 18: Skill Checkpoint File Conflicts Between Sessions

**What goes wrong:** `process-project` saves state to `~/.claude/skills/broker/.pipeline-state.json`. Two concurrent conversations (or a resumed conversation) overwrite or read the wrong file.

**Prevention:** Include project ID in filename: `.pipeline-state-{project_id}.json`. `pipeline-check.py` matches by project ID, not global file.

**Phase:** Wave 1 (task 15). Checkpoint naming design.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Wave 0: Foundation | Removing stale types before replacements exist (Pitfall 2) | Add new types first, update consumers, then remove old types |
| Wave 0: Foundation | Shared theme change breaking pipeline (Pitfall 13) | Visually verify `/pipeline` after theme update |
| Wave 0: Foundation | API path mismatches blocking all testing (Pitfall 12) | Fix 4 paths as absolute first task |
| Wave 1: Skills | Hooks firing 15x during pipeline (Pitfall 4) | Pipeline-mode sentinel file pattern |
| Wave 1: Skills | Hook auth silently failing (Pitfall 9) | Log warnings, verify in Stop hook |
| Wave 1: Skills | Portal DOM breaking on carrier updates (Pitfall 6) | Mapfre only, verify() function, dry-run mode |
| Wave 1: Skills | Checkpoint file collisions (Pitfall 18) | Include project_id in filename |
| Wave 2: High-Impact Frontend | Comparison matrix ag-grid 2-3x over budget (Pitfall 3) | Prototype first, 1-day gate, pivot to custom table |
| Wave 2: High-Impact Frontend | Coverage tab grouping vs editing conflict (Pitfall 10) | Use fullWidthRow, not true row grouping |
| Wave 2: AI Skills | Domain knowledge hardcoded in prompts (Pitfall 8) | Read from CarrierConfig API, not prompt text |
| Wave 3: Remaining Frontend | Spec drift across 3 documents (Pitfall 1) | Quote exact spec section in plan, reconciliation table |
| Wave 3: Remaining Frontend | Generic CRUD look repeat (Pitfall 5) | Visual spec from day one, screenshot diffs in PRs |
| Wave 3: Remaining Frontend | "Run in Claude Code" UX confusion (Pitfall 11) | Explicit toast text, first-use popover |
| Wave 3: Remaining Frontend | Analysis tab breaking step indicator (Pitfall 14) | Data-driven step config, dual status dimension |
| Wave 4: Animation | CSS jank on data pages (Pitfall 7) | transform/opacity only, DevTools Performance test |
| All waves | Missing empty states (Pitfall 16) | Screenshot of empty state required per PR |

---

## Integration Pitfalls (Skills + Hooks + Frontend)

### Integration 1: Hook Triggers Gap Analysis, Frontend Shows Stale Data

**What goes wrong:** Skill writes coverages via API. `post-coverage-write.py` hook triggers gap analysis on the backend. Frontend has stale React Query cache showing old gap status. User sees "missing" gaps that were just filled.

**Mitigation:** Skills should output "Data updated. Refresh the browser tab to see changes." Frontend should use `refetchInterval` on coverage query while `analysis_status === 'running'`. Future: WebSocket/SSE for real-time updates.

### Integration 2: Skill Creates Coverages with Fields Frontend Cannot Display

**What goes wrong:** `parse-contract` skill creates coverages with `contract_clause`, `source_excerpt`, `gap_amount`, `ai_critical_finding`. Current `ProjectCoverage` type (broker.ts lines 42-55) lacks most of these fields. Analysis tab renders `undefined`.

**Mitigation:** Wave 0 task 4 (add missing fields to `ProjectCoverage` type) MUST complete before Analysis tab (Wave 3) or Coverage tab updates (Wave 2). Types are the foundation.

### Integration 3: Pipeline Skill Fills Claude Code Context Window

**What goes wrong:** `process-project` pipeline runs 9 steps sequentially, each with API calls, PDF reading, and AI analysis. Full pipeline takes 10-15 minutes. Context window fills with intermediate output, and later steps lose context about earlier results.

**Mitigation:** Each step skill should produce minimal output (1-2 summary lines, not full data dumps). Pipeline uses checkpoint files to track state rather than relying on conversation context.

### Integration 4: Hook and Skill Both Call the Same Endpoint

**What goes wrong:** The `gap-analysis` skill explicitly calls `POST /analyze-gaps`. The `post-coverage-write.py` hook also calls `POST /analyze-gaps`. During a pipeline run where the skill calls gap analysis AND the hook fires, the endpoint is called twice with the same data. Not harmful (idempotent), but wasteful and confusing in logs.

**Mitigation:** Pipeline-mode sentinel (same solution as Pitfall 4) prevents hooks from firing during pipeline runs where the skill handles the orchestration.

---

## Sources

- Direct codebase analysis: `frontend/src/features/broker/` (63 files), `frontend/src/shared/grid/theme.ts` (17 lines), `frontend/src/features/broker/types/broker.ts` (379 lines)
- SPEC-BROKER-REDESIGN.md (1680 lines, all 8 sections + 2 appendices analyzed)
- SPEC-BROKER-FRONTEND-TECHNICAL.md (837 lines, all 8 sections analyzed)
- MILESTONES.md (v15.0 Broker Module MVP history, v16.0 Briefing Intelligence)
- Existing component implementations verified: `ProjectPipelineGrid.tsx` (135 lines), `ComparisonView.tsx` (107 lines), `BrokerDashboard.tsx` (42 lines), `StepIndicator.tsx`, `BrokerProjectDetail.tsx`
- Claude Code hooks infrastructure: `~/.claude/settings.json` (current hook configuration verified)
- ag-grid row grouping + pinnedBottomRowData + inline editing interaction (training data, MEDIUM confidence -- prototype recommended)
- Playwright automation stability patterns (training data, MEDIUM confidence on carrier portal specifics)
