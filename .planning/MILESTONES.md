# Milestones

## v1.0 — Email Copilot ✓

**Goal:** Ship a dogfooding-ready email copilot that syncs Gmail, scores emails using context store, drafts replies in the user's voice, and provides a review UI for approval.

**Started:** 2026-03-24
**Completed:** 2026-03-25
**Phases:** 1-6 (core) + 48, 49, 49.1 (patches)
**Last phase number:** 49.1

**Key deliverables:**
- Gmail read sync with expanded OAuth scopes
- 5-tier email scoring using context store intelligence
- Voice-learned draft reply generation (Sonnet)
- Scored inbox UI with virtual list + draft approval flow
- Critical email toast alerts
- Feedback flywheel (edit-to-learn voice updates, re-scoring)

---

## v2.0 — AI-Native CRM ✓

**Goal:** Founders never lose track of an account again — a single screen with all contacts, timeline, commitments, intel, and next actions, all auto-populated from skill runs.

**Started:** 2026-03-26
**Completed:** 2026-03-27
**Phases:** 50-53 (4 phases, 9 plans)
**Last phase number:** 53
**Stats:** 63 files changed, +7,866 lines

**Key deliverables:**
- CRM data model — accounts, contacts, outreach tables with RLS and company name normalization
- Seed CLI — 206 real accounts, 235 contacts, 81 outreach activities from GTM stack files
- Full REST API — accounts/contacts CRUD, outreach pipeline, unified timeline, pulse signals, auto-graduation
- Accounts page — searchable, filterable, sortable table with pagination at `/accounts`
- Account detail — 3-column deep-dive with contacts panel, chronological timeline, intel sidebar, action bar
- Pipeline page — prospect triage with fit score ranking and Graduate action
- Sidebar navigation — Accounts and Pipeline links integrated into app shell
- Pulse signals — revenue-gated signal cards on Briefing page linking to accounts

---

## v2.1 — CRM Redesign: Intelligence-First Relationships ✓

**Goal:** Replace the flat accounts table with five distinct surfaces (Pipeline grid + Prospects/Customers/Advisors/Investors relationship pages), each with AI synthesis, interactive context panels, premium UI/UX, and a signal layer with badge counts.

**Started:** 2026-03-27
**Completed:** 2026-03-27
**Phases:** 54-58 (5 phases, 16 plans)
**Last phase number:** 58

**Key deliverables:**
- Data model evolution — relationship_type array + GIN index, entity_level, ai_summary cache fields, two-phase status rename
- Relationships & Signals APIs — partition predicate, rate-limited AI synthesis, badge counts
- Pipeline grid — AG Grid with filters, saved view tabs, graduation modal
- Four relationship surfaces — card-grid list + shared detail with type-driven tabs, AI context panel
- Unified Company Intelligence Engine — single skill engine for document uploads and URL crawls
- Design system tokens — shadows, badges, avatars, transitions

---

## v3.0 — Intelligence Flywheel ✓

**Goal:** Conversations automatically become CRM intelligence. Meetings sync from Granola, get classified and processed into 9 insight types across 7 context files, auto-link to accounts, and feed back into meeting prep briefings.

**Started:** 2026-03-28
**Completed:** 2026-03-28
**Phases:** 59-63 (5 phases, 13 plans)
**Last phase number:** 63

**Key deliverables:**
- Team Privacy Foundation — user-level RLS for emails, integrations, calendar, skill runs
- Meeting data model — split-visibility RLS, Granola adapter with encrypted API key, dedup sync
- Meeting Intelligence Pipeline — 8-type classification, 9 insight types, 7 context files, auto account linking
- Meeting surfaces — list/detail pages, timeline enrichment, intelligence tabs, contact discovery
- Meeting Prep Loop — context-aware briefings for upcoming meetings, closing the intelligence flywheel

---

## v4.0 — Flywheel OS ✓

**Goal:** Intelligence operating system for founders — unified meetings, task extraction from transcripts, and a single daily ritual that syncs, processes, preps, executes, and briefs.

**Started:** 2026-03-28
**Completed:** 2026-03-29
**Phases:** 64-66.1 (4 phases, 13 plans)
**Last phase number:** 66.1

**Key deliverables:**
- Unified meetings data layer — calendar events and Granola transcripts in one table with fuzzy dedup and lifecycle status
- Task intelligence — Stage 7 extracts commitments (yours/theirs/mutual) from transcripts, maps to executable skills
- Flywheel ritual engine — single MCP invocation runs 5 stages: sync → process → prep → execute → compose HTML brief
- Stabilization — 18 issues fixed (env var mismatch, migration FK, UTC timezone, N+1 query, Stage 4 guards, execution caps, optimistic lock, MCP timeout)

---


## v5.0 — Tasks UI ✓

**Goal:** Users can see, manage, and act on extracted tasks through a dedicated Tasks page with filtering, status tracking, and inline completion.

**Started:** 2026-03-29
**Completed:** 2026-03-29
**Phases:** 67 (1 phase, 7 plans)
**Last phase number:** 67

**Key deliverables:**
- Tasks page — filterable, sortable task list with status tracking and inline actions
- Task detail — full context with source attribution, deadline, assignee
- Task lifecycle — create, complete, snooze, dismiss with optimistic UI updates

---

## v6.0 — Email-to-Tasks ✓

**Goal:** Emails with action items automatically generate tasks, closing the loop between inbox triage and task execution.

**Started:** 2026-03-29
**Completed:** 2026-03-29
**Phases:** 68 (1 phase, 3 plans)
**Last phase number:** 68

**Key deliverables:**
- Email-to-task extraction — action items from scored emails become tracked tasks
- Task attribution — each task links back to source email thread
- Sync integration — task extraction wired into email scoring pipeline

---

## v7.0 — Email Voice & Intelligence Overhaul ✓

**Goal:** Transform email from a siloed draft engine into a bidirectional intelligence source that sounds like the user, shares voice across all skills, and feeds relationship/deal/contact intelligence back into the context store.

**Started:** 2026-03-30
**Completed:** 2026-03-30
**Phases:** 69-75 (7 phases, 13 plans)
**Last phase number:** 75
**Stats:** 41 files changed, +5,691 / -454 lines

**Key deliverables:**
- Per-tenant model configuration — all 5 email engines read LLM model from settings JSONB, defaulting to claude-sonnet-4-6
- Voice profile overhaul — 10 fields from 50 sent emails (formality, greeting style, paragraph patterns, emoji usage, question style, avg sentences)
- Voice Settings UI — view all 10 learned fields, edit tone/sign-off inline, Reset & Relearn with confirmation
- Draft enhancements — collapsible voice annotation badges, regenerate dropdown (shorter/longer/casual/formal/custom)
- Voice as context store asset — sender-voice.md written after extraction and updated on every incremental learning
- Email context extractor — extracts contacts, topics, deal signals, relationship signals, action items from priority 3+ emails
- Context extraction pipeline — wired into gmail sync loop with confidence routing (high/medium auto-write, low → review queue), 200/day per-tenant cap, 10/cycle batch limit, approve/reject API endpoints

---

