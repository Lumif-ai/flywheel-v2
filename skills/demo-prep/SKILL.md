---
name: demo-prep
version: "1.0"
description: Prepare a custom demo for a prospect company by researching them, seeding a self-contained customer context file, and generating demo-ready artifacts. Zero writes to shared context files.
context-aware: true
reads:
  - positioning.md
  - product-modules.md
  - market-taxonomy.md
writes:
  - customer-*.md
triggers:
  - "demo prep"
  - "prepare demo"
  - "custom demo"
  - "demo for"
  - "prep a demo"
  - "seed demo"
web_tier: 2
---

# Demo Prep

Prepare a custom product demo for a prospect company. Researches the company, seeds a **self-contained** customer context file, and generates demo-ready artifacts.

This skill is context-aware. Follow the protocol in `~/.claude/skills/_shared/context-protocol.md`.

## Version

v1.1 (2026-03-16)

## Design Principle: Self-Contained Customer Files

**ALL research goes into `customer-{company}.md` only.** No writes to shared context files (contacts.md, competitive-intel.md, industry-signals.md, icp-profiles.md). This keeps your operational context store clean — when you delete a customer file after the demo, there's zero residue.

The customer file has dedicated sections for contacts, competitive intel, industry context, and pain points specific to that prospect. The demo briefing reads from the customer file directly.

## What This Skill Does

1. **Researches the prospect** — crawls their website, searches for news/press, finds key people
2. **Seeds customer-{company}.md** — self-contained file with everything: company intel, contacts, competitive landscape, pain points, tech stack, compliance needs
3. **Generates demo briefing** — HTML briefing showing what the product "knows" about them
4. **Validates demo readiness** — checks that the customer file has enough depth

## Input

**Required:**
- Company name (e.g., "Acme Insurance")
- Company website URL (e.g., "https://acmeinsurance.com")

**Optional:**
- Key contact name(s) for research
- Specific pain points or topics to emphasize
- Industry vertical if not obvious from website
- Demo date (for urgency framing in briefing)

## Process

### Step 1: Research the Company

Use multiple sources — don't rely on website alone:

**1a. Website crawl:**
```bash
python3 -c "
import asyncio, sys
sys.path.insert(0, '$(python3 -c "import os; print(os.path.realpath(os.path.expanduser(\"~/.claude/skills/_shared/engines\")))")')
from company_intel import crawl_company, structure_intelligence
raw = asyncio.run(crawl_company('{URL}', max_pages=8))
intel = structure_intelligence(raw['text'], 'demo-prep-crawl')
import json; print(json.dumps(intel, indent=2))
"
```

**IMPORTANT:** Do NOT call `write_company_intelligence()` — that writes to shared context files. Instead, capture the structured `intel` dict and use it in Step 2 to populate the customer file only.

If crawl fails (site blocks, timeout), fall back to web search for the company name.

**1b. Web search for recent context:**
Search for: "{company name} news", "{company name} challenges", "{company name} technology stack"
Extract: recent press releases, funding rounds, leadership changes, regulatory issues, tech partnerships.

**1c. Key people research (if contacts provided):**
Search for the contact names + company. Extract: title, role, background.
Store findings for Step 2 — do NOT write to contacts.md.

**1d. Competitive landscape:**
Search for: "{company name} competitors", "{company name} alternatives"
Store findings for Step 2 — do NOT write to competitive-intel.md.

### Step 2: Create Customer Context File

**2a. Copy the template:**
```bash
cp ~/.claude/context/_templates/customer-template.md ~/.claude/context/customer-{slug}.md
```
Where `{slug}` is the lowercased, hyphenated company name (e.g., `acme-insurance`).

**2b. Replace the header:**
Update `{CUSTOMER_NAME}` with the actual company name, `{DATE}` with today, `{SKILL}` with `demo-prep`. Delete the Usage section.

**2c. Populate ALL sections** using the context store append API. Every piece of research goes into this one file:

```bash
python3 -c "
import sys, os
sys.path.insert(0, os.path.realpath(os.path.expanduser('~/.claude/skills/_shared/engines')))
from context_utils import append_entry
append_entry('customer-{slug}.md', '{entry_text}', 'demo-prep', agent_id='demo-prep')
"
```

**Entries to create (all in customer-{slug}.md):**

| Detail tag | Content | Source |
|-----------|---------|--------|
| `company-profile` | What they do, products, market position, size | Website crawl |
| `relationship-context` | Stage: prospect, champion/buyer: TBD or from research | Research |
| `key-contacts` | Names, titles, roles of people discovered | Web/LinkedIn search |
| `vendor-ecosystem` | Tools/platforms they use (from careers page, G2, BuiltWith) | Website + search |
| `competitive-landscape` | Their competitors and how they differentiate | Web search |
| `industry-context` | Regulatory environment, market trends affecting them | Web search |
| `compliance-needs` | Industry vertical, regulatory requirements, compliance signals | Website crawl |
| `pain-signals` | Pain points mapped to your product modules | Website + search |
| `feature-fit` | Which of your modules solve their problems | Cross-ref with product-modules.md |

Use this format for each entry:
```
[{today} | source: demo-prep | {detail-tag}] confidence: low | evidence: 1
- {content line 1}
- {content line 2}
```

Confidence starts at `low` (single source: web research). Evidence starts at `1`.

### Step 3: Read Your Positioning (Not Write)

Read from shared context (your operational data) to inform the briefing:
- `positioning.md` — your value propositions, differentiators
- `product-modules.md` — your product inventory, features
- `market-taxonomy.md` — your industry categories

These are READ-ONLY. Never write demo prospect data into these files.

### Step 4: Generate Demo Briefing

Create an HTML briefing at `~/demos/{company-slug}-demo-briefing.html`.

Read the design system from `~/.claude/design-guidelines.md` for styling.

**Section 1: Company Intelligence**
- What they do, key products, market position
- Source: `company-profile` entry in customer file

**Section 2: Why They Need Us**
- Their pain points (from `pain-signals`) mapped to your product modules (from `product-modules.md`)
- Clear 1:1 mapping: "They struggle with X → Our module Y solves this"

**Section 3: Their World**
- Industry trends, regulatory landscape, competitive pressures
- Source: `industry-context`, `competitive-landscape`, `compliance-needs` entries

**Section 4: Key People**
- Contacts found, their roles, decision-making power
- Source: `key-contacts` entry in customer file

**Section 5: Recommended Demo Flow**
- Which product features to show first (based on pain-signals priority)
- Talking points per feature (connecting their pain to your solution)
- Potential objections to prepare for (from competitive-landscape)

### Step 5: Validate Demo Readiness

Check that the customer file has enough depth:

| Check | Minimum | How |
|-------|---------|-----|
| Customer file exists | 1 file | `customer-{slug}.md` exists |
| Company profile | 1 entry | Has `company-profile` detail tag |
| Pain signals | 1+ entries | Has `pain-signals` detail tag |
| Feature mapping | 1+ entries | Has `feature-fit` detail tag |
| Key contacts | 0+ entries | Optional but improves demo |

Report results:
```
Demo readiness: 4/4 checks passed

Files created:
  customer-acme-insurance.md (7 entries)

Shared context: UNTOUCHED (zero writes to shared files)

Demo briefing: ~/demos/acme-insurance-demo-briefing.html

Next steps:
  - Review: ~/demos/acme-insurance-demo-briefing.html
  - Run: meeting-prep for {contact name} at {company}
  - Open: context store dashboard to see customer file

Cleanup (after demo):
  - rm ~/.claude/context/customer-acme-insurance.md
```

## Output

1. **customer-{company}.md** — self-contained context file (the ONLY write)
2. **Demo briefing HTML** — `~/demos/{company-slug}-demo-briefing.html`
3. **Readiness report** — printed summary with next steps and cleanup command

## Cleanup

After the demo, remove the customer file:
```bash
rm ~/.claude/context/customer-{slug}.md
```
This is all that's needed. No shared context files were modified, so there's nothing else to clean up.

## Edge Cases

- **Website blocks crawling:** Fall back to web search results. Note lower confidence in entries.
- **No contacts provided:** Skip people research. Note "Key contacts: TBD" in briefing.
- **Customer file already exists:** Ask user: "customer-{slug}.md already exists. Update with new research or start fresh?" Don't overwrite without asking.
- **Sparse research results:** Still create the file with what you have. Low-confidence entries are better than no entries. Note gaps in readiness report.
- **Prospect becomes a real customer:** The customer file transitions naturally — future skills (meeting-processor, meeting-prep) will append real entries with higher confidence scores. No migration needed.

## Memory

This skill learns:
- Which research sources produce the best results per industry
- Which demo briefing sections the user finds most valuable
- Preferred demo flow structure
