---
name: lumifai-meeting-prep
description: Pre-meeting research and interview prep for Lumif.ai discovery calls. Accepts any combination of inputs — LinkedIn URL, company name/URL, person details, or other relevant links — and produces a structured HTML briefing with tailored interview questions. Uses a layered context architecture: always loads a slim core brief, then maps the person's entire professional orbit, screens each entity for fit, and generates 10-15 demo-led questions informed by validated insights from past expert calls. Triggers on "prep for meeting", "research this person", "interview prep", "meeting brief", "call prep", LinkedIn URLs, company names, or any request to prepare for an upcoming conversation.
---

# Lumif.ai Meeting Prep

Generate a pre-meeting briefing by mapping a person's professional orbit, screening companies for fit, and producing 10-15 sharp, demo-led questions informed by past call intelligence.

## What This Skill Does

Takes flexible input (any combination of LinkedIn URL, company name/URL, person details, or relevant links) and produces a single HTML briefing:
- **Person dossier** — background, role, expertise, career arc, conversation hooks
- **Multi-entity map** — every meaningful company in their orbit, screened for Lumif.ai fit
- **Fit assessment** — company fit + person fit, evidence-based from research and past calls
- **10-15 demo-led questions** — specific, informed, no redundancy with what research already answers
- **Quick reference** — cheat sheet to glance at during the call

---

## Step 0: Gather Inputs

All inputs are optional — use whatever is provided. Ask the user for anything not already given:

1. **LinkedIn URL** (optional — ideal but not always available)
2. **Company name or URL** (optional — can be the primary starting point if no LinkedIn)
3. **Person details** (optional — name, title, role, or any context the user knows about them manually)
4. **Other relevant links** (optional — company website, news articles, conference bios, Twitter/X profiles, podcast episodes, blog posts, or any URL that provides context)
5. **Meeting context** (optional — alumni, cold outreach, warm intro, conference)
6. **Specific goals** (optional — anything particular they want to learn)

**Input scenarios and how to handle them:**

| What's Provided | Approach |
|-----------------|----------|
| LinkedIn URL only | Full person + company research from LinkedIn as anchor |
| LinkedIn URL + company | Full research, company info supplements LinkedIn |
| Company name/URL only (no person) | Company-focused briefing, skip person dossier or build minimal one from any provided details |
| Company + person name/title (no LinkedIn) | Web search for the person using name + company + title, build profile from public sources |
| Company + manual person notes | Use provided details as-is, supplement with web research where possible |
| Any combination + extra links | Use all provided links as additional research sources — fetch and extract relevant context from each |

**Key principle:** Work with whatever you have. A company-only prep is still valuable. A person prep built from manual notes + web search is still useful. Never block on missing a LinkedIn URL.

---

## Step 0.5: Prior Call Detection

Automatically detect whether this is a follow-up meeting by searching for prior transcripts and preps. This runs silently — no user prompting needed.

### 0.5a: Extract Person Identifier

From the inputs gathered in Step 0, extract a name slug for matching:
- From LinkedIn URL: extract the slug (e.g., `linkedin.com/in/sean-beausoleil` → `sean-beausoleil`)
- From person name: normalize to lowercase hyphenated (e.g., "Michelle Ashford" → `michelle-ashford`)
- From company + role: use as fallback matching context

### 0.5b: Search for Prior Transcripts

**If no person name slug could be extracted** (company-only prep), skip the person search (0.5b) and Prior Call Context (0.5c) — set `meeting_number = 1`, `is_followup = false`. But still run the company-level search (0.5b-2) if a company name is available — company intel is valuable even without a specific person.

**If the transcripts directory doesn't exist** (`/Users/sharan/Projects/lumifai/transcripts/`), skip Step 0.5 entirely — set `meeting_number = 1`, `is_followup = false`, and proceed to Step 1. This skill works standalone without any prior meeting infrastructure.

Search `/Users/sharan/Projects/lumifai/transcripts/` for filenames containing the person's name slug.

**Matching rules:**
- Match on person name slug anywhere in filename (e.g., `sean-beausoleil` matches `2026-02-19-sean-beausoleil-ex-rmr-group.md` AND `2026-02-26-sean-beausoleil-ex-rmr-group-followup.md`)
- Sort matches by date (earliest first) to establish chronological order
- Also search `/Users/sharan/Projects/lumifai/insights/meeting-prep-*.html` for prior prep files matching the slug

**Edge case — same person, different contexts (e.g., Jeff Carroll):**
- If multiple transcripts match but have different company contexts (e.g., `jeff-carroll-mit-advisor` vs `jeff-carroll-tartan-residential`), include ALL of them — the person carries context across roles
- When building Prior Call Context, note which context/company each prior call was in

### 0.5b-2: Company-Level Transcript Search

Separately from the person search, also search for transcripts involving the **same company** but with **different people**. This surfaces intel from colleagues, competitors, or other contacts at the same organization.

**How to search:**
- Extract company name slug from inputs (e.g., "Liberty Mutual" → `liberty-mutual`, "Scottish Water" → `scottish-water`)
- Search `/Users/sharan/Projects/lumifai/transcripts/` filenames for the company slug
- Exclude any transcripts already found in the person search (avoid double-counting)
- Also check the `_interview-index.md` file if it exists — it may list company names that don't appear in filenames

**If company-matched transcripts are found** (from different people):
- Read them and extract company-specific insights: processes described, tools mentioned, pain points, org structure, team names, compliance workflows
- Store as `company_intel` — this is NOT the same as `Prior Call Context` (it's a different person's perspective on the same company)
- Do NOT set `is_followup = true` based on company matches alone — follow-up status is person-specific

**How this feeds into the rest of the skill:**
- **Step 1**: When researching the company, cross-reference against `company_intel` — you already have insider knowledge from a prior call
- **Step 4 (Hypothesis)**: Add a line: `-- Company intel: [Person B] at [same company] discussed [key topics] on [date]. Key insight: [one sentence].`
- **Step 5 (Questions)**: Use `company_intel` to ask sharper questions — e.g., "We've learned that [company] uses [tool] for compliance — is that your experience too?" (anonymize the source: say "we've learned" not "[Person B] told us")
- **Step 6 (HTML)**: In Section 8 (Intel from Past Calls), include a subsection: **"Intel from [Company Name]"** with bullet points from the company-matched transcript. Anonymize the source person.

**Leverage `_interview-index.md` for enrichment:**
If `/Users/sharan/Projects/lumifai/transcripts/_interview-index.md` exists, read it and extract:
- **Referral connections:** Check the "Warm Lead" column — if the person being prepped was flagged as a warm lead in someone else's row, note who referred them and load that referring person's transcript for relationship context
- **Severity/classification pre-load:** If the person's primary company appears in the Company column, pull the severity rating and Painkiller/Vitamin classification from that row — use as a baseline expectation for the upcoming call
- **Segment pattern matching:** Count how many interviews exist in the same Category (e.g., "Insurance", "Construction") — this tells you how validated your playbook is for this segment

**If no company matches found:** Skip the company transcript search. The `_interview-index.md` enrichment above still runs independently (it doesn't depend on company matches).

**Example:** Prepping for Person A at Liberty Mutual. The company search finds `2026-02-10-edith-shi-liberty-mutual.md`. That transcript reveals Liberty Mutual's internal compliance workflow, tools they use, and pain points Edith described. This intel is loaded as `company_intel` and used to make questions for Person A much sharper — without revealing that Edith was the source.

### 0.5c: Build Prior Call Context

If prior transcripts are found, read ALL of them and extract:

```
PRIOR CALL CONTEXT
-- meeting_number: [2nd / 3rd / Nth — based on count of prior transcripts + 1]
-- prior_calls:
   Call 1: [date] — [company context] — [transcript path]
   Call 2: [date] — [company context] — [transcript path]
-- key_insights: [2-4 most important things learned about this person across all calls]
-- quotable_moments: [Direct quotes that reveal their thinking, pain points, or priorities]
-- topics_already_covered: [List of topics discussed — NEVER re-ask these]
-- open_action_items: [Intros promised, follow-ups scheduled, materials to send, things they said they'd do]
-- relationship_progression: [How the relationship has evolved — cold → warm → engaged → advisor, etc.]
-- prior_classification: [Their severity/painkiller classification from prior calls, if assessed]
-- prior_persona_category: [What persona category was assigned in prior prep/processing]
-- what_changed_since: [Time elapsed since last call — flag if >30 days as "check for updates"]
```

**If NO prior transcripts found:**
- Set `meeting_number = 1`
- Set `is_followup = false`
- Skill proceeds exactly as before — zero impact on first meetings

**If prior prep exists but no transcript:**
- The meeting was prepped but notes weren't processed (or meeting didn't happen)
- Load the prior prep HTML for context on what research was done
- Flag: "Prior prep found but no transcript — confirm if meeting occurred"

---

## Step 1: Research the Person

### Follow-Up Conditional (meeting_number >= 2)

If Step 0.5 detected prior calls (`is_followup = true`):

**DO NOT scrape LinkedIn, do web searches for the person, or re-research their background.** All person research was done in prior preps — load it from the person research cache (see Memory section) and prior transcripts. Re-scraping LinkedIn wastes time and adds no value for someone we've already met.

**What to SKIP entirely:**
- LinkedIn profile scraping (no Playwright, no WebFetch on linkedin.com)
- Web searches for person name + background
- Career arc discovery, education, certification lookups
- Building a new person dossier from scratch

**What to LOAD from cache/transcripts:**
- Person dossier from `/Users/sharan/Projects/lumifai/insights/prep-cache/{person-slug}.md`
- Prior transcript insights, quotable moments, open action items
- Entity map, company research, and fit assessments from the cached file

**What to DO instead (lightweight, focused research):**
- **Check for role/company changes:** Quick web search for `"[person name]" [last known company]` to detect if they've moved. If the person changed companies, research the NEW company only (proceed to Step 2 for the new company). If changed roles at same company, note it and re-evaluate persona category.
- **Company news since last call:** Web search for `"[company name]" [news/funding/launch]` limited to dates after `[last_call_date]`
- **Open action items status:** Check if any commitments from prior calls have public evidence of completion
- **Agenda focus:** The main effort should be on deciding what to cover this call — what follow-ups are due, what's changed, what wasn't fully explored last time

Then skip to Step 2 (only if company changed or company news warrants research).

### First Meeting (meeting_number = 1)

**If no person info is available** (company-only prep), skip to Step 2 and produce a company-focused briefing. The HTML output should omit the Person Brief section or show a minimal placeholder noting "No specific contact identified."

**If LinkedIn URL is provided**, use it as the primary anchor for person research.

**If no LinkedIn but person details are provided** (name, title, etc.), use web search to find public info. Also fetch any additional URLs the user provided (conference bios, Twitter/X, blog posts, articles, podcast links) and extract relevant context from each.

Search for:
- Person's name + company + title (from LinkedIn URL slug, provided info, or any links)
- Their LinkedIn posts, articles, conference talks, podcast appearances
- Prior companies, career trajectory, notable moves
- Published content, thought leadership, industry commentary

**Build the Person Dossier:**
| Field | Description |
|-------|-------------|
| Name & Title | Full name, current role |
| Company | Current employer |
| Career Arc | Key roles, how they got here, years in industry |
| Domain Expertise | What they know deeply (specific to their background) |
| Public Voice | Things they've said, written, or shared publicly |
| Conversation Hooks | Mutual connections, shared interests, recent activity (2-3 specific openers) |
| Style Signals | Formal/casual, data-driven/narrative, technical/strategic |

---

## Step 2: Research the Company

**Note:** This step researches the person's CURRENT company as a starting point. Step 3 will expand to ALL meaningful companies in their orbit.

Use web search and web_fetch on the company website. Research:
- Core business: what they do, products/services, value proposition
- Industry and sub-sector classification
- Size signals: employee count, revenue range, locations, project volume
- Technology and tools (check careers pages, blog posts, case studies)
- Recent news: funding, acquisitions, leadership changes, product launches
- Regulatory context: what rules/compliance they navigate
- Industry headwinds: current challenges facing their sector

**Industry-specific signals to look for:**

Construction/Insurance:
- Number of subcontractors, projects, or policies managed
- Insurance compliance mentions (COI, certificates, audits)
- Risk management team or processes
- Software stack (Procore, Sage, PlanGrid, ACORD, etc.)
- Workers' compensation or premium audit content
- Claims history mentions, loss runs, experience modification rate

Energy/Oil & Gas:
- ISNetworld or Avetta usage, contractor management scale
- OSHA Process Safety Management mentions
- MSA complexity, environmental compliance

Healthcare:
- Vendor management scale, BAA processes
- HIPAA compliance infrastructure, OIG screening
- Third-party risk management maturity

Retail/Property Management:
- Vendor categories managed (custodial, HVAC, security, etc.)
- Fidelity bond requirements, tenant compliance
- Multi-location compliance burden

Data Centers:
- Build phase GC relationships, operational vendor count
- Hyperscaler vs. colocation, compliance stringency

---

## Step 3: Multi-Entity Intelligence Pass

This is the core architectural step. Instead of assessing fit for one company, map the person's entire professional orbit and screen each entity.

### 3a: Always Load Core Brief

Read `references/company-core.md`. This ~500-word brief provides:
- What Lumif.ai does, the 4 modules, key differentiator
- Competitive positioning summary
- Confirmed/invalidated ICPs
- GTM sequence (felt pain -> latent pain)
- What we are NOT

This is sufficient to position Lumif.ai correctly for ANY meeting.

### 3b: Extract Meaningful Entities from Person's Background

From LinkedIn profile and research, build a structured map of every company/organization this person has meaningfully touched. **Read every detail** — not just job titles, but also:
- **Role descriptions** on LinkedIn (these often contain portfolio companies, subsidiary names, client lists, advisory relationships, or URLs to related entities)
- **Company "About" sections** visible on profile
- **Mentioned companies** within descriptions (e.g., "Board advisor for: Skimmer, Rentvine, InnFlow" or "Investor and operator of residential and commercial roofing companies. https://www.olympusroofing.com")

A single LinkedIn entry can reveal multiple entities. Parse descriptions thoroughly — names of portfolio companies, subsidiaries, partner firms, and advisory relationships are often buried in free text, not listed as separate positions.

**Include:**
- Current company (primary)
- Past companies where they held director+ level roles, or spent 2+ years
- Board positions, advisory roles
- Companies they founded or co-founded
- **Portfolio companies, subsidiaries, or affiliated entities mentioned in role descriptions**
- **Companies linked via URLs in descriptions** (fetch the URL to identify the entity)
- Industry associations or groups where they're actively involved (not just member)

**Exclude:**
- Internships
- Junior positions (analyst, coordinator, early-career roles)
- Short stints (<1 year) unless C-suite
- Passive memberships in large organizations

**Output format:**
```
Entity Map:
1. [Current] Ridgeline Roofing Group — CEO (2025-present) — Roofing investor/operator
2. [Portfolio] Olympus Roofing — via Ridgeline (URL in description) — Commercial roofing
3. [Advisory] Mainsail Partners — EIR (2025-present) — PE firm
4. [Board] Skimmer — Board advisor via Mainsail — Pool service software
5. [Board] Rentvine — Board advisor via Mainsail — Property management software
6. [Board] InnFlow — Board advisor via Mainsail — Hospitality software
7. [Previous] Hensel Phelps — VP Risk (2015-2024) — GC, ENR Top 20
```

### 3c: First-Pass Fit Screen on Each Entity

For each meaningful entity, do a quick fit screen against the core brief and confirmed ICPs. This is a lightweight version of the company-fit-analyzer — just enough to decide where to invest deep research.

| Entity | Industry Match? | Size Signal | Pain Indicators | ICP Status | Fit |
|--------|----------------|-------------|-----------------|------------|-----|
| Hensel Phelps | GC — confirmed ICP | ENR Top 20, $6B+ | Heavy sub base, complex projects | Confirmed (8+ calls) | High |
| Skanska | GC — confirmed ICP | ENR Top 10 | Enterprise scale | Confirmed, but "build vs buy" risk | Medium |
| Webcor Builders | GC — confirmed ICP | ~$2B | Mid-large, sweet spot | Confirmed | High |
| Safety Council | Industry association | N/A | Network value only | N/A | Low (connector) |

**Scoring criteria:**
- **High fit**: Industry matches a confirmed ICP, company size aligns with beachhead ($100M-$1B) or is a plausible target, role suggests compliance pain
- **Medium fit**: Industry matches but size is edge case (too large = "build vs buy", too small = no budget), or industry matches an emerging ICP
- **Low fit**: No industry match, invalidated segment, or entity is relevant only for network value
- **No fit**: Completely unrelated industry, no conceivable connection to compliance/risk

### 3d: Deep Research on High-Fit Entities

For entities scored High or Medium, do actual web research:
- Current sub count, project types, geographic footprint
- Tech stack signals (Procore? Sage? Which COI tracker if any?)
- Recent news (major projects, incidents, leadership changes)
- Compliance-related mentions (OSHA citations, insurance disputes, wrap programs)
- Cross-reference against learnings-synthesis: has anyone from this company or similar companies been interviewed before?
- Cross-reference against `company_intel` from Step 0.5b-2: if a different person at this company was already interviewed, use their insights (tools, workflows, pain points, org structure) to inform research — but anonymize the source
- **Entity-level transcript search:** For each High/Medium-fit entity in the entity map (not just the primary company), search `/Users/sharan/Projects/lumifai/transcripts/` filenames for that entity's name slug. If found, read the transcript and extract entity-specific insights — tools, processes, pain points, org details. Store alongside `company_intel`. This catches cases where the person's background entity (e.g., Hensel Phelps) was discussed in someone else's call. Also check the `_interview-index.md` Company column for matches.
- Any relevant industry-specific signals from Step 2's checklist

For Low-fit entities — skip deep research but note them as potential conversation reference points or network expansion targets.

### 3e: Person Fit Assessment

Separate from company fit. This answers: **Is this person relevant because of who they are, or just because of where they work/worked?**

| Dimension | What to Assess |
|-----------|---------------|
| **Role relevance** | Decision-maker, influencer, day-to-day user, connector, or domain expert? Could they buy, use, recommend, or just opine? |
| **Domain depth** | Do they understand compliance pain firsthand (they've done it), or is it adjacent to their role (they oversee it), or disconnected (marketing VP at a GC)? |
| **Career signal** | Have they moved through roles that repeatedly touch compliance/risk/insurance? (Strong signal — this is their world.) Or is compliance one small piece of their portfolio? |
| **Comparative insight** | Having worked at multiple companies, can they compare approaches? (E.g., "At Skanska we did X, at Hensel Phelps we do Y" — this is gold for discovery.) |
| **Network value** | Regardless of personal fit, who can they connect us to? Past companies, board connections, industry associations, peers. |
| **Engagement type** | Based on all above: is this a product conversation, an expert interview, an advisory session, or a relationship-building call? |

**Person fit scoring:**
- **High**: They touch compliance directly, have decision-making authority or strong influence, and work at a high-fit company
- **Medium**: They oversee compliance (not hands-on), or they're at a medium-fit company, or they're an expert/advisor without buying authority
- **Low**: They don't touch compliance, their companies are low fit, but they have network value or domain knowledge worth extracting

### 3f: Selective Deep Context Loading

Based on the entity map and person assessment, determine the persona category and load relevant deep context.

**Persona categories:**

| Category | Signals | Primary Interest |
|----------|---------|-----------------|
| `GC_RISK` | GC risk manager, insurance coordinator, compliance role at a GC | Time savings, document chaos, sub compliance |
| `GC_EXEC` | VP Risk, CRO, CFO at a GC or owner | Portfolio visibility, audit defensibility, governance |
| `PROJECT_EXEC` | Project executive, PM, superintendent | Delivery risk, sub performance, pre-qual |
| `OWNER` | Developer, owner's rep, OPM | Wrap program exposure, GC accountability |
| `CARRIER` | WC underwriting ops, premium audit leader, carrier exec | Audit cost reduction, accuracy, cash flow |
| `BROKER` | Construction insurance broker, agency principal | Compliance as service, differentiation, efficiency |
| `ENERGY` | Energy/O&G risk, safety, procurement, contractor mgmt | ISN pain, MSA complexity, environmental compliance |
| `HEALTHCARE` | Healthcare compliance, vendor management, risk | Multi-layer compliance (BAA, OIG, credentialing) |
| `RETAIL` | Property management, retail ops, vendor compliance | Vendor lifecycle, fidelity bonds, multi-location |
| `DATA_CENTER` | Data center construction or operations | Build phase + operational compliance |
| `ADVISOR` | Board member, mentor, investor, industry advisor | Strategic feedback, moat, GTM, competitive threats |
| `OTHER` | Doesn't fit above categories | Expert insight, network expansion |

**Routing table — what to load from company-context-full.md:**

| Persona Category | Sections to Focus On |
|-----------------|---------------------|
| `GC_RISK` | [MODULES] + [COMPETITORS: COI Trackers] + [ANGLES: GC Risk Manager] + [STATS] |
| `GC_EXEC` | [MODULES] + [MOAT] + [COMPETITORS: COI Trackers] + [ANGLES: VP of Risk] + [STATS] |
| `PROJECT_EXEC` | [MODULES: Pre-Qual + Monitoring] + [ANGLES: Project Executive] |
| `OWNER` | [MODULES: Wrap + Insurance] + [ANGLES: Owner] + [MOAT] |
| `CARRIER` | [MODULES: Insurance] + [COMPETITORS: Pre-Qual] + [STATS] |
| `BROKER` | [MODULES: Insurance] + [COMPETITORS: COI Trackers] + [ANGLES: Broker] + [GTM] |
| `ENERGY` | [VERTICALS: Energy] + [COMPETITORS: Pre-Qual] + [ANGLES: Energy] |
| `HEALTHCARE` | [VERTICALS: Healthcare] + [ANGLES: Healthcare] + [STATS] |
| `RETAIL` | [VERTICALS: Retail] + [ANGLES: Retail] |
| `DATA_CENTER` | [VERTICALS: Data Centers] + [ANGLES: Data Centers] |
| `ADVISOR` | [MOAT] + [COMPETITORS: full] + [GTM] + [VERTICALS: summary] |
| `OTHER` | [Core brief only — already loaded] |

Read the full `references/company-context-full.md` but focus prep generation ONLY on sections specified by the routing table.

**Loading learnings:**

Read `/Users/sharan/Projects/lumifai/insights/learnings-synthesis.md` and extract:
1. The ICP row matching this person's segment (confirmed, emerging, or invalidated?)
2. The relevant Theme section (Theme 1 for carriers, Theme 2 for GCs/brokers, Theme 3 for cross-cutting)
3. Pain points ranked for their segment
4. Common objections they're likely to raise
5. Tools/workflows their segment typically uses
6. Any past call insights from someone in a similar role or company type
7. Research queue items — is there a pending intro or connection related to this person?

**If learnings-synthesis.md doesn't exist**, skip this and rely on core brief + company-context-full.md only.

---

## Step 4: Hypothesis Synthesis

Synthesize everything from Step 3 into a concise hypothesis block. This is the analytical core — it connects entity mapping, fit screening, person assessment, and learnings into a clear picture.

**Generate:**

```
HYPOTHESIS
-- Primary opportunity: [Which entity is the main fit? Why?]
-- Secondary angles: [Other high-fit entities from their background — reference points for conversation]
-- Person fit: [High/Medium/Low — are they a buyer, user, expert, or connector?]
-- Engagement type: [Customer Discovery / Expert Insight / Channel-Partner / Advisory / Network Expansion]
-- Module alignment: [Which Lumif.ai module(s) are most relevant and why]
-- Key unknowns: [2-3 specific things we need to learn from this conversation]
-- Learnings match: [What does past call data tell us about this segment? Confirmed/emerging/new?]
-- Companies to reference: [Which companies from their background to mention during conversation]
-- Predicted objections: [2-3 likely pushback points from learnings for this persona type]
-- Company intel: [If company_intel found: "[Person] at [company] discussed [topics] on [date]. Key insight: [one sentence]." If none: omit this line.]
-- Prior call context (follow-ups only): [If meeting_number >= 2: "Nth meeting. Prior calls covered [topics]. Open items: [items]. Relationship: [status]. Classification: [painkiller/vitamin @ severity]." If first meeting: omit this line.]
```

**The key unknowns drive the questions.** If research already tells us they use Procore, don't ask "what tools do you use?" If we know their company size, don't ask about scale. The unknowns are things research COULDN'T answer — their internal process, their pain severity, their reaction to the demo, their decision-making authority.

---

## Step 4b: Exposure & Value Synthesis

Using the persona category (from Step 3f), module alignment (from Step 4), and loaded learnings, synthesize a focused "Why This Matters" block. This gives the founder a cheat sheet of exposure risk, validated pain points, relevant modules, and a tailored pitch to carry into the conversation.

### 4b-1: Extract Exposure Risk

Identify 2-4 quantified risk metrics relevant to this person's ICP. Pull from these sources in order:

1. **learnings-synthesis.md** — dollar figures from real calls (e.g., "$100K/yr per FTE on manual COI tracking", "$23M aggregate sub exposure")
2. **company-context-full.md [STATS]** — industry statistics (e.g., "$2.2T U.S. construction spending", "60-70% COI non-compliance on first submission")
3. **Step 2 company research** — tailor to this company's scale (e.g., "With 15 active projects, that's ~5 FTEs or $500K/yr in compliance labor")

Tag each metric with a confidence level:
- `validated` — sourced from 3+ expert calls in this segment
- `emerging` — sourced from 1-2 calls
- `hypothesized` — industry stat or extrapolation, no direct call data

### 4b-2: Match Pain Points to Persona

From `learnings-synthesis.md`, extract the "Hair on Fire Problems" that match this persona's segment. Rank by severity score. Include 3-5 pain points maximum.

**Persona-to-pain mapping:**

| Persona | Primary Pain Points | Source |
|---------|-------------------|--------|
| GC_RISK / GC_EXEC | Manual COI tracking (4.3), sub gaps discovered too late (4.0), fake certificates (3.8), touch labor/rework (4.0) | Validated (8+ GC calls) |
| CARRIER | WC premium audit errors (4.5), reserve accuracy (3.5), training gutted, classification disputes | Validated (5+ carrier calls) |
| BROKER | Manual compliance verification (4.0), competitive differentiation pressure, E&O liability from missed gaps | Validated (3+ broker calls) |
| ENERGY | ISNetworld fatigue, MSA complexity, environmental compliance burden | Emerging (limited data) |
| PROJECT_EXEC | Sub pre-qual gaps, change order compliance blind spot, delivery risk from sub defaults | Emerging |
| OWNER | Wrap program exposure, GC accountability gaps, excluded trade enrollment errors | Emerging |
| ADVISOR / OTHER | Top 3 cross-segment pain points as market validation | Use validated data from strongest segments |
| HEALTHCARE / RETAIL / DATA_CENTER | Industry-specific pain from [VERTICALS] section | Hypothesized — flag as "pure discovery" |

If no learnings exist for this segment, use pain points from company-context-full.md [ANGLES] section for the matched persona and tag as `hypothesized`.

### 4b-3: Select Relevant Modules

Pick only the 1-2 Lumif.ai modules most relevant to this person's role and entities. Rewrite the module description in their language — reference their company names, their industry terms, their specific situation.

**Do NOT list all 4 modules.** Only the ones that solve their identified pain points.

Example for a GC Risk Manager at a mid-size GC:
> **Insurance Compliance** — Parses your MSAs, extracts every insurance requirement per sub trade, reconciles against submitted COIs and endorsements. For a firm managing 20+ active projects, this means knowing exactly which subs have gaps before a claim is filed — not after.

Example for an Advisor with roofing portfolio:
> **Insurance Compliance** — For sub-side companies like [entity], this flips the value prop: instead of chasing compliance, your subs can proactively show GCs they're fully compliant — differentiating them in bid selection.

### 4b-4: Compose Tailored Value Prop

Write a 2-3 sentence pitch in second person, using:
- Their entity names from Step 3b
- Dollar/time figures from the exposure risk (4b-1)
- The specific module capability from 4b-3
- The felt-pain to latent-pain arc from company-core.md GTM section

**For ADVISOR/OTHER personas:** Lead with market opportunity framing ("The construction compliance market wastes $X annually in manual verification"), then ground it with their specific entities ("Companies like [entity] in your portfolio face this daily").

This pitch appears in the HTML briefing AND in the Quick Reference card for at-a-glance use during the call.

---

## Step 5: Generate Questions (10-15, Demo-Led)

This is a demo-led conversation, not a discovery interview. The person has just seen (or is about to see) the product. Questions should be informed by ALL the research done above — never ask something the research already answered.

Read `references/question-bank.md` as a prompt library (not a script) for inspiration on phrasing and follow-up techniques.

### Follow-Up Meeting Questions (meeting_number >= 2)

If this is a follow-up meeting, replace the default Block 1/2/3 structure with these follow-up-specific blocks:

**Block 1 → "Building on Prior Call" (2-3 questions):**
Follow up on commitments, action items, and events since the last call. Source these from `open_action_items` in the Prior Call Context (Step 0.5).

Examples:
- "Last time you mentioned [specific action item] — how did that go?"
- "You were planning to [specific thing they committed to] — any update on that?"
- "When we last spoke, [event/deadline] was coming up — how did it land?"

**Block 2 → "Deepening Discovery" (4-5 questions):**
Go deeper into topics introduced but not fully explored in prior calls. Source from `topics_already_covered` and `key_insights`.

Rules:
- **Never repeat already-answered questions** — check `topics_already_covered` before including any question
- **Reference their own words** — use `quotable_moments` to show you listened ("You mentioned '[exact quote]' — can you expand on that?")
- **Calibrate rather than re-discover** — instead of "How do you handle compliance?", ask "You described your process as [their description] — has anything changed since we last spoke?"
- **Probe gaps** — what did they hint at but not elaborate on? What follow-up questions should have been asked?

**Block 3 → "Strategic & Expansion" (3-4 questions):**
Same structure as first-meeting Block 3 but with specific entity names and context from prior conversation:
- Reference specific companies/people they mentioned in prior calls by name
- If they mentioned colleagues ("my team lead Sarah handles that"), ask about those people
- Advisory formalization if applicable ("Would a more formal advisory relationship make sense?")
- Next steps that build on prior momentum, not restart from zero

**After generating follow-up blocks, skip directly to the "Objection Preparation" section below. Do NOT use the first-meeting blocks.**

---

### First Meeting Questions (meeting_number = 1 ONLY — skip this entire section for follow-ups)

The following blocks apply to first meetings only. If `meeting_number >= 2`, these are NOT used — the follow-up blocks above replace them entirely.

### Block 1: Post-Demo Reaction (2 questions)

These come right after the demo. Keep it open.

1. **"What stood out to you?"** — Open-ended, let them lead. Variants: "What did you like?", "What resonated?" Listen carefully — what they highlight reveals what matters to them.

2. **"What's missing? What would you need to see to take this seriously?"** — Inversion. Let them tell you what to build, what gaps they see, what would make this real for their world.

### Block 2: Context & Validation (5-8 questions)

These probe deeper, informed by the entity map, fit screening, and learnings. Every question should demonstrate that you've done your homework.

**Rules for these questions:**
- Never ask something research already answered (if you know they use Procore, reference it: "How does your Procore workflow handle compliance?")
- Reference specific companies from their background where relevant ("When you were at [past company], was the process similar?")
- Use learnings data as calibration, not claims ("We've heard coordinators spend 25-50% of time on compliance — does that match your experience?")
- **Use exposure risk figures from Step 4b** as calibration anchors (e.g., "We've seen GCs your size carry $20-25M in undetected exposure — does that track?")
- Probe the key unknowns identified in the hypothesis
- Use the relevant [ANGLES] section from company-context-full.md as inspiration for role-specific questions

**Question sources (pick the best 5-8 for this specific person):**

From their **current company**:
- Questions about their specific compliance process, workflow, pain points
- Tech stack questions that reference what research suggests they use
- Scale questions that show you know their company size ("With [X] active projects, how do you...")

From their **career arc** (comparative insight):
- "How did [process] compare between [Company A] and [Company B]?" — leverage their multi-company experience
- "What changed when you moved from [smaller company] to [larger company]?"

From **learnings validation**:
- Calibrate a validated pain point: "Others in your position report [X] — does that match?"
- Probe a tool pattern: "A lot of GCs your size are still on spreadsheets for this — is that your situation too?"
- Test an emerging hypothesis: "We're hearing [trend] — are you seeing that?"

From **entity-specific research**:
- Reference something specific found during deep research (a recent project, a news item, a compliance incident)
- "I saw [company] just won [project] — does a project of that scale change the compliance burden?"

From **company-context-full.md [ANGLES]**:
- Pull the 1-2 most relevant role-specific questions from the angles section
- Tailor them with specific company/entity names from the research

### Block 3: Strategic & Expansion (3-4 questions)

These are about the bigger picture — where this goes, who else matters.

- **Company-specific reference**: "Do you think this could be helpful for companies like [specific company from their background or network]?" — Reference real companies they know and that scored High in the entity fit screen.
- **Org structure probe**: "Who on your team would be the day-to-day user of something like this?" — or "Who else should we be talking to about this?"
- **Advisory frame**: "If you were advising us on where to focus, what would you prioritize?" — Everyone likes being asked for advice. Especially effective for ADVISOR persona.
- **Next step**: "Would it be helpful if we ran your actual [MSA / wrap manual / pre-qual package] through the system?" — The live proof-of-value offer.

### Objection Preparation (not questions — listed separately)

**For follow-ups (meeting_number >= 2):** Check the prior transcripts for objections they *actually* raised. If they already said "we can build this ourselves" in call 1, don't just list the generic response — address it specifically: "They raised build-vs-buy in call 1. For call 2, prepare: [evolved response that acknowledges their specific concern and what's changed since]." Prior call objections take priority over generic predicted objections from learnings-synthesis.

**For first meetings:** Based on the persona category and learnings, list the 2-3 most likely objections and how to handle them. Draw from the "Common objections / concerns" section of learnings-synthesis.

Format:
```
If they say: "We can build this ourselves"
Prepare: Large enterprises with 60+ person teams still take 2+ years to build. The question is whether compliance automation is core to your business or a distraction from it.

If they say: "Our subs won't adopt another system"
Prepare: We've heard this consistently. That's why the platform uses email-based document collection — no sub accounts, no logins, no $700/platform burden.
```

### Question Quality Checklist

Before finalizing, verify each question:
- [ ] Is it specific to THIS person and THESE companies? (Uses names, tools, details from research)
- [ ] Does it ask something research COULDN'T answer? (Not redundant with what we already know)
- [ ] Does it serve a purpose? (Validates ICP, quantifies pain, reveals workflow, expands network, or gets feedback)
- [ ] Would this person find it insightful? (Shows preparation, not laziness)
- [ ] Is it demo-led? (Assumes they've seen the product, doesn't rediscover what was just shown)

---

## Step 6: Generate HTML Briefing

**Read `~/.claude/design-guidelines.md` before generating any HTML.** This is the global Lumif.ai design system and MUST be followed for all visual output.

### Design System (key tokens for quick reference)

**Colors:**
- `--brand: #E94D35` (primary accent — CTAs, highlights, brand moments)
- `--brand-light: rgba(233,77,53,0.1)` (badges, soft backgrounds)
- `--brand-glow: rgba(233,77,53,0.05)` (section tints, subtle warmth)
- `--bg: #FFFFFF` (page background)
- `--bg-subtle: #FAFAFA` (alternate sections, card backgrounds)
- `--bg-warm: #FFF8F6` (warm tinted sections)
- `--text: #121212` (headings, primary text)
- `--text-secondary: #6B7280` (body text, descriptions)
- `--text-muted: #9CA3AF` (placeholders, disabled)
- `--border: #E5E7EB` (dividers, card borders)
- Semantic: `--success: #22C55E`, `--info: #3B82F6`, `--warning: #F97316`, `--danger: #EF4444`

**Typography:**
- Font: Inter (weight 400 body, 600 headings). Import from Google Fonts.
- H1: 48px/600, H2: 30px/600, H3: 20px/600, Body: 16px/400, Caption: 14px/400, Label: 12px/500
- Headings: `#121212`, Body: `#6B7280`, Links: `#E94D35`

**Spacing:** 4px grid (4/8/12/16/24/32/48/64/96px)

**Components:**
- Cards: white, `1px solid #E5E7EB`, `border-radius: 12px`, `padding: 24px`, hover: `border-color: rgba(233,77,53,0.2)` + `box-shadow: 0 4px 16px rgba(0,0,0,0.06)`
- Badges: pill shape (`border-radius: 9999px`), `padding: 4px 12px`, `font-size: 12px`, `font-weight: 500`. Brand: `bg rgba(233,77,53,0.1) color #E94D35`. Success: `bg rgba(34,197,94,0.1) color #16A34A`. Info: `bg rgba(59,130,246,0.1) color #2563EB`. Warning: `bg rgba(249,115,22,0.1) color #EA580C`.
- Buttons: Primary = `bg #E94D35, color white, radius 12px`. Secondary = `transparent, border 1px solid #E5E7EB`. Ghost = `transparent, color #6B7280`.
- Tables: `th` uppercase 12px/500 `#6B7280`, `td` 14px `#121212`, row hover `#FAFAFA`
- Shadows: `0 1px 2px rgba(0,0,0,0.05)` (sm), `0 4px 6px rgba(0,0,0,0.07)` (md), `0 4px 14px rgba(233,77,53,0.15)` (brand)

**Layout:** Max-width `1280px` for dashboards, `1120px` for card grids, `720px` for text-heavy content. Generous whitespace.

**Anti-patterns (never do):** Purple gradients on white, gray-on-gray, rainbow colors, centered body text, more than 2 font families, low contrast text.

### Logo Integration

Embed the Lumif.ai logo in the HTML header. Read the logo file and base64 encode it:
```
Logo path: ~/.claude/brand-assets/lumifai-logo.png
Icon path: ~/.claude/brand-assets/lumifai-icon.png
```
Use the full logo in the header, icon in the print reference card.

### HTML Structure — Document Style

**Design philosophy:** This is a personal prep document, not a dashboard or client deliverable. Optimize for **scanning speed** over visual polish. Think Notion page, not SaaS landing page.

**What to use:** Inter font, brand color for accents/badges, clean typography, clear section headers, bullet points, horizontal rules between sections.

**What NOT to use:** Card hover effects, fade-in animations, page glow gradients, alternating section backgrounds, card grids for entities, CSS transitions. No visual chrome that doesn't aid scanning.

**Overall page:**
- White background (`#FFFFFF`), single column
- Max-width container: `720px` (text-heavy document), centered, with `padding: 48px 24px`
- Sections separated by `<hr>` with `border-top: 1px solid #E5E7EB` and `margin: 32px 0`
- No background alternation between sections

**Header block:**
- Lumif.ai logo (small, top left)
- **Follow-up badge (if meeting_number >= 2):** Green success badge above person name: `"Nth Meeting"` (e.g., "2nd Meeting", "3rd Meeting"). Uses success badge style: `bg rgba(34,197,94,0.1) color #16A34A`.
- Person name (H1, `#121212`), title + company below (`#6B7280`)
- Meeting date (`#9CA3AF`, 14px). **For follow-ups:** append ` — Follow-up call (first call: [date of first transcript])` in same muted style.
- Badge row: persona category (brand), engagement type (info), person fit (warning/success), company fit (neutral)
- Print button (top right, simple)

**Section 1 — Hypothesis & Angle (FIRST after header):**
This is the most important section — it answers "why are we talking to this person?"
- Structured bullet list, not a card
- Primary opportunity, secondary angles, person fit, engagement type, module alignment
- **Key unknowns** — bold, highlighted. These drive the questions.
- Learnings match as badge + one sentence
- Companies to reference

**Section 1.5 — Prior Call Recap (follow-ups only, skip for first meetings):**
If `meeting_number >= 2`, insert a blue info box (`bg rgba(59,130,246,0.1)`, `border-left: 4px solid #3B82F6`, `padding: 16px 20px`, `border-radius: 0 8px 8px 0`) between Hypothesis and Why This Matters:
- **Header:** "Prior Call Recap" with info badge showing call count (e.g., "1 prior call" or "2 prior calls")
- **What was covered:** Bullet list of key topics from `topics_already_covered`
- **Commitments made:** Bullet list from `open_action_items` — bold the item, note who committed to it
- **Classification:** Prior severity/painkiller assessment if available (e.g., "Classified as painkiller — high severity compliance pain")
- **Relationship status:** One-line summary from `relationship_progression`
- Keep this section compact — 8-12 lines max. It's context, not a transcript.

**Section 2 — Why This Matters:**
This is the "weapon" section — synthesized from Step 4b. Four subsections, all scannable:

- **Exposure Risk** — 2-4 bullet points, each with bold metric + one sentence + confidence tag in parentheses.
  Format: `**$23M** — Aggregate undetected sub exposure if endorsement forms aren't verified. *(validated: 8+ calls)*`
  Confidence tags: `validated` (green-tinted), `emerging` (amber-tinted), `hypothesized` (gray-tinted)

- **Pain Points for This Role** — 3-5 bullet points from learnings, ranked by severity.
  Format: `**Manual COI tracking** — 4.3/5 severity. Coordinators spend 25-50% of time on compliance. *(validated)*`
  If no learnings for this segment, use pain points from [ANGLES] and tag as `hypothesized`. Add caption: *"No validated call data for this segment yet. This conversation is pure discovery."*

- **What We Solve** — 1-2 modules only, each as a bold name + 2-3 sentences describing what it does in this person's language, referencing their entities.
  NOT a list of all modules. Only what solves their identified pain.

- **The Pitch** — Single paragraph, 2-3 sentences. Second person, uses their entity names, dollar figures from Exposure Risk, and module capabilities. This is the "if you had 30 seconds" version.
  For ADVISOR personas: lead with market opportunity ("The construction compliance market wastes $X annually"), then entity example ("Companies like [entity] in your portfolio face this daily").

**Section 3 — Conversation Hooks:**
- 3 numbered hooks with bold opener + context in `#6B7280`
- Style signals as a single caption line
- Placed high because you use these in the first 2 minutes

**Section 4 — Key Background:**
- 6-8 bullet points covering career arc, education, expertise, published content
- NOT a visual timeline with dots and lines. Just: `**Company** — Role (dates). One sentence of context.`
- Only include what's relevant to THIS conversation, not a full LinkedIn mirror

**Section 5 — Entity Map:**
- **High/Medium fit entities:** Each gets its own paragraph — company name bold, fit badge inline, then 2-4 sentences of context (what they do, why it's relevant, what to reference in conversation, any research findings)
- **Low fit entities:** Single line — `**Company** — Role — network value only` or `tangential, not a buyer`
- **No fit entities:** Grouped in one line — "Also in background: Skimmer, InnFlow, Weave, InsideSales — no compliance overlap"
- No cards, no grid. Just structured text with bold headers.

**Section 6 — Questions (10-15):**
- **For follow-ups (meeting_number >= 2):** Add a note at the top of the Questions section in a subtle info-tinted box: *"This is a [Nth] meeting. Questions build on prior conversations — see Prior Call Recap above."* Use follow-up block headers: "Building on Prior Call" (2-3), "Deepening Discovery" (4-5), "Strategic & Expansion" (3-4).
- **For first meetings:** Three sub-sections with H3 headers: "Post-Demo Reaction" (2), "Context & Validation" (5-8), "Strategic & Expansion" (3-4)
- Clean numbered list
- Must-ask: `font-weight: 600`, `#121212`
- If-time-allows: `font-weight: 400`, `#6B7280`
- Follow-up prompts: indented, `font-size: 14px`, `#9CA3AF`
- Purpose line: `font-size: 12px`, `#9CA3AF` — useful for prep, scannable during call

**Section 7 — Objection Prep:**
- 2-3 items, each as: bold objection text, then response paragraph below
- No cards, no grid. Simple `**"Objection text"**` followed by response.
- Separated by light horizontal rules

**Section 8 — Intel from Past Calls:**
- Bullet list of relevant validated insights
- Keep brief: `**Pain point** — one sentence of evidence`
- "What to validate" as 1-2 sentence summary
- If no learnings: single line noting "First conversation in this segment"

**Section 9 — Quick Reference (print-friendly):**
- Compact section with `--brand` top border (3px solid)
- Simple key-value layout: name, role, fit, value prop (2-3 sentence pitch from Section 2), top 5 must-ask, key unknowns
- CSS `@media print` rules:
  - Show ALL sections on print — do NOT use `body * { visibility: hidden }` (this causes blank pages beyond the first visible element)
  - Reduce font sizes: 12px body, 28px h1, 20px h2, 16px h3
  - Max-width 100%, padding reduced to 16px
  - Hide the print button and sources section (`display: none`)
  - Add `break-before: page` on `.quick-ref` so it starts on its own page
  - Links: `color: inherit; text-decoration: none`
  - Badges: add `border: 1px solid #ccc` for visibility without background
  - Info boxes and key-unknowns: add `border: 1px solid` to preserve structure
  - Add `print-color-adjust: exact; -webkit-print-color-adjust: exact;` to preserve badge colors and background tints

**Section 10 — Sources (screen only, hidden on print):**
- List of all URLs used during research
- Includes: LinkedIn profile, company websites, articles, faculty pages, portfolio pages
- Use `font-size: 12px`, `color: var(--text-muted)`, underlined links

### Linking Requirements

**Every mention of a company, article, or profile should be a clickable link when a URL is available.** This applies throughout the entire document:

- **Person name** in header links to their LinkedIn profile
- **Company names** link to company websites (e.g., olympusventuregroup.com, jobnimbus.com)
- **Portfolio companies** link to their pages on the parent company's site (e.g., mainsailpartners.com/company/skimmer/)
- **Articles and publications** link to the source (e.g., Medium articles)
- **University/teaching roles** link to faculty directory pages
- **Entity map entries** — every entity name links to its website
- **Questions** — when referencing a company by name, link it
- **Objection prep** — when referencing a company or article, link it

Link styling:
- Company/entity links: `color: var(--brand)`, no underline, underline on hover
- Subtle/secondary links (in captions, no-fit entities): `color: var(--text-muted)`, underlined
- Print: all links styled as plain text (no color, no underline) via `@media print`

Collect all URLs during research in Steps 1-3 and maintain a link map to use throughout the HTML generation.

### Save Location

`lumifai/insights/meeting-prep-{slug}-{YYYY-MM-DD}.html`

Where `{slug}` is:
- Person's name if available (e.g., `mike-torres`)
- Company name if person unknown (e.g., `acme-construction`)
- Combined if both available (e.g., `mike-torres-acme`)

Tell the user the file path so they can open it in a browser or print it.

---

## Step 7: Post-Meeting Connection

After generating the briefing, remind the user:

> After your meeting, say **"process my meeting notes"** to run the Meeting Processor skill.
> It will extract insights into your tracker, update ICPs, and grow the learnings synthesis.
> The more calls you prep and process, the sharper your prep gets — the feedback loop is:
> **Prep -> Meeting -> Process -> Learnings update -> Better prep next time**

---

## Memory & Learned Preferences

This skill remembers research context and prep preferences across sessions.

**Storage architecture:**

```
/Users/sharan/Projects/lumifai/insights/prep-cache/
├── _index.md                    # Quick lookup table: slug → LinkedIn → company → last prep date
├── curtis-kochman.md            # Full person dossier + meeting history + open items
├── patricia-sutherland.md
├── sean-beausoleil.md
└── ...
```

Plus a small preferences file in auto-memory: `~/.claude/projects/-Users-sharan-Projects/memory/lumifai-meeting-prep.md`

### Loading at prep start

Before Step 0 (Gather Inputs), run these checks:

```bash
# 1. Read the index to check if person is already cached
cat /Users/sharan/Projects/lumifai/insights/prep-cache/_index.md 2>/dev/null || echo "NOT_FOUND"

# 2. Load preferences
cat "$(find ~/.claude/projects -name 'lumifai-meeting-prep.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

**If the person's slug appears in `_index.md`:**
- Read their individual file (e.g., `prep-cache/curtis-kochman.md`)
- Set `is_cached = true`
- Skip ALL LinkedIn scraping, web searches for background, career arc discovery
- Use the cached dossier as the person profile
- Focus research time on what's NEW since their `last_updated` date

**If a different person is being prepped but their company appears in another person's cached file:**
- Read that cached file to extract company research — don't re-research the same company

**If person is NOT in the index:**
- Full research as normal (LinkedIn, web search, etc.)
- After prep, create their cache file and add to index

### Index file format (`_index.md`)

One line per person. Scannable in seconds.

```markdown
# Prep Cache Index

| Slug | Name | LinkedIn | Company | Persona | Meetings | Last Prep |
|------|------|----------|---------|---------|----------|-----------|
| curtis-kochman | Curtis Kochman | [LI](https://www.linkedin.com/in/curtis-kochman-25041757/) | Mission Underwriting Managers | CARRIER | 3 | 2026-03-09 |
| patricia-sutherland | Patricia Sutherland | [LI](https://www.linkedin.com/in/patricia-sutherland/) | Keller Williams Realty Boston NW | OTHER | 1 | 2026-03-09 |
| sean-beausoleil | Sean Beausoleil | [LI](https://www.linkedin.com/in/sean-beausoleil/) | ex-RMR Group | GC_RISK | 2 | 2026-02-26 |
```

### Person file format (e.g., `curtis-kochman.md`)

Each person gets their own markdown file with full research, meeting history, and open items.

```markdown
# Curtis Kochman

## Profile
- **LinkedIn:** https://www.linkedin.com/in/curtis-kochman-25041757/
- **Current role:** Chief Growth Officer at Mission Underwriting Managers (as of 2026-03-09)
- **Location:** Venice, Florida (Remote)
- **Education:** West Virginia University, B.A. Communications (1983-1988)

## Career Arc
- Mission Underwriting Managers — CGO (Dec 2025 - Present)
- Typhon Risk — Fractional Executive Consultant (Jun 2024 - Nov 2025)
- Champlain Insurance Group — VP Revenue / CRO (Oct 2022 - Apr 2024)
- Falcon Re — President & CEO (Mar 2020 - Oct 2022)
- Vital Insurance Partners — SVP Programs (Jan 2019 - Feb 2020)
- Highmark Casualty — National Director WC (grew to $60M+)
- Highmark Inc. — VP Cross Selling ($3B+ across 4 companies)
- Marsh & McLennan — Head, Construction Industry Group
- ManagedComp Inc. — Founded 1995, grew to $15M MGA

## Assessment
- **Persona:** CARRIER
- **Person fit:** HIGH
- **Key facts:** WC specialist, 30+ year career, London/Lloyd's experience, deeply connected to carrier CEOs
- **Style signals:** Relationship-driven, bottom-line focused, generous with intros
- **Conversation hooks:** ManagedComp founder story, Highmark WC build, construction background via M&M

## Entity Map
- Mission Underwriting Managers — HIGH (MGA platform, 29+ programs, potential P1 customer/channel)
- Champlain Insurance Group — CONTEXT (prior employer, WC focus)
- Typhon Risk — CONTEXT (MGA consulting)
- Falcon Re — CONTEXT (P&C specialty, London markets)
- Highmark Casualty — CONTEXT (built $60M+ WC carrier)

## Company Research: Mission Underwriting Managers
- **URL:** https://www.gomission.com/
- **What:** Specialty insurance MGA platform — launches and scales underwriting programs
- **Size:** 29+ programs, 80+ products, A- avg carrier rating
- **Acquired by:** Accelerant Holdings (May 2024)
- **HQ:** Scottsdale, AZ
- **Relevance:** Potential P1 customer/channel — MGA programs may include WC lines needing audit automation

## Meeting History
| # | Date | Transcript | Key Topics |
|---|------|-----------|------------|
| 1 | 2026-02-13 | [Link](../../transcripts/2026-02-13-curtis-kochman-champlain-insurance-group-advisor.md) | Carrier segmentation, pricing bands, target carriers, conference strategy |
| 2 | 2026-03-12 | [Link](../../transcripts/2026-03-12-curtis-kochman-champlain-insurance-group-advisor-2.md) | Case study approach, NY WC data, $2-3M audit costs, 25% savings pricing, $10K pilot, warm intros |
| 3 | 2026-03-09 | — | (prep generated, meeting pending) |

## Open Items
- Curtis to email/text inner circle: Liberty Mutual, ICW, Alliance, Selective, EMC, Arch, AE, Everspan, Benchmark, UPMC, Nautilus, Normandy
- Build 4 case study versions (construction + premium audit, demo + case study variants)
- Finalize pricing model (25% savings + flat fee)
- $10K / 90-day pilot structure

## Prep Files
- meeting-prep-curtis-kochman-2026-03-09.html

## Last Updated
2026-03-09
```

### What to save after each run

**To the person's cache file (`prep-cache/{slug}.md`):**
- Create the file if it doesn't exist (first meeting)
- Update in place if it exists (follow-up) — update current role, meeting history, open items, last updated date
- Add any new company research as a section within the person file

**To the index file (`prep-cache/_index.md`):**
- Add a row if new person
- Update meeting count and last prep date if existing person

**To the preferences file (`lumifai-meeting-prep.md` in auto-memory):**
- Briefing count and categories (e.g., "14 preps: 9 expert, 3 advisor, 2 company-only")
- Question preferences — blocks the user values most
- Routing corrections — if user corrects persona category or fit scores
- Workflow preferences — depth, format, sections emphasized

### What NOT to save

- Full briefing content (lives in output HTML files)
- Sensitive personal details (phone numbers, home addresses, private social media)
- One-time meeting context

---

## Guidelines

- **Be honest about unknowns.** If info isn't findable, say so. Never fabricate background details.
- **Privacy first.** Only use publicly available information. No speculation about personal matters.
- **Scale to context.** A 15-min coffee chat needs a lighter brief than a 45-min deep dive.
- **Questions are the product.** The question list is the most valuable section — invest the most effort in making questions specific, insightful, and non-redundant with research.
- **Think like a founder.** Every question should serve a purpose: validate an ICP, quantify pain, identify a channel, or expand the network.
- **Entities first, product second.** Map the person's orbit before thinking about Lumif.ai fit. This prevents product-deck thinking and ensures the prep is person-driven.
- **Research eliminates questions.** If research answers it, don't ask it. The 10-15 questions should probe what research COULDN'T uncover.
- **Demo-led framing.** Assume the person has seen or will see the product. Questions react to the demo, not discover from scratch.
- **Learnings are intelligence, not scripts.** Use validated pain points and past insights to inform questions, not to script the conversation. The goal is sharper questions, not canned pitches.
- **Anonymize past insights.** When referencing learnings in the prep, say "GC risk managers in this segment report..." not "Marcus Landers told us..."
- **Flag novel segments.** If this is the first conversation in an emerging or unknown segment, explicitly note that this is pure discovery — no validated playbook exists yet.
- **Reference real companies.** When asking about fit, use actual company names from their background ("Do you think this could help at [Company X]?"), not hypotheticals.
