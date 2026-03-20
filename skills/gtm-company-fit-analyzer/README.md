# claude-skill-company-fit-analyzer

A Claude Code skill that researches and scores companies as potential clients using deep web crawling + AI inference.

## What it does
- Builds a custom fit profile by interviewing you about your business (once per session)
- Deep-crawls each company's website, LinkedIn, job postings, and case studies
- Scores every company 0–100 with tier labels (Strong Fit / Moderate Fit / Low Fit / No Fit)
- Checks the Do Not Contact list and deduplicates against previously scored companies
- Finds the right decision maker and their LinkedIn profile
- Drafts personalized email + LinkedIn DM for every Strong Fit and Moderate Fit company
- Works with a list of names, URLs, or an existing CSV

## Works great for
- Qualifying inbound leads before calling
- Prioritizing a long list of prospects
- Adding fit scores + outreach to a scraped CSV
- Evaluating whether a specific company is worth pursuing

## Installation
```bash
mkdir -p ~/.claude/skills
unzip gtm-company-fit-analyzer.skill -d ~/.claude/skills/
claude mcp add playwright -- npx @playwright/mcp
# Restart Claude Code
```

## Usage

### Direct invocation
```
/company-fit-analyzer
```

### Natural language
- *"Score these companies for fit against my profile"*
- *"Is Acme Corp a good prospect for us?"*
- *"Research these leads and tell me which ones to prioritize"*
- *"Score my CSV of companies"*

## Output columns (added to your CSV)
`Website_Found` · `Fit_Score` · `Fit_Tier` · `Fit_Reasoning` · `Top_Fit_Signal` · `Top_Concern` · `Est_Employees` · `DM_Name` · `DM_Title` · `DM_LinkedIn` · `Email_Subject` · `Email_Body` · `LinkedIn_DM` · `Crawl_Status`

## Tier definitions
| Tier | Score | Meaning |
|------|-------|---------|
| Strong Fit | 75–100 | Strong match to ICP, reach out this week |
| Moderate Fit | 50–74 | Good signals, worth pursuing |
| Low Fit | 25–49 | Marginal, low priority |
| No Fit | <25 | Not a fit or disqualifier confirmed |
| Unscored | — | Not yet evaluated |

## Requirements
- Claude Code
- Node.js
- Playwright MCP (`claude mcp add playwright -- npx @playwright/mcp`)

## Related skills
- **gtm-web-scraper-extractor** — scrape a directory into a CSV first, then score it
- **gtm-leads-pipeline** — run scraping + scoring end-to-end in a single session
- **gtm-outbound-messenger** — send the scorer's drafted messages to qualified leads
