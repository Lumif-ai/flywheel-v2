> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file references the legacy `~/.claude/skills/` path. Skills are now served exclusively via `flywheel_fetch_skill_assets` from the `skill_assets` table. Retained for historical reference only; runtime bundles are delivered over MCP and paths shown in this document no longer reflect the live code location.

# Execution Recipe Protocol

Execution recipes are cached extraction strategies for websites a skill has scraped before.
They store working code, selectors, behavioral knowledge, and quality baselines so repeat
visits skip DOM exploration and use a proven approach. Recipes live in
`~/.claude/context/_recipes/` as YAML files managed by `recipe_utils.py`.

---

## Recipe Format Specification

```yaml
domain: mit.edu                          # hostname, no www.
task: alumni-directory                   # see Task Type Taxonomy
strategy: innertext_parsing              # enum below
created: 2026-03-10
last_verified: 2026-03-14
last_used: 2026-03-14
use_count: 7
status: active                           # active | suspect | stale | broken

anchors:
  record_container: "main li"            # CSS path to each record
  structural_anchor: "degree connection" # text anchor for line-parsing strategies

fields:
  name:
    strategy: innertext_parsing
    anchor: "lines[0]"
    transform: null
  title:
    strategy: innertext_parsing
    anchor: "degreeIdx + 1"
    offset: 0
    transform: "split_on(' @ ', take=0)"
    derived_from: headline
  company:
    strategy: innertext_parsing
    anchor: "degreeIdx + 1"
    offset: 0
    transform: "split_on(' @ ', take=1)"
    derived_from: headline
  location:
    strategy: css_selector
    anchor: ".result-location"
    transform: "strip_prefix('Location: ')"
    fallback: ""

behaviors:
  page_load_wait: 3000                   # ms to wait after navigation
  rate_limiting: { delay_ms: 2000, jitter_ms: 500 }
  anti_bot: overlay_dismiss              # null | overlay_dismiss | captcha_pause
  spa_handling: stability_poll           # null | stability_poll | mutation_observer

quality_baseline:
  expected_records_per_page: 20
  field_fill_rates:
    name: 1.0
    title: 0.85
    company: 0.80
    location: 0.70

extraction_code: |
  () => {
    const main = document.querySelector('main');
    // ... working JS code verbatim ...
    return records;
  }

pagination:
  type: next_button                      # url_based | next_button | infinite_scroll | load_more
  pattern: null                          # URL pattern for url_based, e.g. "?page={n}"
  code: |
    const btn = document.querySelector('[aria-label="Next"]');
    return { found: !!btn, disabled: btn?.disabled };

# Optional: multi-step workflows
steps:
  - name: apply-filters
    action: interact
    interactions:
      - { selector: "#industry-filter", value: "Construction" }
      - { selector: "#search-btn", action: click }
  - name: extract-results
    action: extract
    # uses top-level extraction_code and fields
```

**Strategy enum:** `innertext_parsing`, `css_selector`, `aria_label`, `table_extraction`, `hybrid`, `multi_step`

**Transform vocabulary:** `split_on(sep, take)`, `regex_extract(pattern, group)`, `strip_prefix(prefix)`, `fallback(value)`

---

## Pre-Scrape Recipe Lookup

> **Note:** When running in Claude Code CLI, the `recipe-lookup.py` PreToolUse hook
> automatically checks the recipe store before scraping commands. The steps below are
> still the authoritative protocol — follow them in headless execution or when the hook
> hasn't fired.

Before DOM exploration (Step 2d in scraper skill), check for a cached recipe:

1. **Determine domain:** Extract hostname from URL, strip `www.` prefix
2. **Determine task:** Infer from user intent and URL pattern (see Task Type Taxonomy)
3. **Check for recipe:**
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py lookup --domain {domain} --task {task}
   ```
4. **If found** (status `active` or `suspect`): load recipe, apply behaviors, execute `extraction_code`, validate against `quality_baseline`
5. **If not found:** proceed with normal DOM exploration

---

## Post-Scrape Recipe Save

After successful extraction, decide whether to create a recipe:

1. **Check visit count:**
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py check-visits --domain {domain} --task {task}
   ```
2. **Second hit heuristic** (visit count >= 1): Build recipe YAML from working code + strategy + behaviors, save:
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py save --domain {domain} --task {task} --file /tmp/recipe.yaml
   ```
3. **First visit** (visit count == 0): Log visit only:
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py log-visit --domain {domain} --task {task}
   ```
4. **User override:** If user says "save a recipe for this site", create immediately regardless of visit count.

---

## Recipe Reuse Flow

When a recipe is found, follow these steps in order:

1. Load recipe YAML
2. Report: "Found cached recipe for {domain}:{task} (last verified {date}, {use_count} uses)"
3. Apply behaviors: set delays, wait strategies from recipe
4. Execute `extraction_code` in browser
5. Quality check: compare actual record count and field fill rates against `quality_baseline`
6. **Quality OK** -- use results, then mark verified:
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py update-verified --domain {domain} --task {task}
   ```
7. **Quality deviation** (non-zero results but count or fill rate anomaly):
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py check-staleness --domain {domain} --task {task} \
     --count {actual_count} --fill-rates '{"name": 0.95, "title": 0.80}'
   ```
   - Returns `{"status": "suspect"}`: use results, warn "Recipe quality degraded"
   - Returns `{"status": "stale"}`: discard results, fall back to fresh DOM exploration (Step 2d)
8. **Extraction fails** (throws error or returns 0 results):
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py check-staleness --domain {domain} --task {task} \
     --count 0 --error "extraction failed: {error_message}"
   ```
   - Always returns stale. Fall back to fresh DOM exploration (Step 2d).
9. **Fresh DOM exploration also fails** after a stale recipe:
   ```bash
   python3 ~/.claude/skills/_shared/recipe_utils.py mark-broken --domain {domain} --task {task} \
     --reason "both recipe and fresh exploration failed"
   ```
   - Surface error to user. Do not retry automatically.

---

## Recipe Building Guide

When creating a recipe from a successful scrape, capture:

- **domain** and **task** (from URL and user intent)
- **strategy** used (which extraction approach worked)
- **anchors** (record container selector, structural text anchors)
- **fields** with per-field strategy, selectors/offsets, transforms
- **extraction_code** (working JS code, verbatim)
- **pagination** method and code
- **behaviors** (wait times, delays, overlay handling, SPA strategies)
- **quality_baseline** (records per page from first page, field fill rates)
- Set `status: active`, `use_count: 0`

---

## Task Type Taxonomy

| Task Name | Use For |
|-----------|---------|
| `search-people` | LinkedIn people search |
| `search-companies` | LinkedIn company search |
| `connections` | LinkedIn connections list |
| `alumni-directory` | School/university alumni directories |
| `extract-list` | Generic paginated listing (default) |
| `extract-profile` | Single entity detail page |
| `directory-search` | Business/member directory with search |

Custom task names are allowed. Prefer standard names when applicable.
