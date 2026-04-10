---
name: gtm-web-scraper-extractor
description: >
  [GTM Stack — parallel multi-term scraping, encoding validation.] Use this skill to extract structured data (contacts, alumni, attendees, leads, listings, etc.)
  from any website into a CSV file using the Playwright MCP browser. Trigger this skill whenever
  the user wants to scrape, extract, collect, or export records from a URL — including LinkedIn
  connections, alumni directories, conference attendee lists, event pages, membership directories,
  company listings, or any paginated web data. Use this skill even if the user just says "grab
  all the entries from this page into a CSV", "pull contact info from this site", "export these
  results", or mentions running multiple search terms across a directory.

  Requires: Playwright MCP server to be connected and active.
compatibility: "Requires Playwright MCP server to be connected and active in Claude Code or Claude.ai."
version: "1.2"
triggers:
  - "extract contacts from"
  - "scrape this page"
  - "pull all attendees"
  - "grab listings from"
  - "export these results to CSV"
  - "web scraper"
tags:
  - gtm
  - web-research
context-aware: true
recipe-aware: true
web_tier: 3
parameters:
  input_schema:
    type: object
    properties:
      url:
        type: string
        format: uri
        description: "URL of the webpage to scrape and extract information from"
    required:
      - url
  input_description: "Requires a URL to scrape. Provide the full URL including https://."
---

# Web Scraper / Data Extractor Skill

Extract structured records from any website into a CSV file using the Playwright MCP browser.
Handles login-gated sites, pagination, resumable sessions, deduplication, and post-processing.

---

## How to Use

### Direct invocation
In Claude Code, type:
```
/gtm-web-scraper-extractor
```
Or just describe what you want — Claude will trigger this skill automatically.

### Natural language triggers
- *"Extract all contacts from [URL] into a CSV"*
- *"Scrape my LinkedIn connections into a spreadsheet"*
- *"Pull all attendees from this conference page"*
- *"Grab every listing from this directory into a CSV"*
- *"Resume the scraping session from yesterday"*

### Works great for
- LinkedIn connections
- Alumni directories (MIT, Harvard, etc.)
- Conference attendees (Luma, Whova, Eventbrite)
- Business directories and membership sites
- Any paginated or scroll-based listing

> **Want to scrape AND score leads in one go?** Use `/gtm-pipeline` instead —
> it runs this skill first, then automatically scores every company for fit.

---

## FIRST TIME SETUP

If the user is running this skill for the first time, or says "set up the scraper" /
"install prerequisites" / "something's not working", run the bundled setup script:

```bash
# Try project-level install first, then fall back to user-level
bash "$(find ~/.claude/skills -name setup.sh -path '*/web-scraper-extractor/*' 2>/dev/null | head -1)"
```

If the script is not found, the skill may not be installed yet. Install it first, then re-run.

This script automatically:
- Verifies Python 3 is installed
- Installs required Python packages (`openpyxl`, `pandas`)
- Checks Node.js is installed (required for Playwright MCP)
- Verifies/installs the Playwright MCP server (`@playwright/mcp`)
- Checks Claude Code MCP config and prints the exact fix command if Playwright is missing

**One-time Playwright MCP registration** (if not already done):
```bash
claude mcp add playwright -- npx @playwright/mcp
```
Restart Claude Code after running this. Verify with: `claude mcp list`

---

## STEP 0 — Check Available Playwright Tools

Before anything else, check which Playwright MCP tools are available in this session. Tool names
vary by MCP setup. Look for tools named like:
- `browser_navigate` / `playwright_navigate`
- `browser_screenshot` / `playwright_screenshot`
- `browser_evaluate` / `playwright_evaluate`
- `browser_click` / `playwright_click`
- `browser_wait_for_selector` / `playwright_wait_for_selector`

Use whichever naming convention is present. If no Playwright tools are available, stop and tell
the user: "The Playwright MCP server doesn't appear to be connected. Please enable it in your
MCP settings and try again."

### 0b. Input Validation
- Verify: URL provided and non-empty before proceeding to audit.
- Verify: URL is accessible (navigate and check for non-error HTTP response) during pre-scrape audit.
- Verify: fields to extract are specified (at least one column name).
- For sites with 100+ pages estimated: confirm scope with user before starting the loop.

### Parallel Execution
Scale browser tabs to batch volume. Use parallel agents for large batches.

| Items | Agents | Notes |
|-------|--------|-------|
| 1-5   | Sequential | Overhead not worth it |
| 6-15  | 2 | -- |
| 16-30 | 3 | -- |
| 31-50 | 4 | -- |
| 51+   | 5 (cap) | Avoid rate limits |

Multi-search-term parallelism is defined separately in STEP 6.

### Backup Protocol
- Before overwriting output CSV: create `.backup.YYYY-MM-DD`, keep last 3
- Back up files before overwriting where applicable

### 0c. Context Store Pre-Read
- Read `~/.claude/context/_catalog.md` to discover available files
- Load: `icp-profiles.md`
- Cap: max 10 recent entries per file
- Show what was loaded: "Loaded X entries from Y context files"
- Use ICP profiles to inform which fields to prioritize during extraction (e.g., industry, company size, geography filters)

---

## STEP 1 — Gather Inputs

Ask the user for the following before doing anything else. Collect all at once to avoid back-and-forth.

| Input | Required? | Description |
|-------|-----------|-------------|
| **URL** | ✅ | Starting page URL |
| **Fields to extract** | ✅ | Column names (e.g. "Name, Job Title, Company, Location, Email") |
| **Login required?** | ✅ | If yes, confirm user is logged in before proceeding |
| **Custom instructions** | Optional | Filters, search terms, keywords, geographic scope, special logic |
| **Output filename** | Optional | Default: `~/Downloads/scrape_<site>_<date>.csv` |
| **Output format** | Optional | CSV (default), JSON, or XLSX |
| **Multiple search terms?** | Optional | Run same scrape for multiple keywords and merge results |
| **Resume previous session?** | Optional | If a status file exists, offer to resume |

---

## STEP 2 — Pre-Scrape Audit (Do Not Skip)

This phase prevents wasted effort. Complete all steps before starting the loop.

### 2a. Confirm Login State
If login is required: navigate to the URL and take a screenshot. Confirm with the user that
the page shows authenticated content (not a login wall). Do not proceed until confirmed.

> **Important — Playwright browser is an isolated session.** It does NOT share cookies or
> login state with the user's regular browser. Even if the user says "I'm already logged in",
> they mean their regular browser. You must confirm they have also logged in inside the
> Playwright browser window specifically. Ask: "Have you logged in to [site] in the browser
> window that Playwright opened?" before proceeding.

### 2b. Apply Filters / Search Terms
If the user specified filters (e.g. "Industry: Construction", "Location: United States"):
- Apply them in the UI before scraping
- Take a screenshot to confirm filters are active
- Note the exact filter state in the status file

### 2c. Count Total Records & Estimate Time
Look for a record count displayed on the page (e.g. "Showing 651 results", "23 pages").
- Record the total count in the status file
- Calculate estimated pages: `ceil(total / records_per_page)`
- Calculate estimated time: assume ~8–15 seconds per page, show ETA to user
- If no count is visible, scrape page 1, count records, note "total unknown"

**Confirm with user before proceeding:**
> "Found ~651 records across ~33 pages. Estimated time: ~7 minutes. Shall I proceed?"

### 2c.5. Recipe Lookup (Skip DOM Exploration if Cached)

This skill supports execution recipes. Follow `~/.claude/skills/_shared/recipe-protocol.md`.

Before probing the DOM from scratch, check if a working recipe exists:

1. **Determine domain and task:**
   - Domain: extract hostname from URL (strip www. prefix)
   - Task: infer from user intent and URL pattern:
     - LinkedIn `/search/results/people/` -> `search-people`
     - LinkedIn `/mynetwork/invite-connect/connections/` -> `connections`
     - LinkedIn `/school/*/people/` -> `alumni-directory`
     - Other URLs -> `extract-list` (default)

2. **Check for recipe:**
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py lookup --domain {domain} --task {task}
   ```

3. **If recipe found:**
   - Report: "Using cached recipe for {domain}:{task} (last verified {date})"
   - Apply behaviors from recipe (delays, wait strategies)
   - Execute the `extraction_code` from the recipe in the browser
   - Validate results against `quality_baseline` (record count, field fill rates)
   - If validation passes: **skip Step 2d entirely**, proceed to Step 3
   - If validation fails: run staleness check per recipe-protocol.md Section 5 (steps 7-9), then proceed to Step 2d if needed

4. **If no recipe found:**
   - Proceed to Step 2d (normal DOM exploration)

### 2d. DOM Exploration — Find the Right Selectors

**Do NOT assume selectors.** Run a structured probe to identify them empirically.

**Step 1 — Find the record container:**
```javascript
// Try common patterns, find which count matches expected records-per-page
const counts = {
  'li': document.querySelectorAll('li').length,
  '[class*="result"]': document.querySelectorAll('[class*="result"]').length,
  '[class*="card"]': document.querySelectorAll('[class*="card"]').length,
  '[class*="item"]': document.querySelectorAll('[class*="item"]').length,
  '[class*="row"]': document.querySelectorAll('[class*="row"]').length,
  'tr': document.querySelectorAll('tr').length,
};
return counts;
```
Pick the selector whose count best matches expected records-per-page (e.g. 20).

**Step 2 — Inspect record structure:**
```javascript
// Examine first 2 records in detail
const sample = [];
document.querySelectorAll('YOUR_CHOSEN_SELECTOR').forEach((el, i) => {
  if (i >= 2) return;
  sample.push({
    fullText: el.innerText.trim().substring(0, 300),
    links: Array.from(el.querySelectorAll('a')).map(a => ({ text: a.innerText.trim(), href: a.href })),
    children: Array.from(el.children).map(c => ({
      tag: c.tagName,
      class: c.className,
      text: c.innerText.trim().substring(0, 80)
    }))
  });
});
return sample;
```

Document the confirmed selectors before proceeding:
```
Record container: .alumni-result-item
Name:             .result-name
Title:            .result-title
Company:          .result-company
Location:         .result-location
Profile URL:      a[href*="/profile/"]
```

### 2e. Detect Pagination Method

Inspect the page for (in order of preference):
1. **URL-based**: Does URL change with page? (e.g. `?page=2`, `#page=2`) → Use this, most reliable
2. **Next button**: Find selector, note how it signals the last page (disabled, hidden, absent)
3. **Infinite scroll**: No button — use scroll + wait pattern
4. **Load more button**: Single button that appends records

Document in status file which method will be used.

---

## STEP 3 — Set Up Output Files

Create both files BEFORE the loop begins.

### CSV File
- Write header row immediately
- UTF-8 encoding
- Wrap all fields in double quotes (`csv.QUOTE_ALL`) to handle commas/newlines in values

### Status File (`<output_name>_status.md`)
```markdown
# Scraper Status — <Site Name>

## Configuration
- URL: <url>
- Filters applied: <filters>
- Fields: <field list>
- Selectors: <documented selectors from Phase 2d>
- Pagination: <method from Phase 2e>
- Total records (estimated): <N>
- Total pages (estimated): <N>
- Session started: <timestamp>

## Progress
| Session | Date | Pages Completed | Records Added | CSV Total | Notes |
|---------|------|-----------------|---------------|-----------|-------|

## Resume Instructions
To resume: start at page <N>, appending to existing CSV (do not rewrite header).
Last record written: <name + company of last row>
Dedup anchor: load last 50 rows of CSV into a Set(name|company) before resuming.
```

---

## STEP 4 — Scraping Loop

### Per-Page Flow
```
FOR each page:
  1. Wait for records to fully load (stability check — see below)
  2. Extract records via playwright_evaluate
  3. Validate: count check + field completeness check
  4. Append valid records to CSV; write failures to _errors.csv
  5. Update status file with page number + running total
  6. Show progress every 5 pages: "Progress: Page X/Y — N records scraped (~Z min remaining)"
  7. Paginate
  8. Check end conditions
```

### Waiting for Dynamic Content (SPA/AJAX Sites)

Many modern sites (React, Vue, Angular) load records asynchronously. Do NOT extract
immediately after navigation. Wait for content to stabilize:

```javascript
// Poll until record count stabilizes for 3 consecutive checks
let prev = 0, stable = 0;
const start = Date.now();
while (stable < 3 && Date.now() - start < 10000) {
  const count = document.querySelectorAll('RECORD_SELECTOR').length;
  if (count > 0 && count === prev) stable++;
  else { stable = 0; prev = count; }
  await new Promise(r => setTimeout(r, 500));
}
return prev;
```

If count is still 0 after 10 seconds: take a screenshot and re-examine the DOM —
selectors may have changed or content may be in an iframe.

### Extraction Template

```javascript
const records = [];
const seenOnPage = new Set(); // dedup within current page

document.querySelectorAll('RECORD_SELECTOR').forEach(el => {
  const name     = el.querySelector('NAME_SEL')?.innerText?.trim()    || '';
  const title    = el.querySelector('TITLE_SEL')?.innerText?.trim()   || '';
  const company  = el.querySelector('COMPANY_SEL')?.innerText?.trim() || '';
  const location = el.querySelector('LOC_SEL')?.innerText?.trim()     || '';
  const url      = el.querySelector('a')?.href                        || '';

  // Skip ghost/template elements (all fields empty)
  if (!name && !company && !title) return;

  // Deduplicate within page
  const key = `${name}|${company}`;
  if (seenOnPage.has(key)) return;
  seenOnPage.add(key);

  records.push({ name, title, company, location, url });
});

return records;
```

### Quality Checks (Per Page — Do Not Skip)

1. **Count check**: Got significantly fewer records than expected per page?
   → Stop. Re-probe selectors. Don't silently write an incomplete page.

2. **Field completeness**: If <50% of records have a key field (name or company),
   the selector is likely wrong — pause and re-examine.

3. **Error records**: Any record where all meaningful fields are blank
   → Write to `<output>_errors.csv` with page number for manual review.

### CSV Append Function

```python
import csv

def append_records(filepath, records, fieldnames):
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL,
                                extrasaction='ignore')
        writer.writerows(records)
```

### Pagination Execution

**URL-based (preferred):**
```python
# Increment page param directly — no clicking needed
next_url = re.sub(r'page=\d+', f'page={current_page + 1}', current_url)
```

**Next button:**
```javascript
// Verify button state before clicking
const btn = document.querySelector('NEXT_BUTTON_SELECTOR');
const isDisabled = btn?.disabled
  || btn?.classList.contains('disabled')
  || btn?.getAttribute('aria-disabled') === 'true'
  || !btn;
return { found: !!btn, disabled: isDisabled };
```

**Infinite scroll:**
```javascript
const before = document.querySelectorAll('RECORD_SELECTOR').length;
window.scrollTo(0, document.body.scrollHeight);
// After this, wait ~2 seconds, then re-check count
// If count === before → end of list reached
```

### End Conditions

Stop when ANY of these are true:
- Next button is absent or disabled
- 0 records extracted from current page
- CSV record count has reached total reported by the site
- URL-based: current page > total pages
- User signals stop

---

## STEP 5 — Resuming a Session

### Saving State (After Each Page)
Always write to status file after every page:
```markdown
| Session 1 | 2026-03-02 | Page 12 | 19 | 231 | Paused by user |
```
And note the last record written: `Last record: Jane Smith | Turner Construction`

### Resume Protocol

1. Read the status file — find last completed page and last record written
2. Open the CSV → load the last 50 rows → build a dedup Set: `Set(name|company)`
3. Navigate to resume point:
   - URL-based: jump directly to `?page=N`
   - Button-based: navigate to base URL → re-apply filters → navigate to page N via URL if possible
4. On the **first page after resume**: extract records but filter out any already in the dedup Set
5. Continue appending — **do NOT rewrite the header row**

---

## STEP 5.5 — Save Recipe (Second Hit Heuristic)

After successful extraction, check if this scrape should generate a recipe:

```bash
python3 ~/.claude/skills/_shared/recipe_utils.py check-visits --domain {domain} --task {task}
```

- **If "create recipe: True"**: Build a recipe YAML capturing:
  - The extraction strategy that worked (innertext_parsing, css_selector, etc.)
  - The working extraction JS code (from Step 4)
  - Pagination method and code
  - Behavioral observations (delays, wait times)
  - Quality baseline (avg records per page, field fill rates)
  - Save via: `python3 ~/.claude/skills/_shared/recipe_utils.py save --domain {domain} --task {task} --file /tmp/recipe.yaml`
  - Report: "Saved execution recipe for {domain}:{task}"

- **If "create recipe: False"**: Log the visit:
  ```bash
  python3 ~/.claude/skills/_shared/recipe_utils.py log-visit --domain {domain} --task {task}
  ```

- **If user explicitly asks to save a recipe**: Save immediately regardless of visit count.

- **After successful extraction with an existing recipe**: Mark it verified:
  ```bash
  python3 ~/.claude/skills/_shared/recipe_utils.py update-verified --domain {domain} --task {task}
  ```

---

## STEP 6 — Multi-Search-Term Runs

When the user wants the same directory scraped for multiple keywords (e.g. "Construction",
"Architecture", "Civil Engineering"):

### Parallel Multi-Term Strategy (use separate browser tabs)

Instead of running each term sequentially, **use separate browser tabs for each search term**:

```
BATCH SIZE RULES (Multi-Term Scraping):
  1 search term  → batch_size = 1  (just run it)
  2–3 terms      → batch_size = number of terms  (one tab per term)
  4–6 terms      → batch_size = 3  (rotate through in 2 rounds)
  7+ terms       → batch_size = 3  (cap at 3 — more tabs causes memory issues
                                     and higher rate-limiting risk)
```

```
PARALLEL MULTI-TERM — [batch_size] concurrent tabs

Tab 1: Search "Construction" → scrape all pages → save to temp CSV
Tab 2: Search "Architecture" → scrape all pages → save to temp CSV
Tab 3: Search "Civil Engineering" → scrape all pages → save to temp CSV
  → All [batch_size] run simultaneously
  → Merge and deduplicate after all tabs complete
```

**Implementation:**
1. Open one tab per search term (up to 3 concurrent tabs — more risks rate limiting)
2. In each tab: apply the search term filter, then run the normal scraping loop
3. Each tab writes to its own temp CSV independently
4. After ALL tabs complete, merge and deduplicate into the final output

**Tab rotation for 4+ search terms:**
```
Round 1: Tab 1→"Construction", Tab 2→"Architecture", Tab 3→"Civil Engineering"
Round 2: When Tab 1 finishes "Construction", navigate to "Plumbing"
         (Tabs 2 and 3 may still be running their first terms)
```

**When NOT to parallelize (force batch_size=1):**
- Site has aggressive rate limiting (LinkedIn, some alumni directories)
- Login session is shared across tabs and site doesn't support concurrent sessions
- Each search term returns 100+ pages (memory/context pressure)
- Site shows CAPTCHA after multiple concurrent requests

In these cases, fall back to sequential with a single tab.

**Estimated speedup by batch size:**
| Terms | Batch size | Sequential | Parallel | Speedup |
|-------|-----------|-----------|----------|---------|
| 2     | 2         | ~20 min   | ~10 min  | ~2x     |
| 3     | 3         | ~30 min   | ~10 min  | ~3x     |
| 6     | 3         | ~60 min   | ~20 min  | ~3x     |

### Sequential fallback (for rate-limited sites)

1. Run each term as a separate pass → save to temp CSVs:
   - `output_construction_temp.csv`
   - `output_architecture_temp.csv`

2. After all passes, merge and deduplicate:

```python
import csv, glob, os

# Use the same directory as the temp files to avoid matching unrelated files
output_dir = os.path.dirname(os.path.abspath('output_merged.csv'))
all_files = glob.glob(os.path.join(output_dir, 'output_*_temp.csv'))
seen = set()
merged = []
all_fieldnames = []  # collect all column names across all files

# First pass: gather all unique fieldnames across all files
for filepath in all_files:
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for field in (reader.fieldnames or []):
            if field not in all_fieldnames:
                all_fieldnames.append(field)

# Second pass: merge records with case-insensitive dedup
for filepath in all_files:
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row.get('Name','').lower().strip()}|{row.get('Company','').lower().strip()}"
            if key not in seen:
                seen.add(key)
                merged.append(row)

if not merged:
    print("No records to merge — check that temp files are not empty.")
else:
    with open('output_merged.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_fieldnames, quoting=csv.QUOTE_ALL,
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(merged)
    print(f"Merged: {len(merged)} unique records from {len(all_files)} search terms")
```

3. Report total unique vs. duplicates removed across terms.

---

## STEP 7 — Post-Processing

After scraping, run these automatically, then offer optional enhancements.

### Automatic Cleanup (Always Run)
```python
import csv, re

def clean_csv(filepath, fieldnames):
    rows = []
    seen = set()
    with open(filepath, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            # Trim whitespace
            row = {k: v.strip() for k, v in row.items()}
            # Skip blank rows
            if not any(row.values()):
                continue
            # Deduplicate on name + company (case-insensitive semantic key)
            key = (row.get('Name', '').lower(), row.get('Company', '').lower())
            if key not in seen:
                seen.add(key)
                rows.append(row)
    # Rewrite cleaned file
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
```

### Optional Enhancements (Offer to User)

| Enhancement | Description |
|-------------|-------------|
| **Split Name** | Add `First Name` and `Last Name` columns |
| **Standardize Location** | Normalize formats (e.g. "New York, NY, USA" → "New York, NY") |
| **Extract Email Domain** | Add `Email Domain` column — useful for company-level filtering |
| **Data Quality Flag** | Add `Quality` column: "Complete" / "Missing Title" / "Missing Company" |
| **Sort** | By Company, Location, or Name |
| **Convert to XLSX** | Auto-sized columns, frozen header row (via openpyxl) |

---

## STEP 8 — Final Summary & Deliverables

```
✅ Scraping complete!

📄 Output:  ~/Downloads/mit_alumni_construction.csv
📊 Records: 451 unique records (23 duplicates removed, 3 errors logged)
📑 Pages:   33 of 33
⚠️  Errors:  3 records → mit_alumni_construction_errors.csv (review manually)
🕐 Time:    11 minutes

Preview:
| Name         | Title           | Company       | Location   |
|--------------|-----------------|---------------|------------|
| Jane Smith   | Project Manager | Turner Const. | Boston, MA |
| ...
```

**Always end with the deliverables block:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Extracted CSV:    /absolute/path/to/output.csv
                    [N] unique records with [field list]

  Status file:      /absolute/path/to/output_status.md
                    Resume point and session history

  Errors (if any):  /absolute/path/to/output_errors.csv
                    [N] records for manual review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Site-Specific Playbooks

### LinkedIn Connections

#### Your own connections
- URL: `https://www.linkedin.com/mynetwork/invite-connect/connections/`
- Login: Always required
- Pagination: Infinite scroll — scroll bottom, wait 2s, check new cards loaded, repeat
- Key selectors: `.mn-connection-card`, `.mn-connection-card__name`, `.mn-connection-card__occupation`
- Rate limiting: Add 2–3s delay between scrolls. LinkedIn throttles aggressively.
- Cap: LinkedIn shows max ~3,000 connections via this URL

#### Another person's connections
To scrape connections from someone else's profile, use the search URL embedded in their
"500+ connections" link. Navigate to their profile first, then find the link:

```
https://www.linkedin.com/search/results/people/?origin=MEMBER_PROFILE_CANNED_SEARCH
  &connectionOf=["PROFILE_URN_ID"]
  &network=["F","S"]
```

The `PROFILE_URN_ID` (e.g. `ACoAACh44kABdfoGUTegnxbINVarKm-nH28qj9Y`) is embedded in the
connections link href on the profile page. You can also extract it from any messaging URL
on the profile. Note: you can only view connections of people who have made them visible.

#### CSS selectors are unreliable on LinkedIn — use innerText line-parsing instead

LinkedIn frequently changes its CSS class names. **Do NOT rely on class-based selectors**
like `.entity-result__title-text` or `.reusable-search__result-container` — they will
silently return empty results when LinkedIn updates its frontend.

Instead, use `innerText` line-parsing anchored to the connection-degree line:

```javascript
() => {
  const main = document.querySelector('main');
  const listItems = Array.from(main.querySelectorAll('li')).filter(li => {
    const text = li.innerText?.trim();
    return text && text.length > 10 && !text.includes('Are these results helpful');
  });

  return listItems.map(li => {
    const lines = li.innerText.trim().split('\n').map(l => l.trim()).filter(Boolean);
    const name = lines[0] || '';

    // Anchor to "Xnd/rd/st degree connection" line — headline is always next
    const degreeIdx = lines.findIndex(l => l.includes('degree connection'));
    const headline  = degreeIdx !== -1 ? lines[degreeIdx + 1] || '' : '';
    const location  = degreeIdx !== -1 ? lines[degreeIdx + 2] || '' : '';

    // Parse headline: "Title @ Company" or "Title at Company" or free-form
    let title = '', company = '';
    if (headline.includes(' @ ')) {
      const parts = headline.split(' @ ');
      title   = parts[0].split('|')[0].trim();
      company = parts[1].split('|')[0].trim();
    } else if (/ at /.test(headline)) {
      const parts = headline.split(/ at /);
      title   = parts[0].trim();
      company = parts.slice(1).join(' at ').split('|')[0].trim();
    } else {
      // Free-form headline (e.g. "Skill1 | Skill2 | Skill3") — use as title, no company
      title = headline.split('|')[0].trim();
    }

    return { name, title, company, location };
  }).filter(r => r.name);
}
```

> **Note on headline parsing:** LinkedIn's headline is a free-form text field. When a person
> writes `"Strategy | Yale | HEC Paris"` without a clear title/company separator, company will
> be empty. This is expected — do not treat it as an extraction failure.

### Alumni Directories (MIT, Harvard, etc.)
- Usually SPA (React/Angular) — always use stability-wait before extracting
- Apply all search filters BEFORE starting the loop; screenshot to confirm
- Next button often: `.pagination-next`, `[aria-label="Next page"]`, or `button[data-page]`

### Conference Attendees
- **Luma**: Event page → "People" tab → often public, infinite scroll
- **Whova**: Requires login → "Community" tab → paginated list
- **Eventbrite**: Check for Export button in organizer dashboard first — faster than scraping
- **Hopin**: Session-specific lists, requires organizer access

### General Directories / Listings
- **Always check for an Export/Download button first** — if it exists, use it
- Look for structured cards, table rows, or repeated list items
- Check `robots.txt` and report to user if scraping is disallowed

---

## Error Recovery Cheatsheet

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 records extracted | Content not loaded / wrong selectors | Re-probe DOM, add stability wait |
| 0 records on LinkedIn search | CSS classes changed | Switch to `innerText` line-parsing (see LinkedIn playbook) |
| Same records every page | Pagination not working | Check URL change; switch to URL-based |
| Records have empty fields | Wrong child selectors | Re-inspect with children probe |
| Page shows login wall | Session expired | Ask user to re-authenticate |
| Sudden slowdown / blank page | Rate limiting | Add 5s delay, reduce pace |
| Count doesn't match expected | Filters not applied | Re-apply filters; screenshot to confirm |
| Duplicates after resume | Dedup anchor missing | Load last 50 CSV rows into Set before resuming |
| Ghost/template elements extracted | Selector too broad | Tighten selector; check for `:empty` or `.hidden` |

## Error Handling

- **Pagination failure (next button missing, URL pattern breaks):** Save all records scraped so far to CSV. Report page count reached and offer to resume manually or switch pagination method.
- **Login session expired mid-scrape:** Pause scraping, save progress to CSV + status file. Ask user to re-authenticate in the Playwright browser, then resume from last completed page.
- **Anti-bot block (CAPTCHA, 429, Cloudflare challenge):** Stop scraping, save progress. Suggest reducing speed (add 5s delay) or using a different session. Never retry aggressively.
- **Encoding issues (mojibake, garbled text):** Detect non-UTF-8 characters in extracted text, attempt `latin-1` fallback. Log affected records to `_errors.csv` for manual review.
- **Selector breakage (0 records on a page that should have data):** Re-probe DOM selectors before continuing. If re-probe fails, save progress and report the breakage.
- Partial results: CSV is appended after each page, never all-at-end.
- Final report includes pages completed, records saved, errors logged, and any pages skipped.

### Resume & Checkpoint
For multi-page scraping or batch URL extraction:
- Save checkpoint after each page/URL completes: `scrape_checkpoint.json` with completed URLs + extracted data paths
- On restart, check for checkpoint — skip already-scraped URLs
- Checkpoint includes: completed URLs, output file paths, extraction stats
- Clear checkpoint after successful batch completion
- For single-URL scrapes: no checkpoint needed (fast operation)

### Idempotency
- Output CSVs use source identifier + timestamp in filename — re-runs create new files
- Same URL scraped twice produces separate output files (no collision)
- Extraction is stateless — no side effects beyond output file creation
- Context store writes: full replacement of updated fields, not append

### Context Management
For large scraping jobs (50+ profiles or multi-page results):
- Process in batches of 25 profiles
- Write extracted data to CSV incrementally (don't hold all results in context)
- Keep running count and summary stats rather than full profile list
- For paginated results: process one page at a time, append to output CSV

## Context Store Post-Write
After completing the main workflow, write discovered knowledge back to the context store:
- Target files: `contacts.md`
- Entry format: `[YYYY-MM-DD | source: gtm-web-scraper-extractor | <detail>] confidence: low | evidence: 1`
- Write to `contacts.md`: scraped contacts with name, title, company, and source URL (confidence: low because scraped data is unverified)
- DEDUP CHECK: Before writing, scan target file for same source + detail + date. Skip if exists.
- Write failures are non-blocking: log error, continue.

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-web-scraper-extractor.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Preferred output format (CSV, JSON, XLSX)
- Encoding preferences (UTF-8 default, any overrides)
- Pagination strategy preferences per site (URL-based vs button vs scroll)
- Site-specific selector patterns that worked
- Rate limiting experience per site

### What NOT to save
- Session-specific content, temporary overrides, confidential data

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
| 1.1 | 2026-03-13 | Added Standards 5 (Resume & Checkpoint), 7 (Idempotency), 11 (Context Management) |
| 1.2 | 2026-03-14 | Added recipe-aware support: Step 2c.5 (recipe lookup) and Step 5.5 (recipe save) |

## Flywheel MCP Integration

When connected to the Flywheel MCP server, persist scraped data to the GTM leads pipeline:

### After scraping each company:
1. Call `flywheel_upsert_lead(name, domain, source="gtm-web-scraper", intel={industry, description, ...})`
2. For each contact found, call `flywheel_add_lead_contact(lead_name, contact_name, email, title, linkedin_url)`

This enables downstream skills (scorer, researcher, drafter) to pick up leads automatically.
If Flywheel MCP is not connected, skip these steps silently and use local file output.
