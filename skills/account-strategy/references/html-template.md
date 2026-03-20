# HTML Template Specification

Defines the HTML output structure for account strategy briefings. Referenced by SKILL.md Phase 10.

**Design authority:** `~/.claude/design-guidelines.md` -- always read before generating HTML.

**Reference implementations:** Study the RMR Group and Amphibious Group briefings in `~/claude-outputs/companies/` for the quality bar. This template codifies their patterns.

---

## Page Setup

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{Company} - Account Strategy v{N} | lumif.ai</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { margin: 0; padding: 0; box-sizing: border-box; }
    /* All CSS inline -- single-file deployment, no external dependencies */
  </style>
</head>
```

---

## CSS Foundation (extract from RMR/TAG briefings)

### Variables & Base

```css
:root {
  --brand: #E94D35;
  --brand-light: rgba(233,77,53,0.1);
  --brand-glow: rgba(233,77,53,0.05);
  --bg: #FFFFFF;
  --bg-subtle: #FAFAFA;
  --bg-warm: #FFF8F6;
  --text: #121212;
  --text-secondary: #6B7280;
  --text-muted: #9CA3AF;
  --border: #E5E7EB;
  --blue: #3B82F6;
  --green: #22C55E;
  --orange: #F97316;
  --purple: #A855F7;
  --teal: #14B8A6;
  --red: #EF4444;
  --yellow: #EAB308;
}
body {
  font-family: 'Inter', -apple-system, sans-serif;
  color: var(--text);
  background: var(--bg);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.container { max-width: 1100px; margin: 0 auto; padding: 0 32px; }
```

**CRITICAL:** Max width is `1100px`, NOT `720px`. The wider layout gives cards, tables, and two-column layouts room to breathe.

### Header

```css
.header {
  background: linear-gradient(135deg, var(--text) 0%, #2d2d2d 100%);
  color: white;
  padding: 40px 0 30px;
  position: relative;
  overflow: hidden;
}
.header::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 4px;
  background: var(--brand);
}
.header .container {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.header h1 { font-size: 28px; font-weight: 800; margin-bottom: 4px; }
.header .subtitle { color: rgba(255,255,255,0.7); font-size: 14px; max-width: 600px; }
.header .meta { text-align: right; font-size: 13px; color: rgba(255,255,255,0.6); }
.status-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}
```

Header content (left side):
- H1: Company name (weight 800, NOT 600)
- Subtitle: one-line description of the briefing's scope
- Account type badge + version badge

Header content (right side):
- Status badge (e.g., "Cold Account", "Severity 5/5 Pain", "Promising - Pre-Commercial")
- Prepared date
- Status line (e.g., "Prospect, post-discovery")
- Champions / key contacts
- Introduced via (if applicable)

### Sticky Nav

```css
.nav-bar {
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border);
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.nav-bar .container { display: flex; gap: 6px; flex-wrap: wrap; }
.nav-link {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.2s;
}
.nav-link:hover { background: var(--brand-light); color: var(--brand); }
```

**Uses pill-shaped links with background hover**, not flat text with underline.

### Section Headings

```css
section { padding: 40px 0; }
section + section { border-top: 1px solid var(--border); }
h2 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}
h2 .icon {
  width: 32px; height: 32px;
  background: var(--brand-light);
  border-radius: 8px;  /* rounded square, NOT circle */
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}
```

Section icon is a **rounded square** (8px radius), NOT a circle. Contains the section number.

---

## Component Library

### Cards

```css
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
.card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.06); }
```

**Colored left-border cards** for semantic emphasis:
```css
/* Use these for contact cards, feature cards, risk cards */
.card[style*="border-left: 4px solid var(--green)"]  /* Champion */
.card[style*="border-left: 4px solid var(--blue)"]   /* Evaluator */
.card[style*="border-left: 4px solid var(--orange)"]  /* Pending / Advisor */
.card[style*="border-left: 4px solid var(--red)"]     /* Blocker / Danger */
.card[style*="border-left: 4px solid var(--brand)"]   /* lumif.ai / Primary */
```

### Info Grid

```css
.info-grid { display: grid; grid-template-columns: 160px 1fr; gap: 8px 16px; font-size: 14px; }
.info-label { color: var(--text-muted); font-weight: 500; }
.info-value { color: var(--text); }
```

**Uses `160px 1fr`** (fixed label width), NOT `1fr 1fr`. This gives a clean label:value alignment.

### Tables

```css
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border);
  font-size: 14px;
  margin: 16px 0;
}
thead th {
  background: var(--text);  /* DARK header, NOT gray */
  color: white;
  padding: 12px 16px;
  font-weight: 600;
  text-align: left;
  font-size: 13px;
}
tbody td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:nth-child(even) { background: var(--bg-subtle); }
```

**CRITICAL:** Table headers use `background: var(--text)` (#121212) with `color: white`. NOT gray background with uppercase gray text.

### Quotes

```css
.quote {
  background: var(--bg-warm);
  border-left: 4px solid var(--brand);
  padding: 16px 20px;
  border-radius: 0 12px 12px 0;
  font-size: 14px;
  font-style: italic;
  color: var(--text);
  margin: 12px 0;
}
.quote .attr {
  font-style: normal;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 6px;
  font-size: 12px;
}
```

Use quotes liberally. Every contact who said something notable in a meeting should be quoted with attribution.

### Callouts

```css
.highlight-box {
  background: linear-gradient(135deg, var(--brand-glow), rgba(59,130,246,0.04));
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  margin: 20px 0;
}
.callout-yellow {
  background: rgba(234,179,8,0.06);
  border: 1px solid rgba(234,179,8,0.25);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 20px 0;
}
.callout-red {
  background: rgba(239,68,68,0.04);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 20px 0;
}
.callout-green {
  background: rgba(34,197,94,0.04);
  border: 1px solid rgba(34,197,94,0.2);
  border-radius: 12px;
  padding: 20px 24px;
  margin: 20px 0;
}
```

- `highlight-box` = "Why This Matters" / "Our Play" callouts (use after every major section)
- `callout-yellow` = Warnings, open questions, things to clarify
- `callout-red` = Critical risks, deal-breakers
- `callout-green` = Good news, confirmed advantages

### Math Blocks (for pricing calculations)

```css
.math-block {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.8;
  margin: 12px 0;
  white-space: pre-wrap;
}
```

### Workflow Flow Diagrams

```css
.flow-container { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.flow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-subtle);
  border-radius: 8px;
  font-size: 13px;
}
.flow-arrow { color: var(--text-muted); font-size: 18px; flex-shrink: 0; }
```

Use for visualizing current workflows: `Step 1 -> Step 2 -> Step 3 -> etc.`

### Action Items

```css
.action-item {
  display: flex;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
}
.action-item:last-child { border-bottom: none; }
.action-num {
  width: 28px; height: 28px;
  background: var(--brand);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}
```

### Badges

```css
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 600;
}
.badge-green { background: rgba(34,197,94,0.12); color: #16a34a; }
.badge-blue { background: rgba(59,130,246,0.12); color: var(--blue); }
.badge-orange { background: rgba(249,115,22,0.12); color: var(--orange); }
.badge-red { background: rgba(239,68,68,0.12); color: var(--red); }
.badge-yellow { background: rgba(234,179,8,0.15); color: #a16207; }
.badge-purple { background: rgba(168,85,247,0.12); color: var(--purple); }
```

### Layouts

```css
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
@media (max-width: 768px) { .two-col, .three-col { grid-template-columns: 1fr; } }
```

### Compact Lists

```css
.compact-list { font-size: 14px; padding-left: 18px; color: var(--text-secondary); }
.compact-list li { margin-bottom: 8px; }
```

### Confidence Bar (for "What We Don't Know" section)

```css
.confidence-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 8px 0; }
.conf-confirmed { background: var(--green); }
.conf-single { background: var(--blue); }
.conf-inferred { background: var(--orange); }
.conf-unknown { background: var(--text-muted); }
```

### Source References

```css
.source-ref { font-size: 11px; color: var(--brand); font-weight: 500; cursor: pointer; }
.source-ref:hover { text-decoration: underline; }
```

Inline: `Revenue of $2.3B <a href="#source-s3" class="source-ref"><sup>[S3]</sup></a>`

### Footer

```css
.footer {
  background: var(--bg-subtle);
  border-top: 1px solid var(--border);
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}
```

### Print

```css
@media print {
  .nav-bar { display: none; }
  section { page-break-inside: avoid; }
  body { font-size: 11pt; }
  .header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
```

---

## Content Patterns (what makes RMR/TAG quality)

These are not CSS -- they are content patterns that make the briefings feel like a senior analyst wrote them. The skill MUST follow these patterns.

### Pattern 1: "Why This Matters" after every major data section

After presenting facts (company profile, competitive table, pricing data), add a `highlight-box` connecting the data to strategy:

```html
<div class="highlight-box">
  <strong>Why TAG matters to lumif.ai:</strong> TAG already white-labels safety programs
  to insurance groups and works with the largest GCs nationally...
</div>
```

### Pattern 2: Direct quotes woven throughout

Don't summarize what people said. Quote them:

```html
<div class="quote">
  "I don't think it can get any more manual."
  <div class="attr">David Daido, describing current workflow, March 12</div>
</div>
```

### Pattern 3: Comparison tables with "Why It Matters for {Company}" column

Don't just list capabilities. Add a column explaining relevance:

```html
<thead><tr><th>Capability</th><th>Internal Tool</th><th>lumif.ai</th><th>Why It Matters for RMR</th></tr></thead>
```

### Pattern 4: Specific tactical advice, not generic

**Bad:** "Find the right entry point at the company."
**Good:** "Frank Cella (Education) is not our strongest vertical. Research Marsh's Construction Practice or Real Estate Practice leads. Our competitive moat (contract parsing, endorsement verification) is strongest in construction/CRE."

### Pattern 5: Prepared responses for likely objections

In risk register or competitive section, include ready-to-use responses:

```html
<div class="callout-yellow">
  <h4>If they bring up their internal COI tool</h4>
  <p>"That's great that you've automated certificate validation. What we add is the
  contract side: parsing the actual agreement, extracting what coverage the contract
  requires..."</p>
</div>
```

### Pattern 6: Named examples from their world

Reference specific projects, people, and systems the prospect uses:
- "Boylston, Causeway, Station East -- larger projects where sub tracking matters"
- "Yardi -> Smartsheet -> manual outreach" (their actual workflow)
- "AECOM relationship -- national MSA, 50 jobs/year"

### Pattern 7: Math blocks for pricing

Show the work, don't just state the number:

```html
<div class="math-block">Project coordinators: 25-50% time on compliance
At ~$70K salary = ~$17K-35K/year per coordinator
With 25 active projects x ~1 coordinator each:
Total compliance labor: $425K-875K/year</div>
```

### Pattern 8: Two-column strategy cards

For "Our Play" sections, use side-by-side cards:

```html
<div class="two-col">
  <div class="card" style="border-left: 4px solid var(--green);">
    <h4>Confirmed: Built for Leases, Not Construction</h4>
    <p>Their internal tool doesn't solve the construction workflow problem...</p>
    <p><strong>Our play:</strong> Position for the unaddressed use case.</p>
  </div>
  <div class="card" style="border-left: 4px solid var(--blue);">
    <h4>Confirmed: Contact Sees lumif.ai as Superior</h4>
    <p>Chris's own words: "very simple compared to..."</p>
    <p><strong>Our play:</strong> Don't position against the internal tool.</p>
  </div>
</div>
```

---

## Section Map

Adapt sections to what's available. Not all sections appear in every briefing.

**For accounts WITH meeting context (like RMR/TAG):**
1. Company Profile
2. Key Contacts (with quotes, decision path)
3. Pain & Workflow (with flow diagram, quantified metrics table)
4. Internal Tools / Existing Solutions (dedicated section if they have one)
5. Competitive Landscape / Our Edge (comparison matrix with "Why It Matters" column)
6. Pilot Design / POC Strategy (two-column: recommended vs stretch)
7. Demo Script Review (modification table if applicable)
8. Pricing (with math blocks)
9. Deal Path & Integration
10. Risks & Dependencies (severity-coded cards + objection responses)
11. Strategic Recommendations (numbered action items with branded circles)
12. Sources

**For COLD accounts (like Marsh McLennan):**
1. Executive Summary (with confidence score prominently displayed)
2. Company Profile (wider research to compensate for no meetings)
3. Stakeholder Map (heavy on "unknown but important" contacts)
4. Competitive Landscape (the strongest section for cold accounts)
5. Commercial Signals (light)
6. Engagement Strategy (entry point analysis is critical)
7. Risk Register (scale mismatch and no-champion risks are common)
8. Strategic Recommendations (specific, not generic)
9. What We Don't Know (this is THE most important section for cold accounts)
10. Sources

The "What We Don't Know" section should always be visually prominent regardless of account type.
