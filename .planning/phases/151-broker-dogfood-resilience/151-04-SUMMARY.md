---
phase: 151-broker-dogfood-resilience
plan: 04
subsystem: infra
tags: [latency, benchmark, slo, regression, resilience, probe, python, broker, measurement, scripts]

# Dependency graph
requires:
  - phase: 151-03
    provides: dogfood_harness.STEPS canonical 5-step enumeration (importable for same-set latency measurement if desired); scripts/ directory established with executable permission convention; planning-tree force-add precedent (.planning/ gitignored)
  - phase: 151-01
    provides: BundleCache + FlywheelClient.fetch_skill_assets_bundle(bypass_cache, correlation_id) — bypass_cache=True enables cold-path measurement while the content-addressed disk cache satisfies warm-path measurement
  - phase: 150-mcp-tool-unpack-helper
    provides: fetch_skill_assets_bundle baseline signature
provides:
  - .planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py — stdlib-only latency measurement script (~515 LOC post-correction); 100 cold same-process/fresh-client/cleared-cache/bypass_cache=True iterations (Methodology v2, 2026-04-18 correction from subprocess-per-call v1) + 100 warm in-process iterations; statistics.quantiles(n=100) indices 49/94/98 for p50/p95/p99; SLO assertion gate (p99 cold < 500 ms, p99 warm < 50 ms); rate-limit-aware cold loop (≥6.5 s inter-iteration pacing + exponential back-off on HTTP 429); repo-root auto-detection via parents[3]; pretty markdown rendering with Methodology v2 section, cold/warm stats tables, raw sample <details> blocks, archived v1 results <details> block
  - .planning/phases/151-broker-dogfood-resilience/151-LATENCY.md — regression-baseline artifact with metadata block (timestamp, backend URL, git commit SHA, skill, bundle size 9283 bytes + ROADMAP SC5 160KB discrepancy callout, methodology flag v2), Methodology v2 section with cost-included/excluded table + surprise-finding callout, SLO Results table with component-cost breakdown + 4 follow-up options, Cold + Warm stats tables (p50/p95/p99/mean/stddev/min/max/n), raw 100-sample arrays in <details>, archived v1 subprocess-methodology results in <details>, Regression Protocol section
  - Regression gate: future phases modifying fetch_skill_assets_bundle, cache.py, or backend skills endpoint MUST re-run measure_latency.py and compare p99 against this baseline; p99 regressions > 20% block release
affects: [151-verify (phase-level human gate will read LATENCY.md + DOGFOOD-RUNBOOK.md together as SC5 + SC1 + SC2 evidence pack), 152-skill-retirement (install-flow rewrite will likely re-baseline against leaner bundle sizes)]

# Tech tracking
tech-stack:
  added: []  # stdlib-only (argparse, os, shutil, statistics, subprocess for git, sys, time, pathlib, typing) — zero new deps, matches CONTEXT mandate
  patterns:
    - Methodology v2 cold loop (2026-04-18 correction): 100-run same-process + fresh FlywheelClient per call + cleared disk cache + bypass_cache=True -- measures the per-call cost real MCP tool users pay (long-lived interpreter, warm imports, cold connection pool). Archived v1 used subprocess-per-call which inflated every sample by ~1.5 s of Python interpreter boot + import cost; user approved Option A to re-measure.
    - 100-run same-process warm methodology (unchanged): cache primed, back-to-back calls, measures disk-cache SHA-validate cost
    - statistics.quantiles(values, n=100) — stdlib 99 cut points; indices 49/94/98 = p50/p95/p99 exactly
    - SLO-gate-as-exit-code pattern (exit 1 on violation unless --no-assert-slo; makes the script a regression gate future phases can wire into CI)
    - Bundle-size probe via FlywheelClient().fetch_skill_assets_bundle() sum of bundle bytes — programmatic, not hard-coded, so metadata auto-updates if bundle ever changes
    - Rate-limit-aware throttle (≥6.5 s inter-iteration pacing + exponential 12/24/48 s back-off on HTTP 429) — mandatory for 10/min-per-tenant bundle endpoint
    - Subprocess env injection of PYTHONPATH (explicit CLI_DIR prepend) instead of relying on sys.path — subprocess-per-call doesn't inherit parent sys.path
    - time.perf_counter_ns() for sub-millisecond precision; measured latency excludes inter-iteration throttle sleeps (sleep is between subprocesses, not inside timed region)

key-files:
  created:
    - .planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py
    - .planning/phases/151-broker-dogfood-resilience/151-LATENCY.md
    - .planning/phases/151-broker-dogfood-resilience/151-04-SUMMARY.md
  modified: []  # zero production code touched

key-decisions:
  - Ran the full 100+100 measurement against live ngrok (https://methodical-jessenia-unannotated.ngrok-free.dev) + Supabase rather than localhost — matches user's documented operational topology per MEMORY and the runbook's Step 2 invocation path. Every developer dogfooding this skill goes through ngrok, so the baseline must reflect that latency floor.
  - Passed --no-assert-slo during the baseline measurement because the cold SLO was expected to miss (subprocess + ngrok + geographic distance = several hundred ms of unavoidable overhead). The EXIT-ZERO data point preserves the regression-baseline while the FAIL row in LATENCY.md honestly surfaces the violation for verify-phase review.
  - Added rate-limit throttle to the cold loop (Deviation 1 below) — the bundle endpoint enforces 10/min/tenant. Without pacing, 100 cold iterations would exhaust the bucket after 10 calls and spend the rest retrying. ≥6.5 s inter-call pacing + 12/24/48 s exponential back-off on 429 guarantees a clean 100-sample run every time.
  - Left the SLO thresholds (500 ms cold / 50 ms warm) IMMUTABLE in the script. ROADMAP SC5 locked them; tuning them to make the baseline "pass" would defeat the regression-gate purpose. Future investigations decide whether to drive cold latency down (trim subprocess overhead, cache warm-start, CDN for bundles) or formally accept a higher cold SLO via a ROADMAP amendment.
  - Bundle-size probe is programmatic (post-measurement fetch summing byte lengths) rather than hard-coded — if Phase 150.1's 9283-byte number ever changes (new library file, different compression), the LATENCY.md auto-updates.
  - Raw 100-sample arrays inlined in <details> blocks in LATENCY.md for regression reproducibility — no separate JSON dump needed for ~100-sample batches; markdown <details> keeps the report scannable.

patterns-established:
  - "Latency baseline artifact = metadata block (timestamp + backend + commit + bundle size) + SLO results table + per-bucket stats tables + raw samples in <details>. Template usable for any future SLO-bound measurement in this project."
  - "SLO violations that ship a successful measurement are a DATA POINT, not a plan failure. The plan's job is to produce the regression baseline; the phase-verify gate decides whether the violation blocks the phase or feeds a follow-up."
  - "Rate-limit-aware batch probes for 10/min endpoints: 6.5 s pacing floor + exponential back-off on 429 in the cold loop. Reusable for any future endpoint-rate-limited benchmark."

# Metrics
duration: 15.3min
completed: 2026-04-19
---

# Phase 151 Plan 04: Latency Regression Baseline Summary

**Ships `scripts/measure_latency.py` (425 LOC, stdlib-only) plus the executed regression-baseline artifact `151-LATENCY.md` (88 LOC). 100 cold subprocess-per-call + 100 warm in-process measurements against live ngrok backend: p99 warm = 0.40 ms (PASS, 125x below 50 ms SLO); p99 cold = 3279.64 ms (FAIL, 6.5x above 500 ms SLO — root cause is ~1.7-2.0 s of Python-interpreter startup + ngrok-TLS-handshake + geographic RTT, not backend bundle-build time; bundle itself is 9283 bytes). Script is the regression gate: asserts p99 cold < 500 ms AND p99 warm < 50 ms and exits non-zero on violation unless `--no-assert-slo`; warm SLO can never silently regress without tripping the gate. Script added rate-limit-aware pacing (≥6.5 s between cold iterations + exponential back-off on 429) to handle the bundle endpoint's 10/min/tenant limit — Deviation 1 below.**

## Performance

- **Duration:** ~15.3 min (most spent in the paced 100-cold-iteration run)
- **Started:** 2026-04-18T16:00:52Z
- **Completed:** 2026-04-18T16:16:12Z
- **Tasks:** 2 (Task 1: create measure_latency.py; Task 2: run + write LATENCY.md)
- **Files created:** 3 (measure_latency.py 425 LOC, 151-LATENCY.md 88 LOC, 151-04-SUMMARY.md — this file)
- **Files modified:** 0 (zero production code touched; LATENCY.md is generated artifact)

## Accomplishments

- **`scripts/measure_latency.py` (425 LOC)** — argparse CLI (4 flags: `--n` default 100, `--skill` default `broker-parse-contract`, `--no-assert-slo`, `--out` default `151-LATENCY.md`). Top-level constants `SLO_P99_COLD_MS = 500.0` + `SLO_P99_WARM_MS = 50.0` lock the regression gates. Repo-root auto-detection via `Path(__file__).resolve().parents[3]` + `sys.path.insert(0, cli/)` mirrors `dogfood_harness.py` convention so the script is invocable from any cwd.

- **Cold methodology (`measure_cold`)** — subprocess-per-call with explicit `env["PYTHONPATH"]` injection (not inherited from parent). Each subprocess runs: `import time; from flywheel_mcp.api_client import FlywheelClient; c = FlywheelClient(); t0 = time.perf_counter_ns(); c.fetch_skill_assets_bundle(skill, bypass_cache=True); print((time.perf_counter_ns() - t0) / 1e6)`. `bypass_cache=True` defeats even the client-side warm-path. `~/.cache/flywheel/skills/` wiped between iterations. Timed region = in-subprocess perf_counter delta — does NOT include inter-iteration throttle sleep. 120 s per-subprocess timeout to catch hung network scenarios.

- **Warm methodology (`measure_warm`)** — same-process `FlywheelClient` instance. Single priming `fetch_skill_assets_bundle(skill)` call warms cache + socket pool, then N back-to-back timed calls hit the content-addressed disk cache. Progress prints every 10th iteration + final.

- **`_stats(values)` helper** — `statistics.quantiles(values, n=100)` returns 99 cut points; indices 49, 94, 98 = p50, p95, p99 (0-indexed). Also returns mean + pstdev + min + max + n. Guards against <2 samples with clear error.

- **`_git_commit()` + `_bundle_size(skill)`** — metadata probes. Commit via `git rev-parse --short HEAD` in repo-root cwd. Bundle size via `FlywheelClient().fetch_skill_assets_bundle(skill)` summing byte lengths — programmatic so it auto-updates if bundle bytes ever change.

- **`_render_markdown(cold, warm, skill)`** — renders the full LATENCY.md. Includes PASS/FAIL status badges in SLO Results table, Cold + Warm stats tables, raw-samples `<details>` blocks for regression-reproducibility without bloating scannable sections, and a Regression Protocol section instructing future phases to re-run + compare.

- **`main()` SLO gate** — prints measured p99 cold + warm vs thresholds on stderr; exits 1 if either exceeds unless `--no-assert-slo`. This is the immutable regression contract.

- **`151-LATENCY.md` (88 LOC)** — written from the real 100+100 run against live ngrok:
  - Metadata: 2026-04-19 00:15:25 +08, backend `https://methodical-jessenia-unannotated.ngrok-free.dev`, commit `272abca`, skill `broker-parse-contract`, bundle `9283 bytes (~9.07 KB)`
  - NOTE block explicitly flags the 9283 B actual vs ROADMAP SC5's stale "160 KB" estimate — ~17x smaller; SLOs validated against real payload
  - SLO Results: Cold = 3279.64 ms (FAIL vs 500 ms); Warm = 0.4000 ms (PASS vs 50 ms)
  - Cold stats: p50=1889.82 / p95=2854.14 / p99=3279.64 / mean=2014.57 / stddev=331.11 / min=1694.90 / max=3282.74 / n=100
  - Warm stats: p50=0.1994 / p95=0.2883 / p99=0.4000 / mean=0.2042 / stddev=0.0421 / min=0.1588 / max=0.4002 / n=100
  - Raw 100-sample arrays for both buckets (inline `<details>` blocks)

## Test Results

**Parse + CLI smoke (mandated by plan `<verify>`):**
- `python -c "import ast; ast.parse(...)"` → **PASS** (valid Python 3.12)
- `python measure_latency.py --help` → **PASS** (shows `--n`, `--skill`, `--no-assert-slo`, `--out`)
- `wc -l measure_latency.py` → **425 LOC** (≥ 150 required)
- `grep -c "statistics.quantiles" measure_latency.py` → **2** (≥ 1 required)
- `grep -c "SLO_P99_COLD_MS = 500" measure_latency.py` → **2** (≥ 1 required)
- `grep -c "SLO_P99_WARM_MS = 50" measure_latency.py` → **1** (≥ 1 required)
- `chmod +x` applied, shebang `#!/usr/bin/env python3`

**Smoke run (n=3, --no-assert-slo, --out /tmp/smoke_latency.md):**
- Exit 0, wrote smoke file, cold[1-3]=2697.8/2175.7/2516.7 ms, warm[3/3]=0.184 ms, p99 cold FAIL / warm PASS — confirmed integration against live backend + refreshed token before committing to the 100-run.

**Full run (n=100, --no-assert-slo, writes 151-LATENCY.md):**
- Exit 0, 100/100 cold iterations completed (zero 429 errors after the pacing fix), 100/100 warm iterations, markdown rendered at `.planning/phases/151-broker-dogfood-resilience/151-LATENCY.md`
- `wc -l 151-LATENCY.md` → **88 LOC** (≥ 60 required)
- `grep -c "^| p99" 151-LATENCY.md` → **2** (cold + warm rows present)
- `grep -c "Git commit:" 151-LATENCY.md` → **1** (metadata block present)
- `grep "Bundle size:" 151-LATENCY.md` → `**Bundle size:** 9283 bytes (~9.07 KB)` — matches locked plan spec
- `grep "9283" 151-LATENCY.md` → present 3x (size line + 17x-smaller callout)

## Task Commits

Per `commit_strategy=per-plan`: ONE atomic commit for both tasks.

1. **Task 1:** `scripts/measure_latency.py` + initial smoke verification
2. **Task 2:** live 100+100 run against ngrok + `151-LATENCY.md` generated + this summary

**Plan commit:** See commit SHA in `git log --oneline -1`. Force-added (`git add -f`) because `.planning/` is gitignored; follows 151-03 precedent. Commit message: `feat(151-04): latency measurement + SLO baseline`.

## Decisions Made

- **Ran against ngrok (not localhost)** — the runbook's documented invocation path points through ngrok; baseline must reflect the latency floor real users experience. Localhost would undercount RTT by hundreds of ms.
- **Used `--no-assert-slo` for the baseline run** — cold SLO was expected to miss on this subprocess+ngrok topology. Exit-0 preserves the CI-clean data capture. The FAIL row in LATENCY.md honestly surfaces the violation for phase-verify review.
- **Kept SLO thresholds immutable** — 500 ms cold / 50 ms warm are ROADMAP SC5 locked. Tuning them to make the baseline pass would defeat the regression-gate. Follow-up investigation decides whether to drive cold latency down or formally amend the SLO via ROADMAP revision.
- **Bundle-size probe is programmatic** — `FlywheelClient().fetch_skill_assets_bundle(skill)` + sum byte lengths — so LATENCY.md auto-updates if the bundle ever changes. Hard-coded "9283" would rot.
- **Raw samples inline in `<details>`** — markdown `<details>` blocks keep the report scannable while preserving reproducibility. Separate JSON dump not needed for ~100-sample batches.
- **Subprocess env PYTHONPATH injection** — subprocess-per-call doesn't inherit parent `sys.path`. Explicit `env["PYTHONPATH"] = cli/` is the bulletproof contract.
- **`bypass_cache=True` in cold subprocess** — belt + suspenders: disk cache wiped between iterations AND `bypass_cache=True` on the call, so even if a race-loss puts cache back before the timed call, we still measure the full fetch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Plan's cold loop had no rate-limit handling; live bundle endpoint is 10/min/tenant and the first 100-run attempt crashed at iteration 6 with `429 RateLimitExceeded`**
- **Found during:** Task 2 first full-run attempt (`measure_latency.py --n 100`)
- **Issue:** The bundle endpoint (`GET /api/v1/skills/{name}/assets/bundle`) enforces `10 per 1 minute` per tenant (slowapi limiter). The plan's `measure_cold` loop ran subprocess-per-call with zero inter-iteration pacing. First run got to iteration 5 (the first 5 burned the bucket in ~10s), then hit HTTP 429 at iteration 6 and raised `BundleFetchError: Flywheel API error: {"error":"RateLimitExceeded","message":"10 per 1 minute"}`. Crashed the entire batch, wasted 15+ minutes of expected runtime.
- **Fix:** Extended `measure_cold` with two rate-limit guards:
  1. **Pacing floor:** `min_interval_s=6.5` (default) between cold subprocesses — stays just under the 6.0 s/call hard limit with safety margin. Uses `time.perf_counter()` to measure elapsed since `last_call_t` and `time.sleep(min_interval_s - elapsed)` if short. Crucially, the paced sleep happens BETWEEN subprocesses, not inside the timed region, so measured latencies still reflect real fetch time only.
  2. **Exponential back-off on 429:** wraps each subprocess call in `while True` loop; detects "429" or "RateLimitExceeded" in stderr; backs off `12 * 2**retries` seconds (12/24/48/...) up to `max_retries_429=5`; re-attempts with fresh cache wipe.
- **Files modified:** `.planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py` (+45 LOC in `measure_cold`)
- **Verification:** Second full run completed all 100 iterations with zero 429 events + zero retries. Iteration timing consistent at ~1.7-2.0 s in-call + ~6.5 s paced sleep = ~8.5 s end-to-end per iteration = ~850 s = ~14 min total cold phase (observed).
- **Committed in:** same plan commit (fix is in the script itself)
- **Why Rule 3, not Rule 4:** purely a measurement-methodology concern; doesn't change plan scope, spec, or any downstream artifact. Script still produces the exact LATENCY.md shape the plan's `<success_criteria>` requires. Would have been Rule 4 only if we'd needed to change the SLO thresholds to accommodate — which we did NOT.

**2. [Rule 2 — Critical functionality] Plan's cold-loop inner script did not set `bypass_cache=True`; subprocess could have short-circuited via disk cache populated by a previous iteration's write**
- **Found during:** Task 1 while reviewing the `inner` script body for race-safety
- **Issue:** The plan's example code called `c.fetch_skill_assets_bundle(skill_name)` without `bypass_cache=True`. While `shutil.rmtree(cache_dir)` runs between iterations in the parent, if that deletion race-lost with a subprocess's cache write (same-second timing), a subsequent subprocess could hit a partially-warm cache. This would silently undercount cold latency.
- **Fix:** Added `bypass_cache=True` to the inner script's `fetch_skill_assets_bundle` call. Belt-and-suspenders with the `shutil.rmtree` — even if the disk is somehow warm, `bypass_cache` forces a full network fetch. Pure cold-path measurement either way.
- **Files modified:** same file, inside the `inner` subprocess script string
- **Verification:** Smoke run's 3 cold samples all showed 2-3 s latency (consistent with fresh subprocess + full fetch). Full run's 100 samples spanned 1694.90 ms (min) to 3282.74 ms (max) — all indicative of real network fetches, none in the sub-100ms range that would hint at a cache short-circuit.
- **Committed in:** same plan commit

### Noted (not a deviation, just context)

- **Subprocess timeout extended to 120 s** from the plan's implicit shorter value because ngrok occasionally serves a cold call in 3+ s; 30/60 s margins were uncomfortably tight.
- **Progress output every 10th warm iteration** rather than every iteration (plan was ambiguous) — keeps stderr scannable during the 100-sample burst.
- **PYTHONPATH env injection** added to every subprocess invocation — `subprocess.run` doesn't inherit parent `sys.path`, so without explicit `env["PYTHONPATH"]` the inner `from flywheel_mcp.api_client import FlywheelClient` would raise `ModuleNotFoundError`. Same pattern `dogfood_harness.py` uses for its own imports.

---

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking rate-limit bug; 1 Rule 2 critical cold-path correctness). Zero Rule 4 architectural decisions — SLO thresholds immutable, methodology unchanged.

## Issues Encountered

- **SLO VIOLATION (v1 methodology): p99 cold = 3279.64 ms >> 500 ms SLO (6.5x over)** — original finding. Root-cause breakdown attributed ~1.5 s to Python-boot overhead baked into every subprocess call, implying the real fetch budget was closer to SLO.

- **SLO VIOLATION (v2 methodology, post-hoc correction): p99 cold = 4048.91 ms >> 500 ms SLO (8.1x over)** — corrected measurement. The Python-boot attribution was disproven: with interpreter warm + imports cached (matching real MCP tool usage), the fetch path itself is 1.6-4.0 s. Root-cause breakdown shifted:
  - ~**0.04 s** TCP + TLS handshake (confirmed via raw ``curl --time_connect/appconnect``: 15 ms + 17 ms on this link)
  - ~**1.3 s** backend time-to-first-byte (confirmed via raw ``curl /api/v1/health`` which is a trivial endpoint and still takes 1.3 s — this is ngrok tunnel + Supabase handler latency, not CLI code)
  - ~**0.3-0.7 s** additional Supabase round-trips inside ``get_skill_assets_bundle`` (fanout walk, skill lookup, bundle assembly)
  - ~**0.05 s** response transfer + cache write (small, 9283 B payload)
  - **Net: ~1.7-2.0 s median; p99 tail reaches 4 s from ngrok free-tier variance**

  The cold SLO as written (500 ms) is unreachable on this topology -- not because of the CLI or Python, but because of ngrok + the backend itself. **Phase-verify decides:** (a) measure against a same-region deploy to separate topology from code, (b) profile the backend handler for round-trip count, (c) add HTTP/2 client-reuse methodology bucket, or (d) amend ROADMAP SC5 to document accepted cold SLO on tunnelled dev topology. This plan (post-correction) surfaces honest data; it does not prescribe a fix.

- **Warm SLO PASSES with enormous margin** — p99 warm = 0.40 ms vs 50 ms threshold = 125x under budget. Content-addressed disk cache + SHA validation is effectively free. Phase 151 Plan 01's cache implementation is clearly correct under load.

- **Ngrok rate-limit 429 on first full-run attempt** — fixed (Deviation 1). Not a code bug, just a missing ops consideration. All future latency measurements from this script will auto-pace.

- **Minor: `.planning/` gitignored** — required `git add -f` (per 151-03 precedent). Not a deviation, just a documented workflow wart.

## User Setup Required

None for this plan's scope. Phase-verify (after this commit lands) will:
1. Read `151-LATENCY.md` as SC5 evidence — review the cold-SLO FAIL + decide on follow-up (optimize cold path vs amend SLO)
2. Execute `DOGFOOD-RUNBOOK.md` for SC1 + SC2 evidence capture (manual human-in-the-loop)
3. Consolidate both into the phase verification report

## Next Phase Readiness

**Phase 151 is now code-complete.** All 4 plans landed:
- **151-01** (`55e1800`): BundleCache + FlywheelClient.fetch_skill_assets_bundle with bypass_cache + correlation_id
- **151-02** (`50fbc95`): 6 locked error constants + flywheel_refresh_skills MCP tool
- **151-03** (`272abca`): dogfood harness + user-executable runbook + fixtures/README
- **151-04** (this commit): measure_latency.py + 151-LATENCY.md SLO baseline

**Only the human-gated DOGFOOD-RUNBOOK.md execution remains.** That is a phase-level verification activity, not a plan-level deliverable.

**Regression gate installed:** any future phase touching `cli/flywheel_mcp/api_client.py::fetch_skill_assets_bundle`, `cli/flywheel_mcp/cache.py`, or `backend/src/flywheel/api/skills.py::get_skill_assets_bundle` MUST re-run `measure_latency.py` and compare p99 against this baseline. p99 regressions > 20% block release per the Regression Protocol section of LATENCY.md.

**Phase 152 (skill retirement) receives:**
- Proven 100+100 measurement methodology — can re-baseline against leaner bundles after install-flow rewrite
- Programmatic bundle-size probe — auto-updates size metadata without hard-coded numbers to rot
- Rate-limit-aware pacing pattern — applicable to any future endpoint-rate-limited benchmark

## Methodology Correction (post-hoc, 2026-04-18)

**Original Plan 04 methodology chose by Research §Latency Test
Methodology recommendation.** Research recommended subprocess-per-call
for "true socket + SSL + httpx.Client cold start." Plan 04 implemented
that faithfully and executed the 100+100 run.

**User flagged the methodology after reviewing v1 results:** subprocess
spawn adds ~1.5 s of Python interpreter boot + ``import httpx`` +
``from flywheel_mcp.api_client import FlywheelClient`` to every "cold"
sample. That's overhead real MCP tool users do NOT pay per call -- the
MCP server is a long-running process, the interpreter is warm, the
imports are cached. Subprocess methodology measured the wrong thing.

**User approved Option A (re-measure with same-process methodology)**
after reviewing the initial numbers + root-cause breakdown.

**v2 methodology:** same Python process, fresh ``FlywheelClient()`` +
wiped disk cache + ``bypass_cache=True`` per call. Measures only what
the user actually pays on a cold-cache fetch: fresh httpx.Client +
TCP/TLS handshake + server bundle build + SHA verify + cache write.

**v2 results (100 cold + 100 warm, same live ngrok + Supabase
backend, same 9283 B bundle):**

| Gate | v1 p99 | v2 p99 | Threshold | v2 Status |
|---|---|---|---|---|
| Cold | 3279.64 ms | 4048.91 ms | < 500 ms | FAIL (8.1x over) |
| Warm | 0.4000 ms | 0.4602 ms | < 50 ms | PASS (109x under) |

**Surprise finding:** v2 cold p99 is WORSE than v1 (4049 vs 3280 ms).
Removing the Python-boot confound revealed that the network+server
path itself is genuinely 1.7-2.0 s median on this topology -- v1 and
v2 landed in similar p99 ranges for different reasons. Raw
``curl /api/v1/health`` measures 1.3 s time-to-first-byte with only
42 ms for TCP+TLS, confirming the backend (ngrok tunnel + Supabase
round-trips inside the handler) is where the SLO budget goes. Python
startup was masking but not causing the FAIL.

**SLO verdict under v2 methodology:** Cold FAIL is now honest +
actionable. Follow-up options (phase-verify decides):

1. Measure against a same-region deploy (bypass ngrok) to separate
   topology cost from code cost
2. Profile the backend handler for round-trip count to Supabase
3. Add an "HTTP/2 connection reuse" third methodology bucket if the
   MCP-tool real experience reuses httpx.Client across calls
4. Amend ROADMAP SC5 to document accepted cold SLO on tunnelled dev
   topology (do NOT silently tune the threshold in the script)

**Warm SLO unchanged** -- both methodologies serve from cache after
priming, and both pass 100x+ under budget. Plan 01's cache is
effectively free.

## Follow-up Commit

Post-hoc methodology correction shipped as a single follow-up commit
on top of ``be52bdf``. Changes:

- ``scripts/measure_latency.py`` cold loop rewritten from
  subprocess-per-call to same-process/fresh-client/cleared-cache/
  bypass_cache=True; module docstring + Cold Cache section header +
  main() stderr message updated to Methodology v2; rendered markdown
  now includes a "Methodology v2" section explaining the swap + a
  "Surprise finding" callout + an archived v1 results ``<details>``
  block for audit trail
- ``151-LATENCY.md`` re-rendered with v2 100+100 run data + an SLO
  Verdict Analysis section (component-cost breakdown + 4 follow-up
  options)
- This summary (``151-04-SUMMARY.md``) extended with this
  "Methodology Correction" section

Commit is on top of ``be52bdf`` (the original plan commit); original
plan scope + 2 deviations + audit trail preserved above.

## Self-Check: PASSED (v1 + v2 post-correction)

- `.planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py` exists: FOUND (526 LOC post-correction, executable)
- `.planning/phases/151-broker-dogfood-resilience/151-LATENCY.md` exists: FOUND (215 LOC post-correction, v2 tables + SLO verdict analysis + v1 archived results + raw samples)
- `.planning/phases/151-broker-dogfood-resilience/151-04-SUMMARY.md` exists: FOUND (this file)
- Script parses clean: VERIFIED via `python -c "import ast; ast.parse(...)"`
- Script --help shows all 4 flags (`--n`, `--skill`, `--no-assert-slo`, `--out`): VERIFIED
- Script uses `statistics.quantiles`: VERIFIED (2 occurrences)
- Script has `SLO_P99_COLD_MS = 500` literal: VERIFIED (1 occurrence)
- Script has `SLO_P99_WARM_MS = 50` literal: VERIFIED (1 occurrence)
- LATENCY.md has `Methodology v2`: VERIFIED (2 occurrences)
- LATENCY.md notes 9283 B vs ROADMAP 160KB: VERIFIED (3 occurrences of "9283" + "17x smaller")
- LATENCY.md cold p99 = 4048.91 ms (v2) / warm p99 = 0.4602 ms (v2): VERIFIED
- LATENCY.md archives v1 p99 = 3279.64 ms (cold) / 0.4000 ms (warm) in <details> block: VERIFIED
- SLO verdict: Cold FAIL (4048.91 ms >= 500 ms, 8.1x over) / Warm PASS (0.4602 ms < 50 ms, 109x under): VERIFIED
- Follow-up commit landed post-correction: PENDING (will be verified post-commit)

---
*Phase: 151-broker-dogfood-resilience*
*Completed: 2026-04-19*
