---
name: gtm-my-company
description: >
  [GTM Stack — schema versioning.] Build and manage your persistent GTM sender profile — the "who you are" context that
  powers lead scoring and outreach across all GTM Stack skills. Run once to set up;
  automatically loaded by gtm-leads-pipeline and gtm-company-fit-analyzer in every future session.
  Triggers on: "/gtm-my-company", "set up my company profile", "update my profile",
  "what company profile is saved", "change my company info", or any request to configure
  GTM context, sender identity, ICPs, value propositions, or buyer personas.
compatibility: "Playwright MCP recommended for website crawling (optional — can build profile from pasted text alone)."
---

# My Company Skill

Build a persistent GTM sender profile that's automatically used by `gtm-leads-pipeline`
and `gtm-company-fit-analyzer`. Run once; never re-enter your business context again.

**Profile stored at:** `~/.claude/gtm-stack/sender-profile.md`

---

## How to Use

### Direct invocation
```
/gtm-my-company
```

### Natural language triggers
- *"Set up my company profile"*
- *"What profile is currently saved?"*
- *"Update my ICP — we're now targeting enterprise"*
- *"Change my value propositions"*
- *"Show me what info the pipeline uses about my company"*

---

## STEP 0 — Check Playwright Availability

Check for Playwright tools (`browser_navigate` etc).

- **If connected:** Note internally — will crawl website in STEP 2b.
  Tell user: "Playwright available — I'll crawl your website automatically."
- **If not connected:** Note internally — will build from pasted text only.
  Tell user: "Playwright isn't connected — I'll build from pasted text or a file you provide.
  You can re-run `/gtm-my-company` with Playwright connected to enrich it from your website later."

Do not block on this. Continue to STEP 1 regardless.

---

## STEP 1 — Check for Existing Profile

Run via bash:
```bash
cat ~/.claude/gtm-stack/sender-profile.md 2>/dev/null || echo "NOT_FOUND"
```

### If profile EXISTS — show summary and offer options:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 YOUR SAVED COMPANY PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Last updated: [date from file]

Company:    [Name from file]
Sender:     [Sender Name, Title]
What we do: [What We Offer — first sentence]
Primary ICP: [Industry] · [Type] · [Size] · [Geography]
             Pain: [Core Pain]

Value props:
  • [VP 1]
  • [VP 2]
  • [VP 3]

Competitors: [Competitor 1], [Competitor 2], [Competitor 3]

Fit signals: [Signal 1], [Signal 2]
Disqualifiers: [Disqualifier 1], [Disqualifier 2]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What would you like to do?

A) Use as-is — this looks right, nothing to change
B) Update permanently — re-research and rebuild (takes 5–10 min, saves over this file)
C) Quick edit — describe what changed, I'll update in memory for this session
   (then you can choose to save permanently too)
D) Show me the full profile — display everything in the saved file
```

Wait for response:

- **A:** Say "Profile confirmed — good to go. Run `/gtm-leads-pipeline` or `/gtm-company-fit-analyzer` when ready." → Done.

- **B:** Run the full Build Wizard starting at STEP 2. Save to file when done.

- **C:**
  Ask: "What changed? Describe the update — e.g. 'We're now targeting enterprise, 50–500 employees' or 'Add new ICP: commercial real estate developers'"
  Read the full saved profile. Apply the stated change in memory.
  Show the updated section(s) and confirm what was changed.
  Ask: "Want to save this change permanently? (yes / no)"
  - If yes → use the Write tool to save the updated profile to `~/.claude/gtm-stack/sender-profile.md` with today's date. Confirm saved.
  - If no → confirm: "Got it — this only affects the current session. The saved file is unchanged."
  → Done.

- **D:** Read and display the full file contents, then show only A/B/C options (not D again —
  the full profile is already visible).

---

### If profile does NOT EXIST:

```
No company profile found yet.

I'll build one from your website and save it permanently — takes 5–10 minutes.
After that, gtm-leads-pipeline and gtm-company-fit-analyzer will load it automatically
every session (no more re-answering "what does your company do").
```

Proceed directly to STEP 2. Do not ask for confirmation.

---

## STEP 2 — Build Wizard

### 2a. Gather inputs (one message)

```
To build your profile, I need a couple of things:

1. Your name and job title
   (used to sign outreach emails and set context for scoring)

2. Your company website URL
   (I'll crawl it to extract positioning, services, and market signals)
   — Skip if you don't have a website yet; I'll build from text instead

3. Any additional context to include? (optional)
   - Path to a file: pitch deck, one-pager, product brief, marketing copy
     e.g. ~/Documents/company-overview.pdf
   - Or paste text directly: copy-paste from your website, deck, or notes
```

Store all answers. Proceed immediately after user responds.
If no URL given (or user says "no website yet"): skip STEP 2b entirely, go to 2c.

### 2b. Crawl the company website

*(Skip this step if no URL provided or Playwright not connected.)*

Navigate via Playwright to the provided URL. Visit in this order — stop after 5 pages
or when all of these are populated: company name, what they sell, primary ICP signals,
2+ differentiator claims:

1. **Homepage** — tagline, headline, hero copy, positioning statement
2. **About / Our Story** — founding context, mission, team size hints
3. **Product / Services / Solutions** — what they sell, how it works
4. **Customers / Case Studies / Who We Serve** — ICP signals, industries, logos
5. **Blog or Resources** (only if needed) — topics reveal target audience

After navigating each page, wait until text content stabilizes before extracting.

Extract:
- Company name and tagline
- What they sell (product/service) and the core problem it solves
- Any explicit ICP or target customer language
- Competitive differentiation claims ("unlike X, we...")
- Social proof: industries served, customer types, company sizes

**If URL unreachable or page fails to load:** proceed with step 2c using
pasted text only — mark `Source: manual` in profile.
**If website requires login:** extract the visible marketing/landing pages only,
mark `Source: partial (login-walled)` in profile.

### 2c. Read supplemental file (if path provided)

Read the file using the Read tool. Extract the same signals as 2b.
Merge with crawl results — prefer more specific language when there's overlap.
If the file and website contradict each other on something meaningful (e.g. different
target market), flag it in the draft: `[Discrepancy: website says X, file says Y — confirm]`.

### 2d. Research competitors

Run two web searches:
```
"[company name] competitors"
"[product/service category] alternatives [current year]"
```

From results, identify 3–5 direct competitors.
For the top 3, do a quick homepage-only visit to extract their main positioning headline.
For each competitor record:
- What they focus on / their angle (from their own homepage)
- How your company differs (infer from crawl context vs. their positioning)

If competitor research returns no useful results, mark:
"Competitive landscape: research inconclusive — fill in manually."

### 2e. Synthesize the profile

Build the full structured profile below. Be specific — avoid generic marketing language.
If you can't find evidence for a field, mark it `[not found — fill in manually]`.

- For **Secondary ICP**: only include if clearly supported by evidence (multiple customer
  types on website, explicit "also serving" language). If not evident, write
  `[Not yet identified — leave blank until confirmed]`. Do not invent one.
- For **Expansion Path**: only include if the website or materials explicitly signal future
  direction. If not stated, omit this field entirely rather than speculating.
- For **Buyer Personas**: if persona info isn't on the website, infer from: job titles
  in case studies, roles in hiring pages, or blog post audiences. If no signals at all,
  mark `[Needs input — fill in manually]`.

Profile format:

```markdown
# My Company Profile
schema_version: 2
Last updated: [today's date]
Source: [URL crawled] [+ file path if provided]

## Sender
Name: [First + Last name]
Title: [Job title]

## Company
Name: [Name]
Website: [URL]
Tagline: [Tagline or headline from homepage]

## What We Offer
[2-3 sentences. Plain English. What product/service, what problem it solves,
how it works at a high level. No jargon. Written as if explaining to a smart friend.]

## Value Propositions
1. [Specific, concrete value prop — ideally lifted from their own copy]
2. [Second value prop]
3. [Third value prop]

## Key Differentiators
- vs [Competitor or alternative approach]: [How we differ and why it matters to the buyer]
- vs [Another alternative]: [Differentiator]

## Competitive Landscape
| Competitor | What they focus on | Our edge vs. them |
|------------|-------------------|-------------------|
| [Name] | [1 sentence from their homepage] | [1 sentence] |
| [Name] | [1 sentence from their homepage] | [1 sentence] |
| [Name] | [1 sentence from their homepage] | [1 sentence] |

## Ideal Customer Profile
### Primary ICP
- Industry: [Industry or industries]
- Company Type: [e.g. General Contractor, SaaS company, Regional Bank]
- Size: [e.g. 10–100 employees, $5M–$50M revenue]
- Geography: [e.g. United States, North America]
- Core Pain: [The specific problem they have that this product solves]
- Buying Trigger: [What event or moment causes them to look for a solution?]

### Secondary ICP
[Only include if clearly evidenced — otherwise write: Not yet identified]

## Buyer Personas
### [Job Title — e.g. VP Operations at a mid-size GC]
- Cares about: [What resonates in outreach — their metrics, pressures, priorities]
- Pain points: [The day-to-day friction this product relieves]
- Objections: [Common pushback at first contact]
- Don't lead with: [What turns them off — features, price, buzzwords]

### [Second Persona if evidenced]
- Cares about: [...]
- Pain points: [...]
- Objections: [...]
- Don't lead with: [...]

## Outreach Context
[2-3 sentences. The narrative that makes cold outreach land: why this problem matters now,
what makes this solution different, what hook tends to open conversations.
Written from sender's perspective.]

## Fit Scoring Signals
Good fit (observable on company websites or LinkedIn):
- [Signal 1 — specific and detectable from web research]
- [Signal 2]
- [Signal 3]

Disqualifiers (automatic No Fit if present):
- [Hard disqualifier 1]
- [Hard disqualifier 2]

## Outreach Preferences
Follow-up cadence:
  Strong Fit:   3 business days
  Moderate Fit: 5 business days

Channels: [Gmail / Outlook / LinkedIn — filled in on first pipeline run]
Sending mode: [Preview each / Batch / Auto — filled in on first pipeline run]
```

**Note for downstream skills using this profile:**
When drafting outreach (Mode C), use the `## Outreach Context` section as the core narrative.
Use `## Key Differentiators` to make the value prop specific. Use the Buyer Persona's
"Cares about" as the hook angle and avoid anything listed under "Don't lead with".

### 2f. Show draft for review

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 DRAFT PROFILE — REVIEW BEFORE SAVING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Full profile content]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Does this look right?
- Any corrections? (describe what to change)
- Type "looks good" or "save" to save as-is
- Type "start over" to rebuild from scratch
```

Wait. Apply corrections and **re-show the full updated profile** (not just the changed
sections — user needs full context to verify everything fits together).
Ask: "Anything else to adjust, or ready to save?"

If user says "start over": discard all gathered data (crawl results, competitor research,
synthesis) and return to STEP 2a with a fresh inputs message.

After 3 rounds of corrections without saving, offer:
> "Want to save what we have and finish editing the file manually? You can open
> `~/.claude/gtm-stack/sender-profile.md` in any text editor."

### 2g. Save profile

Once approved:
1. Create directory: `mkdir -p ~/.claude/gtm-stack` (via Bash)
2. Use the **Write tool** to create/overwrite `~/.claude/gtm-stack/sender-profile.md`
   with the full approved profile content.

Confirm:
```
✅ PROFILE SAVED
   ~/.claude/gtm-stack/sender-profile.md

   gtm-leads-pipeline and gtm-company-fit-analyzer will now load this automatically.

   Next step: run /gtm-leads-pipeline or /gtm-company-fit-analyzer — your profile
   will be detected and loaded at the start of either skill.

   Run /gtm-my-company any time to view or update it.
```

---

## Edge Cases

| Situation | Handle as |
|-----------|-----------|
| No website URL provided / "no website yet" | Skip 2b; build from pasted text only; mark `Source: manual` |
| URL returns 404 / unreachable | Skip 2b; proceed with pasted text; mark `Source: manual` |
| Website requires login | Crawl visible marketing pages only; mark `Source: partial (login-walled)` |
| No Playwright MCP connected | Skip 2b entirely; ask user to paste company description |
| Company has no "About" or "Services" page | Use homepage + any readable subpage |
| User pastes text only (no URL) | Build from text; mark `Source: manual` |
| File path provided but file not found | Tell user, ask them to re-check path or paste text |
| Competitor research returns irrelevant results | Mark competitive landscape "fill in manually" |
| Website and file contradict each other | Flag discrepancy inline in draft; ask user to confirm |
| Multi-product company | Note in draft; ask "Which product/line should scoring focus on?" before finalizing |
| User skips review ("save now") | Save immediately without corrections |
| Profile file already exists during B update | Overwrite after user confirms in STEP 2f |
| Called mid-pipeline (during gtm-leads-pipeline or gtm-company-fit-analyzer) | After saving, remind user: "Restart your pipeline from the beginning to pick up the updated profile." |
| No secondary ICP evident from research | Leave field as "Not yet identified" — never fabricate |
