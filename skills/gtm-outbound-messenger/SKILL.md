---
public: true
name: gtm-outbound-messenger
version: "2.0"
description: >
  [GTM Stack — idempotent sending, provider-agnostic email, rate tracking.] Send personalized outreach emails and LinkedIn DMs to scored leads via the browser.
  Trigger whenever the user wants to send outreach, email leads, message prospects,
  "send emails to hot leads", "reach out to warm companies", "send LinkedIn messages",
  "start outbound", "email the scored list", or "message the leads we scored".
  Reads the scored CSV from gtm-company-fit-analyzer or gtm-pipeline, filters for
  Moderate-to-Strong Fit companies, sends the scorer's pre-drafted messages (with optional
  refinement), and tracks everything via the browser. Maintains a persistent outreach tracker
  at ~/.claude/gtm-stack/outreach-tracker.csv, checks the Do Not Contact list, and supports
  structured outcome tracking.
  Also use this skill when the user says "who have I contacted", "outreach status",
  "follow up on leads", "show my outreach tracker", "show dashboard", "outreach dashboard",
  or "visualize outreach".

  Requires: Playwright MCP connected. A scored CSV with Fit_Score and Fit_Tier columns.
compatibility: "Requires Playwright MCP connected. Works with Gmail, Outlook, Zoho (browser), and LinkedIn."
context-aware: true
web_tier: 3
---

> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file is retained for historical reference only. The authoritative skill bundle is served via `flywheel_fetch_skill_assets` from the `skill_assets` table. Do not edit; edits here have no runtime effect.


# Outbound Messenger Skill

Send personalized outreach to scored leads via browser-based email and LinkedIn.
Maintains a persistent tracker so outreach history is never lost.

**Outreach tracker:** `~/.claude/gtm-stack/outreach-tracker.csv`
**Sender profile:** `~/.claude/gtm-stack/sender-profile.md` (loaded from my-company skill)

---

## How to Use

### Direct invocation
```
/gtm-outbound-messenger
```

### Natural language triggers
- *"Send emails to the hot leads"*
- *"Reach out to warm and hot companies from my scored list"*
- *"Message the leads on LinkedIn"*
- *"Start outbound on [CSV path]"*
- *"Who have I already contacted?"*
- *"Show my outreach tracker"*

### What it does
1. Loads scored CSV → filters Strong Fit + Moderate Fit leads
2. Loads sender profile for personalization context
3. Checks outreach tracker → skips anyone already contacted
4. Asks user to log into their email client + LinkedIn
5. **Finds email addresses** for leads missing emails (searches university/company websites)
6. For each lead: personalizes message → shows preview → **waits for user approval** → sends → logs to tracker
7. Delivers summary + updated tracker

### MANDATORY WORKFLOW RULES (NEVER VIOLATE)

These are hard rules. Violating any of them is a P0 bug.

1. **NEVER skip email lookup. LinkedIn URL ≠ outreach channel.** When the user provides
   a LinkedIn URL (or any LinkedIn source like a member directory, search results, or
   profile link), that is a RESEARCH SOURCE for identifying leads. It is NOT an
   instruction to send outreach on LinkedIn. Always use the LinkedIn profile to extract
   the person's name, title, and organization, then search for their email address on
   the organization's website, staff directory, or other online sources BEFORE drafting
   any outreach. Never navigate to a LinkedIn profile and start sending connection
   requests or messages without first completing the full sequence (rule 6 below).

2. **NEVER send without user approval.** Always draft messages first, show them to the
   user for review, and wait for explicit approval before sending. This applies to ALL
   channels (email AND LinkedIn). The only exception is Auto-Send mode (Mode C), which
   the user must explicitly select.

3. **Email and LinkedIn run in parallel.** Email is the primary outreach channel. LinkedIn
   connection requests are supplementary. Both channels send concurrently using separate
   browser tabs. Never jump straight to LinkedIn sends and skip email outreach.

4. **NEVER send InMail.** LinkedIn Message on a non-1st-degree connection = InMail
   (costs credits). Always send a connection request instead. Only send InMail if the
   user explicitly asks for it.

5. **Check for Connect before Message on LinkedIn.** LinkedIn shows BOTH "Message" and
   "Connect" on non-connected profiles. If Connect is visible, they are NOT a 1st-degree
   connection. Always send a connection request, not InMail.

6. **Retired leads: research successor + ask user about advisory outreach.**
   When research reveals a lead is retired, emeritus, or no longer in their role:
   a. **Always research their successor** at the same organization. The successor
      inherits the same pain points, budget, and infrastructure. Add the successor
      as a new lead with full research (title, org, email, fit signals).
   b. **Do NOT auto-eliminate the retired person.** Instead, ask the user:
      "Found that [Name] is retired from [Org]. Want to include them for
      research/advisory outreach? (Different messaging: learning from their
      experience, not selling.)"
   c. If user says yes, draft a research-oriented message (seeking insights and
      perspective, not pitching the product). Tag them as "Advisory" in the tracker.
   d. If user says no, skip them but still add the successor as a new lead.

7. **Enforced sequence. Every outreach run MUST follow this exact order:**
   1. Find/verify email addresses for all leads (STEP 3.5)
   2. Research each lead's company and role for personalization context
   3. Draft ALL messages (email + LinkedIn) for ALL leads
   4. Show drafts to user and wait for explicit approval
   5. Only after approval: send emails first, then LinkedIn connection requests
   6. Log every send to the outreach tracker

   Never start sending while still drafting. Never send on one channel before
   drafts for all channels are approved. Never skip straight to LinkedIn without
   first finding and emailing. The full batch of drafts must be reviewed and
   approved as a group before any message leaves.

---

## STEP 0 — Verify Prerequisites

### 0a. Playwright MCP
Check for `browser_navigate` or `playwright_navigate` tools.
If missing: "Please connect Playwright MCP and restart."

### 0b. Sender Profile
```bash
cat ~/.claude/gtm-stack/sender-profile.md 2>/dev/null || echo "NOT_FOUND"
```

- **Found:** Load silently. Extract: Sender Name, Title, Company Name, What We Offer,
  Value Propositions, Outreach Context, Buyer Personas (for tone + hooks).
- **Not found:** Read company context from the context store via `flywheel_read_context` (look for company-intel, positioning, sender profile entries). If still missing, ask user for: name, title, company name, one-liner about what they do.

### 0c. Outreach Tracker
```bash
cat ~/.claude/gtm-stack/outreach-tracker.csv 2>/dev/null | head -5 || echo "NOT_FOUND"
```

- **Found:** Load into memory. Build a Set of `contact_name|company|channel` to skip
  already-contacted leads.
- **Not found:** Will create after first send.

### 0d. Do Not Contact List
```bash
cat ~/.claude/gtm-stack/do-not-contact.csv 2>/dev/null | head -5 || echo "NOT_FOUND"
```

- **Found:** Load into memory. Build a Set of company names (lowercased) to skip.
  Any lead whose company is on this list will be automatically excluded.
- **Not found:** Proceed normally — no exclusions.

### 0e. Input Validation
- Verify: scored CSV path provided and file exists before proceeding.
- Verify: scored CSV contains `Fit_Score` and `Fit_Tier` columns (read header row).
- Verify: at least one Strong Fit or Moderate Fit lead exists after filtering.
- If CSV missing or malformed: "Scored CSV not found or missing required columns (Fit_Score, Fit_Tier). Run `/gtm-company-fit-analyzer` first."

### 0f. Context Store Pre-Read
- Read `~/.claude/context/_catalog.md` to discover available files
- Load: `positioning.md`, `objections.md`, `pain-points.md`, `gtm-playbooks.md`
- Cap: max 10 recent entries per file
- Show what was loaded: "Loaded X entries from Y context files"
- Use positioning data to inform message personalization and value prop framing
- Use objections to preemptively address common pushback in outreach
- Use pain points to sharpen hooks in email subjects and LinkedIn DMs
- Use playbooks to match outreach tone and sequence to the lead source

---

## STEP 1 — Intake

Ask all at once:

---
> **Outbound setup:**
>
> 1. **Scored CSV path** — where is your scored leads file?
>    (Default: most recent `leads_scored_*.csv` in ~/Downloads)
>
> 2. **Which tiers to contact?**
>    - A: 🔴 Strong Fit only (75–100)
>    - B: 🔴 Strong Fit + 🟡 Moderate Fit (50–100) ← recommended
>    - C: Custom score threshold (e.g. "60+")
>
> 3. **Which channels?** (pick one or more)
>    - Email (browser-based — Gmail, Outlook, Zoho, Yahoo, ProtonMail, or any webmail)
>    - LinkedIn DM (for 1st-degree connections)
>    - LinkedIn Connection Request with note (for non-connections — auto-detected)
>
> 4. **Message source:**
>    - A: Paste your existing templates (email + LinkedIn) — I'll personalize each one
>    - B: Share rough talking points — I'll draft per lead
>    - C: Write from scratch using your sender profile + fit data
>
> 5. **Sending mode:**
>    - A: **Preview each** — I show you each message before sending (safest, recommended)
>    - B: **Batch preview** — I draft all messages, you review the batch, then I send approved ones
>    - C: **Auto-send** — I send without preview (only for experienced users who trust their templates)
---

Store all answers.

---

## STEP 2 — Load and Filter Leads

### 2a. Read the scored CSV

```python
import csv

def load_scored_leads(filepath, min_score=50):
    leads = []
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = int(row.get('Fit_Score', 0))
            except (ValueError, TypeError):
                continue
            if score >= min_score:
                leads.append(row)
    # Sort by score descending — contact hottest leads first
    leads.sort(key=lambda r: int(r.get('Fit_Score', 0)), reverse=True)
    return leads
```

### 2b. Cross-reference outreach tracker + DNC list — skip already contacted and excluded

```python
def filter_leads(leads, tracker_path, dnc_path, channels):
    """Remove leads that are on DNC list or already contacted on the same channel.
    Uses normalize_company_key() for consistent matching across files."""
    # Load DNC list — use normalized keys for fuzzy matching
    dnc_companies = set()
    try:
        with open(dnc_path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                dnc_companies.add(normalize_company_key(row.get('Company', '')))
    except FileNotFoundError:
        pass

    # Load tracker — use normalized keys
    contacted = set()
    try:
        with open(tracker_path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                name = row.get('Contact_Name','').strip().lower()
                company = normalize_company_key(row.get('Company', ''))
                channel = row.get('Channel','').strip().lower()
                status = row.get('Status', '')
                # Skip pending rows (from crashed sessions) — they need manual review
                if status == 'Pending':
                    continue
                key = f"{name}|{company}|{channel}"
                contacted.add(key)
    except FileNotFoundError:
        pass

    new_leads, skipped, dnc_skipped = [], [], []
    for lead in leads:
        company_key = normalize_company_key(lead.get('Company', ''))
        if company_key in dnc_companies:
            dnc_skipped.append(lead)
            continue

        dominated = True
        for ch in channels:
            name = lead.get('Name', lead.get('DM_Name', '')).strip().lower()
            key = f"{name}|{company_key}|{ch.lower()}"
            if key not in contacted:
                dominated = False
        if dominated:
            skipped.append(lead)
        else:
            new_leads.append(lead)

    return new_leads, skipped, dnc_skipped
```

### 2c. Report to user

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 OUTREACH PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Leads in CSV:           [N total]
Meets score threshold:  [N]
Already contacted:      [N] (skipped)
Do Not Contact:         [N] (excluded)
Ready to contact:       [N]

Channels: [Email + LinkedIn DM]
Mode:     [Preview each / Batch / Auto]

Top 5 leads to contact:
  1. [Company] — [Score]/100 — [Contact Name], [Title]
  2. ...

Estimated time: ~[N] min ([N] leads × ~2 min each)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Proceed?
```

Wait for confirmation.

---

## STEP 3 — Authenticate Channels

For each selected channel, verify the user is logged in.

### Email (auto-detect provider)

Ask the user which email provider they use, or detect from their email domain:

| Domain pattern | Provider | URL to check |
|---------------|----------|-------------|
| `@gmail.com` or Google Workspace | Gmail | `https://mail.google.com` |
| `@outlook.com`, `@hotmail.com`, `@live.com` | Outlook | `https://outlook.live.com/mail/` |
| `@*.onmicrosoft.com` or Office 365 | Outlook 365 | `https://outlook.office.com/mail/` |
| `@zoho.com` or Zoho domain | Zoho | `https://mail.zoho.com` |
| `@yahoo.com` | Yahoo | `https://mail.yahoo.com` |
| `@protonmail.com`, `@proton.me` | ProtonMail | `https://mail.proton.me` |
| Custom domain | Ask user | User provides URL |

**For any provider:**
1. Navigate to the provider's mail URL
2. Take screenshot
3. If login page → ask user to log in manually: "Please log into your email in the browser. Let me know when done."
4. After login confirmed → take screenshot to verify inbox is visible
5. Record which provider is active (used for compose method in STEP 5)

**Gmail-specific:** Use compose URL for To + Subject only, then fill body via form input:
`https://mail.google.com/mail/?view=cm&fs=1&to=EMAIL&su=SUBJECT&tf=cm`
**IMPORTANT:** Do NOT pass `&body=` in the Gmail compose URL — Gmail silently drops or
truncates body text from URL parameters, resulting in blank emails. Always fill the
body via `browser_fill_form` or `browser_type` on the contenteditable compose area
after the compose window loads (see STEP 5 Gmail compose method for details).

**Outlook-specific:** Note deep link format:
`https://outlook.live.com/mail/0/deeplink/compose?to=EMAIL&subject=SUBJECT&body=BODY`

### LinkedIn
1. Navigate to `https://www.linkedin.com/messaging/`
2. Take screenshot → verify logged in or ask user to log in
3. DM compose: navigate to profile URL → click "Message" button

**Important:** Do NOT proceed until all selected channels show authenticated state.
Take a confirming screenshot for each and tell the user:
```
✅ Email: logged in to [Provider] as [email visible]
✅ LinkedIn: logged in as [name visible]
```

---

## STEP 3.5 — Find Missing Email Addresses

**This step is MANDATORY.** Before drafting any messages, check if each lead has an
email address. If the `Email` column is empty, search for it.

### For each lead missing an email:

1. **Search the organization's website** for a staff directory, "Contact Us", or
   "Our Team" page. University websites often have directories at paths like:
   - `/directory/`, `/people/`, `/about/staff/`, `/contact/`
   - Department-specific pages (e.g., `/risk-management/`, `/finance/`)

2. **Search the web** using: `"[Name]" "[Organization]" email` or
   `"[Name]" site:[organization-domain]`

3. **Check LinkedIn contact info** — if you're on their profile, click "Contact info"
   to see if an email is listed (only works for 1st-degree connections or if they
   made it public).

4. **Infer from known patterns** — if other people at the same organization have emails
   like `firstname.lastname@org.edu`, try that pattern. But NEVER send to a guessed
   email without verifying it exists (e.g., via the organization's directory).

### Detect team vs individual emails

After finding an email (or if one already exists in the CSV), classify it:

```python
from gtm_utils import detect_team_email

contact_type = "Team" if detect_team_email(email, contact_name) else "Individual"
```

Common team email patterns: `info@`, `contact@`, `admin@`, `risk@`, `team@`, `hello@`,
`support@`, `office@`, `sales@`, `general@`, `hr@`, `finance@`, `operations@`, etc.

Store the `Contact_Type` in the lead data for use in STEP 4 personalization and STEP 6
tracker logging. If a lead has only a team email and no individual contact name, set
`Contact_Name` to the company name or department name (e.g., "Risk Management Team").

### If email is found:
- Update the CSV with the email address and Contact_Type
- Continue to STEP 4 (Personalize Messages)

### If email is NOT found after searching:
- Log the lead as "Email not found" in notes
- Still send LinkedIn connection request (if LinkedIn URL exists)
- Do NOT skip the lead entirely just because email is missing

### Progress report:
After searching, show:
```
Email lookup complete:
  [N] leads already had emails
  [N] emails found via search
  [N] emails not found (LinkedIn-only outreach)
```

---

## STEP 4 — Personalize Messages

### 4a. Check for pre-drafted messages

The `gtm-company-fit-analyzer` (scorer) drafts outreach messages during scoring. These are
stored in the `Email_Body`, `Email_Subject`, and `LinkedIn_DM` columns of the scored CSV.

For each lead, check if these columns are populated:

- **If `Email_Body` exists** → use it as the email. The scorer had deep crawl context
  and produced the most personalized version possible.
- **If `LinkedIn_DM` exists** → use it as the LinkedIn message.
- **If columns are empty** → fall back to drafting from scratch using STEP 4b rules below.

### 4b. Optional refinement

In Preview Each or Batch Preview modes, always show the pre-drafted message and offer
the option to edit before sending. The user can:
- **Accept as-is** (recommended — scorer's version is well-personalized)
- **Edit** — tweak wording, update a detail, change the CTA
- **Rewrite** — discard scorer's draft and write from scratch using sender profile

In Auto-send mode, send the scorer's draft without preview (the user trusted the templates).

### 4c. Drafting from scratch (fallback)

Only used when `Email_Body` / `LinkedIn_DM` columns are empty in the scored CSV.
Draft using data from:
- **Sender profile:** company name, value props, outreach context, buyer persona hooks
- **Lead data:** company name, contact name, title, fit score, fit reasoning,
  top fit signal, top concern, industry
- **User's template** (if provided in Mode A/B)

### Team vs Individual Email Personalization

When `Contact_Type = "Team"` (detected in STEP 3.5), adjust the email accordingly:

- **Greeting:** Use "Hello [Company] team," or "Hi there," instead of "Hi [First Name],"
- **Body:** Address the team/department, not an individual. Avoid referencing a specific
  person's role, background, or LinkedIn activity. Focus on the company/department's
  needs instead.
- **Example:** "Hello Acme Corp team, I noticed Acme is scaling its multi-state
  operations..." instead of "Hi John, saw your background in project management..."
- **LinkedIn:** Team emails typically have no associated LinkedIn profile. Skip LinkedIn
  outreach for team contacts unless a specific person is identified later.

### Email Personalization Rules

1. **Subject line:** Short, specific, NOT salesy. Reference their company or a signal.
   - Good: "Quick question about [Company]'s sub compliance process"
   - Good: "[First Name] — saw [Company] is scaling to [N] projects"
   - Bad: "Exciting opportunity for [Company]!" / "Let's connect"

2. **Body structure:**
   - Line 1: Personalized hook — reference something specific you found about their company
     (from Fit_Reasoning or Top_Fit_Signal). Never generic.
   - Line 2–3: Bridge to the pain point — connect the hook to a problem they likely have.
     Use buyer persona's "Cares about" and "Pain points" from sender profile.
   - Line 4: What you do — ONE sentence, plain English, from "What We Offer" section.
   - Line 5: Soft CTA — question, not a demand. "Would it make sense to chat for 15 min?"
   - Sign-off: Sender name + title from profile.

   **CRITICAL — Signature requirement:**
   Every drafted email body MUST end with a full signature block. The Gmail body fill
   procedure (Meta+a → insertText) replaces ALL content in the compose area, including
   Gmail's default signature. Therefore the drafted body text itself must contain the
   complete sign-off. Format:
   ```
   Best,
   [Sender Name]
   [Sender Title], [Company Name]
   [Company Website]
   ```
   Never rely on Gmail's auto-signature. Always include it in the drafted body text.

3. **Tone:** Conversational, peer-to-peer. NOT formal/corporate. Short paragraphs.
   Max 120 words total body. No bullet points in cold emails.

4. **DO NOT include:**
   - "I hope this email finds you well"
   - "I'm reaching out because..."
   - Multiple CTAs
   - Attachments or links (first touch only)
   - Buzzwords: "synergy", "leverage", "disrupt", "innovative", "cutting-edge"

### LinkedIn DM Personalization Rules

1. **Much shorter than email** — 3–5 sentences max, ~60 words
2. **Open with context:** "Saw [specific thing] about [Company]" or reference mutual connection
3. **One value statement:** What you do and why it's relevant to them specifically
4. **Soft close:** Question format — "Curious if this resonates?"
5. **No links, no attachments, no pitch decks** in first DM

### Message Generation Template

For each lead, produce:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEAD [N] of [TOTAL]: [Company Name] — [Score]/100 [Tier]
Contact: [Name], [Title]
Channels: [Email to: address] [LinkedIn: URL]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📧 EMAIL
Subject: [subject]

[body]

— [Sender Name], [Title]

💬 LINKEDIN DM
[dm text]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Send both  |  📧 Email only  |  💬 LinkedIn only  |  ✏️ Edit  |  ⏭ Skip
```

---

## STEP 5 — Send Messages

**Read `references/channel-send-methods.md` for the full send procedure.**

That file contains: parallel channel execution strategy, sending modes (A/B/C),
per-provider email compose methods (Gmail, Outlook, Zoho, Yahoo, ProtonMail),
Gmail body fill procedure with bug fixes, LinkedIn connection detection,
LinkedIn DM and connection request flows, and rate limiting.

**Key points (summary, detail in reference):**
- Email + LinkedIn run in parallel using separate browser tabs
- Three sending modes: Preview Each (A, default), Batch Preview (B), Auto-Send (C)
- Gmail requires HTML body insertion via `insertHTML` (compose URL drops `&body=`)
- All URLs must be wrapped in `<a>` tags before insertion for clickable hyperlinks
- LinkedIn: always check Connect before Message to avoid InMail
- Rate limits: 40 emails/day per inbox, 30 LinkedIn/day, 150 LinkedIn/week

---

## STEP 6 — Log to Outreach Tracker

**Read `references/tracker-logging.md` for the full tracker logging procedure.**

That file contains: two-phase write pattern (idempotent sending), tracker schema
(23 columns), follow-up cadence calculation, atomic file operations, and session
resume with pending send recovery.

**Key points (summary, detail in reference):**
- Use two-phase write: Pending before send, Sent after success
- Log immediately after each send, never batch at end
- Tracker at `~/.claude/gtm-stack/outreach-tracker.csv`
- Follow-up: 3 business days for Strong Fit, 5 for Moderate Fit

---

## STEP 7 — Progress Updates

Show after every 5 leads:
```
Progress: 12/28 leads contacted (~8 min remaining)
📧 Emails sent: 10   💬 LinkedIn DMs sent: 8
⏭ Skipped: 2   ❌ Failed: 0
```

---

## STEP 8 — Final Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ OUTREACH COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Leads processed:     [N]
  📧 Emails sent:    [N] via [detected provider]
  💬 LinkedIn DMs:   [N]
  ⏭ Skipped:        [N]
  ❌ Failed:         [N]

Follow-ups due:      [earliest date] — [latest date]

Next steps:
  • Run "/gtm-outbound-messenger" again in 5 days to check follow-ups
  • Run "/gtm-pipeline" to find + score + contact more leads
  • Say "show dashboard" any time for the interactive view
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Always end with the deliverables block:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Outreach tracker:  ~/.claude/gtm-stack/outreach-tracker.csv
                     Total contacts (all time): [N] | This session: [N]

  Pipeline view:     Available in the Flywheel app at /pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Pipeline data is automatically persisted via Flywheel MCP tools.** No manual merge or dashboard generation needed — the pipeline view in the Flywheel app reflects the latest outreach data.

The founder should never have to ask for the dashboard — it's always up to date.

---

## FOLLOW-UP MODE

When the user says "check follow-ups", "who needs a follow-up", or "outreach status":

### Load tracker and filter

```python
def get_pending_follow_ups(tracker_path):
    """Return leads where Follow_Up_Date <= today and Follow_Up_Status == Pending."""
    today = datetime.now().strftime('%Y-%m-%d')
    due = []
    with open(tracker_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('Follow_Up_Status') == 'Pending' and row.get('Follow_Up_Date', '9999') <= today:
                due.append(row)
    return due
```

### Show follow-up dashboard

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 FOLLOW-UPS DUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. [Company] — [Contact Name] — sent [Date] via [Channel]
     Original: "[First 80 chars of message]"
     → Send follow-up?  ✅ Yes  |  ⏭ Skip  |  ✔️ Already replied

  2. [Company] — ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For each "Yes": generate a short follow-up message, show preview, send on approval,
update tracker row: `Follow_Up_Status = Done`.

### Follow-Up Message Drafting Rules

Follow-ups are **more important than first touch** — the recipient already saw your name.
These rules ensure follow-ups feel natural, not automated.

**Email follow-up structure (3-4 sentences max):**
```
Subject: Re: [original subject line]

Hi [First Name],

[1 sentence: Reference the original email — "I sent a note last week about [topic]"]

[1 sentence: Add ONE new piece of value — a relevant stat, a case study result,
a question that shows you thought about their specific situation. Never just
"bumping this" or "circling back."]

[1 sentence: Lighter CTA than the original — "Happy to share more if useful"
or "No worries if the timing isn't right."]

[Sender name]
```

**LinkedIn follow-up (2 sentences max):**
```
Hi [First Name] — following up on my message about [topic].
[One new hook or softer CTA]. No pressure either way.
```

**Follow-up anti-patterns (never use):**
- "Just bumping this to the top of your inbox"
- "Circling back on my previous email"
- "Did you get a chance to read my last message?"
- "I know you're busy, but..."
- Sending the exact same message again
- Adding urgency that doesn't exist ("limited spots", "this week only")

**Follow-up personalization:** If the company has posted anything new since
the original outreach (blog post, LinkedIn update, job posting, press release),
reference it as the "new value" in the follow-up. This proves the follow-up
isn't automated.

For "Already replied": ask for the outcome:
```
What was the outcome?
  A) Replied - Interested (wants to learn more)
  B) Replied - Not Interested (passed for now)
  C) Replied - Using Competitor (has an existing solution)
  D) Meeting Booked (demo / call scheduled)
  E) Bounced (email didn't go through)
  F) Wrong Contact (person isn't the right DM)
```

Update tracker row: `Follow_Up_Status = Not Needed`, `Outcome = [selected value]`.

If outcome is "Replied - Not Interested" or "Replied - Using Competitor":
```
Add [Company] to Do Not Contact list? (y/n)
```
If yes, append to `~/.claude/gtm-stack/do-not-contact.csv`:
```
Company,Contact_Name,Contact_Email,Reason,Date_Added,Added_By
[Company],[Contact],[Email],[Outcome],[Today],[auto]
```

---

## DASHBOARD MODE

When user says "show dashboard", "outreach dashboard", "visualize outreach", or after
completing a send session, generate the full GTM Command Center dashboard.

### Generate the dashboard

Pipeline data is available in the Flywheel app pipeline view. Use `flywheel_list_leads` to check pipeline status programmatically.

---

## TRACKER REPORTING MODE

When user says "show my outreach tracker", "outreach stats", "who have I contacted":

```python
def tracker_summary(tracker_path):
    stats = {'total': 0, 'sent': 0, 'skipped': 0, 'failed': 0,
             'follow_up_pending': 0, 'channels': {}, 'tiers': {}}
    with open(tracker_path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            stats['total'] += 1
            status = row.get('Status', '')
            if status == 'Sent': stats['sent'] += 1
            elif status == 'Skipped': stats['skipped'] += 1
            elif status == 'Failed': stats['failed'] += 1
            if row.get('Follow_Up_Status') == 'Pending':
                stats['follow_up_pending'] += 1
            ch = row.get('Channel', 'unknown')
            stats['channels'][ch] = stats['channels'].get(ch, 0) + 1
            tier = row.get('Fit_Tier', 'unknown')
            stats['tiers'][tier] = stats['tiers'].get(tier, 0) + 1
    return stats
```

Display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 OUTREACH TRACKER — ALL TIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total contacts:     [N]
  Sent:             [N]
  Skipped:          [N]
  Failed:           [N]

By channel:
  Email:             [N] (via [detected provider])
  LinkedIn:          [N]

By tier:
  🔴 Strong Fit:           [N]
  🟡 Moderate Fit:          [N]

Follow-ups pending: [N]
Follow-ups due now: [N]

Tracker file: ~/.claude/gtm-stack/outreach-tracker.csv
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Edge Cases

| Situation | Handle as |
|-----------|-----------|
| No scored CSV provided | Search ~/Downloads for most recent `leads_scored_*.csv` or `*_scoring.csv`; ask user to confirm |
| CSV has no Fit_Score column | Check for Score, Rating, or Tier columns; ask user which column to use |
| No email address in CSV | Skip email channel for that lead; note in tracker |
| No LinkedIn URL in CSV | Search LinkedIn for "[Name] [Company]" via browser; if found use it, if not skip |
| Lead already contacted on email but not LinkedIn | Send LinkedIn only; log as new row with channel=linkedin |
| LinkedIn lead is not a 1st-degree connection | Auto-detect: Connect button visible → send Connection Request. NEVER send InMail (Message to non-connection) unless user explicitly asks |
| LinkedIn shows BOTH Message AND Connect buttons | They are NOT a 1st-degree connection. Message = InMail (costs credits). ALWAYS choose Connect. |
| LinkedIn InMail compose: Submit button disabled | InMail REQUIRES a Subject line. Fill Subject field first. But you should not be here unless user asked for InMail. |
| LinkedIn Connect button only in primary position (not in More menu) | Check for primary Connect `<A>` tag FIRST (aria-label="Invite [Name] to connect"), before checking More menu |
| LinkedIn requires email verification to connect | If lead's email is available, fill it in; otherwise skip and log as Failed with reason |
| LinkedIn weekly invitation limit reached | Stop all connection requests, log remaining as Queued, tell user to wait ~1 week |
| Gmail email body is blank after compose | NEVER use `&body=` in Gmail compose URL — fill body via browser_fill_form after compose loads |
| Email compose URL blocked/changed | Fall back to click-based compose (works for any provider) |
| LinkedIn CAPTCHA or restriction | Stop DMs immediately; log remaining as Queued; tell user to wait |
| Send button not found | Take screenshot; ask user to click Send manually; log status after |
| Session interrupted mid-send | All prior sends are already logged (as Pending→Sent); on resume, check for Pending rows and ask user to verify |
| Pending rows found on resume | Show list, ask user: mark as Sent / Failed / review each. Never auto-re-send. |
| LinkedIn daily limit reached | Skip all remaining LinkedIn DMs, mark as Queued, tell user to resume tomorrow |
| LinkedIn rate limit mid-session | Stop DMs immediately, log remaining as Queued, continue with email sends |
| User says "stop" mid-run | Save progress immediately; report what was sent vs. remaining |
| Email bounced (visible error) | Log as Failed with reason; move to next lead |
| Tracker file corrupted | Back up existing, create fresh, warn user |
| User asks to re-send to someone already contacted | Show tracker record, confirm they want to send again, log as new row with note "Re-send" |
| No sender profile and no templates | Build minimal outreach from CSV data alone; warn messages will be less personalized |
| Over 50 leads to contact | Suggest batching: "That's a lot — want to do Strong Fit leads first (N) and Moderate Fit leads tomorrow?" |

## Context Store Post-Write
After completing the main workflow, write discovered knowledge back to the context store:
- Target files: `contacts.md`, `objections.md`
- Entry format: `[YYYY-MM-DD | source: gtm-outbound-messenger | <detail>] confidence: <level> | evidence: 1`
- Write to `contacts.md`: outreach outcomes per contact (sent, replied, bounced, meeting booked)
- Write to `objections.md`: new objections heard in replies or during LinkedIn exchanges
- DEDUP CHECK: Before writing, scan target file for same source + detail + date. Skip if exists.
- Write failures are non-blocking: log error, continue.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-outbound-messenger.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Preferred tone and writing style for outreach messages
- Signature format and sign-off preferences
- Send time preferences (time of day, days of week)
- Rate limit overrides (custom daily/weekly caps)
- Channel preferences per source type
- Template selections that performed well

### What NOT to save
- Session-specific content, temporary overrides, confidential data

### Parallel Execution
Scale sending agents to batch volume. Max concurrency is rate-limited per channel.

| Items | Agents | Notes |
|-------|--------|-------|
| 1-5   | Sequential | Overhead not worth it |
| 6-15  | 2 | Max 2 LinkedIn tabs, 3 email tabs |
| 16-30 | 3 | Max 2 LinkedIn tabs, 3 email tabs |
| 31-50 | 4 | Max 2 LinkedIn tabs, 4 email tabs |
| 51+   | 5 (cap) | Max 2 LinkedIn tabs, 4 email tabs |

LinkedIn is always capped at 2 concurrent tabs regardless of batch size.

### Idempotency
- Before sending: check outreach tracker for existing entry with composite key (recipient + channel + date)
- If duplicate found: skip send, log "duplicate skipped"
- Re-running produces same output without double-sends
- The tracker CSV is written after each individual send (never batched)

### Backup Protocol
- Before overwriting outreach tracker CSV: create `.backup.YYYY-MM-DD`, keep last 3
- Back up files before overwriting where applicable

## Error Handling

- **Email send failure (compose page error, send button not found):** Log failure in tracker with `Status: Failed`, note the error, continue to next lead. Never lose the draft.
- **LinkedIn rate limit (CAPTCHA, restriction notice):** Stop LinkedIn sends immediately, switch to email-only for remaining leads. Log which leads were not sent LinkedIn DMs.
- **Browser session loss (tab crash, Playwright disconnect):** Save all progress to tracker CSV. Report last successful send. User can resume with `/gtm-outbound-messenger` -- tracker prevents double-sends.
- **Email address not found after search:** Mark lead as `Email: Not Found` in CSV. Still attempt LinkedIn connection request if that channel is selected.
- **Gmail overlay blocker (`div.aSs`):** Auto-hide with `el.style.display = 'none'`; if still blocked, take screenshot and report.
- Partial results: tracker is written after each individual send, never batched at end.
- Final report includes success/failure/skipped counts per channel (email and LinkedIn separately).

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-03-21 | Extracted STEP 5 (channel send methods) and STEP 6 (tracker logging) to references/ for progressive disclosure. SKILL.md reduced from 1414 to ~570 lines. Gmail bug fixes documented in reference (signature truncation, overlay blocker, clickable hyperlinks). |
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |

## Flywheel MCP Integration

When connected to the Flywheel MCP server, track sent messages in the GTM leads pipeline:

### After sending each message:
1. Call `flywheel_send_lead_message(lead_name, contact_email, channel="email|linkedin", step_number=<N>)`
2. This auto-advances the contact's pipeline stage to "sent"
3. If a reply is detected, the system auto-graduates the lead to an account

If Flywheel MCP is not connected, skip these steps silently and use local file output.
