# Phase 151 Dogfood Runbook

**Purpose:** capture live **SC1** (MCP-only skill delivery) and **SC2**
(offline cache fallback) evidence by running `/broker:parse-contract`
against a machine where `~/.claude/skills/broker/` has been renamed
out of the way. This runbook is USER-EXECUTED — it requires a fresh
Claude Code session + a real or generated MSA PDF, neither of which
a programmatic harness can simulate.

Programmatic probes (materialize round-trip, extract endpoint, save
persistence, DB verification, offline-sim WARN) live in
`scripts/dogfood_harness.py`. Run the harness first for a fast
mechanical sanity check; this runbook is the human-in-the-loop
companion.

---

## Prerequisites

- [ ] Backend live (ngrok + Supabase). Smoke:
      `curl -sS "$FLYWHEEL_API_URL/api/v1/health"` returns 200.
- [ ] `flywheel login` recent (within session TTL). Expired token =
      Step 2 fails with ERR_401 (`Session expired. Run \`flywheel
      login\` and retry.`).
- [ ] A broker project exists with a known UUID. Either create via
      frontend or via
      `backend/scripts/seed_broker_demo.py`. Note the UUID.
- [ ] MSA PDF ready to upload. Either a real anonymized one or
      generate via
      `backend/scripts/seed_broker_pdfs.py::generate_msa_regio`
      (see `fixtures/README.md`).
- [ ] Plans 151-01 + 151-02 complete (cache module + 6 locked error
      constants + `flywheel_refresh_skills` tool all shipped).
      Verify: `git log --oneline --all | grep -E '151-0[12]'`.
- [ ] Baseline git state captured for post-run diff:
      `git log -1 --format='%H %s'` noted.

---

## Step 1 — Rename the local broker skills directory

```bash
# Belt-and-suspenders: only rename if broker/ exists AND .broker.bak doesn't
if [ -d ~/.claude/skills/broker ] && [ ! -d ~/.claude/skills/.broker.bak ]; then
  mv ~/.claude/skills/broker ~/.claude/skills/.broker.bak
fi
ls -la ~/.claude/skills/ | grep -iE 'broker|\.broker\.bak'
```

**Expected:** only `.broker.bak` (hidden) in the listing — NO
unhidden `broker/` entry. If the directory didn't exist to begin
with, this step is a no-op; proceed.

**If `~/.claude/skills/broker` is missing entirely** (never installed
locally), that's ALSO fine — we just can't prove "previously-present
skill doesn't shadow MCP fetch" (only "MCP fetch works when skill
absent"). Note this in the evidence paste-back.

---

## Step 2 — Fresh Claude Code session + upload MSA + run slash command

1. Start a **new** Claude Code session (fresh context — Cmd+N or
   equivalent; do NOT reuse the one executing Phase 151).
2. `cd /Users/sharan/Projects/flywheel-v2`.
3. Upload your MSA PDF to the target broker project via the
   frontend UI (project detail → document upload → select file).
4. In the fresh Claude Code session, run:

   ```
   /broker:parse-contract <project-id>
   ```

5. Watch the session for:
   - A `flywheel_fetch_skill_assets` tool invocation (visible in
     Claude Code's tool-call UI). This MUST fire — since local
     `~/.claude/skills/broker/` is renamed, the skill can only be
     sourced via MCP.
   - The subsequent extract call (`POST /api/v1/broker/extract/
     contract-analysis`).
   - Claude's inline coverage analysis.
   - The save call (`POST /api/v1/broker/save/contract-analysis`).
6. Let the command run to completion.

**Expected SC1 evidence:**

- [ ] `/broker:parse-contract` completes without error.
- [ ] Tool-use transcript shows `flywheel_fetch_skill_assets` was
      invoked at least once (proves MCP-only delivery path).
- [ ] Final output summarizes extracted coverages.
- [ ] Zero messages matching `ERR_401`/`ERR_403`/`ERR_404`/
      `ERR_503`/`ERR_CHECKSUM`/`ERR_OFFLINE` from
      `cli/flywheel_mcp/errors.py`.
- [ ] Zero `BundleSecurityError` / zip-slip / path-traversal errors.

**Paste back:** the full Claude Code response transcript (redact any
incidental PII you notice).

---

## Step 3 — DB verification

With your JWT and project-id handy:

```bash
JWT="<paste your token>"
PROJECT_ID="<paste the same UUID as step 2>"

curl -sS -H "Authorization: Bearer $JWT" \
     "$FLYWHEEL_API_URL/api/v1/broker/projects/$PROJECT_ID" \
  | jq '{
      project_id: .id,
      coverages: (.coverages | length),
      sample_coverage: (.coverages[0] // null | {coverage_type, required_limit, currency}),
      documents: (.documents | length)
    }'
```

**Expected:**
- `coverages` ≥ 1 (proves save endpoint wrote).
- `sample_coverage` has real values (not nulls across the board).
- `documents` ≥ 1 (the MSA you uploaded).

**Paste back:** the full JSON output.

---

## Step 4 — Offline simulation (SC2 evidence)

Now prove the cache-fallback path works when the backend is
unreachable. The harness does the mechanical probe in one shot:

```bash
# Confirm cache populated by Step 2's live fetch
ls ~/.cache/flywheel/skills/  # expect at least one <sha256>/ dir

# Run harness offline-sim
FLYWHEEL_API_URL=http://127.0.0.1:1 python3 \
  .planning/phases/151-broker-dogfood-resilience/scripts/dogfood_harness.py \
  --project-id $PROJECT_ID \
  --offline-sim \
  --skip-rename
```

**Expected stderr:**

```
Dogfood correlation_id=<8 hex chars>

=== SC2: Offline cache fallback ===
  [warmup] fetching broker-parse-contract to populate cache...
  [offline] FLYWHEEL_API_URL=http://127.0.0.1:1
WARN: Backend unreachable. Using cached broker-parse-contract bundle (cached <N>s/m/h ago, <ttl remaining>).
  [offline] bundle served from cache — SC2 evidence captured
  [offline] NOTE: watch stderr above for 'WARN: Backend unreachable.' line
```

Key line: `WARN: Backend unreachable. Using cached
broker-parse-contract bundle`. If that line appears **and** exit code
is 0, SC2 passes.

**Paste back:** full stderr + exit code (`echo $?` right after).

---

## Step 5 — Cleanup + restoration

```bash
# Restore the local skills dir (if harness atexit didn't already)
if [ -d ~/.claude/skills/.broker.bak ] && [ ! -d ~/.claude/skills/broker ]; then
  mv ~/.claude/skills/.broker.bak ~/.claude/skills/broker
fi
ls ~/.claude/skills/broker | head -20  # normal SKILL.md files expected
```

If the harness's atexit handler fired, this is a no-op. Ctrl-C
mid-run is handled by the SIGINT signal handler. This step is
insurance — run it unconditionally, even if every prior step
succeeded or failed partway.

---

## Evidence Paste-Back Template

Paste the three blocks below into the phase's verify-phase
conversation:

### Step 2 evidence (SC1 — Claude Code transcript)

```
<full /broker:parse-contract output from a fresh Claude Code session>
```

### Step 3 evidence (SC1 — DB verification)

```json
<jq output from Step 3>
```

### Step 4 evidence (SC2 — Offline WARN + exit 0)

```
<full stderr from Step 4>
exit code: <0 expected>
```

---

## Troubleshooting

| Symptom | Likely cause | One-line fix |
|---|---|---|
| Step 2 `/broker:parse-contract` raises `Session expired.` | `flywheel login` token expired | Run `flywheel login`; restart fresh session; retry Step 2. |
| Step 2 raises `Skill not found: broker-parse-contract.` | Skill not seeded in prod DB | Run `backend/scripts/seed_skills.py --skills-dir skills` (see Phase 150.1 Plan 03 for the SHA gate). |
| Step 2 raises `Flywheel backend unreachable after 3 attempts.` | ngrok down or backend not running | `./start-dev.sh` from repo root; verify `curl $FLYWHEEL_API_URL/api/v1/health` is 200; retry. |
| Step 2 raises `Bundle integrity check failed for broker-parse-contract.` | Cache tampered OR local disk corruption | `flywheel_refresh_skills(name="broker-parse-contract")` from Plan 02; or delete `~/.cache/flywheel/skills/` and retry. |
| Step 4 raises `BundleCacheError` / `Cached bundle expired` | Cache was never populated OR >24h since Step 2 warmed it | Re-run Step 2 first (warms cache against live backend), then retry Step 4. |
| Step 4 succeeds but NO `WARN: Backend unreachable.` line | Bug in Plan 01 offline-fallback stderr wiring | Re-run `pytest cli/tests/test_cache.py -v -k offline` to surface the regression; file a bug. |
| Step 4 hangs instead of raising ConnectError | RST port 1 not rejected (rare — corp firewall) | Replace `http://127.0.0.1:1` with `http://127.0.0.1:59999` (any unused high port) and retry. |
| `~/.claude/skills/.broker.bak` persists after Step 5 | Atexit handler didn't fire (kill -9, crash) | Manual `mv ~/.claude/skills/.broker.bak ~/.claude/skills/broker`. |
| Step 2 times out waiting for PDF upload | Frontend upload silently failing | Open DevTools → Network → retry upload; check for 413 (too large) or 401 (session). |
| Harness exits with `ModuleNotFoundError: flywheel_mcp` | Not running from repo root / `cli/` not on path | `cd /Users/sharan/Projects/flywheel-v2` first; harness inserts `cli/` onto sys.path but only resolves it from repo root. |
