#!/usr/bin/env python3
"""
Log a pipeline run to ~/.claude/gtm-stack/pipeline-runs.json.

Called at the end of every gtm-leads-pipeline run. Appends run metadata
and triggers merge_master.py + generate_dashboard.py if they exist.

Usage:
    python log_run.py \
        --source "MIT Alumni Directory" \
        --source-url "https://alum.mit.edu/directory" \
        --filters "Industry: Construction, Location: US" \
        --people-scraped 312 \
        --duplicates-removed 18 \
        --unique-companies 87 \
        --scored 87 \
        --strong-fit 9 \
        --moderate-fit 14 \
        --low-fit 38 \
        --no-fit 26 \
        --csv-path "~/Downloads/leads_scored_2026-03-03.csv" \
        --duration-min 185

    Or call from Python:
        from log_run import log_pipeline_run
        log_pipeline_run({...})
"""

import json
import os
import subprocess
import sys
import argparse
from datetime import datetime

GTM_DIR = os.path.expanduser("~/.claude/gtm-stack")
RUNS_PATH = os.path.join(GTM_DIR, "pipeline-runs.json")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
STACK_DIR = os.path.dirname(os.path.dirname(SCRIPTS_DIR))

# Import shared utilities
sys.path.insert(0, os.path.join(STACK_DIR, "gtm-shared"))
try:
    from gtm_utils import generate_run_id, atomic_write_json, backup_file
except ImportError:
    # Fallback inline versions
    def generate_run_id():
        return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    def atomic_write_json(fp, data, indent=2):
        import tempfile as _tf
        d = os.path.dirname(fp) or "."; os.makedirs(d, exist_ok=True)
        fd, tmp = _tf.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(data, f, indent=indent, ensure_ascii=False)
            os.replace(tmp, fp)
        except: os.remove(tmp); raise
    def backup_file(fp, max_backups=5): return None


def load_runs():
    """Load existing pipeline runs or return empty list."""
    if not os.path.exists(RUNS_PATH):
        return []
    try:
        with open(RUNS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_runs(runs):
    """Write pipeline runs to JSON atomically."""
    os.makedirs(GTM_DIR, exist_ok=True)
    atomic_write_json(RUNS_PATH, runs)


def log_pipeline_run(run_data):
    """
    Append a pipeline run to pipeline-runs.json.

    Args:
        run_data: dict with keys like source, source_url, filters,
                  people_scraped, unique_companies, scored, strong_fit,
                  moderate_fit, low_fit, no_fit, csv_path, duration_min.

    Returns:
        str: the generated run ID (e.g. "run_004")
    """
    runs = load_runs()

    run_id = generate_run_id()
    run_data["id"] = run_id
    run_data.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
    run_data.setdefault("status", "complete")

    # Normalize tier field names (support both old and new naming)
    tier_map = {
        "hot": "strong_fit", "warm": "moderate_fit",
        "cool": "low_fit", "pass": "no_fit",
    }
    for old_key, new_key in tier_map.items():
        if old_key in run_data and new_key not in run_data:
            run_data[new_key] = run_data.pop(old_key)

    runs.append(run_data)
    save_runs(runs)

    print(f"✅ Pipeline run logged: {run_id}")
    print(f"   Source: {run_data.get('source', 'Unknown')}")
    print(f"   Companies: {run_data.get('unique_companies', 0)}")
    print(f"   Strong Fit: {run_data.get('strong_fit', 0)} | "
          f"Moderate Fit: {run_data.get('moderate_fit', 0)}")

    return run_id


def trigger_post_run():
    """Run merge_master.py and generate_dashboard.py if they exist."""
    # Look in the gtm-stack directory (parent of gtm-leads-pipeline)
    stack_base = os.path.dirname(SCRIPTS_DIR)  # gtm-leads-pipeline/scripts -> gtm-leads-pipeline
    stack_base = os.path.dirname(stack_base)    # gtm-leads-pipeline -> gtm-stack

    merge_script = os.path.join(stack_base, "gtm-leads-pipeline", "scripts", "merge_master.py")
    dash_script = os.path.join(stack_base, "gtm-dashboard", "scripts", "generate_dashboard.py")

    # Also check the installed skill paths
    installed_base = os.path.expanduser("~/.claude/skills/gtm-stack")
    alt_merge = os.path.join(installed_base, "gtm-leads-pipeline", "scripts", "merge_master.py")
    alt_dash = os.path.join(installed_base, "gtm-dashboard", "scripts", "generate_dashboard.py")

    for script in [merge_script, alt_merge]:
        if os.path.exists(script):
            print(f"\n→ Running merge_master.py...")
            subprocess.run([sys.executable, script], check=False)
            break

    for script in [dash_script, alt_dash]:
        if os.path.exists(script):
            print(f"\n→ Running generate_dashboard.py...")
            subprocess.run([sys.executable, script], check=False)
            break


def main():
    parser = argparse.ArgumentParser(description="Log a GTM pipeline run")
    parser.add_argument("--source", required=True, help="Source name")
    parser.add_argument("--source-url", default="", help="Source URL")
    parser.add_argument("--filters", default="", help="Filters applied")
    parser.add_argument("--people-scraped", type=int, default=0)
    parser.add_argument("--duplicates-removed", type=int, default=0)
    parser.add_argument("--unique-companies", type=int, default=0)
    parser.add_argument("--scored", type=int, default=0)
    parser.add_argument("--strong-fit", type=int, default=0)
    parser.add_argument("--moderate-fit", type=int, default=0)
    parser.add_argument("--low-fit", type=int, default=0)
    parser.add_argument("--no-fit", type=int, default=0)
    parser.add_argument("--csv-path", default="")
    parser.add_argument("--duration-min", type=int, default=0)
    parser.add_argument("--no-post-run", action="store_true",
                        help="Skip merge and dashboard generation")
    args = parser.parse_args()

    run_data = {
        "source": args.source,
        "source_url": args.source_url,
        "filters": args.filters,
        "people_scraped": args.people_scraped,
        "duplicates_removed": args.duplicates_removed,
        "unique_companies": args.unique_companies,
        "scored": args.scored,
        "strong_fit": args.strong_fit,
        "moderate_fit": args.moderate_fit,
        "low_fit": args.low_fit,
        "no_fit": args.no_fit,
        "csv_path": args.csv_path,
        "duration_min": args.duration_min,
    }

    log_pipeline_run(run_data)

    if not args.no_post_run:
        trigger_post_run()


if __name__ == "__main__":
    main()
