> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file references the legacy `~/.claude/skills/` path. Skills are now served exclusively via `flywheel_fetch_skill_assets` from the `skill_assets` table. Retained for historical reference only; runtime bundles are delivered over MCP and paths shown in this document no longer reflect the live code location.

# Outreach Tracker Logging

Reference for STEP 6 of the outbound messenger pipeline. Read this file when
you reach STEP 6 after sending messages.

---

## STEP 6 — Log to Outreach Tracker

After EVERY successful send (or skip), immediately append to the tracker.
**Use the two-phase write pattern to prevent duplicate sends on crash recovery.**

**Tracker path:** `~/.claude/gtm-stack/outreach-tracker.csv`

### Two-Phase Write Pattern (Idempotent Sending)

To prevent duplicate sends when a session crashes mid-run:

1. **Before sending:** Write a row with `Status = "Pending"` to the tracker
2. **After successful send:** Update the row to `Status = "Sent"`
3. **On resume:** Any rows with `Status = "Pending"` are flagged for manual review —
   the message may or may not have actually been sent

```python
def log_outreach_pending(record):
    """Phase 1: Write pending row BEFORE sending."""
    record['Status'] = 'Pending'
    record['Notes'] = (record.get('Notes', '') + ' [pending-send]').strip()
    log_outreach(record)

def update_outreach_sent(tracker_path, contact_name, company, channel, date):
    """Phase 2: Update pending row to Sent AFTER successful send."""
    rows = []
    updated = False
    with open(tracker_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if (not updated
                and row.get('Contact_Name', '').strip() == contact_name.strip()
                and row.get('Company', '').strip() == company.strip()
                and row.get('Channel', '').strip().lower() == channel.strip().lower()
                and row.get('Date', '') == date
                and row.get('Status') == 'Pending'):
                row['Status'] = 'Sent'
                row['Notes'] = row.get('Notes', '').replace('[pending-send]', '').strip()
                updated = True
            rows.append(row)
    if updated:
        # Use atomic write to prevent corruption
        atomic_write_csv(tracker_path, rows, fieldnames)
    return updated
```

**On session resume:** Before starting sends, check for any `Status = "Pending"` rows:
```
⚠ Found [N] pending sends from a previous interrupted session:
  1. [Company] — [Contact] via [Channel] on [Date]

These may or may not have actually been delivered.
Options:
  A) Mark all as Sent (I confirmed they went through)
  B) Mark all as Failed (I'll re-send them)
  C) Let me review each one
```

### Tracker Schema

| Column | Description |
|--------|-------------|
| `Date` | YYYY-MM-DD of send |
| `Time` | HH:MM (24h) |
| `Company` | Company name |
| `Contact_Name` | Person contacted |
| `Contact_Title` | Their title |
| `Contact_Email` | Email used (if email channel) |
| `Contact_Type` | `Individual` or `Team` — auto-detected from email address pattern |
| `Contact_LinkedIn` | LinkedIn URL (if LinkedIn channel) |
| `Channel` | email / linkedin |
| `Fit_Score` | From scored CSV |
| `Fit_Tier` | Strong Fit / Moderate Fit |
| `Email_Subject` | Subject line sent (email only) |
| `Email_Body` | Full email body sent |
| `LinkedIn_DM` | Full LinkedIn DM text sent |
| `Message_Preview` | First 100 chars of message body |
| `Status` | Sent / Skipped / Failed / Queued |
| `Failure_Reason` | Why it failed (if applicable) |
| `Outcome` | No Response / Replied - Interested / Replied - Not Interested / Replied - Using Competitor / Meeting Booked / Bounced / Wrong Contact |
| `Follow_Up_Date` | Auto-calculated from tier cadence (see below) |
| `Follow_Up_Status` | Pending / Done / Not Needed |
| `Notes` | Free-text notes |
| `Source_CSV` | Path to the scored CSV this lead came from |
| `Pipeline_Run` | Date of the pipeline run that generated this lead |

### Follow-Up Cadence

Follow-up dates are calculated based on the lead's fit tier. Defaults (configurable
in the sender profile's `## Outreach Preferences` section):

| Tier | Default Follow-Up |
|------|------------------|
| Strong Fit | 3 business days |
| Moderate Fit | 5 business days |

If the sender profile has custom cadence values, use those instead.

### Create or Append

Use atomic file operations from the shared utilities to prevent corruption.

```python
import csv, os
from datetime import datetime, timedelta

# Import shared utilities for atomic writes and LinkedIn rate tracking
import sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/gtm-shared'))
try:
    from gtm_utils import (atomic_append_csv, atomic_write_csv,
                           check_linkedin_rate, increment_linkedin_rate,
                           normalize_company_key)
except ImportError:
    pass  # Fallback: use regular csv.writer if shared utils not available

TRACKER_PATH = os.path.expanduser('~/.claude/gtm-stack/outreach-tracker.csv')
TRACKER_FIELDS = [
    'Date', 'Time', 'Company', 'Contact_Name', 'Contact_Title',
    'Contact_Email', 'Contact_Type', 'Contact_LinkedIn', 'Channel', 'Fit_Score', 'Fit_Tier',
    'Email_Subject', 'Email_Body', 'LinkedIn_DM', 'Message_Preview',
    'Status', 'Failure_Reason', 'Outcome',
    'Follow_Up_Date', 'Follow_Up_Status', 'Notes', 'Source_CSV', 'Pipeline_Run'
]

# Default follow-up cadence (business days). Override via sender profile.
FOLLOW_UP_CADENCE = {
    'Strong Fit': 3,
    'Moderate Fit': 5,
}

def ensure_tracker_exists():
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    if not os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()

def calculate_follow_up_date(send_date_str, tier='Moderate Fit'):
    """Add N business days to send date, based on tier cadence."""
    biz_days = FOLLOW_UP_CADENCE.get(tier, 5)
    send_date = datetime.strptime(send_date_str, '%Y-%m-%d')
    days_added = 0
    current = send_date
    while days_added < biz_days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            days_added += 1
    return current.strftime('%Y-%m-%d')

def log_outreach(record):
    """Append a single outreach record to the tracker."""
    ensure_tracker_exists()
    now = datetime.now()
    record.setdefault('Date', now.strftime('%Y-%m-%d'))
    record.setdefault('Time', now.strftime('%H:%M'))
    tier = record.get('Fit_Tier', 'Moderate Fit')
    record.setdefault('Follow_Up_Date', calculate_follow_up_date(record['Date'], tier))
    record.setdefault('Follow_Up_Status', 'Pending')
    record.setdefault('Failure_Reason', '')
    record.setdefault('Outcome', 'No Response')
    record.setdefault('Notes', '')

    with open(TRACKER_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_FIELDS,
                                quoting=csv.QUOTE_ALL, extrasaction='ignore')
        writer.writerow(record)
```

### Log immediately after each send — do NOT batch at the end.
If the session crashes mid-run, all completed sends are already logged.

---
