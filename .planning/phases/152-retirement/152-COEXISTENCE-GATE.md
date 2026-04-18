# Phase 152 Coexistence-Window Gate

**Purpose:** Confirm every active tenant fetched ≥1 skill bundle from the MCP `skill_assets` path during the coexistence window before the retirement PR is merged.

**Telemetry source:** Application logs. Each bundle fetch emits a line from `backend/src/flywheel/api/skills.py` (around line 710–789) in the form:

```
assets_bundle_fetch tenant=<uuid> root=<skill_name> chain=[...] rollup_sha=<sha12> shas_only=<bool>
```

No database audit table exists — log grep is the authoritative evidence (research §4).

---

## Window definition

- **Window start:** <DATE: Phase 151 deploy date — fill in at gate-check time>
- **Window end:** <DATE: gate-check date; MUST be ≥ window_start + 3 calendar days>
- **Minimum activity per active tenant:** ≥3 distinct `root` invocations across ≥2 calendar days. Rationale: 3 invocations confirms multi-step broker usage (parse-contract, extract-quote, select-carriers); ≥2 days catches intermittent failures.

## Active tenants

Dogfood deployment: 1 active tenant (Sharan / Lumif.ai). If additional tenants exist at gate-check time, enumerate them here before running the query.

| tenant_id | tenant_name | active |
|-----------|-------------|--------|
| <tenant_uuid_1> | <name_1> | yes |

(Update this table with actual tenant UUIDs at gate-check time. Query source: `SELECT id, name FROM tenants WHERE is_active = true;` against production Supabase.)

## Query procedure

Run on the backend host (or against log aggregation if centralized):

```
# 1. Collect all assets_bundle_fetch lines in the window.
grep "assets_bundle_fetch" /var/log/flywheel/app.log \
  | awk -v start="<window_start_iso>" -v end="<window_end_iso>" \
        '$1 >= start && $1 <= end' \
  > /tmp/152-fetches.txt

# 2. Extract unique (tenant, root, date) tuples.
awk '{
  match($0, /tenant=([^ ]+)/, t);
  match($0, /root=([^ ]+)/, r);
  date = substr($1, 1, 10);
  print t[1], r[1], date;
}' /tmp/152-fetches.txt | sort -u > /tmp/152-tuples.txt

# 3. Per tenant, count distinct roots and distinct dates.
awk '{ tenant=$1; roots[tenant]=roots[tenant] FS $2; dates[tenant]=dates[tenant] FS $3 }
     END {
       for (t in roots) {
         split(roots[t], r); n_roots = 0; delete seen;
         for (i in r) if (r[i] && !seen[r[i]]++) n_roots++;
         split(dates[t], d); n_dates = 0; delete seen2;
         for (i in d) if (d[i] && !seen2[d[i]]++) n_dates++;
         printf "tenant=%s distinct_roots=%d distinct_dates=%d\n", t, n_roots, n_dates;
       }
     }' /tmp/152-tuples.txt
```

Expected output per active tenant: `distinct_roots >= 3` AND `distinct_dates >= 2`.

## Pass/fail criteria

- **PASS:** Every active tenant shows `distinct_roots >= 3` AND `distinct_dates >= 2` within the window.
- **FAIL:** Any active tenant falls short. Remediation: extend the window or prompt that tenant to run the missing skills before re-running the gate.

## Evidence block (fill in at gate-check time)

Paste verbatim log excerpts below — at minimum, one line per (tenant, root, date) tuple used to satisfy the criteria.

```
<log_lines>
```

Tenants not meeting the gate (empty if PASS):

```
<tenants_failing>
```

Decision (circle one): **PASS** / **FAIL**
Decision date (UTC): `<decision_date>`
Decision made by: `<human_name>`
