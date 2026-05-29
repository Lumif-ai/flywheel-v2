#!/usr/bin/env python3
"""
extract_profile.py — Phase 151.1 log-parser for TimingMiddleware emissions.

Reads a uvicorn stderr/logfile (e.g. /tmp/flywheel-backend.log) and aggregates
the `request_complete` lines emitted by `flywheel.middleware.timing`
(Phase 151.1 Plan 01) into per-route latency percentiles.

Usage:
    python extract_profile.py LOGFILE [--cold-only|--warm-only] [--group-by route|correlation_id]
                              [--since 2026-04-20T10:00:00Z] [--route-contains /assets/bundle]
                              [--min-samples 3] [--format markdown|json]

Emits a markdown table (default) with columns:
    route | n | p50_ms | p95_ms | p99_ms | mean_db_count | mean_db_total_ms

Used by:
    - Plan 03: renders the ngrok-topology per-handler breakdown into 151.1-PROFILE.md
    - Plan 04: regression test parses the same log + asserts p99 thresholds

Design notes:
    - Stdlib-only (no deps beyond Python 3.9+).
    - Uses `open(..., errors="replace")` so binary interleave in the log file
      (e.g., subprocess output) doesn't crash the parser.
    - Regex tolerates optional tenant_id field and additional trailing keys.
    - percentile() uses the nearest-rank definition at indices floor(n*q);
      matches Phase 151's measurement script for apples-to-apples comparison.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# Regex matches a line such as:
#   2026-04-20 11:35:05,925 INFO flywheel.timing: request_complete
#     route=/api/v1/skills/... method=GET status=200 duration_ms=2625.30
#     db_count=8 db_total_ms=1571.87 cold=True correlation_id=smoke01
LINE_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}[.,]\d+)\s+INFO\s+"
    r"flywheel\.timing:\s+request_complete\s+"
    r"route=(?P<route>\S+)\s+"
    r"method=(?P<method>\S+)\s+"
    r"status=(?P<status>\d+)\s+"
    r"duration_ms=(?P<duration_ms>[\d.]+)\s+"
    r"db_count=(?P<db_count>\d+)\s+"
    r"db_total_ms=(?P<db_total_ms>[\d.]+)\s+"
    r"cold=(?P<cold>True|False)\s+"
    r"correlation_id=(?P<correlation_id>\S+)"
)


@dataclass
class Record:
    ts: datetime
    route: str
    method: str
    status: int
    duration_ms: float
    db_count: int
    db_total_ms: float
    cold: bool
    correlation_id: str


def _parse_ts(raw: str) -> datetime:
    # Handle either `,` or `.` as ms separator
    raw = raw.replace(",", ".")
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)


def parse(logfile: Path, *, since: datetime | None = None) -> list[Record]:
    """Parse `request_complete` lines from `logfile`.

    Returns a list of Record objects, optionally filtered to lines newer than
    `since` (a timezone-aware datetime).
    """
    out: list[Record] = []
    with open(logfile, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LINE_RE.search(line)
            if not m:
                continue
            try:
                ts = _parse_ts(m.group("ts"))
            except ValueError:
                continue
            if since is not None and ts < since:
                continue
            out.append(
                Record(
                    ts=ts,
                    route=m.group("route"),
                    method=m.group("method"),
                    status=int(m.group("status")),
                    duration_ms=float(m.group("duration_ms")),
                    db_count=int(m.group("db_count")),
                    db_total_ms=float(m.group("db_total_ms")),
                    cold=(m.group("cold") == "True"),
                    correlation_id=m.group("correlation_id"),
                )
            )
    return out


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (matches Phase 151 measure_latency.py behaviour)."""
    if not values:
        return float("nan")
    s = sorted(values)
    # For p99 on 100 samples: index 98 (i.e., floor(100 * 0.99) - 1 with edge clamp)
    idx = max(0, min(len(s) - 1, int(round(pct / 100.0 * len(s))) - 1))
    return s[idx]


@dataclass
class Agg:
    route: str
    n: int
    p50: float
    p95: float
    p99: float
    mean_db_count: float
    mean_db_total_ms: float
    max_duration_ms: float
    min_duration_ms: float
    cold_count: int = 0
    warm_count: int = 0


def aggregate(records: Iterable[Record], *, group_by: str = "route") -> list[Agg]:
    """Group records by `group_by` (route|correlation_id) and emit percentile stats."""
    buckets: dict[str, list[Record]] = {}
    for r in records:
        key = getattr(r, group_by)
        buckets.setdefault(key, []).append(r)

    rows: list[Agg] = []
    for key, recs in buckets.items():
        durs = [r.duration_ms for r in recs]
        rows.append(
            Agg(
                route=key,
                n=len(recs),
                p50=percentile(durs, 50),
                p95=percentile(durs, 95),
                p99=percentile(durs, 99),
                mean_db_count=statistics.mean(r.db_count for r in recs),
                mean_db_total_ms=statistics.mean(r.db_total_ms for r in recs),
                max_duration_ms=max(durs),
                min_duration_ms=min(durs),
                cold_count=sum(1 for r in recs if r.cold),
                warm_count=sum(1 for r in recs if not r.cold),
            )
        )
    rows.sort(key=lambda a: -a.p99)
    return rows


def render_markdown(rows: list[Agg], *, title: str = "") -> str:
    lines: list[str] = []
    if title:
        lines.append(f"### {title}")
        lines.append("")
    lines.append(
        "| Route | N | p50 ms | p95 ms | p99 ms | max ms | mean db_count | mean db_total_ms | cold/warm |"
    )
    lines.append(
        "| ----- | -: | -----: | -----: | -----: | -----: | ------------: | ---------------: | --------- |"
    )
    for r in rows:
        lines.append(
            f"| `{r.route}` | {r.n} | {r.p50:.2f} | {r.p95:.2f} | {r.p99:.2f} | "
            f"{r.max_duration_ms:.2f} | {r.mean_db_count:.2f} | {r.mean_db_total_ms:.2f} | "
            f"{r.cold_count}/{r.warm_count} |"
        )
    return "\n".join(lines)


def render_json(rows: list[Agg]) -> str:
    return json.dumps(
        [
            {
                "route": r.route,
                "n": r.n,
                "p50_ms": r.p50,
                "p95_ms": r.p95,
                "p99_ms": r.p99,
                "max_ms": r.max_duration_ms,
                "mean_db_count": r.mean_db_count,
                "mean_db_total_ms": r.mean_db_total_ms,
                "cold_count": r.cold_count,
                "warm_count": r.warm_count,
            }
            for r in rows
        ],
        indent=2,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Parse request_complete lines from a flywheel.timing logfile and aggregate "
            "per-route latency percentiles. Input is the stderr/logfile produced by "
            "uvicorn when TimingMiddleware (Phase 151.1 Plan 01) is installed."
        )
    )
    ap.add_argument("logfile", type=Path, help="Path to backend log file")
    ap.add_argument(
        "--cold-only", action="store_true",
        help="Filter to cold=True records only (X-Flywheel-Cache-State: cold)"
    )
    ap.add_argument(
        "--warm-only", action="store_true",
        help="Filter to cold=False records only"
    )
    ap.add_argument(
        "--route-contains", type=str, default=None,
        help="Restrict to routes containing this substring (e.g., /assets/bundle)"
    )
    ap.add_argument(
        "--since", type=str, default=None,
        help="Ignore records before this ISO timestamp (e.g., 2026-04-20T03:30:00Z)"
    )
    ap.add_argument(
        "--group-by", choices=("route", "correlation_id"), default="route"
    )
    ap.add_argument(
        "--min-samples", type=int, default=1,
        help="Drop groups with fewer than N samples"
    )
    ap.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    ap.add_argument(
        "--title", type=str, default="",
        help="Optional title above the markdown table"
    )
    args = ap.parse_args()

    if not args.logfile.exists():
        print(f"error: logfile not found: {args.logfile}", file=sys.stderr)
        return 2

    since_dt: datetime | None = None
    if args.since:
        raw = args.since.rstrip("Z")
        since_dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)

    records = parse(args.logfile, since=since_dt)

    if args.cold_only:
        records = [r for r in records if r.cold]
    if args.warm_only:
        records = [r for r in records if not r.cold]
    if args.route_contains:
        records = [r for r in records if args.route_contains in r.route]

    rows = aggregate(records, group_by=args.group_by)
    rows = [r for r in rows if r.n >= args.min_samples]

    if not rows:
        print(f"(no matching records in {args.logfile})", file=sys.stderr)
        return 1

    if args.format == "markdown":
        print(render_markdown(rows, title=args.title))
    else:
        print(render_json(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
