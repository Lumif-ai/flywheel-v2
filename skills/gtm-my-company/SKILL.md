---
name: gtm-my-company
version: "3.1"
description: >
  Company profile enricher that builds and maintains your persistent GTM sender
  profile through a guided wizard (steps 2a-2g). Gathers data via website crawling
  (Playwright MCP), competitor research (WebSearch), supplemental file reading, and
  user input. Writes positioning, ICP, competitive intel, objection handling, market
  taxonomy, and product inventory to the context store. Also maintains the legacy
  sender-profile.md for backward compatibility with existing GTM pipeline skills.
context-aware: true
triggers:
  - manual
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
output:
  - context-store-writes
  - sender-profile-compat
web_tier: 2
---

# gtm-my-company

**Trigger phrases:** "update company profile", "build sender profile", "update positioning", "my company", "who are we", "update ICP", "update competitive intel", "update objections", or any request to configure GTM context, sender identity, ICPs, value propositions, or buyer personas.

---

## Step 0: Load Existing Context and Check Tools

### 0a. Check Playwright Availability

Check for Playwright tools (`browser_navigate` etc).

- **If connected:** Note internally -- will crawl website in Step 2c.
  Tell user: "Playwright available -- I'll crawl your website automatically."
- **If not connected:** Note internally -- will build from pasted text only.
  Tell user: "Playwright isn't connected -- I'll build from pasted text or a file you provide.
  You can re-run `/gtm-my-company` with Playwright connected to enrich it from your website later."

Do not block on this. Continue regardless.

### 0b. Load Existing Context

Run the pre-read to snapshot existing context store data and detect what already exists:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared/engines"))
from gtm_company import (
    pre_read_context, format_context_entry, write_to_context_store,
    write_profile, log_profile_event, WRITE_TARGETS
)

existing_context = pre_read_context("gtm-my-company")
print(f"Loaded {len(existing_context)} context files")

for target in WRITE_TARGETS:
    if target in existing_context and existing_context[target]:
        entry_count = existing_context[target].count("[20")
        print(f"  {target}: ~{entry_count} existing entries")
    else:
        print(f"  {target}: empty (no existing data)")
```

Programmatically, pre-read via:
```
python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags sales,outreach,product,market,competitors --json
```

Show the user what positioning data already exists.

---

## Step 1: Determine Mode

Three modes based on existing data and user intent:

### Build Mode (no existing data, or user chooses "rebuild")
Full wizard from scratch -- run Steps 2a through 2g sequentially.

### Update Mode (data exists, user wants to update)
1. Show current positioning data from context store organized by section.
2. Ask: "What has changed? New product features? New competitors? Updated ICP? New verticals?"
3. Only gather information for sections that need updating.
4. Skip to Step 2e (Synthesize) with updated sections merged into existing data.

### Quick Edit Mode (user wants to change specific fields)
1. Show current profile organized by section with numbered fields.
2. Let user specify which fields to edit by number or description.
3. Accept edits inline, write only changed sections.
4. Skip directly to Step 2f (Review) with minimal changes applied.

If data exists in any of the write target files, ask:
**"Do you want to (A) use as-is, (B) update/rebuild the full profile, or (C) quick edit specific fields?"**

- **A:** Confirm profile is current. Done.
- **B:** Run full Build Wizard (Steps 2a-2g).
- **C:** Enter Quick Edit mode.

If no data exists, proceed directly to Step 2a.

---

## Step 2: Build Wizard

### Step 2a: Core Identity

Gather from user (one message):
1. **Your name and job title** (used to sign outreach and set sender context)
2. **Company name** (if not already in context store)
3. **Founding date** (approximate is fine)
4. **Mission/vision** (one sentence each, or "skip")
5. **Company website URL** (skip if no website yet -- will build from text)
6. **Any supplemental files?** Path to pitch deck, one-pager, product brief, or marketing copy
   (e.g., `~/Documents/company-overview.pdf`). Or paste text directly.

Store all answers. Proceed immediately after user responds.

Check context store for existing data in `positioning.md` and `company-core.md` -- pre-fill
what is already known and ask user to confirm or correct.

### Step 2b: Product/Service Inventory

Read `product-modules.md` from context store if it exists. Then gather:

1. **All products/services** -- not just the primary one. List every product line, module, add-on, or service tier.
2. **For each product:** What problem it solves, who uses it, how it works at a high level.
3. **Product relationships:** Are they bundled? Tiered? Independent? Cross-sell paths?
4. **Pricing model:** Per-seat, usage-based, flat fee, tiered, enterprise custom. Approximate price points.

If the user has many products, organize them into categories. Write to `product-modules.md` following the context store entry format.

### Step 2c: Website Crawling (Playwright)

*(Skip if no URL provided or Playwright not connected.)*

Navigate via Playwright to the provided URL. Visit in this order -- stop after 5 pages
or when all key fields are populated:

1. **Homepage** -- tagline, headline, hero copy, positioning statement
2. **About / Our Story** -- founding context, mission, team size hints
3. **Product / Services / Solutions** -- what they sell, how it works, features
4. **Pricing** -- pricing model, tiers, approximate price points
5. **Customers / Case Studies / Who We Serve** -- ICP signals, industries, logos, testimonials

After navigating each page, wait until text content stabilizes before extracting.

Extract:
- Company name and tagline
- What they sell (product/service) and the core problem it solves
- Any explicit ICP or target customer language
- Competitive differentiation claims ("unlike X, we...")
- Social proof: industries served, customer types, company sizes
- Pricing signals and model
- Tech stack mentions or integration partnerships

**If URL unreachable or page fails to load:** Proceed with pasted text only -- mark `Source: manual` in profile.
**If website requires login:** Extract visible marketing/landing pages only -- mark `Source: partial (login-walled)`.

### Step 2d: Competitive Landscape

Identify top 3 competitors. Sources (in priority order):
1. `competitive-intel.md` from context store (if it has existing entries)
2. User input ("Who do you compete with?")
3. WebSearch: `"[company name] competitors"` and `"[product category] alternatives [current year]"`

For each of the top 3 competitors:
- **WebSearch** for: product features, pricing, positioning, recent news, funding
- **Visit homepage via Playwright** (if available) to extract their main positioning headline
- Record: What they focus on (from their own copy), how user's company differs

Write findings to `competitive-intel.md` via context store.

If competitor research returns no useful results, mark: "Competitive landscape: research inconclusive -- fill in manually."

### Step 2e: Market Positioning and Synthesis

Gather and synthesize (reading from context store + user input):

**From `positioning.md`:** Existing value propositions, differentiators, elevator pitch.
**From `icp-profiles.md`:** Existing ICP definitions, buyer personas.
**From `market-taxonomy.md`:** Existing vertical classifications.

Then gather from user:
1. **Target verticals/industries** -- which industries, what sub-segments, why now
2. **ICP definition** -- company characteristics (size, industry, tech stack, geography)
3. **Buyer personas** -- decision-maker titles, what they care about, pain points, objections
4. **Key differentiators** -- how you differ from each competitor and from status quo
5. **Sales motion** -- deal size range, typical sales cycle length, primary channels (inbound/outbound/partner), sales team size

Write vertical/industry data to `market-taxonomy.md` following the context store entry format.

### Step 2f: Evidence and Traction

Gather social proof and evidence:
1. **Customer names/logos** (if shareable) -- industries, company sizes
2. **Case studies** -- problem, solution, result (even informal ones)
3. **Metrics and traction** -- ARR, growth rate, customer count, retention, NPS (whatever they are comfortable sharing)
4. **Awards, press, partnerships** -- anything that builds credibility
5. **Testimonial quotes** -- specific quotes from customers if available

### Step 2g: Voice and Messaging

Gather communication preferences:
1. **Tone** -- formal, conversational, technical, casual, authoritative
2. **Key phrases to use** -- specific language that resonates with their buyers
3. **Words/phrases to avoid** -- jargon, competitor names, overpromises, specific claims
4. **Outreach context** -- the narrative that makes cold outreach land: why this problem matters now, what hook opens conversations
5. **Objection handling** -- common objections heard in sales + evidence-based responses

Write objection data to `objections.md` via context store.

---

## Step 3: Structure and Write Profile Data

Build the `profile_data` dict from all gathered information. This is LLM work -- structure the data, then write it to the context store and legacy file.

**Context store sections:**

| Key | Context File | What to Include |
|-----|-------------|-----------------|
| `positioning` | positioning.md | Value propositions, key differentiators, elevator pitch, what we offer, how we are different |
| `icp` | icp-profiles.md | Ideal customer profiles, company characteristics, buyer personas, decision-maker titles |
| `competitors` | competitive-intel.md | Competitive landscape, feature comparisons, positioning against each, win/loss patterns |
| `objections` | objections.md | Common objections, evidence-based responses, counter-arguments, proof points |
| `verticals` | market-taxonomy.md | Target industries, sub-segments, market signals, entry timing, regulatory context |
| `products` | product-modules.md | Product/service inventory, pricing model, product relationships |

**Legacy sender-profile.md sections** (also included in profile_data):

| Key | What to Include |
|-----|-----------------|
| `sender` | Sender name, role, email |
| `company` | Company overview, founding, mission |
| `value_props` | Detailed value propositions |
| `differentiators` | What makes us different |
| `competitive_landscape` | Full competitive analysis |
| `icps` | Detailed ICP descriptions |
| `buyer_personas` | Persona cards |
| `fit_scoring` | Scoring criteria for lead qualification |

Each value should be a list of content line strings:

```python
profile_data = {
    "positioning": [
        "Company is a [what] for [whom]",
        "Replaces [old way] with [new way]",
        "Key differentiator: [specific advantage]",
    ],
    "icp": [
        "[Industry] companies with [characteristic]",
        "Company size: [range]",
        "Decision maker: [titles]",
    ],
    "competitors": [
        "Competitor: [Name] -- [their positioning]",
        "Advantage: [how we differ]",
    ],
    "objections": [
        "Objection: '[common pushback]'",
        "Response: [evidence-based counter]",
    ],
    "verticals": [
        "[Industry vertical]: [sub-segments], [market signals]",
    ],
    "products": [
        "[Product name]: [description], [pricing model]",
    ],
}
```

### Show Draft for Review

Before writing, show the full synthesized profile to the user:

```
DRAFT PROFILE -- REVIEW BEFORE SAVING

[Full profile content organized by section]

Does this look right?
- Any corrections? (describe what to change)
- Type "looks good" or "save" to save as-is
- Type "start over" to rebuild from scratch
```

Wait for response. Apply corrections and re-show the full updated profile (not just
changed sections -- user needs full context to verify everything fits together).

After 3 rounds of corrections without saving, offer:
"Want to save what we have and finish editing the file manually?"

If user says "start over": discard all gathered data and return to Step 2a.

### Write Profile

Once approved:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared/engines"))
from gtm_company import write_profile, pre_read_context, log_profile_event

# profile_data structured by the LLM above
results = write_profile(profile_data, "gtm-my-company")
print(f"Context store: {results['context_store_results']}")
print(f"Legacy file: {results['legacy_result']}")
```

Programmatically, append entries via:
```
python3 ~/.claude/skills/_shared/context_utils.py append positioning.md --source gtm-my-company --detail "[tag]" --content "[lines]"
```

```python
# Log event
files_written = list(results['context_store_results'].keys())
log_profile_event(files_written, len(files_written))
```

---

## Step 4: Verification

Read back from context store to confirm writes landed correctly:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared/engines"))
from gtm_company import pre_read_context, WRITE_TARGETS

updated_context = pre_read_context("gtm-my-company")
for target in WRITE_TARGETS:
    if target in updated_context and updated_context[target]:
        print(f"  {target}: confirmed written")
    else:
        print(f"  {target}: WARNING - no data found")

# Check legacy file
legacy_path = os.path.expanduser("~/.claude/gtm-stack/sender-profile.md")
if os.path.exists(legacy_path):
    size = os.path.getsize(legacy_path)
    print(f"  sender-profile.md: confirmed ({size} bytes)")
else:
    print(f"  sender-profile.md: WARNING - not found")
```

Report results to user. If any write target is missing, offer to retry that section.

---

## Edge Cases

| # | Situation | Handle as |
|---|-----------|-----------|
| 1 | Pre-revenue company | Focus on vision, founding story, problem validation. Skip traction metrics. Mark pricing as "TBD". Emphasize founder background and market opportunity instead of revenue proof. |
| 2 | Pivot in progress | Ask: "What are you pivoting FROM and TO?" Build profile for the new direction. Flag any legacy positioning that contradicts the pivot for user review. |
| 3 | Multiple products | Ask: "Which product/line should scoring focus on?" Build comprehensive inventory in product-modules.md but mark the primary product for outreach. |
| 4 | B2B vs B2C vs B2B2C | Adjust ICP structure: B2B uses company characteristics, B2C uses demographic/psychographic, B2B2C needs both. Ask which buyer to target for outreach. |
| 5 | Marketplace/platform | Capture both sides: supply-side and demand-side profiles. Ask which side outreach targets. Build separate ICPs for each side. |
| 6 | Regulated industry | Note regulatory context in market-taxonomy.md. Flag compliance requirements that affect messaging (e.g., cannot make certain claims). Adjust tone to industry norms. |
| 7 | Solo founder vs team | Adjust sender context: solo founder is the brand; team needs role clarity. For solo founders, emphasize personal credibility and domain expertise. |
| 8 | International vs domestic | Capture geography in ICP. Note language/cultural considerations for outreach. Flag timezone implications for sales motion. |
| 9 | Hardware + software | Capture both product types with different sales cycles. Hardware may have longer cycles, different pricing models, and physical logistics considerations. |
| 10 | Service vs product | Services need: engagement model, deliverables, team composition. Products need: features, pricing tiers, technical specs. Capture the right structure for each. |
| 11 | Open source | Capture: community edition vs enterprise, conversion funnel, developer audience vs enterprise buyer. Two ICPs likely needed. |
| 12 | Enterprise vs SMB | Different sales motions: enterprise is top-down, SMB is bottom-up or self-serve. Capture both if the company spans segments. Note deal size and cycle differences. |
| 13 | Stealth mode | Minimize public-facing details. Skip website crawling. Build from internal docs and user input only. Mark profile as "confidential -- do not use in outreach without review". |

**Additional edge cases:**

| Situation | Handle as |
|-----------|-----------|
| No website URL provided / "no website yet" | Skip 2c; build from pasted text only; mark `Source: manual` |
| URL returns 404 / unreachable | Skip 2c; proceed with pasted text; mark `Source: manual` |
| Website requires login | Crawl visible marketing pages only; mark `Source: partial (login-walled)` |
| No Playwright MCP connected | Skip 2c entirely; ask user to paste company description |
| Company has no "About" or "Services" page | Use homepage + any readable subpage |
| User pastes text only (no URL) | Build from text; mark `Source: manual` |
| File path provided but file not found | Tell user, ask them to re-check path or paste text |
| Competitor research returns irrelevant results | Mark competitive landscape "fill in manually" |
| Website and file contradict each other | Flag discrepancy inline in draft; ask user to confirm |
| User skips review ("save now") | Save immediately without corrections |
| Profile file already exists during rebuild | Overwrite after user confirms in Step review |
| Called mid-pipeline | After saving, remind: "Restart your pipeline from the beginning to pick up the updated profile." |
| No secondary ICP evident | Leave as "Not yet identified" -- never fabricate |

---

## Memory & Learned Preferences

**Memory file:** `~/.claude/projects/-Users-sharan/memory/gtm-my-company.md`

### Loading (Step 0c)
Check for saved preferences. Auto-apply and skip answered questions.
Show: "Loaded preferences: [list what was applied]"

### Saving (after each run)
Update memory with new preferences. Edit existing entries, never duplicate.

### What to save
- Wizard answers (core identity, products, verticals, ICPs, voice preferences)
- Profile version and last update date
- Preferred data sources (website crawl vs manual vs file import)
- Company name and core identity
- Preferred positioning language/tone
- Known competitors and how to position against them
- ICP refinements from sales feedback
- Objection patterns that work best
- Vertical preferences and industry focus

### What NOT to save
- Session-specific content, temporary overrides, confidential data

---

### Resume & Checkpoint
Profile generation involves multiple research phases. If interrupted:
- Save partial profile to `sender-profile.md.partial` after each major section completes
- On restart, detect partial file and offer to resume from last completed section
- Sections: Company Overview -> Product/Service -> Target Market -> Differentiators -> Messaging
- Clear partial file after successful completion

### Idempotency
- `sender-profile.md` is overwritten entirely on each run (single source of truth)
- Profile generation is deterministic given same inputs -- safe to re-run
- No append operations -- each run produces complete, self-contained profile
- Context store writes: full file replacement, not partial updates

### Context Management
- Profile data is structured in discrete sections -- each section researched and written independently
- Web research results summarized before incorporation (don't keep raw HTML in context)
- Final profile assembled from section summaries
- If research produces excessive content, prioritize: messaging > differentiators > market > overview

### Backup Protocol
- Before overwriting `sender-profile.md`: create `.backup.YYYY-MM-DD`, keep last 3
- Use `gtm_utils.backup_file()` from `~/.claude/skills/gtm-shared/gtm_utils.py` where available
- Context store writes: backup target file before modification
- Never delete old profile without backup

## Error Handling

- **Website crawl failure (URL unreachable, timeout, login wall):** Fall back to manual input; mark `Source: manual`.
- **Supplemental file not found or unreadable:** Tell user the path, ask for correction or paste text instead.
- **Context store write failure:** Log error with filename, attempt legacy sender-profile.md write independently.
- **Legacy write failure:** Log error, context store writes are still valid -- do not retry.
- **Playwright timeout on a page:** Skip that page, continue with next page in crawl order; note which pages were skipped.
- **WebSearch rate limit:** Wait and retry once; if still blocked, skip competitor research and mark section "fill in manually".
- **Partial profile data:** Write whatever sections are complete, skip empty sections. Never write empty entries.
- Partial results: save progress incrementally per section, never all-at-end.
- Final report includes success/failure counts per context store file.

---

## Context Store

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md` for pre-read, post-write, and knowledge overflow handling.

## Important Notes

- All context store writes follow the entry format in `~/.claude/skills/_shared/context-protocol.md`
- Profile is written to BOTH context store AND legacy sender-profile.md (dual-write pattern, locked decision from Phase 4)
- Perform the dual-write: update both context store files and legacy `sender-profile.md`
- Each build wizard step validates input before proceeding -- allow user to revise at each step

### Input Validation
- Verify: company name or website URL provided before starting Build Wizard (Step 2a).
- Verify: supplemental file paths exist and are readable before attempting file import.
- For Update Mode: confirm at least one context store file has existing data before proceeding.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.1 | 2026-03-13 | Replaced hardcoded context file list in frontmatter with `context-aware: true`. Removed phantom Python engine note referencing non-existent `context_utils.py`. Replaced `context_utils.append_entry()` reference with context-protocol.md. |
| 3.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
