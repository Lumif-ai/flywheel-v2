---
name: one-pager
version: "1.0"
context-aware: true
web_tier: 1
token_budget: 8192
description: >
  Create professional B2B value proposition one-pagers that survive scrutiny
  from senior buyers. Sector-specific, data-backed, single-page documents for
  cold outreach and first meetings. Use when anyone asks to create a one-pager,
  value prop, value proposition doc, sales one-pager, or marketing one-pager.
  Also triggers on "create a one-pager for [vertical]", "make a value prop",
  "sales collateral", or any request to produce a professional single-page
  sales document. Produces structured JSON output for rich rendering in the
  Flywheel library with PDF/DOCX export.
tags:
  - sales
  - collateral
parameters:
  output_schema:
    type: object
    required:
      - schema_version
      - document_type
      - headline
      - stats_banner
      - problem_columns
      - outcomes
      - comparison_table
      - footnotes
      - audit_trail
      - cta
      - capability_hint
    properties:
      schema_version:
        type: string
      document_type:
        type: string
        enum:
          - value-prop-one-pager
      vertical:
        type:
          - string
          - "null"
      target_market:
        type:
          - string
          - "null"
      headline:
        type: string
      subheadline:
        type:
          - string
          - "null"
      stats_banner:
        type: array
        items:
          type: object
          required:
            - value
            - label
          properties:
            value:
              type: string
            label:
              type: string
            footnote_id:
              type:
                - integer
                - "null"
          additionalProperties: false
      problem_columns:
        type: array
        items:
          type: object
          required:
            - title
            - description
          properties:
            title:
              type: string
            description:
              type: string
          additionalProperties: false
      outcomes:
        type: array
        items:
          type: object
          required:
            - lead
            - detail
          properties:
            lead:
              type: string
            detail:
              type: string
          additionalProperties: false
      comparison_table:
        type: object
        required:
          - columns
          - rows
        properties:
          columns:
            type: array
            items:
              type: string
            minItems: 2
            maxItems: 2
          rows:
            type: array
            items:
              type: object
              required:
                - metric
                - manual
                - product
              properties:
                metric:
                  type: string
                manual:
                  type: string
                product:
                  type: string
                footnote_id:
                  type:
                    - integer
                    - "null"
              additionalProperties: false
        additionalProperties: false
      audit_trail:
        type: object
        required:
          - title
          - description
        properties:
          title:
            type: string
          description:
            type: string
        additionalProperties: false
      capability_hint:
        type: string
      cta:
        type: object
        required:
          - text
        properties:
          text:
            type: string
          url:
            type:
              - string
              - "null"
        additionalProperties: false
      footnotes:
        type: array
        items:
          type: object
          required:
            - id
            - source
            - quality
          properties:
            id:
              type: integer
            source:
              type: string
            quality:
              type: string
              enum:
                - first-party
                - third-party
                - competitor
                - inferred
          additionalProperties: false
    additionalProperties: false
---

# Value Proposition One-Pager

Create professional, defensible, sector-specific value proposition one-pagers that survive scrutiny from senior buyers.

**Changelog:**
- v1.0.0 (2026-04-10): Initial Flywheel version — extracted from sales-collateral v2.1, structured JSON output, context store integration

---

## What This Skill Does

Produces a single branded value proposition one-pager for a specific vertical/industry:
- Sector-specific, data-backed, single-page document
- Designed for cold outreach, first meetings, and leave-behinds
- Rendered as a rich interactive page in the Flywheel library
- Downloadable as PDF or DOCX

---

## Step 0: Gather Inputs

Before creating the one-pager, establish:

1. **Product/company**: What does the product do? (Auto-fill from context store `positioning` and `product-modules` if available)
2. **Target vertical**: Which industry is this for? (Check context store `vertical-strategy` for existing knowledge)
3. **Target market**: Geography? (affects terminology, currency, regulatory references — defaults to US)
4. **Target reader**: Who picks this up? (Check context store `icp-profiles` for existing personas)
5. **Competitive landscape**: What existing tools/processes does the buyer already use? (Check context store `competitive-intel`)

Load context silently via `flywheel_read_context`. Auto-apply data and show the user what was used. Only ask for what's genuinely missing.

---

## Step 1: Understand the Product Positioning

Before writing, establish the core positioning framework. Read context store `positioning` and `product-modules` first.

### The Displacement Question
Every B2B product displaces something. Understand what:
- **What does the buyer do today?** (manual process, spreadsheets, existing software, nothing)
- **What tools do they already have?** (name specific products from context store `competitive-intel`)
- **Where is the gap?** (what those tools don't do that the product does)

### System of Record vs. System of Intelligence
This is the most powerful B2B framing for any AI-powered product:
- **System of record**: Where humans manually review, verify, and key in results. The system stores what someone concluded.
- **System of intelligence**: Where AI does the analysis, comparison, or reconciliation. The system does the concluding.
- Frame it as: "[Existing tool] is where your team records that [task] was done. But someone still had to [manual steps]. [Product] automates the [task] itself."

### Core Positioning
Read current positioning from context store. The positioning anchors all content decisions.

---

## Step 2: Research the Vertical

For any vertical, research these dimensions before writing. Check context store `vertical-strategy` first — if the vertical is already researched, skip to Step 2.5.

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

**CRITICAL: Getting the domain wrong invalidates everything downstream.** If you don't deeply understand the buyer's world (regulatory mandates, workflows, terminology, economics), the doc will be corrected by the user. For unfamiliar domains, do thorough web research before writing.

**After researching a new vertical**: Write findings back to context store via `flywheel_write_context` (pain-points, competitive-intel, icp-profiles, vertical-strategy, market-stats). This ensures meeting-prep, outbound, and other skills benefit from the research.

---

## Step 2.5: Brainstorm Before Building

**Do not skip this step.** Before writing any copy, align with the user on:

1. **Audience**: Who exactly picks this up? (A partner's COO is different from a carrier's VP of audit)
2. **Framing**: What is the core message? Draft 3-5 headline directions and discuss.
3. **Structure**: What sections does this doc need? Sketch the layout.
4. **Metrics**: What stats or proof points should appear? Which are defensible?

Present options, get alignment, then write. The cost of rewriting a finished doc is 10x the cost of aligning on structure upfront.

---

## Step 3: Write the Content

### Content Principles

**1. Concrete Scenarios Over Statistics in Headlines**

Bad: "70% of submissions are non-compliant"
Good: "[Specific failure scenario 1]. [Specific failure scenario 2]. [Specific failure scenario 3]. How many are in your [organisation/portfolio/pipeline] right now?"

Use three specific failure types that hit different fear centres for the target buyer.

**2. Name Their Actual Tools in the Competitive Gap**

Bad: "Existing tools check fields. Document management stores files."
Good: "[ToolName1] and [ToolName2] do [what they do well]. Your team records that [task] was done. But someone still had to [manual steps]. [Product] automates the [task] itself."

Pull named tools from context store `competitive-intel`.

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

**7. Never Fabricate Numbers**

NEVER make up statistics, counts, or figures that are not sourced from research, public filings, or the user. This includes:
- Vendor counts, headcount, cost savings, or efficiency percentages that are not sourced
- Store counts, revenue figures, or operational details that are not from public filings or confirmed research
- Extrapolated or "reasonable estimate" numbers presented as fact

If a specific number would strengthen the copy but you don't have a source, either: (a) use a qualitative description instead, (b) use a sourced industry average with footnote, or (c) ask the user.

**8. Transparent Sourcing**

**Every metric in the document must have a footnote.** No exceptions. Use superscript numbers for all sources.

Source quality tiers (flag in footnotes):
- **first-party**: Their own pricing page, annual report, press release. Most reliable.
- **third-party**: Independent journalism, industry reports, regulatory filings. Reliable.
- **competitor**: A competing vendor's blog or comparison page. Flag potential bias.
- **inferred**: Derived from multiple data points. Explain the reasoning in the footnote.

Rules:
- Your own coined terms don't need sourcing
- Self-evidently true descriptions don't need sources
- Never present vendor blog sources as independent research
- If a number is inferred, label it as such and explain the derivation

**9. Broader Capability Hint**

End with one italicised line:
- "The same engine that [does primary thing] can [do broader thing]: [examples]."

**10. CTA**

Specific, low-friction, value-giving:
- "Book a 15-minute call. We'll show you what [core capability] looks like for your [projects/portfolio/organisation]. [website]"
- NOT: "Contact us to learn more"
- NOT: "Request a demo"

**11. Spell Out Technical Terms**

Always spell out abbreviations on first use. If the reader can't forward the doc to their Finance Director without explanation, the doc isn't ready.

### Visual Design Principles

**12. Minimal Brand Colour Usage**

Brand colour (#E94D35) appears in: section headings, one status quo panel, the table header row, and the "With [Product]" column values. That's it.

**13. Subdued Bullets**

Bullet points use grey (#9CA3AF), not brand colour. The bold lead-in text does the work.

**14. One-Page Fit**

Value prop one-pagers MUST fit on one page when exported as PDF. Write tight copy upfront.

**15. Clean Visual Hierarchy**

One page should have at most three visual weights: the headline, one shaded data panel, and one branded table. Everything else is clean text.

---

## Step 4: Critical Self-Review

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

## Step 5: Output Format

After self-review and user alignment, output the final one-pager as a **valid JSON object**. This structured format enables rich rendering in the Flywheel library.

You MUST output a JSON object with this exact structure as your final message. Do not wrap in markdown code fences. Do not include any text before or after the JSON.

```
{
  "schema_version": "1.0",
  "document_type": "value-prop-one-pager",
  "vertical": "the target vertical/industry",
  "target_market": "US",
  "headline": "2-3 line scenario-based headline (Content Principle #1)",
  "subheadline": "optional tagline or positioning statement",
  "stats_banner": [
    {
      "value": "47%",
      "label": "of submissions flagged for non-compliance",
      "footnote_id": 1
    }
  ],
  "problem_columns": [
    {
      "title": "Manual & Error-Prone",
      "description": "2-3 sentences describing the nature of the manual work"
    },
    {
      "title": "Point-in-Time Only",
      "description": "2-3 sentences describing the timing problem"
    },
    {
      "title": "No Audit Trail",
      "description": "2-3 sentences describing the accountability gap"
    }
  ],
  "outcomes": [
    {
      "lead": "Your team stops manually reviewing every submission",
      "detail": "AI reads the contract requirements, reads the supplier evidence, and does the reconciliation automatically."
    }
  ],
  "comparison_table": {
    "columns": ["Manual Process", "With ProductName"],
    "rows": [
      {
        "metric": "Review time per submission",
        "manual": "4-6 hours of analyst time",
        "product": "Under 15 minutes*",
        "footnote_id": 2
      }
    ]
  },
  "audit_trail": {
    "title": "Defensible Due Diligence",
    "description": "Full audit trail demonstrating systematic review. When regulators ask, you can show exactly what was checked, when, and against which requirements."
  },
  "capability_hint": "The same engine that reviews supplier compliance can reconcile any contract requirement against supplier evidence: insurance certificates, safety documentation, financial disclosures.",
  "cta": {
    "text": "Book a 15-minute call. We'll show you what automated compliance review looks like for your portfolio.",
    "url": "https://lumif.ai"
  },
  "footnotes": [
    {
      "id": 1,
      "source": "Deloitte Global CPO Survey 2025",
      "quality": "third-party"
    },
    {
      "id": 2,
      "source": "Based on pilot with 3 enterprise customers, Q1 2026",
      "quality": "first-party"
    }
  ]
}
```

### Schema Rules
- `stats_banner`: 3-4 metrics. Use different number formats for variety (percentage, absolute, currency, zero).
- `problem_columns`: Exactly 3 columns per Content Principle #3.
- `outcomes`: 4-6 bullets per Content Principle #4.
- `comparison_table.rows`: 4-6 rows per Content Principle #6.
- `footnotes`: Every metric must have a footnote. Flag quality tier honestly.
- All text follows the content principles above — no fabricated numbers, concrete scenarios, named tools.

---

## Terminology Rules

- Use industry-specific terminology discovered in Step 2
- "Finance Director" (UK), "CFO" (US)
- "Turnover" (UK), "revenue" (US)
- Avoid em dashes throughout
- Spell out all technical terms and industry-specific abbreviations on first use

### Naming Rules for External Documents

- **Never coin abbreviations** the prospect doesn't use publicly
- **Never name internal contacts by first name** in external docs — reference roles instead
- **Company names must match their own branding** — check capitalization, spacing, and legal name

---

## Context Store Integration

### Reads — Load Before Writing

Before creating the document, silently read these context files via `flywheel_read_context`:

| File | What to extract |
|------|----------------|
| `positioning` | Core value propositions, messaging, differentiators |
| `competitive-intel` | Named competitor tools per vertical, competitive gaps |
| `product-modules` | Module descriptions, capabilities, moat analysis |
| `icp-profiles` | Buyer personas, validated ICPs with evidence |
| `pain-points` | Vertical-specific pain points with severity |
| `vertical-strategy` | Sector knowledge, market entry status, GTM approach |
| `market-stats` | Industry data points, proof points for sales narratives |
| `value-mapping` | Module-to-value translation per vertical and buyer |

Auto-apply this data silently. Show what was used, don't ask for confirmation.

### Writes — Feed Back After Research

When the skill researches a new vertical (Step 2), write findings back via `flywheel_write_context`:

| Finding | Write to |
|---------|----------|
| New vertical pain points | `pain-points` |
| New competitor tools discovered | `competitive-intel` |
| Vertical-specific buyer personas | `icp-profiles` |
| Sector regulatory/market data | `vertical-strategy` |
| Industry statistics found | `market-stats` |

---

## Flywheel MCP Integration

After generating the one-pager, save it to the library:

1. Call `flywheel_save_document(title="One-Pager: {Company} — {Vertical}", content=<the JSON output>, skill_name="one-pager", tags=["one-pager", "<vertical-slug>"])`
2. If for a specific account, include `account_id` from pipeline

---

## Error Handling

| Failure | Response |
|---------|----------|
| Context store empty | Proceed without enrichment — ask user for inputs directly, warn in output |
| Web research fails | Continue with context store data only, flag gaps |
| User provides no vertical | Ask — this is required, cannot proceed without it |
| Output exceeds one page | Tighten copy first (never reduce font sizes below readability) |
