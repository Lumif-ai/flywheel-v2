# Outbound Messenger

Send personalized outreach emails and LinkedIn DMs to scored leads via the browser. Part of the GTM Stack.

## What it does

- Reads a scored CSV (from `gtm-company-fit-analyzer` or `gtm-leads-pipeline`)
- Filters for Strong Fit (75–100) and Moderate Fit (50–74) leads
- Sends the scorer's pre-drafted messages (with optional refinement before sending)
- Checks the Do Not Contact list before sending
- Sends via your logged-in email client (Gmail, Outlook, Zoho) and/or LinkedIn
- Logs every touchpoint to a persistent tracker at `~/.claude/gtm-stack/outreach-tracker.csv`
- Tracks structured outcomes (Replied - Interested, Meeting Booked, etc.)
- Auto-calculates follow-ups based on tier cadence (Strong Fit: 3 days, Moderate Fit: 5 days)
- Prevents duplicate outreach across sessions

## Requirements

- Playwright MCP connected
- A scored CSV with `Fit_Score` and `Fit_Tier` columns
- Sender profile recommended (`/gtm-my-company` to set up)

## Usage

```
/gtm-outbound-messenger      # Send outreach to scored leads
"send emails to strong fit"  # Natural language
"check follow-ups"           # See who needs a follow-up
"show outreach tracker"      # View all-time outreach stats
"show dashboard"             # Full pipeline command center
```

## Supported Channels

- Gmail (browser)
- Outlook (browser)
- Zoho Mail (browser)
- LinkedIn DM

## Outreach Tracker

Persistent CSV at `~/.claude/gtm-stack/outreach-tracker.csv` tracks:
- Date, company, contact, channel, message sent, fit score/tier
- Structured Outcome column (No Response / Replied - Interested / Meeting Booked / etc.)
- Auto-calculated follow-up dates per tier cadence
- Follow-up status (Pending / Done / Not Needed)
- Free-text Notes for anything else

## Part of the GTM Stack

```
gtm-web-scraper-extractor  →  gtm-company-fit-analyzer  →  gtm-outbound-messenger
        ↑                                                   ↓
        └──────────── gtm-leads-pipeline (orchestrator) ────────┘
                              ↑
                         my-company (sender profile)
```
