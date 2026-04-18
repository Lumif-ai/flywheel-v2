# Phase 151 Latency Baseline

**Measured:** 2026-04-19 00:15:25 +08
**Backend:** https://methodical-jessenia-unannotated.ngrok-free.dev
**Git commit:** 272abca
**Skill under test:** broker-parse-contract
**Bundle size:** 9283 bytes (~9.07 KB)

> NOTE: ROADMAP SC5 originally estimated "160 KB broker bundle" before
> the v1.2 Pattern 3a migration in Phase 150.1 stripped backend-side LLM
> code. Actual bundle size at Phase 151 is **9283 bytes**
> (~9.07 KB) -- about **17x smaller** than the
> original estimate. SLOs apply to this real payload; future regressions
> must re-measure against the current bundle.

## SLO Results

| Gate | Measured p99 | Threshold | Status |
|---|---|---|---|
| Cold cache | 3279.64 ms | < 500 ms | FAIL |
| Warm cache | 0.4000 ms | < 50 ms | PASS |

## Cold Cache (subprocess per call, cache wiped between iterations)

Includes Python interpreter startup + httpx.Client instantiation + fresh
TCP + TLS handshake to the backend. Representative of a first-invocation
session on a clean dev machine. Subprocess startup overhead
(~30-60 ms on macOS) is baked into every sample -- intentional, matches
real CLI/MCP cold-boot UX.

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

## Warm Cache (same process, cache + socket pool primed)

Back-to-back ``fetch_skill_assets_bundle`` calls after a priming call.
All hits served from content-addressed disk cache -- SHA validation on
load is the dominant cost.

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

## Raw Samples

<details>
<summary>Cold samples (ms)</summary>

```
2583.24, 2388.44, 2340.12, 2188.74, 1984.15, 1842.49, 1855.68, 1763.37, 1901.53, 1887.89, 3282.74, 2168.42, 2193.63, 2036.80, 1943.71, 1948.91, 1749.44, 1923.75, 1852.38, 1922.63, 2152.32, 1789.70, 1815.64, 1806.52, 1916.97, 2281.83, 1816.78, 1906.87, 1925.86, 1895.31, 2698.44, 2506.20, 2965.13, 1756.67, 1697.48, 1832.03, 1811.72, 1845.15, 1715.88, 1828.38, 2640.71, 2862.33, 1737.76, 1785.51, 1778.38, 2385.40, 1830.39, 2667.64, 2268.03, 2031.20, 1811.28, 1927.05, 1694.90, 1923.27, 1782.92, 1764.03, 1773.46, 1935.38, 1860.31, 2081.98, 1825.84, 1846.73, 1709.30, 2048.92, 1813.29, 1735.00, 1881.65, 2069.78, 2062.52, 1788.87, 2876.00, 1910.50, 2269.74, 1729.89, 2972.26, 2560.73, 1822.39, 2254.92, 1888.04, 2525.87, 1956.25, 1700.21, 2469.52, 1755.40, 2044.48, 1827.58, 1808.43, 1827.25, 1786.82, 2074.19, 1891.60, 1724.87, 1768.17, 1747.60, 1874.42, 1739.96, 2033.07, 1831.78, 1915.19, 1823.42
```

</details>

<details>
<summary>Warm samples (ms)</summary>

```
0.3761, 0.2888, 0.2762, 0.2780, 0.2325, 0.2238, 0.2165, 0.2191, 0.2115, 0.2192, 0.2183, 0.2169, 0.2086, 0.2087, 0.2075, 0.2097, 0.2395, 0.2218, 0.2167, 0.2153, 0.2099, 0.2152, 0.2055, 0.2083, 0.2130, 0.2057, 0.2210, 0.2062, 0.2181, 0.2072, 0.2077, 0.3480, 0.2547, 0.2080, 0.2057, 0.1968, 0.2047, 0.2001, 0.1941, 0.1905, 0.1913, 0.1941, 0.2350, 0.2197, 0.2353, 0.1966, 0.1878, 0.1882, 0.1895, 0.1884, 0.1927, 0.1848, 0.1831, 0.1819, 0.1862, 0.1628, 0.1615, 0.1624, 0.1661, 0.1608, 0.1626, 0.1694, 0.1610, 0.1594, 0.1594, 0.1591, 0.1591, 0.3003, 0.4002, 0.2440, 0.2317, 0.2187, 0.2208, 0.2095, 0.2005, 0.2030, 0.1981, 0.1965, 0.1949, 0.1962, 0.2059, 0.1972, 0.1987, 0.1968, 0.1911, 0.1913, 0.1942, 0.1825, 0.1588, 0.1610, 0.1614, 0.1625, 0.1603, 0.1600, 0.1593, 0.1595, 0.1603, 0.1597, 0.1594, 0.1609
```

</details>

## Regression Protocol

Any future phase that modifies
``cli/flywheel_mcp/api_client.py::fetch_skill_assets_bundle``,
``cli/flywheel_mcp/cache.py``, or
``backend/src/flywheel/api/skills.py::get_skill_assets_bundle`` MUST
re-run this script before merge. p99 regressions > 20% block release
until investigated.

Re-run: ``python .planning/phases/151-broker-dogfood-resilience/scripts/measure_latency.py``
