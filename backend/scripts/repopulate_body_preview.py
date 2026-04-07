"""Repopulate truncated body_preview in activities from source CSV.

The initial load script truncated email_body to 500 chars. This script
reads the full body from the CSV and updates each activity's body_preview
by matching on contact email.

Source: ~/claude-outputs/research/broker-contacts-enriched-ALL.csv
Target tenant: lumif.ai (559dfb86-106f-4b1e-aeef-dce3df6ffbba)
"""

import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from flywheel.db.session import get_session_factory

TENANT_ID = "559dfb86-106f-4b1e-aeef-dce3df6ffbba"
CSV_PATH = Path.home() / "claude-outputs/research/broker-contacts-enriched-ALL.csv"


def load_csv() -> dict[str, str]:
    """Build email -> full email_body mapping from CSV."""
    mapping: dict[str, str] = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            email = (row.get("email") or "").strip().lower()
            body = (row.get("email_body") or "").strip()
            if email and body:
                mapping[email] = body
    return mapping


async def run():
    email_to_body = load_csv()
    print(f"Loaded {len(email_to_body)} email->body mappings from CSV")

    factory = get_session_factory()
    updated = 0
    skipped = 0

    async with factory() as db:
        # Fetch all draft outreach activities with their contact emails
        result = await db.execute(
            text("""
                SELECT a.id, c.email, a.body_preview
                FROM activities a
                JOIN contacts c ON c.id = a.contact_id
                WHERE a.tenant_id = :tid
                  AND a.status = 'drafted'
                  AND a.direction = 'outbound'
                  AND c.email IS NOT NULL
            """),
            {"tid": TENANT_ID},
        )
        rows = result.fetchall()
        print(f"Found {len(rows)} drafted outbound activities to check")

        for row in rows:
            activity_id = row[0]
            contact_email = (row[1] or "").strip().lower()
            current_body = row[2] or ""

            full_body = email_to_body.get(contact_email)
            if not full_body:
                skipped += 1
                continue

            # Only update if the current body is shorter (was truncated)
            if len(current_body) < len(full_body):
                await db.execute(
                    text("UPDATE activities SET body_preview = :body WHERE id = :id"),
                    {"body": full_body, "id": str(activity_id)},
                )
                updated += 1
            else:
                skipped += 1

        await db.commit()

    print()
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped} (no match or already full)")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run())
