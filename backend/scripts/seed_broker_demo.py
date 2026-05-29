"""Seed a full broker demo environment with realistic data.

Layers seeded (bottom-up):
  1. Clients (3)
  2. Client Contacts (7)
  3. Carriers (5)
  4. Carrier Contacts (7)
  5. Projects (3) — at different workflow stages
  6. Uploaded Files (19) — realistic PDFs generated via reportlab
  7. Project Coverages (18)
  8. Carrier Quotes (22)
  9. Activities (24)
 10. Solicitation Drafts (6)
 11. Recommendations (1)

Usage:
    backend/.venv/bin/python3 backend/scripts/seed_broker_demo.py
    backend/.venv/bin/python3 backend/scripts/seed_broker_demo.py --clean-only

Requires: reportlab (install via: uv pip install --python backend/.venv/bin/python3 reportlab)
"""

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TENANT_ID = "c273099e-032a-4f1e-991b-db69c4de67c4"  # Alaya (sharanjm90+broker@gmail.com)
OWNER_ID = "68c47b08-08a4-48d0-a90f-b29721a7e0e6"
NOW = datetime.now(timezone.utc)


def ts(days_ago: int = 0, hours_ago: int = 0) -> str:
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).isoformat()


# ---------------------------------------------------------------------------
# Stable UUIDs
# ---------------------------------------------------------------------------
# Clients
CLIENT_REGIO = str(uuid4())
CLIENT_PACIFIC = str(uuid4())
CLIENT_DESARROLLO = str(uuid4())

# Carriers
CARRIER_CHUBB = str(uuid4())
CARRIER_ZURICH = str(uuid4())
CARRIER_AXA = str(uuid4())
CARRIER_MAPFRE = str(uuid4())
CARRIER_TOKIO = str(uuid4())

# Projects
PROJECT_REGIO = str(uuid4())
PROJECT_PACIFIC = str(uuid4())
PROJECT_DESARROLLO = str(uuid4())

# Uploaded files — 19 total
FILE_MSA_REGIO = str(uuid4())
FILE_MSA_PACIFIC = str(uuid4())
FILE_MSA_DESARROLLO = str(uuid4())
FILE_BOND_REGIO = str(uuid4())
FILE_BOND_PACIFIC = str(uuid4())
FILE_COI_REGIO = str(uuid4())
FILE_COI_PACIFIC = str(uuid4())
FILE_COI_DESARROLLO_PRE = str(uuid4())
FILE_COI_DESARROLLO_FINAL = str(uuid4())
FILE_POLICY_DEC_REGIO = str(uuid4())
FILE_POLICY_DEC_PACIFIC = str(uuid4())
FILE_QUOTE_CHUBB_REGIO = str(uuid4())
FILE_QUOTE_AXA_REGIO = str(uuid4())
FILE_QUOTE_MAPFRE_REGIO = str(uuid4())
FILE_QUOTE_ZURICH_PACIFIC = str(uuid4())
FILE_QUOTE_AXA_PACIFIC = str(uuid4())
FILE_QUOTE_TOKIO_PACIFIC = str(uuid4())
FILE_QUOTE_MAPFRE_DESARROLLO = str(uuid4())
FILE_QUOTE_AXA_DESARROLLO = str(uuid4())

# Map PDF generator names → file IDs
FILE_ID_MAP = {
    "msa_regio": FILE_MSA_REGIO,
    "msa_pacific": FILE_MSA_PACIFIC,
    "msa_desarrollo": FILE_MSA_DESARROLLO,
    "bond_regio": FILE_BOND_REGIO,
    "bond_pacific": FILE_BOND_PACIFIC,
    "coi_regio": FILE_COI_REGIO,
    "coi_pacific": FILE_COI_PACIFIC,
    "coi_desarrollo_pre": FILE_COI_DESARROLLO_PRE,
    "coi_desarrollo_final": FILE_COI_DESARROLLO_FINAL,
    "policy_dec_regio": FILE_POLICY_DEC_REGIO,
    "policy_dec_pacific": FILE_POLICY_DEC_PACIFIC,
    "quote_chubb_regio": FILE_QUOTE_CHUBB_REGIO,
    "quote_axa_regio": FILE_QUOTE_AXA_REGIO,
    "quote_mapfre_regio_surety": FILE_QUOTE_MAPFRE_REGIO,
    "quote_zurich_pacific": FILE_QUOTE_ZURICH_PACIFIC,
    "quote_axa_pacific": FILE_QUOTE_AXA_PACIFIC,
    "quote_tokio_pacific": FILE_QUOTE_TOKIO_PACIFIC,
    "quote_mapfre_desarrollo": FILE_QUOTE_MAPFRE_DESARROLLO,
    "quote_axa_desarrollo": FILE_QUOTE_AXA_DESARROLLO,
}

ALL_FILE_IDS = list(FILE_ID_MAP.values())


# ===================================================================
# DATA DEFINITIONS
# ===================================================================

def get_clients():
    return [
        {
            "id": CLIENT_REGIO,
            "name": "Constructora Regio SA de CV",
            "normalized_name": "constructora regio",
            "legal_name": "Constructora Regio, S.A. de C.V.",
            "domain": "constructoraregio.com.mx",
            "tax_id": "CRE-060115-AB3",
            "industry": "Construction",
            "location": "San Pedro Garza García, Nuevo León, México",
            "notes": "Large general contractor specializing in industrial parks and commercial buildings. 20+ year track record in northeast Mexico.",
        },
        {
            "id": CLIENT_PACIFIC,
            "name": "Pacific Builders LLC",
            "normalized_name": "pacific builders",
            "legal_name": "Pacific Builders LLC",
            "domain": "pacificbuilders.com",
            "tax_id": "87-1234567",
            "industry": "Construction",
            "location": "Long Beach, CA, USA",
            "notes": "Mid-size commercial contractor focused on mixed-use and residential high-rise in Southern California.",
        },
        {
            "id": CLIENT_DESARROLLO,
            "name": "Desarrollo Industrial MX",
            "normalized_name": "desarrollo industrial",
            "legal_name": "Desarrollo Industrial MX, S.A. de C.V.",
            "domain": "desarrolloindustrial.mx",
            "tax_id": "DIM-980520-QR7",
            "industry": "Real Estate Development",
            "location": "Monterrey, Nuevo León, México",
            "notes": "Industrial park developer. Owns and operates 4 parks across Nuevo León and Coahuila. Major client — handles entire insurance program.",
        },
    ]


def get_client_contacts():
    return [
        # Allowed roles: primary, billing, technical, legal, executive
        {"broker_client_id": CLIENT_REGIO, "name": "Carlos Mendoza Rivera", "email": "cmendoza@constructoraregio.com.mx", "phone": "+52 81 8363 4500", "role": "executive", "is_primary": True},
        {"broker_client_id": CLIENT_REGIO, "name": "Ana Lucía Garza", "email": "agarza@constructoraregio.com.mx", "phone": "+52 81 8363 4510", "role": "legal", "is_primary": False},
        {"broker_client_id": CLIENT_PACIFIC, "name": "David Chen", "email": "dchen@pacificbuilders.com", "phone": "+1 562 555 0142", "role": "executive", "is_primary": True},
        {"broker_client_id": CLIENT_PACIFIC, "name": "Sarah Mitchell", "email": "smitchell@pacificbuilders.com", "phone": "+1 562 555 0155", "role": "primary", "is_primary": False},
        {"broker_client_id": CLIENT_PACIFIC, "name": "Roberto Fuentes", "email": "rfuentes@pacificbuilders.com", "phone": "+1 562 555 0167", "role": "technical", "is_primary": False},
        {"broker_client_id": CLIENT_DESARROLLO, "name": "Ing. Fernando Villarreal", "email": "fvillarreal@desarrolloindustrial.mx", "phone": "+52 81 8340 2200", "role": "executive", "is_primary": True},
        {"broker_client_id": CLIENT_DESARROLLO, "name": "Lic. Patricia Salinas", "email": "psalinas@desarrolloindustrial.mx", "phone": "+52 81 8340 2215", "role": "legal", "is_primary": False},
    ]


def get_carriers():
    return [
        {
            "id": CARRIER_CHUBB, "carrier_name": "Chubb Mexico", "carrier_type": "insurance",
            "carrier_code": "CHUBB-MX", "submission_method": "email",
            "coverage_types": ["general_liability", "auto", "workers_comp", "umbrella", "builders_risk"],
            "regions": ["mexico", "latam"], "min_project_value": 5000000, "max_project_value": 500000000,
            "avg_response_days": 5, "avg_premium_ratio": 0.0058, "total_quotes": 12, "total_selected": 4,
            "notes": "Preferred carrier for large construction risks in Mexico. Strong underwriting team.",
        },
        {
            "id": CARRIER_ZURICH, "carrier_name": "Zurich North America", "carrier_type": "insurance",
            "carrier_code": "ZURICH-NA", "submission_method": "portal",
            "portal_url": "https://zurichna.com/portal",
            "coverage_types": ["general_liability", "auto", "umbrella", "professional_liability"],
            "regions": ["usa", "canada", "mexico"], "min_project_value": 2000000, "max_project_value": 300000000,
            "avg_response_days": 7, "avg_premium_ratio": 0.0062, "total_quotes": 8, "total_selected": 3,
            "notes": "Good for cross-border US/Mexico risks. Portal submissions preferred.",
        },
        {
            "id": CARRIER_AXA, "carrier_name": "AXA Mexico", "carrier_type": "insurance",
            "carrier_code": "AXA-MX", "submission_method": "email",
            "coverage_types": ["general_liability", "auto", "workers_comp", "property"],
            "regions": ["mexico", "usa"], "min_project_value": 1000000, "max_project_value": 200000000,
            "avg_response_days": 4, "avg_premium_ratio": 0.0055, "total_quotes": 15, "total_selected": 6,
            "notes": "Most competitive on workers' comp and auto. Fast turnaround.",
        },
        {
            "id": CARRIER_MAPFRE, "carrier_name": "Mapfre Mexico", "carrier_type": "insurance",
            "carrier_code": "MAPFRE-MX", "submission_method": "email",
            "coverage_types": ["general_liability", "auto", "surety", "property"],
            "regions": ["mexico", "latam"], "min_project_value": 500000, "max_project_value": 150000000,
            "avg_response_days": 3, "avg_premium_ratio": 0.0048, "total_quotes": 20, "total_selected": 8,
            "notes": "Best rates for mid-size projects. Also writes surety bonds. Very responsive.",
        },
        {
            "id": CARRIER_TOKIO, "carrier_name": "Tokio Marine", "carrier_type": "insurance",
            "carrier_code": "TOKIO", "submission_method": "email",
            "coverage_types": ["general_liability", "umbrella", "builders_risk", "marine_cargo"],
            "regions": ["mexico", "usa", "asia"], "min_project_value": 10000000, "max_project_value": 1000000000,
            "avg_response_days": 10, "avg_premium_ratio": 0.0065, "total_quotes": 5, "total_selected": 1,
            "notes": "Premium carrier for large/complex risks. Slower but very thorough underwriting.",
        },
    ]


def get_carrier_contacts():
    return [
        {"carrier_config_id": CARRIER_CHUBB, "name": "María Elena Gutiérrez", "email": "maria.gutierrez@chubb.com.mx", "phone": "+52 55 5258 2100", "role": "submissions", "is_primary": True},
        {"carrier_config_id": CARRIER_CHUBB, "name": "Jorge Ramírez", "email": "jorge.ramirez@chubb.com.mx", "phone": "+52 55 5258 2150", "role": "account_manager", "is_primary": False},
        {"carrier_config_id": CARRIER_ZURICH, "name": "Jennifer Walsh", "email": "jennifer.walsh@zurichna.com", "phone": "+1 847 555 0200", "role": "submissions", "is_primary": True},
        {"carrier_config_id": CARRIER_AXA, "name": "Alejandro Vega", "email": "alejandro.vega@axa.com.mx", "phone": "+52 55 5169 1000", "role": "submissions", "is_primary": True},
        {"carrier_config_id": CARRIER_MAPFRE, "name": "Laura Domínguez", "email": "laura.dominguez@mapfre.com.mx", "phone": "+52 55 5230 8700", "role": "submissions", "is_primary": True},
        {"carrier_config_id": CARRIER_MAPFRE, "name": "Ricardo Flores", "email": "ricardo.flores@mapfre.com.mx", "phone": "+52 55 5230 8750", "role": "account_manager", "is_primary": False},
        {"carrier_config_id": CARRIER_TOKIO, "name": "Kenji Tanaka", "email": "kenji.tanaka@tokiomarine.com", "phone": "+52 55 5081 6300", "role": "submissions", "is_primary": True},
    ]


def get_projects():
    return [
        {
            "id": PROJECT_REGIO,
            "name": "Parque Industrial Ciénega Phase II",
            "project_type": "construction",
            "description": "Industrial park development — 12 warehouse units, admin building, and shared infrastructure. Phase II of the Ciénega complex.",
            "contract_value": 185000000, "currency": "MXN",
            "start_date": "2026-03-01", "end_date": "2027-04-30",
            "location": "Ciénega de Flores, Nuevo León, México",
            "language": "es",
            "status": "gaps_identified", "analysis_status": "completed",
            "client_id": CLIENT_REGIO,
            "source_document_id": FILE_MSA_REGIO,
        },
        {
            "id": PROJECT_PACIFIC,
            "name": "Harbor View Tower Renovation",
            "project_type": "construction",
            "description": "Seismic retrofit and interior renovation of 18-story mixed-use tower. Structural reinforcement, elevator modernization, full MEP upgrade.",
            "contract_value": 8200000, "currency": "USD",
            "start_date": "2025-06-01", "end_date": "2027-06-01",
            "location": "Long Beach, CA, USA",
            "language": "en",
            "status": "quotes_partial", "analysis_status": "completed",
            "client_id": CLIENT_PACIFIC,
            "source_document_id": FILE_MSA_PACIFIC,
        },
        {
            "id": PROJECT_DESARROLLO,
            "name": "Nave Industrial Apodaca Lote 7",
            "project_type": "construction",
            "description": "15,000 sqm industrial warehouse with loading docks, fire suppression, and office mezzanine for lease to automotive supplier.",
            "contract_value": 42000000, "currency": "MXN",
            "start_date": "2025-01-15", "end_date": "2025-11-30",
            "location": "Apodaca, Nuevo León, México",
            "language": "es",
            "status": "delivered", "analysis_status": "completed",
            "client_id": CLIENT_DESARROLLO,
            "source_document_id": FILE_MSA_DESARROLLO,
        },
    ]


def get_uploaded_files():
    """Return file metadata. size_bytes is filled in during PDF generation."""
    def _f(file_id, filename, doc_type, project_name, extracted, extra_meta=None):
        meta = {"document_type": doc_type, "project_name": project_name}
        if extra_meta:
            meta.update(extra_meta)
        return {
            "id": file_id, "filename": filename, "mimetype": "application/pdf",
            "size_bytes": 0,
            "storage_path": f"{TENANT_ID}/{file_id}/{filename}",
            "extracted_text": extracted,
            "metadata": meta,
        }

    return [
        # --- Contracts ---
        _f(FILE_MSA_REGIO, "MSA-2026-0147-Constructora-Regio.pdf", "contract",
           "Parque Industrial Ciénega Phase II",
           "MASTER SERVICE AGREEMENT. Parties: Desarrollo Industrial MX (Owner) and Constructora Regio (Contractor). "
           "Contract value: MXN $185,000,000. Insurance: CGL $5M, Auto $2M, WC statutory, Umbrella $10M, Builders Risk full value. "
           "Surety: Performance Bond 100%, Payment Bond 100%. Additional insured and waiver of subrogation required."),
        _f(FILE_MSA_PACIFIC, "Contract-HVT-2025-001-Pacific-Builders.pdf", "contract",
           "Harbor View Tower Renovation",
           "CONSTRUCTION CONTRACT. Harbor View Tower seismic retrofit. Pacific Builders LLC contractor. "
           "Contract value: $8,200,000 USD. Insurance: CGL $5M, Auto $2M, WC statutory (CA), Umbrella $5M, "
           "Builders Risk $8.2M (must include earthquake), Professional Liability $2M if design-build. "
           "Surety: Performance $8.2M, Payment $8.2M, Maintenance Bond 10% ($820K)."),
        _f(FILE_MSA_DESARROLLO, "Contrato-DIM-NAV-2024-007-Nave-Apodaca.pdf", "contract",
           "Nave Industrial Apodaca Lote 7",
           "CONTRATO DE OBRA. Nave Industrial Apodaca Lote 7. Constructora del Norte contractor. "
           "Valor: MXN $42,000,000. Seguro: RC General $3M, Auto $1M, Riesgos de Trabajo statutory. "
           "Fianzas: Cumplimiento 100%, Pago 100%."),

        # --- Bond Schedules ---
        _f(FILE_BOND_REGIO, "Bond-Requirements-Constructora-Regio-2026.pdf", "bond_schedule",
           "Parque Industrial Ciénega Phase II",
           "SURETY BOND REQUIREMENTS. Constructora Regio. Required: Performance Bond MXN $185M, Payment Bond MXN $185M. "
           "Bonding history: MXN $260M completed (Phase I, Saltillo, MTY office). No claims. "
           "Recommended sureties: Mapfre (prior relationship), Chubb (prior), Zurich (new market).",
           {"carrier": "TBD — solicitation required"}),
        _f(FILE_BOND_PACIFIC, "Bond-Schedule-Pacific-Builders-2026.pdf", "bond_schedule",
           "Harbor View Tower Renovation",
           "SURETY BOND SCHEDULE. Pacific Builders LLC. Surety: Zurich NA (A+, XV). "
           "Active: Performance $8.2M + Payment $8.2M (Harbor View), Performance $4.5M + Payment $4.5M (Westside). "
           "Capacity: $35M aggregate, $25.4M committed, $9.6M available. "
           "Gaps: No Maintenance Bond, No Bid Bond, possible subdivision bond."),

        # --- COIs ---
        _f(FILE_COI_REGIO, "COI-Constructora-Regio-2025.pdf", "coi",
           "Parque Industrial Ciénega Phase II",
           "CERTIFICATE OF INSURANCE. Constructora Regio. Current: CGL $3M (Mapfre), Auto $1M (AXA), "
           "WC statutory (AXA), Umbrella $5M (Mapfre). Gaps vs contract: CGL needs $5M (gap $2M), "
           "Umbrella needs $10M (gap $5M), no Builders Risk, no surety bonds."),
        _f(FILE_COI_PACIFIC, "COI-Pacific-Builders-2025.pdf", "coi",
           "Harbor View Tower Renovation",
           "CERTIFICATE OF INSURANCE. Pacific Builders LLC. CGL $5M (Zurich), Auto $2M (Zurich), "
           "WC statutory (State Fund), Umbrella $5M (Zurich), Builders Risk $8.2M (Tokio Marine). "
           "Additional insured: Harbor View Properties LLC."),
        _f(FILE_COI_DESARROLLO_PRE, "COI-Constructora-Norte-2024-Pre.pdf", "coi",
           "Nave Industrial Apodaca Lote 7",
           "CERTIFICATE OF INSURANCE (pre-placement). Constructora del Norte. Current: CGL $2M (AXA), "
           "Auto $500K (AXA), WC statutory (AXA). Gaps: CGL needs $3M, Auto needs $1M, no construction all-risk, no bonds."),
        _f(FILE_COI_DESARROLLO_FINAL, "COI-Nave-Apodaca-2025-Final.pdf", "coi",
           "Nave Industrial Apodaca Lote 7",
           "CERTIFICATE OF INSURANCE — FINAL. All coverages bound. CGL $3M (Mapfre, $22,400), "
           "Auto $1M (AXA, $8,900), WC statutory (AXA, $15,200). Performance Bond $42M (Mapfre, $63K MXN), "
           "Payment Bond $42M (Mapfre, $42K MXN). Total: $46,500 insurance + MXN $315K surety.",
           {"status": "final_bound"}),

        # --- Policy Declarations ---
        _f(FILE_POLICY_DEC_REGIO, "Policy-Dec-CGL-Constructora-Regio.pdf", "policy_declarations",
           "Parque Industrial Ciénega Phase II",
           "POLICY DECLARATIONS. CGL Policy MPF-RC-2025-0998. Carrier: Mapfre Mexico. "
           "Limit: $3M occurrence, $6M aggregate. Deductible: $15K. Premium: $18,500. "
           "Endorsements: Waiver of subrogation included, NO additional insured endorsed. "
           "Exclusions: earthquake, asbestos, pollution (no buyback), professional liability, "
           "EIFS defects, subsidence. Analysis: limit insufficient for Phase II ($5M required), "
           "no AI endorsement for Desarrollo Industrial."),
        _f(FILE_POLICY_DEC_PACIFIC, "Policy-Dec-CGL-Umbrella-Pacific-Builders.pdf", "policy_declarations",
           "Harbor View Tower Renovation",
           "POLICY DECLARATIONS. CGL ZNA-CGL-2025-1890: $5M occurrence, $10M aggregate, $25K deductible, $48K premium. "
           "Umbrella ZNA-UMB-2025-0445: $5M/$5M, $10K SIR, $15K premium. Carrier: Zurich NA. "
           "Endorsements: Additional Insured (Harbor View Properties), Primary & Non-Contributory, Waiver of Subrogation. "
           "Exclusions: mold/fungus ($100K sublimit), EIFS, lead paint, pollution, professional liability."),

        # --- Quote Letters ---
        _f(FILE_QUOTE_CHUBB_REGIO, "Quote-Chubb-Mexico-CMX-2026-Q-0891.pdf", "quote_letter",
           "Parque Industrial Ciénega Phase II",
           "CHUBB MEXICO QUOTATION. CGL $5M/$25K ded/$47,500. Auto $2M/$10K/$12,300. "
           "WC statutory/$28,700. Umbrella $10M/$10K SIR/$18,500. Total: $107,000. "
           "Exclusions: earthquake, asbestos, professional liability, pollution. Valid 90 days.",
           {"carrier": "Chubb Mexico"}),
        _f(FILE_QUOTE_AXA_REGIO, "Quote-AXA-Mexico-2026-Q-1455.pdf", "quote_letter",
           "Parque Industrial Ciénega Phase II",
           "AXA MEXICO QUOTATION. CGL $5M/$20K ded/$42,800. Auto $2M/$7,500/$10,900. "
           "WC statutory/$25,100. Total: $78,800. No umbrella available from AXA for this class. "
           "Exclusions: earthquake, asbestos, professional liability, pollution, subsidence.",
           {"carrier": "AXA Mexico"}),
        _f(FILE_QUOTE_MAPFRE_REGIO, "Quote-Mapfre-Surety-2026-Q-0223.pdf", "quote_letter",
           "Parque Industrial Ciénega Phase II",
           "MAPFRE MEXICO SURETY QUOTATION. Performance Bond MXN $185M at 0.45% = MXN $832,500. "
           "Payment Bond MXN $185M at 0.30% = MXN $555,000. Total: MXN $1,387,500 (~$77K USD). "
           "Preferred rates based on Phase I history. Aggregate capacity MXN $400M.",
           {"carrier": "Mapfre Mexico"}),
        _f(FILE_QUOTE_ZURICH_PACIFIC, "Quote-Zurich-NA-2026-Q-4521.pdf", "quote_letter",
           "Harbor View Tower Renovation",
           "ZURICH NA QUOTATION. CGL $5M/$25K/$52,000. Umbrella $5M/$10K SIR/$16,500. "
           "Total: $68,500. Exclusions: mold ($100K sublimit), EIFS, lead, pollution.",
           {"carrier": "Zurich North America"}),
        _f(FILE_QUOTE_AXA_PACIFIC, "Quote-AXA-XL-2026-Q-7891.pdf", "quote_letter",
           "Harbor View Tower Renovation",
           "AXA XL QUOTATION. CGL $5M/$50K ded/$44,800. Auto $2M/$5K/$14,200. Total: $59,000. "
           "WARNING: CGL deductible $50K may not meet contract requirement of $25K.",
           {"carrier": "AXA XL"}),
        _f(FILE_QUOTE_TOKIO_PACIFIC, "Quote-Tokio-Marine-BR-2026-Q-0334.pdf", "quote_letter",
           "Harbor View Tower Renovation",
           "TOKIO MARINE BUILDERS RISK. Completed value $8.2M. All-risk special form. "
           "EARTHQUAKE INCLUDED (5% ded, $50K min). Flood $250K sublimit. $25K non-EQ deductible. "
           "Premium: $38,500/yr ($77K for 24-month term).",
           {"carrier": "Tokio Marine"}),
        _f(FILE_QUOTE_MAPFRE_DESARROLLO, "Quote-Mapfre-2024-Q-3345-Nave-Apodaca.pdf", "quote_letter",
           "Nave Industrial Apodaca Lote 7",
           "MAPFRE COMBINED QUOTE. CGL $3M/$15K/$22,400. Performance Bond $42M at 0.45% = MXN $189K. "
           "Payment Bond $42M at 0.30% = MXN $126K. Total: $22,400 + MXN $315K surety.",
           {"carrier": "Mapfre Mexico"}),
        _f(FILE_QUOTE_AXA_DESARROLLO, "Quote-AXA-2024-Q-9012-Nave-Apodaca.pdf", "quote_letter",
           "Nave Industrial Apodaca Lote 7",
           "AXA MEXICO QUOTATION. Auto $1M/$5K/$8,900. WC statutory/$15,200. Total: $24,100.",
           {"carrier": "AXA Mexico"}),
    ]


def get_coverages():
    return [
        # --- Project Regio (gaps_identified) — 7 coverages ---
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "general_liability", "category": "insurance",
         "display_name": "Commercial General Liability", "language": "es",
         "required_limit": 5000000, "required_deductible": 25000,
         "required_terms": "Per occurrence, completed operations included",
         "contract_clause": "Section 3 — Insurance Requirements, Row 1",
         "current_limit": 3000000, "current_carrier": "Mapfre Mexico",
         "current_policy_number": "MPF-RC-2025-0998", "current_expiry": "2026-06-01",
         "gap_status": "gap", "gap_amount": 2000000,
         "gap_notes": "Current limit $3M vs required $5M. Need to increase or place project-specific policy.",
         "source_document_id": FILE_MSA_REGIO, "source_page": 2, "source_section": "Section 3",
         "source_excerpt": "Commercial General Liability — $5,000,000 per occurrence",
         "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "auto_liability", "category": "insurance",
         "display_name": "Commercial Auto Liability", "language": "es",
         "required_limit": 2000000, "required_deductible": 10000,
         "required_terms": "CSL, hired and non-owned included",
         "contract_clause": "Section 3 — Insurance Requirements, Row 2",
         "current_limit": 1000000, "current_carrier": "AXA Mexico",
         "current_policy_number": "AXA-AU-2025-0456", "current_expiry": "2026-06-01",
         "gap_status": "gap", "gap_amount": 1000000,
         "gap_notes": "Current $1M vs required $2M. Increase needed.",
         "source_document_id": FILE_MSA_REGIO, "source_page": 2, "source_section": "Section 3",
         "source_excerpt": "Commercial Auto Liability — $2,000,000 combined single limit",
         "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "workers_comp", "category": "insurance",
         "display_name": "Workers' Compensation", "language": "es",
         "required_terms": "Statutory limits per Mexican labor law",
         "contract_clause": "Section 3, Row 3",
         "current_carrier": "AXA Mexico", "current_policy_number": "AXA-RT-2025-0457",
         "current_expiry": "2026-06-01",
         "gap_status": "covered", "gap_notes": "Current policy meets statutory requirement",
         "source_document_id": FILE_MSA_REGIO, "source_page": 2, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "umbrella", "category": "insurance",
         "display_name": "Umbrella / Excess Liability", "language": "es",
         "required_limit": 10000000, "required_deductible": 10000,
         "required_terms": "Follow-form over CGL, Auto, WC",
         "contract_clause": "Section 3, Row 4",
         "current_limit": 5000000, "current_carrier": "Mapfre Mexico",
         "current_policy_number": "MPF-UMB-2025-0320", "current_expiry": "2026-06-01",
         "gap_status": "gap", "gap_amount": 5000000,
         "gap_notes": "Current $5M vs required $10M.",
         "source_document_id": FILE_MSA_REGIO, "source_page": 2, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "builders_risk", "category": "insurance",
         "display_name": "Builders Risk / Course of Construction", "language": "es",
         "required_limit": 185000000, "required_terms": "Full replacement value",
         "contract_clause": "Section 3, Row 5",
         "gap_status": "gap", "gap_amount": 185000000,
         "gap_notes": "No builders risk coverage exists — must place new policy",
         "source_document_id": FILE_MSA_REGIO, "source_page": 2, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "performance_bond", "category": "surety",
         "display_name": "Performance Bond", "language": "es",
         "required_limit": 185000000,
         "required_terms": "100% of contract, through Final Completion + 12mo warranty",
         "contract_clause": "Section 4 — Surety Bond Requirements",
         "gap_status": "gap", "gap_amount": 185000000,
         "gap_notes": "Bond not placed — surety submission required",
         "source_document_id": FILE_BOND_REGIO, "source_page": 1, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "coverage_type": "payment_bond", "category": "surety",
         "display_name": "Payment Bond", "language": "es",
         "required_limit": 185000000,
         "required_terms": "100% of contract value",
         "contract_clause": "Section 4 — Surety Bond Requirements",
         "gap_status": "gap", "gap_amount": 185000000,
         "gap_notes": "Bond not placed — surety submission required",
         "source_document_id": FILE_BOND_REGIO, "source_page": 1, "confidence": "high"},

        # --- Project Pacific (quotes_received) — 6 coverages ---
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "general_liability", "category": "insurance",
         "display_name": "Commercial General Liability",
         "required_limit": 5000000, "required_deductible": 25000,
         "current_limit": 5000000, "current_carrier": "Zurich North America",
         "current_policy_number": "ZNA-CGL-2025-1890", "current_expiry": "2026-05-01",
         "gap_status": "covered", "gap_notes": "Current Zurich policy meets limit. Renewal quotes received.",
         "source_document_id": FILE_MSA_PACIFIC, "source_page": 2, "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "auto_liability", "category": "insurance",
         "display_name": "Commercial Auto Liability",
         "required_limit": 2000000,
         "current_limit": 2000000, "current_carrier": "Zurich North America",
         "current_policy_number": "ZNA-AU-2025-1891", "current_expiry": "2026-05-01",
         "gap_status": "covered",
         "source_document_id": FILE_MSA_PACIFIC, "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "builders_risk", "category": "insurance",
         "display_name": "Builders Risk (All-Risk incl. Earthquake)",
         "required_limit": 8200000, "required_terms": "All-risk, must include earthquake",
         "current_limit": 8200000, "current_carrier": "Tokio Marine",
         "current_policy_number": "TM-BR-2025-0112", "current_expiry": "2027-06-01",
         "gap_status": "covered", "gap_notes": "Tokio Marine policy includes earthquake — meets contract.",
         "source_document_id": FILE_POLICY_DEC_PACIFIC, "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "performance_bond", "category": "surety",
         "display_name": "Performance Bond",
         "required_limit": 8200000,
         "current_limit": 8200000, "current_carrier": "Zurich North America",
         "current_policy_number": "ZNA-PB-2025-0445", "current_expiry": "2027-06-01",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "payment_bond", "category": "surety",
         "display_name": "Payment Bond",
         "required_limit": 8200000,
         "current_limit": 8200000, "current_carrier": "Zurich North America",
         "current_policy_number": "ZNA-PYB-2025-0446", "current_expiry": "2027-06-01",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "coverage_type": "maintenance_bond", "category": "surety",
         "display_name": "Maintenance Bond",
         "required_limit": 820000,
         "required_terms": "2-year maintenance bond upon substantial completion, 10% of contract",
         "gap_status": "gap", "gap_amount": 820000,
         "gap_notes": "Required by contract — not yet placed. Triggers at substantial completion.",
         "source_document_id": FILE_BOND_PACIFIC, "confidence": "medium"},

        # --- Project Desarrollo (delivered) — 5 coverages, all met ---
        {"broker_project_id": PROJECT_DESARROLLO, "coverage_type": "general_liability", "category": "insurance",
         "display_name": "Responsabilidad Civil General", "language": "es",
         "required_limit": 3000000, "required_deductible": 15000,
         "current_limit": 3000000, "current_carrier": "Mapfre Mexico",
         "current_policy_number": "MPF-RC-2025-1122", "current_expiry": "2026-01-15",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "coverage_type": "auto_liability", "category": "insurance",
         "display_name": "Responsabilidad Auto", "language": "es",
         "required_limit": 1000000,
         "current_limit": 1000000, "current_carrier": "AXA Mexico",
         "current_policy_number": "AXA-AU-2025-0789", "current_expiry": "2026-01-15",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "coverage_type": "workers_comp", "category": "insurance",
         "display_name": "Riesgos de Trabajo", "language": "es",
         "current_carrier": "AXA Mexico",
         "current_policy_number": "AXA-RT-2025-0790", "current_expiry": "2026-01-15",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "coverage_type": "performance_bond", "category": "surety",
         "display_name": "Fianza de Cumplimiento", "language": "es",
         "required_limit": 42000000,
         "current_limit": 42000000, "current_carrier": "Mapfre Mexico",
         "current_policy_number": "MPF-FC-2025-0334", "current_expiry": "2026-05-30",
         "gap_status": "covered", "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "coverage_type": "payment_bond", "category": "surety",
         "display_name": "Fianza de Pago", "language": "es",
         "required_limit": 42000000,
         "current_limit": 42000000, "current_carrier": "Mapfre Mexico",
         "current_policy_number": "MPF-FP-2025-0335", "current_expiry": "2026-05-30",
         "gap_status": "covered", "confidence": "high"},
    ]


def get_quotes():
    return [
        # === Project Regio — 3 carriers, multiple lines ===
        # Chubb (4 lines)
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "premium": 47500, "deductible": 25000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2026-05-25", "status": "received",
         "exclusions": ["Earthquake damage", "Asbestos", "Professional liability", "Pollution"],
         "conditions": ["Additional insured: Desarrollo Industrial MX", "Waiver of subrogation included"],
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_CHUBB_REGIO, "source_page": 1,
         "source_excerpt": "CGL: $5M limit, $25K deductible, $47,500 premium", "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "premium": 12300, "deductible": 10000, "limit_amount": 2000000,
         "term_months": 12, "validity_date": "2026-05-25", "status": "received",
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_CHUBB_REGIO, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "premium": 28700, "term_months": 12,
         "validity_date": "2026-05-25", "status": "received",
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_CHUBB_REGIO, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "premium": 18500, "deductible": 10000, "limit_amount": 10000000,
         "term_months": 12, "validity_date": "2026-05-25", "status": "received",
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_CHUBB_REGIO, "confidence": "high"},

        # AXA (3 lines — no umbrella)
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "AXA Mexico", "carrier_config_id": CARRIER_AXA,
         "premium": 42800, "deductible": 20000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2026-05-28", "status": "received",
         "exclusions": ["Earthquake", "Asbestos", "Professional liability", "Pollution", "Subsidence"],
         "conditions": ["Additional insured per contract", "Waiver of subrogation on all lines"],
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_AXA_REGIO, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "AXA Mexico", "carrier_config_id": CARRIER_AXA,
         "premium": 10900, "deductible": 7500, "limit_amount": 2000000,
         "term_months": 12, "validity_date": "2026-05-28", "status": "received",
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_AXA_REGIO, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "AXA Mexico", "carrier_config_id": CARRIER_AXA,
         "premium": 25100, "term_months": 12,
         "validity_date": "2026-05-28", "status": "received",
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_AXA_REGIO, "confidence": "high"},

        # Mapfre (surety — 2 bonds)
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "carrier_type": "surety",          "premium": 46250, "limit_amount": 185000000,  # MXN $832,500 ≈ $46,250 USD
         "term_months": 24, "validity_date": "2026-05-05", "status": "received",
         "conditions": ["Indemnity agreement from shareholders >10%", "Quarterly financial reporting"],
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_MAPFRE_REGIO, "confidence": "high"},
        {"broker_project_id": PROJECT_REGIO, "carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "carrier_type": "surety",          "premium": 30833, "limit_amount": 185000000,  # MXN $555,000 ≈ $30,833 USD
         "term_months": 18, "validity_date": "2026-05-05", "status": "received",
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_MAPFRE_REGIO, "confidence": "high"},

        # === Project Pacific — 3 carriers ===
        # Zurich (2 lines: CGL, Umbrella)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_name": "Zurich North America", "carrier_config_id": CARRIER_ZURICH,
         "premium": 52000, "deductible": 25000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2026-06-10", "status": "received",
         "exclusions": ["Mold/fungus (sublimit $100K)", "EIFS defects", "Lead paint", "Pollution"],
         "conditions": ["Additional insured: Harbor View Properties", "Primary & non-contributory"],
         "received_at": ts(days_ago=7),
         "source_document_id": FILE_QUOTE_ZURICH_PACIFIC, "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "carrier_name": "Zurich North America", "carrier_config_id": CARRIER_ZURICH,
         "premium": 16500, "deductible": 10000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2026-06-10", "status": "received",
         "received_at": ts(days_ago=7),
         "source_document_id": FILE_QUOTE_ZURICH_PACIFIC, "confidence": "high"},

        # AXA XL (2 lines: CGL, Auto — flagged)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_name": "AXA XL", "carrier_config_id": CARRIER_AXA,
         "premium": 44800, "deductible": 50000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2026-06-12", "status": "received",
         "exclusions": ["Subsidence", "EIFS", "Mold/fungus", "Professional services"],
         "has_critical_exclusion": True,
         "critical_exclusion_detail": "Deductible $50K — contract requires $25K or lower",
         "received_at": ts(days_ago=5),
         "source_document_id": FILE_QUOTE_AXA_PACIFIC, "confidence": "high"},
        {"broker_project_id": PROJECT_PACIFIC, "carrier_name": "AXA XL", "carrier_config_id": CARRIER_AXA,
         "premium": 14200, "deductible": 5000, "limit_amount": 2000000,
         "term_months": 12, "validity_date": "2026-06-12", "status": "received",
         "received_at": ts(days_ago=5),
         "source_document_id": FILE_QUOTE_AXA_PACIFIC, "confidence": "high"},

        # Tokio Marine (Builders Risk)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_name": "Tokio Marine", "carrier_config_id": CARRIER_TOKIO,
         "premium": 38500, "deductible": 25000, "limit_amount": 8200000,
         "term_months": 24, "validity_date": "2026-05-18", "status": "received",
         "conditions": ["Earthquake included (5% ded, $50K min)", "Monthly value reporting required"],
         "received_at": ts(days_ago=3),
         "source_document_id": FILE_QUOTE_TOKIO_PACIFIC, "confidence": "high"},

        # === Project Desarrollo — 2 carriers (selected) ===
        # Mapfre (CGL + surety)
        {"broker_project_id": PROJECT_DESARROLLO, "carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "premium": 22400, "deductible": 15000, "limit_amount": 3000000,
         "term_months": 12, "status": "selected", "selected_at": ts(days_ago=120),
         "received_at": ts(days_ago=150),
         "source_document_id": FILE_QUOTE_MAPFRE_DESARROLLO, "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "carrier_type": "surety",          "premium": 10500, "limit_amount": 42000000,
         "term_months": 18, "status": "selected", "selected_at": ts(days_ago=120),
         "received_at": ts(days_ago=150),
         "source_document_id": FILE_QUOTE_MAPFRE_DESARROLLO, "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "carrier_type": "surety",          "premium": 7000, "limit_amount": 42000000,
         "term_months": 12, "status": "selected", "selected_at": ts(days_ago=120),
         "received_at": ts(days_ago=150),
         "source_document_id": FILE_QUOTE_MAPFRE_DESARROLLO, "confidence": "high"},
        # AXA (Auto, WC)
        {"broker_project_id": PROJECT_DESARROLLO, "carrier_name": "AXA Mexico", "carrier_config_id": CARRIER_AXA,
         "premium": 8900, "deductible": 5000, "limit_amount": 1000000,
         "term_months": 12, "status": "selected", "selected_at": ts(days_ago=120),
         "received_at": ts(days_ago=145),
         "source_document_id": FILE_QUOTE_AXA_DESARROLLO, "confidence": "high"},
        {"broker_project_id": PROJECT_DESARROLLO, "carrier_name": "AXA Mexico", "carrier_config_id": CARRIER_AXA,
         "premium": 15200, "term_months": 12,
         "status": "selected", "selected_at": ts(days_ago=120),
         "received_at": ts(days_ago=145),
         "source_document_id": FILE_QUOTE_AXA_DESARROLLO, "confidence": "high"},
    ]


def get_activities():
    return [
        # === Project Regio timeline ===
        {"broker_project_id": PROJECT_REGIO, "activity_type": "project_created",
         "description": "Project created from uploaded MSA contract", "occurred_at": ts(days_ago=21)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "document_uploaded",
         "description": "MSA-2026-0147-Constructora-Regio.pdf uploaded",
         "document_id": FILE_MSA_REGIO, "occurred_at": ts(days_ago=21)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "document_uploaded",
         "description": "Bond requirements schedule uploaded",
         "document_id": FILE_BOND_REGIO, "occurred_at": ts(days_ago=21)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "document_uploaded",
         "description": "Current COI uploaded for gap analysis",
         "document_id": FILE_COI_REGIO, "occurred_at": ts(days_ago=21, hours_ago=1)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "document_uploaded",
         "description": "Existing CGL policy declarations uploaded",
         "document_id": FILE_POLICY_DEC_REGIO, "occurred_at": ts(days_ago=21, hours_ago=1)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "analysis_completed",
         "description": "AI analysis completed — 7 coverage requirements extracted, 5 gaps identified (CGL limit, Auto limit, Umbrella limit, Builders Risk, both surety bonds)",
         "occurred_at": ts(days_ago=20)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "solicitation_sent",
         "description": "Quote request sent to Chubb Mexico (CGL, Auto, WC, Umbrella)",
         "carrier_name": "Chubb Mexico", "occurred_at": ts(days_ago=18)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "solicitation_sent",
         "description": "Quote request sent to AXA Mexico (CGL, Auto, WC)",
         "carrier_name": "AXA Mexico", "occurred_at": ts(days_ago=18)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "quote_received",
         "description": "Chubb Mexico — $107,000 total (CGL $47.5K, Auto $12.3K, WC $28.7K, Umbrella $18.5K)",
         "carrier_name": "Chubb Mexico", "occurred_at": ts(days_ago=14)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "quote_received",
         "description": "AXA Mexico — $78,800 total (CGL $42.8K, Auto $10.9K, WC $25.1K). No umbrella available.",
         "carrier_name": "AXA Mexico", "occurred_at": ts(days_ago=12)},
        {"broker_project_id": PROJECT_REGIO, "activity_type": "quote_received",
         "description": "Mapfre surety quote — Performance + Payment bonds, MXN $1.39M total (~$77K USD)",
         "carrier_name": "Mapfre Mexico", "occurred_at": ts(days_ago=8)},

        # === Project Pacific timeline ===
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "project_created",
         "description": "Project created for Harbor View Tower insurance review",
         "occurred_at": ts(days_ago=30)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "document_uploaded",
         "description": "Construction contract HVT-2025-001 uploaded",
         "document_id": FILE_MSA_PACIFIC, "occurred_at": ts(days_ago=30)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "document_uploaded",
         "description": "Current bond schedule uploaded",
         "document_id": FILE_BOND_PACIFIC, "occurred_at": ts(days_ago=30)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "document_uploaded",
         "description": "Current COI and policy declarations uploaded",
         "document_id": FILE_COI_PACIFIC, "occurred_at": ts(days_ago=30, hours_ago=1)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "analysis_completed",
         "description": "AI analysis completed — 6 coverage lines, 1 gap (maintenance bond). Most current policies meet requirements.",
         "occurred_at": ts(days_ago=29)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "quote_received",
         "description": "Zurich NA renewal quote — CGL $52K, Umbrella $16.5K ($68.5K total)",
         "carrier_name": "Zurich North America", "occurred_at": ts(days_ago=7)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "quote_received",
         "description": "AXA XL quote — CGL $44.8K, Auto $14.2K ($59K total). FLAGGED: $50K deductible exceeds contract requirement.",
         "carrier_name": "AXA XL", "occurred_at": ts(days_ago=5)},
        {"broker_project_id": PROJECT_PACIFIC, "activity_type": "quote_received",
         "description": "Tokio Marine builders risk renewal — $38.5K/yr, earthquake included",
         "carrier_name": "Tokio Marine", "occurred_at": ts(days_ago=3)},

        # === Project Desarrollo timeline (delivered) ===
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "project_created",
         "description": "Project created for Nave Industrial Apodaca Lote 7",
         "occurred_at": ts(days_ago=180)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "analysis_completed",
         "description": "Coverage analysis completed — 5 lines required, gaps in CGL limit and Auto limit",
         "occurred_at": ts(days_ago=178)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "quote_received",
         "description": "Mapfre — CGL $22.4K + surety bonds MXN $315K",
         "carrier_name": "Mapfre Mexico", "occurred_at": ts(days_ago=150)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "quote_received",
         "description": "AXA — Auto $8.9K, WC $15.2K",
         "carrier_name": "AXA Mexico", "occurred_at": ts(days_ago=145)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "quote_selected",
         "description": "Carriers selected: Mapfre (CGL + surety), AXA (Auto + WC). Total: $46.5K + MXN $315K.",
         "occurred_at": ts(days_ago=120)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "recommendation_sent",
         "description": "Coverage recommendation delivered to Ing. Villarreal",
         "occurred_at": ts(days_ago=115)},
        {"broker_project_id": PROJECT_DESARROLLO, "activity_type": "project_delivered",
         "description": "All policies bound, certificates delivered. Final COI issued.",
         "occurred_at": ts(days_ago=110)},
    ]


def get_solicitations():
    return [
        # Regio — Chubb (sent)
        {"broker_project_id": PROJECT_REGIO, "carrier_config_id": CARRIER_CHUBB,
         "subject": "RFQ: Constructora Regio — Ciénega Phase II (CGL, Auto, WC, Umbrella)",
         "body": "Dear María Elena,\n\nWe are requesting a quotation for Constructora Regio on the Parque Industrial Ciénega Phase II project.\n\nRequired: CGL $5M, Auto $2M CSL, WC statutory, Umbrella $10M.\nContract value: MXN $185M. Duration: Mar 2026 – Apr 2027.\n\nMSA and current COI attached.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "sent", "sent_to_email": "maria.gutierrez@chubb.com.mx", "sent_at": ts(days_ago=18)},
        # Regio — AXA (sent)
        {"broker_project_id": PROJECT_REGIO, "carrier_config_id": CARRIER_AXA,
         "subject": "RFQ: Constructora Regio — Ciénega Phase II (CGL, Auto, WC)",
         "body": "Dear Alejandro,\n\nRequesting competitive quotation for Constructora Regio's Ciénega Phase II project.\n\nRequired: CGL $5M, Auto $2M, WC statutory.\nContract value: MXN $185M.\n\nMSA attached.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "sent", "sent_to_email": "alejandro.vega@axa.com.mx", "sent_at": ts(days_ago=18)},
        # Regio — Mapfre surety (sent)
        {"broker_project_id": PROJECT_REGIO, "carrier_config_id": CARRIER_MAPFRE,
         "subject": "RFQ: Constructora Regio — Surety Bonds (Performance + Payment)",
         "body": "Dear Laura,\n\nRequesting surety bond quotations:\n- Performance Bond: MXN $185M\n- Payment Bond: MXN $185M\n\nProject: Ciénega Phase II. Prior relationship: Phase I completed without claims.\n\nBond requirements schedule and financial statements attached.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "sent", "sent_to_email": "laura.dominguez@mapfre.com.mx", "sent_at": ts(days_ago=15)},
        # Pacific — Zurich renewal (sent)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_config_id": CARRIER_ZURICH,
         "subject": "Renewal: Pacific Builders — Harbor View Tower (CGL, Umbrella)",
         "body": "Dear Jennifer,\n\nSubmitting for renewal on Pacific Builders' CGL and Umbrella policies expiring May 1, 2026.\n\nCurrent: CGL $5M (ZNA-CGL-2025-1890), Umbrella $5M (ZNA-UMB-2025-0445).\n\nNo claims during current term. Updated loss runs attached.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "sent", "sent_to_email": "jennifer.walsh@zurichna.com", "sent_at": ts(days_ago=14)},
        # Pacific — Tokio (sent, builders risk)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_config_id": CARRIER_TOKIO,
         "subject": "RFQ: Pacific Builders — Builders Risk Renewal (Harbor View Tower)",
         "body": "Dear Kenji,\n\nRequesting renewal quote for builders risk on Harbor View Tower.\n\nCurrent: TM-BR-2025-0112, $8.2M completed value, earthquake included.\nProject on schedule — remaining 14 months.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "sent", "sent_to_email": "kenji.tanaka@tokiomarine.com", "sent_at": ts(days_ago=10)},
        # Pacific — AXA comparison (draft)
        {"broker_project_id": PROJECT_PACIFIC, "carrier_config_id": CARRIER_AXA,
         "subject": "RFQ: Pacific Builders — Harbor View Tower (CGL, Auto — Comparison)",
         "body": "Dear Michael,\n\nSeeking competitive quotes for Pacific Builders:\n- CGL $5M (current with Zurich)\n- Auto $2M CSL\n\nProject: Harbor View Tower Renovation, $8.2M contract.\n\nBest regards,\nLumif.ai Insurance Brokers",
         "status": "draft"},
    ]


def get_recommendations():
    return [
        {
            "broker_project_id": PROJECT_DESARROLLO,
            "subject": "Coverage Recommendation — Nave Industrial Apodaca Lote 7",
            "body": (
                "Dear Ing. Villarreal,\n\n"
                "Following our analysis of the insurance and surety requirements for Nave Industrial Apodaca Lote 7, "
                "we recommend the following coverage program:\n\n"
                "INSURANCE:\n"
                "• General Liability: Mapfre Mexico — $3M limit, $15K deductible, $22,400/yr\n"
                "• Auto Liability: AXA Mexico — $1M limit, $5K deductible, $8,900/yr\n"
                "• Workers' Compensation: AXA Mexico — Statutory, $15,200/yr\n\n"
                "SURETY:\n"
                "• Performance Bond: Mapfre Mexico — MXN $42M, MXN $189,000\n"
                "• Payment Bond: Mapfre Mexico — MXN $42M, MXN $126,000\n\n"
                "Total: $46,500 USD (insurance) + MXN $315,000 (surety)\n\n"
                "All coverages meet contractual requirements. We recommend binding promptly to lock current rates.\n\n"
                "Best regards,\nLumif.ai Insurance Brokers"
            ),
            "recipient_email": "fvillarreal@desarrolloindustrial.mx",
            "status": "sent", "sent_at": ts(days_ago=115),
        },
    ]


# ===================================================================
# DATABASE OPERATIONS
# ===================================================================

BROKER_TABLES = [
    "broker_activities", "submission_documents", "solicitation_drafts",
    "broker_recommendations", "carrier_quotes", "project_coverages",
    "broker_project_emails", "broker_projects",
    "broker_client_contacts", "broker_clients",
    "carrier_contacts", "carrier_configs",
]


async def clean_broker_data(db):
    """Delete all broker data for the tenant."""
    print("Cleaning existing broker data...")

    # Delete seeded uploaded files
    for fid in ALL_FILE_IDS:
        await db.execute(
            text("DELETE FROM uploaded_files WHERE id = :id AND tenant_id = :tid"),
            {"id": fid, "tid": TENANT_ID},
        )
        await db.commit()

    for table in BROKER_TABLES:
        result = await db.execute(
            text(f"DELETE FROM {table} WHERE tenant_id = :tid"),
            {"tid": TENANT_ID},
        )
        await db.commit()
        print(f"  {table}: {result.rowcount} deleted")
    print()


async def insert_row(db, table: str, data: dict):
    """Insert one row with per-statement commit (PgBouncer workaround)."""
    data["tenant_id"] = TENANT_ID
    col_list = list(data.keys())

    cast_placeholders = []
    params = {}
    for k in col_list:
        v = data[k]
        if isinstance(v, dict):
            cast_placeholders.append(f"CAST(:{k} AS jsonb)")
            params[k] = json.dumps(v)
        elif isinstance(v, list):
            cast_placeholders.append(f":{k}")
            params[k] = v
        elif isinstance(v, str) and len(v) == 10 and v[:4].isdigit() and v[4] == "-" and v[7] == "-":
            # Date string like "2026-03-01" → date object for asyncpg
            cast_placeholders.append(f":{k}")
            params[k] = date.fromisoformat(v)
        elif isinstance(v, str) and "T" in v and v[:4].isdigit() and ("+" in v[10:] or v.endswith("Z")):
            # ISO timestamp string → datetime object for asyncpg
            cast_placeholders.append(f":{k}")
            params[k] = datetime.fromisoformat(v)
        else:
            cast_placeholders.append(f":{k}")
            params[k] = v

    cols = ", ".join(col_list)
    vals = ", ".join(cast_placeholders)
    await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), params)
    await db.commit()


async def upload_pdf(tenant_id, file_id, filename, content):
    """Upload PDF to Supabase Storage."""
    try:
        from flywheel.services.document_storage import upload_file
        path = await upload_file(tenant_id, file_id, filename, content, "application/pdf")
        return path, len(content)
    except Exception as e:
        print(f"    WARNING: Storage upload failed for {filename}: {e}")
        return f"{tenant_id}/{file_id}/{filename}", len(content)


# ===================================================================
# MAIN
# ===================================================================

async def seed():
    from seed_broker_pdfs import get_pdf_generators

    factory = get_session_factory()
    generators = get_pdf_generators()

    print("=" * 60)
    print("BROKER DEMO SEED")
    print("=" * 60)
    print(f"Tenant: {TENANT_ID}")
    print(f"Owner:  {OWNER_ID}")
    print()

    async with factory() as db:
        await clean_broker_data(db)

        if args.clean_only:
            print("Clean-only mode — done.")
            return

        # --- Generate PDFs ---
        print(f"Generating {len(generators)} PDFs...")
        pdf_bytes = {}
        for name, (filename, gen_fn) in generators.items():
            content = gen_fn()
            pdf_bytes[name] = content
            print(f"  {filename}: {len(content):,} bytes")
        print()

        # --- Upload to Supabase Storage ---
        print("Uploading PDFs to Supabase Storage...")
        for name, (filename, _) in generators.items():
            file_id = FILE_ID_MAP[name]
            await upload_pdf(TENANT_ID, file_id, filename, pdf_bytes[name])
            print(f"  ✓ {filename}")
        print()

        # --- Insert uploaded_files ---
        print("Inserting uploaded file records...")
        files = get_uploaded_files()
        for f in files:
            gen_name = [k for k, v in FILE_ID_MAP.items() if v == f["id"]][0]
            f["size_bytes"] = len(pdf_bytes[gen_name])
            await insert_row(db, "uploaded_files", f)
        print(f"  ✓ {len(files)} files\n")

        # --- Clients ---
        print("Inserting clients...")
        clients = get_clients()
        for c in clients:
            await insert_row(db, "broker_clients", c)
        print(f"  ✓ {len(clients)}\n")

        # --- Client contacts ---
        print("Inserting client contacts...")
        cc = get_client_contacts()
        for c in cc:
            c["id"] = str(uuid4())
            await insert_row(db, "broker_client_contacts", c)
        print(f"  ✓ {len(cc)}\n")

        # --- Carriers ---
        print("Inserting carriers...")
        carriers = get_carriers()
        for c in carriers:
            await insert_row(db, "carrier_configs", c)
        print(f"  ✓ {len(carriers)}\n")

        # --- Carrier contacts ---
        print("Inserting carrier contacts...")
        ccon = get_carrier_contacts()
        for c in ccon:
            c["id"] = str(uuid4())
            await insert_row(db, "carrier_contacts", c)
        print(f"  ✓ {len(ccon)}\n")

        # --- Projects ---
        print("Inserting projects...")
        projects = get_projects()
        for p in projects:
            p["created_by_user_id"] = OWNER_ID
            p["analysis_completed_at"] = ts(days_ago=20)
            await insert_row(db, "broker_projects", p)
        print(f"  ✓ {len(projects)}\n")

        # --- Coverages ---
        print("Inserting coverages...")
        coverages = get_coverages()
        for c in coverages:
            c["id"] = str(uuid4())
            await insert_row(db, "project_coverages", c)
        print(f"  ✓ {len(coverages)}\n")

        # --- Quotes ---
        print("Inserting quotes...")
        quotes = get_quotes()
        for q in quotes:
            q["id"] = str(uuid4())
            await insert_row(db, "carrier_quotes", q)
        print(f"  ✓ {len(quotes)}\n")

        # --- Activities ---
        print("Inserting activities...")
        activities = get_activities()
        for a in activities:
            a["id"] = str(uuid4())
            await insert_row(db, "broker_activities", a)
        print(f"  ✓ {len(activities)}\n")

        # --- Solicitations ---
        print("Inserting solicitation drafts...")
        solicitations = get_solicitations()
        for s in solicitations:
            s["id"] = str(uuid4())
            s["created_by_user_id"] = OWNER_ID
            await insert_row(db, "solicitation_drafts", s)
        print(f"  ✓ {len(solicitations)}\n")

        # --- Recommendations ---
        print("Inserting recommendations...")
        recs = get_recommendations()
        for r in recs:
            r["id"] = str(uuid4())
            r["created_by_user_id"] = OWNER_ID
            await insert_row(db, "broker_recommendations", r)
        print(f"  ✓ {len(recs)}\n")

    # --- Summary ---
    print("=" * 60)
    print("SEED COMPLETE")
    print("=" * 60)
    print(f"  Clients:          {len(clients)}")
    print(f"  Client contacts:  {len(cc)}")
    print(f"  Carriers:         {len(carriers)}")
    print(f"  Carrier contacts: {len(ccon)}")
    print(f"  Projects:         {len(projects)}")
    print(f"  Uploaded files:   {len(files)} ({sum(len(v) for v in pdf_bytes.values()):,} bytes total)")
    print(f"  Coverages:        {len(coverages)}")
    print(f"  Quotes:           {len(quotes)}")
    print(f"  Activities:       {len(activities)}")
    print(f"  Solicitations:    {len(solicitations)}")
    print(f"  Recommendations:  {len(recs)}")
    print()
    print("Demo pages:")
    print("  /broker/clients   → 3 clients with contacts")
    print("  /broker/projects  → 3 projects (gaps_identified, quotes_received, delivered)")
    print("  /broker/carriers  → 5 carriers with contacts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed broker demo data")
    parser.add_argument("--clean-only", action="store_true", help="Only clean, don't re-seed")
    args = parser.parse_args()
    asyncio.run(seed())
