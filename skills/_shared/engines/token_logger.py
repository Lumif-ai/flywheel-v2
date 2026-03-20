"""
token_logger.py - Token usage JSONL logging for headless execution.

Logs every LLM call with user, skill, model, token counts, and duration.
Provides usage summary aggregation for monitoring and cost tracking.

Public API:
    log_token_usage(user_id, skill, model, input_tokens, output_tokens, duration_ms, mode)
    read_usage_summary(since_date) -> dict
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level path -- patchable for tests
TOKEN_LOG = Path.home() / ".claude" / "logs" / "token_usage.jsonl"


def log_token_usage(
    user_id: str,
    skill: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    mode: str = "llm",
) -> None:
    """Append a token usage entry to the JSONL log.

    Args:
        user_id: Slack user ID or other identifier.
        skill: Skill name that was invoked.
        model: Model used (e.g. 'claude-sonnet-4-20250514').
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        duration_ms: Total execution duration in milliseconds.
        mode: Execution mode ('llm' or 'engine').

    Logging failures are caught and logged -- never block execution.
    """
    try:
        TOKEN_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "skill": skill,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms,
            "mode": mode,
        }
        with open(TOKEN_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        logger.error("Failed to log token usage: %s", e)


def read_usage_summary(since_date: str = None) -> dict:
    """Read and aggregate token usage from the log file.

    Args:
        since_date: Optional ISO date string (YYYY-MM-DD). If provided,
            only entries after this date are included.

    Returns:
        Dict with keys: total_tokens, by_user, by_skill, by_model,
        invocation_count.
    """
    summary = {
        "total_tokens": 0,
        "by_user": {},
        "by_skill": {},
        "by_model": {},
        "invocation_count": 0,
    }

    if not TOKEN_LOG.exists():
        return summary

    try:
        with open(TOKEN_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Filter by date if specified
                if since_date:
                    ts = entry.get("timestamp", "")
                    entry_date = ts[:10]  # YYYY-MM-DD prefix
                    if entry_date < since_date:
                        continue

                tokens = entry.get("input_tokens", 0) + entry.get(
                    "output_tokens", 0
                )
                summary["total_tokens"] += tokens
                summary["invocation_count"] += 1

                # Aggregate by user
                user = entry.get("user_id", "unknown")
                summary["by_user"][user] = (
                    summary["by_user"].get(user, 0) + tokens
                )

                # Aggregate by skill
                skill = entry.get("skill", "unknown")
                summary["by_skill"][skill] = (
                    summary["by_skill"].get(skill, 0) + tokens
                )

                # Aggregate by model
                model = entry.get("model", "unknown")
                summary["by_model"][model] = (
                    summary["by_model"].get(model, 0) + tokens
                )

    except IOError as e:
        logger.error("Failed to read token usage log: %s", e)

    return summary
