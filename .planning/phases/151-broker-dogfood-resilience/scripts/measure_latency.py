#!/usr/bin/env python3
"""Phase 151 latency measurement -- regression baseline for SC5.

Measures p99 first-fetch (cold) and p99 cached-fetch (warm) against the
live Flywheel backend (ngrok + Supabase per user's operational topology).
Writes results to 151-LATENCY.md for future regression comparison.

Methodology v2 (2026-04-18 correction, supersedes v1):

* **Cold** -- Same Python process, fresh :class:`FlywheelClient`
  instance + cleared disk cache per iteration. Each call pays: (a) fresh
  httpx.Client instantiation (new TCP + TLS handshake, new connection
  pool), (b) server-side bundle build, (c) SHA-256 verification, (d)
  atomic cache write. ``bypass_cache=True`` is passed so the client does
  not short-circuit via any in-memory warm-path. ``~/.cache/flywheel/skills/``
  is wiped between iterations to force a true cache miss. **Python
  interpreter startup + import costs are NOT measured** -- those are
  paid ONCE per MCP server session in production, not per tool call, so
  amortising them over 100 iterations (as v1 did by subprocess-per-call)
  was unrepresentative and inflated p99 by ~1.5-2.0 s.
* **Warm** -- Same process, one persistent :class:`FlywheelClient`
  instance. A single priming call warms the cache + socket pool, then
  N back-to-back ``fetch_skill_assets_bundle`` calls are timed. All hit
  the content-addressed disk cache (near-zero network I/O). SHA
  validation on cache load is the dominant cost. (Unchanged from v1.)
* **Timing** -- ``time.perf_counter_ns()`` for sub-millisecond precision;
  converted to ms via ``/ 1e6``.
* **Quantiles** -- ``statistics.quantiles(values, n=100)`` (stdlib only)
  returns 99 cut points; indices 49, 94, 98 = p50, p95, p99 (0-indexed
  so ``qs[49]`` is the 50th percentile).

Why the v1 -> v2 correction:
    v1 used ``subprocess.run([python, '-c', ...])`` for every cold
    measurement. Each subprocess paid ~1.5 s of Python interpreter boot
    + ``import httpx`` + ``from flywheel_mcp.api_client import
    FlywheelClient`` before the timed region even started. Real MCP tool
    users run inside a long-lived Claude Code / MCP server process --
    the interpreter is warm and imports are cached. v1's p99 = 3279 ms
    was therefore ~90% Python-boot overhead, not fetch latency. v2
    measures the actual cost a user pays on their FIRST cold-cache
    fetch of a session: one HTTPS round-trip + server bundle build +
    SHA verify + cache write.

Rate-limit handling is retained (6.5 s pacing floor + exponential
back-off on HTTP 429) -- the bundle endpoint is rate-limited at
``10 per 1 minute`` per tenant regardless of how we time the call.

SLO gates (asserted, script exits non-zero on violation unless
``--no-assert-slo``):

    * p99 cold < 500 ms
    * p99 cached < 50 ms

Usage:
    # Default: 100 cold + 100 warm against $FLYWHEEL_API_URL
    python scripts/measure_latency.py

    # Custom sample size (for quick verify on dev)
    python scripts/measure_latency.py --n 25

    # Skip SLO gate (collect data only, no exit on violation)
    python scripts/measure_latency.py --no-assert-slo

    # Target skill (default: broker-parse-contract)
    python scripts/measure_latency.py --skill broker-parse-contract
"""
from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

# Repo-root detection mirrors dogfood_harness.py so flywheel_mcp imports
# resolve regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_DIR = _REPO_ROOT / "cli"
if str(_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_CLI_DIR))

OUT_PATH = Path(__file__).parent.parent / "151-LATENCY.md"

SLO_P99_COLD_MS = 500.0
SLO_P99_WARM_MS = 50.0


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "flywheel" / "skills"


def measure_cold(
    n: int,
    skill: str,
    *,
    min_interval_s: float = 6.5,
    max_retries_429: int = 5,
) -> list[float]:
    """Cold = same-process, fresh FlywheelClient + cleared disk cache per iteration.

    Methodology v2 (2026-04-18): matches real MCP tool usage where the
    Python interpreter is warm (long-running MCP server process) but the
    network connection, disk cache, and server bundle-build path are all
    cold. Each timed call pays:

        * Fresh ``FlywheelClient()`` instantiation -- new httpx.Client,
          new TCP + TLS handshake to the backend, no reused socket pool.
        * ``bypass_cache=True`` on the fetch call -- defeats any
          in-memory warm-path so we measure the full fetch even if the
          disk wipe race-losses.
        * ``~/.cache/flywheel/skills/`` wiped before each call so
          there is no disk-cache short-circuit.
        * Server-side bundle build + SHA-256 verify + cache write on
          response.

    What is NOT measured (unlike v1's subprocess-per-call): Python
    interpreter startup (~1.5 s) and ``import httpx`` / ``from
    flywheel_mcp.api_client import FlywheelClient`` cost. Those are paid
    ONCE per MCP server session, not per tool call, so amortising them
    into a per-call "cold" number was unrepresentative.

    Rate-limit handling: the bundle endpoint is rate-limited at
    ``10 per 1 minute`` per tenant. We pace cold iterations with a
    ``min_interval_s`` floor (default 6.5 s -- leaves safety margin
    under the 6.0 s hard limit) and retry with exponential back-off on
    HTTP 429. The *measured latency* is the ``time.perf_counter_ns()``
    delta around the ``fetch_skill_assets_bundle`` call only -- it does
    NOT include the inter-iteration throttle sleep or the cache wipe.
    """
    # Lazy imports so this module stays importable even when cli/ isn't
    # on sys.path (e.g. unit tests of _stats / _render_markdown).
    from flywheel_mcp.api_client import FlywheelClient
    from flywheel_mcp.bundle import BundleFetchError

    latencies_ms: list[float] = []
    cache_dir = _default_cache_dir()
    last_call_t: float | None = None
    for i in range(n):
        # Pace iterations to stay under the 10/min rate limit.
        if last_call_t is not None:
            elapsed = time.perf_counter() - last_call_t
            if elapsed < min_interval_s:
                time.sleep(min_interval_s - elapsed)

        retries = 0
        while True:
            # Force a cache miss: wipe disk cache BEFORE instantiating
            # client so even its constructor can't pre-warm anything.
            if cache_dir.exists():
                shutil.rmtree(cache_dir)

            # Fresh FlywheelClient per call -- ensures no reused httpx
            # connection pool, new TLS handshake, new auth-token load.
            client = FlywheelClient()

            last_call_t = time.perf_counter()
            try:
                t0 = time.perf_counter_ns()
                client.fetch_skill_assets_bundle(skill, bypass_cache=True)
                ms = (time.perf_counter_ns() - t0) / 1e6
                break  # success
            except BundleFetchError as exc:
                msg = str(exc)
                # Surface 429 rate-limit explicitly -- back off + retry.
                is_429 = "429" in msg or "RateLimitExceeded" in msg or (
                    getattr(exc, "status_code", None) == 429
                )
                if is_429:
                    if retries >= max_retries_429:
                        raise RuntimeError(
                            f"cold fetch {i + 1}/{n} still rate-limited "
                            f"after {max_retries_429} retries: {msg[-400:]}"
                        ) from exc
                    backoff = min(60.0, 12.0 * (2**retries))
                    print(
                        f"  cold[{i + 1}/{n}]: 429 rate-limit hit, "
                        f"backing off {backoff:.0f}s (retry {retries + 1}/"
                        f"{max_retries_429})",
                        file=sys.stderr,
                    )
                    time.sleep(backoff)
                    retries += 1
                    continue
                raise RuntimeError(
                    f"cold fetch {i + 1}/{n} failed: {msg[-400:]}"
                ) from exc

        latencies_ms.append(ms)
        print(f"  cold[{i + 1}/{n}]: {ms:.1f}ms", file=sys.stderr)
    return latencies_ms


def measure_warm(n: int, skill: str) -> list[float]:
    """Warm = same process, cache + socket pool primed.

    All N calls hit the content-addressed disk cache. SHA validation on
    load dominates the measured cost; zero bundle bytes cross the wire.
    """
    from flywheel_mcp.api_client import FlywheelClient  # lazy import

    client = FlywheelClient()
    # Prime cache + pool.
    client.fetch_skill_assets_bundle(skill)
    latencies_ms: list[float] = []
    for i in range(n):
        t0 = time.perf_counter_ns()
        client.fetch_skill_assets_bundle(skill)
        ms = (time.perf_counter_ns() - t0) / 1e6
        latencies_ms.append(ms)
        if (i + 1) % 10 == 0 or (i + 1) == n:
            print(f"  warm[{i + 1}/{n}]: {ms:.3f}ms", file=sys.stderr)
    return latencies_ms


def _stats(values: list[float]) -> dict:
    if len(values) < 2:
        raise ValueError(f"need >=2 samples for quantiles, got {len(values)}")
    qs = statistics.quantiles(values, n=100)  # 99 cut points at 1..99
    return {
        "p50": qs[49],
        "p95": qs[94],
        "p99": qs[98],
        "mean": statistics.mean(values),
        "stddev": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
        "n": len(values),
    }


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(_REPO_ROOT),
        ).stdout.strip()
    except Exception:
        return "unknown"


def _bundle_size(skill: str) -> int:
    """Best-effort bundle-size probe for the metadata block.

    Sums the bytes of every (name, version, bytes) triple returned by
    fetch_skill_assets_bundle. Catches every failure mode (network,
    401, 404) and returns -1 so the LATENCY.md still renders.
    """
    try:
        from flywheel_mcp.api_client import FlywheelClient  # lazy import

        _, bundles = FlywheelClient().fetch_skill_assets_bundle(skill)
        return sum(len(b) for _, _, b in bundles)
    except Exception:
        return -1


def _render_markdown(cold: list[float], warm: list[float], skill: str) -> str:
    cs = _stats(cold)
    ws = _stats(warm)
    bundle_bytes = _bundle_size(skill)
    cold_ok = cs["p99"] < SLO_P99_COLD_MS
    warm_ok = ws["p99"] < SLO_P99_WARM_MS
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    # Avoid divide-by-zero if bundle probe failed.
    bundle_kb = (bundle_bytes / 1024.0) if bundle_bytes > 0 else 0.0
    shrink_factor = (160 * 1024) // bundle_bytes if bundle_bytes > 0 else 0
    backend = os.environ.get("FLYWHEEL_API_URL") or os.environ.get(
        "FLYWHEEL_API_URL_DEFAULT", "https://uat-flywheel-backend.lumif.ai"
    )
    return f"""# Phase 151 Latency Baseline

**Measured:** {timestamp}
**Backend:** {backend}
**Git commit:** {_git_commit()}
**Skill under test:** {skill}
**Bundle size:** {bundle_bytes} bytes (~{bundle_kb:.2f} KB)
**Methodology:** v2 (same-process, fresh client per call) -- see below

> NOTE: ROADMAP SC5 originally estimated "160 KB broker bundle" before
> the v1.2 Pattern 3a migration in Phase 150.1 stripped backend-side LLM
> code. Actual bundle size at Phase 151 is **{bundle_bytes} bytes**
> (~{bundle_kb:.2f} KB) -- about **{shrink_factor}x smaller** than the
> original estimate. SLOs apply to this real payload; future regressions
> must re-measure against the current bundle.

## Methodology v2 (current)

Each cold iteration runs inside the SAME Python process as the script
itself, with a fresh ``FlywheelClient()`` and a wiped disk cache per
call. This matches real MCP tool usage: the Python interpreter is warm
(long-running Claude Code / MCP server process) but the connection
pool, disk cache, and server-side bundle-build path are all cold.

| Cost included? | v2 methodology |
|---|---|
| Python interpreter startup | No (paid once per session, not per call) |
| ``import httpx`` / ``flywheel_mcp`` | No (paid once per session) |
| Fresh httpx.Client + TCP + TLS handshake | Yes (per-call) |
| Server-side bundle build + SHA compute | Yes (per-call) |
| SHA-256 verify on bytes | Yes (per-call) |
| Atomic cache write to disk | Yes (per-call) |

**Why the change from v1:** v1 used ``subprocess.run([python, '-c',
...])`` per cold call, which included ~1.5-2.0 s of Python interpreter
boot + ``import httpx`` + ``from flywheel_mcp.api_client import
FlywheelClient`` in every "cold" sample -- overhead real MCP tool users
do NOT pay per call (paid once per long-lived MCP server session). v2
isolates the per-call cost users actually experience. User-approved
Option A (re-measure) after reviewing v1 results. v1 numbers are
archived below for audit trail.

> **Surprise finding:** v2 cold p99 is NOT dramatically better than
> v1. v1 and v2 happen to land in the same 3000-4000 ms range for
> different reasons -- v1's ~1.5 s Python-boot was masking what is
> genuinely a ~1.7-2.0 s median network+server fetch path on this
> ngrok + Supabase topology (raw ``curl /api/v1/health`` measures
> 1.3 s time-to-first-byte with only 42 ms for TCP+TLS). The backend
> itself -- not Python startup, not the CLI -- is where the cold SLO
> budget is going. Investigation targets: ngrok free-tier tunnel
> latency, Supabase round-trips inside ``get_skill_assets_bundle``,
> and whether a same-region deploy or HTTP/2 connection reuse would
> close the gap.

## SLO Results

| Gate | Measured p99 | Threshold | Status |
|---|---|---|---|
| Cold cache | {cs['p99']:.2f} ms | < {SLO_P99_COLD_MS:.0f} ms | {'PASS' if cold_ok else 'FAIL'} |
| Warm cache | {ws['p99']:.4f} ms | < {SLO_P99_WARM_MS:.0f} ms | {'PASS' if warm_ok else 'FAIL'} |

## Cold Cache (same process, fresh FlywheelClient + cleared disk cache per call)

**Methodology v2** (see Methodology v2 section above): fresh
``FlywheelClient()`` instance per call + ``~/.cache/flywheel/skills/``
wiped between iterations + ``bypass_cache=True`` on the fetch. Measures
the actual first-fetch cost an MCP tool user pays on a cold cache: one
HTTPS round-trip (TCP + TLS handshake, new connection pool) + server-side
bundle build + SHA-256 verify + atomic cache write. Python interpreter
startup is NOT included -- it's paid once per MCP server session, not
per call.

| Metric | Value (ms) |
|---|---|
| p50 | {cs['p50']:.2f} |
| p95 | {cs['p95']:.2f} |
| p99 | {cs['p99']:.2f} |
| mean | {cs['mean']:.2f} |
| stddev | {cs['stddev']:.2f} |
| min | {cs['min']:.2f} |
| max | {cs['max']:.2f} |
| n | {cs['n']} |

## Warm Cache (same process, cache + socket pool primed)

Back-to-back ``fetch_skill_assets_bundle`` calls after a priming call.
All hits served from content-addressed disk cache -- SHA validation on
load is the dominant cost.

| Metric | Value (ms) |
|---|---|
| p50 | {ws['p50']:.4f} |
| p95 | {ws['p95']:.4f} |
| p99 | {ws['p99']:.4f} |
| mean | {ws['mean']:.4f} |
| stddev | {ws['stddev']:.4f} |
| min | {ws['min']:.4f} |
| max | {ws['max']:.4f} |
| n | {ws['n']} |

## Raw Samples

<details>
<summary>Cold samples (ms)</summary>

```
{', '.join(f'{v:.2f}' for v in cold)}
```

</details>

<details>
<summary>Warm samples (ms)</summary>

```
{', '.join(f'{v:.4f}' for v in warm)}
```

</details>

## Archived: v1 Methodology Results (subprocess-per-call, 2026-04-19 00:15 +08)

<details>
<summary>Initial measurement -- inflated by ~1.5 s Python interpreter boot per sample</summary>

The original Plan 04 run used ``subprocess.run([python, '-c', ...])``
for every cold measurement. Each subprocess paid the full Python
interpreter startup + ``import httpx`` + ``from
flywheel_mcp.api_client import FlywheelClient`` cost BEFORE the timed
region -- overhead that real MCP tool users do NOT pay per call (it's
paid once per long-lived MCP server session). The numbers are preserved
here for audit trail; they should NOT be used as a regression baseline.

**v1 cold (subprocess-per-call, n=100):**

| Metric | Value (ms) |
|---|---|
| p50 | 1889.82 |
| p95 | 2854.14 |
| p99 | 3279.64 |
| mean | 2014.57 |
| stddev | 331.11 |
| min | 1694.90 |
| max | 3282.74 |
| n | 100 |

**v1 warm (same process, cache primed, n=100):**

| Metric | Value (ms) |
|---|---|
| p50 | 0.1994 |
| p95 | 0.2883 |
| p99 | 0.4000 |
| mean | 0.2042 |
| stddev | 0.0421 |
| min | 0.1588 |
| max | 0.4002 |
| n | 100 |

v1 warm is unchanged by the methodology swap -- only the cold
methodology was flawed.

</details>

## Regression Protocol

Any future phase that modifies
``cli/flywheel_mcp/api_client.py::fetch_skill_assets_bundle``,
``cli/flywheel_mcp/cache.py``, or
``backend/src/flywheel/api/skills.py::get_skill_assets_bundle`` MUST
re-run this script before merge. p99 regressions > 20% block release
until investigated.

Re-run: ``python .planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py``
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument(
        "--n",
        type=int,
        default=100,
        help="sample size per bucket (default 100)",
    )
    ap.add_argument(
        "--skill",
        default="broker-parse-contract",
        help="skill under test (default broker-parse-contract)",
    )
    ap.add_argument(
        "--no-assert-slo",
        action="store_true",
        help="collect data, don't exit-fail on SLO miss",
    )
    ap.add_argument(
        "--out",
        default=str(OUT_PATH),
        help="output markdown path",
    )
    args = ap.parse_args()

    print(
        "Measuring COLD fetches (same process, fresh FlywheelClient + "
        "cleared disk cache per call)...",
        file=sys.stderr,
    )
    cold = measure_cold(args.n, args.skill)
    print(
        "Measuring WARM fetches (same process, cache primed)...",
        file=sys.stderr,
    )
    warm = measure_warm(args.n, args.skill)

    md = _render_markdown(cold, warm, args.skill)
    Path(args.out).write_text(md)
    print(f"Wrote {args.out}", file=sys.stderr)

    cs, ws = _stats(cold), _stats(warm)
    print("\nResults:", file=sys.stderr)
    print(
        f"  p99 cold = {cs['p99']:.2f} ms (threshold {SLO_P99_COLD_MS:.0f} ms)",
        file=sys.stderr,
    )
    print(
        f"  p99 warm = {ws['p99']:.4f} ms (threshold {SLO_P99_WARM_MS:.0f} ms)",
        file=sys.stderr,
    )

    slo_fail = False
    if cs["p99"] >= SLO_P99_COLD_MS:
        print(
            f"FAIL: p99 cold {cs['p99']:.2f} ms >= {SLO_P99_COLD_MS:.0f} ms SLO",
            file=sys.stderr,
        )
        slo_fail = True
    if ws["p99"] >= SLO_P99_WARM_MS:
        print(
            f"FAIL: p99 warm {ws['p99']:.4f} ms >= {SLO_P99_WARM_MS:.0f} ms SLO",
            file=sys.stderr,
        )
        slo_fail = True

    if slo_fail and not args.no_assert_slo:
        sys.exit(1)

    print("OK: SLOs met", file=sys.stderr)


if __name__ == "__main__":
    main()
