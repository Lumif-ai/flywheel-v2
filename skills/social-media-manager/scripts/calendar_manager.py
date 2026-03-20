#!/usr/bin/env python3
"""Content Calendar Manager for Social Media Manager.

Manages the content calendar: add, list, update, reschedule posts.
Calendar is stored as CSV for simplicity and portability.

Usage:
    python3 calendar_manager.py add --date 2026-03-15 --platform linkedin --title "Post title" [--lens CEO] [--tier evergreen] [--series "Series Name" --episode 1]
    python3 calendar_manager.py list [--week|--month] [--platform linkedin]
    python3 calendar_manager.py update --id POST-001 --status approved
    python3 calendar_manager.py reschedule --id POST-001 --new-date 2026-03-17
    python3 calendar_manager.py stats
    python3 calendar_manager.py --smoke-test
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta


DATA_DIR = os.path.expanduser("~/.claude/skills/social-media-manager/data")
CALENDAR_PATH = os.path.join(DATA_DIR, "calendar.csv")

FIELDS = [
    "id", "date", "platform", "title", "lens", "category", "tier",
    "series", "episode", "status", "draft_path", "intent",
    "created_at", "updated_at"
]

VALID_STATUSES = ["idea", "drafting", "draft_ready", "approved", "scheduled", "published", "killed"]
VALID_PLATFORMS = ["linkedin", "x", "both"]
VALID_TIERS = ["now", "this_week", "evergreen"]
VALID_INTENTS = ["brand", "lead_gen", "hiring", "investor_signal", "engagement", "thought_leadership"]
VALID_CATEGORIES = ["technical", "product", "leadership", "industry", "personal", "engagement"]


def ensure_calendar():
    """Ensure calendar CSV exists with headers."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CALENDAR_PATH):
        with open(CALENDAR_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def read_calendar():
    """Read all calendar entries."""
    ensure_calendar()
    with open(CALENDAR_PATH, "r", newline="") as f:
        return list(csv.DictReader(f))


def write_calendar(entries):
    """Write all entries back to calendar."""
    ensure_calendar()
    with open(CALENDAR_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(entries)


def next_id(entries):
    """Generate next sequential ID."""
    if not entries:
        return "POST-001"
    max_num = 0
    for e in entries:
        try:
            num = int(e["id"].split("-")[1])
            if num > max_num:
                max_num = num
        except (IndexError, ValueError):
            pass
    return f"POST-{max_num + 1:03d}"


def add_entry(args):
    """Add a new calendar entry."""
    entries = read_calendar()
    now = datetime.now().isoformat()
    entry = {
        "id": next_id(entries),
        "date": args.date,
        "platform": args.platform,
        "title": args.title,
        "lens": getattr(args, "lens", ""),
        "category": getattr(args, "category", ""),
        "tier": getattr(args, "tier", "evergreen"),
        "series": getattr(args, "series", ""),
        "episode": getattr(args, "episode", ""),
        "status": "idea",
        "draft_path": "",
        "intent": getattr(args, "intent", ""),
        "created_at": now,
        "updated_at": now,
    }
    entries.append(entry)
    write_calendar(entries)
    print(f"Added: {entry['id']} — \"{entry['title']}\" on {entry['date']} ({entry['platform']})")
    return entry


def list_entries(args):
    """List calendar entries, optionally filtered."""
    entries = read_calendar()
    today = datetime.now().date()

    if getattr(args, "week", False):
        week_end = today + timedelta(days=7)
        entries = [e for e in entries if today <= datetime.strptime(e["date"], "%Y-%m-%d").date() <= week_end]
    elif getattr(args, "month", False):
        entries = [e for e in entries if datetime.strptime(e["date"], "%Y-%m-%d").date().month == today.month]

    if getattr(args, "platform", None):
        entries = [e for e in entries if e["platform"] == args.platform or e["platform"] == "both"]

    if getattr(args, "status", None):
        entries = [e for e in entries if e["status"] == args.status]

    # Sort by date
    entries.sort(key=lambda e: e["date"])

    if not entries:
        print("No entries found matching filters.")
        return

    # Display
    print(f"{'ID':<10} {'Date':<12} {'Platform':<10} {'Status':<12} {'Lens':<8} {'Title'}")
    print("-" * 80)
    for e in entries:
        title = e["title"][:40] + "..." if len(e["title"]) > 40 else e["title"]
        series_tag = f" [{e['series']} #{e['episode']}]" if e.get("series") else ""
        print(f"{e['id']:<10} {e['date']:<12} {e['platform']:<10} {e['status']:<12} {e.get('lens', ''):<8} {title}{series_tag}")

    print(f"\nTotal: {len(entries)} entries")


def update_entry(args):
    """Update an entry's status."""
    entries = read_calendar()
    found = False
    for e in entries:
        if e["id"] == args.id:
            if args.status and args.status not in VALID_STATUSES:
                print(f"ERROR: Invalid status '{args.status}'. Valid: {VALID_STATUSES}")
                sys.exit(1)
            if args.status:
                e["status"] = args.status
            e["updated_at"] = datetime.now().isoformat()
            found = True
            print(f"Updated {e['id']}: status → {e['status']}")
            break

    if not found:
        print(f"ERROR: Entry '{args.id}' not found")
        sys.exit(1)

    write_calendar(entries)


def reschedule_entry(args):
    """Reschedule an entry to a new date."""
    entries = read_calendar()
    found = False
    for e in entries:
        if e["id"] == args.id:
            old_date = e["date"]
            e["date"] = args.new_date
            e["updated_at"] = datetime.now().isoformat()
            found = True
            print(f"Rescheduled {e['id']}: {old_date} → {e['date']}")
            break

    if not found:
        print(f"ERROR: Entry '{args.id}' not found")
        sys.exit(1)

    write_calendar(entries)


def show_stats(args=None):
    """Show calendar statistics."""
    entries = read_calendar()
    if not entries:
        print("Calendar is empty.")
        return

    today = datetime.now().date()

    # Status breakdown
    status_counts = {}
    for e in entries:
        status_counts[e["status"]] = status_counts.get(e["status"], 0) + 1

    # Platform breakdown
    platform_counts = {}
    for e in entries:
        platform_counts[e["platform"]] = platform_counts.get(e["platform"], 0) + 1

    # Category breakdown (last 30 days published)
    recent_published = [e for e in entries
                        if e["status"] == "published"
                        and (today - datetime.strptime(e["date"], "%Y-%m-%d").date()).days <= 30]
    category_counts = {}
    for e in recent_published:
        cat = e.get("category", "uncategorized")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Lens breakdown
    lens_counts = {}
    for e in recent_published:
        lens = e.get("lens", "untagged")
        lens_counts[lens] = lens_counts.get(lens, 0) + 1

    # Upcoming
    upcoming = [e for e in entries
                if e["status"] in ("draft_ready", "approved", "scheduled")
                and datetime.strptime(e["date"], "%Y-%m-%d").date() >= today]
    upcoming.sort(key=lambda e: e["date"])

    # Overdue
    overdue = [e for e in entries
               if e["status"] in ("idea", "drafting", "draft_ready")
               and datetime.strptime(e["date"], "%Y-%m-%d").date() < today]

    print("CONTENT CALENDAR STATS")
    print("=" * 40)
    print(f"\nTotal entries: {len(entries)}")
    print(f"\nBy status:")
    for s, c in sorted(status_counts.items()):
        print(f"  {s:<15} {c}")

    print(f"\nBy platform:")
    for p, c in sorted(platform_counts.items()):
        print(f"  {p:<15} {c}")

    if category_counts:
        print(f"\nCategory mix (last 30 days, {len(recent_published)} published):")
        total = sum(category_counts.values())
        for cat, c in sorted(category_counts.items(), key=lambda x: -x[1]):
            pct = (c / total) * 100 if total > 0 else 0
            print(f"  {cat:<15} {c} ({pct:.0f}%)")

    if lens_counts:
        print(f"\nLens mix (last 30 days):")
        total = sum(lens_counts.values())
        for lens, c in sorted(lens_counts.items(), key=lambda x: -x[1]):
            pct = (c / total) * 100 if total > 0 else 0
            print(f"  {lens:<15} {c} ({pct:.0f}%)")

    if upcoming:
        print(f"\nUpcoming ({len(upcoming)}):")
        for e in upcoming[:5]:
            print(f"  {e['date']} — {e['platform']:<10} {e['title'][:50]}")

    if overdue:
        print(f"\nOverdue ({len(overdue)}):")
        for e in overdue[:5]:
            print(f"  {e['date']} — {e['platform']:<10} {e['title'][:50]}")
        if len(overdue) > 5:
            print(f"  ... and {len(overdue) - 5} more")


def smoke_test():
    """Run smoke test."""
    import tempfile
    global CALENDAR_PATH, DATA_DIR

    # Use temp directory
    old_path = CALENDAR_PATH
    old_dir = DATA_DIR
    DATA_DIR = tempfile.mkdtemp()
    CALENDAR_PATH = os.path.join(DATA_DIR, "calendar.csv")

    try:
        # Add entries
        class Args:
            pass
        a = Args()
        a.date = "2026-03-15"
        a.platform = "linkedin"
        a.title = "Test post about compliance"
        a.lens = "CEO"
        a.category = "product"
        a.tier = "evergreen"
        a.series = ""
        a.episode = ""
        a.intent = "brand"
        entry = add_entry(a)
        assert entry["id"] == "POST-001"

        a.date = "2026-03-16"
        a.platform = "x"
        a.title = "Quick thread on tech decisions"
        a.lens = "CTO"
        entry2 = add_entry(a)
        assert entry2["id"] == "POST-002"

        # List
        a2 = Args()
        a2.week = False
        a2.month = False
        a2.platform = None
        a2.status = None
        list_entries(a2)

        # Update
        a3 = Args()
        a3.id = "POST-001"
        a3.status = "approved"
        update_entry(a3)

        # Stats
        show_stats()

        print("\nSMOKE TEST PASSED")
        return True

    finally:
        CALENDAR_PATH = old_path
        DATA_DIR = old_dir


def main():
    parser = argparse.ArgumentParser(description="Content Calendar Manager")
    parser.add_argument("--smoke-test", action="store_true")
    sub = parser.add_subparsers(dest="command")

    # Add
    add_p = sub.add_parser("add")
    add_p.add_argument("--date", required=True)
    add_p.add_argument("--platform", required=True, choices=VALID_PLATFORMS)
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--lens", default="")
    add_p.add_argument("--category", default="", choices=[""] + VALID_CATEGORIES)
    add_p.add_argument("--tier", default="evergreen", choices=VALID_TIERS)
    add_p.add_argument("--series", default="")
    add_p.add_argument("--episode", default="")
    add_p.add_argument("--intent", default="", choices=[""] + VALID_INTENTS)

    # List
    list_p = sub.add_parser("list")
    list_p.add_argument("--week", action="store_true")
    list_p.add_argument("--month", action="store_true")
    list_p.add_argument("--platform", choices=VALID_PLATFORMS)
    list_p.add_argument("--status", choices=VALID_STATUSES)

    # Update
    update_p = sub.add_parser("update")
    update_p.add_argument("--id", required=True)
    update_p.add_argument("--status", choices=VALID_STATUSES)

    # Reschedule
    resched_p = sub.add_parser("reschedule")
    resched_p.add_argument("--id", required=True)
    resched_p.add_argument("--new-date", required=True)

    # Stats
    sub.add_parser("stats")

    args = parser.parse_args()

    if args.smoke_test:
        success = smoke_test()
        sys.exit(0 if success else 1)

    if args.command == "add":
        add_entry(args)
    elif args.command == "list":
        list_entries(args)
    elif args.command == "update":
        update_entry(args)
    elif args.command == "reschedule":
        reschedule_entry(args)
    elif args.command == "stats":
        show_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
