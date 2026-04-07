# Channel-Specific Send Methods

Reference for STEP 5 of the outbound messenger pipeline. Read this file when
you reach STEP 5 during message sending.

---

## STEP 5 — Send Messages

### Parallel Channel Execution (Email + LinkedIn simultaneously)

When both email and LinkedIn channels are selected, run them **in parallel** using
separate browser tabs. Email and LinkedIn are independent channels with no dependencies
between them, so there is no reason to serialize.

**How it works:**
- **Tab group 1 (email):** Uses dynamic batch sizing (1-4 tabs) to compose and send emails
- **Tab group 2 (LinkedIn):** Uses a dedicated tab for connection requests/DMs (sequential within LinkedIn due to rate limits)
- Both channel groups run concurrently. While an email is being composed in one tab,
  a LinkedIn connection request can be sent in another tab.
- Each channel tracks its own rate limits independently (email: 40/day, LinkedIn: 30/day, 150/week)
- Both channels log to the same outreach tracker (file-level locking prevents conflicts)

**Preview modes with parallel channels:**
- **Preview Each (Mode A):** Show email + LinkedIn drafts together per lead, approve both,
  then send both channels simultaneously for that lead before moving to the next
- **Batch Preview (Mode B):** Draft all messages for all channels first, show batch,
  then on approval send all emails in parallel tabs while simultaneously sending LinkedIn
- **Auto-Send (Mode C):** Send email and LinkedIn for each lead concurrently, no preview

### Sending Mode: Preview Each (Mode A — default)

For each lead:
1. Show the personalized message preview (from STEP 4)
2. Wait for user choice: Send / Edit / Skip
3. If **Edit:** ask what to change, regenerate, re-show
4. If **Send:** execute the send for each channel (see channel-specific steps below)
5. If **Skip:** log as "Skipped" in tracker, move to next lead
6. After send: log to outreach tracker immediately

### Sending Mode: Batch Preview (Mode B)

1. Generate ALL messages first → show as a numbered list
2. Ask user: "Approve all, or list numbers to edit/skip?"
3. Apply edits → re-show changed ones
4. On final approval → send all approved in sequence
5. Log each to tracker as sent

### Sending Mode: Auto-Send (Mode C)

1. Generate + send without preview
2. Show brief confirmation after each: `✅ [Company] — email sent, LinkedIn DM sent`
3. Log each to tracker
4. Show running tally every 5 leads

### Channel-Specific Send Steps

#### Email — Parallel Send (Gmail, Outlook, Zoho, or any browser-based email)

**Pre-send email rate limit check (run once before the email send loop):**

```python
from gtm_utils import check_email_rate, increment_email_rate

count_today, remaining, over_limit = check_email_rate()
if over_limit:
    print(f"⚠ Email daily limit reached ({count_today} emails sent today from this inbox).")
    print("Sending more than 40 emails/day per inbox risks spam filters and lowers sender trust score.")
    print("Skip email sends for now — resume tomorrow, or switch to a different inbox.")
    # Skip all email sends, mark as Queued
elif remaining < len(email_leads):
    print(f"⚠ Only {remaining} emails remaining today ({count_today} already sent from this inbox).")
    print(f"Recommendation: Send {remaining} emails today, queue the rest for tomorrow.")
    print("Exceeding 40 emails/day per inbox can trigger spam filters and damage deliverability.")
    # Ask user: send {remaining} now and queue rest, or send all (at their risk)?
```

**After each successful email send**, call `increment_email_rate()` to track the
daily count persistently across sessions.

**Dynamic batch sizing:** The number of parallel tabs adapts to the workload.

```
BATCH SIZE RULES:
  1–5 emails    → batch_size = 1  (sequential, not worth the tab overhead)
  6–15 emails   → batch_size = 2  (2 tabs)
  16–50 emails  → batch_size = 3  (3 tabs, the sweet spot)
  51+ emails    → batch_size = 4  (4 tabs max — more causes tab-switching overhead)
```

**Provider-agnostic parallel strategy:**

All browser-based email providers (Gmail, Outlook, Zoho, Yahoo, ProtonMail,
FastMail, or any webmail) support the same parallel pattern:

```
PARALLEL EMAIL COMPOSE — [batch_size] tabs

Batch 1:
  Tab 1: Open compose for Lead A → draft/preview
  Tab 2: Open compose for Lead B → draft/preview
  Tab 3: Open compose for Lead C → draft/preview
    → User reviews all [batch_size] previews at once
    → Send approved ones, skip/edit others

Batch 2:
  Rotate tabs to next [batch_size] leads
  → Continue until all emails are sent
```

**Per-provider compose method:**

| Provider | Fast compose method | Body fill method | Fallback |
|----------|-------------------|-----------------|----------|
| Gmail | Compose URL: `https://mail.google.com/mail/?view=cm&fs=1&to={EMAIL}&su={SUBJECT}&tf=cm` (NO `&body=`) | After compose loads: use `browser_fill_form` on the contenteditable body area (`[aria-label="Message Body"]` or `div[role="textbox"]`). If fill_form doesn't work, use `browser_type` to type into the focused body area. | Click Compose button → fill all fields via form_input |
| Outlook | `https://outlook.live.com/mail/0/deeplink/compose?to={EMAIL}&subject={SUBJECT}&body={BODY}` | Body in URL works for Outlook | Click "New mail" → fill fields |
| Outlook 365 | `https://outlook.office.com/mail/deeplink/compose?to={EMAIL}&subject={SUBJECT}&body={BODY}` | Body in URL works for Outlook 365 | Click "New mail" → fill fields |
| Zoho | No compose URL — click "New Mail" → fill To/Subject/Body | Fill via form_input | Same |
| Yahoo | `https://compose.mail.yahoo.com/?to={EMAIL}&subject={SUBJECT}&body={BODY}` | Body in URL works for Yahoo | Click Compose → fill fields |
| ProtonMail | No compose URL — click "New message" → fill fields | Fill via form_input | Same |
| Any other | Click compose/new button → fill To/Subject/Body using form_input | Fill via form_input | Same |

**URL-encode** all parameters in compose URLs. Use `encodeURIComponent()` for
subject fields. Special characters in email addresses should be percent-encoded.

**CRITICAL — Gmail body fill procedure (prevents blank emails + ensures clickable links):**

Gmail's compose URL silently drops the `&body=` parameter. After navigating to the
compose URL, the compose window opens with To and Subject pre-filled but Body empty.
You MUST fill the body separately, and you MUST use HTML insertion so that URLs
render as clickable hyperlinks (not plain text).

```
GMAIL BODY FILL — Step by step:
1. Navigate to: https://mail.google.com/mail/?view=cm&fs=1&to={EMAIL}&su={SUBJECT}&tf=cm
2. Wait for compose window to load (~2 seconds)
3. Take a snapshot to find the body area element ref
4. Look for the contenteditable body div — it will appear as one of:
   - A textbox with aria-label containing "Message Body" or "Body"
   - A generic contenteditable div inside the compose area
   - The element after the Subject field in the compose form
5. Click on the body area to focus it
6. Select all existing content (Meta+a) to clear Gmail's default signature
7. CONVERT THE BODY TEXT TO HTML before insertion:
   - Replace newlines with <br> tags
   - Wrap any URL (https://... or http://...) in an <a> tag:
     https://example.com  -->  <a href="https://example.com">https://example.com</a>
   - This is CRITICAL for calendar links, website URLs, and any other
     links in the email — without this, they paste as plain text and
     recipients cannot click them
8. Insert the HTML body using browser_evaluate:
   ```javascript
   // Find the focused contenteditable body div and set innerHTML
   const body = document.querySelector('[aria-label="Message Body"], div[role="textbox"][aria-multiline="true"]');
   if (body) {
     body.focus();
     document.execCommand('selectAll');
     document.execCommand('insertHTML', false, HTML_BODY_STRING);
   }
   ```
   Where HTML_BODY_STRING is the converted HTML from step 7.
9. Take a snapshot to VERIFY:
   a. The body text is visible in the compose window
   b. URLs appear as clickable hyperlinks (blue/underlined), not plain text
   c. The signature block is present (name + title + company)
   The body text MUST be the EXACT full draft shown to the user during
   preview, including the signature block. Do not truncate, summarize,
   or omit the closing lines.
10. If signature is missing or links are plain text, re-insert using step 8.
11. Only click Send after confirming body, signature, AND hyperlinks are correct.

NEVER skip the verification step — if body is empty, signature is missing,
or links are not clickable, try the alternative fill method before sending.
```

**URL-to-hyperlink conversion function (use before insertion):**

```python
import re

def text_to_html_email_body(text):
    """Convert plain text email body to HTML with clickable hyperlinks."""
    # Escape HTML entities first
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Convert URLs to <a> tags (must run after HTML escaping)
    url_pattern = r'(https?://[^\s<>&]+)'
    text = re.sub(url_pattern, r'<a href="\1">\1</a>', text)
    # Convert newlines to <br>
    text = text.replace('\n', '<br>')
    return text
```

**This URL-to-hyperlink conversion applies to ALL email providers, not just Gmail.**
For Outlook compose URLs that use `&body=`, URLs are also rendered as plain text.
Use the same HTML insertion approach via browser_evaluate after the compose window loads.

**Parallel implementation (applies to ALL providers):**

1. Detect which email provider the user is logged into (from STEP 3 auth)
2. Calculate `batch_size` based on total email count (see rules above)
3. For each batch:
   a. Open `batch_size` compose windows:
      - If provider has compose URL → open URL in each tab
      - If no compose URL → in each tab: click compose, fill fields with form_input
   b. Take screenshot of each tab to verify fields are populated
   c. **Preview Each mode:** Show all previews to user, wait for approval
   d. **Auto-send mode:** Click Send on each tab with 2-second delay between tabs
   e. **Batch Preview mode:** Collect all previews first, show batch, then send approved
   f. Log each to tracker using pending→sent pattern (STEP 6)
   g. Rotate tabs to next batch

**Send button detection (per provider):**
- Gmail: `[aria-label*="Send"]` or `div[data-tooltip="Send"]`
- Outlook: `[aria-label="Send"]` or button containing "Send" text
- Zoho: `[data-action="send"]` or button containing "Send"
- Generic fallback: Find button with text "Send" or aria-label containing "Send"
- Always take a confirmation screenshot after clicking Send

**Estimated speedup by batch size:**
| Emails | Batch size | Sequential | Parallel | Speedup |
|--------|-----------|-----------|----------|---------|
| 5      | 1         | ~5 min    | ~5 min   | 1x      |
| 15     | 2         | ~15 min   | ~8 min   | ~2x     |
| 30     | 3         | ~30 min   | ~11 min  | ~3x     |
| 60     | 4         | ~60 min   | ~16 min  | ~4x     |

#### LinkedIn DM — Send via Profile

**Pre-send rate limit check (run once before the LinkedIn DM loop):**

```python
from gtm_utils import check_linkedin_rate, increment_linkedin_rate

count_today, remaining_today, over_daily, count_week, remaining_week, over_weekly = check_linkedin_rate()
if over_weekly:
    print(f"⚠ LinkedIn WEEKLY limit reached ({count_week}/150 this week).")
    print("LinkedIn caps connection requests at ~150/week. Wait until next week to resume.")
    # Skip all LinkedIn sends, mark as Queued
elif over_daily:
    print(f"⚠ LinkedIn daily limit reached ({count_today}/30 today, {count_week}/150 this week).")
    print("Skip LinkedIn for now — resume tomorrow.")
    # Skip all LinkedIn sends, mark as Queued
else:
    effective_remaining = min(remaining_today, remaining_week)
    if effective_remaining < len(linkedin_leads):
        print(f"⚠ Only {effective_remaining} LinkedIn sends remaining (today: {remaining_today}, week: {remaining_week}).")
        print(f"Will send {effective_remaining} and queue the rest.")
```

**After each successful LinkedIn DM send**, call `increment_linkedin_rate()` to
track the daily count persistently across sessions.

1. Navigate to the contact's LinkedIn profile URL
   (use `DM_LinkedIn` column from CSV if available)
2. If no LinkedIn URL: search LinkedIn for "[Name] [Company]", select correct profile
3. **Take a snapshot and determine connection status BEFORE clicking anything.**

#### LinkedIn Connection Status Detection (2-step check)

After taking a snapshot of the profile, check these **two positions only**, in order:

**Position 1 — Primary action bar (check FIRST, always):**
The Connect button sits in the main action bar, right next to the Message/Follow
button, directly below the profile header. In the snapshot look for:
- `link "Invite [Name] to connect"` with href containing `/preload/custom-invite/`
- `button "Connect"`
- Any element with text "Connect" in the action bar area

**Position 2 — More menu (check ONLY if Position 1 found nothing):**
Click the "More actions" / 3-dots button, then scan the dropdown for "Connect".

**Based on what you find:**

| Found | Meaning | Action |
|-------|---------|--------|
| "Connect" (either position) | Not connected | Connection Request flow (below) |
| "Pending" | Already sent | Skip, log "Already Sent" |
| "Message" only (no Connect anywhere) | 1st-degree connection | DM flow (step 4) |
| "Follow" only | Restricted profile | Skip, log reason |

**Do NOT click More first. Do NOT click Message if Connect exists anywhere.**
Message on a non-connection = InMail (costs credits). Never send InMail unless
the user explicitly asks for it.

#### LinkedIn DM Flow (1st-degree connections only)

4. Click "Message" button on their profile
5. Wait for message compose box to appear
6. Type the DM text into the message input
7. Click Send button (or press Enter)
8. Take screenshot to verify "sent" state
9. Close the message window

**LinkedIn rate limiting:** Add 30-60 second delay between DMs.
If a CAPTCHA or restriction notice appears:
- Stop immediately
- Tell user: "LinkedIn is rate-limiting. Sent [N] DMs so far. Wait 1-2 hours."
- Log remaining leads as "Queued" in tracker

#### LinkedIn Connection Request Flow (non-connections)

**Connection Request flow — step by step:**

Once the 2-step detection (above) found a Connect button, extract the vanity
name from the profile URL (`url.split('/in/')[1].rstrip('/')`) and proceed:

```
LINKEDIN CONNECTION REQUEST — Reliable method

1. NAVIGATE DIRECTLY to the invite URL:
   https://www.linkedin.com/preload/custom-invite/?vanityName={VANITY_NAME}

   Do NOT click the Connect <A> tag via JavaScript — it fires but does
   NOT navigate. Always use browser_navigate to this URL directly.

2. WAIT for the "Add a note to your invitation?" dialog to appear
3. SNAPSHOT to get element refs for the dialog buttons

4. CLICK "Add a note" button
   (Do NOT click "Send without a note" — personalized notes get
   higher acceptance rates)

5. SNAPSHOT to get the textarea ref

6. FILL the textarea using browser_fill_form:
   - 300 character limit — verify count before submitting
   - Use the LinkedIn Connection Request text from the outreach drafts

7. SNAPSHOT to verify the note text is filled

8. CLICK "Send invitation" button
   - Use the snapshot ref, not text matching

9. VERIFY: The dialog closes and a success toast appears, or the
   page navigates away from the invite URL

EDGE CASES:
- "Email verification required" dialog: LinkedIn sometimes asks you to
  enter the recipient's email address to verify you know them. If this
  appears:
  - If you have the lead's email → fill it in and proceed
  - If you don't have their email → click Cancel, skip this lead,
    log as "Failed" with reason "Email verification required"

- "Weekly invitation limit reached": Stop all connection requests
  immediately. Log remaining as "Queued". Tell user to wait ~1 week.

- Profile not found / 404: Log as "Failed" with reason "Profile not found"
```

**Tracker logging for connection requests:**
- `Channel`: "LinkedIn" (same as DMs)
- `LinkedIn_DM`: Store the connection request note text
- `Notes`: Include "Connection request with note" to distinguish from DMs
- `Status`: "Sent" on success, "Failed" with reason on failure

---
