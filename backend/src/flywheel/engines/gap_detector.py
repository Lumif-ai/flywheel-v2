"""
gap_detector.py - Pure Python gap detection for broker coverage analysis.

Compares required_limit vs current_limit for each coverage and classifies
gap_status as covered, insufficient, missing, or unknown. No AI, no DB,
no external dependencies.

Functions:
  detect_gaps(coverages) -> list[dict]
    Classify each coverage's gap status and compute gap_amount.
  summarize_gaps(results) -> dict[str, int]
    Count totals by gap_status.
"""

from typing import Any


def detect_gaps(coverages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify each coverage's gap status by comparing required vs current limits.

    Rules:
    - is_manual_override=True: pass through unchanged (broker's manual assessment)
    - required_limit is None: gap_status="unknown", gap_amount=None
    - current_limit is None or 0: gap_status="missing", gap_amount=required_limit
    - current_limit >= required_limit: gap_status="covered", gap_amount=0.0
    - 0 < current < required: gap_status="insufficient", gap_amount=difference

    Args:
        coverages: List of coverage dicts with at minimum required_limit,
                   current_limit, and optionally is_manual_override.

    Returns:
        List of shallow-copied dicts with gap_status and gap_amount set.
        Input list is never mutated.
    """
    results: list[dict[str, Any]] = []

    for cov in coverages:
        updated = dict(cov)  # shallow copy — don't mutate input

        # Manual override: preserve broker's assessment, skip detection
        if cov.get("is_manual_override"):
            results.append(updated)
            continue

        required = cov.get("required_limit")
        current = cov.get("current_limit")

        if required is None:
            updated["gap_status"] = "unknown"
            updated["gap_amount"] = None
        elif current is None or current == 0:
            updated["gap_status"] = "missing"
            updated["gap_amount"] = float(required)
        elif current >= required:
            updated["gap_status"] = "covered"
            updated["gap_amount"] = 0.0
        else:
            # 0 < current < required
            updated["gap_status"] = "insufficient"
            updated["gap_amount"] = float(required) - float(current)

        results.append(updated)

    return results


def summarize_gaps(results: list[dict[str, Any]]) -> dict[str, int]:
    """Count coverages by gap_status.

    Args:
        results: Output of detect_gaps().

    Returns:
        Dict with keys: total, covered, insufficient, missing, unknown.
    """
    summary = {
        "total": len(results),
        "covered": 0,
        "insufficient": 0,
        "missing": 0,
        "unknown": 0,
    }

    for r in results:
        status = r.get("gap_status")
        if status in summary:
            summary[status] += 1

    return summary
