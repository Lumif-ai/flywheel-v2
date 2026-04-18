> **⚠ DEPRECATED (Phase 152 — 2026-04-19):** This file references the legacy `~/.claude/skills/` path. Skills are now served exclusively via `flywheel_fetch_skill_assets` from the `skill_assets` table. Retained for historical reference only; runtime bundles are delivered over MCP and paths shown in this document no longer reflect the live code location.

# Context Store Protocol

This file defines how context-aware skills discover and use the shared context store
at `~/.claude/context/`. The catalog (`_catalog.md`) is the routing table -- read it
first, write through it always.

---

## Pre-Read Protocol

> **Note:** When running in Claude Code CLI, the `pre-read-context.py` SessionStart hook
> automatically injects a context snapshot at session start. The steps below are still
> the authoritative protocol — follow them when the hook hasn't fired (headless execution,
> first-time setup) or when you need deeper context than the snapshot provides.

Before executing your main task, load relevant context:

1. **Read the catalog:** Load `~/.claude/context/_catalog.md` to get the file inventory
   with Tags, Status, Description, and consumer/enricher relationships.

2. **Match tags to your task domain:**
   - Outreach task --> files tagged `outreach`, `people`, `competitors`
   - Contract review --> files tagged `customer`, `product`
   - Content creation --> files tagged `content`, `market`, `product`
   - Meeting prep --> files tagged `people`, `sales`, `competitors`, `customer`

3. **Skip empty files:** If a file's Status column is `empty`, it has no entries. Skip it.

4. **Load recent entries:** For each relevant file, read up to **10 most recent entries**
   (bottom of file). Do not load entire files into context -- manage your context window.

5. **Customer auto-discovery:** If the task mentions or implies a specific customer,
   check for `customer-{name}.md` in the catalog. Load it if it exists.
   If no customer is mentioned, skip all customer-specific files.

6. **Positioning is always relevant:** `positioning.md` applies to nearly every
   outward-facing task. Include it unless the task is purely internal.

---

## Post-Write Protocol

After completing work, capture new knowledge for the shared store:

1. **Identify new knowledge:** Contacts found, insights extracted, patterns noticed,
   competitive signals, pricing data, objections heard, feature requests, etc.

2. **Find the target file:** Match the knowledge to a catalog file using Tags and
   Description columns. One piece of knowledge = one target file.

3. **Check for duplicates:** Before writing, scan the target file for entries with the
   same source + same detail keyword + same date. If a match exists, skip the write.

4. **Write using the standard entry format** (see Entry Format Reference below).
   (Format is also validated by the `post-write-validate.py` PostToolUse hook.)

5. **One entry per distinct observation.** Do not bundle unrelated knowledge into a
   single entry. A meeting that surfaces a contact AND a pain point = two entries
   in two different files.

---

## Post-Run Verification

> **Note:** When running in Claude Code CLI, the `cost-verify.py` Stop hook automatically
> verifies declared writes at session end. The steps below are still the authoritative
> protocol — follow them in headless execution or when you need explicit verification.

After completing all writes, verify that declared writes actually happened:

1. **Check your SKILL.md `writes:` list** -- these are the files you declared you'd write to.

2. **Call verify_writes** to check the event log:
```bash
python3 ~/.claude/skills/_shared/context_utils.py verify-writes \
  --agent-id {your-skill-name} --declared contacts.md,insights.md [--since-minutes 10]
```

3. **If missing writes are reported:** Log a warning at the end of your output:
   `Warning: Declared write to {file} did not execute. Data may not have compounded.`

4. **Do NOT retry LLM-generated writes** -- the content is no longer available.
   Only retry mechanical writes where the engine has the data.

---

## Knowledge Overflow

When knowledge does not fit any existing catalog file:

1. Append to `~/.claude/context/_inbox.md` using this format:
   ```
   [YYYY-MM-DD | source: {skill-name} | inbox-proposal]
   - **Proposed file:** {suggested-filename.md}
   - **Reasoning:** {why this doesn't fit existing files}
   - **Content:** {the actual knowledge}
   ```

2. Surface the inbox write at the END of your run output. Never pause mid-task to ask
   about file placement.

3. **The compounding test:** "Would another skill ever want this?"
   - Yes --> write to `_inbox.md` (or the correct context file if one exists)
   - No, genuinely skill-specific config --> `references/` directory in your skill folder

---

## Entry Format Reference

The standard context store entry format:

```
[YYYY-MM-DD | source: {skill-name} | {detail-tag}] confidence: {level} | evidence: {N}
- Content line 1
- Content line 2
```

**Field rules:**

| Field | Values | Notes |
|-------|--------|-------|
| `source` | skill name | e.g., `meeting-processor`, `legal-doc-advisor` |
| `detail-tag` | short descriptor | e.g., `acme-corp-meeting`, `contract-review-insight` |
| `confidence` | `low`, `medium`, `high` | low = single observation, medium = corroborated, high = well-established |
| `evidence` | integer starting at 1 | Increment when corroborated by additional observations |

- Content lines: prefixed with `- `, concise, factual
- No raw transcripts or unprocessed dumps
- Max entry size: 4000 characters

---

## What NOT to Write

Do not write these to the context store:

- **Session-specific temporary data** -- scratch work, intermediate calculations
- **Raw unprocessed content** -- full transcripts, raw HTML, complete documents
- **Skill-specific configuration** -- templates, schemas, format specs (use `references/`)
- **Duplicate information** -- already captured in another entry with same meaning
- **Speculative or unverified claims** -- wait until you have at least one concrete signal

---

## Programmatic Interface

The protocol above is implemented as a Python utility at `~/.claude/skills/_shared/context_utils.py`.
Skills can use it for consistent, testable context store operations.

### CLI Commands

```bash
# Pre-read: load relevant context by tags
python3 ~/.claude/skills/_shared/context_utils.py pre-read --tags sales,outreach [--customer acme] [--json]

# Append entry with dedup + backup
python3 ~/.claude/skills/_shared/context_utils.py append contacts.md \
  --source meeting-prep --detail "contact: john-smith" \
  --content "- Name: John Smith\n- Title: CTO" \
  [--confidence low] [--evidence 1]

# Check for duplicate before writing
python3 ~/.claude/skills/_shared/context_utils.py check-dup contacts.md \
  --source meeting-prep --detail "contact: john-smith" [--date 2026-03-13]

# Browse catalog (optionally filter by tags)
python3 ~/.claude/skills/_shared/context_utils.py catalog [--tags sales] [--json]

# Verify declared writes happened (post-run check)
python3 ~/.claude/skills/_shared/context_utils.py verify-writes \
  --agent-id meeting-prep --declared contacts.md,insights.md [--since-minutes 10]
```

### Python API (when imported)

```python
import sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/_shared"))
from context_utils import pre_read, post_write, append_entry, check_duplicate, format_entry

# Pre-read
ctx = pre_read(tags=["sales", "outreach"], customer="acme")
# ctx["entries"] = {"contacts.md": [...], "positioning.md": [...]}

# Append with dedup + backup
result = append_entry("contacts.md", entry_text)
# result = {"status": "written"|"duplicate"|"error", "path": "...", "backup": "..."}

# Batch post-write
results = post_write(knowledge_items=[...], source="meeting-prep")
```

Skills should use the CLI interface during execution (via bash) or import the module directly
when building Python scripts. Both interfaces implement the same protocol with identical
dedup, backup, and format enforcement.
