# Concept Brief: Agent Resilience Patterns

> Generated: 2026-03-28
> Mode: Competitive Analysis
> Source: ByteDance deer-flow (50K+ stars, MIT license, v2.0)
> Artifacts Ingested: deer-flow middleware pipeline, agent harness architecture, deep-research skill, Flywheel hooks system, skill execution gateway, context store protocol

## Problem Statement

Flywheel's skill execution relies on Claude Code's native agent system with 5 ad-hoc hooks for contract enforcement, attribution tracking, and cost verification. This works, but has three gaps that will become critical as the platform scales, especially for Autopilot (autonomous long-running loops):

1. **No loop detection** -- agents can repeat the same tool calls indefinitely without intervention, wasting tokens and time. This is a common failure mode in long-running autonomous workflows.

2. **No context summarization** -- long skill runs hit context window limits with no graceful degradation. The agent either loses early context silently or fails entirely.

3. **No structured research completeness gate** -- research skills (account-research, meeting-prep) produce output without verifying coverage. There's no systematic check for "did we actually explore enough angles before synthesizing?"

These gaps are manageable in human-supervised CLI usage but become blockers for Autopilot's autonomous execution loop.

## Proposed Approach

Cherry-pick three architectural patterns from deer-flow's middleware system. Implement natively in Flywheel v2's execution gateway -- no dependency on LangGraph or deer-flow code.

### Pattern 1: Middleware Chain Architecture

**What deer-flow does:** 12-layer composable middleware pipeline. Each concern (guardrails, summarization, loop detection, token tracking, clarification) is an isolated layer that wraps the agent execution loop.

**What Flywheel should do:** Formalize the existing 5 hooks into a typed middleware chain in the v2 execution gateway (`skill_executor.py`). Each middleware gets a `before()` and `after()` hook with access to the execution context.

```
SkillRun request
  → InputValidationMiddleware (existing: contract-enforce)
  → RecipeLookupMiddleware (existing: recipe-lookup)
  → LoopDetectionMiddleware (NEW)
  → ContextSummarizationMiddleware (NEW)
  → AttributionMiddleware (existing: attribution-track)
  → CostVerificationMiddleware (existing: cost-verify)
  → Core skill execution
  → PostWriteValidationMiddleware (existing: post-write-validate)
```

**Key design decision:** Middleware is ordered and composable. Adding a new concern means adding a new class, not modifying existing hook scripts.

### Pattern 2: Loop Detection

**What deer-flow does:** `LoopDetectionMiddleware` tracks recent tool calls and detects repetitive patterns (same tool with same/similar arguments called N times in a window).

**What Flywheel should do:** Track the last N tool calls per skill run. If the same tool+args pattern repeats more than a configurable threshold (default: 3), inject a system message forcing the agent to take a different approach or terminate with a diagnostic.

**Implementation surface:** Single module in `backend/services/middleware/loop_detection.py`. Operates on the tool call log already captured by attribution tracking.

**Complexity:** Low. Pattern matching on a sliding window of tool calls.

### Pattern 3: Research Completeness Gate

**What deer-flow does:** 4-phase research protocol with explicit synthesis check:
1. Broad exploration -- survey, identify dimensions
2. Deep dive -- targeted searches per dimension, multiple keyword phrasings
3. Diversity and validation -- gather 6 info types (facts, examples, opinions, trends, comparisons, criticisms)
4. Synthesis check -- verify: 3-5+ angles searched? Important sources read in full? Concrete data collected? Both benefits AND limitations explored?

**What Flywheel should do:** Add a `ResearchCompletenessGate` to research-heavy skills (account-research, meeting-prep, company-intel). Before synthesis/output generation, run a checklist:

- Minimum source diversity (web + context store + documents)
- Minimum angle coverage (not just one dimension of the company/person)
- Presence of concrete data (numbers, dates, specifics -- not just qualitative summaries)
- Contradiction check (if all findings agree perfectly, coverage is likely too narrow)

**Implementation surface:** Shared utility in `backend/services/research_gate.py`, called by skill executors before the synthesis stage. Returns pass/fail with a gap list; on fail, the skill executor can loop back for additional research or flag gaps in output.

**Complexity:** Medium. Mostly prompt engineering for the checklist, plus a validation pass over extracted context entries.

## What We Explicitly Skip

These deer-flow features were evaluated and rejected:

| Feature | Why Skip |
|---|---|
| LangGraph runtime | Would replace Claude Code's native agent system for marginal gain. Massive dependency. |
| Context summarization middleware | Revisit when Autopilot ships. Not needed for current human-supervised skill runs where context resets per session. |
| Podcast/video generation | Content creation, not intelligence. Not aligned with Flywheel's compounding knowledge mission. |
| AI-generated slide images | Not editable. Worse than Flywheel's text-based pptx skill for business use. |
| 27 chart types engine | Dashboard/HTML output already handles visualization adequately. |
| Sandbox/Docker execution | Breaks local context store workflow. Flywheel runs in the user's environment by design. |
| IM integrations (Telegram/Feishu) | Slack skill already exists. Adding more channels is GTM distraction. |

## Effort Estimate

| Pattern | Effort | Dependencies |
|---|---|---|
| Middleware chain refactor | 2-3 days | None -- refactors existing hooks |
| Loop detection | 1-2 days | Middleware chain (or can be standalone module) |
| Research completeness gate | 0.5-1 day | None -- enhances existing skill executors |
| **Total** | **4-6 days** | |

## Prerequisites

- Current Flywheel v2 must be stable and flawless before any of these changes
- Integration sync RCA fixes should land first (the 5 cascading failures)
- Autopilot architecture gaps (6 open) should be resolved -- these patterns directly support Autopilot

## Success Criteria

1. No skill run repeats the same failing tool call more than 3 times without intervention
2. Research skills produce output with verifiable coverage across multiple angles
3. Adding a new middleware concern requires adding one file, not modifying existing hooks
4. Zero regression in existing skill behavior -- all 40+ skills work unchanged
