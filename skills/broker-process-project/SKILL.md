---
public: true
name: broker-process-project
version: "1.1"
web_tier: 3
description: Full placement workflow — from uploaded documents to carrier solicitations
context-aware: true
triggers:
  - /broker:process-project
tags:
  - broker
  - insurance
  - pipeline
  - placement
assets: []
depends_on: ["broker"]
dependencies:
  skills:
    - broker-parse-contract
    - broker-parse-policies
    - broker-gap-analysis
    - broker-select-carriers
    - broker-fill-portal
    - broker-draft-emails
  files:
    - "~/.claude/skills/broker/api_client.py"
---

# Broker Pipeline: process-project

> **Version:** 1.0 | **Last Updated:** 2026-04-15
> **Changelog:** Phase 135 — initial pipeline implementation

This pipeline chains 6 step skills to take a broker project from uploaded documents all the way
to carrier solicitation drafts. It activates `BROKER_PIPELINE_MODE=1` to suppress redundant
hook API calls during batch writes, then deactivates it before email drafts so the audit trail
hooks fire normally.

---

## Pipeline Announcement

When `/broker:process-project` is triggered, announce:

```
Starting process-project pipeline. This chains 6 steps:
parse-contract → parse-policies → gap-analysis → select-carriers → fill-portal → draft-emails

You will be asked for input at each step. The pipeline will pause at fill-portal for
portal login — you must complete those submissions manually before the pipeline continues.
```

---

## Inputs

Ask the broker for the following before starting:

1. **PROJECT_ID** — UUID of the broker project (from the Flywheel web app project detail page)
2. **CONTRACT_PDF** — absolute path to the MSA contract PDF on your local machine
3. **POLICY_PDFS** — comma-separated absolute paths to existing policy PDFs, or type `skip` to skip

Validate that PROJECT_ID matches UUID format before proceeding.

---

## Activate Pipeline Sentinel

After collecting inputs, activate the pipeline mode sentinel:

```python
import os
os.environ["BROKER_PIPELINE_MODE"] = "1"
print("Pipeline mode ON — hooks suppressed during batch writes")
```

This prevents the coverage-write hook and quote-write hook from firing redundant API calls
while each step skill writes data.

---

## Step 1 — parse-contract

Execute:

```
Now executing Step 1: parse-contract.
Follow the instructions in ~/.claude/skills/broker/steps/parse-contract.md
for PROJECT_ID={project_id} and PDF_PATH={contract_pdf}.
```

Wait for parse-contract to complete and report the extracted coverages count.
Confirm success before proceeding to Step 2. If parse-contract fails or returns 0 coverages,
ask the broker whether to continue or abort.

---

## Step 2 — parse-policies

If POLICY_PDFS were provided (not `skip`):

```
Now executing Step 2: parse-policies.
Follow the instructions in ~/.claude/skills/broker/steps/parse-policies.md
for PROJECT_ID={project_id} with policy PDFs: {policy_pdfs}.
```

Wait for completion and report how many coverage records were updated.

If POLICY_PDFS was `skip`:

```
Step 2 skipped — no policy PDFs provided. Coverage current_limit and carrier fields
will remain empty until policies are parsed.
```

---

## Step 3 — gap-analysis

Execute:

```
Now executing Step 3: gap-analysis.
Follow the instructions in ~/.claude/skills/broker/steps/gap-analysis.md
for PROJECT_ID={project_id}.
```

Wait for the gap summary table. If 0 gaps found, note it and ask the broker:

```
Gap analysis found 0 coverage gaps. This may mean all coverages meet MSA requirements,
or that parse-policies was skipped. Continue to carrier selection anyway? (yes/no)
```

---

## Step 4 — select-carriers

Execute:

```
Now executing Step 4: select-carriers.
Follow the instructions in ~/.claude/skills/broker/steps/select-carriers.md
for PROJECT_ID={project_id}.
```

Wait for the routing plan and broker confirmation. After broker confirms, capture:
- `portal_carrier_ids` — list of carrier_config_ids routed to portal submission
- `email_carrier_config_ids` — list of carrier_config_ids routed to email solicitation

---

## Step 5 — fill-portal (INTERACTIVE PAUSE)

If `portal_carrier_ids` is non-empty:

```
PIPELINE PAUSE — Step 5: fill-portal requires an interactive browser session.

Follow the instructions in ~/.claude/skills/broker/steps/fill-portal.md
for each portal carrier listed in the routing plan above.

This step cannot be automated. You must:
  1. Log in to each carrier portal in your browser
  2. Run the Playwright fill script for each carrier
  3. Manually review and submit each portal form

Return here when all portal submissions are finished.
Type 'done' when all portal submissions are complete.
```

Wait for the broker to type `done` before continuing.

If `portal_carrier_ids` is empty:

```
Step 5 skipped — no portal carriers in routing plan. All carriers will receive email solicitations.
```

---

## Deactivate Pipeline Sentinel

After the portal step (whether completed or skipped), deactivate the sentinel so that
the draft-emails step triggers normal audit hooks:

```python
import os
os.environ.pop("BROKER_PIPELINE_MODE", None)
print("Pipeline mode OFF — hooks re-enabled")
```

---

## Step 6 — draft-emails

Execute:

```
Now executing Step 6: draft-emails.
Follow the instructions in ~/.claude/skills/broker/steps/draft-emails.md
for PROJECT_ID={project_id} with CARRIER_CONFIG_IDS={email_carrier_config_ids}.
```

Wait for the draft creation report showing how many email drafts were saved.

---

## Pipeline Complete Summary

After Step 6 completes, print:

```
Process-Project Pipeline Complete
==================================
Project: {project_id}
Steps completed: 6/6 (adjust to N/6 if steps were skipped)

Results:
  - Coverages extracted:  {N}  (from parse-contract)
  - Policies matched:     {N}  (from parse-policies, or "skipped")
  - Gaps found:           {N}  (from gap-analysis)
  - Portal carriers:      {N}  (submitted via fill-portal)
  - Email drafts created: {N}  (from draft-emails)

Next step: Wait for carrier responses, then run /broker:compare-quotes
```

---

## Memory Update (Standard 1)

After pipeline completion, append to `~/.claude/skills/broker/auto-memory/broker.md`:

```
[{date}] process-project pipeline completed for project {project_id}.
Steps: {completed_count}/6. Portal submissions: {portal_count}. Email drafts: {email_count}.
```

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Step fails mid-pipeline | Report which step failed, preserve all work done so far, ask broker to fix and re-run that step standalone before re-running pipeline |
| Broker aborts at gap-analysis | Deactivate BROKER_PIPELINE_MODE sentinel before exiting |
| Portal step returns error | Keep sentinel active, report error, ask broker to resolve manually then type 'done' |
| PROJECT_ID invalid | Fail immediately with UUID format reminder before activating sentinel |
