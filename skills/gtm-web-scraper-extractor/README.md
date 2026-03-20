# claude-skill-web-scraper

A Claude Code skill that extracts structured data from any website into a CSV using the Playwright MCP browser.

## What it does
- Scrapes contacts, alumni, attendees, leads, or any records from any URL
- Handles login-gated sites (you log in manually, Claude does the rest)
- Pagination, infinite scroll, AJAX/SPA sites
- Resumable sessions — pick up where you left off
- Deduplication, error logging, post-processing
- Multi-search-term runs with merged output

## Works great for
- LinkedIn connections — your own, or from any other profile
- Alumni directories (MIT, Harvard, etc.)
- Conference attendee lists (Luma, Whova, Eventbrite)
- Any business or people directory

## Installation
```bash
# 1. Clone or download this repo
mkdir -p ~/.claude/skills
git clone https://github.com/Sharan0516/claude-skill-web-scraper.git ~/.claude/skills/web-scraper-extractor

# 2. Add Playwright MCP
claude mcp add playwright -- npx @playwright/mcp

# 3. Restart Claude Code, then say:
# "Set up the web scraper prerequisites"
```

## Usage
Just describe what you want in Claude Code:
- *"Extract all contacts from this URL into a CSV"*
- *"Scrape my LinkedIn connections into a spreadsheet"*
- *"Go to linkedin.com/in/username and extract 10 of their connections with name, title, company, location"*
- *"Resume the scraping session from yesterday"*

## LinkedIn Notes

**Scraping another person's connections:**
Point Claude at a LinkedIn profile URL and ask for their connections. Claude will find the
`connectionOf` search URL automatically and extract the results.

**Login:**
The Playwright browser is an **isolated session** — it does not share cookies with your
regular browser. You must log in to LinkedIn (or any other site) inside the Playwright
browser window before scraping begins.

**CSS selectors:** LinkedIn changes its frontend frequently. This skill uses `innerText`
line-parsing instead of CSS class selectors, making it robust to LinkedIn UI updates.

## Requirements
- Claude Code
- Node.js
- Python 3
- Playwright MCP server (`npx @playwright/mcp`)

## Changelog

### 2026-03-02
- Added LinkedIn playbook for scraping **another person's connections** (not just your own)
- Replaced fragile CSS-class extraction with `innerText` line-parsing for LinkedIn search results
- Added headline parsing logic for all LinkedIn headline formats (`@ Company`, `at Company`, free-form)
- Added explicit note: Playwright browser is an isolated session, separate from your regular browser
- Added LinkedIn-specific row to Error Recovery cheatsheet
