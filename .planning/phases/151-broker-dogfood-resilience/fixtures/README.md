# Phase 151 Dogfood Fixtures

## MSA PDF Source

Phase 149-era seed script `backend/scripts/seed_broker_pdfs.py` (verified
present on disk at commit-time) exports `generate_msa_regio()` at
line 67 — a realistic, PII-safe, byte-deterministic MSA PDF generator
using `reportlab`. This is the chosen source for the Phase 151 dogfood
run.

**Title:** *Constructora Regio ↔ Desarrollo Industrial — Parque
Industrial Ciénega Phase II* (per `seed_broker_pdfs.py:68`).

## How to produce the MSA at run time

The harness and runbook deliberately do NOT check a binary PDF into
git. Generate on demand:

```bash
cd /Users/sharan/Projects/flywheel-v2/backend
source .venv/bin/activate
python3 -c "
from pathlib import Path
from scripts.seed_broker_pdfs import generate_msa_regio
out = Path('../.planning/phases/151-broker-dogfood-resilience/fixtures/msa-constructora-regio.pdf')
out.write_bytes(generate_msa_regio())
print(f'wrote {out.resolve()} ({out.stat().st_size} bytes)')
"
```

The generator is byte-deterministic (reportlab's `canvas.Canvas` with
a fixed timestamp / no random IDs by construction in
`seed_broker_pdfs.py`), so two runs on any dev machine produce
identical bytes. You can upload this PDF to a broker project via the
frontend document upload UI, then use that project's UUID for the
`--project-id` arg to `dogfood_harness.py` and step 2 of
`DOGFOOD-RUNBOOK.md`.

## Fallback: use Phase 149 demo seed

If the run-time generation above errors (venv drift, missing
reportlab, etc.), `backend/scripts/seed_broker_demo.py` seeds a full
demo broker project into the dev DB including several PDFs. Run it
once, query the DB for the project UUID, and re-use that for the
dogfood run.

```bash
cd /Users/sharan/Projects/flywheel-v2/backend
source .venv/bin/activate
python3 scripts/seed_broker_demo.py
# Then query for an MSA-type document
```

## Synthetic edge-case PDF (deferred)

Per `151-CONTEXT.md` §Deferred, a synthetic no-Spanish / no-coverage
edge-case PDF is NOT shipped in this phase. If the real-MSA dogfood
reveals coverage-extraction edge cases worth adding, a follow-up
phase generates one with `reportlab` (pre-installed per user global
`~/.claude/CLAUDE.md`).

## Why NO persistent fixture PDFs are committed

- **Binary churn** — regenerating the PDF on one machine with a
  different reportlab patch version would flip bytes; committing the
  PDF invites noisy diffs.
- **PII ambiguity** — even anonymized legal text sometimes carries
  residual identifiers that cleanup missed. The generator is
  auditable; an opaque committed PDF is not.
- **Byte-determinism invariant** — the Phase 147 ZipInfo invariant
  (deterministic zips) extends here in spirit: always prefer a
  deterministic generator over a committed binary.
