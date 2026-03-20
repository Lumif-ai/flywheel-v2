"""
skill_runner_web.py - SSE streaming wrapper for skill execution in the web app.

Wraps execution_gateway.execute_skill() in an async SSE generator for real-time
browser streaming via HTMX SSE extension. Also provides per-user output storage
for retrieving past skill results.

Public API:
    sse_event(event, data) -> str
    sse_comment(text) -> str
    skill_sse_generator(skill_name, input_text, user_id, params) -> AsyncGenerator
    store_result(user_id, result) -> str
    load_result(user_id, run_id) -> dict
    list_results(user_id, limit=20) -> list
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# sys.path setup (same pattern as web_app.py)
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)


# ---------------------------------------------------------------------------
# SSE formatting helpers
# ---------------------------------------------------------------------------


def sse_event(event: str, data) -> str:
    """Format a Server-Sent Event string.

    JSON-encodes the data to handle newlines safely (research pitfall #3).
    Each SSE message is terminated by a double newline.

    Args:
        event: SSE event name (e.g. 'status', 'result', 'error', 'done').
        data: Data payload (will be JSON-encoded if not a string).

    Returns:
        Formatted SSE string ready to yield.
    """
    if isinstance(data, str):
        encoded = data
    else:
        encoded = json.dumps(data)
    return f"event: {event}\ndata: {encoded}\n\n"


def sse_comment(text: str) -> str:
    """Format an SSE comment line (used for keep-alive pings).

    Args:
        text: Comment text.

    Returns:
        SSE comment string.
    """
    return f": {text}\n\n"


# ---------------------------------------------------------------------------
# Async SSE generator
# ---------------------------------------------------------------------------


async def skill_sse_generator(
    skill_name: str,
    input_text: str,
    user_id: str,
    params: dict = None,
):
    """Async generator that streams SSE events during skill execution.

    Yields SSE events for status, result, error, and done phases.
    Calls execute_skill via asyncio.to_thread to avoid blocking the event loop
    (proven pattern from slack_bot.py line 623).

    The result event includes pre-rendered HTML via output_renderer.render_output().

    Args:
        skill_name: Name of the skill to execute.
        input_text: User input text.
        user_id: Authenticated user ID.
        params: Optional additional parameters.

    Yields:
        SSE-formatted strings for each event.
    """
    params = params or {}

    # Emit all stages as pending upfront so UI can show the full pipeline
    yield sse_event("stages", {"stages": [
        {"name": "context", "label": "Loading context", "status": "pending"},
        {"name": "execute", "label": "Running skill", "status": "pending"},
        {"name": "render", "label": "Formatting output", "status": "pending"},
    ]})

    # Started event (backward compatible)
    yield sse_event("status", {
        "phase": "started",
        "skill": skill_name,
    })

    current_stage = "context"

    try:
        # Stage 1: Context loading
        yield sse_event("stage", {"name": "context", "status": "active", "label": "Loading context..."})

        # Lazy import of execute_skill (same pattern as other modules)
        from execution_gateway import execute_skill

        yield sse_event("stage", {"name": "context", "status": "completed", "label": "Context loaded"})

        # Stage 2: Skill execution
        current_stage = "execute"
        display_name = skill_name.replace("-", " ").title()
        yield sse_event("stage", {"name": "execute", "status": "active", "label": f"Running {display_name}..."})

        result = await asyncio.to_thread(
            execute_skill, skill_name, input_text, user_id, params,
            True,  # force_llm=True for web: use Claude API with web research
        )

        yield sse_event("stage", {"name": "execute", "status": "completed", "label": "Execution complete"})

        # Stage 3: Output rendering
        current_stage = "render"
        yield sse_event("stage", {"name": "render", "status": "active", "label": "Formatting output..."})

        # Enrich attribution data via attribution module
        enriched_attribution = {}
        try:
            from attribution import build_attribution
            enriched_attribution = build_attribution(result.context_attribution)
        except ImportError:
            logger.warning("attribution module not available, using raw attribution")
            enriched_attribution = result.context_attribution or {}
        except Exception as e:
            logger.warning("build_attribution failed: %s", e)
            enriched_attribution = result.context_attribution or {}

        # Render output HTML via output_renderer
        rendered_html = None
        try:
            from output_renderer import render_output
            templates_dir = str(Path(__file__).parent / "templates")
            rendered_html = render_output(
                result.skill_name,
                result.output,
                enriched_attribution,
                templates_dir,
            )
        except ImportError:
            logger.warning("output_renderer not available, falling back to <pre> tag")
            rendered_html = f"<pre>{_escape_html(result.output)}</pre>"
        except Exception as e:
            logger.warning("render_output failed: %s, falling back to <pre> tag", e)
            rendered_html = f"<pre>{_escape_html(result.output)}</pre>"

        # Store result for later retrieval
        try:
            run_id = store_result(user_id, result)
        except Exception as e:
            logger.warning("Failed to store result: %s", e)
            run_id = None

        yield sse_event("stage", {"name": "render", "status": "completed", "label": "Output ready"})

        yield sse_event("result", {
            "rendered_html": rendered_html,
            "output": result.output,
            "mode": result.mode,
            "duration_ms": result.duration_ms,
            "context_attribution": enriched_attribution,
            "skill_name": result.skill_name,
            "run_id": run_id,
        })

    except Exception as e:
        logger.error("Skill execution failed: %s", e)
        error_summary = str(e)[:100]
        yield sse_event("stage", {"name": current_stage, "status": "failed", "label": f"Failed: {error_summary}"})
        yield sse_event("error", {"error": str(e)})

    # Always yield done event (HTMX sse-close listens for this)
    yield sse_event("done", "complete")


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for fallback <pre> rendering."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Output storage (per-user JSON files)
# ---------------------------------------------------------------------------

OUTPUTS_DIR_BASE = Path.home() / ".claude" / "users"


def _get_outputs_dir(user_id: str) -> Path:
    """Get (and create) the outputs directory for a user."""
    outputs_dir = OUTPUTS_DIR_BASE / user_id / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def store_result(user_id: str, result) -> str:
    """Serialize and store an ExecutionResult for later retrieval.

    Uses atomic write (temp + rename) per context_utils pattern.

    Args:
        user_id: User identifier.
        result: ExecutionResult from execution_gateway.

    Returns:
        run_id (uuid string) for retrieving the result later.
    """
    run_id = str(uuid.uuid4())
    outputs_dir = _get_outputs_dir(user_id)

    data = {
        "run_id": run_id,
        "skill_name": result.skill_name,
        "output": result.output,
        "mode": result.mode,
        "duration_ms": result.duration_ms,
        "context_attribution": result.context_attribution,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    target = outputs_dir / f"{run_id}.json"

    # Atomic write: temp file + rename
    fd, tmp_path = tempfile.mkstemp(
        dir=str(outputs_dir), suffix=".tmp", prefix=".output-"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, str(target))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return run_id


def load_result(user_id: str, run_id: str) -> dict:
    """Load a stored skill result by run_id.

    Args:
        user_id: User identifier.
        run_id: UUID string from store_result.

    Returns:
        Dict with stored result data.

    Raises:
        FileNotFoundError: If run_id not found.
    """
    # Validate run_id format to prevent path traversal
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise FileNotFoundError(f"Invalid run_id format: {run_id}")

    outputs_dir = _get_outputs_dir(user_id)
    result_path = outputs_dir / f"{run_id}.json"

    if not result_path.exists():
        raise FileNotFoundError(f"Result not found: {run_id}")

    with open(result_path, "r") as f:
        return json.load(f)


def list_results(user_id: str, limit: int = 20) -> list:
    """List recent stored results for a user, sorted by timestamp descending.

    Args:
        user_id: User identifier.
        limit: Maximum number of results to return.

    Returns:
        List of result dicts (without full output text for efficiency).
    """
    outputs_dir = _get_outputs_dir(user_id)

    if not outputs_dir.exists():
        return []

    results = []
    for path in outputs_dir.glob("*.json"):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            # Return summary (exclude full output for list view)
            results.append({
                "run_id": data.get("run_id"),
                "skill_name": data.get("skill_name"),
                "mode": data.get("mode"),
                "duration_ms": data.get("duration_ms"),
                "timestamp": data.get("timestamp"),
            })
        except (json.JSONDecodeError, OSError):
            continue

    # Sort by timestamp descending
    results.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return results[:limit]
