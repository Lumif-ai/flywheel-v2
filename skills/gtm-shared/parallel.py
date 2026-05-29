"""
Parallel execution utilities for the GTM Stack.

Provides batching helpers and parallel browser tab management for skills
that need to process multiple items concurrently via Playwright MCP.

IMPORTANT: These are STRATEGY HELPERS, not direct executors. Claude Code
orchestrates the actual parallelism by opening multiple browser tabs and
interleaving operations. This module provides the batching logic, result
collection, and progress tracking.

Parallelization modes (from fastest to safest):
  1. MULTI-TAB    — Open N browser tabs, rotate through them (best for crawling)
  2. BATCH-THEN-PROCESS — Collect data in bulk, then process sequentially (best for scoring)
  3. PIPELINE     — Overlap phases: crawl company N+1 while scoring company N
  4. SEQUENTIAL   — One at a time (required for sending, rate-limited operations)

Usage in SKILL.md instructions:
  "Use the parallel batch strategy from shared/parallel.py with batch_size=3"
"""

import os
import json
import math
from datetime import datetime


# ═══════════════════════════════════════════
# BATCH PLANNING
# ═══════════════════════════════════════════

def plan_parallel_batches(items, batch_size=None, task_type="default", max_batches=None):
    """
    Split a list of items into parallel batches.

    Args:
        items: list of things to process (companies, URLs, search terms, etc.)
        batch_size: explicit override, or None to auto-calculate from task_type
        task_type: one of "quick_filter", "website_discovery", "deep_crawl",
                   "dm_lookup", "email_send", "multi_term_scrape", "default"
        max_batches: cap on total batches (None = no cap)

    Returns:
        list of lists, each inner list is one parallel batch

    Example:
        >>> plan_parallel_batches(companies, task_type="quick_filter")
        [["A","B","C","D"], ["E","F","G","H"], ...]
    """
    if batch_size is None:
        batch_size = calculate_batch_size(len(items), task_type)

    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i + batch_size])
        if max_batches and len(batches) >= max_batches:
            break
    return batches


def calculate_batch_size(item_count, task_type="default"):
    """
    Calculate optimal batch size based on item count and task type.

    Each task type has different constraints:
      - quick_filter: I/O-light (homepage only), can use more tabs
      - website_discovery: search-heavy, moderate tabs
      - deep_crawl: text-heavy, fewer tabs to avoid context overflow
      - dm_lookup: LinkedIn rate-limited, max 2 tabs
      - email_send: moderate, scales with count
      - multi_term_scrape: one tab per term, cap at 3
      - default: conservative 3-tab default

    Returns:
        int: recommended batch_size (number of concurrent tabs)
    """
    rules = {
        "quick_filter": [
            (10, 1), (30, 3), (60, 4), (float('inf'), 5)
        ],
        "website_discovery": [
            (8, 1), (25, 3), (60, 4), (float('inf'), 5)
        ],
        "deep_crawl": [
            (5, 1), (20, 2), (float('inf'), 3)
        ],
        "dm_lookup": [
            (5, 1), (float('inf'), 2)  # Never exceed 2 for LinkedIn
        ],
        "email_send": [
            (5, 1), (15, 2), (50, 3), (float('inf'), 4)
        ],
        "multi_term_scrape": [
            (1, 1), (3, 3), (float('inf'), 3)  # Cap at 3 for scraping
        ],
        "default": [
            (5, 1), (20, 2), (float('inf'), 3)
        ],
    }

    thresholds = rules.get(task_type, rules["default"])
    for max_count, size in thresholds:
        if item_count <= max_count:
            return size
    return 3  # Fallback


def estimate_parallel_time(total_items, time_per_item_sec, batch_size=3):
    """
    Estimate wall-clock time for parallel processing.

    Returns:
        dict with total_sequential_min, total_parallel_min, speedup, num_batches
    """
    num_batches = math.ceil(total_items / batch_size)
    sequential_sec = total_items * time_per_item_sec
    parallel_sec = num_batches * time_per_item_sec  # each batch takes ~1 item's time
    # Add 20% overhead for tab switching
    parallel_sec *= 1.2

    return {
        "total_items": total_items,
        "batch_size": batch_size,
        "num_batches": num_batches,
        "sequential_min": round(sequential_sec / 60, 1),
        "parallel_min": round(parallel_sec / 60, 1),
        "speedup": round(sequential_sec / parallel_sec, 1) if parallel_sec > 0 else 1,
    }


# ═══════════════════════════════════════════
# PARALLEL PROGRESS TRACKER
# ═══════════════════════════════════════════

class ParallelProgressTracker:
    """
    Track progress across parallel batches. Provides formatted status updates.

    Usage:
        tracker = ParallelProgressTracker(total=45, batch_size=3, label="companies")
        tracker.complete("Meridian Construction", result={"score": 92, "tier": "Strong Fit"})
        tracker.complete("Atlas Group", result={"score": 87, "tier": "Strong Fit"})
        tracker.fail("Unknown Corp", reason="No website found")
        print(tracker.status())
    """

    def __init__(self, total, batch_size=3, label="items"):
        self.total = total
        self.batch_size = batch_size
        self.label = label
        self.completed = []
        self.failed = []
        self.start_time = datetime.now()

    def complete(self, item_name, result=None):
        self.completed.append({"name": item_name, "result": result})

    def fail(self, item_name, reason=""):
        self.failed.append({"name": item_name, "reason": reason})

    @property
    def done_count(self):
        return len(self.completed) + len(self.failed)

    @property
    def remaining(self):
        return self.total - self.done_count

    def elapsed_min(self):
        return round((datetime.now() - self.start_time).total_seconds() / 60, 1)

    def eta_min(self):
        if self.done_count == 0:
            return "?"
        rate = self.elapsed_min() / self.done_count
        return round(rate * self.remaining, 1)

    def status(self):
        """Return a formatted progress string."""
        pct = round(self.done_count / self.total * 100) if self.total > 0 else 0
        return (
            f"Progress: {self.done_count}/{self.total} {self.label} "
            f"({pct}%) — {len(self.completed)} done, {len(self.failed)} failed "
            f"— ~{self.eta_min()} min remaining"
        )

    def batch_status(self, batch_num, batch_total):
        """Return a formatted batch progress string."""
        return (
            f"Batch {batch_num}/{batch_total} "
            f"({self.done_count}/{self.total} {self.label} complete, "
            f"~{self.eta_min()} min remaining)"
        )


# ═══════════════════════════════════════════
# BROWSER TAB MANAGEMENT STRATEGY
# ═══════════════════════════════════════════

def generate_tab_rotation_plan(items, num_tabs=3):
    """
    Generate a tab rotation plan for Playwright MCP multi-tab crawling.

    The strategy:
      1. Open `num_tabs` browser tabs
      2. Navigate tab 1 to company A, tab 2 to company B, tab 3 to company C
      3. While tabs are loading, extract from the tab that loaded first
      4. After extracting from a tab, navigate it to the next company
      5. Repeat until all companies are processed

    This keeps all tabs busy — while one is loading, others are being extracted.

    Returns:
        dict with tab_assignments and instructions for Claude Code

    Example output:
        {
            "num_tabs": 3,
            "rounds": [
                {"tab_1": "Company A", "tab_2": "Company B", "tab_3": "Company C"},
                {"tab_1": "Company D", "tab_2": "Company E", "tab_3": "Company F"},
            ],
            "total_rounds": 5,
            "instructions": "..."
        }
    """
    rounds = []
    for i in range(0, len(items), num_tabs):
        batch = items[i:i + num_tabs]
        round_assignment = {}
        for j, item in enumerate(batch):
            round_assignment[f"tab_{j + 1}"] = item
        rounds.append(round_assignment)

    instructions = f"""
PARALLEL TAB ROTATION — {num_tabs} tabs, {len(items)} items, {len(rounds)} rounds

Setup:
  1. Open {num_tabs} browser tabs using tabs_create_mcp (or equivalent)
  2. Keep track of which tab is processing which item

Per round:
  1. Navigate ALL {num_tabs} tabs to their assigned URLs simultaneously
     (don't wait for one to finish before starting the next)
  2. Wait for content to stabilize on each tab (use the stability-check pattern)
  3. Extract from whichever tab is ready first
  4. After extraction, immediately navigate that tab to its next-round assignment
  5. Continue until all tabs in the round are extracted

Key principle: A tab should NEVER be idle while waiting for another tab.
    """.strip()

    return {
        "num_tabs": num_tabs,
        "rounds": rounds,
        "total_rounds": len(rounds),
        "total_items": len(items),
        "instructions": instructions,
    }


# ═══════════════════════════════════════════
# PHASE PIPELINING
# ═══════════════════════════════════════════

def generate_pipeline_plan(items, phases):
    """
    Generate a pipelined execution plan where phases overlap.

    Example: While deep-crawling Company B, score Company A (already crawled).

    Args:
        items: list of item names
        phases: list of phase dicts with name and est_seconds

    Returns:
        Execution plan showing overlapped phases
    """
    plan = {
        "phases": [p["name"] for p in phases],
        "items": items,
        "strategy": "pipeline",
        "description": (
            "Pipeline strategy: start phase N+1 for item K while "
            "phase N runs for item K+1. This overlaps I/O-bound phases "
            "(crawling, searching) with CPU-bound phases (scoring, drafting)."
        ),
        "execution_order": [],
    }

    # Generate interleaved execution order
    for i, item in enumerate(items):
        for phase in phases:
            plan["execution_order"].append({
                "item": item,
                "phase": phase["name"],
                "can_overlap_with": (
                    f"{items[i+1]}/{phases[0]['name']}"
                    if i + 1 < len(items) else "nothing"
                ),
            })

    return plan
