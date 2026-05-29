#!/usr/bin/env python3
"""Phase 152.1 Plan 02 Task 2 -- mechanical rewrite of broker-*/SKILL.md bodies.

Rewrites four surfaces across the 10 broker-*/SKILL.md files:

  (A) Python import headers:
          import sys, os[, X]
          sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
          import api_client
          [import field_validator]
      ->
          import os[, X]
          from flywheel.broker import api_client[, field_validator]

  (B) Memory-Update sections (heading body):
          `~/.claude/skills/broker/auto-memory/broker.md` append
      ->
          `flywheel_write_context(file_name="broker", ...)` MCP call

  (C) Frontmatter `dependencies.files:` cleanup:
        - Drop `~/.claude/skills/broker/*.py` / `*.yaml` entries
        - Add `dependencies.python_packages: ["flywheel-ai>=0.4.0"]`
          (uses existing `python_packages` key for consistency with parse-policies)

  (D) /broker:fill-portal portal invocation + process-project step references:
        - `~/.claude/skills/broker/portals/mapfre.py` path -> pip namespace / `python -m`
        - `~/.claude/skills/broker/steps/<step>.md` references in process-project ->
          invoke `/broker:<step>` slash trigger instead

Idempotent: running twice produces zero additional changes. Post-rewrite guard
fails loudly if any legacy pattern (sys.path.insert + ~/.claude/skills/broker, the
auto-memory path, or flat-form `from flywheel_broker import`) survives.

Usage:
    python3 scripts/rewrite_broker_skill_bodies.py [--dry-run] [--verbose]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BROKER_SKILLS = [
    "broker-parse-contract",
    "broker-parse-policies",
    "broker-gap-analysis",
    "broker-select-carriers",
    "broker-fill-portal",
    "broker-draft-emails",
    "broker-extract-quote",
    "broker-draft-recommendation",
    "broker-process-project",
    "broker-compare-quotes",
]

# ---------------------------------------------------------------------------
# Concern A: Python import headers
# ---------------------------------------------------------------------------
#
# Three block variants observed across the 10 files (whitespace-exact from source):
#
#   (A1) both helpers:
#           import sys, os[, X]
#           sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
#           import api_client
#           import field_validator
#
#   (A2) api_client only:
#           import sys, os[, X]
#           sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
#           import api_client
#
#   (A3) field_validator only:
#           import sys, os[, X]
#           sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
#           import field_validator
#
# We handle the `import sys, os[, X]` prefix generically (capture trailing ", X"
# segment so `import sys, os, uuid` becomes `import os, uuid`).

_PREFIX = r"import\s+sys,\s*os(?P<extra>(?:,\s*\w+)*)\s*\n"
_SPI = r"""sys\.path\.insert\(\s*0,\s*os\.path\.expanduser\(\s*["']~/\.claude/skills/broker/["']\s*\)\s*\)\s*\n"""

# A1 -- both helpers, order: api_client then field_validator
_RE_A1 = re.compile(
    _PREFIX + _SPI + r"import\s+api_client\s*\nimport\s+field_validator\s*\n",
    re.MULTILINE,
)

# A2 -- api_client only
_RE_A2 = re.compile(
    _PREFIX + _SPI + r"import\s+api_client\s*\n",
    re.MULTILINE,
)

# A3 -- field_validator only
_RE_A3 = re.compile(
    _PREFIX + _SPI + r"import\s+field_validator\s*\n",
    re.MULTILINE,
)


def _replace_a1(m: re.Match) -> str:
    extra = m.group("extra") or ""
    return f"import os{extra}\nfrom flywheel.broker import api_client, field_validator\n"


def _replace_a2(m: re.Match) -> str:
    extra = m.group("extra") or ""
    return f"import os{extra}\nfrom flywheel.broker import api_client\n"


def _replace_a3(m: re.Match) -> str:
    extra = m.group("extra") or ""
    return f"import os{extra}\nfrom flywheel.broker import field_validator\n"


def _rewrite_imports(body: str) -> tuple[str, int]:
    """Rewrite import blocks. Order matters: A1 must be tried before A2.

    Returns (new_body, replacement_count).
    """
    # Try A1 (two helpers) first -- its pattern is a strict superset of A2's,
    # so applying A2 first would split it into two partial matches.
    new_body, n1 = _RE_A1.subn(_replace_a1, body)
    new_body, n2 = _RE_A2.subn(_replace_a2, new_body)
    new_body, n3 = _RE_A3.subn(_replace_a3, new_body)
    return new_body, n1 + n2 + n3


# ---------------------------------------------------------------------------
# Concern B: Memory-Update section
# ---------------------------------------------------------------------------

_MEMORY_HEADING_RE = re.compile(
    r"^(#{2,3})\s*(?:Step\s*\d+\s*:\s*)?Memory\s+Update(?:\s*\([^)]*\))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Per-skill memory content hints (skill_slug -> (skill_label, summary_hint))
_MEMORY_HINTS: dict[str, tuple[str, str]] = {
    "broker-parse-contract": (
        "parse-contract",
        "{n_coverages} coverages, insurance={n_insurance}, surety={n_surety}",
    ),
    "broker-parse-policies": (
        "parse-policies",
        "{n_policies} policies parsed for project {PROJECT_ID}",
    ),
    "broker-gap-analysis": (
        "gap-analysis",
        "{n_gaps} gaps identified across {n_coverages} coverages",
    ),
    "broker-select-carriers": (
        "select-carriers",
        "selected {n_carriers} carriers ({n_portal} portal, {n_email} email) for project {PROJECT_ID}",
    ),
    "broker-fill-portal": (
        "fill-portal",
        "{carrier} portal filled for project {PROJECT_ID} ({n_coverages} coverages)",
    ),
    "broker-draft-emails": (
        "draft-emails",
        "{n_emails} emails drafted to {n_carriers} carriers for project {PROJECT_ID}",
    ),
    "broker-extract-quote": (
        "extract-quote",
        "{n_line_items} line items extracted from {carrier} quote ({total_premium} {currency})",
    ),
    "broker-draft-recommendation": (
        "draft-recommendation",
        "recommendation drafted ranking {n_quotes} quotes for project {PROJECT_ID}",
    ),
    "broker-process-project": (
        "process-project",
        "pipeline executed end-to-end -- {n_stages}/6 stages completed for project {PROJECT_ID}",
    ),
    "broker-compare-quotes": (
        "compare-quotes",
        "compared {n_quotes} quotes across {n_coverages} coverages for project {PROJECT_ID}",
    ),
}


def _build_memory_body(skill_slug: str) -> str:
    label, hint = _MEMORY_HINTS[skill_slug]
    return (
        "After this step succeeds, persist a session summary to the Flywheel context store\n"
        "via the MCP tool `mcp__flywheel__flywheel_write_context`:\n"
        "\n"
        "- `file_name=\"broker\"`\n"
        "- `content` = a short markdown summary of what was done (project id, key metrics,\n"
        "  and the skill-specific signals -- see example below)\n"
        "\n"
        "Example call shape:\n"
        "\n"
        "```python\n"
        "mcp__flywheel__flywheel_write_context(\n"
        "    file_name=\"broker\",\n"
        "    content=(\n"
        f"        \"## {label} -- {{today}}\\n\"\n"
        f"        \"- Project {{PROJECT_ID}}: {hint}\\n\"\n"
        "    ),\n"
        ")\n"
        "```\n"
        "\n"
        "Do NOT append to any local file -- the context store is the durable home for skill memory.\n"
    )


def _rewrite_memory_section(body: str, skill_slug: str) -> tuple[str, bool]:
    """Replace the Memory-Update section body (keeps heading).

    Section terminates at next top-level `## ` heading OR a horizontal rule `---`
    line OR end-of-file. Code-fence state is tracked so that `## ...` lines
    inside ```fenced blocks``` do NOT count as the next heading.
    """
    lines = body.splitlines(keepends=True)
    heading_idx: int | None = None
    in_fence = False
    for i, line in enumerate(lines):
        raw = line.rstrip("\n")
        # Track code fences (both ``` and ~~~ variants)
        if re.match(r"^\s*(?:```|~~~)", raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _MEMORY_HEADING_RE.match(raw):
            heading_idx = i
            break
    if heading_idx is None:
        return body, False

    # Walk forward from heading_idx+1 to find section end, again respecting fences.
    end_idx = len(lines)
    in_fence = False
    for j in range(heading_idx + 1, len(lines)):
        raw = lines[j].rstrip("\n")
        if re.match(r"^\s*(?:```|~~~)", raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = raw.strip()
        if stripped == "---" or stripped.startswith("## "):
            end_idx = j
            break

    new_body_text = _build_memory_body(skill_slug)
    # Preserve heading line + blank line + new body + blank line before next section
    new_section = [lines[heading_idx], "\n", new_body_text, "\n"]
    new_lines = lines[:heading_idx] + new_section + lines[end_idx:]
    return "".join(new_lines), True


# ---------------------------------------------------------------------------
# Concern C: Frontmatter dependencies.files: cleanup
# ---------------------------------------------------------------------------


def _rewrite_frontmatter(full_text: str) -> tuple[str, bool]:
    """Edit the YAML frontmatter block in-place using targeted regex.

    Rules:
      - Remove lines of the form `    - "~/.claude/skills/broker/*"` under
        `dependencies.files:`.
      - If the `files:` list becomes empty (no list items left), remove
        the `files:` key entirely.
      - If `dependencies:` becomes empty (no subkeys), remove it entirely.
      - Ensure `dependencies.python_packages:` contains `"flywheel-ai>=0.4.0"`
        (appends if missing; uses existing python_packages list if present).
    """
    fm_match = re.match(r"^---\n(.*?\n)---\n", full_text, re.DOTALL)
    if not fm_match:
        return full_text, False

    fm_text = fm_match.group(1)
    original_fm = fm_text

    # (1) Remove broker-file list items under dependencies.files:
    fm_text = re.sub(
        r'^\s+-\s*"~/\.claude/skills/broker/[^"]+"\s*\n',
        "",
        fm_text,
        flags=re.MULTILINE,
    )

    # (2) If `files:` key is now followed immediately by a non-list line (i.e., it has
    # no items), remove the `files:` line. Detection: `  files:\n` followed by a
    # non-indented-list line.
    fm_text = re.sub(
        r"^\s*files:\s*\n(?=\s*(?:python_packages:|python:|skills:|[a-z]\w*:\s*|[-]|\Z)|---\n)",
        "",
        fm_text,
        flags=re.MULTILINE,
    )

    # Also clean up the case where `files:` sits at the tail of `dependencies:`
    # (next non-indented key or frontmatter end).
    # Remove `  files:\n` if the next line is dedented (no leading 4-space list item).
    fm_text = re.sub(
        r"^(\s+)files:\s*\n(?!(?:\1)?\s+-\s)",
        "",
        fm_text,
        flags=re.MULTILINE,
    )

    # (3) Ensure dependencies.python_packages: ["flywheel-ai>=0.4.0"] exists.
    if "flywheel-ai>=0.4.0" not in fm_text and "flywheel-ai >= 0.4.0" not in fm_text:
        if re.search(r"^dependencies:\s*\n", fm_text, re.MULTILINE):
            if re.search(r"^\s+python_packages:\s*\n", fm_text, re.MULTILINE):
                # Append flywheel-ai entry to existing python_packages list
                fm_text = re.sub(
                    r"^(\s+python_packages:\s*\n(?:\s+-\s.*\n)*)",
                    lambda m: m.group(1) + '    - "flywheel-ai>=0.4.0"\n',
                    fm_text,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                # Insert new python_packages sublist at the end of the `dependencies:` block.
                # Find the dependencies block: from `dependencies:\n` until next top-level key
                # (non-whitespace at column 0) or end of frontmatter.
                def _inject(match: re.Match) -> str:
                    block = match.group(0)
                    # If block already trails with newline, inject before the final newline.
                    if not block.endswith("\n"):
                        block += "\n"
                    return block + '  python_packages:\n    - "flywheel-ai>=0.4.0"\n'

                fm_text = re.sub(
                    r"^dependencies:\s*\n(?:[ \t]+.*\n)*",
                    _inject,
                    fm_text,
                    count=1,
                    flags=re.MULTILINE,
                )
        else:
            # No dependencies: block yet -- add one before the closing frontmatter line.
            fm_text = (
                fm_text.rstrip("\n")
                + "\ndependencies:\n"
                + "  python_packages:\n"
                + '    - "flywheel-ai>=0.4.0"\n'
            )

    # (4) If `dependencies:` is now empty (no subkeys under it), drop it.
    fm_text = re.sub(
        r"^dependencies:\s*\n(?=[a-zA-Z_][^\n]*:|---|\Z)",
        "",
        fm_text,
        flags=re.MULTILINE,
    )

    changed = fm_text != original_fm
    if not changed:
        return full_text, False

    new_full = "---\n" + fm_text + "---\n" + full_text[fm_match.end():]
    return new_full, True


# ---------------------------------------------------------------------------
# Concern D: Portal + step-reference rewrites
# ---------------------------------------------------------------------------


def _rewrite_fill_portal(body: str) -> tuple[int, str]:
    """Rewrite /broker:fill-portal portal invocation paths.

    Four concerns, each targeted:
      (D1) Python dep-check block that probes the existence of ``mapfre.py`` as
           a local file: replace with ``importlib.util.find_spec`` namespace probe.
      (D2) Narrative references to ``~/.claude/skills/broker/portals/mapfre.py``
           -> ``flywheel.broker.portals.mapfre`` (plain namespace reference, no
           backtick nesting).
    """
    total = 0

    # (D1) Replace the mapfre_path var + path-exists check with a pip-namespace probe.
    d1_pattern = re.compile(
        r'mapfre_path\s*=\s*os\.path\.expanduser\(\s*"~/\.claude/skills/broker/portals/mapfre\.py"\s*\)\s*\n'
        r"if\s+not\s+os\.path\.exists\(\s*mapfre_path\s*\)\s*:\s*\n"
        r"\s+missing\.append\([^)]+\)\s*\n",
        re.MULTILINE,
    )
    d1_replacement = (
        "# Namespace probe: flywheel-ai ships the mapfre portal as a pip module\n"
        "from importlib.util import find_spec as _find_spec\n"
        'if _find_spec("flywheel.broker.portals.mapfre") is None:\n'
        '    missing.append("flywheel.broker.portals.mapfre (run: pip install --upgrade flywheel-ai)")\n'
    )
    body, n_d1 = d1_pattern.subn(d1_replacement, body)
    total += n_d1

    # Also clean up the trailing log line that references `{mapfre_path}`
    body, n_d1b = re.subn(
        r"print\(\s*f\"mapfre\.py found at:\s*\{\s*mapfre_path\s*\}\"\s*\)\s*\n",
        'print("mapfre portal importable: flywheel.broker.portals.mapfre")\n',
        body,
    )
    total += n_d1b

    # (D2) Narrative references to the old local mapfre.py path (inside backticks
    # in prose / block quotes). Replace with the pip namespace path.
    body, n_d2 = re.subn(
        r"~/\.claude/skills/broker/portals/mapfre\.py",
        "flywheel.broker.portals.mapfre",
        body,
    )
    total += n_d2

    return total, body


def _rewrite_process_project_step_refs(body: str) -> tuple[int, str]:
    """Rewrite the `Follow the instructions in ~/.claude/skills/broker/steps/X.md`
    lines in broker-process-project to use the slash-command trigger instead.

    Returns (num_replacements, new_body). Applies only to matches of that specific
    narrative pattern.
    """
    pattern = re.compile(
        r"Follow the instructions in\s+~/\.claude/skills/broker/steps/([a-z-]+)\.md",
    )

    def _repl(m: re.Match) -> str:
        step = m.group(1)
        return f"Invoke the `/broker:{step}` skill (router dispatches via MCP fetch)"

    new, n = pattern.subn(_repl, body)
    return n, new


def _rewrite_sibling_skill_refs(body: str) -> tuple[int, str]:
    """Rewrite `Follow the instructions in ~/.claude/skills/broker-<slug>/SKILL.md`
    references (used by pipeline skills like broker-compare-quotes) to slash-command
    invocation. Matches the process-project rewrite style.

    Returns (num_replacements, new_body).
    """
    pattern = re.compile(
        r"Follow the instructions in\s+~/\.claude/skills/broker-([a-z-]+)/SKILL\.md",
    )

    def _repl(m: re.Match) -> str:
        step = m.group(1)
        return f"Invoke the `/broker:{step}` skill (router dispatches via MCP fetch)"

    new, n = pattern.subn(_repl, body)
    return n, new


# ---------------------------------------------------------------------------
# Per-file driver
# ---------------------------------------------------------------------------


def rewrite_file(path: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """Rewrite a single SKILL.md file. Returns per-concern counts."""
    slug = path.parent.name
    original = path.read_text(encoding="utf-8")
    body = original

    # Split frontmatter from body so Concerns B+D never touch the frontmatter.
    fm_match = re.match(r"^(---\n.*?\n---\n)", body, re.DOTALL)
    if fm_match:
        frontmatter_raw = fm_match.group(1)
        body_only = body[fm_match.end():]
    else:
        frontmatter_raw = ""
        body_only = body

    # Concern A: import headers (body-only)
    body_only, imports_n = _rewrite_imports(body_only)

    # Concern B: Memory-Update section (body-only)
    body_only, memory_changed = _rewrite_memory_section(body_only, slug)

    # Concern D: portal / step-refs (skill-specific; body-only)
    portal_n = 0
    step_refs_n = 0
    if slug == "broker-fill-portal":
        portal_n, body_only = _rewrite_fill_portal(body_only)
    if slug == "broker-process-project":
        step_refs_n, body_only = _rewrite_process_project_step_refs(body_only)
    if slug == "broker-compare-quotes":
        # compare-quotes pipeline references sibling skill SKILL.md files; same
        # rewrite pattern as process-project but different URL shape.
        step_refs_n, body_only = _rewrite_sibling_skill_refs(body_only)

    # Re-stitch frontmatter + body for Concern C, which edits only the frontmatter block.
    body = frontmatter_raw + body_only
    body, fm_changed = _rewrite_frontmatter(body)

    changes_made = body != original

    if not dry_run and changes_made:
        path.write_text(body, encoding="utf-8")

    return {
        "slug": slug,
        "imports_replaced": imports_n,
        "memory_updated": memory_changed,
        "frontmatter_cleaned": fm_changed,
        "portal_rewrites": portal_n,
        "step_refs_rewritten": step_refs_n,
        "changes_made": changes_made,
    }


# ---------------------------------------------------------------------------
# Post-rewrite guards
# ---------------------------------------------------------------------------


def _post_rewrite_guards() -> int:
    """Scan all 10 SKILL.md files for surviving legacy patterns. Returns 0 on pass."""
    failed = False
    for slug in BROKER_SKILLS:
        path = REPO / "skills" / slug / "SKILL.md"
        if not path.exists():
            print(f"FAIL: {path} missing")
            failed = True
            continue
        body = path.read_text(encoding="utf-8")
        # Body-only check -- frontmatter `depends_on: ["broker"]` and other non-import
        # mentions of "broker" elsewhere are fine. We specifically look for the legacy
        # patterns the rewrite was supposed to kill.
        if "sys.path.insert" in body and "~/.claude/skills/broker" in body:
            print(f"FAIL: {slug} still has sys.path.insert + ~/.claude/skills/broker")
            failed = True
        if "auto-memory/broker.md" in body:
            print(f"FAIL: {slug} still references auto-memory/broker.md")
            failed = True
        if "from flywheel_broker import" in body:
            print(
                f"FAIL: {slug} uses flat form 'from flywheel_broker import' "
                "-- must use dot form 'from flywheel.broker import'"
            )
            failed = True
        # Extra guard: no `~/.claude/skills/broker/*.py` file references should remain in the body
        # (frontmatter file paths are handled separately)
        if re.search(r"~/\.claude/skills/broker/[a-z_/]+\.py", body):
            print(f"FAIL: {slug} still references ~/.claude/skills/broker/*.py files")
            failed = True
    if failed:
        return 1
    print("PASS: no legacy patterns remaining across 10 broker-* skill bodies.")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    totals = {
        "imports": 0,
        "memory": 0,
        "frontmatter": 0,
        "portal": 0,
        "step_refs": 0,
        "files_changed": 0,
    }

    for slug in BROKER_SKILLS:
        path = REPO / "skills" / slug / "SKILL.md"
        if not path.exists():
            print(f"SKIP: {path} not found")
            continue
        result = rewrite_file(path, dry_run=args.dry_run, verbose=args.verbose)
        totals["imports"] += result["imports_replaced"]
        totals["memory"] += 1 if result["memory_updated"] else 0
        totals["frontmatter"] += 1 if result["frontmatter_cleaned"] else 0
        totals["portal"] += result["portal_rewrites"]
        totals["step_refs"] += result["step_refs_rewritten"]
        totals["files_changed"] += 1 if result["changes_made"] else 0
        print(f"  {slug}: {result}")

    print(f"\nTotals: {totals}")
    if args.dry_run:
        print("(dry-run -- no files modified)")
        return 0

    return _post_rewrite_guards()


if __name__ == "__main__":
    sys.exit(main())
