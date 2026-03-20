# GTM Dashboard

Generate the Command Center — one window into your entire GTM pipeline.

## What it shows

- **Overview** — pipeline funnel, key stats, score distribution, recent runs
- **Actions** — priority-sorted items: uncontacted strong fits, overdue follow-ups, failed sends
- **People** — every contact reached with sortable table; click to see full emails/DMs sent
- **Runs** — every pipeline run with per-run funnel stats
- **Companies** — every scored company, filterable by tier or run

## Usage

```
/dashboard
"show dashboard"
"how's my pipeline?"
"what's the status?"
```

## Auto-generated after

- Every `gtm-leads-pipeline` run
- Every `gtm-outbound-messenger` send session
- Every `gtm-company-fit-analyzer` batch completion

## Files

| File | Purpose |
|------|---------|
| `~/.claude/gtm-stack/gtm-leads-master.xlsx` | Primary data source |
| `~/.claude/gtm-stack/gtm-dashboard.html` | Output — open in any browser |

## Scripts

```bash
# Generate dashboard
python ~/.claude/skills/gtm-stack/gtm-dashboard/scripts/generate_dashboard.py

# Custom output path
python ... --output ~/Desktop/gtm.html
```
