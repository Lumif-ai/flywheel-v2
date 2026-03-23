---
name: spec
version: "1.4"
description: >-
  Turn vague ideas into executable specifications through propose-then-react drafting,
  adversarial review, and acceptance criteria tightening. Ingests existing artifacts
  (URLs, transcripts, code, screenshots) to extract requirements. Produces SPEC.md files
  consumable by GSD, Ralph loops, or manual development. Also reviews existing specs for
  gaps, contradictions, and missing edge cases. Integrates with execution feedback via
  SPEC-GAPS.md. Use when user says "spec this out", "write a spec", "I want to build X",
  "review this spec", "is this spec complete", "find gaps", "tighten the spec",
  "spec review", "what am I missing", "help me define requirements", or shares an idea
  they want to turn into a buildable specification.
---

# spec

## Philosophy

The spec problem is an **elicitation problem**, not a writing problem. Users know what they want
but can't articulate it completely. This skill helps users think more clearly -- not fill out
better templates.

**Core principles:**
1. **Propose-then-react, not interview.** Ask 2-3 framing questions, then generate a draft. Reacting is 10x easier than generating.
2. **Artifact-first.** Ingest what already exists (URLs, transcripts, code, screenshots) rather than extracting everything through questions.
3. **Acceptance criteria are the only thing that matters.** Everything else is context to derive them.
4. **Built-in adversarial pass.** Every generation ends with a self-review. No separate step needed.
5. **Living document.** Execution gaps feed back into the spec through SPEC-GAPS.md.

## Modes

This skill operates in three modes, all under one entry point.

### Mode 1: Generate (`/spec` or `/spec generate`)

**When:** User has an idea, artifacts, or a rough description and needs a structured spec.

**Flow:**

**Step 1: Ingest existing artifacts**

Before asking ANY questions, check what the user has already provided:
- URLs → fetch and extract requirements, features, patterns
- Meeting transcripts → extract decisions, requirements, constraints
- Existing code / repo → infer current architecture, patterns, constraints
- Screenshots / mockups → extract UI requirements, flows
- Competitor products → reverse-engineer feature requirements
- Slack threads / docs → extract discussed requirements
- Existing SPEC.md → load as starting point for refinement

If artifacts are provided, extract everything possible FIRST. This reduces the questions needed.

**Artifact extraction specifics:**

For each artifact type, here's what to extract:

| Artifact | Extract | Ignore |
|----------|---------|--------|
| **URL (product/competitor)** | Feature list, UI patterns, user flows, pricing tiers, error messages visible | Marketing copy, blog posts, team bios |
| **Meeting transcript** | Decisions made ("we agreed to..."), requirements stated ("it must..."), constraints mentioned ("we can't because..."), deferred items ("let's not do X in v1") | Small talk, scheduling discussion, off-topic tangents |
| **Existing code** | Data models (what entities exist), API endpoints (what operations), validation rules (what constraints), error handling patterns (what fails) | Implementation details (how, not what), test files (unless testing reveals requirements) |
| **Screenshots/mockups** | UI elements (buttons, forms, tables), data displayed (what fields), user flows (what connects to what), states visible (empty, loading, error) | Exact styling, pixel measurements, color values |
| **Slack/docs** | Feature requests, bug reports (imply missing requirements), user complaints (imply UX requirements), decisions with context | Emoji reactions, thread replies that are just "+1" |

**Step 2: Ask 2-3 framing questions (MAX)**

Based on what's already known from artifacts, ask ONLY what's genuinely missing. Common framers:

- "What's the ONE thing this must do perfectly?" (core value)
- "Who uses this and what triggers them to use it?" (user + entry point)
- "What does 'done' look like -- how would you demo this to someone?" (acceptance criteria seed)

If artifacts already answer these, skip directly to drafting. Do NOT ask questions the artifacts already answer.

**Step 3: Draft the spec**

Generate a complete SPEC.md using the output format below. Include:
- All requirements extracted from artifacts
- Inferred edge cases the user likely hasn't considered
- Domain-aware requirements (use web research if the domain has common patterns -- e.g., Stripe billing needs retry logic, auth needs token refresh, etc.)

**Step 4: Self-review (built-in adversarial pass)**

After drafting, automatically run the 6 review lenses (see Mode 2) against your own draft.
Append a "Gaps Found During Generation" section listing anything material. This saves the
user from needing to run a separate review.

**Step 5: Present and iterate**

Show the draft spec + gaps to the user. Let them react:
- Confirm assumptions
- Fill identified gaps
- Correct wrong inferences
- Add requirements you missed

Iterate until the user says it's good. Each iteration should be fast -- update and re-present,
don't re-interview.

---

### Mode 2: Review (`/spec review`)

**When:** User has an existing spec (any format -- SPEC.md, PRD, GitHub issue, requirements doc, or even a GSD PROJECT.md + REQUIREMENTS.md) and wants it pressure-tested.

**Input:** A spec file path, URL, or pasted content. Also accepts `--include-gaps` flag to incorporate SPEC-GAPS.md from prior execution runs.

**The 7 Review Lenses:**

**Lens 1: Ambiguity & Absence Scan**
Two sub-checks:

*1a: Vague language* — flag language that forces the implementer to guess:
- "Handle errors appropriately" → which errors? what does the user see?
- "Support multiple formats" → which formats exactly?
- "Should be fast" → what latency target?
- "Secure authentication" → which auth method? what threat model?

*1b: Absent specifications* — flag things that should be specified but aren't mentioned at all.
Absence is worse than vagueness: vague specs get implemented wrong, absent specs don't get
implemented at all. Check for:
- API endpoints with no request body defined
- SSE/WebSocket streams with no event types listed
- Webhooks with no payload format
- Database tables with no column definitions
- State machines with no transition triggers
- Integrations with no error/timeout handling

**Lens 2: Completeness Check**
For each feature/requirement, verify:
- Happy path defined? ✓/✗
- Error states defined? ✓/✗
- Empty/zero states defined? ✓/✗
- Boundary conditions defined? ✓/✗
- Permissions/access control defined? ✓/✗
- Data validation rules defined? ✓/✗

For every API endpoint, additionally check:
- Request body/params defined? ✓/✗
- Response format defined? ✓/✗
- Error responses (4xx, 5xx) defined? ✓/✗
- Auth requirements defined? ✓/✗
- Rate limiting defined? ✓/✗

**Lens 3: Contradiction Detection**
Three sub-checks:

*3a: Requirement vs requirement* — direct conflicts:
- "Users can delete their account" + "All user data must be retained for compliance"
- "Real-time updates" + "Works offline"
- "Simple one-page UI" + 15 listed features

*3b: Schema vs data flow* — structural inconsistencies:
- Schema column exists but data flow describes storing the same data in JSONB
- API endpoint references a table that doesn't exist in the schema
- Edge case references stale column/table names from prior spec revisions
- Flow says "data goes to X" but schema shows the field on Y

*3c: Scope vs description* — what the spec says it covers vs what it actually specifies:
- Phase plan claims to cover feature X, but no requirements exist for X
- Anti-requirements exclude something, but a requirement implicitly includes it

Especially important for specs that went through multiple edit rounds.

**Lens 4: Acceptance Criteria Audit**
For EVERY requirement, check:
- Is there a testable "done" definition?
- Could two engineers disagree on whether it's met?
- Is it observable from the user's perspective (not implementation-shaped)?

**Lens 5: Persona & State Transition Walkthrough**
Simulate relevant user types through the spec. Go beyond static personas to include
**state transition personas** — users at lifecycle handoff points:

*Static personas:*
- First-time user: what's the onboarding flow?
- Power user: what shortcuts/bulk operations exist?
- Admin/operator: what management capabilities are defined?
- Mobile user: does the spec account for responsive/mobile, and if deferred, is that risky?

*State transition personas (users between states):*
- Just signed up (between anonymous and active — what do they see?)
- Invited team member (tenant has data, user doesn't — different from first-time)
- Returning after inactivity (stale context, expired trial, expired token?)
- User whose integration broke (calendar disconnected, API key expired, third-party down)
- Mid-upgrade/downgrade (plan changing, feature access in flux)
- Post-cancellation (what's accessible? what's deleted? what's exportable?)

Identify any persona or state whose journey hits an undefined behavior.

**Lens 6: Non-Functional & Operational Gap Scan**
Check across four categories — only flag items **relevant to the project scope**:

*Technical non-functionals:*
- Performance targets (latency, throughput, concurrent users)
- Security (auth, input validation, data encryption, OWASP top 10)
- Accessibility (WCAG level, screen reader support)
- Scalability (expected load, growth assumptions)
- Monitoring (logging, alerting, health checks)

*Third-party dependency resilience:*
- For EACH external service the spec depends on: what happens when it's down?
- Retry strategy? Fallback? User-facing error message?
- Examples: payment provider outage, AI API outage, email service down, OAuth provider down

*Legal & compliance:*
- Terms of Service / Privacy Policy required?
- Cookie consent (if web app)?
- Data Processing Agreement (if B2B)?
- Data retention / deletion obligations?
- Only flag if the project handles user data or payments

*Product operations:*
- Admin dashboard or internal tooling needs?
- Conversion funnel tracking (signup → activation → retention)?
- Cost monitoring (API spend, infrastructure, per-user economics)?
- State transition UX (what user sees at: trial expiry, key expiry, plan change, account deletion)

**Lens 7: Cross-Reference Consistency**
For specs that have been edited iteratively or have technical detail (schema, API, data flow):
- Schema columns match data flow descriptions (no orphaned columns, no JSONB-vs-column conflicts)
- API endpoints match schema tables (every table should be reachable via API)
- Edge cases reference correct table/column names (not stale names from prior revisions)
- Requirement IDs referenced in other sections actually exist
- Phase plan scope matches what the spec actually describes
- Acceptance criteria reference the correct feature (not copy-paste from another requirement)

Skip this lens for high-level or early-stage specs that don't have technical detail yet.

---

**After the 7 lenses: Per-Entity Deep Scan**

The 7 lenses scan breadth-first (checking one concern across all features). This catches
category-level gaps but misses depth gaps — where a single feature looks complete but its
interfaces, states, and connections aren't fully specified.

After running all 7 lenses, do a **depth-first pass** on every entity in the spec:

**For each API endpoint:**
- [ ] Request: method, path, params/body with types, required vs optional
- [ ] Response: success shape (JSON structure), status code
- [ ] Errors: every error response with status code, body, and user-facing message
- [ ] Auth: which role(s) can call this, what happens if unauthorized
- [ ] Validation: what happens with invalid input (before it hits the database)
- [ ] Rate limiting: specified or explicitly N/A

**For each database table/schema:**
- [ ] Every column's allowed values documented (especially status/enum columns)
- [ ] Every status value mentioned ANYWHERE in the spec exists in the column's allowed values
- [ ] Indexes specified for columns used in WHERE clauses
- [ ] Cascade behavior on delete (especially for user/tenant deletion)

**For each third-party integration:**
- [ ] Happy path: how it works when the service is up
- [ ] Auth failure: invalid/expired credentials (401)
- [ ] Rate limit: what happens at the limit (429)
- [ ] Billing failure: insufficient credits/quota (402)
- [ ] Total outage: service is completely down (timeout/5xx)
- [ ] User-facing message for each failure mode

**For each user lifecycle state:**
- [ ] Entry condition: how does the user get INTO this state?
- [ ] Exit conditions: ALL ways the user leaves this state (including background jobs, expiry, admin action)
- [ ] What happens to in-flight operations when state changes (running jobs, open sessions, unsaved work)
- [ ] What the user SEES in this state (not just what the system does)

**For each status/enum field:**
- [ ] Every value mentioned anywhere in the spec is in the field's allowed values list
- [ ] Transitions between values are defined (which transitions are valid)
- [ ] Terminal states identified (which values are final)

This depth pass catches the class of issues where "feature X is specified" but "feature X's
POST endpoint has no response format" or "feature X mentions status 'waiting_for_api' but the
schema only allows 'pending', 'running', 'completed', 'failed'."

**When to run the depth pass:**
- Always run on specs with technical detail (schema, API endpoints, data flows)
- Skip for high-level or early-stage specs (no entities to deep-scan yet)
- For large specs (20+ endpoints, 10+ tables), run the depth pass on the 5 most complex
  entities first, then expand if the user wants more coverage

---

**Output:**

Present findings as a numbered list grouped by severity:

```
## Spec Review: [spec name]

### Critical (will cause rework)
1. [Finding] — [why it matters] — [suggested fix]
2. ...

### Major (likely edge case bugs)
3. [Finding] — [why it matters] — [suggested fix]
4. ...

### Minor (polish)
5. [Finding] — [why it matters] — [suggested fix]

### Execution Gaps (from SPEC-GAPS.md)  ← only if --include-gaps
6. [GAP-001] Agent assumed X during execution — confirm or correct
```

**Per workflow preferences: review only, never auto-fix.** Present findings and ask which to address.

If `--include-gaps` is used, also read SPEC-GAPS.md and surface all OPEN gaps as additional
findings. These represent real ambiguities discovered during execution -- highest signal items.

---

### Mode 3: Tighten (`/spec tighten`)

**When:** Spec exists but acceptance criteria are weak, vague, or missing.

**Flow:**

1. Read the spec
2. Extract every requirement/feature
3. For each, evaluate its acceptance criteria using the **5-point checklist:**
   - **Testable?** Could a test (automated or manual) verify this?
   - **Observable?** Described from the user's perspective, not implementation details?
   - **Unambiguous?** Would two engineers agree on pass/fail?
   - **Complete?** Covers happy path, error path, AND edge cases?
   - **Bounded?** Has specific values, not adjectives (numbers, formats, timeouts)?
4. Classify each criterion:
   - **Strong (5/5):** Leave alone
   - **Weak (2-4/5):** Rewrite with specific deficiencies noted
   - **Missing (0-1/5 or absent):** Generate from scratch
5. Present side-by-side: original vs tightened criteria with which checks failed
6. User confirms, adjusts, or rejects each change

**Tightening rules:**
- Replace "should" with "must" or remove the requirement
- Replace adjectives ("fast", "secure", "robust") with measurable targets
- Replace passive voice ("errors are handled") with active user-observable behavior ("user sees error toast with message and retry button")
- Split compound criteria ("system is fast and reliable") into separate testable items
- Add error/edge criteria to any acceptance criterion that only covers the happy path
- For every user-facing action: specify what the user SEES (not just what the system does)

**Per-entity tightening (depth pass):**

After tightening individual criteria, check for entity-level gaps:

- **API endpoints:** Does every endpoint have request format, response format, AND error responses specified?
- **State transitions:** Does every status change have a trigger, a resulting state, AND what the user sees?
- **Third-party calls:** Does every external dependency have a timeout and a failure behavior?
- **Data fields:** Does every user-editable field have validation rules and error messages?

**Example transformations:**

| Before | After | Failed Checks |
|--------|-------|---------------|
| "Dashboard loads quickly" | "Dashboard renders initial data within 2 seconds on 3G connection" | Bounded, Testable |
| "Secure authentication" | "Passwords hashed with bcrypt (cost 10+), JWT with 15-min expiry, refresh token rotation" | Bounded, Complete |
| "Handle errors gracefully" | "API errors return structured JSON {error, message, code}, 4xx for client errors, 5xx for server errors, user sees toast notification with actionable message" | Observable, Bounded |
| "Support file uploads" | "Accept PNG/JPG/PDF up to 10MB, validate MIME type server-side, show upload progress, reject with specific error message on failure" | Bounded, Complete |
| "Users can manage their profile" | "User can edit: display name (1-50 chars), email (validated, confirmation required), avatar (PNG/JPG, max 2MB, cropped to 200x200). Changes save within 1s. Invalid input shows inline error below the field." | Complete, Observable, Bounded |

---

### Mode 4: GSD Bridge (`/spec gsd`)

**When:** User has a SPEC.md (from this skill or manually written) and wants to feed it into
GSD for execution. Transforms SPEC.md into GSD's expected format.

**Flow:**

1. Read the SPEC.md
2. Run the validator script: `python3 ~/.claude/skills/spec/scripts/validate_spec.py SPEC.md`
3. If score < 7/10, warn user and suggest tightening first
4. Transform into GSD format:

**SPEC.md → GSD mapping:**

| SPEC.md Section | GSD Target | Transformation |
|-----------------|-----------|----------------|
| Overview + Core Value | PROJECT.md "What This Is" + "Core Value" | Direct copy |
| Must Have requirements | REQUIREMENTS.md (v1, with checkboxes) | Convert REQ-IDs to GSD format (CATEGORY-NN) |
| Should Have requirements | REQUIREMENTS.md (v1, lower priority) | Same, marked as lower priority |
| Won't Have | REQUIREMENTS.md "Out of Scope" table | Convert to Feature + Reason table |
| Constraints | PROJECT.md "Constraints" | Direct copy with WHY preserved |
| Anti-Requirements | PROJECT.md "Out of Scope" or constraints | Merge into constraints where relevant |
| Edge Cases | Distributed into phase CONTEXT.md | Allocated to relevant phases during planning |
| Open Questions | PROJECT.md "Context" or flagged for discuss-phase | Unresolved questions surfaced during phase discussion |
| Users & Entry Points | PROJECT.md "Context" | Added as user context |
| Acceptance Criteria | REQUIREMENTS.md per-requirement detail + phase success criteria | Acceptance criteria become success criteria in ROADMAP.md |

5. Output the transformed files to `.planning/` directory
6. Suggest running `/gsd:plan-phase` next

**The key insight:** Acceptance criteria from SPEC.md become the `must_haves.truths` in GSD's
PLAN.md. This means specs with strong acceptance criteria produce better GSD plans automatically.

---

### Mode 5: Validate (`/spec validate`)

**When:** User wants a programmatic quality check on their spec.

**Flow:**

1. Run: `python3 ~/.claude/skills/spec/scripts/validate_spec.py <spec-path> [--gaps]`
2. Present the report to the user
3. If score < 7, suggest specific improvements

The validator checks:
- Structural completeness (required sections present)
- Acceptance criteria coverage (every requirement has testable criteria)
- Ambiguity detection (vague language patterns like "handle errors", "should", "etc.")
- Edge case coverage
- Anti-requirements presence
- Execution gaps (if `--gaps` flag and SPEC-GAPS.md exists)

Run after generate, after review, or any time to check spec health.

---

## Examples

Reference examples are in `~/.claude/skills/spec/examples/`:

| Example | What It Shows | Why It's Valuable |
|---------|---------------|-------------------|
| `example-from-artifacts.md` | **Artifact-to-spec transformation.** User provides a meeting transcript, competitor reference, and one-liner. Skill extracts requirements from all three, asks ONE question, produces a complete spec with self-review. | Demonstrates the core differentiator: propose-then-react, not interview. Shows exactly what gets extracted from each artifact type. |
| `example-subtle-gaps.md` | **Reviewing a spec that looks complete.** A well-written permissions spec with acceptance criteria, edge cases, and constraints. Review catches 7 findings including 3 critical issues: content ownership ambiguity, cross-user permission gaps, and mid-session role change race condition. | Shows the skill finds gaps a junior reviewer would miss. Every finding passes the "two engineers would build this differently" test. |
| `example-feedback-loop.md` | **The full living document cycle.** Notification system spec goes through execution. Agent hits 4 ambiguities, logs them to SPEC-GAPS.md with options and assumptions. User resolves all 4 in one sentence. Spec updates. | Demonstrates the novel SPEC-GAPS.md feedback loop that no other spec tool provides. Shows how execution-discovered gaps are structured, resolved, and fed back. |

Use these as calibration when generating or reviewing specs.

---

## SPEC.md Output Format

```markdown
# [Project/Feature Name] — Specification

> Status: Draft | Reviewed | Execution-Ready
> Created: YYYY-MM-DD
> Last updated: YYYY-MM-DD

## Overview
[2-3 sentences: what is this, who is it for, why does it matter]

## Core Value
[The ONE thing that cannot fail. Everything else is negotiable.]

## Users & Entry Points
| User Type | Entry Point | Primary Goal |
|-----------|-------------|--------------|
| [type] | [how they get here] | [what they need] |

## Requirements

### Must Have
- **[REQ-ID]**: [Requirement description]
  - **Acceptance Criteria:**
    - [ ] [Testable, observable criterion]
    - [ ] [Testable, observable criterion]

### Should Have
- **[REQ-ID]**: [Requirement description]
  - **Acceptance Criteria:**
    - [ ] [Testable, observable criterion]

### Won't Have (this version)
- [Feature] — Reason: [why excluded]

## Edge Cases & Error States
| Scenario | Expected Behavior |
|----------|-------------------|
| [edge case] | [what happens] |
| [error state] | [what user sees] |

## Constraints
- [Technical constraint + why]
- [Business constraint + why]
- [Timeline constraint + why]

## Anti-Requirements
[What this explicitly is NOT. Prevents scope creep.]
- This is NOT [thing it might be confused with]
- This does NOT [thing someone might assume]

## Open Questions
[Anything still genuinely unresolved — flag, don't guess]
- [ ] [Question that needs a decision]

## Artifacts Referenced
[URLs, transcripts, mockups, competitor products that informed this spec]
- [artifact]: [what was extracted from it]
```

---

## SPEC-GAPS.md Format (Execution Feedback)

This file is written by execution agents (GSD executor, Ralph) when they hit spec ambiguities.
The spec skill reads it during `review --include-gaps` to surface real-world gaps.

```markdown
# Specification Gaps — Discovered During Execution

## GAP-001 [OPEN|RESOLVED]
- **Discovered by**: [agent type], [phase/iteration], [task/step]
- **Timestamp**: [YYYY-MM-DD HH:MM]
- **Context**: [What was being built when the gap was hit]
- **Gap**: [What the spec doesn't cover]
- **Options**: (a) [option] (b) [option] (c) [option]
- **Assumed**: [What the agent chose and built]
- **Severity**: [Critical|Major|Minor] — [why this severity]
- **Resolved**: [date + decision, if resolved]
- **Spec Updated**: [yes/no — was SPEC.md updated to reflect resolution]
```

**Severity definitions:**
- **Critical**: Wrong assumption means significant rework or data loss
- **Major**: Wrong assumption means bugs in edge cases
- **Minor**: Wrong assumption means cosmetic or UX inconsistency

---

## Integration Points

### With GSD

**For GSD executor** — add to PLAN.md prompt instructions:
```
When the spec is ambiguous about what to build:
1. Check if SPEC-GAPS.md exists and has a prior resolution for this gap
2. If not, choose the most reasonable option
3. Log your assumption to SPEC-GAPS.md with severity rating
4. Continue execution — do NOT stop unless severity is Critical AND
   you have accumulated 3+ critical open gaps
```

**For GSD verify-work** — after phase completion:
```
Check SPEC-GAPS.md for open gaps discovered during this phase.
Include them in VERIFICATION.md under "Assumptions Made (Need Confirmation)".
```

**For GSD plan-phase** — during planning:
```
Read SPEC-GAPS.md if it exists. Resolved gaps inform planning decisions.
Open gaps from prior phases should be flagged to user before planning continues.
```

### With Ralph

**For Ralph PROMPT.md** — include instruction:
```
When the specification is ambiguous:
- Make a reasonable assumption and continue
- Append your assumption to specs/SPEC-GAPS.md
- Do NOT stop or ask — log and proceed
```

**For Ralph loop script** — between iterations:
```bash
# Check critical gap accumulation
if [ -f specs/SPEC-GAPS.md ]; then
  critical=$(grep -c '\[OPEN\]' specs/SPEC-GAPS.md | grep -c 'Critical' || echo 0)
  if [ "$critical" -gt 3 ]; then
    echo "Warning: $critical critical spec gaps. Review specs/SPEC-GAPS.md"
    read -p "Continue? (y/n) " choice
    [ "$choice" != "y" ] && break
  fi
fi
```

### Standalone

Works independently of any execution framework. User writes or provides a spec,
skill reviews/tightens it, outputs an improved version.

---

## Domain-Aware Generation

When generating specs for common domains, use web research to surface requirements
the user likely hasn't considered:

| Domain | Common Hidden Requirements |
|--------|---------------------------|
| Payments/Billing | Failed payment retry, dunning emails, proration, tax handling, refund flow, webhook idempotency |
| Authentication | Token refresh, session invalidation, password reset flow, rate limiting, account lockout, MFA |
| File Upload | MIME validation, virus scanning, storage limits, progress indication, resume interrupted uploads |
| Email/Notifications | Bounce handling, unsubscribe, rate limiting, template management, delivery tracking |
| API Design | Pagination, rate limiting, versioning, error format, auth, CORS, idempotency keys |
| Real-time/WebSocket | Reconnection, message ordering, presence, backpressure, offline queue |
| Multi-tenant | Data isolation, tenant-scoped queries, billing per tenant, tenant admin vs super admin |
| Search | Indexing strategy, relevance ranking, facets/filters, empty results UX, typo tolerance |

This is not a checklist to force on the user. It's a knowledge base to draw from when the
domain matches, surfacing relevant items the user can confirm or dismiss.

---

## Dependency Check

- **Required**: None (pure prompt-based skill, no external packages)
- **Optional**: WebSearch/WebFetch for domain research and artifact ingestion
- **Optional**: Playwright MCP for URL artifact ingestion (competitor sites, web apps)

---

## Input Validation

Before starting any mode:
1. **Generate**: Verify at least one input exists (idea description, URL, file, transcript). If nothing provided, ask "What are we building?"
2. **Review**: Verify spec file exists and is readable. If path invalid, check common locations (./SPEC.md, .planning/SPEC.md, specs/SPEC.md)
3. **Tighten**: Same as review, plus verify spec has identifiable requirements (not just prose)

---

## Error Handling

- If URL fetch fails during artifact ingestion: log warning, continue with other inputs
- If web research fails during domain-aware generation: skip domain enrichment, note it in output
- If spec file not found: suggest common locations, ask user to provide path
- Never lose a partial draft — if generation is interrupted, output what exists so far

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/{project}/memory/spec.md`

### Loading (at start)
Before any mode, check for saved preferences:
- User's preferred spec format or sections
- Domain expertise level (adjusts how much domain research to include)
- Common constraints they always want included (e.g., "always consider accessibility")
- Preferred acceptance criteria style
- Review severity calibration (do they find certain lens findings useful vs noisy?)

### Saving (after each run)
After completion, save:
- Format preferences expressed ("I prefer shorter specs", "always include anti-requirements")
- Domain patterns the user confirmed as relevant (build domain knowledge over time)
- Review lens calibration (which findings did user act on vs dismiss?)
- Tightening style preferences (measurement targets, threshold values the user chose)

### What NOT to save
- Actual spec content (it's in the file)
- Project-specific requirements (they're in SPEC.md)
- Sensitive business details

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-19 | Initial version: generate (propose-then-react), review (6 lenses), tighten (acceptance criteria), SPEC-GAPS.md format, GSD/Ralph integration points, domain-aware generation |
| 1.1 | 2026-03-19 | Added: validate_spec.py script, GSD bridge mode (Mode 4), validate mode (Mode 5), 3 worked examples, artifact extraction specifics table, GSD executor Rule 5 (SPEC-GAPS.md logging) |
| 1.2 | 2026-03-19 | Review lens overhaul from field testing: Lens 1 adds absent-spec detection. Lens 2 adds API contract completeness. Lens 3 adds schema-vs-flow consistency. Lens 5 adds state transition personas. Lens 6 adds third-party resilience, legal, operations. New Lens 7: cross-reference consistency. |
| 1.3 | 2026-03-19 | Added per-entity deep scan after 7 lenses (depth-first pass). Addresses multi-round convergence problem: 7 lenses scan breadth-first (one concern across all features), deep scan checks each entity's full contract (API endpoints, schema columns, third-party failure modes, lifecycle states, status enums). Reduces review rounds from 5-8 to 1-2 for technical specs. |
| 1.4 | 2026-03-20 | **Tighten mode overhaul:** 5-point checklist (testable, observable, unambiguous, complete, bounded) replaces binary strong/weak classification. Per-entity tightening depth pass added (mirrors review's deep scan). Failed checks shown in output. **GSD verifier wired to SPEC-GAPS.md:** New Step 6b reads SPEC-GAPS.md, surfaces open assumptions in "Assumptions Made" section, Critical gaps block `passed` status. |
