---
public: true
name: broker-gap-analysis
version: "1.1"
web_tier: 3
description: Call the analyze-gaps endpoint and print a coverage gap summary table
context-aware: true
triggers:
  - /broker:gap-analysis
tags:
  - broker
  - insurance
  - gap-analysis
  - coverage
assets: []
depends_on: ["broker"]
dependencies:
  files:
    - "~/.claude/skills/broker/api_client.py"
    - "~/.claude/skills/broker/field_validator.py"
---

# /broker:gap-analysis — Analyze Coverage Gaps for a Project

Call the backend analyze-gaps endpoint and print a detailed gap summary showing
which coverages are missing, insufficient, adequate, or excessive.

## Step 1: Dependency Check

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator
import httpx

missing = []
if not os.environ.get("FLYWHEEL_API_URL"):
    missing.append("FLYWHEEL_API_URL")
if not os.environ.get("FLYWHEEL_API_TOKEN"):
    missing.append("FLYWHEEL_API_TOKEN")
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}\n"
                       "Run: export FLYWHEEL_API_URL=https://... && export FLYWHEEL_API_TOKEN=<jwt>")

print("OK: All dependencies satisfied.")
```

If anything fails, stop and report the missing dependency. Do not proceed.

## Step 2: Collect Input

Ask the user for:
- **PROJECT_ID** — UUID of the broker project

Validate using field_validator:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client
import field_validator

PROJECT_ID = "<user-provided-project-id>"
PROJECT_ID = field_validator.validate_uuid(PROJECT_ID, "PROJECT_ID")
print(f"Validated: project_id={PROJECT_ID}")
```

## Step 3: Call analyze-gaps Endpoint

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

print(f"Running gap analysis for project {PROJECT_ID}...")
result = api_client.run(api_client.post(f"projects/{PROJECT_ID}/analyze-gaps"))
gaps = result.get("gaps", result.get("coverages", []))
print(f"Received {len(gaps)} coverage record(s) from gap analysis.")
```

## Step 4: Print Gap Summary Table

Print each coverage's gap status with color-coded text labels:

- **MISSING** — no current coverage at all (current_limit is None or 0)
- **INSUFFICIENT** — has coverage but current_limit < required_limit
- **ADEQUATE** — current_limit meets required_limit
- **EXCESS** — current_limit exceeds required_limit

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/broker/"))
import api_client

PROJECT_ID = "<validated-project-id>"

result = api_client.run(api_client.post(f"projects/{PROJECT_ID}/analyze-gaps"))
gaps = result.get("gaps", result.get("coverages", []))

status_counts = {"MISSING": 0, "INSUFFICIENT": 0, "ADEQUATE": 0, "EXCESS": 0}

print(f"\nCoverage Gap Analysis — Project {PROJECT_ID}\n")
print(f"{'Coverage Type':<35} {'Status':<14} {'Required Limit':>16} {'Current Limit':>14} {'Gap Amount':>14}")
print("-" * 100)

for g in gaps:
    coverage_type = g.get("coverage_type", "Unknown")
    required = g.get("required_limit") or 0
    current = g.get("current_limit") or 0
    gap_status = g.get("gap_status", "").upper()

    # Derive status if not provided by backend
    if not gap_status:
        if current == 0 or current is None:
            gap_status = "MISSING"
        elif current < required:
            gap_status = "INSUFFICIENT"
        elif current >= required:
            gap_status = "ADEQUATE"
            if current > required * 1.1:
                gap_status = "EXCESS"

    gap_amount = required - current if gap_status in ("MISSING", "INSUFFICIENT") else 0
    status_counts[gap_status] = status_counts.get(gap_status, 0) + 1

    # Format gap amount
    gap_str = f"{gap_amount:,.0f}" if gap_amount > 0 else "-"
    required_str = f"{required:,.0f}" if required else "N/A"
    current_str = f"{current:,.0f}" if current else "None"

    print(
        f"{coverage_type:<35} "
        f"{gap_status:<14} "
        f"{required_str:>16} "
        f"{current_str:>14} "
        f"{gap_str:>14}"
    )

print("\nSummary:")
for status, count in status_counts.items():
    if count > 0:
        print(f"  {status}: {count}")

total_gaps = status_counts.get("MISSING", 0) + status_counts.get("INSUFFICIENT", 0)
if total_gaps == 0:
    print("\nAll coverages are adequate or better.")
else:
    print(f"\n{total_gaps} coverage(s) need attention (MISSING or INSUFFICIENT).")
    print("Run /broker:parse-policies to load current policy data if not already done.")
```

## Step 5: Memory Update

After analysis, update `~/.claude/skills/broker/auto-memory/broker.md`:

```
## Gap Analysis History
- Project {PROJECT_ID}: gap analysis run on {today's date}
  - MISSING: {count}
  - INSUFFICIENT: {count}
  - ADEQUATE: {count}
  - EXCESS: {count}
```

Done. The gap analysis is complete. To resolve gaps, use `/broker:fill-portal` to
submit quotes to carrier portals.
