"""
execution_gateway.py - Hybrid execution gateway for headless skill invocation.

Routes skill invocations to Python engines (fast, deterministic) or Claude API
(reasoning, tool use). Enforces context store contracts and logs token usage.

Public API:
    execute_skill(skill_name, input_text, user_id, params) -> ExecutionResult
    route_skill(spec) -> str
    execute_tool(tool_name, tool_input, contract, user_id) -> str
    enforce_contract(skill_name, operation, target_file, contract) -> bool
"""

import importlib
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# Import from src/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from skill_converter import ENGINE_REGISTRY, ExecutionSpec, convert_skill
from skill_governance import handle_empty_context
import context_utils

try:
    import anthropic
except ImportError:
    anthropic = None  # Deferred -- only needed for LLM path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Result of a skill execution."""

    output: str
    mode: str  # "engine" or "llm"
    skill_name: str
    user_id: str
    token_usage: Optional[dict] = None
    contract_violations: list = field(default_factory=list)
    duration_ms: int = 0
    context_attribution: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Attribution tracking
# ---------------------------------------------------------------------------


def _count_entries(content: str) -> int:
    """Count context entries in raw content by counting entry headers.

    Entry headers follow the format: [YYYY-MM-DD | source: ... | detail]
    """
    if not content:
        return 0
    return len(re.findall(r'\[\d{4}-\d{2}-\d{2}\s*\|', content))


def _track_engine_reads(module) -> tuple:
    """Wrapper around module.pre_read_context() that builds attribution data.

    Args:
        module: Engine module with pre_read_context() method.

    Returns:
        Tuple of (context_snapshot, attribution_dict).
        attribution_dict maps filename -> {"entry_count": int, "chars_read": int}.
    """
    context_snapshot = module.pre_read_context()
    attribution = {}
    for filename, content in context_snapshot.items():
        if content:  # Exclude empty files
            attribution[filename] = {
                "entry_count": _count_entries(content),
                "chars_read": len(content),
            }
    return context_snapshot, attribution


# Thread-local storage for LLM path attribution tracking.
# Uses threading.local() because execute_skill wraps calls in
# asyncio.to_thread(), so concurrent skill executions would corrupt
# a shared module-level dict.
_THREAD_ATTRIBUTION = threading.local()


def _get_thread_attribution() -> dict:
    """Get the attribution dict for the current thread."""
    if not hasattr(_THREAD_ATTRIBUTION, 'data'):
        _THREAD_ATTRIBUTION.data = {}
    return _THREAD_ATTRIBUTION.data


def _clear_thread_attribution():
    """Clear attribution data for the current thread."""
    _THREAD_ATTRIBUTION.data = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_skill(
    skill_name: str,
    input_text: str,
    user_id: str,
    params: dict = None,
    force_llm: bool = False,
) -> ExecutionResult:
    """Execute a skill via the gateway.

    Main entry point. Routes to Python engine or LLM path based on
    ENGINE_REGISTRY. Measures duration and logs token usage.

    Args:
        skill_name: Name of the skill to execute.
        input_text: User input text / prompt.
        user_id: Slack user ID or other identifier.
        params: Optional additional parameters.
        force_llm: If True, bypass engine and use Claude API LLM path.
            Used by web interface for full-powered skill execution
            (web research, reasoning, tool use).

    Returns:
        ExecutionResult with output, mode, and metadata.
    """
    start = time.time()
    params = params or {}
    violations = []

    try:
        spec = convert_skill(skill_name)
    except FileNotFoundError as e:
        duration_ms = int((time.time() - start) * 1000)
        return ExecutionResult(
            output=f"Skill not found: {e}",
            mode="error",
            skill_name=skill_name,
            user_id=user_id,
            duration_ms=duration_ms,
        )

    mode = "llm" if force_llm else route_skill(spec)
    token_usage = None
    attribution = {}

    if mode == "engine":
        try:
            output, attribution = run_engine(skill_name, params, user_id)
        except Exception as e:
            output = f"Engine error: {e}"
            logger.error("Engine execution failed for %s: %s", skill_name, e)
    else:
        try:
            output, token_usage, attribution = run_llm_skill(
                spec, input_text, user_id
            )
        except Exception as e:
            output = f"LLM execution error: {e}"
            logger.error("LLM execution failed for %s: %s", skill_name, e)

    duration_ms = int((time.time() - start) * 1000)

    # Log token usage
    if token_usage:
        try:
            from token_logger import log_token_usage

            log_token_usage(
                user_id=user_id,
                skill=skill_name,
                model=token_usage.get("model", "claude-sonnet-4-20250514"),
                input_tokens=token_usage.get("input_tokens", 0),
                output_tokens=token_usage.get("output_tokens", 0),
                duration_ms=duration_ms,
                mode=mode,
            )
        except Exception as e:
            logger.error("Failed to log token usage: %s", e)

    return ExecutionResult(
        output=output,
        mode=mode,
        skill_name=skill_name,
        user_id=user_id,
        token_usage=token_usage,
        contract_violations=violations,
        duration_ms=duration_ms,
        context_attribution=attribution,
    )


def route_skill(spec: ExecutionSpec) -> str:
    """Determine execution path for a skill.

    Args:
        spec: ExecutionSpec from skill_converter.

    Returns:
        'engine' if skill has a Python engine, 'llm' otherwise.
    """
    if spec.has_engine:
        return "engine"
    return "llm"


# ---------------------------------------------------------------------------
# Engine execution
# ---------------------------------------------------------------------------


def run_engine(skill_name: str, params: dict, user_id: str) -> tuple:
    """Execute a skill via its Python engine.

    Each engine has a thin adapter that maps the generic params dict to
    engine-specific function calls. Engines are NOT refactored -- adapters
    handle the interface translation.

    Args:
        skill_name: Skill name (must be in ENGINE_REGISTRY).
        params: Parameters dict from the invocation.
        user_id: User identifier.

    Returns:
        Tuple of (output_string, attribution_dict).

    Raises:
        ValueError: If skill is not in ENGINE_REGISTRY.
        Exception: Engine errors are propagated to caller.
    """
    module_name = ENGINE_REGISTRY.get(skill_name)
    if not module_name:
        raise ValueError(f"No engine registered for skill: {skill_name}")

    # Import engine module dynamically
    module = importlib.import_module(module_name)

    # Route to the appropriate adapter
    if skill_name in ("meeting-prep", "ctx-meeting-prep"):
        return _adapt_meeting_prep(module, params)
    elif skill_name in ("meeting-processor", "ctx-meeting-processor"):
        return _adapt_meeting_processor(module, params)
    elif skill_name in ("gtm-my-company", "ctx-gtm-my-company"):
        return _adapt_gtm_company(module, params)
    elif skill_name == "gtm-pipeline":
        return _adapt_gtm_pipeline(module, params)
    elif skill_name in ("investor-update", "ctx-investor-update"):
        return _adapt_investor_update(module, params)
    else:
        raise ValueError(f"No adapter for engine skill: {skill_name}")


# ---------------------------------------------------------------------------
# Engine adapters
# ---------------------------------------------------------------------------


def _adapt_meeting_prep(module, params: dict) -> tuple:
    """Adapter for meeting-prep engine. Returns (output, attribution)."""
    context, attribution = _track_engine_reads(module)
    contact_name = params.get("contact_name", "")
    company_name = params.get("company_name", "")
    synthesis = params.get("synthesis", context)
    context_file_count = len(context)
    output = module.generate_prep_report(
        contact_name, company_name, synthesis, context_file_count
    )
    return output, attribution


def _adapt_meeting_processor(module, params: dict) -> tuple:
    """Adapter for meeting-processor engine. Returns (output, attribution)."""
    context, attribution = _track_engine_reads(module)
    extracted = params.get("extracted", {})
    cross_refs = params.get("cross_refs", [])
    write_results = params.get("write_results", {})
    meeting_type = params.get("meeting_type", "unknown")
    output = module.generate_enriched_output(
        extracted, cross_refs, write_results, meeting_type
    )
    return output, attribution


def _adapt_gtm_company(module, params: dict) -> tuple:
    """Adapter for gtm-my-company engine. Returns (output, attribution)."""
    context, attribution = _track_engine_reads(module)
    profile_data = params.get("profile_data", {})
    result = module.write_profile(profile_data)
    return json.dumps(result, indent=2), attribution


def _adapt_gtm_pipeline(module, params: dict) -> tuple:
    """Adapter for gtm-pipeline engine. Returns (output, attribution)."""
    context, attribution = _track_engine_reads(module)
    result = module.run_effectiveness_tracking(context_snapshot=context)
    return json.dumps(result, indent=2), attribution


def _adapt_investor_update(module, params: dict) -> tuple:
    """Adapter for investor-update engine. Returns (output, attribution)."""
    context, attribution = _track_engine_reads(module)
    since_date = params.get("since_date", "")
    themes, signals, report_data, report = module.generate_intelligence_report(
        context, since_date
    )
    return report, attribution


# ---------------------------------------------------------------------------
# LLM execution
# ---------------------------------------------------------------------------


def run_llm_skill(
    spec: ExecutionSpec,
    user_input: str,
    user_id: str,
    max_iterations: int = 25,
) -> tuple:
    """Execute a skill via Claude API with tool use loop.

    Uses the sync anthropic client. For async contexts (e.g. Slack bot),
    wrap in asyncio.to_thread().

    Args:
        spec: ExecutionSpec with system prompt and tool definitions.
        user_input: User's input text.
        user_id: User identifier for contract enforcement.
        max_iterations: Maximum number of tool-use loop iterations.

    Returns:
        Tuple of (output_text, token_usage_dict, attribution_dict).

    Raises:
        ImportError: If anthropic SDK is not installed.
    """
    if anthropic is None:
        raise ImportError("anthropic SDK required for LLM path")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_input}]
    total_input_tokens = 0
    total_output_tokens = 0
    model = "claude-sonnet-4-20250514"

    # Clear thread-local attribution before starting
    _clear_thread_attribution()

    # Build tools list: replace client-side web_search with Anthropic's
    # server-side web_search_20250305 (DuckDuckGo HTML scraping is blocked)
    combined_tools = []
    has_web_search = False
    for tool in (spec.tools or []):
        if tool.get("name") == "web_search":
            has_web_search = True
            continue  # Skip client-side web_search
        combined_tools.append(tool)
    # Add server-side web search (Anthropic handles it, no client-side scraping)
    if has_web_search:
        combined_tools.append({
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,
        })

    for _ in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=spec.system_prompt,
            tools=combined_tools,
            messages=messages,
        )

        # Track token usage
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Check if done (end_turn with no tool_use blocks)
        if response.stop_reason == "end_turn":
            # Extract text from content blocks
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            output = "\n".join(text_parts) if text_parts else ""
            usage = {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "model": model,
            }
            attribution = dict(_get_thread_attribution())
            _clear_thread_attribution()
            return output, usage, attribution

        # Handle tool_use: process ALL content blocks (pitfall #3)
        # Server-side tools (web_search_20250305) are auto-handled by Anthropic —
        # their results appear as web_search_tool_result blocks in response.content.
        # We only need to process client-side tool_use blocks.
        if response.stop_reason == "tool_use":
            # Add assistant response to messages (includes both text and tool_use blocks)
            messages.append(
                {"role": "assistant", "content": response.content}
            )

            # Execute each CLIENT-SIDE tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(
                        block.name,
                        block.input,
                        spec.contract,
                        user_id,
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )

            # Only add user message if there are client-side tool results
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

    # Max iterations reached
    usage = {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "model": model,
    }
    attribution = dict(_get_thread_attribution())
    _clear_thread_attribution()
    return "Skill exceeded maximum iterations", usage, attribution


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def execute_tool(
    tool_name: str,
    tool_input: dict,
    contract: dict,
    user_id: str,
) -> str:
    """Execute a tool call from the LLM.

    Dispatches to the appropriate handler based on tool_name.
    Contract enforcement is applied for write operations.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input parameters from the LLM.
        contract: Skill's contract (reads/writes lists).
        user_id: User identifier.

    Returns:
        String result for tool_result message.
    """
    if tool_name == "read_context":
        file_name = tool_input.get("file", "")
        try:
            content = context_utils.read_context(file_name, agent_id=user_id)
            if not content:
                _, suggestion = handle_empty_context("", file_name)
                return suggestion if suggestion else f"No entries found in {file_name}"
            # Track attribution for this read in thread-local storage
            attribution = _get_thread_attribution()
            attribution[file_name] = {
                "entry_count": _count_entries(content),
                "chars_read": len(content),
            }
            return content
        except Exception as e:
            return f"Error reading {file_name}: {e}"

    elif tool_name == "append_entry":
        file_name = tool_input.get("file", "")
        # Contract enforcement before write
        if not enforce_contract(user_id, "write", file_name, contract):
            return f"BLOCKED: Contract violation - skill not allowed to write to {file_name}"

        content_lines = tool_input.get("content", [])
        detail = tool_input.get("detail", "")
        confidence = tool_input.get("confidence", "medium")

        entry = {
            "content": content_lines,
            "detail": detail,
            "confidence": confidence,
            "source": user_id,
        }
        try:
            result = context_utils.append_entry(
                file=file_name,
                entry=entry,
                source=user_id,
                agent_id=user_id,
            )
            return f"Entry written to {file_name}: {result}"
        except Exception as e:
            return f"Error writing to {file_name}: {e}"

    elif tool_name == "web_search":
        query = tool_input.get("query", "")
        try:
            return _web_search(query)
        except Exception as e:
            return f"Web search error: {e}"

    elif tool_name == "web_fetch":
        url = tool_input.get("url", "")
        try:
            return _web_fetch(url)
        except Exception as e:
            return f"Web fetch error: {e}"

    elif tool_name == "read_file":
        path = tool_input.get("path", "")
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {path}: {e}"

    elif tool_name == "write_file":
        path = tool_input.get("path", "")
        content = tool_input.get("content", "")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"File written: {path}"
        except Exception as e:
            return f"Error writing file {path}: {e}"

    else:
        return f"Unknown tool: {tool_name}"


# ---------------------------------------------------------------------------
# Contract enforcement
# ---------------------------------------------------------------------------


def enforce_contract(
    skill_name: str,
    operation: str,
    target_file: str,
    contract: dict,
) -> bool:
    """Check if a skill is allowed to perform an operation on a file.

    For write operations, checks the contract's writes list.
    For read operations, always returns True (reads unrestricted).

    Args:
        skill_name: Name of the skill (for logging).
        operation: 'read' or 'write'.
        target_file: Context file being accessed.
        contract: Dict with 'reads' and 'writes' lists.

    Returns:
        True if allowed, False if blocked.
    """
    if operation == "read":
        return True

    writes = contract.get("writes", [])
    if writes == ["*"] or "*" in writes:
        return True

    if target_file in writes:
        return True

    # Violation
    logger.warning(
        "Contract violation: %s attempted to write to %s (allowed: %s)",
        skill_name,
        target_file,
        writes,
    )

    # Log violation to events
    try:
        context_utils.log_event(
            "contract_violation",
            {
                "skill": skill_name,
                "operation": operation,
                "target": target_file,
                "allowed_writes": writes,
            },
        )
    except Exception:
        pass  # Best-effort event logging

    return False


# ---------------------------------------------------------------------------
# Web tools
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _web_fetch(url: str, max_chars: int = 8000) -> str:
    """Fetch a URL and extract readable text content.

    Uses httpx + beautifulsoup4 to fetch and parse HTML.
    Returns plain text, truncated to max_chars.
    """
    import httpx
    from bs4 import BeautifulSoup

    resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script, style, nav, footer elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Clean up multiple blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars] + "\n\n[Content truncated]"

    return clean_text if clean_text else "No readable content found at URL"


def _web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results.

    Returns formatted search results with title, URL, and snippet.
    """
    import httpx

    # DuckDuckGo HTML search
    params = {"q": query, "kl": "us-en"}
    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params=params,
        headers=_HEADERS,
        follow_redirects=True,
        timeout=15,
    )
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for r in soup.select(".result")[:num_results]:
        title_el = r.select_one(".result__title a")
        snippet_el = r.select_one(".result__snippet")
        if title_el:
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            results.append(f"**{title}**\n{href}\n{snippet}")

    if not results:
        return f"No search results found for: {query}"

    return "\n\n".join(results)
