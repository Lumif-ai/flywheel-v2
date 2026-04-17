---
public: true
name: gtm-company-fit-analyzer
description: >
  [GTM Stack — parallel execution, data integrity, backup.] Use this skill to research companies and score them as potential clients, partners, or
  targets. Trigger whenever the user wants to qualify leads, evaluate a company, score a
  list, research prospects, or asks things like "is this a good fit", "research these leads",
  "score my CSV", "which companies should I prioritize", or "check if these companies need
  our services". Accepts company names, URLs, or a CSV file. Works for ANY business type —
  Claude interviews the user to build a fit profile before scoring. Uses Playwright MCP to
  discover company websites, deep-crawl them, and infer fit from indirect signals.

  Requires: Playwright MCP server connected.
compatibility: "Requires Playwright MCP server connected and active."
version: "1.0"
triggers:
  - "score these companies"
  - "is this a good fit"
  - "research these leads"
  - "score my CSV"
  - "which companies should I prioritize"
  - "qualify these leads"
tags:
  - gtm
  - fit-analysis
context-aware: true
web_tier: 3
---

# Company Fit Analyzer Skill

Research and score companies as potential clients using deep web crawling + AI inference.
Generic and reusable — builds a custom fit profile by interviewing the user first,
then applies it consistently across all companies. Outputs fit score, reasoning,
decision maker LinkedIn profile, and personalized outreach (email + LinkedIn DM)
for every Strong Fit and Moderate Fit company.

---

## How to Use

### Direct invocation
In Claude Code, type:
```
/gtm-company-fit-analyzer
```
Or describe what you want — Claude will trigger this skill automatically.

### Natural language triggers
- *"Score these companies for fit against my profile"*
- *"Is [Company Name] a good prospect for us?"*
- *"Research these leads and tell me which ones to prioritize"*
- *"Score my CSV of companies"*
- *"Which of these companies needs what we sell?"*

### What you'll need
- A list of company names, URLs, or a CSV file
- A description of your business and ideal customer (Claude will ask)
- An outreach template or talking points (optional — Claude can write from scratch)

> **Have a directory to scrape first?** Use `/gtm-pipeline` instead —
> it scrapes the site and feeds the results directly into this scorer.

---

## STEP 0 — Check Playwright Tools

Confirm Playwright MCP tools are available (`browser_navigate` / `playwright_navigate` etc).
If none found: "Playwright MCP isn't connected — please enable it and restart Claude Code."

### 0b. Input Validation
- Verify: at least one company name, URL, or CSV file path provided before starting.
- Verify: if CSV provided, file exists and has a recognizable company column (Company, Employer, Organization).
- For batches >50 companies: confirm scope and estimated time with user before proceeding.

### Parallel Execution
Scale browser tabs to batch volume. Use parallel agents for large batches.

| Items | Agents | Notes |
|-------|--------|-------|
| 1-5   | Sequential | Overhead not worth it |
| 6-15  | 2 | -- |
| 16-30 | 3 | -- |
| 31-50 | 4 | -- |
| 51+   | 5 (cap) | Avoid rate limits |

Sub-phase batch sizing (quick filter, deep crawl, DM lookup) is defined in STEPs 4-9.5.

### Checkpoint Protocol
- Save to `<output-dir>/fit_analysis_status.md` every 10 items
- At startup: check for existing status file, offer resume
- Include: items completed, items remaining, partial results path, fit profile

### Context Management
- Compress working context every 10 items (discard raw crawl text, keep scored summaries)
- Hard checkpoint every 20 items: save all state to disk (CSV + status file)

### Backup Protocol
- Before overwriting scored CSV: create `.backup.YYYY-MM-DD`, keep last 3
- Back up files before overwriting where applicable

### 0c. Context Store Pre-Read
- Read `~/.claude/context/_catalog.md` to discover available files
- Load: `icp-profiles.md`, `positioning.md`, `pain-points.md`, `competitive-intel.md`
- Cap: max 10 recent entries per file
- Show what was loaded: "Loaded X entries from Y context files"
- Use ICP profiles to pre-populate fit scoring dimensions and weights
- Use positioning to inform outreach message drafting for Strong/Moderate Fit companies
- Use pain points to identify which signals to prioritize during deep crawl
- Use competitive intel to recognize competitor mentions on target company websites

---

## STEP 0.5 — Load Sender Profile

The sender profile captures who YOU are. Load it from the context store.

**Load via Flywheel MCP:**
Use `flywheel_read_context` to search for company-intel, positioning, and sender profile entries.

### If profile FOUND in context store — load silently and proceed:

Read the profile entries into memory. Show a single confirmation banner and
**skip STEP 1 entirely** — go directly to STEP 2 (collect outreach starting point):

```
✅ Company profile loaded: [Company Name]
   Sender: [Name, Title]
   ICP: [Industry] · [Type] · [Size] · [Geography]
   Fit signals: [Signal 1], [Signal 2]
   Disqualifiers: [Disqualifier 1], [Disqualifier 2]
```

Populate fit signals and disqualifiers from the profile context entries.
Pull sender name from the profile for use in outreach signing.

If the user says "actually I want to use different scoring context" at any point before
scoring begins → ask what to change, apply in memory for this session only.

### If profile NOT FOUND:

```
No company profile found in the context store.

I'll ask about your business below for this session and save it to the context store
for future sessions. Or you can provide a company profile document.

Continue with quick interview? (yes / no)
```

- **no:** Fall through to STEP 1 interview as normal.

---

## STEP 1 — Build the Fit Profile (once per session)

**Skip this step entirely if a profile was loaded in STEP 0.5.** Go straight to STEP 2.
If a profile was already built this session via interview, skip this step.

### 1a. Interview — ask all at once

> **I need to understand your business before scoring anything. Please answer:**
>
> 1. **Your name and title**
> 2. **What your business does** — what you sell, what problem it solves (2–3 sentences)
> 3. **Who is your ideal customer?** — industry, company type, size, geography
> 4. **What makes a company a GREAT fit?** — think about your best existing clients. What do they have in common? What pain do they share that you solve?
> 5. **What disqualifies a company?** — too big, wrong industry, already solved the problem, etc.

### 1b. Synthesize and confirm

Build a structured profile from the interview answers and show it for confirmation:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FIT PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sender:     [Name, Title]
Business:   [What you sell + problem solved]
Target:     [Industry, type, size, geography]

GOOD FIT SIGNALS:
  • [Signal 1 — specific and observable or inferable]
  • [Signal 2]
  • [Signal 3]
  • [Signal 4]

DISQUALIFIERS:
  • [Disqualifier 1]
  • [Disqualifier 2]

INFERENCE NOTES:
  [For any signal not visible on websites: HOW to infer it from proxy signals]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Does this look right? Any corrections?
```

**If any signal isn't observable on a website**, ask:
> "What indirect signs would suggest a company has that problem? (e.g. team size, hiring patterns, tech stack, project types)"

### 1c. Save reminder
Save the profile to the context store via `flywheel_write_context` (file: company-intel, source: gtm-company-fit-analyzer). Tell the user: "Profile saved to context store — it'll load automatically in every future session."

---

## STEP 2 — Collect Outreach Starting Point (once per session)

Ask this once before scoring any company:

> **For outreach messages (drafted for Strong Fit & Moderate Fit only), what's your starting point?**
>
> - **Option A:** Paste your existing email and/or LinkedIn template — I'll personalize each for every company
> - **Option B:** Share a rough draft or talking points — I'll refine and adapt per company
> - **Option C:** I'll write both from scratch using what I find during research
>
> Which option? (And if A or B, paste your content now)

Store as `outreach_mode` and `outreach_base_content`. Do not ask again during the session.

---

## STEP 3 — Determine Run Mode

**Single company** — one name or URL → full report in conversation
**Batch** — CSV file or list of names → loop through all, append columns to CSV

For batch: confirm row count and estimated time (~3 min/company for full crawl).
Ask: "Resume a previous run, or start fresh?"

---

## STEP 3.5 — Cross-Run Dedup & Do Not Contact Check

Before scoring, check if any companies in the current batch have been previously scored
or are on the Do Not Contact list.

### 3.5a — Check master workbook

```bash
python3 -c "
import os, csv, re

# Normalize company names for matching (same logic as shared/gtm_utils.py)
_SUFFIXES = re.compile(r'\b(inc|llc|ltd|co|corp|corporation|company|group|partners|holdings|enterprises|solutions|services|international|intl)\b\.?', re.IGNORECASE)
def normalize_key(name):
    if not name: return ''
    k = name.strip().lower(); k = _SUFFIXES.sub('', k)
    k = re.sub(r'[^a-z0-9\s]', '', k); k = re.sub(r'\s+', ' ', k).strip()
    return k

master = os.path.expanduser('~/.claude/gtm-stack/gtm-leads-master.xlsx')
if os.path.exists(master):
    from openpyxl import load_workbook
    wb = load_workbook(master, read_only=True, data_only=True)
    ws = wb['All Companies']
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h) for h in rows[0]] if rows else []
    ci = headers.index('Company') if 'Company' in headers else 0
    si = headers.index('Fit_Score') if 'Fit_Score' in headers else -1
    ti = headers.index('Fit_Tier') if 'Fit_Tier' in headers else -1
    for r in rows[1:]:
        print(f'{normalize_key(str(r[ci]) if r[ci] else \"\")}|{r[ci]}|{r[si] if si>=0 else \"\"}|{r[ti] if ti>=0 else \"\"}')
    wb.close()
else:
    print('NO_MASTER')
"
```

If master exists, build a lookup of previously scored companies (name → score, tier, date).

### 3.5b — Check Do Not Contact list

```bash
cat ~/.claude/gtm-stack/do-not-contact.csv 2>/dev/null || echo "NOT_FOUND"
```

If DNC list exists, load company names into a skip set.

### 3.5c — Report and handle duplicates

For each company in the current batch:

- **On DNC list** → skip entirely, mark `Fit_Tier = No Fit`, `Fit_Reasoning = "On Do Not Contact list"`.
  Do not deep-crawl.

- **Previously scored** → show to user:
  ```
  ⚠ Previously scored companies found:
    1. Meridian Construction — 92/100 (Strong Fit) on 2026-03-03
    2. Atlas Group — 87/100 (Strong Fit) on 2026-03-03

  Options:
    A) Keep existing scores (skip re-crawling) ← recommended
    B) Re-score all of them (full deep crawl)
    C) Let me pick which ones to re-score
  ```

  Default: keep existing. If kept, copy previous scores into current CSV.

- **New company** → proceed to scoring normally.

---

## STEP 4 — Quick Filter (for batches over 20 companies)

Before doing expensive deep crawls, do a rapid 30-second homepage-only pass to eliminate
obvious non-fits. This saves significant time on large lists.

### Parallel Quick Filter (use multi-tab rotation)

The quick filter only visits homepages — it's I/O-bound and ideal for parallelization.
**Open browser tabs based on batch size and rotate through companies:**

```
BATCH SIZE RULES (Quick Filter):
  1–10 companies  → batch_size = 1  (sequential, tab overhead isn't worth it)
  11–30 companies → batch_size = 3  (3 tabs)
  31–60 companies → batch_size = 4  (4 tabs)
  61+ companies   → batch_size = 5  (5 tabs — max for quick homepage checks)
```

```
PARALLEL QUICK FILTER — [batch_size] tabs

Round 1: Tab 1 → Company A homepage | Tab 2 → Company B homepage | Tab 3 → Company C homepage
  → While Tab 1 loads, Tab 2 and 3 are also loading
  → Extract from whichever tab loads first
  → Immediately navigate that tab to the next company (Company D)
Round 2: Continue rotating until all companies are checked
```

**Implementation with Playwright MCP:**
1. Calculate `batch_size` based on total company count (see rules above)
2. Use `tabs_create_mcp` to open `batch_size` browser tabs
3. Navigate all tabs simultaneously — don't wait for one before starting the next
4. For each tab, once the page is loaded:
   - Take a screenshot
   - Check homepage text against disqualifiers from the fit profile
   - Record result (Pass/Fail + reason)
   - Navigate tab to the next unvisited company
4. A tab should **never sit idle** while another tab is loading

**Estimated speedup:** Scales with batch size × 30-second homepage check.
For 50 companies with batch_size=4: ~6 min parallel vs ~25 min sequential.

For each company, visit homepage only and check against the loaded fit profile's
hard disqualifiers. Additionally always flag:
- Site is parked / company appears dissolved
- Industry is completely different from anything in the ICP (obvious mismatch)
- Company size is clearly far outside the ICP range (too large or too small)

Do NOT use hardcoded industry-specific checks (e.g. "We self-perform all work") —
those belong in the fit profile's Disqualifiers section, not here.

Mark obvious **No Fit** companies immediately with `Fit_Tier = No Fit (Quick)` and move on.
Only deep-crawl the remaining companies.

Report before starting deep crawls:
> "Quick pass complete: eliminated N obvious non-fits. Deep-crawling remaining N companies (~X hours)."

**Quick Filter Exclusion Report (always show):**

After the quick pass, show the full list of excluded companies so the user can spot-check:
```
⚡ QUICK FILTER RESULTS
  Eliminated [N] obvious non-fits:
    1. [Company Name] — [Reason: parked site / wrong industry / too large / too small]
    2. [Company Name] — [Reason]
    ...

  ⚠ Any of these look wrong? Tell me and I'll deep-crawl them.
  Otherwise, proceeding with [N] companies for deep analysis.
```

If the user identifies any false positives, remove them from the No Fit (Quick) list
and add them back to the deep-crawl queue.

---

## STEP 5 — Discover Company Website

Run for every company regardless of whether a name or URL was provided.

### Parallel Website Discovery (batch search queries)

Website discovery is search-heavy and I/O-bound — perfect for parallelization.
**Process companies in dynamic batches based on count:**

```
BATCH SIZE RULES (Website Discovery):
  1–8 companies   → batch_size = 1  (sequential)
  9–25 companies  → batch_size = 3  (3 tabs)
  26–60 companies → batch_size = 4  (4 tabs)
  61+ companies   → batch_size = 5  (5 tabs max)
```

```
PARALLEL DISCOVERY — [batch_size] tabs

Tab 1: Search "[Company A] official website" → evaluate results → record URL
Tab 2: Search "[Company B] official website" → evaluate results → record URL
Tab 3: Search "[Company C] official website" → evaluate results → record URL
  → Rotate tabs to next batch when each completes
```

**For name-only companies (no URL provided):**
1. Open 3 tabs, each searching for a different company
2. While waiting for search results on one tab, evaluate results on another
3. Once a company's website is confirmed, navigate that tab to the next company's search
4. Record all discovered URLs in the status file before proceeding to deep crawl

**For batches with URLs already provided:** skip this step for those companies.

This step is independent per company — no ordering constraints.
Speedup scales linearly with batch size (e.g. 4 tabs ≈ 4x faster).

**If name only:**
```
Search: "[Company Name] [city if known]"
Search: "[Company Name] official website"
```

Evaluate results:
- ✅ Accept: company's own domain, LinkedIn company page
- ❌ Skip: Yelp, BBB, Clutch, Angi, Bloomberg, news articles, individual LinkedIn profiles

Navigate to the candidate URL. Screenshot. Confirm name + industry + location match.

**If no website found:** search LinkedIn directly.
**If still nothing:** mark `Crawl_Status = No Web Presence`, `Fit_Score = 0`,
`Fit_Tier = No Fit`, `Fit_Reasoning = "No web presence found — unable to evaluate."`,
and skip to the next company.

**If URL provided:** navigate directly, verify it's the right company, proceed.

---

## STEP 6 — Deep Crawl

Visit in this order. Extract signals relevant to the fit profile — adapt based on
what matters for this specific profile, not everything applies to every business.

### Pipelined Deep Crawl + Score (overlap crawling with scoring)

The deep crawl is the most time-consuming phase (~3 min per company). Use a
**pipeline strategy** to overlap I/O-bound crawling with scoring/writing:

```
BATCH SIZE RULES (Deep Crawl):
  1–5 companies   → batch_size = 1  (sequential — scoring needs full attention)
  6–20 companies  → batch_size = 2  (2 tabs — crawl + score overlap)
  21+ companies   → batch_size = 3  (3 tabs max — more risks context overflow)
```

Deep crawl uses FEWER tabs than quick filter because each company requires
multiple page visits and produces much more text to process.

```
PIPELINE STRATEGY — [batch_size] tabs, crawl and score overlap

Timeline (batch_size=2):
  t=0:00  Tab 1 → Start crawling Company A (Homepage, About, Services...)
  t=0:30  Tab 2 → Start crawling Company B (while A continues loading pages)
  t=2:30  Tab 1 → Company A crawl complete → START SCORING Company A
          Tab 1 → Navigate to Company C (while scoring A in background)
  t=3:00  Tab 2 → Company B crawl complete → Score B, navigate to Company D
  ...

Timeline (batch_size=3):
  t=0:00  Tab 1 → Crawl Company A
  t=0:30  Tab 2 → Crawl Company B
  t=1:00  Tab 3 → Crawl Company C
  t=2:30  Tab 1 done → Score A, start crawling D
  t=3:00  Tab 2 done → Score B, start crawling E
  t=3:30  Tab 3 done → Score C, start crawling F
  ...
```

**How to implement:**
1. Calculate `batch_size` from the batch size rules above
2. Open `batch_size` browser tabs
3. Start crawling Company A in Tab 1 (visit all pages in sequence per that tab)
4. While Tab 1 is loading pages, start crawling Company B in Tab 2
5. When Tab 1's crawl is done, compile the signal sheet (STEP 7) and score (STEP 8)
   — this is text processing, doesn't need the browser
6. Meanwhile Tab 2 is still crawling — no idle time
7. After scoring Company A, navigate Tab 1 to start Company C's crawl
8. Continue rotating: always have one tab crawling while scoring the previous company

**When to override batch_size to 1 (force sequential):**
- Sites that aggressively rate-limit (e.g., LinkedIn company pages)
- When context window is more than 60% full (risk of overflow with parallel text)
- When a site requires CAPTCHA per visit (parallel tabs trigger more CAPTCHAs)

**Key constraint:** All pages for ONE company must be crawled in the SAME tab
(maintains session state, cookies, navigation context). Don't split one company's
pages across multiple tabs.

**Progress update format (parallel-aware):**
```
Progress: 15/45 companies
  Tab 1: Crawling Company X (page 4/7)
  Tab 2: Scoring Company W (writing outreach)
  🔴 Strong: 4  🟡 Moderate: 6  🔵 Low: 3  ⚫ No Fit: 2
  ~25 min remaining (3x faster than sequential)
```

### Per-company crawl order

**1. Homepage** — tagline, services overview, scale signals, tech mentions
**2. About** — founding year, headcount, growth story
**3. Services** — what they do vs. what they coordinate/outsource
**4. Portfolio / Projects / Case Studies** — project types, scale, recency, volume
**5. Team** — headcount, role breakdown, leadership names and accessibility
**6. Careers / Jobs** — what are they hiring for right now? (reveals growth + structure)
**7. Blog / News** — last post date, topics, growth signals
**8. Any fit-profile-specific page** — e.g. "Subcontractor", "Vendor", "Technology", "Partners"
**9. LinkedIn company page** — employee count (most reliable), recent posts, job postings

Do NOT search for individual decision maker LinkedIn profiles here — that happens in
STEP 9.5 after scoring, and only for companies that score Strong Fit or Moderate Fit.

**Retired / Former lead handling:**
When research reveals that the lead contact is retired, emeritus, or no longer in their role:
1. **Always research and record their successor** at the same organization. Search the
   org's staff directory or LinkedIn for the current person in that role. Add the
   successor as a new lead row with full details (name, title, email, LinkedIn URL).
   The organization's fit signals (budget, construction, COI needs) transfer directly.
2. **Do NOT auto-eliminate the retired person.** Flag them as "Retired" in the reasoning
   and present to the user with the option to include them for research/advisory outreach
   (different messaging: seeking insights, not selling). The user decides.

**Waiting for SPA/AJAX content:** after navigating each page, wait until text element
count stabilizes for 3 consecutive checks before extracting.

---

## STEP 7 — Compile Signal Sheet

After all crawls, organize into a structured summary before scoring:

```
COMPANY: [Name]
Website: [URL] | LinkedIn: [URL] | Location: [City, State]
Est. Employees: [N] (source: LinkedIn / Team page)
Industry / Role: [e.g. General Contractor, Facilities Manager]
Founded: [Year]

FIT SIGNALS FOUND:
  [Signal from profile] → [Evidence found or "Not found"]
  [Signal from profile] → [Evidence found or "Not found"]

DISQUALIFIERS CHECKED:
  [Disqualifier] → Present / Not present / Unclear

TECH / TOOLS MENTIONED: [List or "None"]
HIRING ACTIVITY: [Roles + count or "None visible"]
LAST CONTENT UPDATE: [Date or "Unknown"]
DECISION MAKER: [Pending — searched in STEP 9.5 after scoring, Strong Fit & Moderate Fit only]
```

---

## STEP 8 — Score

### Dynamic scoring framework

1. From the fit profile, identify the 4–5 dimensions that matter most
2. Assign weights totaling 100 — most critical dimension gets 25–30 pts, always include
   "Decision Maker Identifiability" at 10 pts (scored from website signals, not LinkedIn)
3. Score each dimension with explicit evidence cited
4. If any hard disqualifier is confirmed → cap total at 20 regardless of other scores

**Decision Maker Identifiability (10 pts):** Score based on whether a DM can likely be found,
using signals visible on the website — does the About page list leadership names? Are executive
names mentioned in case studies or press releases? Are leadership emails guessable from the
domain? Full 10 pts if name is already visible; 5 pts if inferrable; 0 if company is completely
opaque. The actual LinkedIn URL lookup happens in STEP 9.5 after scoring.

Example table (adapt dimensions to actual profile):
| Dimension | Max | Score | Evidence |
|-----------|-----|-------|---------|
| [Primary signal] | 30 | X | [what was found] |
| [Secondary signal] | 25 | X | [what was found] |
| [Supporting signal] | 20 | X | [what was found] |
| Size / stage fit | 15 | X | [what was found] |
| Decision maker identifiability | 10 | X | [e.g. CEO name on About page] |
| **Total** | **100** | **X** | |

### Tiers
- 🔴 **Strong Fit (75–100)** — strong match to ICP, reach out this week
- 🟡 **Moderate Fit (50–74)** — good signals, worth pursuing
- 🔵 **Low Fit (25–49)** — marginal, low priority
- ⚫ **No Fit (<25)** — not a fit or disqualifier confirmed

---

## STEP 9 — Write Fit Reasoning

3–4 sentences. Be specific. Always cite actual evidence from the crawl.
Never write generic statements.

**Structure:**
1. What kind of company + key size/scale fact
2. Strongest fit signal found (and where)
3. Biggest gap or concern
4. Overall verdict

**Good:**
> "Meridian Construction is a 45-person GC in Boston running 8 simultaneous commercial
> projects — team page shows 6 PMs and no field trade staff, confirming a coordination
> model with heavy sub use. No software tools mentioned anywhere on the site, and they're
> currently hiring two PMs on LinkedIn, suggesting the admin workload is already
> outpacing their process. No vendor/sub page found, so COI workflow is unknown."

**Bad (never write this):**
> "This company could benefit from our services based on their industry and size."

---

## STEP 9.5 — Find Decision Makers (Strong Fit & Moderate Fit only)

Run this step only after scoring is complete. **Skip for Low Fit and No Fit companies entirely.**

### Parallel DM Lookup (multi-tab LinkedIn search)

DM lookups are independent per company — ideal for parallel execution.
**LinkedIn is rate-sensitive — use conservative batch sizes:**

```
BATCH SIZE RULES (DM Lookup — LinkedIn):
  1–5 leads    → batch_size = 1  (sequential — safest)
  6–15 leads   → batch_size = 2  (2 tabs with 30s stagger)
  16+ leads    → batch_size = 2  (still 2 max — LinkedIn throttles hard)
```

LinkedIn is the one platform where batch_size should NEVER exceed 2.

```
PARALLEL DM LOOKUP — [batch_size] tabs, 30-second delay between searches

Tab 1: Search "[Company A] VP Operations LinkedIn" → find profile → record
Tab 2: Search "[Company B] CEO LinkedIn" → find profile → record
  → 30-second minimum gap between NEW searches on each tab
  → While waiting for search cooldown on Tab 1, process Tab 2's results
  → Rotate to next company when each tab completes
```

**Rate limiting rules for LinkedIn:**
- Maximum 2 concurrent LinkedIn tabs
- 30-second minimum between search queries per tab
- If CAPTCHA or restriction appears → drop to 1 tab, increase delay to 60 seconds
- If restricted again → stop DM lookups, mark remaining as `DM_LinkedIn = Pending`

**Estimated speedup:** 2x for DM lookups. For 15 Strong+Moderate companies:
~7 min parallel vs ~15 min sequential.

For every company that scored 50+ (Moderate Fit or Strong Fit), search LinkedIn for the decision maker:

```
Search: "[Company Name] [Owner OR Founder OR Principal OR VP Operations] LinkedIn"
```

Priority order for titles:
1. Owner / Founder / Principal (small companies — decision maker)
2. President / CEO
3. VP Operations / Director of Operations (mid-size — feels the pain)
4. Office Manager / Operations Manager (last resort)

Record:
```
DM Name:        [Full name]
DM Title:       [Current title]
DM LinkedIn:    [Profile URL]
Active on LI:   Yes / No / Unknown
Confidence:     High (confirmed current role) / Medium / Low
```

Confirm the LinkedIn profile matches the company (check current position in profile).
If not found or wrong person: mark `DM_LinkedIn = Not Found`, leave DM_Name blank.

Write DM fields to CSV immediately after finding each — these feed STEP 10 outreach.

> **Why this runs after scoring:** Searching LinkedIn for decision makers takes time.
> For sources like alumni portals, conference pages, or directories where LinkedIn URLs
> aren't already known, doing this for every company wastes time on companies that
> ultimately score Low Fit or No Fit. Scoring first, then looking up DMs only for actionable
> leads, keeps the run efficient.

---

## STEP 10 — Draft Outreach (Strong Fit & Moderate Fit only — skip Low Fit and No Fit)

Draft both an email and a LinkedIn DM for every Strong Fit and Moderate Fit company.
Use the outreach mode chosen in Step 2.

### Format rules

**Email:**
- Subject line required — specific, mention their company or a project
- 4–6 sentences in body
- Slightly more formal than LinkedIn
- Sign with sender's name (from fit profile) + title if provided

**LinkedIn DM:**
- No subject line
- 2–3 sentences MAX — read on mobile, in a noisy inbox
- One hook + one ask. No full pitch.
- Never paste an email into LinkedIn — signals mass outreach

### Drafting by mode

**Mode A — personalizing user's template:**
- Use template verbatim as base
- Replace all placeholders with real data found during crawl
- Insert ONE company-specific observation at the most natural point
- Do not restructure the template
- Flag any placeholder that couldn't be filled: `[NEEDS MANUAL CHECK: couldn't find X]`

**Mode B — building on rough draft / talking points:**
- Use user's content as the message intent and core
- Restructure to fit email vs. LinkedIn length constraints
- Add the specific hook from the crawl
- Sharpen vague language; keep the user's voice

**Mode C — from scratch:**

Email structure:
```
Subject: [Specific — mention their company or a real project]

Hi [First Name],

[One sentence: specific observation about their company from the crawl —
a named project, a job posting, a service gap, recent growth. About them, not you.]

[One sentence: connect that observation to the pain — frame as a pattern,
not an accusation. Make it feel like insight, not a pitch.]

[One sentence: what you do, plain English, no jargon.]

[One sentence: low-friction ask — 15-min call, happy to share how others
handle this, a quick question.]

[Sender name]
[Title if provided]
```

LinkedIn DM structure:
```
Hi [First Name] — [one specific hook from the crawl, 1 sentence].
[One-sentence ask — "worth a quick chat?" or "happy to share how a few
[their industry type]s are handling this."]
```

### Rules that apply to all modes
- Address decision maker by first name
- Reference ONE specific thing from the crawl — proves you looked
- Single soft ask — never ask to buy, never multiple asks
- No generic openers ("I came across your company...")
- No feature lists
- No attachments or links

---

## STEP 11 — Output

### Single company report
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 COMPANY FIT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Company:    [Name]
Website:    [URL]
LinkedIn:   [Company page URL]
Location:   [City, State]
Size:       [Est. employees + source]

FIT SCORE:  [X] / 100  [Tier emoji + label]

REASONING:
[3–4 sentences, specific and evidence-based]

SIGNALS:
  ✅ [Found signal]
  ⚠️  [Partial signal]
  ❌ [Not found]

DISQUALIFIERS:
  ✅ Not present: [list]
  🚫 Confirmed: [list if any]

SCORING:
  [Dimension table]

DECISION MAKER:
  [Name] — [Title]
  LinkedIn: [URL]
  Confidence: [High/Med/Low]

OUTREACH (Strong Fit & Moderate Fit only):
  Hook used: [specific detail]

  📧 EMAIL
  Subject: [Subject]
  ---
  [Full email body]
  ---

  💬 LINKEDIN DM
  ---
  [2–3 sentence DM]
  ---

  ⚠️  Manual check needed: [Yes/No + what]

PAGES CRAWLED: [list]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Batch CSV columns (append to existing — never modify original data)

| Column | Description |
|--------|-------------|
| `Website_Found` | URL (or "Not Found") |
| `Fit_Score` | 0–100 |
| `Fit_Tier` | Strong Fit / Moderate Fit / Low Fit / No Fit / No Fit (Quick) |
| `Fit_Reasoning` | 3–4 sentence explanation |
| `Top_Fit_Signal` | Strongest signal found |
| `Top_Concern` | Biggest gap or risk |
| `Est_Employees` | Number or range + source |
| `DM_Name` | Decision maker name |
| `DM_Title` | Decision maker title |
| `DM_LinkedIn` | Decision maker LinkedIn URL |
| `DM_Confidence` | High / Medium / Low |
| `Email_Subject` | Email subject line (Strong Fit & Moderate Fit only) |
| `Email_Body` | Full email body (Strong Fit & Moderate Fit only) |
| `LinkedIn_DM` | Short DM (Strong Fit & Moderate Fit only) |
| `Outreach_Mode` | A / B / C |
| `Personalization_Hook` | Specific detail used |
| `Manual_Check_Needed` | Yes / No |
| `Crawl_Status` | Complete / Partial / Quick Filter / No Web Presence |

Append using bash_tool:
```python
import csv

def append_fit_scores(filepath, results, new_fields):
    with open(filepath, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        existing_fields = list(rows[0].keys()) if rows else []

    all_fields = existing_fields + [f for f in new_fields if f not in existing_fields]

    # Match results to rows by company name (case-insensitive)
    results_by_name = {r['company'].lower().strip(): r for r in results}
    for row in rows:
        company_key = row.get('Company', row.get('company', '')).lower().strip()
        match = results_by_name.get(company_key)
        if match:
            row.update(match)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_fields,
                                quoting=csv.QUOTE_ALL, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
```

---

## STEP 12 — Batch Progress, Context Management & Resume

### Progress updates
Show a running tally every 5 companies:
```
Progress: 15/45 — 🔴 Strong: 4  🟡 Moderate: 6  🔵 Low: 3  ⚫ No Fit: 2  (~25 min left)
```

### Status file (update after every company)
```markdown
# Fit Analysis Status

## Profile
[Full fit profile block — so sessions are reproducible]

## Outreach mode: [A/B/C]

## Progress
| # | Company | Website | Score | Tier | Status |
|---|---------|---------|-------|------|--------|

Last completed: Row N — [Company name]
```

### Context management (critical for large batches)

**After every company:** discard raw crawl text. Keep only the scored row summary.

**Every 10 companies:** explicitly re-read the fit profile from the status file.
Do a quick calibration — would company #1 score the same today? Note any drift.

**Every 20 companies:** hard checkpoint announcement:
```
⏸️ CHECKPOINT — N/total complete
Strong Fit leads so far: [names + scores]
~N min remaining. Safe to pause here.
```

**Parallel-specific context management:**
- When running 2-3 tabs, each tab's crawl text accumulates faster. Be more aggressive
  about discarding: drop crawl text as soon as scoring is complete for that company
  (don't wait for the batch to finish).
- Keep a running JSON summary of all scored companies in the status file — this is
  your source of truth if you need to restart after a context overflow.
- If context is approaching the limit and multiple tabs are mid-crawl: finish the
  current company on each tab, score them, save to CSV, THEN pause. Never abandon
  a half-crawled company — the partial data is useless.

**If context is filling up:** stop, save status, tell user:
> "Saved through company N. Start a new session and say 'resume the fit analysis' to continue."

### Resume protocol
1. Read status file — find last completed row
2. Skip rows in CSV where `Fit_Score` is already populated
3. Re-read fit profile and outreach mode from status file
4. Continue appending — never rewrite existing rows or headers

---

## Final Summary (batch)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ FIT ANALYSIS COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Companies:       45 analyzed (8 quick-passed, 37 deep-crawled)
Websites found:  38 / 45

🔴 Strong Fit  (75–100):  9  ← outreach ready
🟡 Moderate Fit (50–74):  12  ← outreach ready
🔵 Low Fit     (25–49):  14  ← no outreach
⚫ No Fit      (<25):    10  ← no outreach

TOP LEADS:
1. [Company] — 91/100 — [DM name, LinkedIn] — [one-line reason]
2. [Company] — 87/100 — [DM name, LinkedIn] — [one-line reason]
3. [Company] — 83/100 — [DM name, LinkedIn] — [one-line reason]

CSV: [path]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Always end with the deliverables block:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Scored CSV:       /absolute/path/to/scored.csv
                    All companies with Fit_Score, Fit_Tier, reasoning, and outreach drafts

  Status file:      /absolute/path/to/scored_status.md
                    Resume file with fit profile and progress log
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then ask: "Want me to export just Strong Fit + Moderate Fit to a separate action list CSV?"

---

## Edge Cases

| Situation | Handle as |
|-----------|----------|
| Name only, no URL | Run Step 5 discovery first |
| Two companies with same name | Search with city qualifier; confirm with user |
| Wrong company found | Add city/industry to search; ask user to confirm |
| No website or LinkedIn | `No Web Presence`, score = N/A |
| Login wall on target site | Extract visible content, mark `Partial` |
| Site parked / inactive | Mark `Partial`, use LinkedIn only |
| Timeout | Wait 15s max, mark `Partial` |
| Obvious enterprise | Quick-pass immediately if profile disqualifies large companies |
| Vague fit profile | Push back — get 2–3 specific observable signals before starting |
| User says "just score them" | Minimal interview: "What do you sell?" + "Who's your ideal customer?" |

## Error Handling

- **Website unreachable (DNS failure, timeout, 404):** Mark `Crawl_Status = No Web Presence`, `Fit_Score = 0`, skip to next company. Do not block the batch.
- **Scrape blocked (CAPTCHA, Cloudflare, 403):** Mark `Crawl_Status = Partial`, score from whatever was visible (homepage text, LinkedIn). Note limitation in reasoning.
- **Scoring failure (ambiguous signals, all dimensions inconclusive):** Assign conservative score, flag `Manual_Check_Needed = Yes`, explain gaps in reasoning.
- **LinkedIn DM lookup rate-limited:** Drop to 1 tab, increase delay to 60s. If restricted again, mark remaining leads as `DM_LinkedIn = Pending` and continue.
- **CSV write failure mid-batch:** Retry once. If still failing, dump scored results to a new CSV in same directory, report both paths.
- Partial results: CSV is updated after each company is scored, never all-at-end.
- Final report includes success/partial/failure counts and lists companies that need manual review.

## Context Store Post-Write
After completing the main workflow, write discovered knowledge back to the context store:
- Target files: `contacts.md`, `insights.md`
- Entry format: `[YYYY-MM-DD | source: gtm-company-fit-analyzer | <detail>] confidence: <level> | evidence: 1`
- Write to `contacts.md`: decision makers discovered during DM lookup (name, title, company, LinkedIn URL, confidence level)
- Write to `insights.md`: company research findings (industry trends, common tech stacks, hiring patterns, fit signal patterns observed across the batch)
- DEDUP CHECK: Before writing, scan target file for same source + detail + date. Skip if exists.
- Write failures are non-blocking: log error, continue.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-company-fit-analyzer.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Scoring weights (dimension weights user has adjusted or confirmed)
- Industry preferences (verticals that matter most, disqualifier patterns)
- Output format preferences (CSV path, which columns matter, XLSX vs CSV)
- Crawl preferences (pages user finds most valuable, skip preferences)
- LinkedIn enrichment preferences (always/never/ask)

### What NOT to save
- Session-specific content, temporary overrides, confidential data

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |

## Flywheel MCP Integration

When connected to the Flywheel MCP server, persist scores to the GTM leads pipeline:

### After scoring each company:
1. Call `flywheel_upsert_lead(name, fit_score=<score>, fit_tier="<tier>", fit_rationale="<why>", source="gtm-company-fit-analyzer")`
2. Include any additional intel discovered during scoring in the `intel` parameter

If Flywheel MCP is not connected, skip these steps silently and use local file output.
