"""Seed the coverage_types table with 23 canonical coverage types.

Uses INSERT ... ON CONFLICT (key) DO NOTHING for idempotency.
Requires broker_schema_mods_03.py to have been run first.

Usage:
    cd backend && uv run python scripts/seed_coverage_taxonomy.py
"""

import asyncio

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Seed data: 23 coverage types from SPEC-COVERAGE-TAXONOMY.md section 6
# ---------------------------------------------------------------------------

COVERAGE_TYPES: list[dict] = [
    # --- 6.1 Liability (6) ---
    {
        "key": "general_liability",
        "category": "liability",
        "display_names": {"en": "Commercial General Liability", "es": "Responsabilidad Civil General"},
        "aliases": {"en": ["CGL", "GL", "General Liability"], "es": ["RCG"]},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 1,
    },
    {
        "key": "auto",
        "category": "liability",
        "display_names": {"en": "Commercial Auto", "es": "Responsabilidad Civil Vehicular"},
        "aliases": {"en": ["Auto Liability", "Commercial Auto Liability"], "es": ["Responsabilidad Civil Vehicular", "Seguro de Flotilla"]},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 2,
    },
    {
        "key": "professional_liability",
        "category": "liability",
        "display_names": {"en": "Professional Liability (E&O)", "es": "Responsabilidad Civil Profesional"},
        "aliases": {"en": ["Professional Indemnity", "PI", "E&O"], "es": ["Indemnizacion Profesional"]},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 3,
    },
    {
        "key": "umbrella",
        "category": "liability",
        "display_names": {"en": "Umbrella/Excess Liability", "es": "Poliza Paraguas"},
        "aliases": {"en": ["Excess Liability", "Umbrella"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 4,
    },
    {
        "key": "environmental_liability",
        "category": "liability",
        "display_names": {"en": "Environmental Liability", "es": "Responsabilidad Civil Ambiental"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction", "energy"],
        "sort_order": 5,
    },
    {
        "key": "employers_liability",
        "category": "liability",
        "display_names": {"en": "Employer's Liability", "es": "Responsabilidad Civil Patronal"},
        "aliases": {"en": ["EL"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 6,
    },
    # --- 6.2 Property (5) ---
    {
        "key": "property",
        "category": "property",
        "display_names": {"en": "Commercial Property", "es": "Seguro de Danos Materiales"},
        "aliases": {"en": ["Property Insurance"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 7,
    },
    {
        "key": "builders_risk",
        "category": "property",
        "display_names": {"en": "Builder's Risk (CAR)", "es": "Todo Riesgo Construccion (CAR)"},
        "aliases": {"en": ["CAR", "Contractor's All Risk"], "es": ["TRC"]},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 8,
    },
    {
        "key": "equipment_floater",
        "category": "property",
        "display_names": {"en": "Contractor's Equipment", "es": "Equipo de Contratista"},
        "aliases": {"en": ["Equipment Floater", "Inland Marine"], "es": []},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 9,
    },
    {
        "key": "installation_floater",
        "category": "property",
        "display_names": {"en": "Installation Floater", "es": "Seguro de Montaje"},
        "aliases": {"en": ["Installation Insurance"], "es": []},
        "countries": [],
        "lines_of_business": ["construction", "manufacturing"],
        "sort_order": 10,
    },
    {
        "key": "marine_cargo",
        "category": "property",
        "display_names": {"en": "Marine Cargo", "es": "Seguro de Transporte de Carga"},
        "aliases": {"en": ["Cargo Insurance", "Transit Insurance"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 11,
    },
    # --- 6.3 Surety (5) ---
    {
        "key": "performance_bond",
        "category": "surety",
        "display_names": {"en": "Performance Bond", "es": "Fianza de Cumplimiento"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 12,
    },
    {
        "key": "payment_bond",
        "category": "surety",
        "display_names": {"en": "Payment Bond", "es": "Fianza de Pago"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 13,
    },
    {
        "key": "bid_bond",
        "category": "surety",
        "display_names": {"en": "Bid Bond", "es": "Fianza de Seriedad de Oferta"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 14,
    },
    {
        "key": "maintenance_bond",
        "category": "surety",
        "display_names": {"en": "Maintenance Bond", "es": "Fianza de Vicios Ocultos"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction"],
        "sort_order": 15,
    },
    {
        "key": "advance_payment_bond",
        "category": "surety",
        "display_names": {"en": "Advance Payment Bond", "es": "Fianza de Anticipo"},
        "aliases": {"en": [], "es": []},
        "countries": ["MX"],
        "lines_of_business": ["construction"],
        "sort_order": 16,
    },
    # --- 6.4 Workers Compensation (1) ---
    {
        "key": "workers_comp",
        "category": "workers_comp",
        "display_names": {"en": "Workers' Compensation", "es": "Riesgos de Trabajo (Complementario IMSS)"},
        "aliases": {"en": ["Work Comp", "WC"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 17,
    },
    # --- 6.5 Specialty (5) ---
    {
        "key": "cyber_liability",
        "category": "specialty",
        "display_names": {"en": "Cyber Liability", "es": "Seguro de Riesgos Ciberneticos"},
        "aliases": {"en": ["Cyber Insurance"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 18,
    },
    {
        "key": "directors_officers",
        "category": "specialty",
        "display_names": {"en": "Directors & Officers (D&O)", "es": "Responsabilidad Civil de Consejeros"},
        "aliases": {"en": ["D&O"], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 19,
    },
    {
        "key": "pollution_liability",
        "category": "specialty",
        "display_names": {"en": "Pollution Liability", "es": "Responsabilidad por Contaminacion"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": ["construction", "energy"],
        "sort_order": 20,
    },
    {
        "key": "wrap_up",
        "category": "specialty",
        "display_names": {"en": "Owner/Contractor Controlled Insurance (OCIP/CCIP)", "es": "Programa de Seguro Controlado"},
        "aliases": {"en": ["OCIP", "CCIP", "Wrap-Up"], "es": []},
        "countries": ["US", "MX"],
        "lines_of_business": ["construction"],
        "sort_order": 21,
    },
    {
        "key": "delay_in_startup",
        "category": "specialty",
        "display_names": {"en": "Delay in Startup (DSU/ALOP)", "es": "Perdida de Beneficios Anticipada"},
        "aliases": {"en": ["DSU", "ALOP"], "es": []},
        "countries": [],
        "lines_of_business": ["construction", "energy"],
        "sort_order": 22,
    },
    # --- 6.6 Special (1) ---
    {
        "key": "other",
        "category": "special",
        "display_names": {"en": "Other", "es": "Otro"},
        "aliases": {"en": [], "es": []},
        "countries": [],
        "lines_of_business": [],
        "sort_order": 23,
    },
]


# ---------------------------------------------------------------------------
# INSERT statement template
# ---------------------------------------------------------------------------

INSERT_SQL = """INSERT INTO coverage_types (
    key, category, display_names, aliases, countries, lines_of_business,
    is_active, is_verified, added_by, sort_order
) VALUES (
    :key, :category, CAST(:display_names AS jsonb), CAST(:aliases AS jsonb),
    :countries, :lines_of_business,
    true, true, 'seed', :sort_order
) ON CONFLICT (key) DO NOTHING"""


async def run_seed() -> None:
    factory = get_session_factory()

    # Verify table exists
    async with factory() as session:
        r = await session.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'coverage_types')"
        ))
        if not r.scalar():
            raise RuntimeError(
                "coverage_types table does not exist. Run broker_schema_mods_03.py first."
            )

    import json

    inserted = 0
    for ct in COVERAGE_TYPES:
        async with factory() as session:
            result = await session.execute(
                text(INSERT_SQL),
                {
                    "key": ct["key"],
                    "category": ct["category"],
                    "display_names": json.dumps(ct["display_names"]),
                    "aliases": json.dumps(ct["aliases"]),
                    "countries": ct["countries"],
                    "lines_of_business": ct["lines_of_business"],
                    "sort_order": ct["sort_order"],
                },
            )
            await session.commit()
            if result.rowcount > 0:
                inserted += 1
            print(f"OK: {ct['key']} ({ct['category']})")

    # Verify count
    async with factory() as session:
        r = await session.execute(text("SELECT COUNT(*) FROM coverage_types"))
        count = r.scalar()

    print(f"\nSeed complete: {inserted} new rows inserted, {count} total rows in coverage_types.")
    if count != 23:
        print(f"WARNING: Expected 23 rows, got {count}.")


if __name__ == "__main__":
    asyncio.run(run_seed())
