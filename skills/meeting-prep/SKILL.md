---
name: meeting-prep
version: "4.0"
description: >
  Full-depth bidirectional meeting preparation skill. Supports 8 meeting types
  (discovery, follow-up, investor, advisory, partnership, customer success,
  internal, hiring) with type-specific hypothesis, questions, and briefing
  sections. Handles multi-person meetings with group dynamics mapping and
  per-person question allocation. Reads compounded knowledge from the context
  store, researches contacts via web, performs multi-entity orbit mapping with
  fit screening, and produces comprehensive HTML briefings. Writes research
  intelligence back to 4 context files.
context-aware: true
triggers:
  - manual
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
    # Transcripts read from TRANSCRIPT_DIRS in meeting_prep.py (not context store files)
output:
  - meeting-prep-briefing-html
  - context-store-cross-references
  - research-intelligence-writes
---

# meeting-prep

You are preparing a meeting briefing using the **flywheel-powered** meeting preparation pipeline. This skill adapts to **8 meeting types** (discovery, follow-up, investor, advisory, partnership, customer success, internal, hiring) and handles **multi-person meetings** as a first-class concept.

Core pipeline: load context -> gather attendees -> detect prior history -> research attendees -> type-specific hypothesis -> type-specific questions/answers -> HTML briefing -> write intelligence back.

**Trigger phrases:** "prep for meeting", "meeting prep", "prepare for call", "brief me on", "who am I meeting", "prepare for my meeting with", "meeting brief", or any reference to preparing for an upcoming meeting or call.

---

## Step 0: Verify Dependencies & Load Context Store

### 0a: Dependency Check (fail fast)

```python
import sys, os

# Verify engine module exists and imports cleanly
engine_path = os.path.expanduser("~/.claude/skills/_shared/engines")
if not os.path.isdir(engine_path):
    print("FATAL: Engine directory not found at ~/.claude/skills/_shared/engines/")
    print("Action: Ensure the flywheel engine package is installed.")
    sys.exit(1)

sys.path.insert(0, engine_path)
try:
    from meeting_prep import (
        pre_read_context, find_contact_context, find_company_context,
        synthesize_meeting_context, format_context_briefing, generate_prep_report,
        write_research_to_context_store, write_contact_profile,
        WRITE_TARGETS
    )
    print("Engine: meeting_prep loaded OK")
except ImportError as e:
    print(f"FATAL: Cannot import meeting_prep engine: {e}")
    print("Action: Check ~/.claude/skills/_shared/engines/meeting_prep.py exists and has no syntax errors.")
    sys.exit(1)

# Verify context utils
ctx_utils = os.path.expanduser("~/.claude/skills/_shared/context_utils.py")
if not os.path.isfile(ctx_utils):
    print("WARNING: context_utils.py not found. Context store reads/writes will fall back to manual.")

# Verify context catalog
catalog = os.path.expanduser("~/.claude/context/_catalog.md")
if not os.path.isfile(catalog):
    print("WARNING: Context catalog not found at ~/.claude/context/_catalog.md")
    print("Context store integration will be limited. Continuing with web research only.")
```

### 0b: Load Context Store

```python
existing_context = pre_read_context("meeting-prep")
print(f"Loaded {len(existing_context)} context files")
for f, content in existing_context.items():
    entry_count = content.count("[20")  # rough entry count
    print(f"  {f}: ~{entry_count} entries")
```

Programmatically, pre-read via:
```
python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags people,sales,competitors,customer --json
```

Show the user what was loaded (file count, rough entry count per file).

Also load supplementary context for hypothesis synthesis:
- Read `product-modules.md` for product inventory (modules, capabilities, differentiation)
- Read `positioning.md` for value propositions and messaging
- Read `competitive-intel.md` for competitive landscape
- Read `market-taxonomy.md` for vertical context and industry classification

## Step 1: Get Meeting Details & Build Attendee List

Ask the user for:
- **Who** they are meeting (names, companies -- may be multiple people)
- **Meeting purpose/type** (discovery, follow-up, investor, advisory, partnership, customer success, internal, hiring)
- **Desired outcome** (what do you want to walk away with?)
- **Specific topics** to cover or prepare for
- **LinkedIn URLs** or other links for research (optional)
- **Who from our side** is attending (if multiple -- for role assignment)

### 1a: Build the Attendee List

Structure attendees as a list. Single person = list of 1.

```
attendees_their_side = [
  {name, company, title, linkedin_url, role_in_meeting, is_primary},  # primary = most important
  ...
]
attendees_our_side = [
  {name, title, role_in_meeting},  # e.g., "CTO handles technical deep-dive"
  ...
]
is_multi_person = len(attendees_their_side) > 1 or len(attendees_our_side) > 1
primary_contact = attendees_their_side[0]  # the one marked is_primary
```

**Single attendee (most common):** `attendees_their_side` has 1 entry. Pipeline runs as normal.
**Multiple their-side attendees:** Research each person. Build group dynamics map. Allocate questions per person.
**Multiple our-side attendees:** Add "Who Covers What" section to briefing. Plan handoff moments.

If the user provides partial info (just a name), proceed with what is available. The context store may fill in company and other details.

### Step 1b: Input Validation Gate

Before proceeding to research, validate that enough information exists to produce a useful briefing:

| What We Have | Verdict | Action |
|---|---|---|
| Person name + company | **Proceed** | Full pipeline |
| Person name only (no company) | **Proceed with warning** | Search context store + web for company. Print: "No company specified. Searching context store and web..." |
| Company only (no person) | **Proceed as company-focused** | Skip Steps 3, 5 (person research, orbit map). Produce company briefing with industry context. Print: "Company-only prep. Skipping person research." |
| LinkedIn URL only | **Proceed** | Extract name + company from URL slug or page. |
| Nothing provided | **Stop** | Ask: "Who are you meeting? I need at least a name, company, or LinkedIn URL." |

Also detect **meeting type** using heuristics from `references/briefing-quality-checklist.md` Section 5. If ambiguous, ask: "This looks like a [type] meeting. Correct, or is it something else?"

Set `meeting_type` variable for use in Steps 7 and 8.

## Step 2: Prior Call Detection

Automatically detect whether this is a follow-up meeting by searching the context store.

### 2a: Extract Person Identifier

From the inputs gathered in Step 1, extract a name slug for matching:
- From LinkedIn URL: extract the slug (e.g., `linkedin.com/in/sean-beausoleil` -> `sean-beausoleil`)
- From person name: normalize to lowercase hyphenated (e.g., "Michelle Ashford" -> `michelle-ashford`)
- From company + role: use as fallback matching context

### 2b: Search Context Store for Prior Meetings

```python
contact_results = find_contact_context(contact_name, existing_context)
company_results = find_company_context(company_name, existing_context)
```

Check `contacts.md` for existing entries from the same company or person. Build prior call context showing:
- What was discussed previously
- What was promised or what changed since last meeting
- Relationship status and meeting count

**If prior context found:**
- Set `is_followup = true`
- Build prior call summary from context store entries
- Note meeting count based on entries in contacts.md and insights.md

**If no prior context found:**
- Set `is_followup = false`, `meeting_number = 1`
- Proceed as first meeting -- zero impact on pipeline

### 2c: Company-Level Intel Search

Separately search for context about the **same company** from **different people**. This surfaces intel from colleagues or other contacts at the same organization.

- Search contacts.md for other entries with the same company name
- Search competitive-intel.md for mentions of the company
- Search insights.md for meeting intelligence involving the company

This `company_intel` is distinct from the person's prior call context. Use it to sharpen questions (anonymize the source: say "we've learned" not "[Person B] told us").

## Step 2.5: Cross-Meeting Transcript Synthesis

Follow the full protocol in `references/transcript-synthesis.md` (Steps 2.5.1-2.5.5).

Key outputs from this step:
- `transcripts` list (may be empty -- graceful degradation to context-store-only)
- `tier` (quick/pattern/deep/none)
- `relationship_intelligence_html` (for Section 1.8 in the briefing)
- Relationship summary writeback to contacts.md (compounding)

## Step 2.6: Load or Run Call Intelligence

Follow the full protocol in `references/call-intelligence-integration.md` (Steps 2.6.1-2.6.4).

Key outputs from this step:
- `ci_file` (JSON dict or None)
- Call intelligence feeds into: Section 1.9 (summary), Step 6 (hypothesis), Step 7 (questions)

## Step 3: Research Attendees

**Loop over `attendees_their_side`.** Primary contact gets full research. Additional attendees get lighter research (name, title, role in meeting, likely concerns).

**For multi-person meetings (is_multi_person = true):**
After researching all attendees, build a **Group Dynamics Map**:
- **Decision maker:** Who has final authority?
- **Influencer:** Who shapes the decision maker's opinion?
- **Champion:** Who's pushing for this internally?
- **Blocker:** Who might resist?
- **Evaluator:** Who's doing technical/operational assessment?
- **Conflicting agendas:** Where do attendees' interests diverge?
- **Common ground:** What do all attendees agree on?

**For multi-person our-side:**
Build a **Role Assignment** section:
- Who covers what topic (e.g., "CTO handles architecture, CEO handles commercial")
- Planned handoff moments
- Unified messaging check (same numbers, same positioning)

### Primary Contact Research

### Follow-Up Conditional (is_followup = true)

If Step 2 detected prior context:

**DO NOT re-research their background from scratch.** Prior research exists in context store entries. Focus on:
- **Check for role/company changes:** Quick web search to detect if they've moved
- **Company news since last contact:** Web search limited to dates after last interaction
- **Open action items status:** Check if any commitments have public evidence of completion
- **Agenda focus:** Decide what to cover this call based on context store data

### First Meeting (is_followup = false)

**If no person info is available** (company-only prep), skip to Step 4 and produce a company-focused briefing.

**If LinkedIn URL is provided**, use it as the primary anchor for person research.

**If no LinkedIn but person details are provided** (name, title, etc.), use web search to find public info.

Search for:
- Person's name + company + title
- Their LinkedIn posts, articles, conference talks
- Prior companies, career trajectory, notable moves
- Published content, thought leadership

**Build the Person Dossier:**

| Field | Description |
|-------|-------------|
| Name & Title | Full name, current role |
| Company | Current employer |
| Career Arc | Key roles, how they got here, years in industry |
| Domain Expertise | What they know deeply |
| Public Voice | Things they've said, written, or shared publicly |
| Conversation Hooks | Mutual connections, shared interests, recent activity (2-3 specific openers) |
| Style Signals | Formal/casual, data-driven/narrative, technical/strategic |

## Step 4: Research the Company

Use web search and web_fetch on the company website. Research:
- Core business: what they do, products/services, value proposition
- Industry and sub-sector classification (cross-reference against market-taxonomy.md)
- Size signals: employee count, revenue range, locations, project volume
- Technology and tools (check careers pages, blog posts, case studies)
- Recent news: funding, acquisitions, leadership changes, product launches
- Regulatory context: what rules/compliance they navigate
- Industry headwinds: current challenges facing their sector

**Industry-specific signals to look for** (informed by market-taxonomy.md verticals):
- Construction: subcontractor counts, project types, insurance compliance
- Insurance/MGA: policy volume, carrier relationships, audit processes
- Energy: contractor management, safety compliance, environmental requirements
- Healthcare: vendor management, regulatory compliance
- Transportation/Logistics: fleet compliance, safety management
- Professional Services: client compliance requirements

## Step 5: Multi-Entity Orbit Mapping

**Read `references/meeting-types.md` for type-specific overrides to this step.** The default pipeline below applies to `discovery` type. Other types (investor, advisory, partnership, customer-success, internal, hiring) have their own Step 5 overrides that replace or modify the logic below.

This is the core architectural step for discovery/sales meetings. Instead of assessing fit for one company, map the person's entire professional orbit and screen each entity.

### 5a: Extract Meaningful Entities from Person's Background

From LinkedIn profile and research, build a structured map of every company/organization this person has meaningfully touched:
- Current company (primary)
- Past companies where they held director+ level roles, or spent 2+ years
- Board positions, advisory roles
- Companies they founded or co-founded
- Portfolio companies, subsidiaries, or affiliated entities mentioned in role descriptions
- Industry associations or groups where they're actively involved

**Exclude:** Internships, junior positions, short stints (<1 year unless C-suite), passive memberships.

**Output format:**
```
Entity Map:
1. [Current] Company A -- CEO (2025-present) -- Industry description
2. [Portfolio] Company B -- via Company A -- Sub-industry
3. [Advisory] Company C -- EIR (2025-present) -- Industry
4. [Board] Company D -- Board advisor -- Industry
5. [Previous] Company E -- VP (2015-2024) -- Industry description
```

### 5b: First-Pass Fit Screen on Each Entity

For each meaningful entity, do a quick fit screen against context store data:
- Cross-reference against icp-profiles.md for existing ICP signals
- Check market-taxonomy.md for industry classification
- Check competitive-intel.md for known tools/vendors

| Entity | Industry Match? | Size Signal | Pain Indicators | Fit |
|--------|----------------|-------------|-----------------|-----|
| Company A | Confirmed ICP | Mid-market | Strong pain signals | High |
| Company B | Emerging ICP | Unknown | Possible fit | Medium |
| Company C | No match | N/A | Network value only | Low |

**Scoring criteria:**
- **High fit**: Industry matches confirmed ICP, company size aligns, role suggests relevant pain
- **Medium fit**: Industry matches but size is edge case, or emerging ICP segment
- **Low fit**: No industry match, but relevant for network value or domain knowledge
- **No fit**: Completely unrelated industry

### 5c: Deep Research on High-Fit Entities

For entities scored High or Medium, do actual web research:
- Current operations, project types, geographic footprint
- Tech stack signals
- Recent news (major projects, incidents, leadership changes)
- Cross-reference against context store entries for any prior intelligence
- Entity-level search in contacts.md and insights.md

For Low-fit entities -- skip deep research but note them as conversation reference points.

### 5d: Person Fit Assessment

Separate from company fit. This answers: **Is this person relevant because of who they are, or just because of where they work?**

| Dimension | What to Assess |
|-----------|---------------|
| **Role relevance** | Decision-maker, influencer, day-to-day user, connector, or domain expert? |
| **Domain depth** | Do they understand the pain firsthand, or is it adjacent? |
| **Career signal** | Have they moved through roles that repeatedly touch the relevant domain? |
| **Comparative insight** | Having worked at multiple companies, can they compare approaches? |
| **Network value** | Who can they connect us to? Past companies, board connections, peers. |
| **Engagement type** | Product conversation, expert interview, advisory session, or relationship-building? |

**Person fit scoring:**
- **High**: Touches domain directly, has decision-making authority, works at a high-fit company
- **Medium**: Oversees domain (not hands-on), or at a medium-fit company, or expert without buying authority
- **Low**: No direct domain connection, but has network value or knowledge worth extracting

### 5e: Persona Category Assignment

Based on entity map and person assessment, assign a persona category:

| Category | Signals | Primary Interest |
|----------|---------|-----------------|
| `EXEC` | C-suite, VP-level, P&L owner | Portfolio visibility, governance, strategic risk |
| `PRACTITIONER` | Manager, coordinator, hands-on operator | Time savings, workflow efficiency, tool consolidation |
| `BROKER` | Insurance broker, agency principal | Differentiation, compliance as service, efficiency |
| `CARRIER` | Underwriting ops, audit leader, carrier exec | Cost reduction, accuracy, cash flow |
| `LEGAL` | General counsel, compliance officer | Regulatory risk, audit defensibility |
| `COMPLIANCE` | Compliance manager, risk officer | Gap detection, automated monitoring |
| `SAFETY` | Safety director, HSE manager | Incident prevention, regulatory adherence |
| `PROCUREMENT` | Procurement lead, vendor manager | Vendor lifecycle, onboarding efficiency |
| `FINANCE` | CFO, controller, finance director | Cost control, premium accuracy, reserve management |
| `HR` | HR director, workforce compliance | Workforce compliance, classification accuracy |
| `OPERATIONS` | COO, operations manager | Operational efficiency, process standardization |
| `ADVISOR` | Board member, mentor, investor, industry advisor | Strategic feedback, market validation, competitive landscape |

**Routing: what context to emphasize per persona:**

All persona-to-pain mappings read from context store at runtime -- not hardcoded. For each persona:
1. Read `icp-profiles.md` for ICP signals matching this persona's industry/role
2. Read `pain-points.md` for validated pain points in this persona's segment
3. Read `competitive-intel.md` for competitive tools in their domain
4. Read `positioning.md` for relevant value propositions
5. Read `product-modules.md` for module alignment

## Step 6: Hypothesis Synthesis

**Read `references/meeting-types.md` for type-specific hypothesis format.** The default below applies to `discovery` type. Other types use entirely different hypothesis structures (e.g., investor uses "Investor Angle", advisory uses "Decision/Dilemma Framing", customer-success uses "Account Status").

Synthesize everything from Steps 2-5 into a concise hypothesis block. This is the analytical core -- it connects:
- **Who they are** (contacts.md, person research)
- **What they struggle with** (pain-points.md, research findings)
- **What competitors they use** (competitive-intel.md, research findings)
- **How we can help** (positioning.md, product-modules.md)

This is the "why this meeting matters" section.

**Generate:**

```
HYPOTHESIS
-- Primary opportunity: [Which entity is the main fit? Why?]
-- Secondary angles: [Other high-fit entities from their background]
-- Person fit: [High/Medium/Low -- are they a buyer, user, expert, or connector?]
-- Engagement type: [Customer Discovery / Expert Insight / Channel-Partner / Advisory / Network Expansion]
-- Module alignment: [Which product module(s) are most relevant and why]
-- Key unknowns: [2-3 specific things we need to learn from this conversation]
-- Companies to reference: [Which companies from their background to mention]
-- Predicted objections: [2-3 likely pushback points based on context store data]
-- Company intel: [If company_intel found from context store, summarize. If none: omit.]
-- Prior context (follow-ups only): [If is_followup: summarize prior interactions. If first meeting: omit.]
```

**The key unknowns drive the questions.** If research already answers something, don't ask it. The unknowns are things research COULDN'T answer.

### 6b: Exposure & Value Synthesis

Using the persona category, module alignment, and context store data, synthesize a "Why This Matters" block:

**Exposure Risk** -- 2-4 quantified risk metrics relevant to this person's segment. Pull from:
1. `pain-points.md` -- validated pain data from real interactions
2. `icp-profiles.md` -- industry statistics and benchmarks
3. Step 4 company research -- tailored to this company's scale

**Pain Points for This Role** -- 3-5 bullet points from pain-points.md, ranked by evidence count.
If no validated data for this segment, flag as "pure discovery."

**What We Solve** -- 1-2 modules only from product-modules.md, described in this person's language using their entity names.

**The Pitch** -- Single paragraph, 2-3 sentences, second person, using their entity names and relevant figures.

## Step 7: Generate Questions or Answers (Type-Dependent)

**Read `references/meeting-types.md` for type-specific question/answer generation.** The paradigm flips by type:
- **Discovery/Follow-up/Advisory/Partnership/Customer Success:** Generate QUESTIONS (you're asking)
- **Investor/Hiring (being interviewed):** Generate ANSWERS (you're being asked) + a few questions for them
- **Internal:** Generate DISCUSSION QUESTIONS (you're facilitating)

**Multi-person question allocation (is_multi_person = true):**
- Total question budget: 10-12 for the meeting, NOT per person
- Tag each question with the intended respondent: `[For VP Eng]`, `[For Procurement]`, `[For all]`
- Sequence: start with common-ground questions, then role-specific ones
- Adapt depth to seniority: strategic for execs, operational for practitioners

**Default below applies to discovery/demo type.** Questions should be informed by ALL the research done above -- never ask something the research already answered.

Read `references/question-bank.md` as a prompt library for phrasing inspiration.

### Follow-Up Meeting Questions (is_followup = true)

Replace default structure with follow-up-specific blocks:

**Block 1 -- "Building on Prior Context" (2-3 questions):**
Follow up on commitments, action items, and events since the last interaction. Source from context store entries.

**Block 2 -- "Deepening Discovery" (4-5 questions):**
Go deeper into topics introduced but not fully explored. Rules:
- **Never repeat already-answered questions** -- check context store for topics covered
- **Reference their own context** -- use prior interaction data to show continuity
- **Calibrate rather than re-discover** -- refine understanding, don't start over
- **Probe gaps** -- what was hinted at but not elaborated?

**Block 3 -- "Strategic & Expansion" (3-4 questions):**
Entity names and context from prior interactions. Referrals, advisory formalization, next steps.

### First Meeting Questions (is_followup = false)

**Block 1: Post-Demo Reaction (2 questions):**
1. "What stood out to you?" -- Open-ended, let them lead.
2. "What's missing? What would you need to see?" -- Inversion, let them identify gaps.

**Block 2: Context & Validation (5-8 questions):**
Every question demonstrates you've done your homework.
- Never ask something research already answered
- Reference specific companies from their background
- Use context store data as calibration, not claims
- Probe the key unknowns from the hypothesis
- Use exposure risk figures as calibration anchors

**Question sources (pick the best 5-8):**
- From their **current company**: process, workflow, pain, tech stack, scale
- From their **career arc**: comparative insight across companies
- From **context store validation**: calibrate validated pain points, probe tool patterns, test emerging hypotheses
- From **entity-specific research**: reference specific findings

**Block 3: Strategic & Expansion (3-4 questions):**
- Company-specific references from their background
- Org structure probe
- Advisory frame
- Next step / proof-of-value offer

### Objection Preparation

**For follow-ups:** Check context store for objections they raised previously. Address specifically with evolved responses.

**For first meetings:** Based on persona category and context store data, list 2-3 most likely objections with response strategies.

Format:
```
If they say: "[Objection]"
Prepare: [Response strategy informed by positioning.md and competitive-intel.md]
```

### Question Quality Checklist

Before finalizing, verify each question:
- [ ] Is it specific to THIS person and THESE companies? (Uses names, tools, details)
- [ ] Does it ask something research COULDN'T answer?
- [ ] Does it serve a purpose? (Validates ICP, quantifies pain, reveals workflow, expands network)
- [ ] Would this person find it insightful? (Shows preparation)
- [ ] Is it demo-led? (Assumes they've seen the product)

## Step 8: Generate HTML Briefing

**Read `~/.claude/design-guidelines.md` before generating any HTML.** Follow the global design system for all visual output.

**Read `references/briefing-quality-checklist.md` before finalizing.** This is the quality calibration reference. Use it to:
1. Run universal quality gates against the briefing content
2. Run meeting-type-specific gates (using `meeting_type` from Step 1b)
3. Run multi-person gates if multiple attendees
4. Score each confidence dimension (research depth, outcome clarity, question quality, risk preparation, attendee coverage)
5. Calculate overall confidence score
6. Add Prep Gaps callout if any dimension scores below 7

### HTML Structure -- 10-Section Document

**Design philosophy:** This is a personal prep document. Optimize for **scanning speed** over visual polish. Think Notion page, not SaaS landing page.

**Overall page:**
- White background, single column
- Max-width container: `720px`, centered, with `padding: 48px 24px`
- Sections separated by `<hr>` with `border-top: 1px solid #E5E7EB` and `margin: 32px 0`
- No background alternation between sections

**Header block:**
- Logo (small, top left)
- Meeting type badge (e.g., "Discovery", "Investor", "Advisory") in brand color
- Follow-up badge (if is_followup): Green success badge: "Nth Meeting"
- **Single attendee:** Person name (H1), title + company below
- **Multi-person:** Meeting title (H1, e.g., "Philips CPQ Review"), attendee list below with names + titles
- Desired outcome (1 sentence, bold) -- from Step 1
- Meeting date. For follow-ups: append last interaction date.
- Badge row: meeting type, persona category (primary), engagement type, person fit, company fit
- Print button (top right)

**Section 0.5 -- Attendee Dossiers (multi-person only):**
If `is_multi_person`, add a section before the Executive Summary:
- Mini-card per attendee: name, title, role in meeting (decision maker/influencer/evaluator), 2-3 bullet background, likely concerns
- Group dynamics map: power structure visualization (who defers to whom)
- If `attendees_our_side` > 1: "Who Covers What" table (our person -> their topic -> handoff trigger)

**Section 0.5 is omitted for single-attendee meetings.**

**Section 1 -- Executive Summary / Hypothesis & Angle:**
- Structured bullet list
- Primary opportunity, secondary angles, person fit, engagement type, module alignment
- **Key unknowns** -- bold, highlighted. These drive the questions.
- Companies to reference

**Section 1.5 -- Prior Context Recap (follow-ups only):**
Blue info box with:
- What was covered in prior interactions
- Commitments made / action items
- Classification / fit assessment from prior data
- Relationship status summary

**Section 1.8 -- Relationship Intelligence (from Cross-Meeting Synthesis):**

If `relationship_intelligence_html` was generated in Step 2.5, insert it here.

Template:
```html
<div class="section" style="margin: 24px 0; padding: 20px; background: rgba(233,77,53,0.04); border-radius: 12px; border-left: 3px solid #E94D35;">
  <h2 style="margin-top: 0;">Relationship Intelligence</h2>
  <p class="tier-badge" style="display: inline-block; padding: 2px 10px; border-radius: 999px; background: #E94D35; color: white; font-size: 13px;">{TIER} synthesis from {N} prior meetings</p>
  {relationship_intelligence_html content}
</div>
```

If no transcripts were found (Step 2.5 was skipped), omit this section entirely — do NOT show an empty section or "no data" message.

**Section 1.9 -- Call Intelligence Summary (from call-intelligence skill):**

If `ci_file` was loaded in Step 2.6, render a structured summary of granular call intelligence. This is distinct from relationship intelligence (Section 1.8) -- it focuses on **what was decided and discussed**, not the relationship arc.

Template:
```html
<div class="section" style="margin: 24px 0; padding: 20px; background: rgba(59,130,246,0.04); border-radius: 12px; border-left: 3px solid #3B82F6;">
  <h2 style="margin-top: 0;">Call Intelligence</h2>
  <p style="display: inline-block; padding: 2px 10px; border-radius: 999px; background: #3B82F6; color: white; font-size: 13px;">{N} meetings analyzed, {date_range}</p>

  <h3>Key Decisions ({count})</h3>
  <table><!-- Chronological: Date | Decision | Decided By | Impact --></table>

  <h3>Technical Specifications Locked ({count})</h3>
  <ul><!-- Each spec as bullet with code-style values --></ul>

  <h3>Open Threads ({count})</h3>
  <table><!-- Topic | Status | Blocking? — sorted by blocking first --></table>

  <h3>Overdue Action Items</h3>
  <ul><!-- Only overdue items, with owner and original date --></ul>

  <p style="font-size: 12px; color: #6B7280;">
    Full report: <a href="file:///path/to/call-intelligence-report.html">View complete call intelligence</a>
    | Run <code>/call-intelligence</code> to refresh
  </p>
</div>
```

Render rules:
- **Decisions:** Show top 10 most impactful. If more exist, note "N more in full report."
- **Specs:** Group by domain. Show all locked specs.
- **Open threads:** Show all, sorted by blocking status. Highlight blocking items in warning color.
- **Action items:** Show only overdue items. If none overdue, show "All action items current."
- **Link to full report:** Include path to the HTML report from call-intelligence skill.

If `ci_file` was not loaded (Step 2.6), omit this section entirely.

**Section 2 -- Why This Matters (Exposure & Value):**
- Exposure Risk -- 2-4 bullet points with metrics and confidence tags
- Pain Points for This Role -- 3-5 bullet points ranked by evidence
- What We Solve -- 1-2 modules described in their language
- The Pitch -- 2-3 sentence tailored value proposition

**Section 3 -- Conversation Hooks:**
- 3 numbered hooks with bold opener + context
- Style signals as a single caption line

**Section 4 -- Key Background:**
- 6-8 bullet points covering career arc, education, expertise
- Only what's relevant to THIS conversation

**Section 5 -- Entity Map (Orbit Map):**
- High/Medium fit entities: paragraph each with fit badge, context, and conversation relevance
- Low fit entities: single line with network value note
- No fit entities: grouped in one line

**Section 6 -- Questions (10-15):**
- For follow-ups: "Building on Prior Context" (2-3), "Deepening Discovery" (4-5), "Strategic & Expansion" (3-4)
- For first meetings: "Post-Demo Reaction" (2), "Context & Validation" (5-8), "Strategic & Expansion" (3-4)
- Must-ask: `font-weight: 600`
- If-time-allows: `font-weight: 400`, muted color
- Follow-up prompts: indented, smaller font
- Purpose line: smallest font, muted

**Section 7 -- Objection Prep:**
- 2-3 items: bold objection text, then response paragraph
- Separated by light horizontal rules

**Section 8 -- Intel from Context Store:**
- Bullet list of relevant cross-referenced insights from context store
- Evidence counts showing how many prior interactions inform each insight
- "What to validate" summary
- If no prior context: note "First conversation -- no prior intelligence"

**Section 9 -- Quick Reference (print-friendly):**
- Compact section with brand-color top border
- Key-value: name, role, fit, pitch, top 5 must-ask, key unknowns
- Print CSS: show all sections, reduce fonts, max-width 100%, hide print button and sources

**Section 10 -- Sources (screen only, hidden on print):**
- List of all URLs used during research
- Small font, muted color, underlined links

### Linking Requirements

Every mention of a company, article, or profile should be a clickable link when a URL is available. Company/entity links use brand color, subtle/secondary links use muted color. Print: all links as plain text.

### Save & Deliver

Save the HTML briefing to a location that makes sense for the user's project structure.

**Always end with the deliverables block:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Briefing (HTML):  /absolute/path/to/briefing.html
                    Open in any browser for the full prep doc

  Context writes:   [N] files updated in ~/.claude/context/
                    contacts.md, competitive-intel.md, industry-signals.md, icp-profiles.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 9: Write Research Intelligence to Context Store

After completing research (Steps 3-5), write discovered intelligence back to the context store. This is the bidirectional value -- every meeting prep enriches the knowledge base for future use.

```python
from meeting_prep import write_research_to_context_store, write_contact_profile

# Write contact profiles discovered during research
write_contact_profile(
    name="Full Name",
    title="Job Title",
    company="Company Name",
    relationship="prospect",  # or customer, advisor, etc.
    role="decision-maker",     # or champion, influencer, evaluator
    notes="Key observations from research"
)

# Write research intelligence to context store
research_data = {
    "contacts": [
        {"detail": "contact: firstname-lastname", "content_lines": [...], "confidence": "low"}
    ],
    "competitive_intel": [
        {"detail": "tools-at-company-name", "content_lines": [...], "confidence": "low"}
    ],
    "industry_signals": [
        {"detail": "signal-description", "content_lines": [...], "confidence": "low"}
    ],
    "icp_signals": [
        {"detail": "fit-signal-company-name", "content_lines": [...], "confidence": "low"}
    ]
}

results = write_research_to_context_store(research_data)
for target, result in results.items():
    print(f"  {target}: {result}")
```

Programmatically, append entries via:
```
python3 ~/.claude/skills/_shared/context_utils.py append contacts.md --source meeting-prep --detail "contact: [name]" --content "[lines]"
```

**What to write:**
- **contacts.md**: New contact profiles discovered during research (per-person schema: Name, Title, Company, Relationship, Role, Notes)
- **competitive-intel.md**: Tools/vendors the company uses (discovered from LinkedIn/website/careers pages)
- **industry-signals.md**: Regulatory trends, market shifts relevant to the company
- **icp-profiles.md**: Fit signals, persona categorization from research

**Write rules:**
- All writes tagged `source: meeting-prep-research` to distinguish from meeting-processor writes
- Default confidence: `low` (single-observation research data)
- Write failures do NOT block the main preparation pipeline (log error, continue)
- Check for existing entries before writing to avoid duplicates

## Step 10: Post-Meeting Connection

After generating the briefing, remind the user:

> After your meeting, say **"process my meeting notes"** to run the Meeting Processor skill.
> It will extract insights, update contacts, and grow the knowledge base.
> The more calls you prep and process, the sharper your prep gets -- the feedback loop is:
> **Prep -> Meeting -> Process -> Context Store update -> Better prep next time**

---

## Memory & Learned Preferences

Check for auto-memory file at `~/.claude/auto-memory/meeting-prep.md`. If it exists, load:
- Preferred briefing format (detailed vs concise)
- Key contacts and their companies (avoid re-asking)
- Meeting type preferences for recurring meetings
- Topics the user always wants covered

After generating a briefing, save any new learned preferences to the auto-memory file.

### Idempotency
- Before writing to context store: check for existing entry with composite key (contact + file + date)
- If duplicate found: skip write, log "duplicate skipped"
- Re-running prep for the same contact on the same day produces same context writes without duplicates

## Progress Updates

Report status at each milestone:
- "Researching [person name]... (1 of N attendees)"
- "Company intel gathered -- moving to recent news..."
- "Agenda drafted -- generating briefing document..."

For multi-attendee meetings, report after each person completes.

## Backup Protocol

Before writing to any context store file during post-write:
- Create `.backup.YYYY-MM-DD` of the target file before overwriting
- Keep last 3 backups
- If write fails, original file remains intact from backup

## Error Handling

- **Context store empty:** Fall back to web research only. Note: "Context store is empty. Process some meetings first to enable flywheel-powered briefings."
- **Context store read failure:** Log warning, continue with web research only
- **No web access:** Produce context-store-only briefing with available data
- **Contact not found in context store:** Normal for first meetings -- proceed with web research
- **Partial data:** Include whatever is available; never crash on missing data
- **Write failure:** Log error, continue pipeline. Write failures are non-blocking.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Guidelines

- **Be honest about unknowns.** If info isn't findable, say so. Never fabricate.
- **Privacy first.** Only use publicly available information.
- **Scale to context.** A 15-min coffee chat needs a lighter brief than a 45-min deep dive.
- **Questions are the product.** The question list is the most valuable section.
- **Entities first, product second.** Map the person's orbit before thinking about fit.
- **Research eliminates questions.** If research answers it, don't ask it.
- **Demo-led framing.** Assume the person has seen or will see the product.
- **Context store data is intelligence, not scripts.** Use it to inform, not to script.
- **Anonymize past insights.** Say "teams in this segment report..." not specific names.
- **Flag novel segments.** If first conversation in a segment, note it explicitly.
- **Reference real companies.** Use actual company names from their background.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 4.0 | 2026-03-17 | **Major refactor: meeting types + multi-person support.** Added references/meeting-types.md with type-specific overrides for Steps 5/6/7/8 across 8 meeting types (discovery, follow-up, investor, advisory, partnership, customer-success, internal, hiring). Step 1 now builds attendee list (their-side + our-side). Step 3 loops over attendees with group dynamics mapping for multi-person. Steps 5/6/7 route to type-specific logic. Step 7 paradigm flips for investor/hiring (answers, not questions). Step 8 adds Section 0.5 (Attendee Dossiers) for multi-person, meeting type badge, desired outcome in header. Backward compatible: single-person discovery meetings work exactly as before. |
| 3.8 | 2026-03-17 | Extracted Steps 2.5/2.6 to references/ (transcript-synthesis.md, call-intelligence-integration.md). Added dependency verification (Step 0a). Added input validation gate (Step 1b) with meeting type detection. Added briefing quality checklist (references/briefing-quality-checklist.md) with 8 meeting types, multi-person gates, and confidence scoring. Integrated quality gate into Step 8. |
| 3.7 | 2026-03-13 | Step 2.6 now auto-runs call intelligence inline for deep tier / deep dive requests; non-deep tiers use cache only |
| 3.6 | 2026-03-13 | Added Step 2.6 (Load Call Intelligence) and Section 1.9 (Call Intelligence Summary) for integration with standalone call-intelligence skill; JSON cache with 7-day TTL |
| 3.5 | 2026-03-13 | Moved relationship writeback from Step 9.3 to Step 2.5.5 (co-located with synthesis); added complete_synthesis() wrapper |
| 3.4 | 2026-03-13 | Added TRANSCRIPT_DIRS comment to frontmatter; documented cross-meeting synthesis in changelog |
| 3.3 | 2026-03-13 | Replaced hardcoded context file lists with context-aware: true; removed phantom context_utils.py engine reference |
| 3.2 | 2026-03-13 | Added Standard 8 (Progress Updates) and Standard 12 (Backup Protocol); Added Step 2.5 (Cross-Meeting Transcript Synthesis), Section 1.8 (Relationship Intelligence HTML), Step 9.3 (Relationship Writeback) |
| 3.1 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
