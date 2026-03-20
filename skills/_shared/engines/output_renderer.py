"""
output_renderer.py - Output rendering pipeline for skill results.

Transforms raw skill text output into structured, professional HTML documents.
Each skill type has a purpose-built template; unknown types fall back to generic.

Public API:
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
}


def detect_output_type(skill_name: str) -> str:
    """Map skill name to output template type. Returns 'generic' for unknown skills."""
    if not skill_name:
        return "generic"
    return TYPE_MAP.get(skill_name.strip().lower(), "generic")


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def parse_output_sections(raw_output: str) -> dict:
    """Parse markdown-style output into structured sections.

    Splits on ## headings. Content before the first heading goes into an
    'Overview' section. Returns dict with 'sections' list, 'raw' string,
    and 'section_count' int.
    """
    if not raw_output or not raw_output.strip():
        return {"sections": [], "raw": raw_output or "", "section_count": 0}

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
    """Build a section dict from title and collected lines."""
    content = "\n".join(lines).strip()
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
    """Extract bullet-point items from content text."""
    items = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            items.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
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

            # Pattern: **Label:** Value
            match = re.match(r"\*\*(.+?)\*\*[:\s]+(.+)", stripped)
            if match:
                label = match.group(1).strip().rstrip(":")
                value = match.group(2).strip()
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
            html = _md.markdown(str(text), extensions=["extra"])
            return Markup(html)
        except ImportError:
            # Fallback: at minimum convert **bold** and newlines
            import re as _re
            from markupsafe import Markup
            text = str(text)
            text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            text = text.replace('\n', '<br>')
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
        contacts=[],
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
