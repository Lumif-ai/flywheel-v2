---
name: quick-valuation
description: "Fast, executive-style company valuation — 1-2 page summary with named comparable companies, implied valuation range, and key risks. No methodology explanation. Use when a user wants a quick company valuation, back-of-envelope estimate, comps-based valuation, executive summary valuation, or says 'quick valuation', 'what is this company worth', 'ballpark valuation', 'value this quickly', 'comps analysis', or 'how much is X worth'. Produces concise, board-ready output assuming the audience understands finance. Triggers on any valuation request where speed and conciseness matter more than a full report. Also use when user explicitly asks for a 'quick' or 'short' or 'executive' valuation."
---

# Quick Valuation — Executive Style

Produce a **1-2 page valuation memo** styled like a corporate development team's internal note. No methodology lectures. Named comps. Straight to the number.

## Output Structure

Generate a Word document (.docx) with exactly these sections:

### Page 1: Valuation Summary

**Header block:**
- Company name (large, bold), industry, date
- One-line business description
- "CONFIDENTIAL — For Internal Use Only"

**The Number** (prominent — first thing the reader sees, 16pt+ bold):
```
Enterprise Value Range: $XM — $YM
Central Estimate: $ZM (X.Xx Net Revenue | X.Xx EBITDA)
```

**Company Snapshot** — compact table, max 8 rows:

| Metric | Value |
|--------|-------|
| Net Revenue (TTM) | $X.XM |
| EBITDA (TTM) | $X.XM |
| EBITDA Margin | XX% |
| Revenue Growth (YoY / 3yr CAGR) | XX% / XX% |
| Employees | ~XXX |
| Geography | XX |

**Comparable Companies Table** — 5-8 real, named public companies or recent transactions:

| Company | EV ($M) | Rev ($M) | EBITDA ($M) | EV/Rev | EV/EBITDA | Notes |
|---------|---------|----------|-------------|--------|-----------|-------|
| [Real company] | ... | ... | ... | ... | ... | ... |
| **Comp Median** | | | | **X.Xx** | **X.Xx** | |
| **Target (adj.)** | | | | **X.Xx** | **X.Xx** | |
| **Implied EV** | | | | **$X.XM** | **$X.XM** | |

**Why Above/Below Comp Median** — 3-5 bullets, plain language:
- "Trades at discount because [small scale / private / geography]"
- "Warrants premium for [growth / IP / recurring revenue]"
- "Private company discount of ~25-35% applied"

### Page 2 (optional): Risks & Context

**Key Risks** — 3-5 one-line bullets
**Deal Context** — 2-3 sentences if relevant (acquisition, fundraising, JV)
**Sources** — compact citation list

---

## Workflow

### Step 1: Gather Inputs (Max 1 Round of Questions)

Scan what user provided. Ask at most **3 questions in 1 round**. If still missing info, assume and state assumptions. Minimum needed: revenue + EBITDA (1 year) + industry.

### Step 2: Find Named Comparable Companies

Use WebSearch to find **real companies with actual financial data**. This is the core differentiator — no unnamed "industry medians."

Search strategy:
1. `"[industry] public companies revenue EBITDA market cap 2025 2026"`
2. `"[industry] acquisition deal value 2025 2026"`
3. Fetch Damodaran sector multiples as cross-check from pages.stern.nyu.edu/~adamodar/

Build a table of 5-8 named comps. If exact financials unavailable, note "est." with source.

### Step 3: Calculate Implied Valuation

1. Take comp median EV/Revenue and EV/EBITDA
2. Apply to target's financials
3. Adjust for size (private discount 20-40%), growth, geography, revenue quality
4. State adjustments as plain-language bullets — no formulas
5. Run a quick internal DCF as sanity check — do NOT show the math, just note if it confirms or diverges from comps

### Step 4: Generate 1-2 Page .docx

Use python-docx. Formatting rules:
- Arial font, information-dense layout
- Valuation range: 16pt bold, prominent
- Tables: light blue headers (#D5E8F0), 9pt body
- CONFIDENTIAL in footer
- NO table of contents, NO methodology section, NO appendix, NO football field
- Maximum 2 pages

---

## Do NOT

- Explain what a DCF or multiple is
- Include a "Methodology" section
- Show WACC calculations
- Include an appendix
- Exceed 2 pages
- Use unnamed "industry median" multiples
- Ask more than 3 questions
- Add a football field chart

---

## Memory & Learned Preferences

This skill remembers valuation context to speed up repeat analyses.

**Memory file:** Check the auto-memory directory for `quick-valuation.md`:
```bash
cat "$(find ~/.claude/projects -name 'quick-valuation.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

### Loading preferences (at session start)

Before Step 1 (Gather Inputs), check for saved preferences. If found, load:

```
Learned preferences loaded:
├─ User's company: [e.g. "Lumif.ai — AI/SaaS, pre-revenue"]
├─ Industry: [e.g. "InsurTech / Construction Tech"]
├─ Preferred comp sets: [e.g. "always include Jones, TrustLayer, Constrafor"]
└─ Past valuations: [e.g. "2 valuations completed"]
```

If valuing the user's own company again, pre-fill known financials and ask only for updates.

### What to save after each run

- **User's company context** — if they're valuing their own company, save the basics
- **Industry classification** — so it doesn't need to be re-asked
- **Preferred comparable companies** — comps the user approved or added
- **Rejected comps** — companies the user said are not comparable (don't suggest again)
- **Valuation context pattern** — usually fundraising, acquisition, strategic, etc.
- **Output preferences** — where to save, formatting preferences

Use the Edit tool to update existing entries — never duplicate. Save to `~/.claude/projects/-Users-sharan-Projects/memory/quick-valuation.md`.

### What NOT to save

- Specific financial figures (may change rapidly)
- Valuation results (session-specific)
- Confidential deal context

