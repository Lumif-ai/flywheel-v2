# Leads Pipeline

End-to-end orchestrator: **Scrape → Score → Send → Track**

## What it does

Runs the full GTM pipeline in one session:
1. **Scrape** leads from any directory/site (via `gtm-web-scraper-extractor`)
2. **Collapse** people into unique companies
3. **Score** each company for fit (via `gtm-company-fit-analyzer`)
4. **Send** personalized outreach to Strong Fit + Moderate Fit leads (via `gtm-outbound-messenger`)
5. **Track** every touchpoint in a persistent outreach tracker
6. **Deliver** ranked list with scores, reasoning, contacts, and outreach status

## Requirements

- Playwright MCP connected
- All GTM Stack skills installed: `gtm-web-scraper-extractor`, `gtm-company-fit-analyzer`, `gtm-outbound-messenger`
- Sender profile recommended (`/gtm-my-company` to set up)

## Usage

```
/leads-pipeline
"find construction companies from this directory, score them, and send outreach"
"scrape, score, and send"
```

## GTM Stack Architecture

```
┌─────────────────────────────────────────────────┐
│              gtm-leads-pipeline                    │
│              (orchestrator skill)                  │
│                                                   │
│  PHASE 1        PHASE 2           PHASE 3         │
│  ┌──────┐      ┌─────────┐      ┌──────────┐    │
│  │Scrape│ ───→ │  Score   │ ───→ │  Send    │    │
│  └──────┘      └─────────┘      └──────────┘    │
│      ↑              ↑                ↑     ↓      │
│  web-scraper   company-fit     outbound-   │      │
│  -extractor    -analyzer       messenger   │      │
│                     ↑                      ↓      │
│                my-company          outreach-       │
│              (sender profile)      tracker.csv    │
└─────────────────────────────────────────────────┘
```

## Persistent Files

| File | Location | Purpose |
|------|----------|---------|
| Sender Profile | `~/.claude/gtm-stack/sender-profile.md` | Who you are, ICPs, value props |
| Outreach Tracker | `~/.claude/gtm-stack/outreach-tracker.csv` | All outreach history, follow-ups |
| Pipeline Runs | `~/.claude/gtm-stack/pipeline-runs.json` | Run history metadata |
| Do Not Contact | `~/.claude/gtm-stack/do-not-contact.csv` | Companies to skip |
| Master Workbook | `~/.claude/gtm-stack/gtm-leads-master.xlsx` | Deduped companies + outreach |
| Dashboard | `~/.claude/gtm-stack/gtm-dashboard.html` | Command Center view |
