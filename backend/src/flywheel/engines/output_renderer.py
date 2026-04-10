"""
output_renderer.py - Output rendering pipeline for skill results.

Transforms raw skill text output into structured, professional HTML documents.
Each skill type has a purpose-built template; unknown types fall back to generic.

Public API:
    sanitize_html(html) -> str
    detect_output_type(skill_name) -> str
    parse_output_sections(raw_output) -> dict
    extract_key_facts(sections) -> list
    render_output(skill_name, raw_output, attribution, templates_dir) -> str
    render_output_standalone(skill_name, raw_output, attribution, templates_dir) -> str
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML sanitization (allowlist-based XSS protection)
# ---------------------------------------------------------------------------

from bs4 import BeautifulSoup

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "strong", "em", "b", "i", "u", "s", "code", "pre", "blockquote",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
    "dl", "dt", "dd",
    "sup", "sub",
}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
DANGEROUS_PROTOCOLS = {"javascript", "vbscript", "data"}


def sanitize_html(html: str) -> str:
    """Allowlist-based HTML sanitizer. Strips disallowed tags and attributes.

    Uses BeautifulSoup4 to parse HTML and remove:
    - Tags not in ALLOWED_TAGS (via decompose -- removes tag AND contents)
    - Attributes not in ALLOWED_ATTRS for that tag
    - href/src values using dangerous protocols (javascript:, vbscript:, data:)
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.decompose()
            continue
        allowed = ALLOWED_ATTRS.get(tag.name, set())
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag[attr]
        for url_attr in ("href", "src"):
            if url_attr in tag.attrs:
                val = tag[url_attr].strip().lower()
                if any(val.startswith(p + ":") for p in DANGEROUS_PROTOCOLS):
                    del tag[url_attr]
    return str(soup)


# ---------------------------------------------------------------------------
# Output type detection
# ---------------------------------------------------------------------------

TYPE_MAP = {
    "meeting-prep": "meeting_brief",
    "ctx-meeting-prep": "meeting_brief",
    "legal-review": "legal_review",
    "ctx-legal-review": "legal_review",
    "gtm-outbound-messenger": "outreach_batch",
    "ctx-gtm-outbound-messenger": "outreach_batch",
    "investor-update": "investor_update",
    "ctx-investor-update": "investor_update",
    "company-fit-analyzer": "competitive_analysis",
    "ctx-company-fit-analyzer": "competitive_analysis",
    "one-pager": "one_pager",
    "ctx-one-pager": "one_pager",
}


def detect_output_type(skill_name: str) -> str:
    """Map skill name to output template type. Returns 'generic' for unknown skills."""
    if not skill_name:
        return "generic"
    return TYPE_MAP.get(skill_name.strip().lower(), "generic")


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- delimited block at start of content)."""
    if not text or not text.lstrip().startswith("---"):
        return text
    # Find the closing ---
    stripped = text.lstrip()
    end = stripped.find("---", 3)
    if end == -1:
        return text
    # Skip past closing --- and any trailing newline
    after = stripped[end + 3:]
    return after.lstrip("\n")


def parse_output_sections(raw_output: str) -> dict:
    """Parse markdown-style output into structured sections.

    Splits on ## headings. Content before the first heading goes into an
    'Overview' section. Returns dict with 'sections' list, 'raw' string,
    and 'section_count' int.
    """
    if not raw_output or not raw_output.strip():
        return {"sections": [], "raw": raw_output or "", "section_count": 0}

    # Strip YAML frontmatter if present
    raw_output = _strip_frontmatter(raw_output)

    lines = raw_output.split("\n")
    sections = []
    current_title = None
    current_lines = []

    for line in lines:
        heading_match = re.match(r"^##\s+(.+)$", line)
        if heading_match:
            # Save previous section
            if current_title is not None or current_lines:
                _save_section(sections, current_title, current_lines)
            current_title = heading_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_title is not None or current_lines:
        _save_section(sections, current_title, current_lines)

    # If no headings found, wrap everything as a single section
    if not sections:
        content = raw_output.strip()
        if content:
            bullet_items = _extract_items(content)
            sections.append({
                "title": "Overview",
                "content": content,
                "bullet_items": bullet_items,
            })

    return {
        "sections": sections,
        "raw": raw_output,
        "section_count": len(sections),
    }


def _save_section(sections: list, title: Optional[str], lines: list):
    """Build a section dict from title and collected lines.

    Strips leading/trailing blank lines from the content block so that
    the markdown converter doesn't produce spurious <br> tags at the
    boundaries of each section.
    """
    # Drop leading blank lines (common after a ## heading)
    while lines and not lines[0].strip():
        lines = lines[1:]
    # Drop trailing blank lines
    while lines and not lines[-1].strip():
        lines = lines[:-1]

    content = "\n".join(lines)
    if not title and not content:
        return
    title = title or "Overview"
    bullet_items = _extract_items(content)
    sections.append({
        "title": title,
        "content": content,
        "bullet_items": bullet_items,
    })


def _extract_items(content: str) -> list:
    """Extract bullet-point items from content text.

    Handles nested lists by detecting indentation level (2 or 4 spaces)
    and prefixing sub-items with an indent marker so templates can
    distinguish hierarchy when needed.
    """
    items = []
    for line in content.split("\n"):
        stripped = line.strip()
        # Detect indentation depth (number of leading spaces / 2)
        leading = len(line) - len(line.lstrip())
        depth = leading // 2  # 0 = top-level, 1 = sub-item, 2 = sub-sub-item

        if stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:].strip()
            if depth > 0:
                items.append({"text": text, "depth": depth})
            else:
                items.append(text)
        elif re.match(r"^\d+\.\s+", stripped):
            text = re.sub(r"^\d+\.\s+", "", stripped).strip()
            if depth > 0:
                items.append({"text": text, "depth": depth})
            else:
                items.append(text)
    return items


# ---------------------------------------------------------------------------
# Key facts extraction
# ---------------------------------------------------------------------------

def extract_key_facts(sections: list) -> list:
    """Extract key-value pairs from sections for sidebar/summary cards.

    Looks for patterns like:
      **Label:** Value
      - Label: Value
      Label: Value (at start of line)
    """
    facts = []
    seen = set()

    for section in sections:
        content = section.get("content", "")
        for line in content.split("\n"):
            stripped = line.strip()

            # Pattern: **Label:** Value  or  - **Label**: Value
            match = re.match(r"^[-*]?\s*\*\*(.+?)\*\*[:\s]+(.+)", stripped)
            if match:
                label = match.group(1).strip().rstrip(":")
                value = re.sub(r"\*\*(.+?)\*\*", r"\1", match.group(2).strip())
                key = label.lower()
                if key not in seen and value:
                    facts.append({"label": label, "value": value})
                    seen.add(key)
                continue

            # Pattern: - Label: Value (bullet with colon)
            match = re.match(r"^[-*]\s+(.+?):\s+(.+)", stripped)
            if match:
                label = match.group(1).strip()
                value = match.group(2).strip()
                # Skip if label is too long (probably a sentence, not a key)
                if len(label) <= 40:
                    key = label.lower()
                    if key not in seen and value:
                        facts.append({"label": label, "value": value})
                        seen.add(key)

    return facts


# ---------------------------------------------------------------------------
# Meeting-prep-specific post-processing
# ---------------------------------------------------------------------------

# Key facts to surface in the sidebar for meeting briefs.
# Maps lowercase label prefixes to display labels.
_MEETING_BRIEF_FACT_LABELS = {
    "education": "Education",
    "location": "Location",
    "founded": "Founded",
    "scale": "Scale",
    "revenue": "Revenue",
    "core": "Core Business",
    "languages": "Languages",
    "title": "Title",
    "company": "Company",
}


def _extract_meeting_contacts(sections: list) -> list:
    """Extract contact cards from 'Who He Is' / 'Who She Is' / profile sections.

    Looks for **Name** | Title, Company patterns and structured bullet lists
    with Name:, Title:, Email:, LinkedIn: fields.
    """
    contacts = []
    for section in sections:
        content = section.get("content", "")
        title_lower = section.get("title", "").lower()

        # Pattern 1: **Name** | Title | Company on the FIRST non-empty line
        if "who" in title_lower or "profile" in title_lower or "background" in title_lower or "contact" in title_lower:
            first_line = ""
            for cline in content.split("\n"):
                if cline.strip():
                    first_line = cline.strip()
                    break
            if "|" in first_line and "**" in first_line:
                parts = [p.strip() for p in first_line.split("|")]
                name = re.sub(r"\*\*(.+?)\*\*", r"\1", parts[0]).strip()
                title_str = parts[1].strip() if len(parts) > 1 else ""
                company = parts[2].strip() if len(parts) > 2 else ""
                if name and len(name) < 60:
                    contact = {"name": name, "title": title_str}
                    if company:
                        contact["title"] = f"{title_str}, {company}" if title_str else company
                    contacts.append(contact)

        # Pattern 2: structured list with - Name:, - Title:, - Email:
        name = title = email = linkedin = None
        for line in content.split("\n"):
            stripped = line.strip()
            m = re.match(r"^[-*]\s+\*?\*?Name\*?\*?[:\s]+(.+)", stripped, re.I)
            if m:
                name = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(1)).strip()
            m = re.match(r"^[-*]\s+\*?\*?Title\*?\*?[:\s]+(.+)", stripped, re.I)
            if m:
                title = m.group(1).strip()
            m = re.match(r"^[-*]\s+\*?\*?Email\*?\*?[:\s]+(.+)", stripped, re.I)
            if m:
                email = m.group(1).strip()
            m = re.match(r"^[-*]\s+\*?\*?LinkedIn\*?\*?[:\s]+(.+)", stripped, re.I)
            if m:
                linkedin = m.group(1).strip()

        if name and not any(c["name"] == name for c in contacts):
            contacts.append({
                "name": name,
                "title": title or "",
                "email": email,
                "linkedin": linkedin,
            })

    return contacts


def _curate_meeting_key_facts(sections: list, all_facts: list) -> list:
    """Select the most relevant key facts for a meeting brief sidebar.

    Prioritizes structured profile fields (Education, Location, Scale, etc.)
    and caps at 8 items to keep the sidebar clean.
    """
    curated = []
    seen = set()

    # First pass: grab priority facts by label
    for fact in all_facts:
        label_lower = fact["label"].lower().rstrip(":")
        for prefix, display in _MEETING_BRIEF_FACT_LABELS.items():
            if label_lower.startswith(prefix) and prefix not in seen:
                curated.append({"label": display, "value": fact["value"]})
                seen.add(prefix)
                break

    # Second pass: fill remaining slots (up to 8) with other facts
    for fact in all_facts:
        if len(curated) >= 8:
            break
        label_lower = fact["label"].lower().rstrip(":")
        if not any(label_lower.startswith(p) for p in seen):
            curated.append(fact)
            seen.add(label_lower)

    return curated


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _load_jinja2_env(templates_dir: str):
    """Create a Jinja2 Environment from the given templates directory."""
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        raise ImportError(
            "Jinja2 is required for output rendering. "
            "Install with: pip install Jinja2"
        )
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=True,
    )

    # Add markdown-to-HTML filter for rendering raw markdown in templates
    def _md_to_html(text):
        """Convert markdown text to HTML. Handles bold, italic, links, lists."""
        if not text:
            return ""
        try:
            import markdown as _md
            from markupsafe import Markup
            # Extensions:
            #   extra     - tables, fenced code, footnotes, attr_list, etc.
            #   sane_lists - prevents a bullet list from being interrupted by
            #                a different list type; gives cleaner nested lists
            #   nl2br     - converts single newlines to <br>, matching how
            #                most users expect markdown to render
            #   smarty    - typographic quotes and dashes
            html = _md.markdown(
                str(text),
                extensions=["extra", "sane_lists", "nl2br", "smarty"],
                # LLM output typically uses 2-space indent for nested lists;
                # the default tab_length=4 causes nested items to flatten.
                tab_length=2,
            )
            html = sanitize_html(html)
            return Markup(html)
        except ImportError:
            # Fallback: best-effort regex conversion when markdown lib missing
            import re as _re
            from markupsafe import Markup
            text = str(text)

            # --- Headings (### h3, ## h2 etc.) ---
            text = _re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', text, flags=_re.MULTILINE)
            text = _re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', text, flags=_re.MULTILINE)
            text = _re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', text, flags=_re.MULTILINE)
            text = _re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', text, flags=_re.MULTILINE)

            # --- Bold / italic ---
            text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

            # --- Unordered list blocks ---
            def _convert_ul(m):
                block = m.group(0)
                items = _re.findall(r'^[ \t]*[-*]\s+(.+)$', block, _re.MULTILINE)
                li = "".join(f"<li>{item}</li>" for item in items)
                return f"<ul>{li}</ul>"
            text = _re.sub(
                r'(?:^[ \t]*[-*]\s+.+$\n?)+',
                _convert_ul,
                text,
                flags=_re.MULTILINE,
            )

            # --- Ordered list blocks ---
            def _convert_ol(m):
                block = m.group(0)
                items = _re.findall(r'^\d+\.\s+(.+)$', block, _re.MULTILINE)
                li = "".join(f"<li>{item}</li>" for item in items)
                return f"<ol>{li}</ol>"
            text = _re.sub(
                r'(?:^\d+\.\s+.+$\n?)+',
                _convert_ol,
                text,
                flags=_re.MULTILINE,
            )

            # --- Links: [text](url) ---
            text = _re.sub(
                r'\[([^\]]+)\]\(([^)]+)\)',
                r'<a href="\2">\1</a>',
                text,
            )

            # --- Horizontal rules ---
            text = _re.sub(r'^---+$', '<hr>', text, flags=_re.MULTILINE)

            # --- Remaining newlines to <br> (skip lines already wrapped in block tags) ---
            text = _re.sub(r'\n(?!<)', '<br>\n', text)

            text = sanitize_html(text)
            return Markup(text)

    env.filters["md"] = _md_to_html
    return env


def render_output(
    skill_name: str,
    raw_output: str,
    attribution: Optional[dict] = None,
    templates_dir: Optional[str] = None,
) -> str:
    """Render skill output as an HTML fragment using the appropriate template.

    Args:
        skill_name: Name of the skill that produced the output.
        raw_output: Raw text output from skill execution.
        attribution: Dict of {filename: entry_count} showing context sources.
        templates_dir: Path to templates directory. Defaults to src/templates/.

    Returns:
        Rendered HTML string (fragment, not full document).
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")

    attribution = attribution or {}
    output_type = detect_output_type(skill_name)

    # Structured JSON output path — skills like one-pager output JSON directly.
    # Convention: structured skill outputs MUST include "schema_version" at the
    # top level for detection.  The value is a semver string (e.g. "1.0").
    # Templates receive the parsed dict as `structured_data` in their context.
    structured_data = None
    if raw_output and raw_output.strip().startswith("{"):
        try:
            import json as _json
            candidate = _json.loads(raw_output)
            if isinstance(candidate, dict) and candidate.get("schema_version"):
                structured_data = candidate
        except (ValueError, TypeError):
            pass

    parsed = parse_output_sections(raw_output)
    key_facts = extract_key_facts(parsed["sections"])

    env = _load_jinja2_env(templates_dir)

    # Try specific template, fall back to generic
    template_path = f"outputs/{output_type}.html"
    try:
        template = env.get_template(template_path)
    except Exception:
        logger.info(
            "Template %s not found, falling back to generic", template_path
        )
        template = env.get_template("outputs/generic.html")

    # Detect enriched vs raw attribution format
    if isinstance(attribution, dict) and "total_entries" in attribution:
        # Enriched format from build_attribution()
        total_entries = attribution.get("total_entries", 0)
        total_files = attribution.get("total_files", 0)
        source_skills = attribution.get("source_skills", [])
        compound_depth = attribution.get("compound_depth", 0)
        file_pills = attribution.get("files", [])
    else:
        # Legacy raw format: {filename: count}
        total_entries = sum(attribution.values()) if attribution else 0
        total_files = len(attribution) if attribution else 0
        source_skills = []
        compound_depth = 0
        file_pills = [
            {"name": k, "entry_count": v, "description": ""}
            for k, v in (attribution or {}).items()
        ]

    # Meeting-prep-specific post-processing
    contacts = []
    if output_type == "meeting_brief":
        contacts = _extract_meeting_contacts(parsed["sections"])
        key_facts = _curate_meeting_key_facts(parsed["sections"], key_facts)

    return template.render(
        sections=parsed["sections"],
        key_facts=key_facts,
        raw=parsed["raw"],
        attribution=attribution,
        file_pills=file_pills,
        skill_name=skill_name,
        output_type=output_type,
        section_count=parsed["section_count"],
        total_entries=total_entries,
        total_files=total_files,
        source_skills=source_skills,
        compound_depth=compound_depth,
        contacts=contacts,
        structured_data=structured_data,
    )


def render_output_standalone(
    skill_name: str,
    raw_output: str,
    attribution: Optional[dict] = None,
    templates_dir: Optional[str] = None,
) -> str:
    """Render skill output as a full standalone HTML document with inline CSS.

    Suitable for standalone viewing, PDF export, or email embedding.
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")

    # Render the output fragment
    fragment = render_output(skill_name, raw_output, attribution, templates_dir)

    # Read CSS for inline embedding
    css_path = os.path.join(
        os.path.dirname(__file__), "static", "css", "outputs.css"
    )
    flywheel_css_path = os.path.join(
        os.path.dirname(__file__), "static", "css", "flywheel.css"
    )

    css_parts = []
    for path in [flywheel_css_path, css_path]:
        try:
            with open(path, "r") as f:
                css_parts.append(f.read())
        except FileNotFoundError:
            logger.warning("CSS file not found: %s", path)

    css_inline = "\n".join(css_parts)

    # Format skill name for display
    display_name = skill_name.replace("ctx-", "").replace("-", " ").title()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{display_name} - Flywheel Output</title>
  <style>
{css_inline}
  </style>
</head>
<body>
  <div class="output-standalone">
    <div class="output-container">
      {fragment}
    </div>
  </div>
</body>
</html>"""
