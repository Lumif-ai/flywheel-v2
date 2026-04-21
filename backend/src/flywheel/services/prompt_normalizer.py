"""Serve-time prompt normalizer for MCP callers.

When a skill prompt is fetched via ``?mode=mcp``, this module rewrites
server-side / internal tool names into the MCP tool names and native client
capabilities that Claude Code / Claude Desktop actually expose.

The four passes MUST run in this exact order:

1. **Prefix strip** -- remove ``mcp__flywheel__`` so downstream passes see
   canonical ``flywheel_*`` names.
2. **MCP tool-name map** -- rename legacy / server-side tool names to
   their MCP equivalents (12 mappings).
3. **Native capability map** -- replace tool names that correspond to
   built-in client features (7 mappings, e.g. ``web_search`` -> ``WebSearch``).
4. **Doc-block replacement** -- swap full "Available Tools" documentation
   sections (used by call-intelligence, meeting-prep, meeting-processor)
   with MCP-format equivalents.

No data is mutated on disk -- normalization is applied only to the HTTP
response body.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Pass 1 -- strip ``mcp__flywheel__`` prefix
# ---------------------------------------------------------------------------
# Lookahead ensures we only strip when followed by a canonical flywheel_ name.
_PREFIX_RE = re.compile(r"mcp__flywheel__(?=flywheel_)")

# ---------------------------------------------------------------------------
# Pass 2 -- server-side tool name -> MCP tool name
# ---------------------------------------------------------------------------
_TOOL_NAME_MAP: dict[str, str] = {
    "context_read": "flywheel_read_context",
    "read_context": "flywheel_read_context",
    "context_write": "flywheel_write_context",
    "append_entry": "flywheel_write_context",
    "context_query": "flywheel_read_context",
    "flywheel_list_leads": "flywheel_list_pipeline",
    "flywheel_upsert_lead": "flywheel_upsert_pipeline_entry",
    "flywheel_add_lead_contact": "flywheel_add_pipeline_contact",
    "flywheel_draft_lead_message": "flywheel_draft_pipeline_message",
    "flywheel_send_lead_message": "flywheel_send_pipeline_message",
    "flywheel_graduate_lead": "flywheel_upsert_pipeline_entry",
    "flywheel_fetch_account": "flywheel_fetch_pipeline_entry",
}

# ---------------------------------------------------------------------------
# Pass 3 -- server-side tool name -> native client capability
# ---------------------------------------------------------------------------
_NATIVE_CAPABILITY_MAP: dict[str, str] = {
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "file_write": "Write",
    "file_read": "Read",
    "read_file": "Read",
    "write_file": "Write",
    "python_execute": "Bash",
}

# ---------------------------------------------------------------------------
# Pass 4 -- full "Available Tools" doc-block replacement
# ---------------------------------------------------------------------------
_MCP_TOOLS_BLOCK = (
    '- **flywheel_read_context**: Search the context store. '
    'Call with query="company-intel" to search for entries.\n'
    '- **flywheel_write_context**: Write to context store. '
    'Call with file_name="company-intel", content="your content".\n'
    "- **WebSearch**: Search the web. Use your built-in web search capability.\n"
    "- **WebFetch**: Fetch and extract text from a URL. "
    "Use your built-in web fetch capability.\n"
    "- **Write**: Save generated output to a file. "
    "Use your native file write capability."
)

# Match from ``- **context_read**:`` through ``- **file_write**:`` plus rest
# of that final line.
_DOC_BLOCK_RE = re.compile(
    r"- \*\*context_read\*\*:.*?- \*\*file_write\*\*:[^\n]*",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Pre-compiled replacement regexes (longest key first to avoid substring
# collisions, word-boundary anchored to prevent partial matches).
# ---------------------------------------------------------------------------


def _build_replacement_list(
    mapping: dict[str, str],
) -> list[tuple[re.Pattern[str], str]]:
    """Return ``(compiled_regex, replacement)`` pairs sorted longest-key-first."""
    pairs: list[tuple[re.Pattern[str], str]] = []
    for old in sorted(mapping, key=len, reverse=True):
        pairs.append((re.compile(rf"\b{re.escape(old)}\b"), mapping[old]))
    return pairs


_TOOL_NAME_REPLACEMENTS = _build_replacement_list(_TOOL_NAME_MAP)
_NATIVE_REPLACEMENTS = _build_replacement_list(_NATIVE_CAPABILITY_MAP)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_for_mcp(prompt: str) -> str:
    """Apply 4-pass normalization to *prompt* and return the result.

    Returns an empty string when *prompt* is ``None`` or empty.
    """
    if not prompt:
        return ""

    # Pass 1 -- strip mcp__flywheel__ prefix
    text = _PREFIX_RE.sub("", prompt)

    # Pass 2 -- MCP tool-name mapping
    for pattern, replacement in _TOOL_NAME_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    # Pass 3 -- native capability mapping
    for pattern, replacement in _NATIVE_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    # Pass 4 -- doc-block replacement
    text = _DOC_BLOCK_RE.sub(_MCP_TOOLS_BLOCK, text)

    return text
