"""Load US commercial insurance brokerage leads from CSV into pipeline.

Source: ~/claude-outputs/research/broker-contacts-enriched-ALL.csv
Target tenant: lumif.ai (559dfb86-106f-4b1e-aeef-dce3df6ffbba)
Owner: sharan@lumif.ai (6dab0bee-5027-4d1c-83fa-bfbaa92cf239)

Creates:
- pipeline_entries (1 per org, entity_type=company)
- contacts (1 per CSV row, is_primary=false)
- activities (1 draft outreach email per contact)
- pipeline_entry_sources (1 per org, source_type=gtm_scrape)
"""

import asyncio
import csv
import sys
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# Constants
TENANT_ID = "559dfb86-106f-4b1e-aeef-dce3df6ffbba"
OWNER_ID = "6dab0bee-5027-4d1c-83fa-bfbaa92cf239"
CSV_PATH = Path.home() / "claude-outputs/research/broker-contacts-enriched-ALL.csv"


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse spaces."""
    return " ".join(name.lower().strip().split())


def load_csv() -> dict:
    """Load CSV and group contacts by organization."""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    orgs: dict = defaultdict(lambda: {"contacts": [], "lanes": set(), "domain": None})
    for row in rows:
        org_name = row["organization"].strip()
        orgs[org_name]["contacts"].append(row)
        orgs[org_name]["lanes"].add(row.get("lane", ""))
        # Take first non-empty domain
        if row.get("domain") and not orgs[org_name]["domain"]:
            orgs[org_name]["domain"] = row["domain"].strip()

    return orgs


async def run():
    orgs = load_csv()
    factory = get_session_factory()

    total_entries = 0
    total_contacts = 0
    total_activities = 0
    total_sources = 0

    print(f"Loading {len(orgs)} orgs with contacts into pipeline...")
    print(f"Tenant: {TENANT_ID}")
    print(f"Owner:  {OWNER_ID}")
    print()

    async with factory() as db:
        # Pre-check: ensure pipeline is empty for this tenant
        r = await db.execute(
            text("SELECT count(*) FROM pipeline_entries WHERE tenant_id = :tid"),
            {"tid": TENANT_ID},
        )
        existing = r.scalar()
        if existing > 0:
            print(f"WARNING: {existing} pipeline entries already exist for this tenant.")
            print("This script is designed for initial load into an empty pipeline.")
            resp = input("Continue anyway? (yes/no): ")
            if resp.strip().lower() != "yes":
                print("Aborted.")
                return

        for org_name, data in sorted(orgs.items()):
            entry_id = uuid4()
            domain = data["domain"] or ""
            lanes = sorted(data["lanes"] - {""})
            contacts = data["contacts"]

            # Build intel JSONB
            intel = {
                "vertical": "US Commercial Insurance Brokerage",
                "practice_areas": lanes,
                "contact_count": len(contacts),
            }
            # Add city/state from first contact as HQ hint
            first = contacts[0]
            if first.get("city") or first.get("state"):
                intel["hq_hint"] = ", ".join(
                    filter(None, [first.get("city", ""), first.get("state", "")])
                )

            # --- 1. Create pipeline_entry ---
            await db.execute(
                text("""
                    INSERT INTO pipeline_entries (
                        id, tenant_id, owner_id, entity_type, name, normalized_name,
                        domain, stage, fit_score, fit_tier, relationship_type,
                        source, channels, intel, created_at, updated_at
                    ) VALUES (
                        :id, :tenant_id, :owner_id, 'company', :name, :normalized_name,
                        :domain, 'identified', 0, NULL, :relationship_type,
                        'gtm_scrape', :channels, CAST(:intel AS jsonb), now(), now()
                    )
                """),
                {
                    "id": str(entry_id),
                    "tenant_id": TENANT_ID,
                    "owner_id": OWNER_ID,
                    "name": org_name,
                    "normalized_name": normalize_name(org_name),
                    "domain": domain,
                    "relationship_type": ["prospect"],
                    "channels": ["email"],
                    "intel": __import__("json").dumps(intel),
                },
            )
            total_entries += 1

            # --- 2. Create pipeline_entry_source ---
            await db.execute(
                text("""
                    INSERT INTO pipeline_entry_sources (
                        id, tenant_id, pipeline_entry_id, source_type, created_at
                    ) VALUES (
                        :id, :tenant_id, :entry_id, 'gtm_scrape', now()
                    )
                """),
                {
                    "id": str(uuid4()),
                    "tenant_id": TENANT_ID,
                    "entry_id": str(entry_id),
                },
            )
            total_sources += 1

            # --- 3. Create contacts + draft activities ---
            for contact in contacts:
                contact_id = uuid4()
                contact_name = contact.get("full_name", "").strip()
                contact_email = contact.get("email", "").strip()
                contact_title = contact.get("title", "").strip()
                contact_linkedin = contact.get("linkedin_url", "").strip()
                email_status = contact.get("email_status", "").strip()
                lane = contact.get("lane", "").strip()
                variant = contact.get("variant", "").strip()
                variant_theme = contact.get("variant_theme", "").strip()
                city = contact.get("city", "").strip()
                state = contact.get("state", "").strip()

                # Build contact notes with enrichment context
                notes_parts = []
                if city or state:
                    notes_parts.append(f"Location: {', '.join(filter(None, [city, state]))}")
                if email_status:
                    notes_parts.append(f"Email status: {email_status}")
                if lane:
                    notes_parts.append(f"Lane: {lane}")
                if contact.get("apollo_id"):
                    notes_parts.append(f"Apollo ID: {contact['apollo_id']}")
                contact_notes = " | ".join(notes_parts) if notes_parts else None

                await db.execute(
                    text("""
                        INSERT INTO contacts (
                            id, tenant_id, pipeline_entry_id, name, email, title,
                            role, linkedin_url, phone, notes, is_primary,
                            created_at, updated_at
                        ) VALUES (
                            :id, :tenant_id, :entry_id, :name, :email, :title,
                            NULL, :linkedin_url, NULL, :notes, false,
                            now(), now()
                        )
                    """),
                    {
                        "id": str(contact_id),
                        "tenant_id": TENANT_ID,
                        "entry_id": str(entry_id),
                        "name": contact_name or "Unknown",
                        "email": contact_email or None,
                        "title": contact_title or None,
                        "linkedin_url": contact_linkedin or None,
                        "notes": contact_notes,
                    },
                )
                total_contacts += 1

                # --- 4. Create draft outreach activity ---
                email_subject = contact.get("email_subject", "").strip()
                email_body = contact.get("email_body", "").strip()

                if email_subject or email_body:
                    activity_metadata = {
                        "step_number": 1,
                        "status": "drafted",
                        "variant": variant,
                        "variant_theme": variant_theme,
                        "lane": lane,
                        "from_email": "sharan@lumif.ai",
                    }

                    await db.execute(
                        text("""
                            INSERT INTO activities (
                                id, tenant_id, pipeline_entry_id, contact_id,
                                type, channel, direction, status,
                                subject, body_preview, metadata,
                                occurred_at, created_at
                            ) VALUES (
                                :id, :tenant_id, :entry_id, :contact_id,
                                'email', 'email', 'outbound', 'drafted',
                                :subject, :body_preview, CAST(:metadata AS jsonb),
                                now(), now()
                            )
                        """),
                        {
                            "id": str(uuid4()),
                            "tenant_id": TENANT_ID,
                            "entry_id": str(entry_id),
                            "contact_id": str(contact_id),
                            "subject": email_subject or None,
                            "body_preview": email_body if email_body else None,
                            "metadata": __import__("json").dumps(activity_metadata),
                        },
                    )
                    total_activities += 1

            print(f"  ✓ {org_name}: {len(contacts)} contacts, domain={domain or '(none)'}")

        # Commit everything
        await db.commit()

    print()
    print("=" * 60)
    print("LOAD COMPLETE")
    print("=" * 60)
    print(f"  Pipeline entries:  {total_entries}")
    print(f"  Contacts:          {total_contacts}")
    print(f"  Draft activities:  {total_activities}")
    print(f"  Sources:           {total_sources}")
    print()
    print("All data committed to tenant lumif.ai (sharan@lumif.ai)")


if __name__ == "__main__":
    asyncio.run(run())
