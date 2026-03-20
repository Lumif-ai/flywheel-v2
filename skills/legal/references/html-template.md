# HTML Report Template

Use this template when generating the HTML output file in Step 3.
Replace all `{{PLACEHOLDER}}` values with actual content from your analysis.

The template uses inline CSS only — no external dependencies.

```python
#!/usr/bin/env python3
"""
Generate the HTML legal review report.
Call this after completing all 8 sections of analysis.
Fill in all variables before running.
"""

# ── FILL THESE IN ──────────────────────────────────────────────────────────────
doc_title       = "{{DOCUMENT TITLE}}"          # e.g. "Acme Corp MSA v2.1"
doc_type        = "{{AGREEMENT TYPE}}"           # e.g. "SaaS Master Services Agreement"
review_date     = "{{DATE}}"                     # e.g. "2 March 2026"
verdict_label   = "{{VERDICT}}"                  # SAFE TO SIGN / SIGN WITH CHANGES / DO NOT SIGN YET / DO NOT SIGN
verdict_emoji   = "{{EMOJI}}"                    # 🟢 / 🟡 / 🔴 / ⛔
verdict_color   = "{{COLOR}}"                    # #1a7a4a / #b8860b / #c0392b / #7b0000
confidence      = "{{CONFIDENCE}}"               # High / Medium / Low + reason
counterparty    = "{{COUNTERPARTY NAME}}"
founder_role    = "{{FOUNDER ROLE}}"             # e.g. "the party being asked to sign"
leverage        = "{{WHO HAS LEVERAGE}}"         # e.g. "Counterparty has significantly more leverage"

executive_summary_html = """
{{PASTE EXECUTIVE SUMMARY HTML HERE — use <p> tags}}
"""

risk_table_rows = """
{{PASTE RISK TABLE ROWS HERE}}
<!-- Format each row as:
<tr>
  <td><strong>Section 4.2</strong></td>
  <td class="quote">"exact clause language here"</td>
  <td>Plain English meaning</td>
  <td>Why it matters</td>
  <td>What could go wrong</td>
  <td class="risk-high">🔴 High</td>
  <td>Suggested fix</td>
</tr>
Risk classes: risk-low / risk-medium / risk-high / risk-critical
-->
"""

financial_html        = "{{PASTE SECTION 3 CONTENT AS HTML <p> BLOCKS}}"
control_html          = "{{PASTE SECTION 4 CONTENT AS HTML <p> AND <ul> BLOCKS}}"
ip_html               = "{{PASTE SECTION 5 CONTENT AS HTML <p> AND <ul> BLOCKS}}"
negotiation_html      = "{{PASTE SECTION 6 CONTENT AS HTML BLOCKS}}"
scenarios_html        = "{{PASTE SECTION 7 CONTENT AS HTML BLOCKS}}"
top3_fixes            = [
    "{{FIX 1}}",
    "{{FIX 2}}",
    "{{FIX 3}}",
]
negotiate_effort      = "{{e.g. 3–5 business days of back-and-forth}}"
# ── END FILL IN ────────────────────────────────────────────────────────────────

import re, os, pathlib

safe_title = re.sub(r'[^a-z0-9_-]', '_', doc_title.lower())[:40]

# Use /mnt/user-data/outputs/ on Claude.ai desktop, else ~/Documents/legal-reviews/
if os.path.isdir("/mnt/user-data/outputs"):
    output_dir = "/mnt/user-data/outputs"
else:
    output_dir = os.path.join(str(pathlib.Path.home()), "Documents", "legal-reviews")
    os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(output_dir, f"legal_review_{safe_title}.html")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Legal Review: {doc_title}</title>
<style>
  :root {{
    --red:      #c0392b;
    --orange:   #e67e22;
    --yellow:   #b8860b;
    --green:    #1a7a4a;
    --critical: #7b0000;
    --bg:       #f8f7f4;
    --card:     #ffffff;
    --border:   #e0ddd8;
    --text:     #1a1a1a;
    --muted:    #666;
    --sidebar-w: 220px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
  }}
  /* ── Layout ── */
  .layout {{ display: flex; min-height: 100vh; }}
  .sidebar {{
    width: var(--sidebar-w);
    background: #1c1c1e;
    color: #ccc;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    flex-shrink: 0;
    padding: 24px 0;
  }}
  .sidebar .brand {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #888;
    padding: 0 20px 16px;
    border-bottom: 1px solid #333;
    margin-bottom: 16px;
  }}
  .sidebar a {{
    display: block;
    padding: 8px 20px;
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 12px;
    color: #aaa;
    text-decoration: none;
    transition: color 0.15s, background 0.15s;
    border-left: 3px solid transparent;
  }}
  .sidebar a:hover {{ color: #fff; background: #2c2c2e; border-left-color: #888; }}
  .sidebar .verdict-badge {{
    margin: 16px;
    padding: 10px 12px;
    border-radius: 6px;
    background: {verdict_color}22;
    border: 1px solid {verdict_color}55;
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: {verdict_color};
    text-align: center;
    letter-spacing: 0.5px;
  }}
  .main {{ flex: 1; padding: 48px 56px; max-width: 1000px; }}
  /* ── Header ── */
  .header {{ margin-bottom: 40px; padding-bottom: 28px; border-bottom: 2px solid var(--border); }}
  .header .eyebrow {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .header h1 {{ font-size: 28px; font-weight: 700; line-height: 1.3; margin-bottom: 12px; }}
  .header .meta {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: var(--muted);
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }}
  .header .meta span strong {{ color: var(--text); }}
  /* ── Verdict banner ── */
  .verdict-banner {{
    background: {verdict_color}0f;
    border: 2px solid {verdict_color};
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 40px;
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .verdict-banner .emoji {{ font-size: 32px; line-height: 1; }}
  .verdict-banner .text h2 {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: {verdict_color};
    margin-bottom: 4px;
  }}
  .verdict-banner .text p {{
    font-size: 14px;
    color: var(--muted);
    font-style: italic;
  }}
  /* ── Sections ── */
  .section {{ margin-bottom: 52px; }}
  .section h2 {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 20px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  .section p {{ margin-bottom: 14px; font-size: 15px; }}
  .section ul {{ margin: 10px 0 14px 20px; }}
  .section ul li {{ margin-bottom: 8px; font-size: 15px; }}
  /* ── Risk table ── */
  .table-wrap {{ overflow-x: auto; margin: 0 -8px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
    font-family: 'Helvetica Neue', sans-serif;
  }}
  th {{
    background: #f0eeea;
    text-align: left;
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
  }}
  td {{
    padding: 12px 14px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    line-height: 1.5;
  }}
  tr:hover td {{ background: #faf9f7; }}
  td.quote {{
    font-family: 'Georgia', serif;
    font-style: italic;
    font-size: 12.5px;
    color: #444;
    max-width: 220px;
  }}
  /* Risk level cells */
  .risk-low      {{ color: var(--green);    font-weight: 700; white-space: nowrap; }}
  .risk-medium   {{ color: var(--yellow);   font-weight: 700; white-space: nowrap; }}
  .risk-high     {{ color: var(--red);      font-weight: 700; white-space: nowrap; }}
  .risk-critical {{ color: var(--critical); font-weight: 700; white-space: nowrap; }}
  /* ── Scenarios ── */
  .scenario {{
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--red);
    border-radius: 8px;
    padding: 24px 28px;
    margin-bottom: 24px;
  }}
  .scenario h3 {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 16px;
    color: var(--red);
  }}
  .scenario dl {{ display: grid; grid-template-columns: 140px 1fr; gap: 8px 16px; font-size: 14px; }}
  .scenario dt {{ font-weight: 700; color: var(--muted); font-family: 'Helvetica Neue', sans-serif; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; padding-top: 2px; }}
  .scenario dd {{ color: var(--text); }}
  /* ── Fix list ── */
  .fix-list {{ list-style: none; }}
  .fix-list li {{
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--red);
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 10px;
    font-size: 14px;
  }}
  .fix-list li::before {{
    content: '⚑ ';
    color: var(--red);
    font-weight: 700;
  }}
  /* ── Negotiation ── */
  .redline-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }}
  .redline-card .label {{
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--red);
    margin-bottom: 6px;
  }}
  .redline-card .label.should {{ color: var(--yellow); }}
  .redline-card .label.nice {{ color: var(--green); }}
  /* ── Confidence ── */
  .confidence-box {{
    background: #f0eeea;
    border-radius: 6px;
    padding: 14px 18px;
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: var(--muted);
    margin-top: 16px;
  }}
  .confidence-box strong {{ color: var(--text); }}
  /* ── Footer ── */
  .footer {{
    margin-top: 60px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
    font-family: 'Helvetica Neue', sans-serif;
    font-size: 12px;
    color: var(--muted);
    text-align: center;
  }}
  /* ── Print ── */
  @media print {{
    .sidebar {{ display: none; }}
    .main {{ padding: 24px; max-width: 100%; }}
    .verdict-banner {{ break-inside: avoid; }}
    .scenario {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="layout">

<!-- Sidebar -->
<nav class="sidebar">
  <div class="brand">Legal Review</div>
  <div class="verdict-badge">{verdict_emoji} {verdict_label}</div>
  <a href="#executive-summary">1. Executive Summary</a>
  <a href="#risk-areas">2. Risk Areas</a>
  <a href="#financial">3. Financial Exposure</a>
  <a href="#control">4. Control &amp; Power</a>
  <a href="#ip">5. IP &amp; Data</a>
  <a href="#negotiation">6. Negotiation</a>
  <a href="#scenarios">7. Worst Cases</a>
  <a href="#recommendation">8. Recommendation</a>
</nav>

<!-- Main content -->
<main class="main">

  <!-- Header -->
  <header class="header">
    <div class="eyebrow">Founder-First Legal Review</div>
    <h1>{doc_title}</h1>
    <div class="meta">
      <span><strong>Type:</strong> {doc_type}</span>
      <span><strong>Counterparty:</strong> {counterparty}</span>
      <span><strong>Your role:</strong> {founder_role}</span>
      <span><strong>Date:</strong> {review_date}</span>
      <span><strong>Leverage:</strong> {leverage}</span>
    </div>
  </header>

  <!-- Verdict banner -->
  <div class="verdict-banner">
    <div class="emoji">{verdict_emoji}</div>
    <div class="text">
      <h2>{verdict_label}</h2>
      <p>Confidence: {confidence}</p>
    </div>
  </div>

  <!-- Section 1 -->
  <section class="section" id="executive-summary">
    <h2>1 · Executive Summary</h2>
    {executive_summary_html}
  </section>

  <!-- Section 2 -->
  <section class="section" id="risk-areas">
    <h2>2 · Critical Risk Areas</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Clause</th>
            <th>Exact Language</th>
            <th>Plain English</th>
            <th>Why It Matters</th>
            <th>What Could Go Wrong</th>
            <th>Risk</th>
            <th>Suggested Fix</th>
          </tr>
        </thead>
        <tbody>
          {risk_table_rows}
        </tbody>
      </table>
    </div>
  </section>

  <!-- Section 3 -->
  <section class="section" id="financial">
    <h2>3 · Financial &amp; Liability Exposure</h2>
    {financial_html}
  </section>

  <!-- Section 4 -->
  <section class="section" id="control">
    <h2>4 · Control &amp; Power Dynamics</h2>
    {control_html}
  </section>

  <!-- Section 5 -->
  <section class="section" id="ip">
    <h2>5 · IP &amp; Data Ownership</h2>
    {ip_html}
  </section>

  <!-- Section 6 -->
  <section class="section" id="negotiation">
    <h2>6 · Negotiation Strategy</h2>
    {negotiation_html}
  </section>

  <!-- Section 7 -->
  <section class="section" id="scenarios">
    <h2>7 · Worst-Case Scenarios</h2>
    {scenarios_html}
  </section>

  <!-- Section 8 -->
  <section class="section" id="recommendation">
    <h2>8 · Final Recommendation</h2>
    <div class="verdict-banner">
      <div class="emoji">{verdict_emoji}</div>
      <div class="text">
        <h2>{verdict_label}</h2>
        <p>Confidence: {confidence}</p>
      </div>
    </div>
    <p><strong>Top 3 things to fix before signing:</strong></p>
    <ul class="fix-list">
      {''.join(f'<li>{fix}</li>' for fix in top3_fixes)}
    </ul>
    <p style="margin-top:16px"><strong>Estimated negotiation effort:</strong> {negotiate_effort}</p>
    <div class="confidence-box">
      <strong>Confidence level explained:</strong> {confidence}
    </div>
  </section>

  <footer class="footer">
    Legal Document Advisor — Founder-First Review &nbsp;·&nbsp; {review_date}
  </footer>

</main>
</div>
</body>
</html>"""

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Saved: {output_path}")
```

## HOW TO USE THIS TEMPLATE

1. Read this file at the start of Step 3
2. Copy the Python block into a bash_tool call
3. Fill in every `{{PLACEHOLDER}}` with real content from your analysis
4. For `risk_table_rows`: build each `<tr>` with **exactly 7 `<td>` cells** (Clause, Exact Language, Plain English, Why It Matters, What Could Go Wrong, Risk, Suggested Fix) — use the appropriate `risk-low/medium/high/critical` class on the risk cell. NEVER omit the 7th "Suggested Fix" cell.
5. For `scenarios_html`: use this structure per scenario:
```html
<div class="scenario">
  <h3>Scenario 1: [Title]</h3>
  <dl>
    <dt>What happens</dt><dd>[text]</dd>
    <dt>How it plays out</dt><dd>[text]</dd>
    <dt>Financial impact</dt><dd>[text]</dd>
    <dt>Reputational impact</dt><dd>[text]</dd>
    <dt>How to mitigate</dt><dd>[text]</dd>
  </dl>
</div>
```
6. For `negotiation_html`: use this structure:
```html
<div class="redline-card">
  <div class="label">Must Fix — Non-Negotiable</div>
  <p><strong>Clause X:</strong> [issue]. Replace with: "[exact redline language]"</p>
</div>
<div class="redline-card">
  <div class="label should">Should Fix — Push Hard</div>
  <p>[...]</p>
</div>
<div class="redline-card">
  <div class="label nice">Nice to Have</div>
  <p>[...]</p>
</div>
```
