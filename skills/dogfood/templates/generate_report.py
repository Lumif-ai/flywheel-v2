#!/usr/bin/env python3
"""
Generate a self-contained HTML report from a dogfood session.

Reads report.md and screenshots/ from the output directory and produces
a single report.html with all screenshots embedded as base64.

Usage:
    python3 generate_report.py [output_dir]

If output_dir is not given, uses the directory containing this script.
"""

import base64
import os
import re
import sys
from datetime import date

# --- Paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else SCRIPT_DIR
REPORT_MD = os.path.join(OUTPUT_DIR, "report.md")
SCREENSHOTS_DIR = os.path.join(OUTPUT_DIR, "screenshots")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "report.html")


# --- Image helpers ---

def img_b64(filename):
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def img_tag(filename, max_width=320):
    data = img_b64(filename)
    if not data:
        return (
            f"<span style='color:#999;font-style:italic;font-size:12px'>"
            f"{filename} not found</span>"
        )
    return (
        f'<img src="data:image/png;base64,{data}" '
        f'style="max-width:{max_width}px;border-radius:6px;border:1px solid #e0e0e0;'
        f'cursor:pointer;display:block" '
        f'onclick="openModal(this.src)" />'
    )


# --- Parse report.md ---

def parse_report(md_text):
    meta = {}

    # Header meta table: | **Date** | ... | etc.
    for row in md_text.split("\n"):
        m = re.match(r"\| \*\*(\w+)\*\* \| (.+?) \|", row)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key in ("Date", "App", "URL", "Session", "Scope"):
                meta[key] = val

    # Summary counts
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Total": 0}
    for row in md_text.split("\n"):
        for severity in ["Critical", "High", "Medium", "Low"]:
            m = re.match(rf"\| (?:\*\*)?{severity}(?:\*\*)? \| (\d+) \|", row, re.IGNORECASE)
            if m:
                counts[severity] = int(m.group(1))
        m = re.match(r"\| \*\*Total\*\* \| \*\*(\d+)\*\* \|", row)
        if m:
            counts["Total"] = int(m.group(1))

    # Issues — split on ### ISSUE-NNN: headings
    # re.split with a capture group gives [preamble, id1, body1, id2, body2, ...]
    parts = re.split(r"\n### (ISSUE-\d+): ", md_text)

    issues = []
    i = 1
    while i < len(parts) - 1:
        issue_id = parts[i].strip()
        body = parts[i + 1]
        i += 2

        # Title is the first line of body
        title = body.split("\n")[0].strip()

        # Field table rows
        fields = {}
        for row in body.split("\n"):
            m = re.match(r"\| \*\*([^*]+)\*\* \| (.+?) \|", row)
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()

        severity = fields.get("Severity", "low").lower().split()[0]  # handle "low / ux" etc.
        category = fields.get("Category", "")
        url = fields.get("URL", "")

        # Description block (between **Description** and the next bold heading or ---)
        desc_match = re.search(
            r"\*\*Description\*\*\s*\n+(.+?)(?=\n\*\*|\n---|\Z)", body, re.DOTALL
        )
        description = desc_match.group(1).strip() if desc_match else ""
        # Strip markdown formatting for HTML display
        description = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", description)
        description = re.sub(r"`(.+?)`", r"<code>\1</code>", description)
        # Truncate very long descriptions
        if len(description) > 500:
            description = description[:500] + "…"

        # Screenshot references: ![...](screenshots/filename.png)
        screenshots = re.findall(r"!\[.*?\]\(screenshots/([^)]+)\)", body)
        # Deduplicate preserving order
        seen = set()
        unique_shots = []
        for s in screenshots:
            if s not in seen:
                seen.add(s)
                unique_shots.append(s)

        issues.append(
            {
                "id": issue_id,
                "title": title,
                "severity": severity,
                "category": category,
                "url": url,
                "description": description,
                "screenshots": unique_shots,
            }
        )

    return meta, counts, issues


# --- HTML generation ---

SEVERITY_COLORS = {
    "critical": {"bg": "#fdf4ff", "badge": "#9333ea"},
    "high":     {"bg": "#fef2f2", "badge": "#dc2626"},
    "medium":   {"bg": "#fffbeb", "badge": "#d97706"},
    "low":      {"bg": "#f0fdf4", "badge": "#16a34a"},
}


def severity_badge(sev):
    color = SEVERITY_COLORS.get(sev, {"badge": "#6b7280"})["badge"]
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;border-radius:9999px;'
        f'font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">'
        f"{sev}</span>"
    )


def screenshots_cell(screenshots):
    if not screenshots:
        return '<span style="color:#999;font-size:12px">—</span>'
    parts = [img_tag(s) for s in screenshots]
    return '<div style="display:flex;flex-direction:column;gap:8px">' + "".join(parts) + "</div>"


def build_rows(issues):
    rows = []
    for issue in issues:
        sev = issue["severity"]
        bg = SEVERITY_COLORS.get(sev, {}).get("bg", "#fff")
        url_html = ""
        if issue["url"] and issue["url"] not in ("{page URL where issue was found}", "—", ""):
            url_html = (
                f'<div style="margin-top:6px">'
                f'<a href="{issue["url"]}" style="font-size:11px;color:#2563eb;text-decoration:none">'
                f'{issue["url"]}</a></div>'
            )
        rows.append(
            f"""    <tr style="background:{bg};vertical-align:top">
      <td style="padding:12px 14px;white-space:nowrap;font-weight:700;font-family:monospace;font-size:13px">{issue["id"]}</td>
      <td style="padding:12px 14px;white-space:nowrap">{severity_badge(sev)}</td>
      <td style="padding:12px 14px;font-size:12px;color:#555;white-space:nowrap">{issue["category"]}</td>
      <td style="padding:12px 14px;max-width:260px">
        <div style="font-weight:600;font-size:13px;line-height:1.4;margin-bottom:4px">{issue["title"]}</div>
        <div style="font-size:12px;color:#555;line-height:1.5">{issue["description"]}</div>
        {url_html}
      </td>
      <td style="padding:12px 14px;min-width:340px">{screenshots_cell(issue["screenshots"])}</td>
    </tr>"""
        )
    return "\n".join(rows)


def build_stat_cards(counts):
    cards = []
    for label, cls, key in [
        ("Total Issues", "total", "Total"),
        ("Critical", "critical", "Critical"),
        ("High", "high", "High"),
        ("Medium", "medium", "Medium"),
        ("Low", "low", "Low"),
    ]:
        n = counts.get(key, 0)
        if key == "Total" or n > 0:
            cards.append(
                f'  <div class="stat-card {cls}">'
                f'<div class="num">{n}</div>'
                f'<div class="label">{label}</div></div>'
            )
    return "\n".join(cards)


def generate_html(meta, counts, issues):
    app_url = meta.get("URL", meta.get("App URL", ""))
    session = meta.get("Session", "—")
    scope = meta.get("Scope", "—")
    report_date = meta.get("Date", str(date.today()))
    title = f"Dogfood Report — {app_url}" if app_url else "Dogfood Report"

    rows_html = build_rows(issues)
    stat_cards_html = build_stat_cards(counts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #1a1a1a; }}
  .header {{ background: #fff; border-bottom: 1px solid #e2e8f0; padding: 24px 32px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; color: #0f172a; }}
  .header .meta {{ display: flex; gap: 24px; margin-top: 8px; flex-wrap: wrap; }}
  .header .meta span {{ font-size: 13px; color: #64748b; }}
  .header .meta strong {{ color: #334155; }}
  .summary {{ display: flex; gap: 12px; padding: 20px 32px; flex-wrap: wrap; }}
  .stat-card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 20px; min-width: 100px; text-align: center; }}
  .stat-card .num {{ font-size: 28px; font-weight: 800; }}
  .stat-card .label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }}
  .stat-card.total .num {{ color: #0f172a; }}
  .stat-card.critical .num {{ color: #9333ea; }}
  .stat-card.high .num {{ color: #dc2626; }}
  .stat-card.medium .num {{ color: #d97706; }}
  .stat-card.low .num {{ color: #16a34a; }}
  .table-wrap {{ padding: 0 32px 40px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  thead tr {{ background: #f1f5f9; }}
  th {{ padding: 12px 14px; text-align: left; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: #64748b; border-bottom: 2px solid #e2e8f0; white-space: nowrap; }}
  td {{ border-bottom: 1px solid #e2e8f0; }}
  tr:last-child td {{ border-bottom: none; }}
  #modal {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.85); z-index:1000; align-items:center; justify-content:center; cursor:zoom-out; }}
  #modal.open {{ display:flex; }}
  #modal img {{ max-width:90vw; max-height:90vh; border-radius:8px; box-shadow:0 20px 60px rgba(0,0,0,.6); }}
</style>
</head>
<body>

<div class="header">
  <h1>{title}</h1>
  <div class="meta">
    <span><strong>Date:</strong> {report_date}</span>
    <span><strong>URL:</strong> {app_url}</span>
    <span><strong>Session:</strong> {session}</span>
    <span><strong>Scope:</strong> {scope}</span>
  </div>
</div>

<div class="summary">
{stat_cards_html}
</div>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Severity</th>
        <th>Category</th>
        <th>Issue &amp; Description</th>
        <th>Screenshot(s)</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
</div>

<div id="modal" onclick="closeModal()">
  <img id="modal-img" src="" alt="" />
</div>

<script>
function openModal(src) {{
  document.getElementById('modal-img').src = src;
  document.getElementById('modal').classList.add('open');
}}
function closeModal() {{
  document.getElementById('modal').classList.remove('open');
}}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeModal(); }});
</script>
</body>
</html>"""


# --- Main ---

if not os.path.exists(REPORT_MD):
    print(f"Error: report.md not found at {REPORT_MD}")
    sys.exit(1)

with open(REPORT_MD) as f:
    md_text = f.read()

meta, counts, issues = parse_report(md_text)

if not issues:
    print("Warning: no issues parsed from report.md — check that headings follow '### ISSUE-NNN: Title' format.")

html = generate_html(meta, counts, issues)

with open(OUTPUT_HTML, "w") as f:
    f.write(html)

size_mb = os.path.getsize(OUTPUT_HTML) / 1024 / 1024
print(f"Generated: {OUTPUT_HTML}")
print(f"Issues:    {len(issues)}")
print(f"Size:      {size_mb:.1f} MB")
