"""Enrich the Nave Industrial Apodaca Lote 7 project with rich seed data.

Targets: project caf6a4f6-053a-4234-8c0a-8f94503731c9

Layers seeded:
  1. Uploaded Files (7) — contract, existing policies, 5 quote PDFs
  2. Project Coverages (13) — 8 insurance + 4 surety + 1 extra (replaces existing 5)
  3. Carrier Configs (6) — Mapfre, GNP, Chubb, Zurich, Aserta, Dorama
  4. Carrier Quotes (24) — linked to coverages via coverage_id

Usage:
    backend/.venv/bin/python3 backend/scripts/seed_broker_rich.py

Idempotent: deletes existing coverages/quotes/files for this project before inserting.
"""

import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# Path setup — load .env from backend/ directory
# ---------------------------------------------------------------------------
_backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend_dir / "src"))

# Load .env before importing anything from flywheel
_env_file = _backend_dir / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = value

from sqlalchemy import text

from flywheel.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ID = "caf6a4f6-053a-4234-8c0a-8f94503731c9"
NOW = datetime.now(timezone.utc)


def ts(days_ago: int = 0, hours_ago: int = 0) -> str:
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).isoformat()


# ---------------------------------------------------------------------------
# Stable UUIDs for new entities
# ---------------------------------------------------------------------------
# Uploaded files
FILE_MSA = str(uuid4())
FILE_POLIZAS = str(uuid4())
FILE_QUOTE_MAPFRE = str(uuid4())
FILE_QUOTE_GNP = str(uuid4())
FILE_QUOTE_CHUBB = str(uuid4())
FILE_QUOTE_ASERTA = str(uuid4())
FILE_QUOTE_DORAMA = str(uuid4())

ALL_FILE_IDS = [FILE_MSA, FILE_POLIZAS, FILE_QUOTE_MAPFRE, FILE_QUOTE_GNP,
                FILE_QUOTE_CHUBB, FILE_QUOTE_ASERTA, FILE_QUOTE_DORAMA]

# Carrier configs
CARRIER_MAPFRE = str(uuid4())
CARRIER_GNP = str(uuid4())
CARRIER_CHUBB = str(uuid4())
CARRIER_ZURICH = str(uuid4())
CARRIER_ASERTA = str(uuid4())
CARRIER_DORAMA = str(uuid4())

ALL_CARRIER_IDS = [CARRIER_MAPFRE, CARRIER_GNP, CARRIER_CHUBB, CARRIER_ZURICH,
                   CARRIER_ASERTA, CARRIER_DORAMA]

# Coverage IDs (stable so quotes can reference them)
COV_CGL = str(uuid4())
COV_CAR = str(uuid4())
COV_AUTO = str(uuid4())
COV_RT = str(uuid4())
COV_EQUIPO = str(uuid4())
COV_TRANSPORTE = str(uuid4())
COV_CONTAMINACION = str(uuid4())
COV_UMBRELLA = str(uuid4())
COV_CUMPLIMIENTO = str(uuid4())
COV_ANTICIPO = str(uuid4())
COV_VICIOS = str(uuid4())
COV_PAGO = str(uuid4())
COV_RCPROFESIONAL = str(uuid4())


# ===================================================================
# DATA DEFINITIONS
# ===================================================================

def get_uploaded_files(tenant_id):
    def _f(file_id, filename, doc_type, extracted, extra_meta=None):
        meta = {"document_type": doc_type, "project_name": "Nave Industrial Apodaca Lote 7"}
        if extra_meta:
            meta.update(extra_meta)
        return {
            "id": file_id,
            "filename": filename,
            "mimetype": "application/pdf",
            "size_bytes": 24576,  # placeholder
            "storage_path": f"{tenant_id}/{file_id}/{filename}",
            "extracted_text": extracted,
            "metadata": meta,
        }

    return [
        _f(FILE_MSA,
           "MSA-Contrato-Nave-Industrial-Apodaca-Lote-7.pdf", "contract",
           "CONTRATO DE OBRA A PRECIO ALZADO. Partes: Desarrollo Industrial MX, S.A. de C.V. (Propietario) "
           "y Constructora Pacífico del Norte, S.A. de C.V. (Contratista). Proyecto: Nave Industrial Apodaca Lote 7. "
           "Ubicación: Parque Industrial Kalos, Apodaca, Nuevo León. Superficie: 15,000 m². "
           "Valor del contrato: MXN $42,000,000.00 IVA incluido. Plazo: 15 de enero 2025 al 30 de noviembre 2025. "
           "Sección 7 — Requisitos de Seguros: RC General $5M, Todo Riesgo Construcción por valor total del contrato, "
           "RC Auto $1M, Riesgos de Trabajo conforme a ley, Equipo y Maquinaria $3M, Transporte de Materiales $2M, "
           "RC por Contaminación $5M, Umbrella/Exceso RC $10M. "
           "Sección 8 — Fianzas: Cumplimiento 10%, Anticipo 20%, Vicios Ocultos 10%, Pago 10%."),

        _f(FILE_POLIZAS,
           "Polizas-Vigentes-Constructora-Pacifico.pdf", "existing_policies",
           "RESUMEN DE PÓLIZAS VIGENTES. Constructora Pacífico del Norte. "
           "RC General: AXA México, póliza AXA-RCG-2024-8821, límite $2,000,000, vence 15-jun-2025. "
           "RC Auto: AXA México, póliza AXA-AU-2024-5567, límite $500,000, vence 15-jun-2025. "
           "Riesgos de Trabajo: IMSS registro patronal Y60-23456-10-8, vigente. "
           "Sin póliza de Todo Riesgo Construcción. Sin póliza de Equipo. Sin Umbrella. Sin fianzas vigentes.",
           {"status": "current_policies"}),

        _f(FILE_QUOTE_MAPFRE,
           "Quote-Mapfre-2024.pdf", "quote_letter",
           "COTIZACIÓN MAPFRE MÉXICO. Ref: MPF-COT-2024-4521. "
           "RC General: $5,000,000 límite, deducible $20,000, prima $38,500. "
           "Todo Riesgo Construcción: $42,000,000, deducible $50,000, prima $126,000. "
           "RC Auto: $1,000,000, deducible $5,000, prima $8,200. "
           "Riesgos de Trabajo: Estatutario, prima $18,500. "
           "Equipo y Maquinaria: $3,000,000, deducible $15,000, prima $22,800. "
           "Vigencia: 90 días. Total seguros: $214,000.",
           {"carrier": "Mapfre Mexico"}),

        _f(FILE_QUOTE_GNP,
           "Quote-GNP-2024.pdf", "quote_letter",
           "COTIZACIÓN GNP SEGUROS. Ref: GNP-IND-2024-7832. "
           "RC General: $5,000,000, deducible $25,000, prima $42,100. "
           "Todo Riesgo Construcción: $42,000,000, deducible $75,000, prima $138,600. "
           "RC por Contaminación: $5,000,000, deducible $50,000, prima $35,400. "
           "Transporte de Materiales: $2,000,000, deducible $10,000, prima $12,800. "
           "Total: $228,900. Vigencia 60 días.",
           {"carrier": "GNP Seguros"}),

        _f(FILE_QUOTE_CHUBB,
           "Quote-Chubb-2024.pdf", "quote_letter",
           "COTIZACIÓN CHUBB MÉXICO. Ref: CMX-2024-Q-1192. "
           "RC General: $5,000,000, deducible $15,000, prima $36,200. "
           "RC Auto: $1,000,000, deducible $7,500, prima $7,800. "
           "Umbrella/Exceso RC: $10,000,000, SIR $10,000, prima $28,500. "
           "Total: $72,500. Vigencia 90 días.",
           {"carrier": "Chubb Mexico"}),

        _f(FILE_QUOTE_ASERTA,
           "Quote-Aserta-2024.pdf", "quote_letter",
           "COTIZACIÓN AFIANZADORA ASERTA. Ref: ASR-FZ-2024-3301. "
           "Fianza de Cumplimiento: $4,200,000, prima 1.2% = $50,400. "
           "Fianza de Anticipo: $8,400,000, prima 1.5% = $126,000. "
           "Fianza de Vicios Ocultos: $4,200,000, prima 1.0% = $42,000. "
           "Fianza de Pago: $4,200,000, prima 1.0% = $42,000. "
           "Total fianzas: $260,400. Vigencia: por duración del proyecto + 12 meses.",
           {"carrier": "Afianzadora Aserta"}),

        _f(FILE_QUOTE_DORAMA,
           "Quote-Dorama-2024.pdf", "quote_letter",
           "COTIZACIÓN FIANZAS DORAMA. Ref: DRM-2024-FZ-0887. "
           "Fianza de Cumplimiento: $4,200,000, prima 1.0% = $42,000. "
           "Fianza de Anticipo: $8,400,000, prima 1.3% = $109,200. "
           "Fianza de Vicios Ocultos: $4,200,000, prima 0.9% = $37,800. "
           "Fianza de Pago: $4,200,000, prima 0.85% = $35,700. "
           "Total fianzas: $224,700. Vigencia: proyecto + 12 meses.",
           {"carrier": "Fianzas Dorama"}),
    ]


def get_carrier_configs(tenant_id):
    return [
        {
            "id": CARRIER_MAPFRE,
            "carrier_name": "Mapfre Mexico",
            "carrier_type": "insurance",
            "carrier_code": "MAPFRE-MX",
            "submission_method": "portal",
            "portal_url": "https://agentes.mapfre.com.mx",
            "coverage_types": ["general_liability", "builders_risk", "auto", "workers_comp", "equipment", "umbrella"],
            "regions": ["mexico", "latam"],
            "min_project_value": 500000,
            "max_project_value": 200000000,
            "avg_response_days": 3,
            "avg_premium_ratio": 0.0051,
            "total_quotes": 18,
            "total_selected": 7,
            "notes": "Carrier preferido para riesgos de construcción industriales en el noreste. Relación de 8 años. Buenas tarifas en CAR.",
        },
        {
            "id": CARRIER_GNP,
            "carrier_name": "GNP Seguros",
            "carrier_type": "insurance",
            "carrier_code": "GNP-MX",
            "submission_method": "email",
            "coverage_types": ["general_liability", "builders_risk", "pollution", "transit"],
            "regions": ["mexico"],
            "min_project_value": 1000000,
            "max_project_value": 500000000,
            "avg_response_days": 5,
            "avg_premium_ratio": 0.0055,
            "total_quotes": 10,
            "total_selected": 3,
            "notes": "Fuerte en contaminación y transporte. Suscripción más lenta pero cobertura amplia. Contacto: Lic. Ramírez.",
        },
        {
            "id": CARRIER_CHUBB,
            "carrier_name": "Chubb Mexico",
            "carrier_type": "insurance",
            "carrier_code": "CHUBB-MX",
            "submission_method": "email",
            "coverage_types": ["general_liability", "auto", "umbrella", "professional_liability"],
            "regions": ["mexico", "latam", "usa"],
            "min_project_value": 5000000,
            "max_project_value": 500000000,
            "avg_response_days": 5,
            "avg_premium_ratio": 0.0058,
            "total_quotes": 12,
            "total_selected": 4,
            "notes": "Premium carrier. Mejor opción para umbrella y exceso. Deducibles bajos.",
        },
        {
            "id": CARRIER_ZURICH,
            "carrier_name": "Zurich Mexico",
            "carrier_type": "insurance",
            "carrier_code": "ZURICH-MX",
            "submission_method": "email",
            "coverage_types": ["builders_risk", "equipment", "transit", "pollution"],
            "regions": ["mexico", "usa", "latam"],
            "min_project_value": 2000000,
            "max_project_value": 300000000,
            "avg_response_days": 7,
            "avg_premium_ratio": 0.0060,
            "total_quotes": 6,
            "total_selected": 2,
            "notes": "Especialista en CAR y equipo pesado. Proceso de suscripción más largo pero buenos términos.",
        },
        {
            "id": CARRIER_ASERTA,
            "carrier_name": "Afianzadora Aserta",
            "carrier_type": "surety",
            "carrier_code": "ASERTA",
            "submission_method": "email",
            "coverage_types": ["performance_bond", "advance_bond", "hidden_defects_bond", "payment_bond"],
            "regions": ["mexico"],
            "min_project_value": 500000,
            "max_project_value": 500000000,
            "avg_response_days": 4,
            "avg_premium_ratio": 0.012,
            "total_quotes": 14,
            "total_selected": 5,
            "notes": "Afianzadora líder en México. Proceso rápido. Requiere estados financieros auditados y contragarantía.",
        },
        {
            "id": CARRIER_DORAMA,
            "carrier_name": "Fianzas Dorama",
            "carrier_type": "surety",
            "carrier_code": "DORAMA",
            "submission_method": "email",
            "coverage_types": ["performance_bond", "advance_bond", "hidden_defects_bond", "payment_bond"],
            "regions": ["mexico"],
            "min_project_value": 200000,
            "max_project_value": 200000000,
            "avg_response_days": 3,
            "avg_premium_ratio": 0.010,
            "total_quotes": 9,
            "total_selected": 4,
            "notes": "Tarifas competitivas, especialmente en fianzas de anticipo. Buen servicio para constructoras medianas.",
        },
    ]


def get_coverages():
    return [
        # --- 8 Insurance coverages ---
        {
            "id": COV_CGL,
            "coverage_type": "general_liability",
            "category": "insurance",
            "display_name": "Responsabilidad Civil General",
            "language": "es",
            "required_limit": 5000000,
            "required_deductible": 20000,
            "required_terms": "Por ocurrencia, incluyendo operaciones completadas y productos",
            "contract_clause": "Cláusula 7.1 — Seguro de Responsabilidad Civil General",
            "current_limit": 2000000,
            "current_carrier": "AXA México",
            "current_policy_number": "AXA-RCG-2024-8821",
            "current_expiry": "2025-06-15",
            "gap_status": "gap",
            "gap_amount": 3000000,
            "gap_notes": "Póliza actual $2M vs requerido $5M. Necesario incrementar o colocar póliza específica del proyecto.",
            "source_document_id": FILE_MSA,
            "source_page": 14,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "El Contratista deberá mantener vigente durante toda la ejecución de la obra un seguro de "
                "Responsabilidad Civil General con límite mínimo de $5,000,000.00 M.N. por ocurrencia, que cubra "
                "daños a terceros en sus personas y bienes, incluyendo operaciones completadas y responsabilidad "
                "contractual. La póliza deberá nombrar al Propietario como asegurado adicional."
            ),
            "confidence": "high",
        },
        {
            "id": COV_CAR,
            "coverage_type": "builders_risk",
            "category": "insurance",
            "display_name": "Todo Riesgo Construcción (CAR)",
            "language": "es",
            "required_limit": 42000000,
            "required_deductible": 50000,
            "required_terms": "Valor total del contrato, incluyendo materiales en tránsito y en sitio",
            "contract_clause": "Cláusula 7.2 — Seguro Todo Riesgo de Construcción",
            "gap_status": "gap",
            "gap_amount": 42000000,
            "gap_notes": "Sin póliza CAR existente. Se requiere colocación nueva por el valor total del contrato.",
            "source_document_id": FILE_MSA,
            "source_page": 14,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "El Contratista contratará una póliza de Todo Riesgo de Construcción (Contractor's All Risk) por "
                "el valor total del contrato de $42,000,000.00 M.N., cubriendo daños materiales a la obra en "
                "ejecución, materiales almacenados en sitio y en tránsito, equipos instalados y obras provisionales. "
                "Deberá incluir cobertura de remoción de escombros y gastos extraordinarios."
            ),
            "confidence": "high",
        },
        {
            "id": COV_AUTO,
            "coverage_type": "auto_liability",
            "category": "insurance",
            "display_name": "Responsabilidad Civil Automóviles",
            "language": "es",
            "required_limit": 1000000,
            "required_deductible": 5000,
            "required_terms": "Límite combinado único, vehículos propios y arrendados",
            "contract_clause": "Cláusula 7.3 — Seguro de RC Automóviles",
            "current_limit": 500000,
            "current_carrier": "AXA México",
            "current_policy_number": "AXA-AU-2024-5567",
            "current_expiry": "2025-06-15",
            "gap_status": "gap",
            "gap_amount": 500000,
            "gap_notes": "Póliza actual $500K vs requerido $1M. Incremento necesario.",
            "source_document_id": FILE_MSA,
            "source_page": 15,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "Seguro de Responsabilidad Civil por uso de vehículos automotores con límite combinado único "
                "mínimo de $1,000,000.00 M.N., aplicable a todos los vehículos utilizados en relación con la obra, "
                "incluyendo vehículos propios, arrendados y de subcontratistas."
            ),
            "confidence": "high",
        },
        {
            "id": COV_RT,
            "coverage_type": "workers_comp",
            "category": "insurance",
            "display_name": "Riesgos de Trabajo (IMSS)",
            "language": "es",
            "required_terms": "Conforme a la Ley del Seguro Social y Ley Federal del Trabajo",
            "contract_clause": "Cláusula 7.4 — Seguro de Riesgos de Trabajo",
            "current_carrier": "IMSS",
            "current_policy_number": "Y60-23456-10-8",
            "gap_status": "covered",
            "gap_notes": "Registro patronal vigente ante el IMSS. Cumple con obligación estatutaria.",
            "source_document_id": FILE_MSA,
            "source_page": 15,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "El Contratista acreditará estar al corriente en el pago de cuotas obrero-patronales ante el "
                "Instituto Mexicano del Seguro Social y contar con registro patronal vigente para todos los "
                "trabajadores asignados a la obra, conforme a lo dispuesto en la Ley Federal del Trabajo."
            ),
            "confidence": "high",
        },
        {
            "id": COV_EQUIPO,
            "coverage_type": "equipment",
            "category": "insurance",
            "display_name": "Equipo y Maquinaria de Construcción",
            "language": "es",
            "required_limit": 3000000,
            "required_deductible": 15000,
            "required_terms": "Todo riesgo sobre equipo propio y arrendado en sitio",
            "contract_clause": "Cláusula 7.5 — Seguro de Equipo y Maquinaria",
            "gap_status": "gap",
            "gap_amount": 3000000,
            "gap_notes": "Sin cobertura existente para equipo. Requiere colocación nueva.",
            "source_document_id": FILE_MSA,
            "source_page": 15,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "Seguro de equipo y maquinaria de construcción con límite mínimo de $3,000,000.00 M.N. que ampare "
                "daños materiales, robo y avería de maquinaria pesada, grúas, retroexcavadoras y equipo menor "
                "utilizado en la obra, tanto propio como arrendado."
            ),
            "confidence": "high",
        },
        {
            "id": COV_TRANSPORTE,
            "coverage_type": "transit",
            "category": "insurance",
            "display_name": "Transporte de Materiales",
            "language": "es",
            "required_limit": 2000000,
            "required_deductible": 10000,
            "required_terms": "Materiales en tránsito terrestre dentro del territorio nacional",
            "contract_clause": "Cláusula 7.6 — Seguro de Transporte de Materiales",
            "gap_status": "gap",
            "gap_amount": 2000000,
            "gap_notes": "Sin cobertura de transporte existente. Necesaria para acero estructural y prefabricados.",
            "source_document_id": FILE_MSA,
            "source_page": 16,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "Póliza de seguro de transporte de carga terrestre con límite mínimo de $2,000,000.00 M.N. por "
                "embarque, cubriendo materiales de construcción, acero estructural, elementos prefabricados y "
                "equipos durante su traslado desde los puntos de origen hasta el sitio de la obra."
            ),
            "confidence": "high",
        },
        {
            "id": COV_CONTAMINACION,
            "coverage_type": "pollution",
            "category": "insurance",
            "display_name": "RC por Contaminación Ambiental",
            "language": "es",
            "required_limit": 5000000,
            "required_deductible": 50000,
            "required_terms": "Contaminación súbita y gradual durante construcción",
            "contract_clause": "Cláusula 7.7 — Seguro de RC por Contaminación",
            "gap_status": "gap",
            "gap_amount": 5000000,
            "gap_notes": "Sin cobertura. Requerida por proximidad a zona residencial y manejo de solventes/impermeabilizantes.",
            "source_document_id": FILE_MSA,
            "source_page": 16,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "Debido a la proximidad del sitio con zonas habitacionales, el Contratista deberá contar con un "
                "seguro de Responsabilidad Civil por Contaminación Ambiental con límite mínimo de $5,000,000.00 M.N. "
                "que cubra eventos de contaminación súbita y gradual derivados de las actividades de construcción, "
                "incluyendo manejo de químicos, solventes e impermeabilizantes."
            ),
            "confidence": "medium",
        },
        {
            "id": COV_UMBRELLA,
            "coverage_type": "umbrella",
            "category": "insurance",
            "display_name": "Umbrella / Exceso de RC",
            "language": "es",
            "required_limit": 10000000,
            "required_deductible": 10000,
            "required_terms": "Follow-form sobre RC General, Auto y Riesgos de Trabajo",
            "contract_clause": "Cláusula 7.8 — Póliza Umbrella / Exceso de RC",
            "gap_status": "gap",
            "gap_amount": 10000000,
            "gap_notes": "Sin cobertura umbrella existente. Requerida como capa adicional sobre las pólizas base.",
            "source_document_id": FILE_MSA,
            "source_page": 16,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "Póliza de exceso de responsabilidad civil (Umbrella) con límite mínimo de $10,000,000.00 M.N. "
                "en exceso de las coberturas de RC General, RC Automóviles y Riesgos de Trabajo, con forma de "
                "seguimiento (follow-form) y retención autoasegurada (SIR) no mayor a $10,000.00 M.N."
            ),
            "confidence": "medium",
        },

        # --- 4 Surety bonds ---
        {
            "id": COV_CUMPLIMIENTO,
            "coverage_type": "performance_bond",
            "category": "surety",
            "display_name": "Fianza de Cumplimiento",
            "language": "es",
            "required_limit": 4200000,
            "required_terms": "10% del valor del contrato, vigente hasta recepción definitiva",
            "contract_clause": "Cláusula 8.1 — Fianza de Cumplimiento",
            "gap_status": "gap",
            "gap_amount": 4200000,
            "gap_notes": "Fianza no emitida. Requerida antes del inicio de obra.",
            "source_document_id": FILE_MSA,
            "source_page": 17,
            "source_section": "Sección 8 — Fianzas",
            "source_excerpt": (
                "El Contratista entregará al Propietario, previo al inicio de los trabajos, una fianza de "
                "cumplimiento por el 10% del valor total del contrato ($4,200,000.00 M.N.) expedida por "
                "institución afianzadora autorizada, que garantice el fiel y oportuno cumplimiento de todas "
                "las obligaciones derivadas del presente contrato."
            ),
            "confidence": "high",
        },
        {
            "id": COV_ANTICIPO,
            "coverage_type": "advance_bond",
            "category": "surety",
            "display_name": "Fianza de Anticipo",
            "language": "es",
            "required_limit": 8400000,
            "required_terms": "20% del valor del contrato, amortizable conforme a estimaciones",
            "contract_clause": "Cláusula 8.2 — Fianza de Anticipo",
            "gap_status": "gap",
            "gap_amount": 8400000,
            "gap_notes": "Fianza no emitida. Condición para liberación del anticipo del 20%.",
            "source_document_id": FILE_MSA,
            "source_page": 17,
            "source_section": "Sección 8 — Fianzas",
            "source_excerpt": (
                "Para la entrega del anticipo del 20% del valor del contrato ($8,400,000.00 M.N.), el Contratista "
                "deberá presentar fianza de anticipo por el monto total del anticipo. La fianza será amortizada "
                "proporcionalmente conforme se presenten y paguen las estimaciones de obra."
            ),
            "confidence": "high",
        },
        {
            "id": COV_VICIOS,
            "coverage_type": "hidden_defects_bond",
            "category": "surety",
            "display_name": "Fianza de Vicios Ocultos",
            "language": "es",
            "required_limit": 4200000,
            "required_terms": "10% del valor del contrato, vigente 24 meses post-recepción",
            "contract_clause": "Cláusula 8.3 — Fianza de Vicios Ocultos",
            "gap_status": "gap",
            "gap_amount": 4200000,
            "gap_notes": "Fianza requerida al momento de la recepción de la obra. Vigencia 24 meses.",
            "source_document_id": FILE_MSA,
            "source_page": 18,
            "source_section": "Sección 8 — Fianzas",
            "source_excerpt": (
                "Al momento de la recepción de la obra, el Contratista entregará fianza por vicios ocultos "
                "equivalente al 10% del valor del contrato ($4,200,000.00 M.N.) con vigencia de 24 meses "
                "contados a partir de la fecha de recepción, garantizando la reparación de cualquier defecto "
                "de construcción no visible al momento de la entrega."
            ),
            "confidence": "high",
        },
        {
            "id": COV_PAGO,
            "coverage_type": "payment_bond",
            "category": "surety",
            "display_name": "Fianza de Pago a Proveedores",
            "language": "es",
            "required_limit": 4200000,
            "required_terms": "10% del valor del contrato, garantiza pago a subcontratistas y proveedores",
            "contract_clause": "Cláusula 8.4 — Fianza de Pago",
            "gap_status": "gap",
            "gap_amount": 4200000,
            "gap_notes": "Fianza no emitida. Protege a subcontratistas y proveedores de materiales.",
            "source_document_id": FILE_MSA,
            "source_page": 18,
            "source_section": "Sección 8 — Fianzas",
            "source_excerpt": (
                "Fianza de pago por el 10% del valor del contrato ($4,200,000.00 M.N.) que garantice el pago "
                "oportuno a subcontratistas, proveedores de materiales y trabajadores. El Propietario podrá "
                "hacer efectiva esta fianza ante incumplimiento comprobado de pagos por parte del Contratista."
            ),
            "confidence": "high",
        },

        # --- 1 additional insurance (RC Profesional — medium confidence) ---
        {
            "id": COV_RCPROFESIONAL,
            "coverage_type": "professional_liability",
            "category": "insurance",
            "display_name": "RC Profesional (Diseño Estructural)",
            "language": "es",
            "required_limit": 2000000,
            "required_terms": "Aplica si el contratista asume responsabilidad de diseño",
            "contract_clause": "Cláusula 7.9 — Seguro de RC Profesional (condicional)",
            "gap_status": "gap",
            "gap_amount": 2000000,
            "gap_notes": "Cláusula condicional: aplica solo si el contratista realiza diseño estructural. Confirmar con el cliente.",
            "source_document_id": FILE_MSA,
            "source_page": 16,
            "source_section": "Sección 7 — Requisitos de Seguros",
            "source_excerpt": (
                "En caso de que el Contratista asuma responsabilidad total o parcial del diseño estructural, "
                "deberá contar con un seguro de Responsabilidad Civil Profesional con límite mínimo de "
                "$2,000,000.00 M.N. que cubra errores y omisiones en los servicios de ingeniería y diseño."
            ),
            "confidence": "medium",
        },
    ]


def get_quotes():
    """Carrier quotes linked to specific coverages."""
    return [
        # === Mapfre Mexico (5 insurance lines) ===
        {"carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "coverage_id": COV_CGL, "carrier_type": "insurance",
         "premium": 38500, "deductible": 20000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2025-04-15", "status": "received",
         "exclusions": ["Sismo y terremoto", "Asbesto", "RC profesional", "Contaminación gradual"],
         "conditions": ["Asegurado adicional: Desarrollo Industrial MX", "Cesión de derechos de recuperación"],
         "received_at": ts(days_ago=10),
         "source_document_id": FILE_QUOTE_MAPFRE, "source_page": 1,
         "source_excerpt": "RC General: $5,000,000 límite, $20,000 deducible, prima anual $38,500", "confidence": "high"},

        {"carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "coverage_id": COV_CAR, "carrier_type": "insurance",
         "premium": 126000, "deductible": 50000, "limit_amount": 42000000,
         "term_months": 11, "validity_date": "2025-04-15", "status": "received",
         "exclusions": ["Sismo (sublímite $5M, deducible 2%)", "Diseño defectuoso", "Desgaste normal"],
         "conditions": ["Reporte mensual de avance de obra", "Inspección trimestral por aseguradora"],
         "received_at": ts(days_ago=10),
         "source_document_id": FILE_QUOTE_MAPFRE, "source_page": 2,
         "source_excerpt": "CAR: $42,000,000 límite, $50,000 deducible general, prima $126,000", "confidence": "high"},

        {"carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "coverage_id": COV_AUTO, "carrier_type": "insurance",
         "premium": 8200, "deductible": 5000, "limit_amount": 1000000,
         "term_months": 12, "validity_date": "2025-04-15", "status": "received",
         "received_at": ts(days_ago=10),
         "source_document_id": FILE_QUOTE_MAPFRE, "confidence": "high"},

        {"carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "coverage_id": COV_RT, "carrier_type": "insurance",
         "premium": 18500, "term_months": 12,
         "validity_date": "2025-04-15", "status": "received",
         "conditions": ["Complemento a obligaciones IMSS", "Cobertura de accidentes en sitio de obra"],
         "received_at": ts(days_ago=10),
         "source_document_id": FILE_QUOTE_MAPFRE, "confidence": "high"},

        {"carrier_name": "Mapfre Mexico", "carrier_config_id": CARRIER_MAPFRE,
         "coverage_id": COV_EQUIPO, "carrier_type": "insurance",
         "premium": 22800, "deductible": 15000, "limit_amount": 3000000,
         "term_months": 11, "validity_date": "2025-04-15", "status": "received",
         "exclusions": ["Desgaste normal", "Falta de mantenimiento"],
         "received_at": ts(days_ago=10),
         "source_document_id": FILE_QUOTE_MAPFRE, "confidence": "high"},

        # === GNP Seguros (4 lines) ===
        {"carrier_name": "GNP Seguros", "carrier_config_id": CARRIER_GNP,
         "coverage_id": COV_CGL, "carrier_type": "insurance",
         "premium": 42100, "deductible": 25000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2025-04-01", "status": "received",
         "exclusions": ["Sismo", "Contaminación gradual", "RC profesional", "Asbesto", "Hundimiento"],
         "conditions": ["Asegurado adicional requerido", "Renuncia de subrogación incluida"],
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_GNP, "source_page": 1,
         "source_excerpt": "RC General: $5,000,000 por ocurrencia, deducible $25,000, prima $42,100", "confidence": "high"},

        {"carrier_name": "GNP Seguros", "carrier_config_id": CARRIER_GNP,
         "coverage_id": COV_CAR, "carrier_type": "insurance",
         "premium": 138600, "deductible": 75000, "limit_amount": 42000000,
         "term_months": 11, "validity_date": "2025-04-01", "status": "received",
         "exclusions": ["Sismo (no incluido)", "Diseño defectuoso", "Penalidades contractuales"],
         "conditions": ["Inspección inicial obligatoria", "Reporte de avance mensual"],
         "has_critical_exclusion": True,
         "critical_exclusion_detail": "Deducible $75K excede requerimiento contractual de $50K; sismo no incluido",
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_GNP, "source_page": 2,
         "source_excerpt": "CAR: $42,000,000, deducible $75,000, prima $138,600. NOTA: Sismo excluido.", "confidence": "high"},

        {"carrier_name": "GNP Seguros", "carrier_config_id": CARRIER_GNP,
         "coverage_id": COV_CONTAMINACION, "carrier_type": "insurance",
         "premium": 35400, "deductible": 50000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2025-04-01", "status": "received",
         "exclusions": ["Contaminación preexistente", "Multas y sanciones gubernamentales"],
         "conditions": ["Plan de manejo ambiental aprobado", "Notificación inmediata de incidente"],
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_GNP, "source_page": 3,
         "source_excerpt": "RC Contaminación: $5,000,000, deducible $50,000, prima $35,400", "confidence": "high"},

        {"carrier_name": "GNP Seguros", "carrier_config_id": CARRIER_GNP,
         "coverage_id": COV_TRANSPORTE, "carrier_type": "insurance",
         "premium": 12800, "deductible": 10000, "limit_amount": 2000000,
         "term_months": 12, "validity_date": "2025-04-01", "status": "received",
         "conditions": ["Cobertura puerta a puerta", "Incluye carga y descarga"],
         "received_at": ts(days_ago=8),
         "source_document_id": FILE_QUOTE_GNP, "confidence": "high"},

        # === Chubb Mexico (3 lines) ===
        {"carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "coverage_id": COV_CGL, "carrier_type": "insurance",
         "premium": 36200, "deductible": 15000, "limit_amount": 5000000,
         "term_months": 12, "validity_date": "2025-04-20", "status": "received",
         "exclusions": ["Sismo", "Asbesto", "Contaminación", "RC profesional"],
         "conditions": ["Asegurado adicional: Desarrollo Industrial MX", "Primary & non-contributory", "Renuncia de subrogación"],
         "received_at": ts(days_ago=7),
         "source_document_id": FILE_QUOTE_CHUBB, "source_page": 1,
         "source_excerpt": "RC General: $5,000,000 ocurrencia, $15,000 deducible, prima $36,200. Mejor deducible del mercado.", "confidence": "high"},

        {"carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "coverage_id": COV_AUTO, "carrier_type": "insurance",
         "premium": 7800, "deductible": 7500, "limit_amount": 1000000,
         "term_months": 12, "validity_date": "2025-04-20", "status": "received",
         "received_at": ts(days_ago=7),
         "source_document_id": FILE_QUOTE_CHUBB, "confidence": "high"},

        {"carrier_name": "Chubb Mexico", "carrier_config_id": CARRIER_CHUBB,
         "coverage_id": COV_UMBRELLA, "carrier_type": "insurance",
         "premium": 28500, "deductible": 10000, "limit_amount": 10000000,
         "term_months": 12, "validity_date": "2025-04-20", "status": "received",
         "exclusions": ["Contaminación", "RC profesional", "Cyber"],
         "conditions": ["Follow-form sobre RC General y Auto", "SIR $10,000"],
         "received_at": ts(days_ago=7),
         "source_document_id": FILE_QUOTE_CHUBB, "source_page": 2,
         "source_excerpt": "Umbrella: $10,000,000 en exceso, SIR $10,000, prima $28,500", "confidence": "high"},

        # === Zurich Mexico (3 lines — no CGL, focused on specialty) ===
        # (Zurich not quoting this project — they focus on larger risks)

        # === Afianzadora Aserta (4 surety bonds) ===
        {"carrier_name": "Afianzadora Aserta", "carrier_config_id": CARRIER_ASERTA,
         "coverage_id": COV_CUMPLIMIENTO, "carrier_type": "surety",
         "premium": 50400, "limit_amount": 4200000,
         "term_months": 12, "validity_date": "2025-04-10", "status": "received",
         "conditions": ["Contragarantía hipotecaria o prendaria", "Estados financieros auditados 2023-2024",
                        "Acta constitutiva y poderes notariales"],
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_ASERTA, "source_page": 1,
         "source_excerpt": "Fianza de Cumplimiento: $4,200,000 (10% del contrato), prima 1.2% = $50,400", "confidence": "high"},

        {"carrier_name": "Afianzadora Aserta", "carrier_config_id": CARRIER_ASERTA,
         "coverage_id": COV_ANTICIPO, "carrier_type": "surety",
         "premium": 126000, "limit_amount": 8400000,
         "term_months": 11, "validity_date": "2025-04-10", "status": "received",
         "conditions": ["Comprobante de depósito del anticipo", "Calendario de amortización aprobado"],
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_ASERTA, "source_page": 1,
         "source_excerpt": "Fianza de Anticipo: $8,400,000 (20% del contrato), prima 1.5% = $126,000", "confidence": "high"},

        {"carrier_name": "Afianzadora Aserta", "carrier_config_id": CARRIER_ASERTA,
         "coverage_id": COV_VICIOS, "carrier_type": "surety",
         "premium": 42000, "limit_amount": 4200000,
         "term_months": 24, "validity_date": "2025-04-10", "status": "received",
         "conditions": ["Vigencia 24 meses post-recepción", "Acta de recepción de obra firmada"],
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_ASERTA, "source_page": 2,
         "source_excerpt": "Fianza de Vicios Ocultos: $4,200,000, prima 1.0% = $42,000, vigencia 24 meses", "confidence": "high"},

        {"carrier_name": "Afianzadora Aserta", "carrier_config_id": CARRIER_ASERTA,
         "coverage_id": COV_PAGO, "carrier_type": "surety",
         "premium": 42000, "limit_amount": 4200000,
         "term_months": 12, "validity_date": "2025-04-10", "status": "received",
         "conditions": ["Lista de subcontratistas y proveedores principales"],
         "received_at": ts(days_ago=12),
         "source_document_id": FILE_QUOTE_ASERTA, "source_page": 2,
         "source_excerpt": "Fianza de Pago: $4,200,000, prima 1.0% = $42,000", "confidence": "high"},

        # === Fianzas Dorama (4 surety bonds) ===
        {"carrier_name": "Fianzas Dorama", "carrier_config_id": CARRIER_DORAMA,
         "coverage_id": COV_CUMPLIMIENTO, "carrier_type": "surety",
         "premium": 42000, "limit_amount": 4200000,
         "term_months": 12, "validity_date": "2025-04-08", "status": "received",
         "conditions": ["Contragarantía: pagaré notarial", "Estados financieros últimos 2 ejercicios",
                        "Fianza expedida en 48 hrs tras documentación completa"],
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_DORAMA, "source_page": 1,
         "source_excerpt": "Fianza de Cumplimiento: $4,200,000, prima 1.0% = $42,000", "confidence": "high"},

        {"carrier_name": "Fianzas Dorama", "carrier_config_id": CARRIER_DORAMA,
         "coverage_id": COV_ANTICIPO, "carrier_type": "surety",
         "premium": 109200, "limit_amount": 8400000,
         "term_months": 11, "validity_date": "2025-04-08", "status": "received",
         "conditions": ["Amortización proporcional a estimaciones", "Documentación completa requerida"],
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_DORAMA, "source_page": 1,
         "source_excerpt": "Fianza de Anticipo: $8,400,000, prima 1.3% = $109,200", "confidence": "high"},

        {"carrier_name": "Fianzas Dorama", "carrier_config_id": CARRIER_DORAMA,
         "coverage_id": COV_VICIOS, "carrier_type": "surety",
         "premium": 37800, "limit_amount": 4200000,
         "term_months": 24, "validity_date": "2025-04-08", "status": "received",
         "conditions": ["Vigencia 24 meses", "Aplica al momento de recepción de obra"],
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_DORAMA, "source_page": 2,
         "source_excerpt": "Fianza de Vicios Ocultos: $4,200,000, prima 0.9% = $37,800", "confidence": "high"},

        {"carrier_name": "Fianzas Dorama", "carrier_config_id": CARRIER_DORAMA,
         "coverage_id": COV_PAGO, "carrier_type": "surety",
         "premium": 35700, "limit_amount": 4200000,
         "term_months": 12, "validity_date": "2025-04-08", "status": "received",
         "conditions": ["Cubre pago a proveedores y subcontratistas"],
         "received_at": ts(days_ago=14),
         "source_document_id": FILE_QUOTE_DORAMA, "source_page": 2,
         "source_excerpt": "Fianza de Pago: $4,200,000, prima 0.85% = $35,700", "confidence": "high"},
    ]


# ===================================================================
# DATABASE OPERATIONS
# ===================================================================

async def insert_row(db, table: str, data: dict):
    """Insert one row with per-statement commit (PgBouncer workaround)."""
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
            cast_placeholders.append(f":{k}")
            params[k] = date.fromisoformat(v)
        elif isinstance(v, str) and "T" in v and v[:4].isdigit() and ("+" in v[10:] or v.endswith("Z")):
            cast_placeholders.append(f":{k}")
            params[k] = datetime.fromisoformat(v)
        else:
            cast_placeholders.append(f":{k}")
            params[k] = v

    cols = ", ".join(col_list)
    vals = ", ".join(cast_placeholders)
    await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), params)
    await db.commit()


async def seed():
    factory = get_session_factory()

    print("=" * 60)
    print("BROKER RICH SEED — Nave Industrial Apodaca Lote 7")
    print("=" * 60)
    print(f"Project: {PROJECT_ID}")
    print()

    async with factory() as db:
        # --- Fetch tenant_id from the existing project ---
        result = await db.execute(
            text("SELECT tenant_id FROM broker_projects WHERE id = :pid"),
            {"pid": PROJECT_ID},
        )
        row = result.fetchone()
        if not row:
            print(f"ERROR: Project {PROJECT_ID} not found in broker_projects!")
            return
        tenant_id = str(row[0])
        print(f"Tenant: {tenant_id}\n")

        # --- Clean existing data for this project ---
        print("Cleaning existing data for this project...")

        # Delete quotes for this project
        r = await db.execute(
            text("DELETE FROM carrier_quotes WHERE broker_project_id = :pid"),
            {"pid": PROJECT_ID},
        )
        await db.commit()
        print(f"  carrier_quotes: {r.rowcount} deleted")

        # Delete coverages for this project
        r = await db.execute(
            text("DELETE FROM project_coverages WHERE broker_project_id = :pid"),
            {"pid": PROJECT_ID},
        )
        await db.commit()
        print(f"  project_coverages: {r.rowcount} deleted")

        # Delete uploaded files we'll re-create
        for fid in ALL_FILE_IDS:
            await db.execute(
                text("DELETE FROM uploaded_files WHERE id = :id"),
                {"id": fid},
            )
            await db.commit()

        # Delete carrier configs we'll re-create (avoid duplication)
        for cid in ALL_CARRIER_IDS:
            await db.execute(
                text("DELETE FROM carrier_configs WHERE id = :id"),
                {"id": cid},
            )
            await db.commit()

        # Also delete any existing carriers with the same names for this tenant
        for name in ["Mapfre Mexico", "GNP Seguros", "Chubb Mexico", "Zurich Mexico",
                      "Afianzadora Aserta", "Fianzas Dorama"]:
            await db.execute(
                text("DELETE FROM carrier_quotes WHERE carrier_name = :cn AND broker_project_id = :pid"),
                {"cn": name, "pid": PROJECT_ID},
            )
            await db.commit()

        print()

        # --- Insert uploaded files ---
        print("Inserting uploaded files...")
        files = get_uploaded_files(tenant_id)
        for f in files:
            f["tenant_id"] = tenant_id
            await insert_row(db, "uploaded_files", f)
        print(f"  {len(files)} files inserted\n")

        # --- Insert carrier configs (upsert-like: skip if name already exists) ---
        print("Inserting carrier configs...")
        carriers = get_carrier_configs(tenant_id)
        carrier_count = 0
        for c in carriers:
            # Check if carrier name already exists for this tenant
            existing = await db.execute(
                text("SELECT id FROM carrier_configs WHERE tenant_id = :tid AND carrier_name = :cn AND carrier_type = :ct"),
                {"tid": tenant_id, "cn": c["carrier_name"], "ct": c["carrier_type"]},
            )
            existing_row = existing.fetchone()
            if existing_row:
                # Update the ID reference so quotes point to the right carrier
                old_id = c["id"]
                new_id = str(existing_row[0])
                # Remap the global variable
                if c["carrier_name"] == "Mapfre Mexico":
                    globals()["CARRIER_MAPFRE_ACTUAL"] = new_id
                print(f"  {c['carrier_name']} ({c['carrier_type']}) already exists — using existing id {new_id[:8]}...")
                # Update the carrier config IDs in the quote data
                _remap_carrier_id(old_id, new_id)
            else:
                c["tenant_id"] = tenant_id
                await insert_row(db, "carrier_configs", c)
                carrier_count += 1
                print(f"  {c['carrier_name']} ({c['carrier_type']}) inserted")
        print(f"  {carrier_count} new carriers inserted\n")

        # --- Insert coverages ---
        print("Inserting project coverages...")
        coverages = get_coverages()
        for c in coverages:
            c["tenant_id"] = tenant_id
            c["broker_project_id"] = PROJECT_ID
            await insert_row(db, "project_coverages", c)
        print(f"  {len(coverages)} coverages inserted\n")

        # --- Insert quotes ---
        print("Inserting carrier quotes...")
        quotes = get_quotes()
        for q in quotes:
            q["id"] = str(uuid4())
            q["tenant_id"] = tenant_id
            q["broker_project_id"] = PROJECT_ID
            await insert_row(db, "carrier_quotes", q)
        print(f"  {len(quotes)} quotes inserted\n")

        # --- Update project status to reflect rich data ---
        await db.execute(
            text("UPDATE broker_projects SET status = 'quotes_partial', analysis_status = 'completed' WHERE id = :pid"),
            {"pid": PROJECT_ID},
        )
        await db.commit()
        print("Updated project status to 'quotes_partial'\n")

        # --- Verification ---
        print("=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        r = await db.execute(
            text("SELECT COUNT(*) FROM project_coverages WHERE broker_project_id = :pid"),
            {"pid": PROJECT_ID},
        )
        cov_count = r.scalar()
        print(f"  Coverages:      {cov_count}")

        r = await db.execute(
            text("SELECT COUNT(*) FROM carrier_quotes WHERE broker_project_id = :pid"),
            {"pid": PROJECT_ID},
        )
        quote_count = r.scalar()
        print(f"  Quotes:         {quote_count}")

        r = await db.execute(
            text("SELECT COUNT(*) FROM carrier_quotes WHERE broker_project_id = :pid AND coverage_id IS NOT NULL"),
            {"pid": PROJECT_ID},
        )
        linked_count = r.scalar()
        print(f"  Quotes w/ coverage_id: {linked_count}")

        r = await db.execute(
            text("SELECT COUNT(*) FROM uploaded_files WHERE id = ANY(:ids)"),
            {"ids": ALL_FILE_IDS},
        )
        file_count = r.scalar()
        print(f"  Uploaded files: {file_count}")

        r = await db.execute(
            text("SELECT COUNT(*) FROM project_coverages WHERE broker_project_id = :pid AND source_excerpt IS NOT NULL AND source_excerpt != ''"),
            {"pid": PROJECT_ID},
        )
        excerpt_count = r.scalar()
        print(f"  Coverages with source_excerpt: {excerpt_count}")

        r = await db.execute(
            text("SELECT coverage_type, display_name, gap_status, required_limit, current_limit FROM project_coverages WHERE broker_project_id = :pid ORDER BY coverage_type"),
            {"pid": PROJECT_ID},
        )
        print(f"\n  Coverage details:")
        for row in r.fetchall():
            ctype, dname, gap, req_limit, cur_limit = row
            req_str = f"${req_limit:,.0f}" if req_limit else "statutory"
            cur_str = f"${cur_limit:,.0f}" if cur_limit else "—"
            print(f"    {dname:45s} | {gap:15s} | req: {req_str:>15s} | cur: {cur_str:>12s}")

    print("\nSeed complete!")


# Carrier ID remapping for existing carriers
_carrier_remap = {}

def _remap_carrier_id(old_id, new_id):
    _carrier_remap[old_id] = new_id


# Patch get_quotes to use remapped IDs
_original_get_quotes = get_quotes

def get_quotes_with_remap():
    quotes = _original_get_quotes()
    for q in quotes:
        cid = q.get("carrier_config_id")
        if cid in _carrier_remap:
            q["carrier_config_id"] = _carrier_remap[cid]
    return quotes

# Override
get_quotes = get_quotes_with_remap


if __name__ == "__main__":
    asyncio.run(seed())
