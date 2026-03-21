---
name: sales-collateral
version: 1.1.0
web_tier: 1
description: Create professional B2B sales documents including value proposition one-pagers, partnership pitches, case studies (1-page and 2-page), and vertical-specific marketing collateral. Use when anyone asks to create a value prop doc, sales one-pager, partnership pitch, case study, marketing doc, customer-facing collateral, leave-behind, pitch doc, or any sales document. Also triggers on "create a one-pager", "make a value prop", "build a case study", "partnership one-pager", "sales collateral", "marketing one-pager", or any request to produce a professional sales document. ALWAYS use this skill when creating sales or marketing documents. Produces documents that are defensible, honest, and designed to survive scrutiny from senior buyers.
---

# B2B Sales Collateral Creator

Create professional, defensible, sector-specific sales documents that survive scrutiny from senior buyers.

**Changelog:**
- v1.1.0 (2026-03-18): Added partnership pitch doc type, brainstorm-before-build step, stats banner component, stricter source attribution, naming/template/multi-doc guidance, domain research emphasis
- v1.0.0 (2026-03-16): Initial merged version — core framework + Lumif.ai specifics + context store integration

---

## What This Skill Does

Produces branded Word documents (.docx) for sales and marketing:
- **Value Proposition One-Pagers** — sector-specific, data-backed, single-page docs for cold outreach and first meetings
- **Partnership Pitches** — one-pagers pitched to a potential partner's leadership, framed around what the partner's business gains (revenue, stickiness, competitive moat), not what the product does. Different audience, different structure from value prop docs.
- **Case Studies (1-page)** — compressed customer stories with stats and narrative
- **Case Studies (2-page)** — fuller customer stories with challenge, solution, results, and impact
- **Vertical Adaptations** — same core positioning adapted for different industries

---

## Dependency Check (Standard 2)

Before starting, verify:
1. **docx skill** exists — check `~/.claude/skills/` for a docx-capable skill (e.g., `document-skills:docx`). If missing, warn the user and stop.
2. **Brand template** exists at `~/.claude/brand-assets/lumifai-page-template.docx`. If missing, create from scratch instead.
3. **Template content check**: Unpack the template header and verify it has no outdated content (old addresses, stale URLs, wrong company names). Fix before first use. Outdated template content leaks into every doc.
4. **Context store** is accessible at `~/.claude/context/`. If missing, proceed without context enrichment but warn the user.

---

## Context Store Integration (Standard 14)

### Reads — Load Before Writing

Before creating any document, silently read these context files to enrich content:

| File | What to extract |
|------|----------------|
| `~/.claude/context/positioning.md` | Core value propositions, messaging, differentiators |
| `~/.claude/context/competitive-intel.md` | Named competitor tools per vertical, competitive gaps |
| `~/.claude/context/product-modules.md` | Module descriptions, capabilities, moat analysis |
| `~/.claude/context/icp-profiles.md` | Buyer personas, validated ICPs with evidence |
| `~/.claude/context/pain-points.md` | Vertical-specific pain points with severity |
| `~/.claude/context/vertical-strategy.md` | Sector knowledge, market entry status, GTM approach |
| `~/.claude/context/objections.md` | Common objections and proven responses |
| `~/.claude/context/market-stats.md` | Industry data points, proof points for sales narratives |
| `~/.claude/context/value-mapping.md` | Module-to-value translation per vertical and buyer |
| `~/.claude/context/content-library.md` | Existing published collateral to avoid duplication |

Auto-apply this data silently. Show what was used, don't ask for confirmation.

### Writes — Feed Back After Research

When the skill researches a new vertical (Step 2), write findings back:

| Finding | Write to |
|---------|----------|
| New vertical pain points | `~/.claude/context/pain-points.md` |
| New competitor tools discovered | `~/.claude/context/competitive-intel.md` |
| Vertical-specific buyer personas | `~/.claude/context/icp-profiles.md` |
| Sector regulatory/market data | `~/.claude/context/vertical-strategy.md` |
| Industry statistics found | `~/.claude/context/market-stats.md` |
| New collateral produced | `~/.claude/context/content-library.md` |

Use the standard context store append format:
```
[YYYY-MM-DD | source: sales-collateral | detail-tag] confidence: high | evidence: N
- Content line
```

---

## Memory & Learning (Standard 1)

Track and learn from each collateral creation:
- **Document preferences**: font size tweaks, copy tone, layout preferences the user corrects
- **Successful patterns**: which headline styles, CTA formats, or framings the user approved
- **Vertical research done**: which verticals have been fully researched vs. need work
- **Template iterations**: brand template changes or overrides

Save learned preferences to memory so future runs auto-apply them.

---

## Step 0: Gather Inputs

Before creating any document, establish:

1. **Document type**: Value prop one-pager, 1-page case study, or 2-page case study?
2. **Product/company**: What does the product do? (Auto-fill from `positioning.md` and `product-modules.md` if available)
3. **Target vertical**: Which industry is this for? (Check `vertical-strategy.md` for existing knowledge)
4. **Target market**: Geography? (affects terminology, currency, regulatory references)
5. **Target reader**: Who picks this up? (Check `icp-profiles.md` for existing personas)
6. **Brand template**: Use `~/.claude/brand-assets/lumifai-page-template.docx` if it exists. Otherwise ask.
7. **Competitive landscape**: What existing tools/processes does the buyer already use? (Check `competitive-intel.md`)

If context store has answers, auto-apply them and show the user what was used. Only ask for what's genuinely missing.

---

## Step 1: Understand the Product Positioning

Before writing, establish the core positioning framework. Read `positioning.md` and `product-modules.md` first.

### The Displacement Question
Every B2B product displaces something. Understand what:
- **What does the buyer do today?** (manual process, spreadsheets, existing software, nothing)
- **What tools do they already have?** (name specific products from `competitive-intel.md`)
- **Where is the gap?** (what those tools don't do that the product does)

### System of Record vs. System of Intelligence
This is the most powerful B2B framing for any AI-powered product:
- **System of record**: Where humans manually review, verify, and key in results. The system stores what someone concluded.
- **System of intelligence**: Where AI does the analysis, comparison, or reconciliation. The system does the concluding.
- Frame it as: "[Existing tool] is where your team records that [task] was done. But someone still had to [manual steps]. [Product] automates the [task] itself."

### Lumif.ai Core Positioning (auto-loaded from context store)
- "Contract-to-coverage review" is Lumif.ai's coined term for the end-to-end compliance process
- AI reads the contract, reads the policy/evidence document, does the reconciliation
- Primary sales wedge across all verticals
- Three modules: Insurance Compliance (primary wedge), Wrap Programme Management (US CCIP/OCIP), Vendor Pre-Qualification
- Broader capability hint: the same engine can reconcile ANY contract requirement against supplier evidence

---

## Step 2: Research the Vertical

For any vertical, research these dimensions before writing. Check `vertical-strategy.md` and `references/vertical-guide.md` first — if the vertical is already researched, skip to Step 3.

### 1. Industry-Specific Pain
- What's the high-stakes failure scenario? (The one that makes the front page)
- What regulatory or legal consequences exist?
- What's the financial exposure from the manual process failing?

### 2. Existing Ecosystem
- What tools does the buyer already use? (Name them specifically)
- What prequalification / compliance systems exist?
- Where does manual work still happen despite these tools?

### 3. Terminology
- What do they call their stakeholders? (suppliers, vendors, contractors, partners)
- What do they call their agreements? (contracts, frameworks, MSAs, SLAs)
- What do they call compliance roles? (risk manager, compliance officer, procurement)
- What's the buyer entity called? (principal contractor, asset owner, operator)

### 4. Regulatory Landscape
- Who regulates this sector?
- What triggers enforcement?
- What due diligence defence exists?
- Are there investment or compliance cycles that drive urgency?

### 5. Buyer Persona
- Who has the problem? (operational role)
- Who has the budget? (Finance Director, VP, C-suite)
- What keeps them up at night?

See `references/research-framework.md` for the full research checklist and example output.

**After researching a new vertical**: Write findings back to the context store (see Writes table above). This ensures meeting-prep, outbound, and other skills benefit from the research.

**CRITICAL: Getting the domain wrong invalidates everything downstream.** If you don't deeply understand the buyer's world (regulatory mandates, workflows, terminology, economics), the doc will be corrected by the user. For unfamiliar domains, do thorough web research before writing. Example: WC premium audit is a mandatory annual reconciliation process, not a post-claims activity. Getting this wrong required a complete rewrite.

---

## Step 2.5: Brainstorm Before Building

**Do not skip this step.** Before writing any copy, align with the user on:

1. **Audience**: Who exactly picks this up? (A partner's COO is different from a carrier's VP of audit)
2. **Framing**: What is the core message? Draft 3-5 headline directions and discuss.
3. **Structure**: What sections does this doc need? Sketch the layout.
4. **Metrics**: What stats or proof points should appear? Which are defensible?

Present options, get alignment, then write. The cost of rewriting a finished doc is 10x the cost of aligning on structure upfront. In practice, headline and audience framing take 2-3 rounds to land.

---

## Step 3: Write the Content

### Content Principles

These principles apply universally to all B2B sales documents.

**1. Concrete Scenarios Over Statistics in Headlines**

Bad: "70% of submissions are non-compliant"
Good: "[Specific failure scenario 1]. [Specific failure scenario 2]. [Specific failure scenario 3]. How many are in your [organisation/portfolio/pipeline] right now?"

Use three specific failure types that hit different fear centres for the target buyer.

**2. Name Their Actual Tools in the Competitive Gap**

Bad: "Existing tools check fields. Document management stores files."
Good: "[ToolName1] and [ToolName2] do [what they do well]. Your team records that [task] was done. But someone still had to [manual steps]. [Product] automates the [task] itself."

Pull named tools from `competitive-intel.md` or `references/vertical-guide.md`.

**3. The Real Problem Panel (3 columns)**

Use self-evidently true qualitative descriptions:
- Column 1: The nature of the manual work (slow, error-prone, can't scale)
- Column 2: The timing problem (point-in-time check, not ongoing monitoring)
- Column 3: The accountability gap (no audit trail, no traceability when something goes wrong)

These should NOT need sources because they describe observable reality.

**4. Outcome-First Bullets**

Bold lead-ins describe what changes for the PERSON, not what the SOFTWARE does:
- Good: "Your team stops [painful manual task]."
- Good: "AI reads [input A], reads [input B], does the [reconciliation/comparison/analysis]."
- Bad: "Upload a document and requirements are extracted automatically."

**5. Defensible Due Diligence / Audit Trail**

Every sector has a trigger event. Address it directly:
- "Full audit trail demonstrating systematic [verification/review]. When [trigger event] arises, you can show exactly what was checked, when, and against which [clause/requirement/standard]."

**6. Expected Outcomes Table**

| Metric | Manual Process | With [Product] |
|--------|---------------|----------------|

"Manual Process" column: blend honest qualitative descriptions with sourced numbers where available.
"With [Product]" column: product outcomes with * citation and honest caveat footnote.

**7. Transparent Sourcing**

**Every metric in the document must have a footnote.** No exceptions. Use superscript numbers (not asterisks) for all sources.

Source quality tiers (flag in footnotes):
- **First-party**: Their own pricing page, annual report, press release. Most reliable.
- **Third-party**: Independent journalism, industry reports, regulatory filings. Reliable.
- **Competitor source**: A competing vendor's blog or comparison page. Flag potential bias.
- **Inferred**: Derived from multiple data points. Explain the reasoning in the footnote.

Rules:
- Your own coined terms don't need sourcing
- Self-evidently true descriptions don't need sources
- Never present vendor blog sources as independent research
- Be honest about what each number is and where it came from
- If a number is inferred (not directly stated in any source), label it as such and explain the derivation

**8. Broader Capability Hint**

End with one italicised line:
- "The same engine that [does primary thing] can [do broader thing]: [examples]."

**9. CTA**

Specific, low-friction, value-giving:
- "Book a 15-minute call. We'll show you what [core capability] looks like for your [projects/portfolio/organisation]. [website]"
- NOT: "Contact us to learn more"
- NOT: "Request a demo"

**10. Spell Out Technical Terms**

Always spell out abbreviations on first use. If the reader can't forward the doc to their Finance Director without explanation, the doc isn't ready.

---

### Visual Design Principles

**11. Minimal Brand Colour Usage**

Brand colour (#E94D35) appears in: section headings, one status quo panel, the table header row, and the "With [Product]" column values. That's it.

**12. Subdued Bullets**

Bullet points use grey (#9CA3AF), not brand colour. The bold lead-in text does the work.

**13. One-Page Fit**

Value prop one-pagers MUST fit on one page. Write tight copy upfront. If it spills, tighten copy first (don't reduce font sizes below readability).

**14. Clean Visual Hierarchy**

One page should have at most three visual weights: the headline, one shaded data panel, and one branded table. Everything else is clean text.

---

## Step 4: Build the Document

Read the docx skill reference:
```
view ~/.claude/skills/document-skills/docx/SKILL.md
```

### Brand Template

Use `~/.claude/brand-assets/lumifai-page-template.docx` as the base template. See `references/template-specs.md` for full brand specs including colours, fonts, sizing, and build process.

Key specs (aligned to design-guidelines.md):
- Primary accent: #E94D35
- Headlines: #121212 (dark)
- Body: Inter/Arial
- Section headings: brand accent
- Remove footer bar for value prop docs to save space

If a branded template exists, use the unpack/edit XML/repack workflow to preserve branding. Otherwise, create from scratch using the docx skill.

Always verify: convert to PDF, check page count, visually inspect.

### Docx Rebuild Protocol

Repeated in-place zip updates to a .docx file can corrupt it. If a file won't open after multiple edit cycles:
1. Delete the corrupted output file
2. Create a fresh zip from the unpacked directory: `cd /tmp/unpacked-dir && zip -r -0 /tmp/fresh.docx . -x ".*"`
3. Copy to the output location
4. Verify it opens before continuing with further edits

---

## Step 5: Critical Self-Review

Before presenting, review as if you're the target buyer:

1. **Would I call bullshit on any claim?** If a number feels inflated or a source feels weak, remove or reframe.
2. **Does the competitive gap respect existing tools?** Never trash tools the buyer already uses. Acknowledge what they do well, then show the gap.
3. **Is every technical term explained?** Could a Finance Director read this without Googling?
4. **Is the headline concrete or abstract?** Scenarios beat statistics.
5. **Is the "Manual Process" column honest?** Descriptions of reality are stronger than sourced stats from vendor blogs.
6. **Is there a due diligence / audit trail angle?** This is what keeps senior compliance and risk buyers up at night.
7. **Are the claims transparent about their source?** Industry data clearly marked. Product data clearly marked.
8. **Would I forward this internally?** If a middle manager wouldn't send this to their director for budget approval, the doc isn't ready.

Rate the document honestly (1-10) and explain what would improve it.

---

## Step 6: Present and Iterate

Present the document with:
- A critical review from the target buyer's perspective
- Flagged claims that could be challenged
- Terminology that might be too jargon-heavy
- An honest rating and what would push it higher

---

## Case Study Specific Guidance

### Customer Profile Realism
- Validate company size, employee count, team structure, project volume against industry norms
- Err conservative. A slightly understated profile is more credible than an inflated one.

### Narrative Arc
Pain --> Turning Point --> Solution --> Proof --> Future
- **Pain**: Describe the operational reality (not feature gaps)
- **Turning point**: A specific incident that made the status quo untenable
- **Solution**: What changed and why this product (the competitive gap, not a feature list)
- **Proof**: Results with specific numbers tied back to the turning point
- **Future**: What they plan to do next (signals expansion value)

### Quotes
- Situational and specific, not generic praise
- Reference specific incidents, numbers, or timeframes
- Tie the closing quote back to the opening pain point
- Attribution: use title only (not name) for hypothetical case studies

### Stats Banner (Standard Component for All One-Pagers)

A stats banner is a standard top-of-page element for both value prop one-pagers and partnership pitches. Place it directly below the headline.

- 3-4 metrics in a horizontal row with warm tint background (#FFF8F6)
- Numbers in brand accent (#E94D35), bold, larger size (12-14pt)
- Descriptions in muted grey (#9CA3AF), smaller size (7.5-8pt)
- Each metric has a superscript footnote number linking to sources at the bottom
- Use different number formats for variety: percentage, absolute number, currency, zero/none
- Each metric independently meaningful and defensible
- Footnotes at doc bottom: grey (#AAAAAA), smallest size (6-7pt), with source name and year

---

## Terminology Rules

- "Contract-to-coverage review" (not "contract-to-evidence reconciliation")
- "Trade contractors" (UK construction), "contractors" / "supply chain partners" (water utilities), "subcontractors" (US construction)
- "Finance Director" (UK), "CFO" (US)
- "Turnover" (UK), "revenue" (US)
- Avoid em dashes throughout
- Spell out all insurance types on first use

### Naming Rules for External Documents

- **Never coin abbreviations** the prospect doesn't use publicly. Check their website, brochures, and prior conversations. If they don't use a shorthand, neither should we. Use their full name on first mention, then a natural short form (e.g., "The Amphibious Group" -> "Amphibious", never "TAG" unless they use it).
- **Never name internal contacts by first name** in external docs. Reference roles and activities instead (e.g., "building insurance carrier relationships" not "Ken is building carrier relationships"). Internal people change roles; docs persist.
- **Company names must match their own branding.** Check capitalization, spacing, and legal name. "lumif.ai" not "Lumif.ai". "The Amphibious Group" not "Amphibious Group" on first mention.

---

## Multi-Document Sets

When creating multiple docs for the same account (e.g., Doc 1: compliance, Doc 2: audit):
- **Consistent headline style** across the set (same font, same weight, same line structure)
- **Consistent stats banner format** (same background color, same number styling, same footnote format)
- **Cross-reference between docs** where relevant (e.g., Doc 2 timeline references "Deploy Doc 1 products first")
- **Consistent terminology** (if Doc 1 uses "Amphibious", Doc 2 must too, not "The Amphibious Group" in one and "TAG" in another)
- **Same CTA format** across the set

---

## Deliverables (Standard 6)

Every run MUST end with a clear deliverables block:

```
## Deliverables
- Document: /path/to/output.docx
- PDF preview: /path/to/output.pdf (if generated)
- Vertical: [which vertical]
- Type: [value-prop | partnership-pitch | case-study-1p | case-study-2p]
- Rating: [1-10] with improvement notes
- Context store updates: [list files written to, or "none"]
```

---

## Tool Access (Web Platform)

When running on the web platform, you have access to these tools via tool_use:

- **context_read**: Read context files. Call with `{"file": "company-intel"}` to read a context file.
- **context_write**: Write to context files. Call with `{"file": "company-intel", "content": ["line1", "line2"], "detail": "description", "confidence": "high"}`.
- **context_query**: Search across context. Call with `{"search": "search terms"}`.
- **web_search**: Search the web. Call with `{"query": "search query"}`. Limited to 20 searches per run.
- **web_fetch**: Fetch and extract text from a URL. Call with `{"url": "https://..."}`.
- **file_write**: Save generated output. Call with `{"filename": "output.html", "content": "<html>...", "mimetype": "text/html"}`.

When running in Claude Code (CLI), use direct Python calls to context_utils instead.

## Reference Files

- `references/research-framework.md` — Detailed vertical research checklist and example research output
- `references/template-specs.md` — Brand template specifications (colours, fonts, sizing, build process)
- `references/vertical-guide.md` — Sector-specific knowledge for proven verticals (construction, water utilities)
