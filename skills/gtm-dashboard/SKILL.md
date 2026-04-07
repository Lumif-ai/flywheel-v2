---
name: gtm-dashboard
enabled: false
description: >
  [GTM Stack — XSS protection, backup, real data bridge.] Generate and display the GTM Command Center — a single-page dashboard showing
  your entire pipeline from scraped leads through to meetings booked. Trigger on:
  "show dashboard", "gtm dashboard", "pipeline dashboard", "command center",
  "how's my pipeline", "what's the status", "visualize my leads", "show me the funnel".
  Auto-generated after every pipeline run and outreach session.
compatibility: "Requires at least one pipeline run or outreach session to have data."
version: "1.1"
context-aware: true
web_tier: 2
---

# GTM Dashboard Skill

Generate the Command Center — one window into your entire GTM pipeline.

**Dashboard file:** `~/.claude/gtm-stack/gtm-dashboard.html`
**Primary data source:** `~/.claude/gtm-stack/gtm-leads-master.xlsx`
**Fallback data:** `pipeline-runs.json` + scored CSVs + `outreach-tracker.csv`

---

## How to Use

### Direct invocation
```
/gtm-dashboard
```

### Natural language triggers
- *"Show dashboard"*
- *"GTM dashboard"*
- *"How's my pipeline?"*
- *"What's the status of my outreach?"*
- *"Visualize my leads"*
- *"Command center"*

---

## What the Dashboard Shows

### Overview Tab (default)
- **Pipeline Funnel:** People Scraped → Companies → Strong + Moderate Fit → Contacted → Replied → Meetings
- **Key Numbers:** 6 stat cards (runs, companies, contacted, reply rate, meetings, actions needed)
- **Fit Distribution:** Clickable breakdown — Strong Fit / Moderate Fit / Low Fit / No Fit
- **Recent Runs:** Last 3 pipeline runs with mini-stats

### Actions Tab
Priority-sorted action items:
1. Strong Fit leads not contacted (highest priority)
2. Overdue follow-ups (with days overdue)
3. Failed sends (with failure reason)
4. Moderate Fit leads not contacted

### People Tab
Table of every person contacted, with:
- Contact name, title, company, location
- Fit score + tier badge
- Status (Meeting / Replied / Follow up / Failed / Sent)
- Email subject line + channel badges
- **Click to expand:** full email body, LinkedIn DM text, fit reasoning, outcome notes

Sortable by date, score, company, or status.

### Pipeline Runs Tab
Every pipeline run with source, filters, and per-run funnel stats.

### Companies Tab
Every scored company, filterable by tier or pipeline run.
Click to expand: fit reasoning + full outreach timeline with messages.

---

## Step 0a: Dependency Check
- Verify: Python 3 available, `openpyxl` importable (required to read master workbook).
- Verify: at least one data file exists: `~/.claude/gtm-stack/gtm-leads-master.xlsx` or `~/.claude/gtm-stack/pipeline-runs.json` or `~/.claude/gtm-stack/outreach-tracker.csv`.
- Verify: `generate_dashboard.py` script exists in the skills directory.
- If no data files found: "No GTM data found. Run `/gtm-leads-pipeline` first to generate pipeline data."
- Block if no data files exist (dashboard would be empty).

### Input Validation
- Verify: data files are non-empty (file size > 0 bytes) before attempting to read.
- Verify: if master workbook exists, it has an "All Companies" sheet with at least one data row.
- If custom output path provided: verify parent directory exists and is writable.

---

### Backup Protocol
- Before regenerating dashboard HTML: create `.backup.YYYY-MM-DD`, keep last 3
- Use `gtm-shared/gtm_utils.backup_file()` where applicable
- Applies to `gtm-dashboard.html` and `gtm-leads-master.xlsx`

## Generating the Dashboard

### Script

**Always run merge_master.py before generating the dashboard** to ensure data is current:
```bash
# Step 1: Merge all scored CSVs + outreach tracker into master workbook
python ~/.claude/skills/gtm-leads-pipeline/scripts/merge_master.py

# Step 2: Generate dashboard from the updated master
python ~/.claude/skills/gtm-dashboard/scripts/generate_dashboard.py
```

### Custom output path
```bash
python ... --output ~/Desktop/gtm.html
```

---

## Auto-Generation

The dashboard is regenerated automatically after:
- Every `gtm-leads-pipeline` run (STEP 7.5c)
- Every `gtm-outbound-messenger` send session (Final Summary)
- Every `gtm-company-fit-analyzer` batch completion
- Running `merge_master.py` (which log_run.py triggers)

---

## Persistent Files at ~/.claude/gtm-stack/

| File | Written by | Read by |
|------|-----------|---------|
| `sender-profile.md` | my-company | scorer, messenger |
| `pipeline-runs.json` | log_run.py | merge_master.py |
| `outreach-tracker.csv` | gtm-outbound-messenger | merge_master.py |
| `do-not-contact.csv` | gtm-outbound-messenger | scorer, messenger, merge_master |
| `gtm-leads-master.xlsx` | merge_master.py | generate_dashboard.py |
| `gtm-dashboard.html` | generate_dashboard.py | browser (you) |

---

## Deliverables

**Always end with the deliverables block after generating the dashboard:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Dashboard (HTML): ~/.claude/gtm-stack/gtm-dashboard.html
                    Open in any browser for the interactive view

  Master workbook:  ~/.claude/gtm-stack/gtm-leads-master.xlsx
                    All companies, outreach, and pipeline runs in one file

  Pipeline log:     ~/.claude/gtm-stack/pipeline-runs.json
                    History of all pipeline runs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Edge Cases

| Situation | Handle as |
|-----------|-----------|
| No master workbook | Fall back to raw files |
| No pipeline-runs.json | Empty dashboard with "Run /gtm-leads-pipeline to get started" |
| Missing scored CSV | Skip that run's companies |
| No outreach tracker | Show companies without outreach data |
| Sharing the dashboard | Single self-contained HTML — email, Slack, open anywhere |

## Error Handling

- **Missing master workbook:** Fall back to raw files (`pipeline-runs.json` + scored CSVs + `outreach-tracker.csv`). Run `merge_master.py` first if possible.
- **Corrupt or unreadable XLSX:** Log the openpyxl error, attempt to regenerate by running `merge_master.py`. If still failing, fall back to raw CSV/JSON data.
- **Missing pipeline-runs.json:** Show dashboard with "No pipeline runs recorded" placeholder. Outreach and company data may still populate from other files.
- **Template/script error (generate_dashboard.py crash):** Show full error traceback. Suggest re-running after checking that `merge_master.py` ran successfully.
- **Missing outreach tracker:** Dashboard renders without outreach data. Companies tab still shows fit scores.
- Partial results: render whatever data is available, never fail completely if at least one data source exists.
- Final dashboard footer shows which data sources were loaded and which were missing.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

### Pre-Read Enrichment
Before generating the dashboard, read relevant context store files via `_catalog.md` to enrich the display:
- `positioning.md` — company tagline and messaging for dashboard header
- `win-loss-log.md` — deal outcomes for conversion analysis cards
- `contacts.md` — relationship context for people in the pipeline

### Post-Write
Dashboard generation does not produce new knowledge for the context store. No post-write needed.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-dashboard.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Preferred metrics (which stat cards matter most, custom KPIs)
- Layout preferences (default tab, sort order, column visibility)
- Refresh frequency (how often to auto-regenerate)
- Custom output path preferences

### What NOT to save
- Session-specific content, temporary overrides, confidential data

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-03-13 | Add context-aware flag and pre-read enrichment from context store |
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
