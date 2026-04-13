"""
quote_comparator.py - Pure Python quote comparison engine.

Compares carrier quotes per coverage line and computes ranking flags:
is_best_price, is_best_coverage, is_recommended. No AI, no DB, no external
dependencies.

Functions:
  compare_quotes(coverages, quotes) -> dict
    Main comparison engine. Groups quotes by coverage, ranks them.
  summarize_comparison(result) -> dict
    Returns summary counts from a comparison result.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Valid statuses for comparison (quotes must be in one of these states)
# ---------------------------------------------------------------------------

COMPARABLE_STATUSES = {"extracted", "reviewed", "selected"}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compare_quotes(
    coverages: list[dict[str, Any]], quotes: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compare carrier quotes per coverage line and compute ranking flags.

    Groups quotes by coverage_id, filters to comparable statuses, and for each
    coverage computes:
    - is_best_price: lowest premium (tie-break: lower deductible)
    - is_best_coverage: highest limit_amount (tie-break: lower premium)
    - is_recommended: lowest premium among quotes WITHOUT critical exclusions

    Args:
        coverages: List of ProjectCoverage dicts with keys:
            id, coverage_type, category, required_limit
        quotes: List of CarrierQuote dicts with keys:
            id, coverage_id, carrier_name, carrier_config_id, premium,
            deductible, limit_amount, coinsurance, has_critical_exclusion,
            critical_exclusion_detail, exclusions, status, confidence

    Returns:
        Comparison result dict with per-coverage ranked quotes and metadata.
        Input lists are never mutated.
    """
    # Group quotes by coverage_id
    quotes_by_coverage: dict[Any, list[dict]] = {}
    for q in quotes:
        cov_id = q.get("coverage_id")
        if cov_id is not None:
            quotes_by_coverage.setdefault(cov_id, []).append(q)

    # Track unique carriers across all quotes
    all_carriers: set[str] = set()
    # Track currencies for mismatch detection
    currencies_seen: set[str] = set()

    coverage_results = []

    for cov in coverages:
        cov_id = cov.get("id")
        coverage_type = cov.get("coverage_type", "")
        category = cov.get("category", "")
        required_limit = cov.get("required_limit")

        # Get quotes for this coverage, filter to comparable statuses
        cov_quotes = quotes_by_coverage.get(cov_id, [])
        comparable = [
            q for q in cov_quotes if q.get("status") in COMPARABLE_STATUSES
        ]

        # Track carriers
        for q in comparable:
            carrier = q.get("carrier_name")
            if carrier:
                all_carriers.add(carrier)

        # Sort by premium ascending (nulls last)
        def _premium_sort_key(q: dict) -> tuple:
            p = q.get("premium")
            if p is None:
                return (1, float("inf"), float("inf"))
            return (0, float(p), float(q.get("deductible") or 0))

        ranked = sorted(comparable, key=_premium_sort_key)

        # Determine is_best_price: lowest premium, tie-break lower deductible
        best_price_id = None
        if ranked:
            candidates_with_premium = [
                q for q in ranked if q.get("premium") is not None
            ]
            if candidates_with_premium:
                best_price_id = candidates_with_premium[0].get("id")

        # Determine is_best_coverage: highest limit_amount, tie-break lower premium
        best_coverage_id = None
        candidates_with_limit = [
            q for q in comparable if q.get("limit_amount") is not None
        ]
        if candidates_with_limit:
            best_cov = max(
                candidates_with_limit,
                key=lambda q: (
                    float(q.get("limit_amount") or 0),
                    -float(q.get("premium") or float("inf")),
                ),
            )
            best_coverage_id = best_cov.get("id")

        # Determine is_recommended: lowest premium WITHOUT critical exclusion
        recommended_id = None
        non_critical = [
            q
            for q in ranked
            if not q.get("has_critical_exclusion")
            and q.get("premium") is not None
        ]
        if non_critical:
            recommended_id = non_critical[0].get("id")

        # Build output quotes with flags
        output_quotes = []
        for q in ranked:
            q_id = q.get("id")
            output_quotes.append(
                {
                    "quote_id": q_id,
                    "carrier_name": q.get("carrier_name"),
                    "carrier_config_id": q.get("carrier_config_id"),
                    "premium": q.get("premium"),
                    "deductible": q.get("deductible"),
                    "limit_amount": q.get("limit_amount"),
                    "coinsurance": q.get("coinsurance"),
                    "is_best_price": q_id == best_price_id,
                    "is_best_coverage": q_id == best_coverage_id,
                    "is_recommended": q_id == recommended_id,
                    "has_critical_exclusion": q.get(
                        "has_critical_exclusion", False
                    ),
                    "critical_exclusion_detail": q.get(
                        "critical_exclusion_detail"
                    ),
                    "exclusions": q.get("exclusions", []),
                    "confidence": q.get("confidence"),
                }
            )

        coverage_results.append(
            {
                "coverage_id": cov_id,
                "coverage_type": coverage_type,
                "category": category,
                "required_limit": required_limit,
                "quotes": output_quotes,
            }
        )

    # Detect currency mismatch across all quotes
    for q in quotes:
        meta = q.get("metadata_") or q.get("metadata") or {}
        currency = meta.get("currency") or q.get("currency")
        if currency:
            currencies_seen.add(currency)

    # Count distinct carriers
    total_carriers = len(all_carriers)

    return {
        "coverages": coverage_results,
        "partial": total_carriers < 2,
        "total_carriers": total_carriers,
        "total_coverages": len(coverages),
        "currency_mismatch": len(currencies_seen) > 1,
    }


def summarize_comparison(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize a comparison result with counts and highlights.

    Args:
        result: Output of compare_quotes().

    Returns:
        Dict with summary statistics: total_coverages,
        coverages_with_recommendation, coverages_with_critical_exclusions,
        best_price_carrier (most frequent).
    """
    total_coverages = len(result.get("coverages", []))
    coverages_with_recommendation = 0
    coverages_with_critical = 0
    carrier_best_price_counts: dict[str, int] = {}

    for cov in result.get("coverages", []):
        has_recommendation = False
        has_critical = False

        for q in cov.get("quotes", []):
            if q.get("is_recommended"):
                has_recommendation = True
            if q.get("has_critical_exclusion"):
                has_critical = True
            if q.get("is_best_price"):
                carrier = q.get("carrier_name", "Unknown")
                carrier_best_price_counts[carrier] = (
                    carrier_best_price_counts.get(carrier, 0) + 1
                )

        if has_recommendation:
            coverages_with_recommendation += 1
        if has_critical:
            coverages_with_critical += 1

    # Most frequent best-price carrier
    best_price_carrier = None
    if carrier_best_price_counts:
        best_price_carrier = max(
            carrier_best_price_counts, key=carrier_best_price_counts.get  # type: ignore[arg-type]
        )

    return {
        "total_coverages": total_coverages,
        "coverages_with_recommendation": coverages_with_recommendation,
        "coverages_with_critical_exclusions": coverages_with_critical,
        "best_price_carrier": best_price_carrier,
    }
