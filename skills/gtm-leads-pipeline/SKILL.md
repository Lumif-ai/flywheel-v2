---
name: gtm-leads-pipeline
version: "1.0"
description: >
  Use this skill to run a full end-to-end lead generation, qualification, and outreach pipeline.
  Trigger when the user wants to find AND evaluate AND contact companies in one flow — e.g. "find
  construction companies from this directory, score them, and send outreach", "scrape these
  alumni, tell me which are good prospects, and email the strong fit ones", "build me a scored lead
  list from this URL and start outbound", "run the full pipeline on this directory", or "scrape,
  score, and send". Orchestrates gtm-web-scraper-extractor, gtm-company-fit-analyzer, and
  gtm-outbound-messenger skills in sequence — scraping first, then scoring, then sending outreach
  to qualified leads. Maintains a persistent outreach tracker at ~/.claude/gtm-stack/outreach-tracker.csv.
  Requires all three skills to be installed.

  Requires: Playwright MCP connected. gtm-web-scraper-extractor, gtm-company-fit-analyzer, and
  gtm-outbound-messenger skills installed.
compatibility: "Requires Playwright MCP, gtm-web-scraper-extractor, gtm-company-fit-analyzer, and gtm-outbound-messenger skills."
context-aware: true
web_tier: 2
---

# Leads Pipeline Skill

End-to-end lead generation + qualification + outreach in one session:
**Scrape → Collapse to companies → Score → Send outreach → Track everything → Deliver**

This skill is an orchestrator — it contains no scraping, scoring, or sending logic itself.
It runs `gtm-web-scraper-extractor`, `gtm-company-fit-analyzer`, and `gtm-outbound-messenger` in
sequence and manages the handoff between them.

Requires:
- `gtm-web-scraper-extractor` skill installed
- `gtm-company-fit-analyzer` skill installed
- `gtm-outbound-messenger` skill installed
- Playwright MCP connected

---

## How to Use

### Direct invocation (start here for end-to-end pipelines)
In Claude Code, type:
```
/gtm-leads-pipeline
```
Claude will ask a single intake interview covering scraping, scoring, outreach,
and sending preferences — then run the full pipeline without interruption.

### Natural language triggers
- *"Find construction companies from this directory, score them, and send outreach"*
- *"Scrape these alumni, score them, and email the strong fit ones"*
- *"Build me a scored lead list from [URL] and start outbound"*
- *"Run the full pipeline on this directory"*
- *"Scrape, score, and send"*

### What happens when you run it
1. **Single intake interview** — one set of questions covers everything
2. **Scrape** — extracts all records from the source URL into a CSV
3. **Collapse** — deduplicates people into unique companies
4. **Score** — deep-crawls each company and assigns a fit score (0–100)
5. **Outreach** — drafts personalized email + LinkedIn DM for every Strong Fit and Moderate Fit company
6. **Send** — sends outreach via user's email client + LinkedIn (with preview/approval)
7. **Track** — logs every send to the persistent outreach tracker
8. **Deliver** — ranked list with scores, reasoning, contacts, outreach status

### When to use this vs. the individual skills
| Task | Use |
|------|-----|
| Scrape only (no scoring) | `/gtm-web-scraper-extractor` |
| Score a CSV you already have | `/gtm-company-fit-analyzer` |
| Send outreach to an already-scored CSV | `/gtm-outbound-messenger` |
| Check follow-ups or outreach history | `/gtm-outbound-messenger` |
| Scrape + score + send in one run | `/gtm-leads-pipeline` ← this skill |

---

## STEP 0 — Verify Prerequisites

1. **Playwright MCP** -- check for `browser_navigate` or `playwright_navigate` tools.
   If missing: "Please connect Playwright MCP and restart Claude Code."

2. **All three skills installed** -- check that SKILL.md files exist for
   `gtm-web-scraper-extractor`, `gtm-company-fit-analyzer`, and `gtm-outbound-messenger`
   in the Claude skills directory.
   If any missing, tell the user which one and how to install it.

3. **Block if critical deps missing.** Do not proceed past Step 0 without Playwright and all three sub-skills.

4. **Outreach tracker** -- check for existing tracker:
   ```bash
   cat ~/.claude/gtm-stack/outreach-tracker.csv 2>/dev/null | head -3 || echo "NOT_FOUND"
   ```
   If found, note how many contacts exist (for dedup during send phase).

---

### 0b. Context Store Pre-Read
- Read `~/.claude/context/_catalog.md` to discover available files
- Load: `positioning.md`, `icp-profiles.md`, `pain-points.md`, `contacts.md`
- Cap: max 10 recent entries per file
- Show what was loaded: "Loaded X entries from Y context files"
- Use positioning data to inform outreach personalization
- Use ICP profiles and pain points to inform scoring criteria
- Use contacts to check for previously discovered decision makers

---

## STEP 0.5 — Load Sender Profile

The sender profile captures who YOU are. It's built once with `/gtm-my-company` and
loaded silently here — no re-entry needed if the file exists.

**Profile path:** `~/.claude/gtm-stack/sender-profile.md`

Check via bash:
```bash
cat ~/.claude/gtm-stack/sender-profile.md 2>/dev/null || echo "NOT_FOUND"
```

### If profile FOUND — load silently and proceed:

Read the full profile into memory. Then show a single confirmation banner and
**continue immediately to STEP 1** — do not ask for A/B/C confirmation:

```
✅ Company profile loaded: [Company Name] (last updated: [date])
   Sender: [Name, Title]
   ICP: [Industry] · [Type] · [Size] · [Geography]
   Fit signals: [Signal 1], [Signal 2]
   Disqualifiers: [Disqualifier 1], [Disqualifier 2]
   Outreach tracker: [N] contacts logged (or "new — no outreach history yet")
   (Run /gtm-my-company any time to update this)
```

Skip questions 5–8 from STEP 1 entirely. Populate fit signals and disqualifiers
from the profile's "Fit Scoring Signals" section. Pull sender name from the
profile's "Sender" section for use in outreach.

If the user says "actually I want to use different scoring context" at any point
before the plan is confirmed (STEP 2) → ask what to change, apply in memory for
this run only, and continue. Do not re-run the full build wizard.

### If profile NOT FOUND:

```
No company profile found yet.

I can set one up now (~5–10 min) — it saves permanently and loads automatically
in every future pipeline run. Or I'll ask about your business below for this
session only.

Set up company profile now? (yes / no)
```

- **yes:** Tell user "I'll open a quick setup — when it's done, come back and
  run `/gtm-leads-pipeline` again. Your profile will load automatically."
  Then run the `/gtm-my-company` Build Wizard (STEP 2 of that skill).
  After saving, remind: "Profile saved. Now restart `/gtm-leads-pipeline`."

- **no:** Fall through to STEP 1 with all questions intact (including 5–8).

---

## STEP 0.7 — Load Learned Preferences (Self-Learning)

The pipeline learns user preferences over time and stores them in memory files.
Check for a preferences file that may contain saved defaults:

**Preferences path:** Check the project memory directory for `gtm-pipeline.md` or similar files.
Look in the auto-memory directory (the path shown in the system context as "persistent auto memory directory").

```bash
# Check for learned preferences in memory
cat "$(find ~/.claude/projects -name 'gtm-pipeline.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

### If preferences FOUND — extract and auto-apply:

Read the file and extract any saved defaults. Common learned preferences include:

1. **Known source URLs** — if user mentions a source by alias (e.g. "MIT alumni portal"),
   resolve it to the saved URL automatically. Pre-fill question 1 in STEP 1.

2. **Email channel preferences** — if the file maps source → channel (e.g. "MIT alumni → Outlook"),
   auto-select the channel. Skip question 6 in STEP 1.

3. **Saved email templates** — if a default template exists for this source type,
   auto-select option A and use the saved template. Skip question 5 in STEP 1.

4. **Scoring process notes** — apply any saved scoring rules (e.g. single-pass only,
   checklist-based scoring). These affect STEP 5 behavior, not intake questions.

5. **Default sending mode, output preferences** — if saved, pre-fill and skip those questions.

Show what was auto-applied in the profile banner (append to STEP 0.5 banner):

```
   Learned preferences loaded:
   ├─ Source alias: "MIT alumni" → https://alum.mit.edu/directory/
   ├─ Email channel: Outlook (sharanjm@alum.mit.edu)
   ├─ Template: Saved MIT alumni template (option A)
   └─ Scoring: Single-pass checklist mode
```

Then in STEP 1, **skip any question that has a pre-filled answer** from preferences.
Only ask questions that genuinely need new input (filters, specific people, etc.).

### If preferences NOT FOUND — proceed normally:

No action needed. STEP 1 asks all questions as usual.

### Saving new preferences after each run:

At the end of every pipeline run (after STEP 7), check if the user provided any
answers that should become defaults for future runs. Save/update preferences for:

- Any new source URL + alias the user provided
- The email channel used (mapped to the source)
- Any email template pasted or approved
- Sending mode if the user expressed a consistent preference

Write updates to the same memory file. Use the Edit tool to update existing entries
rather than duplicating. This is how the skill "learns" — each run may refine the
preferences file, so future runs ask fewer questions.

---

## STEP 1 — Single Intake Interview

**If profile was loaded:** ask only the shortened set below (10 questions),
**minus any questions already answered by learned preferences from STEP 0.7.**
**If no profile:** ask all 15 questions in one message.

### With profile loaded (ask only unanswered questions from these):

For each question below, check if STEP 0.7 already provided a default.
If yes, show the pre-filled value and skip the question.
If no, ask it as normal.

---
> **Let's set up your pipeline. A few things before I start:**
>
> **Finding leads:**
> 1. URL of the directory, alumni site, or listing to scrape?
> 2. What information to extract per person? (e.g. Name, Company, Title, Location, Email)
> 3. Any filters or search terms to apply? (e.g. "US only", "Industry: Construction")
> 4. Login required? If yes, please log in before I start.
>
> **Outreach (drafted AND sent for Strong Fit & Moderate Fit companies):**
> 5. Starting point for outreach messages:
>    - **A:** Paste your existing email + LinkedIn template — I'll personalize each one
>    - **B:** Share a rough draft or talking points — I'll refine per company
>    - **C:** Write both from scratch based on what I find
>
> 6. Which channels to send through?
>    - **Email** (browser — Gmail, Outlook, Zoho, Yahoo, ProtonMail, or any webmail)
>    - **LinkedIn DM**
>    (pick one or more)
>
> 7. Sending mode:
>    - **A: Preview each** — I show each message before sending (recommended)
>    - **B: Batch preview** — I draft all, you review the batch, then I send
>    - **C: Auto-send** — I send without preview (only if you trust templates)
>
> **Output:**
> 8. Where to save the final CSV? (Default: `~/Downloads/leads_scored_<date>.csv`)
> 9. Show only Strong Fit leads at the end, or the full ranked list?
> 10. Minimum score threshold for outreach? (Default: 50 = Strong Fit + Moderate Fit)
---

### Without profile (ask all):

---
> **Let's set up your pipeline. A few things before I start:**
>
> **Finding leads:**
> 1. URL of the directory, alumni site, or listing to scrape?
> 2. What information to extract per person? (e.g. Name, Company, Title, Location, Email)
> 3. Any filters or search terms to apply? (e.g. "US only", "Industry: Construction")
> 4. Login required? If yes, please log in before I start.
>
> **Scoring what we find:**
> 5. Your name and title
> 6. What your business does (2–3 sentences)
> 7. Who is your ideal customer? (industry, size, geography)
> 8. What makes a company a great fit?
> 9. What disqualifies a company?
>
> **Outreach (drafted AND sent for Strong Fit & Moderate Fit companies):**
> 10. Starting point for outreach messages:
>    - **A:** Paste your existing email + LinkedIn template — I'll personalize each one
>    - **B:** Share a rough draft or talking points — I'll refine per company
>    - **C:** Write both from scratch based on what I find
>
> 11. Which channels to send through?
>    - **Email** (browser — Gmail, Outlook, Zoho, Yahoo, ProtonMail, or any webmail)
>    - **LinkedIn DM**
>    (pick one or more)
>
> 12. Sending mode:
>    - **A: Preview each** — I show each message before sending (recommended)
>    - **B: Batch preview** — I draft all, you review the batch, then I send
>    - **C: Auto-send** — I send without preview (only if you trust templates)
>
> **Output:**
> 13. Where to save the final CSV? (Default: `~/Downloads/leads_scored_<date>.csv`)
> 14. Show only Strong Fit leads at the end, or the full ranked list?
> 15. Minimum score threshold for outreach? (Default: 50 = Strong Fit + Moderate Fit)
---

Store all answers. Do not re-ask any of these during the run.

### Input Validation
- Verify: source URL provided and non-empty before proceeding to scrape phase.
- Verify: if user selected sending mode, at least one channel (email or LinkedIn) is chosen.
- For batches >50 expected leads: confirm scope with user before proceeding.

### Parallel Execution
Scale sub-skill agents to batch volume. Reference `gtm-shared/parallel.py` for helpers.

| Items | Agents | Notes |
|-------|--------|-------|
| 1-5   | Sequential | Overhead not worth it |
| 6-15  | 2 | -- |
| 16-30 | 3 | -- |
| 31-50 | 4 | -- |
| 51+   | 5 (cap) | Avoid rate limits |

Sub-skills have their own batch sizing (scraper tabs, scorer tabs, messenger tabs).
The orchestrator uses this table when deciding how many parallel agents to spawn
for the scoring and outreach phases.

---

## STEP 2 — Confirm the Plan

Summarize and get confirmation before touching the browser:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 PIPELINE PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1 — SCRAPE
  Source:  [URL]
  Filters: [filters or "none"]
  Fields:  [field list]
  Output:  [CSV path]
  Est:     ~[N] pages × 12s = ~[N] min

PHASE 2 — SCORE (parallel: 2-3 browser tabs)
  Profile: [1-line fit summary]
  Method:  Quick pass (parallel) → deep crawl (pipelined) → DM lookup (parallel)
  Adds:    Fit_Score, Fit_Tier, Reasoning,
           Email + LinkedIn DM for Strong Fit & Moderate Fit
  DM lookup: After scoring, Strong Fit & Moderate Fit only
  Parallel: 3 tabs for quick filter, 2 tabs pipelined for deep crawl
  Est:     ~[N] companies × 1 min = ~[N] min (3x faster than sequential)

PHASE 3 — SEND OUTREACH (email + LinkedIn in parallel)
  Channels:     [Email + LinkedIn DM]
  Tiers:        Strong Fit + Moderate Fit (score ≥ [threshold])
  Sending mode: [Preview each / Batch / Auto]
  Parallel:     Email (up to 4 tabs) + LinkedIn (1 tab) running concurrently
  Rate limits:  Email: 40/day per inbox | LinkedIn: 30/day, 150/week
  Tracker:      ~/.claude/gtm-stack/outreach-tracker.csv
  Skipping:     [N] already contacted (from tracker)

TOTAL ESTIMATE: ~[N] min (was ~[N] hours sequential)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Proceed?
```

Wait for confirmation. Do not start until user says yes.

---

## STEP 3 — Scrape

Follow the `gtm-web-scraper-extractor` skill workflow:
1. Pre-scrape audit (login, filters, count, selectors, pagination)
2. Scraping loop with progress updates
3. Cleanup (deduplicate, trim whitespace)
4. Save CSV

Report when done:
```
✅ SCRAPE COMPLETE
  People found:      [N]
  Duplicates removed:[N]
  Saved to:          [path]
```

---

## STEP 4 — Collapse People → Companies (critical handoff)

The scraper extracts *people*. The scorer evaluates *companies*.
Before scoring, deduplicate at the company level so each company is only researched once.

Before running: read the CSV headers from the scraped file and confirm which column
holds company names. Check for: Company, Employer, Organization, Firm, Workplace.
If the header is not "Company", update company_col below. If multiple candidates exist,
ask the user to confirm before running.

Set paths explicitly:
- `SCRAPED_CSV_PATH` = the path saved during STEP 3 (from the scraper output)
- `SCORING_CSV_PATH` = same directory, same base name + `_scoring.csv`

Run via bash_tool:
```python
import csv
from collections import defaultdict

def collapse_to_companies(input_path, output_path, company_col):
    companies = defaultdict(list)
    fieldnames = []

    with open(input_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            company = row.get(company_col, '').strip()
            if company:
                companies[company].append(row)

    if not companies:
        print(f"ERROR: No companies found. Check that '{company_col}' matches a CSV header.")
        print(f"Available headers: {fieldnames}")
        return 0

    out_fields = list(fieldnames) + ['All_Contacts']
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=out_fields,
                                quoting=csv.QUOTE_ALL, extrasaction='ignore')
        writer.writeheader()
        for company, people in companies.items():
            row = dict(people[0])
            contacts = []
            for p in people:
                parts = [p.get('Name', ''), f"({p.get('Title', '')})" if p.get('Title') else '']
                if p.get('Email'): parts.append(p['Email'])
                if p.get('LinkedIn_URL'): parts.append(p['LinkedIn_URL'])
                contacts.append(' '.join(filter(None, parts)))
            row['All_Contacts'] = '; '.join(contacts)
            writer.writerow(row)

    return len(companies)

company_col = 'Company'
unique = collapse_to_companies(
    input_path='SCRAPED_CSV_PATH',
    output_path='SCORING_CSV_PATH',
    company_col=company_col
)
print(f"Collapsed to {unique} unique companies")
```

Report:
```
📊 HANDOFF — SCRAPE → SCORE
  People scraped:       [N]
  Unique companies:     [N]  ← scoring this many
  Contacts preserved in All_Contacts column

Starting scoring...
```

---

## STEP 5 — Score

**IMPORTANT — Single-pass scoring only:**
Never show an intermediate qualitative assessment table (e.g. "Strong", "Moderate")
before assigning numerical scores. Go straight to checklist-based scoring using the
sender profile's fit signals and disqualifiers. Check each signal as a yes/no against
the researched company, then assign the numerical score. This prevents contradictions
between qualitative labels and actual scores.

Follow the `gtm-company-fit-analyzer` skill workflow using:
- The fit profile and outreach inputs from Step 1 — **skip the interview, it's done**
- The collapsed company CSV from Step 4
- **Parallel execution** — use dynamic batch sizing from gtm-company-fit-analyzer:
  - Quick filter: batch_size auto-calculated (up to 5 tabs for large lists)
  - Deep crawl: batch_size auto-calculated (up to 3 tabs, pipelined)
  - DM lookup: batch_size max 2 (LinkedIn rate-limited)

Remind user at start of scoring:
```
Scoring [N] companies
  Phase 1: Quick filter — [batch_size] tabs, ~[N] min
  Phase 2: Deep crawl + score — [batch_size] tabs pipelined, ~[N] min
  Phase 3: DM lookup — [batch_size] tabs, ~[N] min (Strong Fit + Moderate Fit only)
Progress updates every 5 companies.
```

---

## STEP 5.5 — Generate Deliverables After Scoring

**Always run this immediately after scoring completes, before outreach.**
This ensures the xlsx, html dashboard, and pipeline log exist even if the user
skips or pauses outreach. STEP 7.5 will re-run the same scripts to update with
outreach data after sending.

### 5.5a — Log the pipeline run

Same as STEP 7.5a — run `log_run.py` with all scraping + scoring stats.
At this point, outreach fields are zero (no sends yet).

```bash
python ~/.claude/skills/gtm-leads-pipeline/scripts/log_run.py \
    --source "[Source name]" \
    --source-url "[URL]" \
    --filters "[Filters]" \
    --people-scraped [N] \
    --duplicates-removed [N] \
    --unique-companies [N] \
    --scored [N] \
    --strong-fit [N] \
    --moderate-fit [N] \
    --low-fit [N] \
    --no-fit [N] \
    --csv-path "[path to scored CSV]" \
    --duration-min [N]
```

### 5.5b — Build master workbook + dashboard

```bash
python ~/.claude/skills/gtm-leads-pipeline/scripts/merge_master.py
python ~/.claude/skills/gtm-dashboard/scripts/generate_dashboard.py
```

Report:
```
📁 DELIVERABLES READY (pre-outreach)
  Master workbook: ~/.claude/gtm-stack/gtm-leads-master.xlsx
  Dashboard:       ~/.claude/gtm-stack/gtm-dashboard.html
  Pipeline log:    ~/.claude/gtm-stack/pipeline-runs.json

  These will be updated again after outreach is sent.
```

If user wants to stop here (no outreach), the files are already complete with
scoring data. Outreach columns will show "No" / empty — that's correct.

---

## STEP 6 — Send Outreach

After scoring is complete, transition to the gtm-outbound-messenger workflow.

### 6a. Handoff summary

```
📊 HANDOFF — SCORE → OUTREACH
  Companies scored:     [N]
  🔴 Strong Fit (75-100):     [N]
  🟡 Moderate Fit (50-74):     [N]
  🔵 Low Fit (25-49):     [N]  ← not contacted
  ⚫ No Fit (<25):       [N]  ← not contacted

  Ready for outreach:   [N] (Strong Fit + Moderate Fit, score ≥ [threshold])
  Already contacted:    [N] (found in outreach tracker — skipping)
  New leads to contact: [N]

Starting outreach...
```

### 6b. Authenticate channels

Follow `gtm-outbound-messenger` STEP 3 — verify user is logged into each selected channel.
Do NOT proceed until authenticated.

### 6c. Personalize and send

Follow `gtm-outbound-messenger` STEPs 4–5:
- Use the sender profile loaded in STEP 0.5 for personalization context
- Use user's template choice from STEP 1 intake
- Use the sending mode selected in STEP 1
- **Parallel email drafting:** Use dynamic batch sizing (1–4 tabs based on email count) to compose/preview emails simultaneously
- **Sequential LinkedIn DMs:** Send one at a time with 30-60s delays (rate-limited)
- For each Strong Fit/Moderate Fit lead: personalize → preview (if applicable) → send → log to tracker
- Show progress every 5 leads

### 6d. Channel-specific order (parallel channels)

When both email and LinkedIn are selected, run them **in parallel** using separate
browser tabs. Email and LinkedIn are independent channels with no dependencies.

- **Tab group 1 (email):** Dynamic batch sizing (1-4 tabs) for parallel compose/send
- **Tab group 2 (LinkedIn):** Dedicated tab for connection requests (sequential within LinkedIn)
- Both groups run concurrently for maximum throughput

**Rate limits enforced per channel:**
- **Email:** 40 per inbox per day. If leads exceed this, warn the user:
  "Sending more than 40 emails/day per inbox risks spam filters and lowers sender
  trust score. Recommend sending 40 today and queuing the rest for tomorrow."
- **LinkedIn:** 30 per day, 150 per week. Check both limits before starting.

---

## STEP 7 — Final Delivery

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 PIPELINE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRAPE
  People found:      [N]
  Unique companies:  [N]

SCORING
  Quick-passed:      [N]  (obvious non-fits, skipped deep crawl)
  Deep-crawled:      [N]
  Websites found:    [N]/[N]
  Decision makers:   [N] (Strong Fit & Moderate Fit only)

OUTREACH
  📧 Emails sent:    [N] via [channel]
  💬 LinkedIn DMs:   [N]
  ⏭ Skipped:        [N]
  ❌ Failed:         [N]
  Follow-ups due:    [date range]

RESULTS
  🔴 Strong Fit  (75–100): [N]  — [N] contacted
  🟡 Moderate Fit (50–74):  [N]  — [N] contacted
  🔵 Low Fit (25–49):  [N]
  ⚫ No Fit (<25):    [N]

TOP LEADS CONTACTED
  1. [Company] — [Score]/100
     [DM Name], [Title]
     📧 ✅  💬 ✅
     → [First sentence of email]

  2. [Company] — [Score]/100
     [DM Name], [Title]
     📧 ✅  💬 ✅
     → [First sentence of email]

  3. [Company] — [Score]/100
     [DM Name], [Title]
     📧 ✅  💬 ✅
     → [First sentence of email]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**IMPORTANT — Always show the deliverables section prominently at the very end.**
This must be a clear, separate block AFTER the summary — never buried inside it.
The user needs to see exactly where their files are without hunting through the report.

**Always regenerate the dashboard** after sending outreach by running the
`dashboard/scripts/generate_dashboard.py` script before showing deliverables.

After the summary above, ALWAYS end with this deliverables block:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Master workbook:   ~/.claude/gtm-stack/gtm-leads-master.xlsx
  Dashboard:         ~/.claude/gtm-stack/gtm-dashboard.html
                     (open in any browser)
  Outreach tracker:  ~/.claude/gtm-stack/outreach-tracker.csv
                     Total contacts (all time): [N]
                     This session: [N]
  Pipeline log:      ~/.claude/gtm-stack/pipeline-runs.json
  Scored CSV:        [full path to session CSV]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

This deliverables block is **mandatory** — never skip it, even if the run was partial.

---

## STEP 7.5 — Update Deliverables After Outreach

After outreach is sent, re-run the same three scripts to update xlsx/html with
outreach data (contacted status, email content, follow-up dates). These files
were first created in STEP 5.5 — this step updates them.

### 7.5a — Update the pipeline run log

Use the `log_run.py` helper script (updates the existing run with outreach stats):

```bash
python ~/.claude/skills/gtm-leads-pipeline/scripts/log_run.py \
    --source "[Source name from STEP 1]" \
    --source-url "[URL from STEP 1]" \
    --filters "[Filters from STEP 1]" \
    --people-scraped [N] \
    --duplicates-removed [N] \
    --unique-companies [N] \
    --scored [N] \
    --strong-fit [N] \
    --moderate-fit [N] \
    --low-fit [N] \
    --no-fit [N] \
    --csv-path "[path to scored CSV]" \
    --duration-min [N]
```

This appends to `~/.claude/gtm-stack/pipeline-runs.json` and automatically
triggers merge + dashboard generation.

If the script isn't found at that path, try:
```bash
find ~/.claude -name "log_run.py" -path "*/leads-pipeline/*" 2>/dev/null | head -1
```

### 7.5b — Build the master workbook

```bash
python ~/.claude/skills/gtm-leads-pipeline/scripts/merge_master.py
```

This reads all scored CSVs + outreach tracker + DNC list and produces:
`~/.claude/gtm-stack/gtm-leads-master.xlsx`

Tabs: All Companies (deduped) | Outreach Log | Pipeline Runs | one per source.

### 7.5c — Generate the GTM Dashboard

```bash
python ~/.claude/skills/gtm-dashboard/scripts/generate_dashboard.py
```

Reads the master workbook and produces a self-contained HTML dashboard at:
`~/.claude/gtm-stack/gtm-dashboard.html`

Include in the final output:
```
Dashboard: ~/.claude/gtm-stack/gtm-dashboard.html
           (auto-generated — open in any browser)
```

---

## Checkpoint Protocol

- Save to `~/.claude/gtm-stack/pipeline_status.md` every 10 items (companies scored or messages sent)
- At startup: check for existing status file, offer resume
- Include: phase (scrape/score/outreach), items completed, items remaining, partial results path, CSV path
- Status file is the single source of truth for resume decisions

## Resuming a Partial Run

**Interrupted during scraping:**
Check for partial CSV + status file. Resume from the scraper's last completed page.
Then proceed to collapse → score → send as normal.

**Interrupted during scoring:**
Open CSV — skip rows where `Fit_Score` is already populated.
Re-read fit profile and outreach mode from status file.
Continue appending to same CSV.

**Interrupted during outreach:**
Load outreach tracker → identify which leads from the scored CSV have already been
contacted. Resume sending from the first uncontacted Strong Fit/Moderate Fit lead.
No risk of double-sends — the tracker is the source of truth.

At session start, if partial run detected:
> "Found a partial run:
>   Scraping: [complete / partial at page N]
>   Scoring: [N] of [N] companies scored
>   Outreach: [N] of [N] messages sent
>
> Resume where we left off, or start fresh?"

---

## Progress Updates

Show per-phase milestone updates between phases and every 5 items within phases:

```
PIPELINE PROGRESS — Phase [N]/3
  Scrape:   [complete] [N] people from [N] pages
  Score:    X/Y companies (~Z min remaining)
            Strong: N | Moderate: N | Low: N | No Fit: N
  Outreach: X/Y messages sent (~Z min remaining)
            Email: N | LinkedIn: N | Skipped: N | Failed: N
```

Sub-skills (scraper, scorer, messenger) provide their own per-item progress.
The orchestrator shows phase-level milestones at each handoff.

---

### Idempotency
- Before writing: check for existing entry with composite key (company + source + date)
- If duplicate found: skip write, log "duplicate skipped"
- Re-running produces same output without duplicates
- The outreach tracker is the dedup source of truth for sends (checked in STEP 6)

### Context Management
- Compress working context every 10 items (discard raw crawl text, keep scored summaries)
- Hard checkpoint every 20 items: save all state to disk (CSV + status file)
- Follow the gtm-company-fit-analyzer's checkpoint protocol for the scoring phase

### Backup Protocol
- Before overwriting scored CSV or outreach tracker: create `.backup.YYYY-MM-DD`, keep last 3
- Use `gtm-shared/gtm_utils.backup_file()` where applicable

## Orchestration Rules

- **Never re-ask anything from Step 1** mid-pipeline — all inputs are locked in.
- **Never create a second CSV** unless user explicitly asks for a shortlist export.
- **Pass fit profile and outreach mode explicitly** into the scorer — don't let it re-interview.
- **Pass sender profile + templates explicitly** into the messenger — don't let it re-ask.
- **Log every send immediately** — the outreach tracker is written after each send, not batched.
- **Send email and LinkedIn in parallel** — they are independent channels; run concurrently using separate browser tabs.
- **Context management:** follow the gtm-company-fit-analyzer's checkpoint protocol (compress every 10, hard checkpoint every 20, bail gracefully if context fills).
- **If anything fails mid-run:** save progress, report clearly what completed vs. what remains, give user the option to resume.
- **The outreach tracker is the single source of truth** for who has been contacted. It persists across sessions at `~/.claude/gtm-stack/outreach-tracker.csv` and is checked at the start of every send phase to avoid duplicates.
- **Self-learning — save preferences after every run:** At the end of each pipeline run, update the user's memory file (`gtm-pipeline.md` in their auto-memory directory) with any new or changed preferences: source URL aliases, email channel mappings, approved templates, sending mode defaults, and scoring process notes. This ensures the next run asks fewer questions. Use Edit to update existing entries — never duplicate.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-leads-pipeline.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Preferred data sources and source URL aliases
- Scoring weights and fit signal priorities
- Output format preferences (CSV path, columns, tier display)
- Default sending mode and channel preferences
- Template choices that were approved

### What NOT to save
- Session-specific content, temporary overrides, confidential data

## Error Handling

- **Sub-skill failure (scraper):** Save partial CSV if any pages were scraped. Report page count and offer to resume scraping or proceed with partial data.
- **Sub-skill failure (scorer):** Deliver scraped CSV as-is. Report which companies were scored before failure. Offer to resume scoring from last checkpoint.
- **Sub-skill failure (messenger):** Scored CSV is intact. Check outreach tracker for what was already sent. Resume from first unsent lead.
- **CSV merge failure (collapse step):** Check column headers match expected format. Report mismatched headers and ask user to confirm company column name.
- **Script failure (log_run.py, merge_master.py, generate_dashboard.py):** Log error, continue pipeline. Deliverable files may be stale but pipeline data in CSV is safe.
- Partial results: each phase saves its output independently (scraped CSV, scored CSV, outreach tracker). No phase depends on a later phase's writes.
- Final report includes success/failure counts per phase (scrape/score/outreach).

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |

## Context Store Post-Write
After completing the main workflow, write discovered knowledge back to the context store:
- Target files: `contacts.md`, `insights.md`
- Entry format: `[YYYY-MM-DD | source: gtm-leads-pipeline | <detail>] confidence: <level> | evidence: 1`
- Write to `contacts.md`: new decision makers discovered during scoring (name, title, company, LinkedIn URL)
- Write to `insights.md`: patterns observed across the batch (common fit signals, industry trends, outreach response patterns)
- DEDUP CHECK: Before writing, scan target file for same source + detail + date. Skip if exists.
- Write failures are non-blocking: log error, continue.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.
