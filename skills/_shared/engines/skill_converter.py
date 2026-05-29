"""
skill_converter.py - SKILL.md parser and execution spec generator.

Converts SKILL.md files into structured ExecutionSpec objects for headless
execution. Extracts system prompts, tool definitions, parameter declarations,
and contract enforcement data from skill frontmatter and body.

Public API:
    convert_skill(skill_name, skills_dir) -> ExecutionSpec
    build_system_prompt(name, description, body) -> str
    generate_tool_definitions(spec_data) -> list[dict]
    extract_parameters(spec_data) -> list[dict]
    extract_contract(spec_data, body) -> dict
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import frontmatter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SYSTEM_PROMPT_CHARS = 16000  # ~4000 tokens

# Engine registry: skill names that have Python engines in src/
ENGINE_REGISTRY = {
    "meeting-prep": "meeting_prep",
    "ctx-meeting-prep": "meeting_prep",
    "meeting-processor": "meeting_processor",
    "ctx-meeting-processor": "meeting_processor",
    "gtm-my-company": "gtm_company",
    "ctx-gtm-my-company": "gtm_company",
    "gtm-pipeline": "gtm_pipeline",
    "investor-update": "investor_update",
    "ctx-investor-update": "investor_update",
    "company-intel": "company_intel",
}

# Sections to strip from system prompt (low-value for execution)
_STRIP_SECTION_PATTERNS = [
    r"(?i)^#+\s*changelog\b",
    r"(?i)^#+\s*version\s*history\b",
    r"(?i)^#+\s*revision\s*log\b",
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExecutionSpec:
    """Structured representation of a skill for headless execution."""

    name: str
    description: str
    system_prompt: str
    parameters: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    contract: dict = field(default_factory=lambda: {"reads": ["*"], "writes": ["*"]})
    has_engine: bool = False
    token_budget: int = 50000
    skill_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def convert_skill(
    skill_name: str, skills_dir: Optional[Path] = None
) -> ExecutionSpec:
    """Convert a SKILL.md file into an ExecutionSpec for headless execution.

    Args:
        skill_name: Name of the skill directory (e.g. 'meeting-prep').
        skills_dir: Root directory containing skill subdirectories.
            Defaults to ~/.claude/skills.

    Returns:
        Populated ExecutionSpec.

    Raises:
        FileNotFoundError: If the SKILL.md file does not exist.
    """
    if skills_dir is None:
        # DEPRECATED (Phase 152 — 2026-04-19): legacy ~/.claude/skills/ path; skills are served via flywheel_fetch_skill_assets. Retained for developer tooling only; no runtime impact.
        skills_dir = Path.home() / ".claude" / "skills"

    skill_path = skills_dir / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"SKILL.md not found: {skill_path}")

    post = frontmatter.load(str(skill_path))

    name = post.get("name", skill_name)
    description = post.get("description", "")
    if isinstance(description, str):
        description = description.strip()

    parameters = extract_parameters(post)
    contract = extract_contract(post, post.content)
    tools = generate_tool_definitions(post)
    system_prompt = build_system_prompt(name, description, post.content)
    has_engine = skill_name in ENGINE_REGISTRY
    token_budget = post.get("token_budget", 50000)

    return ExecutionSpec(
        name=name,
        description=description,
        system_prompt=system_prompt,
        parameters=parameters,
        tools=tools,
        contract=contract,
        has_engine=has_engine,
        token_budget=token_budget,
        skill_path=skill_path,
    )


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def build_system_prompt(name: str, description: str, body: str) -> str:
    """Build a focused system prompt from SKILL.md body content.

    Extracts actionable sections, strips changelog/version history,
    truncates overly long examples, and caps at ~4000 tokens.

    Args:
        name: Skill name.
        description: Skill description.
        body: Raw SKILL.md body text (everything after frontmatter).

    Returns:
        Composed system prompt string.
    """
    # Role instruction prefix
    role = f"You are executing the {name} skill. {description}"

    # Context store instructions
    context_instructions = (
        "\n\nYou have access to the flywheel context store via tools. "
        "Use read_context to read company knowledge (positioning, contacts, "
        "competitive intel, etc.). Use append_entry to write new intelligence "
        "back to the context store. Always specify the file name and provide "
        "a clear detail description for each entry."
    )

    # Process body: strip low-value sections
    processed = _strip_sections(body)

    # Truncate long examples (code blocks > 20 lines)
    processed = _truncate_long_examples(processed)

    # Compose prompt
    prompt = role + context_instructions + "\n\n---\n\n" + processed.strip()

    # Cap at MAX_SYSTEM_PROMPT_CHARS
    if len(prompt) > MAX_SYSTEM_PROMPT_CHARS:
        prompt = _truncate_prompt(prompt, role, context_instructions, processed)

    return prompt


# ---------------------------------------------------------------------------
# Tool definition generator
# ---------------------------------------------------------------------------


def generate_tool_definitions(spec_data) -> list:
    """Generate Claude API tool definitions from a SKILL.md post.

    Always includes read_context and append_entry. Conditionally adds
    web_search and file tools based on skill declarations.

    Args:
        spec_data: A frontmatter.Post object (or dict-like with .content).

    Returns:
        List of tool definition dicts in Anthropic tool use format.
    """
    tools = [
        {
            "name": "read_context",
            "description": (
                "Read entries from a context store file. Returns all entries "
                "from the specified file, sorted by date. Use this to access "
                "company knowledge like positioning, contacts, competitive intel."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Context file name, e.g. 'positioning.md', 'contacts.md'",
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional search query to filter entries",
                    },
                },
                "required": ["file"],
            },
        },
        {
            "name": "append_entry",
            "description": (
                "Write a new entry to a context store file. The entry will be "
                "validated, deduplicated, and atomically written."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Context file name to write to",
                    },
                    "content": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Content lines for the entry",
                    },
                    "detail": {
                        "type": "string",
                        "description": "Brief description of what this entry contains",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Confidence level of this information",
                    },
                },
                "required": ["file", "content", "detail"],
            },
        },
    ]

    # Web tools always available (research is core to most skills)
    tools.append(
        {
            "name": "web_search",
            "description": (
                "Search the web using DuckDuckGo. Returns search results "
                "with titles, URLs, and snippets. Use this to find information "
                "about people, companies, industries, news."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, e.g. 'Chris Horney InstallerNet CEO'",
                    }
                },
                "required": ["query"],
            },
        }
    )
    tools.append(
        {
            "name": "web_fetch",
            "description": (
                "Fetch a URL and extract readable text content. Use this to "
                "read web pages, LinkedIn profiles, company websites, articles. "
                "Returns plain text content from the page."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch, e.g. 'https://www.example.com'",
                    }
                },
                "required": ["url"],
            },
        }
    )

    body = getattr(spec_data, "content", "")
    metadata = spec_data if hasattr(spec_data, "get") else {}
    writes = metadata.get("writes", []) if hasattr(metadata, "get") else []
    reads = metadata.get("reads", []) if hasattr(metadata, "get") else []

    # Check if skill needs file access
    needs_files = _skill_needs_files(body, metadata)
    if needs_files:
        tools.append(
            {
                "name": "read_file",
                "description": "Read a file from the filesystem.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to read",
                        }
                    },
                    "required": ["path"],
                },
            }
        )
        tools.append(
            {
                "name": "write_file",
                "description": "Write content to a file on the filesystem.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file",
                        },
                    },
                    "required": ["path", "content"],
                },
            }
        )

    return tools


# ---------------------------------------------------------------------------
# Parameter extractor
# ---------------------------------------------------------------------------


def extract_parameters(spec_data) -> list:
    """Extract structured parameter declarations from SKILL.md frontmatter.

    Each parameter should have at least 'name' and 'prompt' fields.

    Args:
        spec_data: A frontmatter.Post or dict-like with parameter data.

    Returns:
        List of parameter dicts with keys: name, required, type,
        memory_key (optional), prompt.
    """
    raw_params = spec_data.get("parameters", None)
    if not raw_params or not isinstance(raw_params, list):
        return []

    parameters = []
    for param in raw_params:
        if not isinstance(param, dict):
            continue
        # Must have at least name and prompt
        if "name" not in param or "prompt" not in param:
            logger.warning(
                "Skipping parameter missing name or prompt: %s", param
            )
            continue
        parameters.append(
            {
                "name": param["name"],
                "required": param.get("required", False),
                "type": param.get("type", "string"),
                "memory_key": param.get("memory_key"),
                "prompt": param["prompt"],
            }
        )

    return parameters


# ---------------------------------------------------------------------------
# Contract extractor
# ---------------------------------------------------------------------------


def extract_contract(spec_data, body: str) -> dict:
    """Extract context store contract (reads/writes) from SKILL.md.

    Resolution order:
    1. Explicit reads/writes in frontmatter
    2. WRITE_TARGETS in body text
    3. Context Store section references
    4. Fallback to wildcard access

    Args:
        spec_data: A frontmatter.Post or dict-like.
        body: SKILL.md body text.

    Returns:
        Dict with 'reads' and 'writes' lists.
    """
    reads = spec_data.get("reads", None)
    writes = spec_data.get("writes", None)

    # If both present in frontmatter, use them directly
    if reads is not None and writes is not None:
        return {
            "reads": reads if isinstance(reads, list) else [reads],
            "writes": writes if isinstance(writes, list) else [writes],
        }

    # Try extracting from body text
    extracted_writes = _extract_write_targets_from_body(body)
    extracted_reads = _extract_context_refs_from_body(body)

    if reads is None:
        reads = extracted_reads if extracted_reads else ["*"]
    if writes is None:
        writes = extracted_writes if extracted_writes else ["*"]

    if reads == ["*"] and writes == ["*"]:
        logger.warning(
            "No contract declarations found for skill; using wildcard access"
        )

    return {
        "reads": reads if isinstance(reads, list) else [reads],
        "writes": writes if isinstance(writes, list) else [writes],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_sections(body: str) -> str:
    """Remove changelog, version history, and revision log sections."""
    lines = body.split("\n")
    result = []
    skip = False
    skip_level = 0

    for line in lines:
        # Check if this line starts a section to strip
        should_strip = False
        for pattern in _STRIP_SECTION_PATTERNS:
            if re.match(pattern, line.strip()):
                should_strip = True
                # Determine heading level
                match = re.match(r"^(#+)", line.strip())
                skip_level = len(match.group(1)) if match else 1
                break

        if should_strip:
            skip = True
            continue

        if skip:
            # Stop skipping when we hit a heading of same or higher level
            match = re.match(r"^(#+)\s", line.strip())
            if match and len(match.group(1)) <= skip_level:
                skip = False
            else:
                continue

        result.append(line)

    return "\n".join(result)


def _truncate_long_examples(body: str, max_lines: int = 20) -> str:
    """Truncate code blocks longer than max_lines."""
    lines = body.split("\n")
    result = []
    in_code_block = False
    code_block_lines = []
    code_fence = ""

    for line in lines:
        if not in_code_block:
            if line.strip().startswith("```"):
                in_code_block = True
                code_fence = line
                code_block_lines = [line]
            else:
                result.append(line)
        else:
            code_block_lines.append(line)
            if line.strip().startswith("```") and len(code_block_lines) > 1:
                # End of code block
                in_code_block = False
                if len(code_block_lines) > max_lines + 2:  # +2 for fences
                    result.append(code_fence)
                    result.extend(code_block_lines[1 : max_lines + 1])
                    result.append("# ... (truncated)")
                    result.append("```")
                else:
                    result.extend(code_block_lines)
                code_block_lines = []

    # Handle unclosed code block
    if code_block_lines:
        result.extend(code_block_lines)

    return "\n".join(result)


def _truncate_prompt(
    prompt: str, role: str, context_instructions: str, processed: str
) -> str:
    """Truncate prompt to fit within MAX_SYSTEM_PROMPT_CHARS.

    Truncation priority: strip body content from the end, preserving
    the role instruction and context instructions.
    """
    prefix = role + context_instructions + "\n\n---\n\n"
    available = MAX_SYSTEM_PROMPT_CHARS - len(prefix)
    if available <= 0:
        return prefix[:MAX_SYSTEM_PROMPT_CHARS]
    return prefix + processed.strip()[:available]


def _skill_needs_web(body: str, metadata) -> bool:
    """Determine if a skill needs web access tools."""
    # Check frontmatter for web-related declarations
    if hasattr(metadata, "get"):
        deps = metadata.get("dependencies", {})
        if isinstance(deps, dict):
            # Check for web-related dependencies
            files = deps.get("files", [])
            if isinstance(files, list):
                for f in files:
                    if isinstance(f, str) and "web" in f.lower():
                        return True

    # Check body for web search references
    web_keywords = [
        "web search",
        "web_search",
        "search the web",
        "web scraping",
        "websearch",
        "fetch_url",
        "web fetch",
        "research via web",
        "online research",
    ]
    body_lower = body.lower()
    return any(kw in body_lower for kw in web_keywords)


def _skill_needs_files(body: str, metadata) -> bool:
    """Determine if a skill needs filesystem access tools."""
    if hasattr(metadata, "get"):
        deps = metadata.get("dependencies", {})
        if isinstance(deps, dict):
            files = deps.get("files", [])
            if isinstance(files, list) and len(files) > 0:
                return True

    # Check body for file operations
    file_keywords = [
        "read_file",
        "write_file",
        "read file",
        "write file",
        "save to file",
        "output file",
        "csv file",
        "upload",
    ]
    body_lower = body.lower()
    return any(kw in body_lower for kw in file_keywords)


def _extract_write_targets_from_body(body: str) -> list:
    """Extract WRITE_TARGETS list from Python code in body."""
    # Pattern: WRITE_TARGETS = ["file1.md", "file2.md"]
    pattern = r"WRITE_TARGETS\s*=\s*\[([^\]]+)\]"
    match = re.search(pattern, body)
    if match:
        raw = match.group(1)
        # Extract quoted strings
        targets = re.findall(r'["\']([^"\']+)["\']', raw)
        if targets:
            return targets
    return []


def _extract_context_refs_from_body(body: str) -> list:
    """Extract context file references from body text."""
    # Look for .md file references that look like context files
    # Patterns: read_context("file.md"), context/file.md, etc.
    refs = set()

    # Pattern 1: read_context("file.md") or read_context('file.md')
    for match in re.finditer(r'read_context\s*\(\s*["\']([^"\']+)["\']', body):
        refs.add(match.group(1))

    # Pattern 2: context store file references like positioning.md, contacts.md
    # Look for markdown file names in context-related sections
    context_files = re.findall(
        r"(?:context/|context store|read from|reads? )[\w\s]*?(\w[\w-]+\.md)",
        body,
        re.IGNORECASE,
    )
    refs.update(context_files)

    return sorted(refs) if refs else []
