---
name: meeting-intelligence
version: "1.0"
description: >
  Pain landscape synthesis skill. Reads accumulated per-meeting pain points,
  insights, and product feedback from the context store, identifies cross-meeting
  patterns using LLM analysis, and writes one rich entry per pain to pain-landscape.md.
  Confidence calibrated. Idempotent via deterministic upsert.
context-aware: true
triggers:
  - "/synthesize"
  - "synthesize pain landscape"
  - "run synthesis"
  - "analyze pain patterns"
  - "what are the top pains"
tags:
  - meetings
  - synthesis
  - pain-landscape
dependencies:
  skills: []
  files:
    - "~/.claude/context/_catalog.md"
    - "~/.claude/skills/_shared/context_utils.py"
output:
  - pain-landscape-entries
  - synthesis-terminal-report
  - flywheel-library-document
---

# meeting-intelligence

You are running the **pain landscape synthesis pipeline**. Your job is to read
accumulated per-meeting pain entries from three source files in the context store,
group them by underlying pain using LLM analysis, and write one confidence-calibrated
rich entry per pain to `pain-landscape.md`.

**This skill is idempotent.** Re-running will update existing entries (upsert via
deterministic detail tags) — no duplicates, no data loss.

**Trigger phrases:** `/synthesize`, "synthesize pain landscape", "run synthesis",
"analyze pain patterns", "what are the top pains", or any request to summarize
patterns across meetings.

---

## Step 0: Dependency Check (Fail Fast)

Before loading any data, verify all dependencies are available. Print FATAL and exit
if any check fails — do not proceed with incomplete setup.

```python
import sys
import os

print("=== Step 0: Dependency Check ===")

# Check 1: FlywheelClient importable
flywheel_path = os.environ.get(
    "FLYWHEEL_CLIENT_PATH",
    os.path.expanduser("~/Projects/flywheel-v2/cli")
)
if not os.path.exists(flywheel_path):
    print(f"FATAL: FlywheelClient path not found: {flywheel_path}")
    print("Fix: Ensure flywheel-v2 repo is checked out at ~/Projects/flywheel-v2")
    print("     Or set FLYWHEEL_CLIENT_PATH to the correct cli/ directory path.")
    sys.exit(1)

sys.path.insert(0, flywheel_path)
try:
    from flywheel_mcp.api_client import FlywheelClient
    print("OK: FlywheelClient importable")
except ImportError as e:
    print(f"FATAL: Cannot import FlywheelClient: {e}")
    print(f"Fix: Check that {flywheel_path}/flywheel_mcp/api_client.py exists.")
    sys.exit(1)

# Check 2: API URL
api_url = os.environ.get("FLYWHEEL_API_URL", "http://localhost:8000")
print(f"Using API: {api_url}")

# Check 3: Context store reachable
try:
    client = FlywheelClient(base_url=api_url)
    files_resp = client.list_context_files()
    n_files = len(files_resp) if isinstance(files_resp, list) else files_resp.get("count", "?")
    print(f"Context store reachable: {n_files} files")
except Exception as e:
    print(f"FATAL: Cannot reach context store at {api_url}: {e}")
    print("Fix: Ensure the Flywheel backend is running (./start-dev.sh)")
    print(f"     Verify FLYWHEEL_API_URL points to the running instance.")
    sys.exit(1)

print("All dependency checks passed. Proceeding to data load.\n")
```

---

## Step 1: Load Source Data with Pagination

Load all entries from the three source files. Source files are **read-only** — this
step never modifies them.

```python
import sys
import os
from datetime import datetime

# (client already initialized in Step 0 — reuse in the same script)

SOURCE_FILES = ["pain-points.md", "insights.md", "product-feedback.md"]
LOAD_LIMIT = 1000  # Pull all entries in one request (current API supports up to 1000)

print("=== Step 1: Load Source Data ===")

def load_all_entries(client, file_name, limit=LOAD_LIMIT):
    """Load all entries from a context store file.

    NOTE: read_context_file() accepts 'limit' but not 'offset' in the current API.
    We load with limit=1000 to capture all entries in one call. If total > 1000,
    a warning is printed — contact engineering to enable server-side pagination.
    """
    try:
        resp = client.read_context_file(file_name, limit=limit)
    except Exception as e:
        print(f"  WARNING: Could not load {file_name}: {e}")
        return []

    entries = resp.get("entries", [])
    total = resp.get("total", len(entries))
    has_more = resp.get("has_more", False)

    if has_more or total > limit:
        print(
            f"  WARNING: {file_name} has {total} entries, only first {limit} loaded. "
            f"Pagination not yet supported — contact engineering."
        )

    return entries

all_loaded = {}
for source_file in SOURCE_FILES:
    entries = load_all_entries(client, source_file)
    all_loaded[source_file] = entries
    print(f"  {source_file}: {len(entries)} entries loaded")

total_entries = sum(len(e) for e in all_loaded.values())
print(f"  Total: {total_entries} entries to synthesize\n")

# --- Data Quality Check (SYNTH-05) ---
# Validate first 5 entries from pain-points.md before proceeding.

pain_entries = all_loaded.get("pain-points.md", [])

if len(pain_entries) == 0:
    print("ERROR: No pain-points data found. Run meeting-processor first.")
    sys.exit(1)

print("Running data quality check on pain-points.md...")
sample = pain_entries[:5]
passes = 0
issues = []

for i, entry in enumerate(sample):
    # Entries may be dicts (with 'content' key) or raw strings
    content = entry.get("content", str(entry)) if isinstance(entry, dict) else str(entry)

    has_date_prefix = content.startswith("[20")
    has_speaker = any(p in content for p in ["Prospect:", "Team:", "Severity:"])
    has_severity = "Severity:" in content

    if has_date_prefix and has_speaker and has_severity:
        passes += 1
    else:
        missing = []
        if not has_date_prefix:
            missing.append("date prefix [20...")
        if not has_speaker:
            missing.append("speaker prefix (Prospect:/Team:)")
        if not has_severity:
            missing.append("Severity: field")
        issues.append(f"Entry {i+1}: missing {', '.join(missing)}")

if passes < 3:
    sample_preview = (
        content[:200] if content else "(empty)"
    )
    print(
        f"WARNING: pain-points.md format deviation detected.\n"
        f"Expected: entries with speaker prefixes (Prospect:, Team:) and Severity: fields.\n"
        f"Passed: {passes}/5 checks. Issues:\n" +
        "\n".join(f"  - {issue}" for issue in issues) + "\n"
        f"Sample content: {sample_preview}\n"
        f"Proceeding with synthesis — results may be less accurate."
    )
else:
    print(f"Data quality check passed ({passes}/5 sample entries valid).\n")
```

---

## Step 2: LLM Pain Grouping

Use Claude (via the `anthropic` SDK) to group semantically similar pains into pain
clusters. This is the core analysis step — provide all loaded entries as context.

```python
import json
import anthropic

print("=== Step 2: LLM Pain Grouping ===")

# Format entries for the LLM prompt
def format_entries_for_prompt(all_loaded):
    """Format all loaded entries as structured text for the grouping prompt."""
    lines = []
    for file_name, entries in all_loaded.items():
        lines.append(f"\n--- SOURCE: {file_name} ({len(entries)} entries) ---\n")
        for entry in entries:
            if isinstance(entry, dict):
                header = entry.get("header", "")
                content = entry.get("content", "")
                lines.append(f"{header}\n{content}\n")
            else:
                lines.append(f"{str(entry)}\n")
    return "\n".join(lines)

entries_text = format_entries_for_prompt(all_loaded)
n_pain = len(all_loaded.get("pain-points.md", []))
n_insights = len(all_loaded.get("insights.md", []))
n_feedback = len(all_loaded.get("product-feedback.md", []))
total = total_entries

GROUPING_PROMPT = f"""You are analyzing {total} raw pain point entries from prospect meetings.

Sources:
- pain-points.md: {n_pain} entries
- insights.md: {n_insights} entries
- product-feedback.md: {n_feedback} entries

Your task: Group semantically similar pains into pain clusters.

Rules:
1. Group pains that describe the same underlying problem (even if different words).
2. "audit compliance", "premium audit", "WC audit" may be one group OR separate — judge based on content overlap.
3. If ambiguous, list separately with a "Potentially related to: {{other-pain}}" note.
4. Each group must have a slug (kebab-case, max 5 words, e.g., "manual-coi-tracking").
5. For each group, extract from the raw entries:
   - All verbatim phrases (keep exact prospect language — do not paraphrase)
   - Source meeting identifiers (detail tags or dates from entry headers)
   - Speaker attribution: entries where Prospect: speaks first = unprompted; Team: speaks first = prompted
   - Workaround patterns: spreadsheets, manual, hired person, outsourced, software, accepted/ignored
   - Severity signals: count urgency phrases ("killing us", "compliance nightmare", "can't scale", "constantly breaking", "every week", "manually every time", "takes hours", "weeks")

Raw entries:
{entries_text}

Return JSON (and only JSON — no prose before or after):
{{
  "pain_groups": [
    {{
      "slug": "manual-coi-tracking",
      "label": "Manual COI Tracking",
      "mention_count": 14,
      "meeting_count": 11,
      "meeting_sources": ["acme-discovery-2026-03-11", "beta-follow-up-2026-03-14"],
      "verbatim_phrases": [
        {{"text": "spending 15-20 hrs/week on manual COI tracking", "speaker": "Sean", "urgency": true}},
        {{"text": "would be helpful to automate this", "speaker": "Michelle", "urgency": false}}
      ],
      "workarounds": [
        {{"type": "spreadsheet", "count": 3}},
        {{"type": "manual-email", "count": 4}},
        {{"type": "hired-admin", "count": 2}}
      ],
      "prompted_count": 4,
      "unprompted_count": 10,
      "urgency_phrase_count": 11,
      "total_phrases": 14,
      "potentially_related": null
    }}
  ]
}}"""

print(f"Running LLM grouping on {total} entries...")

client_ai = anthropic.Anthropic()

try:
    response = client_ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        messages=[
            {"role": "user", "content": GROUPING_PROMPT}
        ]
    )
    raw_json = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_json.startswith("```"):
        raw_json = raw_json.split("```")[1]
        if raw_json.startswith("json"):
            raw_json = raw_json[4:]
        raw_json = raw_json.strip()

    grouping_result = json.loads(raw_json)
    pain_groups = grouping_result.get("pain_groups", [])
    print(f"Identified {len(pain_groups)} pain groups from {total} entries.\n")

except json.JSONDecodeError as e:
    print(f"ERROR: LLM returned invalid JSON: {e}")
    print(f"Raw response preview: {raw_json[:500]}")
    print("Tip: Re-run /synthesize — occasional parse errors occur with very large entry sets.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: LLM API call failed: {e}")
    print("Fix: Check ANTHROPIC_API_KEY is set. Retry if transient error.")
    sys.exit(1)
```

---

## Step 3: Write Pain Entries to pain-landscape.md

For each identified pain group, construct a rich confidence-calibrated entry and
write it to `pain-landscape.md` via the context store API. Writes are idempotent:
the deterministic `(file, source, detail)` triple ensures upsert behavior — no
duplicates on re-runs.

**Source files (pain-points.md, insights.md, product-feedback.md) are never written
to in this step or any step.**

```python
from datetime import datetime

print("=== Step 3: Write Pain Entries to pain-landscape.md ===")

today = datetime.now().strftime("%Y-%m-%d")

# Confidence calibration thresholds (SYNTH-03)
def confidence_label(mention_count):
    if mention_count >= 25:
        return "high", "STRONG PATTERN"
    elif mention_count >= 10:
        return "medium", "EMERGING PATTERN"
    else:
        return "low", "EARLY SIGNAL"

ACTIVE_WORKAROUND_TYPES = {
    "spreadsheet", "manual-email", "hired-admin", "outsourced",
    "software-tool", "smartsheet", "manual"
}

URGENCY_PHRASES = [
    "killing us", "compliance nightmare", "can't scale", "cannot scale",
    "constantly breaking", "every week", "manually every time",
    "takes hours", "taking hours", "weeks", "bleeding money",
    "nightmare", "hair on fire", "critical", "broken"
]

def build_entry_body(group, total_meetings_processed):
    """Build the rich entry content body for a pain group."""
    slug = group["slug"]
    label = group["label"]
    mention_count = group["mention_count"]
    meeting_count = group["meeting_count"]
    verbatim_phrases = group.get("verbatim_phrases", [])
    workarounds = group.get("workarounds", [])
    prompted_count = group.get("prompted_count", 0)
    unprompted_count = group.get("unprompted_count", 0)
    urgency_phrase_count = group.get("urgency_phrase_count", 0)
    total_phrases = group.get("total_phrases", max(mention_count, 1))
    potentially_related = group.get("potentially_related")
    meeting_sources = group.get("meeting_sources", [])

    confidence_level, pattern_label = confidence_label(mention_count)

    # Confidence header line
    header_line = f"{pattern_label} ({mention_count} mentions across {meeting_count} meetings)"

    # Frequency line
    if total_meetings_processed > 0:
        pct = round((meeting_count / total_meetings_processed) * 100)
    else:
        pct = 0
    frequency_line = f"Frequency: Mentioned in {meeting_count} of {total_meetings_processed} external meetings ({pct}%)"

    # Prompted / unprompted line
    total_attributed = prompted_count + unprompted_count
    if total_attributed > 0:
        unprompted_pct = round((unprompted_count / total_attributed) * 100)
    else:
        unprompted_pct = 0

    hair_on_fire_unprompted = " — hair on fire" if unprompted_pct >= 70 else ""
    prompted_line = f"Prompted: {prompted_count} | Unprompted: {unprompted_count} ({unprompted_pct}% unprompted{hair_on_fire_unprompted})"

    # Severity line
    if total_phrases > 0:
        urgency_pct = round((urgency_phrase_count / total_phrases) * 100)
    else:
        urgency_pct = 0

    hair_on_fire_severity = " — HAIR ON FIRE" if urgency_pct > 70 else ""
    severity_line = f"Severity: {urgency_pct}% urgency language{hair_on_fire_severity}"

    # Language section — split into urgency and mild
    urgency_phrases_list = [p for p in verbatim_phrases if p.get("urgency")]
    mild_phrases_list = [p for p in verbatim_phrases if not p.get("urgency")]

    language_lines = []
    if urgency_phrases_list:
        language_lines.append("Language (urgency):")
        for p in urgency_phrases_list[:5]:
            language_lines.append(f'- "{p["text"]}" ({p.get("speaker", "prospect")})')
    if mild_phrases_list:
        language_lines.append("Language (mild):")
        for p in mild_phrases_list[:3]:
            language_lines.append(f'- "{p["text"]}" ({p.get("speaker", "prospect")})')
    if not language_lines:
        language_lines.append("Language: (no verbatim phrases extracted)")

    # Workarounds section
    workaround_parts = []
    active_workaround_found = False
    for w in workarounds:
        wtype = w.get("type", "unknown")
        wcount = w.get("count", 1)
        workaround_parts.append(f"{wtype} ({wcount})")
        if wtype.lower() in ACTIVE_WORKAROUND_TYPES:
            active_workaround_found = True

    workaround_text = ", ".join(workaround_parts) if workaround_parts else "None documented"
    workaround_line = f"Workarounds: {workaround_text}"

    willingness_line = ""
    if active_workaround_found:
        willingness_line = "→ PROVEN WILLINGNESS TO SPEND"

    # Source meetings
    sources_text = ""
    if meeting_sources:
        sources_text = f"Source meetings: {', '.join(meeting_sources[:10])}"
        if len(meeting_sources) > 10:
            sources_text += f" (+{len(meeting_sources) - 10} more)"

    # Potentially related
    related_text = ""
    if potentially_related:
        related_text = f"Potentially related to: {potentially_related}"

    # Synthesized_at footer
    footer = f"synthesized_at: {today} | based_on: {meeting_count} prospect meetings"

    # Assemble body
    sections = [
        header_line,
        "",
        frequency_line,
        prompted_line,
        severity_line,
        "",
        "\n".join(language_lines),
        "",
        workaround_line,
    ]
    if willingness_line:
        sections.append(willingness_line)
    if sources_text:
        sections.append("")
        sections.append(sources_text)
    if related_text:
        sections.append(related_text)
    sections.append("")
    sections.append(footer)

    return "\n".join(sections)


# Estimate total external meetings from loaded data
# Use meeting_count from the largest pain group as a proxy,
# or count unique meeting sources across all groups.
all_meeting_sources = set()
for group in pain_groups:
    for src in group.get("meeting_sources", []):
        all_meeting_sources.add(src)
total_meetings_processed = max(len(all_meeting_sources), 1)

written_count = 0
failed_count = 0

for i, group in enumerate(pain_groups, 1):
    slug = group["slug"]
    mention_count = group["mention_count"]
    confidence_level, _ = confidence_label(mention_count)

    print(f"[{i}/{len(pain_groups)}] pain: {slug}")

    entry_body = build_entry_body(group, total_meetings_processed)

    entry_content = (
        f"[{today} | source: meeting-intelligence-synthesis | pain: {slug}]\n"
        f"confidence: {confidence_level} | evidence: 1\n"
        f"{entry_body}"
    )

    try:
        client.write_context(
            file_name="pain-landscape.md",
            content=entry_content,
            source="meeting-intelligence-synthesis",
            detail=f"pain: {slug}"
        )
        print(
            f"  Written: pain: {slug} ({confidence_level} confidence, {mention_count} mentions)"
        )
        written_count += 1
    except Exception as e:
        print(f"  ERROR writing pain: {slug} — {e}")
        failed_count += 1

print(
    f"\nStep 3 complete: {written_count} entries written, "
    f"{failed_count} failed, to pain-landscape.md"
)
```

---

## Step 4: Terminal Summary Report

After all entries are written, print a structured summary and save it to the
Flywheel library.

```python
from datetime import datetime

print("\n=== Step 4: Synthesis Summary ===\n")

today = datetime.now().strftime("%Y-%m-%d")

high_confidence = [g for g in pain_groups if g["mention_count"] >= 25]
medium_confidence = [g for g in pain_groups if 10 <= g["mention_count"] < 25]
low_confidence = [g for g in pain_groups if g["mention_count"] < 10]

hair_on_fire_groups = []
for g in pain_groups:
    urgency_count = g.get("urgency_phrase_count", 0)
    total_phrases = g.get("total_phrases", max(g["mention_count"], 1))
    if total_phrases > 0 and (urgency_count / total_phrases) > 0.70:
        hair_on_fire_groups.append(g["slug"])

report_lines = [
    f"# Pain Landscape Synthesis Report",
    f"synthesized_at: {today}",
    f"based_on: {total_meetings_processed} unique meetings",
    f"entries_processed: {total_entries} ({n_pain} pain-points, {n_insights} insights, {n_feedback} product-feedback)",
    f"",
    f"## Pain Groups Identified: {len(pain_groups)}",
    f"",
    f"### Strong Pattern (25+ mentions)",
]
for g in high_confidence:
    report_lines.append(f"- **{g['slug']}**: {g['mention_count']} mentions across {g['meeting_count']} meetings")

report_lines.append(f"\n### Emerging Pattern (10-25 mentions)")
for g in medium_confidence:
    report_lines.append(f"- **{g['slug']}**: {g['mention_count']} mentions across {g['meeting_count']} meetings")

report_lines.append(f"\n### Early Signal (<10 mentions)")
for g in low_confidence:
    report_lines.append(f"- **{g['slug']}**: {g['mention_count']} mentions across {g['meeting_count']} meetings")

if hair_on_fire_groups:
    report_lines.append(f"\n## Hair on Fire Pains (>70% urgency language)")
    for slug in hair_on_fire_groups:
        report_lines.append(f"- {slug}")

report_lines.extend([
    f"",
    f"## Write Results",
    f"- Written: {written_count} entries",
    f"- Failed: {failed_count} entries",
    f"- Target file: pain-landscape.md",
    f"",
    f"---",
    f"*Generated by meeting-intelligence v1.0 | {today}*",
])

report_text = "\n".join(report_lines)
print(report_text)

# Save to Flywheel library (via flywheel_save_document MCP tool)
# Claude Code: call flywheel_save_document with the report text
print("\nSave this report to the Flywheel library:")
print("  flywheel_save_document(")
print(f'    title="Pain Landscape Synthesis {today}",')
print(f'    content=report_text,')
print(f'    document_type="synthesis-report"')
print("  )")
print("\nSynthesis complete.")
```
