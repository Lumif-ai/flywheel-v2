#!/usr/bin/env python3
"""Content Backlog Manager for Social Media Manager.

Manages the idea backlog: capture, enrich, prioritize, promote to calendar.

Usage:
    python3 backlog_manager.py add --idea "Thoughts on compliance automation" [--lens CEO] [--tier evergreen] [--tags "compliance,product"]
    python3 backlog_manager.py list [--tier now|this_week|evergreen] [--limit 10]
    python3 backlog_manager.py promote --id IDEA-001 --date 2026-03-15 --platform linkedin
    python3 backlog_manager.py remove --id IDEA-001
    python3 backlog_manager.py --smoke-test
"""

import argparse
import csv
import os
import sys
from datetime import datetime


DATA_DIR = os.path.expanduser("~/.claude/skills/social-media-manager/data")
BACKLOG_PATH = os.path.join(DATA_DIR, "backlog.csv")

FIELDS = [
    "id", "idea", "lens", "category", "tier", "tags", "source",
    "raw_notes", "status", "promoted_to", "created_at", "updated_at"
]

VALID_TIERS = ["now", "this_week", "evergreen"]
VALID_STATUSES = ["new", "enriched", "promoted", "killed"]


def ensure_backlog():
    """Ensure backlog CSV exists with headers."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BACKLOG_PATH):
        with open(BACKLOG_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def read_backlog():
    """Read all backlog entries."""
    ensure_backlog()
    with open(BACKLOG_PATH, "r", newline="") as f:
        return list(csv.DictReader(f))


def write_backlog(entries):
    """Write all entries back to backlog."""
    ensure_backlog()
    with open(BACKLOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(entries)


def next_id(entries):
    """Generate next sequential ID."""
    if not entries:
        return "IDEA-001"
    max_num = 0
    for e in entries:
        try:
            num = int(e["id"].split("-")[1])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            pass
    return f"IDEA-{max_num + 1:03d}"


def add_idea(args):
    """Add a new idea to the backlog."""
    entries = read_backlog()

    # Dedup check — same idea text within 7 days
    for e in entries:
        if e["idea"].lower().strip() == args.idea.lower().strip() and e["status"] != "killed":
            print(f"Duplicate found: {e['id']} — \"{e['idea']}\" (status: {e['status']})")
            return None

    now = datetime.now().isoformat()
    entry = {
        "id": next_id(entries),
        "idea": args.idea,
        "lens": getattr(args, "lens", ""),
        "category": getattr(args, "category", ""),
        "tier": getattr(args, "tier", "evergreen"),
        "tags": getattr(args, "tags", ""),
        "source": getattr(args, "source", "manual"),
        "raw_notes": getattr(args, "raw_notes", ""),
        "status": "new",
        "promoted_to": "",
        "created_at": now,
        "updated_at": now,
    }
    entries.append(entry)
    write_backlog(entries)
    print(f"Added: {entry['id']} — \"{entry['idea']}\" (tier: {entry['tier']})")
    return entry


def list_ideas(args):
    """List backlog ideas, optionally filtered."""
    entries = read_backlog()

    # Filter out killed/promoted by default
    active = [e for e in entries if e["status"] in ("new", "enriched")]

    if getattr(args, "tier", None):
        active = [e for e in active if e["tier"] == args.tier]

    if getattr(args, "all", False):
        active = entries

    # Sort: now > this_week > evergreen, then by date
    tier_order = {"now": 0, "this_week": 1, "evergreen": 2}
    active.sort(key=lambda e: (tier_order.get(e["tier"], 3), e["created_at"]))

    limit = getattr(args, "limit", None)
    if limit:
        active = active[:int(limit)]

    if not active:
        print("Backlog is empty. Add ideas with: backlog_manager.py add --idea 'your idea'")
        return

    print(f"{'ID':<10} {'Tier':<12} {'Lens':<8} {'Status':<10} {'Idea'}")
    print("-" * 80)
    for e in active:
        idea = e["idea"][:45] + "..." if len(e["idea"]) > 45 else e["idea"]
        tags = f" [{e['tags']}]" if e.get("tags") else ""
        print(f"{e['id']:<10} {e['tier']:<12} {e.get('lens', ''):<8} {e['status']:<10} {idea}{tags}")

    print(f"\nTotal: {len(active)} ideas")

    # Summary by tier
    now_count = sum(1 for e in active if e["tier"] == "now")
    week_count = sum(1 for e in active if e["tier"] == "this_week")
    ever_count = sum(1 for e in active if e["tier"] == "evergreen")
    if now_count:
        print(f"  NOW (urgent): {now_count}")
    if week_count:
        print(f"  THIS WEEK: {week_count}")
    if ever_count:
        print(f"  EVERGREEN: {ever_count}")


def promote_idea(args):
    """Promote an idea to the content calendar."""
    entries = read_backlog()
    found = False
    for e in entries:
        if e["id"] == args.id:
            e["status"] = "promoted"
            e["promoted_to"] = f"{args.date}:{args.platform}"
            e["updated_at"] = datetime.now().isoformat()
            found = True
            print(f"Promoted {e['id']} → calendar: {args.date} on {args.platform}")
            print(f"  Now run: calendar_manager.py add --date {args.date} --platform {args.platform} --title \"{e['idea']}\"")
            break

    if not found:
        print(f"ERROR: Idea '{args.id}' not found")
        sys.exit(1)

    write_backlog(entries)


def remove_idea(args):
    """Kill/remove an idea from the backlog."""
    entries = read_backlog()
    found = False
    for e in entries:
        if e["id"] == args.id:
            e["status"] = "killed"
            e["updated_at"] = datetime.now().isoformat()
            found = True
            print(f"Killed {e['id']} — \"{e['idea']}\"")
            break

    if not found:
        print(f"ERROR: Idea '{args.id}' not found")
        sys.exit(1)

    write_backlog(entries)


def smoke_test():
    """Run smoke test."""
    import tempfile
    global BACKLOG_PATH, DATA_DIR

    old_path = BACKLOG_PATH
    old_dir = DATA_DIR
    DATA_DIR = tempfile.mkdtemp()
    BACKLOG_PATH = os.path.join(DATA_DIR, "backlog.csv")

    try:
        class Args:
            pass

        # Add ideas
        a = Args()
        a.idea = "Thoughts on compliance automation trends"
        a.lens = "CEO"
        a.category = "industry"
        a.tier = "evergreen"
        a.tags = "compliance,trends"
        a.source = "manual"
        a.raw_notes = ""
        entry = add_idea(a)
        assert entry["id"] == "IDEA-001"

        a.idea = "Breaking: new OSHA regulation impact"
        a.tier = "now"
        a.lens = "CEO+CPO"
        entry2 = add_idea(a)
        assert entry2["id"] == "IDEA-002"

        # Dedup test
        a.idea = "Thoughts on compliance automation trends"
        a.tier = "evergreen"
        dup = add_idea(a)
        assert dup is None  # Should be caught as duplicate

        # List
        a2 = Args()
        a2.tier = None
        a2.limit = None
        a2.all = False
        list_ideas(a2)

        # Promote
        a3 = Args()
        a3.id = "IDEA-001"
        a3.date = "2026-03-15"
        a3.platform = "linkedin"
        promote_idea(a3)

        # Remove
        a4 = Args()
        a4.id = "IDEA-002"
        remove_idea(a4)

        print("\nSMOKE TEST PASSED")
        return True

    finally:
        BACKLOG_PATH = old_path
        DATA_DIR = old_dir


def main():
    parser = argparse.ArgumentParser(description="Content Backlog Manager")
    parser.add_argument("--smoke-test", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # Add
    add_p = sub.add_parser("add")
    add_p.add_argument("--idea", required=True)
    add_p.add_argument("--lens", default="")
    add_p.add_argument("--category", default="")
    add_p.add_argument("--tier", default="evergreen", choices=VALID_TIERS)
    add_p.add_argument("--tags", default="")
    add_p.add_argument("--source", default="manual")
    add_p.add_argument("--raw-notes", default="")

    # List
    list_p = sub.add_parser("list")
    list_p.add_argument("--tier", choices=VALID_TIERS)
    list_p.add_argument("--limit", type=int)
    list_p.add_argument("--all", action="store_true")

    # Promote
    prom_p = sub.add_parser("promote")
    prom_p.add_argument("--id", required=True)
    prom_p.add_argument("--date", required=True)
    prom_p.add_argument("--platform", required=True)

    # Remove
    rem_p = sub.add_parser("remove")
    rem_p.add_argument("--id", required=True)

    args = parser.parse_args()

    if args.smoke_test:
        success = smoke_test()
        sys.exit(0 if success else 1)

    if args.command == "add":
        add_idea(args)
    elif args.command == "list":
        list_ideas(args)
    elif args.command == "promote":
        promote_idea(args)
    elif args.command == "remove":
        remove_idea(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
