---
name: company-fit-analyzer
enabled: false
description: >
  DEPRECATED -- Use `/gtm-company-fit-analyzer` instead. This skill is kept as a reference
  for its LinkedIn authenticated scrape (Phase 4.5) but all new scoring should use the GTM
  version which has parallel execution, cross-run dedup, atomic CSV writes, rate limiting,
  and outreach drafting.
compatibility: "Requires Playwright MCP server connected and active."
version: "1.0"
web_tier: 3
---

> **DEPRECATED:** This skill has been superseded by `/gtm-company-fit-analyzer` (85% feature
> overlap, GTM version adds parallel execution, dedup, atomic writes, outreach drafting).
> Use this only if you need the standalone LinkedIn authenticated scrape (Phase 4.5).

# Company Fit Analyzer Skill

Research and score companies as potential clients using deep web crawling + AI inference.
Generic and reusable — Claude builds a custom fit profile by interviewing the user first,
then applies it consistently across all companies.

---

## PHASE 0 — Check Playwright Tools

Before anything else, confirm Playwright MCP tools are available. Look for tools named like
`browser_navigate`, `playwright_navigate`, `browser_screenshot`, `browser_evaluate`, etc.
If none found, tell the user: "Playwright MCP doesn't appear to be connected. Please enable
it in your MCP settings and restart Claude Code."

---

## PHASE 1 — Build the Fit Profile (Do This Once Per Session)

Before scoring any company, Claude must understand what "good fit" means for this user.
If a profile already exists in this session, skip this phase and use it.

### Step 1a — Check if user has a saved profile

Ask:
> "Do you have a saved client profile you'd like to use, or should we build one now?
> (If you've used this skill before, you can just describe your business and I'll
> reconstruct it — or paste in a profile you saved earlier.)"

### Step 1b — Interview the user

Ask these questions **conversationally, all at once** — not one by one:

---
> **Before I start scoring, I need to understand your business and ideal client.
> Please answer these 4 questions:**
>
> 1. **What does your business do?** (1–2 sentences — what you sell and what problem it solves)
>
> 2. **Who is your ideal customer?** (Industry, company type, size, geography — be as
>    specific as you can. "Any company" is not helpful here.)
>
> 3. **What signals make a company a GREAT fit?** (Think about your best existing clients —
>    what do they have in common? What pain do they have that you solve?)
>
> 4. **What signals make a company a BAD fit or disqualify them?** (Too big, too small,
>    wrong industry, already using a competitor, etc.)
---

### Step 1c — Synthesize into a Fit Profile

From the user's answers, build a structured profile object. Show it to the user and ask
them to confirm or correct before proceeding.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FIT PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Business:       [What you sell + problem solved]
Target:         [Industry, company type, size, geography]

GOOD FIT SIGNALS (score up):
  • [Signal 1 — specific and observable]
  • [Signal 2]
  • [Signal 3]
  • [Signal 4]
  • [Signal 5]

BAD FIT / DISQUALIFIERS (score down or skip):
  • [Disqualifier 1]
  • [Disqualifier 2]
  • [Disqualifier 3]

INFERENCE NOTES:
  [Any signals that can't be read directly but must be inferred — note HOW to infer them]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Does this look right? Any corrections before I start?
```

**Important:** If the user mentions signals that aren't visible on websites (e.g. "they
struggle with X"), explicitly ask:
> "That signal won't be stated on their website — what INDIRECT signs would suggest a
> company has that problem? For example, company size, team structure, tools they use
> or don't use, hiring patterns, project types?"

This is critical — the fit profile must be grounded in things Claude can actually observe
or infer from public web presence.

### Step 1d — Save the Profile

Tell the user:
> "I'll use this profile for all companies in this session. You can also save it for
> future sessions — just copy the profile block above and paste it at the start of
> your next session."

---

## PHASE 2 — Determine Run Mode & Inputs

**Mode A — Single company** (one name or URL provided)
→ Deep research, full fit report in conversation

**Mode B — Batch** (CSV file provided, or list of names/URLs)
→ Loop through each, score all, append columns to CSV

For either mode, confirm:
- How many companies? (Batch: show estimated time — ~2–4 min per company for deep crawl)
- Resume a previous scoring run, or start fresh?
- Any companies to skip or prioritize?

---

## PHASE 3 — Discover Company Website (Critical Step)

For every company — whether a name or URL was provided — run this discovery process.

### If only a company NAME is provided (no URL):

**Step 1 — Web search:**
```
Search: "[Company Name] official website"
Search: "[Company Name] [City or State if known]"
```

Evaluate results carefully:
- ✅ Take: Company's own domain (companyname.com, companyname.co, etc.)
- ✅ Take: LinkedIn company page (useful even if we find the website)
- ❌ Skip: Directories (Yelp, BBB, Houzz, Clutch, Angi, Yellow Pages, Bloomberg)
- ❌ Skip: News articles about the company (not their site)
- ❌ Skip: Individual employee LinkedIn profiles

**Step 2 — Verify it's the right company:**
Navigate to the candidate URL. Take a screenshot. Confirm:
- Does the name match?
- Does the location/industry match what we know?
- Is it an active business website (not parked, not under construction)?

**Step 3 — If no website found:**
Search LinkedIn directly:
```
Search: "[Company Name] LinkedIn company page [City if known]"
```
LinkedIn-only companies still yield useful signals (employee count, posts, jobs).

**Step 4 — If still nothing found:**
Mark `Website = Not Found`, `LinkedIn = Not Found`, `Crawl_Status = No Web Presence`.
Score what can be inferred from the name alone (usually very little — be honest about this).

### If a URL IS provided:
Navigate directly. Verify it loads and is the right company. Then proceed to Phase 4.

---

## PHASE 4 — Deep Crawl

Visit pages in this order. At each page, extract signals relevant to the fit profile
built in Phase 1. Adapt what you're looking for based on the profile — not every signal
applies to every business type.

### Crawl Sequence

**1. Homepage**
- What do they do / how do they describe themselves?
- Tagline, headline, key value propositions
- Any technology, software, or platform mentions?
- Scale signals: years in business, number of clients, locations, project volume

**2. About / Our Story**
- Founding year and company age
- Team size and headcount
- Growth story: new offices, acquisitions, expanding markets
- Mission and values (signals culture and priorities)

**3. Services / What We Do**
- Exactly what they offer
- What they do themselves vs. coordinate/outsource
- Any language matching your fit profile signals

**4. Projects / Portfolio / Case Studies / Clients**
- Types and scale of work
- Recency — last project posted
- Volume — how many active projects simultaneously?
- Named clients (signals company size and market position)

**5. Team / Leadership**
- Total visible headcount
- Role breakdown (what kinds of people work there?)
- Leadership accessibility: named principals, founder-led?

**6. Careers / Jobs Page**
- What roles are they hiring for right now?
- Growth signal: how many open roles?
- Role types reveal operational structure
- Also check: LinkedIn Jobs, Indeed for this company

**7. Blog / News / Press**
- Last post date (activity signal)
- Topics they write about (reveals priorities and pain points)
- Growth announcements, new contracts, expansions

**8. Any page directly relevant to your fit signals**
- e.g. "Subcontractor" page, "Partners" page, "Vendor" page, "Technology" page
- Navigate directly if it exists in the menu or footer

**9. LinkedIn Company Page**
- Employee count (often most reliable headcount signal)
- Recent company posts (last 3) — tone, topics, activity
- Job postings — what departments are growing?
- Founded date, headquarters confirmation

**10. Targeted Google searches**
```
Search: "[Company Name] [key signal from fit profile]"
Search: "[Company Name] reviews"
Search: "[Company Name] [city] [industry]"
```
- Forum posts, reviews, news that reveal operational details
- Glassdoor reviews can reveal internal pain points

### Waiting for Dynamic Content
Many modern sites load content asynchronously (React/Vue/Angular). After navigating,
wait for content to stabilize before extracting:
```javascript
let prev = 0, stable = 0;
const start = Date.now();
while (stable < 3 && Date.now() - start < 10000) {
  const count = document.querySelectorAll('p, h1, h2, li').length;
  if (count > 0 && count === prev) stable++;
  else { stable = 0; prev = count; }
  await new Promise(r => setTimeout(r, 500));
}
```

---

## PHASE 4.5 — LinkedIn Enrichment (Authenticated Deep Scrape)

After the web crawl (Phase 4) and scoring (Phase 6) are complete, offer LinkedIn enrichment
for Hot and Warm leads. This phase uses the Playwright browser with the user's authenticated
LinkedIn session to extract high-value signals that aren't available from public web crawling.

**This phase is OPTIONAL** — only run it if:
- The user has Hot or Warm leads that would benefit from deeper validation
- The user agrees to log into LinkedIn in the Playwright browser
- In batch mode, only enrich Hot + Warm tier leads (never waste time on Cool/Pass)

### Step 4.5a — Offer LinkedIn Enrichment

After Phase 6 scoring is complete (or after a batch run finishes), present:

> **LinkedIn Enrichment Available**
>
> I found [X] Hot and [Y] Warm leads. I can enrich these with LinkedIn data to:
> - Verify employee counts and company size
> - Check active job postings (hiring = growth + pain signals)
> - Confirm the contact still works there and their current title
> - Read recent company posts for activity signals
>
> This requires you to log into LinkedIn in the browser. Want to proceed?
> (I'll only scrape your [X+Y] priority leads, not the full list.)

### Step 4.5b — LinkedIn Login

Launch the Playwright browser and navigate to LinkedIn:

```
Navigate to: https://www.linkedin.com/login
```

Then tell the user:

> **Please log into LinkedIn in the browser window.**
> I'll wait until you're on the LinkedIn feed, then I'll start researching.
> (Your credentials are never stored or visible to me — you're logging in directly.)

**Wait for login confirmation:** After the user says they've logged in (or you detect the
feed page), take a snapshot to verify you're on an authenticated LinkedIn page. Look for
elements like the navigation bar, feed content, or profile menu. If still on the login page,
ask the user to try again.

**Important:** Never attempt to type credentials. The user must log in manually.

### Step 4.5c — Build the Enrichment Queue

From the scored results, extract all Hot and Warm leads into a queue:

```
LINKEDIN ENRICHMENT QUEUE:
─────────────────────────────────────
Priority  | Company                | Contact Name        | Score | Existing LinkedIn URL
Hot       | Skanska USA Building   | James Gourley       | 92    | (from CSV or "none")
Hot       | Suffolk Construction   | Chris Kennedy       | 92    | linkedin.com/in/...
Warm      | Halff Associates       | Kristina Hernandez  | 72    | (none)
...
─────────────────────────────────────
Total: [N] companies to enrich
```

### Step 4.5d — Company LinkedIn Research

For each company in the queue, perform these searches IN ORDER:

**1. Find the Company Page**

If a LinkedIn company URL was found in Phase 3/4, navigate directly. Otherwise search:

```
Navigate to: https://www.linkedin.com/search/results/companies/?keywords=[Company Name]
```

Take a snapshot. Identify the correct company from results by matching:
- Company name (exact or close match)
- Location (city/state)
- Industry
- Employee count range (should be plausible given what we already know)

Click through to the company page.

**2. Extract Company Signals from the Company Page**

From the company's LinkedIn main page, extract:

```
LinkedIn Company Signals:
  Company LinkedIn URL:
  Tagline / Description:
  Employee count on LinkedIn:    (this is often the most reliable size metric)
  Headquarters:
  Industry (LinkedIn category):
  Founded:
  Company type:                  (Public, Private, Nonprofit, etc.)
  Followers:                     (engagement/brand signal)
  Associated companies:          (parent/subsidiary relationships)
```

**3. Check Job Postings**

Navigate to the company's Jobs tab:
```
Navigate to: https://www.linkedin.com/company/[company-slug]/jobs/
```

Or click the "Jobs" tab on the company page. Extract:

```
LinkedIn Jobs:
  Total open positions:
  Relevant roles found:          (list any roles matching fit signals — e.g. "Risk Manager",
                                  "Compliance Coordinator", "Insurance Analyst",
                                  "Subcontractor Manager", "Vendor Management")
  Growth departments:            (which teams are hiring most?)
  Seniority levels hiring:       (entry/mid/senior/exec)
```

**Fit-signal job keywords to watch for** (adapt to the fit profile):
- Any role titles containing words from the fit profile's good signals
- Roles suggesting manual processes that the user's product could automate
- Roles suggesting the company is building out the capability the user's product serves

**4. Check Recent Posts**

Navigate to the company's Posts tab:
```
Navigate to: https://www.linkedin.com/company/[company-slug]/posts/
```

Extract the 3 most recent posts:
```
Recent Posts:
  Post 1: [Date] — [Topic summary] — [Engagement: X likes, Y comments]
  Post 2: [Date] — [Topic summary] — [Engagement]
  Post 3: [Date] — [Topic summary] — [Engagement]
  Last post date:                (activity signal — stale = concern)
  Topics relevant to fit:        (any posts about pain points the user solves?)
```

### Step 4.5e — Contact Verification

For each contact person in the queue, verify they still work at the company.

**If the CSV already has a LinkedIn profile URL for the contact:**
```
Navigate to: [their LinkedIn URL]
```
Take a snapshot and extract:
- Current title (does it match the CSV?)
- Current company (still there?)
- Time in role
- Location

**If NO LinkedIn URL exists for the contact, search for them:**
```
Navigate to: https://www.linkedin.com/search/results/people/?keywords=[Person Name]&company=[Company ID]
```

Or use the search bar:
```
Search: "[Person Name] [Company Name]"
```

Filter the results. To improve accuracy, use any available filters:
- Current company filter (if company page was found)
- Location filter (from CSV data)
- School filter: if the source data includes university info (e.g. MIT alumni list),
  filter by school to narrow results

Take a snapshot and identify the correct person. Click through to their profile.

**Extract from the contact's profile:**
```
Contact Verification:
  LinkedIn URL:
  Current title:                 (match to CSV? Title may have changed)
  Current company:               (still at same company? CRITICAL — if they left, flag it)
  Time in current role:
  Location:
  Connections/followers:          (influence signal)
  Recent activity:               (active poster? Engaged professional?)
  Previous companies:            (relevant experience pattern?)
  Education:                     (confirms identity if matching alumni source)
  Open to:                       (if visible — "Open to work" = they may be leaving)
```

**Contact status classification:**
- **Verified** — Name + company match, profile is active
- **Title Changed** — Same company but different title than CSV (note the new title)
- **Company Changed** — They no longer work there (note where they went — and flag
  that the lead may need a new contact at the original company)
- **Not Found** — Could not find their LinkedIn profile
- **Ambiguous** — Multiple potential matches, couldn't confirm which is correct

### Step 4.5f — Score Adjustment (Optional)

After LinkedIn enrichment, check if any scores should be adjusted:

- **Score UP** if LinkedIn revealed:
  - Larger employee count than estimated
  - Job postings matching fit signals (e.g. hiring compliance roles)
  - Recent posts about pain points the user's product solves
  - Active engagement and growth signals

- **Score DOWN** if LinkedIn revealed:
  - Much smaller than estimated (employee count way off)
  - Contact no longer at the company
  - Company appears stagnant (no posts, no hiring, low follower count)
  - Industry/focus different from what the website suggested

- **Flag for user attention** if:
  - Contact moved to a DIFFERENT company that might also be a fit
  - Job posting directly describes the problem the user's product solves
  - Company is hiring for the exact role that would buy the user's product

Update the Fit_Score and Fit_Tier in the CSV if adjustments are warranted.
Note the adjustment reason in the Fit_Reasoning field (append, don't overwrite).

### Step 4.5g — Append LinkedIn Columns to CSV

Add these new columns to the CSV for enriched rows:

| Column | Description |
|--------|-------------|
| `LinkedIn_Company_URL` | Company's LinkedIn page URL |
| `LinkedIn_Employees` | Employee count from LinkedIn |
| `LinkedIn_Followers` | Company follower count |
| `LinkedIn_Open_Jobs` | Number of open positions |
| `LinkedIn_Relevant_Jobs` | Job titles matching fit signals (semicolon-separated) |
| `LinkedIn_Last_Post` | Date of most recent company post |
| `LinkedIn_Contact_URL` | Contact person's LinkedIn profile URL |
| `LinkedIn_Contact_Title` | Their current title on LinkedIn |
| `LinkedIn_Contact_Status` | Verified / Title Changed / Company Changed / Not Found |
| `LinkedIn_Enrichment_Notes` | Key findings, score adjustments, flags |

For rows that were NOT enriched (Cool/Pass), leave these columns blank.

### Step 4.5h — Rate Limiting & Anti-Detection

LinkedIn aggressively rate-limits automated access. Follow these rules:

- **Pace yourself:** Wait 3–5 seconds between page navigations. Never rapid-fire requests.
- **Vary the pattern:** Don't visit Company→Jobs→Posts→Contact in exact same order every time.
  Occasionally visit the contact first, or skip the posts tab.
- **Watch for CAPTCHA/blocks:** If LinkedIn shows a CAPTCHA, verification page, or
  "unusual activity" warning:
  1. Stop immediately
  2. Take a screenshot
  3. Tell the user: "LinkedIn is showing a verification check. Please complete it in the
     browser, then tell me when you're ready to continue."
  4. Wait for user confirmation before resuming
- **Session limits:** After ~25-30 profile views, LinkedIn may start restricting.
  If you notice profiles loading slowly or showing limited data:
  1. Tell the user how many leads remain
  2. Suggest pausing and resuming later (save progress to status file)
  3. Or ask if the remaining leads are worth the risk of a temporary restriction
- **Never:** Use LinkedIn search APIs, scraping tools, or automation libraries beyond
  what's visible in the normal browser session. This is a human-paced browsing session.

### Step 4.5i — Progress Tracking for LinkedIn Enrichment

Update the status file with LinkedIn enrichment progress:

```markdown
## LinkedIn Enrichment Progress
| # | Company | Contact | Company Page | Jobs | Posts | Contact Verified | Status |
|---|---------|---------|-------------|------|-------|-----------------|--------|
| 1 | Skanska | J. Gourley | Found (7200 emp) | 45 open | Active | Verified | Done |
| 2 | Suffolk | C. Kennedy | Found (3800 emp) | 28 open | Active | Title Changed | Done |
| 3 | Halff   | K. Hernandez | Found (1200 emp) | 12 open | Active | Pending | Next |

LinkedIn session started: [timestamp]
Leads enriched: 8/33
Rate limit status: OK
```

Show progress to the user every 5 leads:
```
LinkedIn Enrichment: 10/33 leads done
Verified: 7  |  Title Changed: 1  |  Company Changed: 1  |  Not Found: 1
Score adjustments: 2 upgraded, 1 downgraded
```

---

## PHASE 5 — Compile Signal Sheet

After crawling, organize findings into a structured signal sheet before scoring.
The exact fields depend on the fit profile, but always include:

```
COMPANY SIGNALS:
─────────────────────────────────────────
Basic Info:
  Name:
  Website:           (discovered or provided)
  LinkedIn:
  Location:
  Founded:
  Est. Employees:    (source: LinkedIn / Team page / About)
  Industry / Type:

What They Do:
  Core business description:
  [Any fields relevant to fit profile — e.g. "Self-perform or coordinate?",
   "Project types", "Client types", "Service delivery model"]

Fit Profile Signals Found:
  [For each GOOD FIT signal from the profile:]
  Signal: [name]    Found: Yes / No / Partial    Evidence: [quote or observation]

  [For each DISQUALIFIER from the profile:]
  Disqualifier: [name]    Found: Yes / No / Unclear

Tech & Tools:
  Software/platforms mentioned:
  Appears tech-forward or manual?:

Activity & Growth:
  Last content update:
  Hiring activity:       (Yes/No — what roles?)
  Growth signals:
  Red flags:

Decision Maker:
  Named leadership?:
  Founder-led?:
  Approachable / accessible?:
─────────────────────────────────────────
```

---

## PHASE 6 — Score Against the Fit Profile

### Dynamic Scoring Framework

Because the fit profile varies by user, scoring must be adapted dynamically.
Use this framework every time:

**Step 1 — Identify the 4–5 most important dimensions** from the fit profile.
These should be the signals the user said matter most.

**Step 2 — Assign point weights** that add to 100. Suggested distribution:
- Most critical dimension: 25–30 points
- Second most important: 20–25 points
- Supporting dimensions: 10–15 points each
- Decision maker access: always include, 10 points

**Step 3 — Score each dimension** based on evidence found in the signal sheet.
Be explicit: cite specific evidence for each score, not just a number.

**Step 4 — Check for instant disqualifiers.** If any hard disqualifier from the
profile is confirmed → cap the score at 20 regardless of other signals.

**Example scoring table (adapt dimensions to the actual fit profile):**

| Dimension | Max | Score | Evidence |
|-----------|-----|-------|----------|
| [Primary fit signal] | 30 | X | [what was found] |
| [Secondary fit signal] | 25 | X | [what was found] |
| [Supporting signal] | 15 | X | [what was found] |
| [Size / stage fit] | 20 | X | [what was found] |
| Decision maker access | 10 | X | [what was found] |
| **Total** | **100** | **X** | |

### Priority Tiers (Universal)
- 🔴 **Hot (75–100):** Strong fit across most dimensions. Reach out this week.
- 🟡 **Warm (50–74):** Good signals but gaps remain. Worth pursuing with more research.
- 🔵 **Cool (25–49):** Marginal fit. Low priority unless pipeline is thin.
- ⚫ **Pass (<25):** Not a fit, or hard disqualifier confirmed.

---

## PHASE 7 — Write Fit Reasoning

Write 3–4 sentences. Be specific — reference actual things found during the crawl.
Never write generic statements. Always explain the inference chain when a signal
was indirect.

**Structure to follow:**
1. What kind of company they are + key size/scale fact
2. The strongest fit signal found (and where you found it)
3. The strongest concern or gap (and what it means)
4. Overall recommendation

**Good example:**
> "Meridian Construction is a 45-person GC in Boston running 8 simultaneous commercial
> projects — their team page shows 6 PMs and no field trade staff, confirming they
> coordinate subs rather than self-perform. No software tools are mentioned anywhere on
> the site, and they're currently hiring two new PMs on LinkedIn, suggesting their manual
> admin process is already under strain. Could not find a vendor or subcontractor page,
> so COI process is unknown — but everything else points to a live compliance pain."

**Bad example — never write this:**
> "This company appears to be a good potential client based on their services."

---

## PHASE 8 — Output

### Single Company Mode

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 COMPANY FIT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Company:     [Name]
Website:     [URL — discovered or provided]
LinkedIn:    [URL if found]
Location:    [City, State]
Size:        [Est. employees + source]

FIT SCORE:   [X] / 100   [Tier emoji + label]

REASONING:
[3–4 sentence specific reasoning from Phase 7]

SIGNALS FOUND:
[List each good fit signal: ✅ if found, ⚠️ if partial, ❌ if not found]

DISQUALIFIERS CHECKED:
[List each disqualifier: ✅ Not present, ⚠️ Unclear, 🚫 Confirmed]

SCORING BREAKDOWN:
[Dimension table from Phase 6]

PAGES CRAWLED:
[List pages visited + status]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Batch CSV Mode

Append these columns to the existing CSV without modifying any existing data:

| Column | Description |
|--------|-------------|
| `Website_Found` | URL discovered (or "Not Found") |
| `Fit_Score` | 0–100 |
| `Fit_Tier` | Hot / Warm / Cool / Pass |
| `Fit_Reasoning` | 3–4 sentence specific explanation |
| `Top_Fit_Signal` | The single strongest signal found |
| `Top_Concern` | The single biggest gap or risk |
| `Est_Employees` | Number or range + source |
| `Decision_Maker_Named` | Yes / No |
| `Crawl_Status` | Complete / Partial / No Website / Login Required |
| `LinkedIn_Company_URL` | Company LinkedIn page (from Phase 4.5, Hot/Warm only) |
| `LinkedIn_Employees` | Employee count from LinkedIn |
| `LinkedIn_Open_Jobs` | Number of open positions |
| `LinkedIn_Relevant_Jobs` | Job titles matching fit signals |
| `LinkedIn_Contact_URL` | Contact's LinkedIn profile URL |
| `LinkedIn_Contact_Title` | Current title per LinkedIn |
| `LinkedIn_Contact_Status` | Verified / Title Changed / Company Changed / Not Found |

```python
import csv

def append_fit_scores(filepath, results):
    with open(filepath, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        existing_fields = list(rows[0].keys()) if rows else []

    new_fields = ['Website_Found', 'Fit_Score', 'Fit_Tier', 'Fit_Reasoning',
                  'Top_Fit_Signal', 'Top_Concern', 'Est_Employees',
                  'Decision_Maker_Named', 'Crawl_Status']
    all_fields = existing_fields + [f for f in new_fields if f not in existing_fields]

    results_by_name = {r['name'].lower(): r for r in results}
    for row in rows:
        key = row.get('Name', row.get('Company', '')).lower()
        match = results_by_name.get(key)
        if match:
            row.update(match)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, quoting=csv.QUOTE_ALL,
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
```

---

## PHASE 9 — Batch Progress & Resume

After each company, update `<csv_name>_fit_status.md`:

```markdown
# Fit Analysis Status

## Profile Used
[Paste the fit profile summary here so sessions are reproducible]

## Progress
| # | Company | Website Found | Score | Tier | Status |
|---|---------|--------------|-------|------|--------|
| 1 | Acme Corp | acmecorp.com | 84 | 🔴 Hot | ✅ Done |
| 2 | Smith Inc | Not Found | N/A | ⚫ Pass | ✅ Done |

## Resume Point
Last completed: Row 23 — Pacific Builders
Next up: Row 24 — Atlas Group
```

Show running tally every 5 companies:
```
Progress: 15/45 companies scored (~25 min remaining)
🔴 Hot: 4   🟡 Warm: 6   🔵 Cool: 3   ⚫ Pass: 2
```

### Resume Protocol
1. Read status file — find last completed row
2. Open CSV — skip rows where `Fit_Score` is already populated
3. Continue appending — never rewrite existing scored rows or headers

---

## PHASE 10 — Final Summary (Batch)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ FIT ANALYSIS COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Companies analyzed:   45
Websites found:       38 / 45  (7 had no web presence)
Time taken:           ~2.5 hours

RESULTS:
🔴 Hot  (75-100):  9   ← Reach out this week
🟡 Warm (50-74):  12   ← Qualify further
🔵 Cool (25-49):  14   ← Low priority
⚫ Pass (<25):    10   ← Not a fit

TOP 5 HOT LEADS:
1. [Company]  — 91/100  ([One-line reason])
2. [Company]  — 87/100  ([One-line reason])
3. [Company]  — 83/100  ([One-line reason])
4. [Company]  — 79/100  ([One-line reason])
5. [Company]  — 76/100  ([One-line reason])

Output CSV:    [path]
Status file:   [path]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

---

## Memory & Learned Preferences

This skill remembers fit profiles and scoring patterns across sessions.

**Memory file:** Check the auto-memory directory for `company-fit-analyzer.md`:
```bash
cat "$(find ~/.claude/projects -name 'company-fit-analyzer.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

### Loading preferences (at session start)

Before Phase 1 (Build Fit Profile), check for saved preferences. If found, load:

```
Learned preferences loaded:
├─ Saved fit profile: [e.g. "Lumif.ai — construction risk compliance"]
├─ Scoring corrections: [e.g. "user adjusted weight of size signal to 25%"]
├─ Crawl preferences: [e.g. "always check LinkedIn jobs tab"]
└─ Output preferences: [e.g. "include LinkedIn enrichment for Hot leads"]
```

If a saved fit profile exists and matches the user's current business, offer to reuse it — skip Phase 1 interview entirely.

### What to save after each run

- **Fit profile** — the complete profile built in Phase 1 (so it can be reloaded)
- **Scoring dimension weights** — if user adjusted weights, save the final weights
- **Scoring corrections** — if user disagreed with a score, save the correction rule
- **Crawl preferences** — which pages the user finds most valuable, skip preferences
- **LinkedIn enrichment preferences** — always/never/ask, rate limit experience
- **Output format** — CSV path preferences, which columns matter most
- **Industry-specific signals** — new fit signals discovered during runs

Use the Edit tool to update existing entries — never duplicate. Save to `~/.claude/projects/-Users-sharan-Projects/memory/company-fit-analyzer.md`.

### What NOT to save

- Individual company scores (those live in the CSV)
- Session-specific company lists
- Temporary profile overrides

---

## EDGE CASES

| Situation | How to Handle |
|-----------|--------------|
| Name only, no URL | Run Phase 3 URL discovery before anything else |
| Multiple companies with same name | Search with city/state qualifier, show user options to confirm |
| Website found but wrong company | Try adding city/state to search, or ask user to confirm |
| No website AND no LinkedIn | Mark `No Web Presence`, score = N/A, note in CSV |
| Login wall on company site | Extract what's visible, note `Crawl_Status = Login Required` |
| Site is parked / under construction | Mark `Partial`, extract from LinkedIn only |
| Timeout / very slow site | Wait 15s max, screenshot what loaded, mark `Partial` |
| Obvious enterprise (500+ employees) | Fast-pass if profile says enterprise = disqualifier |
| User's fit profile is vague | Push back — ask for 2–3 specific observable signals before starting |
| User skips profile setup ("just score them") | Do a minimal 2-question version: "What do you sell?" and "Who's your ideal customer?" — enough to score meaningfully |
| LinkedIn CAPTCHA or verification | Stop, screenshot, ask user to complete manually, then resume |
| LinkedIn rate limit / restricted | Save progress, tell user how many remain, offer to resume later |
| Contact left the company | Flag it, note where they went (could be a new lead), suggest finding replacement contact at original company |
| Multiple LinkedIn profiles match | Use location + company + education filters to disambiguate; if still unclear, show options to user |
| Company has no LinkedIn page | Note in CSV, skip LinkedIn enrichment for that company, rely on web crawl data only |
| LinkedIn shows "Premium only" data | Extract what's visible, note limitation, don't attempt workarounds |
| User declines LinkedIn enrichment | Skip Phase 4.5 entirely, proceed with web-only scores |

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
