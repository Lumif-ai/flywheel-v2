---
name: valuation-expert
version: "1.0"
description: "Perform rigorous company valuations for any context — acquisition, joint venture, fundraising, strategic planning, litigation, tax, or internal benchmarking. Use this skill whenever a user asks to value a company, estimate enterprise value, calculate what a business is worth, run a DCF, apply revenue or EBITDA multiples, do comparable company analysis, or produce a valuation report. Also trigger when the user mentions 'valuation', 'what is my company worth', 'acquisition price', 'deal valuation', 'fundraising valuation', 'pre-money', 'post-money', 'EV/Revenue', 'EV/EBITDA', 'discounted cash flow', 'terminal value', 'WACC', or 'valuation memo'. Adapts methodology, premiums/discounts, and report framing to the user's stated purpose. Works for all company stages: pre-revenue, growth-stage, and mature. Produces a professional Word document (.docx) with full methodology transparency. Even if the user just shares financials and asks 'what is this worth', use this skill."
---

# Company Valuation Skill

## Overview

This skill produces **institutional-grade company valuations** as professional Word documents. It supports any valuation context — acquisition, joint venture, fundraising, strategic planning, litigation, tax, internal benchmarking, or other — and adapts its methodology, premiums/discounts, and report framing based on the user's stated purpose. It supports all company stages from pre-revenue to mature.

## Core Principle: Full Transparency

Every valuation produced by this skill must explicitly state:
1. What methods were used and WHY each was selected (or excluded)
2. What data sources informed the multiples/benchmarks (with citations)
3. What assumptions were made and the reasoning behind each
4. What the limitations are — no false precision

---

## Step 1: Gather Inputs from the User (Adaptive Questioning)

Before running any valuation, Claude MUST collect enough information to run a rigorous analysis. However, the user may provide partial data upfront — Claude should adapt its questions based on what is already known vs what is missing.

### How This Works

1. First, SCAN what the user already provided (financials, context clues, file uploads, industry mentions)
2. Then, ask ONLY for what is still missing — do NOT re-ask things the user already stated
3. Batch questions efficiently: use ask_user_input for structured choices and prose for open-ended gaps
4. If the user has given financials but no context, ask context questions. If they gave context but no financials, ask for financials. Adapt.

### Information Needed (check off what is already provided)

The following table lists everything needed. Claude should mentally check which items the user already provided and ONLY ask about the gaps.

| Category | What is Needed | Why It Matters | If Missing, Ask |
|----------|---------------|----------------|-----------------|
| **Industry** | Specific sector and sub-sector | Determines which multiples apply — SaaS vs manufacturing have wildly different EV/Revenue | Structured: ask_user_input with options |
| **Company Stage** | Pre-revenue, early-revenue, growth, or mature | Determines which valuation methods are valid | Can often be INFERRED from financials (negative EBITDA = early stage). Confirm if ambiguous |
| **Financial Data** | Revenue (gross and/or net), EBITDA at minimum. Ideally also: gross margin, net income, CapEx, working capital, debt, cash | Core inputs for every valuation method | Ask what is missing. If user gives revenue + EBITDA, ask about debt/cash/capex as follow-up |
| **Valuation Context** | Why is this being valued? (acquisition, JV, fundraising, strategic planning, litigation, tax, etc.) | Drives which premiums/discounts apply, which methods to emphasize, and how the report is framed | Structured: ask_user_input with options including Acquisition, Joint Venture, Fundraising, Strategic Planning, Litigation/Tax, Other |
| **Geography** | Where the company primarily operates | Affects country risk premium in WACC, comparable selection | Structured: ask_user_input with options |
| **Revenue Model** | Recurring/subscription vs project/transactional vs hybrid | Recurring revenue commands significant premium in multiples | Structured: ask_user_input |
| **Growth Data** | Historical growth rates (Claude can calculate from provided financials) and any forward projections | Drives DCF projections and growth premium adjustments | If user provided multi-year data, CALCULATE the CAGR yourself. Only ask if single year of data. |
| **Balance Sheet** | Debt, cash, any significant liabilities or assets | Needed for Enterprise Value to Equity Value bridge | Open-ended: ask if not provided |
| **Comparable Context** | Any known competitors, recent deals, or offers received | Anchoring data for comparable analysis | Open-ended: ask but make clear this is optional |
| **Strategic Factors** | IP, patents, key contracts, regulatory approvals, customer concentration, team/talent | Qualitative factors that affect strategic premium or discount | Open-ended: ask but make clear this is optional |

### Adaptive Question Flow

**Scenario A: User provides financials + industry**
- Skip industry and financial questions
- Ask: valuation context, geography, revenue model, balance sheet, strategic factors
- Calculate growth rates from provided data

**Scenario B: User provides financials only (no industry/context)**
- Ask: industry (structured), valuation context (structured), geography (structured), revenue model (structured)
- Ask open-ended: balance sheet, strategic factors
- Calculate growth from provided data

**Scenario C: User provides minimal info ("value my company")**
- Ask ALL structured questions in one batch: industry, context, geography, revenue model
- Ask for financials: "Please share your financial data — at minimum I need revenue and EBITDA for 1-2 years. More years = better analysis."
- Follow up with: balance sheet, strategic factors

**Scenario D: User provides a full data package (financials + industry + context)**
- Ask ONLY about gaps: balance sheet details, strategic factors, any known comparables
- Proceed to valuation quickly

### Question Batching Rules
- Use ask_user_input for all structured/bounded questions — batch up to 3 at a time
- Ask open-ended questions (balance sheet, strategic factors, comparables) in prose AFTER the structured questions
- NEVER ask more than 2 rounds of questions total before starting the valuation. If information is still missing after 2 rounds, state your assumptions clearly and proceed
- If the user seems eager to get results, minimize questions and state assumptions instead

---

## Step 2: Select Valuation Methods

Based on inputs, select from methods below. Always use at least 2 methods to triangulate. Read `references/valuation-methods.md` for detailed formulas.

### Method Selection Matrix

| Company Profile | Primary Method | Secondary Method | Tertiary |
|----------------|---------------|-----------------|----------|
| Pre-revenue / Very early | Comparable Transactions, Scorecard | Berkus Method | — |
| Early revenue, EBITDA negative | EV/Revenue Multiples | DCF (with scenario analysis) | Comparable Transactions |
| Growth stage, EBITDA positive | EV/Revenue + EV/EBITDA | DCF | Comparable Transactions |
| Mature, stable cash flows | DCF | EV/EBITDA | Comparable Companies |

### Context-Specific Adjustments (apply based on user's stated valuation purpose)

**Acquisition:**
- Include a control premium discussion (typically 20-40% over standalone value, per Damodaran)
- Include a synergy adjustment section (revenue + cost synergies, even if qualitative)
- Weight comparable transactions more heavily (they embed control premiums)
- Frame the report as a "Valuation Memorandum" for deal negotiation

**Joint Venture:**
- Value the contribution each party brings, not just the whole entity
- Apply proportional value based on assets/IP/revenue contributed
- Consider ongoing value creation vs upfront contribution
- Frame the report around "Contribution Valuation" and implied ownership splits

**Fundraising (Series A/B/C/Growth):**
- Focus on forward-looking multiples (NTM revenue) more than trailing
- Weight revenue multiples heavily — investors price on growth trajectory
- Include a pre-money / post-money framework
- Apply venture-stage discount rates if early (40-60% for seed/A, 25-35% for B/C)
- Frame the report as a "Valuation Analysis" supporting fundraising discussions
- Reference recent comparable funding rounds in the sector

**Strategic Planning / Internal Benchmarking:**
- Use standalone value without control or synergy premiums
- Emphasize sensitivity analysis — what levers drive value up or down
- Frame the report as a "Strategic Valuation Assessment"
- Include scenario planning tied to strategic initiatives

**Litigation / Tax / Regulatory:**
- Use the most defensible methods (DCF + comparable transactions preferred by courts)
- Apply fair market value standard (willing buyer / willing seller, no compulsion)
- Extra rigor on sourcing — every assumption must be citable
- Apply appropriate discounts: lack of marketability (DLOM), lack of control (DLOC) per IRS guidelines
- Frame the report as a "Fair Market Value Opinion"

**Other / Custom:**
- Ask the user what the valuation will be used for and who the audience is
- Adapt framing and methodology emphasis accordingly

---

## Step 3: Source Multiples and Benchmarks

### READ: references/industry-multiples.md

This file contains embedded institutional data tables with EV/Revenue and EV/EBITDA multiples by industry sourced from Damodaran NYU Stern datasets, sector-specific guidance, and size/stage adjustments.

### Data Source Hierarchy (USE THIS ORDER)

1. **Aswath Damodaran datasets (NYU Stern)** — Primary source for:
   - Industry EV/Revenue, EV/EBITDA, EV/EBIT multiples (updated annually, ~45,000 global public companies)
   - Industry betas (levered and unlevered)
   - Cost of capital by sector
   - Country risk premiums
   - Source: https://pages.stern.nyu.edu/~adamodar/
   - Citation: "Damodaran, A. (2025). [Dataset Name]. NYU Stern School of Business."

2. **U.S. Federal Reserve Economic Data (FRED)** — For:
   - Risk-free rate (10-Year Treasury yield)
   - Source: https://fred.stlouisfed.org/

3. **SEC EDGAR** — For:
   - Public comparable company financials (10-K, 10-Q)
   - Transaction details in proxy statements

4. **PitchBook / S&P Capital IQ** — For:
   - Private company transaction multiples
   - VC/PE deal benchmarks

5. **Reliable Web Sources ONLY if institutional sources insufficient**:
   - McKinsey, Bain, BCG research reports
   - Big 4 valuation publications (Deloitte, PwC, EY, KPMG)
   - CFA Institute publications
   - NEVER: blog posts, generic finance websites, Reddit, Quora

### When Using Web Search
- Search for specific institutional sources: "Damodaran EV Revenue multiples 2025"
- Search for specific transactions: "[company name] acquisition valuation SEC filing"
- ALWAYS cite the source in the report
- NEVER present web-sourced data without attribution

---

## Step 4: Build the Valuation

Read `references/valuation-methods.md` for detailed calculation frameworks.

### 4a. Revenue Multiple Approach
1. Identify correct industry median EV/Revenue from Damodaran (references/industry-multiples.md)
2. Apply stage adjustments: early-stage = 30-50% illiquidity/size discount (Damodaran small-firm premium)
3. Apply growth premium/discount vs industry median growth
4. Calculate: Enterprise Value = Selected Multiple x Revenue (TTM or forward)
5. State the multiple range (25th to 75th percentile) for valuation range

### 4b. EBITDA Multiple Approach (only if EBITDA > 0)
1. Identify industry median EV/EBITDA from Damodaran
2. Normalize EBITDA: add back one-time items, above-market owner comp, etc.
3. Apply similar adjustments
4. Calculate: Enterprise Value = Selected Multiple x Normalized EBITDA

### 4c. DCF Approach
1. Build 5-year projections (user-provided or extrapolate from historical CAGR)
2. Free Cash Flow = EBITDA - Taxes - CapEx - Change in Working Capital
3. Determine WACC:
   - Risk-free rate (FRED 10-Year Treasury)
   - Equity risk premium (Damodaran ~4.5-5.5% for US)
   - Beta (Damodaran industry betas)
   - Size premium (Kroll/Duff & Phelps: 2-6% for small companies)
   - Country risk premium (Damodaran, if non-US)
4. Terminal value: Gordon Growth Model at 2-3% long-term growth
5. Discount all cash flows to present
6. ALWAYS run 3 scenarios: Base, Optimistic, Conservative

### 4d. Comparable Transactions (if data available)
- Search for recent M&A transactions in same sector
- Note implied multiples
- Adjust for size, growth, and strategic premium differences

---

## Step 5: Produce the Valuation Range

NEVER present a single-point valuation. Always present:
- A range (low to high) with methodology driving each bound
- A weighted central estimate with explicit weights and reasoning
- A football field chart description (visual range comparison)

### Weighting Guidance
| Scenario | Revenue Multiple Wt | EBITDA Multiple Wt | DCF Wt |
|----------|---------------------|-------------------|--------|
| Pre-profit growth company | 50-60% | 0-10% | 30-40% |
| Early profitable company | 30-40% | 30-40% | 20-30% |
| Mature stable company | 10-20% | 30-40% | 40-50% |

---

## Step 6: Generate the Word Document

Use the docx skill (read /mnt/skills/public/docx/SKILL.md). The document must include:

### Required Document Structure

1. **Cover Page**: Company name, context-appropriate title (e.g. "Valuation Memorandum" for acquisition, "Contribution Valuation" for JV, "Valuation Analysis" for fundraising, "Strategic Valuation Assessment" for planning, "Fair Market Value Opinion" for litigation/tax), date, stated purpose, "CONFIDENTIAL"
2. **Executive Summary** (1 page): Valuation range, primary methodology, one-paragraph conclusion
3. **Company Overview**: Industry, stage, key metrics, historical financial summary table
4. **Methodology Section**: Methods used and WHY, methods excluded and WHY, data sources with citations
5. **Detailed Valuation Analysis**: For each method: inputs, assumptions, calculation, result. All assumptions explicit.
6. **Valuation Summary**: Side-by-side comparison, weighting rationale, final range
7. **Key Assumptions and Limitations**: Every material assumption listed, what could change the valuation, unavailable data
8. **Appendix**: Financial projections, comparable data, source citations

### Formatting Requirements
- Professional fonts (Arial)
- Tables with light blue header shading (#D5E8F0)
- Currency in millions to 2 decimals (e.g., $2.83M)
- Page numbers in footer
- CONFIDENTIAL header note
- Table of contents

---

## Memory & Learned Preferences

This skill remembers valuation context and methodology preferences across sessions.

**Memory file:** Check the auto-memory directory for `valuation-expert.md`:
```bash
cat "$(find ~/.claude/projects -name 'valuation-expert.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

### Loading preferences (at session start)

Before Step 1 (Gather Inputs), check for saved preferences. If found, load:

```
Learned preferences loaded:
├─ User's company: [e.g. "Lumif.ai — AI/SaaS, pre-revenue, Delaware C-corp"]
├─ Industry: [e.g. "InsurTech / Construction Tech"]
├─ Preferred methods: [e.g. "always include DCF + EV/Revenue"]
├─ Comp preferences: [e.g. "approved comps: Jones, TrustLayer"]
└─ Past valuations: [e.g. "3 valuations — 2 fundraising, 1 strategic"]
```

Pre-fill known context and skip redundant questions. If valuing the same company, ask only for updated financials.

### What to save after each run

- **User's company context** — entity, industry, stage, geography
- **Industry classification** — sector and sub-sector for multiple lookups
- **Methodology preferences** — which methods the user values most, which to skip
- **Preferred comparable companies** — comps the user approved
- **Rejected comps** — companies the user said don't apply
- **Valuation context pattern** — typical purpose (fundraising, M&A, etc.)
- **Data source preferences** — preferred sources, any subscriptions available
- **Report format preferences** — level of detail, sections emphasized
- **Feedback corrections** — assumptions the user disagreed with

Use the Edit tool to update existing entries — never duplicate. Save to `~/.claude/projects/-Users-sharan-Projects/memory/valuation-expert.md`.

### What NOT to save

- Specific financial projections (change rapidly)
- Valuation results or ranges (session-specific)
- Confidential deal terms

## Critical Rules

1. Never present false precision — "$4.7M to $8.2M" is more honest than "$6.45M"
2. Always cite sources — every multiple, rate, and benchmark needs a named source
3. Always state assumptions — if you assumed something, say so explicitly
4. Acknowledge limitations — limited data, private company discounts, market conditions
5. Use ranges not points — min 3 scenarios for DCF, percentile ranges for multiples
6. Context drives the framework — acquisition adds control premium and synergies, fundraising emphasizes forward multiples, litigation requires defensible fair market value, JV values contributions. Always apply context-specific adjustments from Step 2.
7. Round appropriately — sub-$50M: nearest $0.1M; larger: nearest $1M
