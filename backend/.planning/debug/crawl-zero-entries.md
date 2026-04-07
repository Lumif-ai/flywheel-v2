---
status: fixing
trigger: "Onboarding crawl shows 0 entries deposited — company-intel engine may run but discovery events never reach the frontend SSE stream."
created: 2026-03-23T00:00:00Z
updated: 2026-03-23T17:50:00Z
---

## Current Focus

hypothesis: CONFIRMED - company_intel.py fails to import due to missing dependencies (html2text, beautifulsoup4)
test: Install missing packages, verify import, test crawl
expecting: Module loads, crawl produces discovery events
next_action: User needs to restart server and test crawl

## Symptoms

expected: Frontend shows 15-30+ items streaming in one by one during crawl, then "Discovery complete - N entries deposited"
actual: Frontend shows "Discovering intelligence..." then "Discovery complete - 0 entries deposited". No individual items appear. 3 consecutive failures.
errors: Previous "skill not found" error fixed with is_company_intel bypass, but 0 entries persists
reproduction: Go to localhost:5175/onboarding, enter URL, submit, watch crawl phase
started: After Phase 42 v4.0 runtime refactor switching filesystem to DB skill discovery

## Eliminated

## Evidence

- timestamp: 2026-03-23T17:45:00Z
  checked: Live server logs at b7bn3xjak.output
  found: "Run e3d3e453... failed (skill=company-intel): No module named 'html2text'"
  implication: The company-intel engine crashes on import before any discovery events can be emitted

- timestamp: 2026-03-23T17:46:00Z
  checked: .venv/bin/python -c "import html2text"
  found: ModuleNotFoundError - html2text not installed in venv
  implication: Confirms the server log error - package genuinely missing

- timestamp: 2026-03-23T17:47:00Z
  checked: .venv/bin/python -c "from bs4 import BeautifulSoup"
  found: ModuleNotFoundError - beautifulsoup4 also missing from venv
  implication: Second missing dependency would have caused same failure even after html2text fix

- timestamp: 2026-03-23T17:48:00Z
  checked: pyproject.toml dependencies list
  found: Neither html2text nor beautifulsoup4 listed in dependencies
  implication: These were never declared - likely assumed present from system Python or old environment

- timestamp: 2026-03-23T17:49:00Z
  checked: Full import of company_intel module after installing both packages
  found: "All company_intel imports OK" - module loads cleanly
  implication: Fix is complete at the package level

- timestamp: 2026-03-23T17:50:00Z
  checked: _execute_company_intel() logic in skill_executor.py (lines 701-900+)
  found: Code correctly emits discovery events at lines 854-858 after enrichment, writes to context store after
  implication: Once the import error is resolved, the event emission logic should work

## Resolution

root_cause: company_intel.py imports html2text (line 23) and bs4/BeautifulSoup (line 25), but neither package was declared in pyproject.toml or installed in the backend virtualenv. The Phase 42 runtime refactor created a new venv that didn't carry over these packages. Every crawl attempt fails immediately with "No module named 'html2text'" before any discovery events can be emitted, causing the frontend to show 0 entries.
fix: 1) Added html2text>=2024.2.26 and beautifulsoup4>=4.12 to pyproject.toml dependencies. 2) Installed both via uv pip install into .venv.
verification: Server restart needed - pyproject.toml change doesn't trigger --reload. User should test by submitting a URL in onboarding.
files_changed:
- pyproject.toml (added html2text and beautifulsoup4 to dependencies)
