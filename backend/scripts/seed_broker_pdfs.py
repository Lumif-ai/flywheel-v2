"""PDF generators for broker demo seed data.

Generates 19 realistic insurance/construction documents:
  - 3 MSA / Construction Contracts (one per project)
  - 2 Bond Schedules (Regio surety requirements, Pacific active bonds)
  - 3 COIs (one current per project, one final for delivered)
  - 2 Policy Declarations pages
  - 9 Quote Letters (multiple carriers per project)

All documents use reportlab with realistic formatting, tables, and content.
"""

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DARK_BLUE = colors.HexColor("#2B3A4A")
NAVY = colors.HexColor("#003366")
DEEP_BLUE = colors.HexColor("#1A5276")
ACCENT = colors.HexColor("#E94D35")


def _build_pdf(story_fn) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = story_fn(styles)
    doc.build(story)
    return buf.getvalue()


def _header_table(data, col_widths, header_color=DARK_BLUE, font_size=8):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


# ===================================================================
# 1. MSA / CONSTRUCTION CONTRACTS
# ===================================================================

def generate_msa_regio() -> bytes:
    """MSA: Constructora Regio ↔ Desarrollo Industrial — Parque Industrial Ciénega Phase II."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=16, spaceAfter=12)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("MASTER SERVICE AGREEMENT", title))
        el.append(Paragraph("Construction & Engineering Services", s["Heading3"]))
        el.append(Spacer(1, 12))
        el.append(Paragraph("<b>Date:</b> January 15, 2026 &nbsp;&nbsp; <b>Agreement No:</b> MSA-2026-0147", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("PARTIES", h2))
        el.append(Paragraph(
            "<b>Owner:</b> Desarrollo Industrial MX, S.A. de C.V., "
            "Av. Constitución 1500, Monterrey, Nuevo León, México, C.P. 64000.", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "<b>Contractor:</b> Constructora Regio, S.A. de C.V., "
            "Blvd. Díaz Ordaz 500, San Pedro Garza García, Nuevo León, C.P. 66215.", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("1. SCOPE OF WORK", h2))
        el.append(Paragraph(
            "Contractor shall furnish all labor, materials, equipment, and services for the "
            "construction of Parque Industrial Ciénega Phase II — 12 warehouse units, admin "
            "building, and shared infrastructure. Total contract value: <b>MXN $185,000,000</b>.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("2. PROJECT TIMELINE", h2))
        el.append(Paragraph(
            "Commencement: March 1, 2026. Substantial Completion: February 28, 2027. "
            "Final Completion: April 30, 2027. Liquidated damages: MXN $150,000/calendar day.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("3. INSURANCE REQUIREMENTS", h2))
        el.append(Paragraph("Contractor shall procure and maintain the following minimum coverages:", b))
        el.append(Spacer(1, 4))
        el.append(_header_table([
            ["Coverage Type", "Minimum Limit", "Additional Requirements"],
            ["Commercial General Liability", "$5,000,000 per occurrence", "Owner as Additional Insured"],
            ["Commercial Auto Liability", "$2,000,000 CSL", "Hired & non-owned included"],
            ["Workers' Compensation", "Statutory limits", "Waiver of subrogation"],
            ["Umbrella / Excess Liability", "$10,000,000 per occurrence", "Follow-form over CGL, Auto, WC"],
            ["Builders Risk", "Full replacement value", "Owner and Contractor named"],
        ], [2.2 * inch, 1.8 * inch, 2.5 * inch]))
        el.append(Spacer(1, 12))

        el.append(Paragraph("4. SURETY BOND REQUIREMENTS", h2))
        el.append(Paragraph("Contractor shall provide bonds from a surety rated A- or better (A.M. Best):", b))
        el.append(Spacer(1, 4))
        el.append(_header_table([
            ["Bond Type", "Amount", "Duration"],
            ["Performance Bond", "100% of contract ($185M MXN)", "Through Final Completion + 12mo warranty"],
            ["Payment Bond", "100% of contract ($185M MXN)", "Through Final Completion"],
        ], [2.0 * inch, 2.5 * inch, 2.2 * inch]))
        el.append(Spacer(1, 12))

        el.append(Paragraph("5. ADDITIONAL INSURED & SUBROGATION", h2))
        el.append(Paragraph(
            "All policies (except WC) shall name Owner as Additional Insured. "
            "Both parties waive subrogation rights for losses covered by required insurance. "
            "Certificates due 10 business days before Commencement.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("6. INDEMNIFICATION", h2))
        el.append(Paragraph(
            "Contractor shall defend, indemnify, and hold harmless Owner from all claims arising "
            "from Contractor's negligent acts, errors, or omissions.", b))
        return el
    return _build_pdf(story)


def generate_msa_pacific() -> bytes:
    """Contract: Pacific Builders — Harbor View Tower Renovation."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=16, spaceAfter=12)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("CONSTRUCTION CONTRACT", title))
        el.append(Paragraph("Harbor View Tower — Seismic Retrofit & Renovation", s["Heading3"]))
        el.append(Spacer(1, 12))
        el.append(Paragraph("<b>Date:</b> April 20, 2025 &nbsp;&nbsp; <b>Contract No:</b> HVT-2025-001", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("PARTIES", h2))
        el.append(Paragraph(
            "<b>Owner:</b> Harbor View Properties LLC, 1200 Ocean Blvd, Long Beach, CA 90802.", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "<b>Contractor:</b> Pacific Builders LLC, 4521 Harbor Blvd, Suite 300, Long Beach, CA 90802.", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("1. SCOPE OF WORK", h2))
        el.append(Paragraph(
            "Seismic retrofit and interior renovation of 18-story mixed-use tower. Includes structural "
            "reinforcement, elevator modernization, full MEP upgrade, and tenant improvements. "
            "Contract value: <b>$8,200,000 USD</b>.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("2. INSURANCE REQUIREMENTS", h2))
        el.append(_header_table([
            ["Coverage", "Limit", "Requirements"],
            ["CGL", "$5,000,000 per occurrence", "Additional Insured, completed operations"],
            ["Auto Liability", "$2,000,000 CSL", "All owned, hired, non-owned"],
            ["Workers' Comp", "Statutory (CA)", "Waiver of subrogation"],
            ["Umbrella", "$5,000,000", "Follow-form over CGL, Auto, WC"],
            ["Builders Risk", "$8,200,000 (full value)", "All-risk, including earthquake"],
            ["Professional Liability", "$2,000,000", "If design-build services provided"],
        ], [1.8 * inch, 1.8 * inch, 2.8 * inch]))
        el.append(Spacer(1, 12))

        el.append(Paragraph("3. SURETY REQUIREMENTS", h2))
        el.append(_header_table([
            ["Bond", "Amount", "Notes"],
            ["Performance Bond", "$8,200,000 (100%)", "A.M. Best A- or better"],
            ["Payment Bond", "$8,200,000 (100%)", "Per CA Civil Code §9550"],
            ["Maintenance Bond", "10% of contract ($820,000)", "2 years post substantial completion"],
        ], [2.0 * inch, 2.0 * inch, 2.5 * inch]))
        el.append(Spacer(1, 12))

        el.append(Paragraph("4. SPECIAL CONDITIONS", h2))
        el.append(Paragraph(
            "Given the seismic retrofit scope, Builders Risk policy must explicitly include "
            "earthquake coverage. Contractor to carry Pollution Liability if hazmat encountered "
            "during demolition. Owner requires 30 days advance notice of cancellation on all policies.", b))
        return el
    return _build_pdf(story)


def generate_msa_desarrollo() -> bytes:
    """Contract: Desarrollo Industrial — Nave Industrial Apodaca Lote 7."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=16, spaceAfter=12)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("CONTRATO DE OBRA", title))
        el.append(Paragraph("Nave Industrial Apodaca — Lote 7", s["Heading3"]))
        el.append(Spacer(1, 12))
        el.append(Paragraph("<b>Fecha:</b> December 10, 2024 &nbsp;&nbsp; <b>Contrato No:</b> DIM-NAV-2024-007", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("PARTES", h2))
        el.append(Paragraph(
            "<b>Propietario:</b> Desarrollo Industrial MX, S.A. de C.V., "
            "Av. Constitución 1500, Monterrey, N.L.", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "<b>Contratista:</b> Constructora del Norte, S.A. de C.V., "
            "Av. Industrias 2300, Apodaca, N.L.", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("1. ALCANCE", h2))
        el.append(Paragraph(
            "Construction of a 15,000 sqm industrial warehouse with loading docks, fire suppression, "
            "and office mezzanine. For lease to tier-1 automotive supplier. "
            "Valor del contrato: <b>MXN $42,000,000</b>.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("2. REQUISITOS DE SEGURO", h2))
        el.append(_header_table([
            ["Cobertura", "Límite Mínimo", "Requisitos"],
            ["Responsabilidad Civil General", "$3,000,000 por evento", "Asegurado adicional: Propietario"],
            ["Auto", "$1,000,000 CSL", "Vehículos propios y rentados"],
            ["Riesgos de Trabajo", "Límites de ley", "Conforme a LFT"],
            ["Todo Riesgo Construcción", "Valor total del contrato", "Nombrar a ambas partes"],
        ], [2.2 * inch, 1.8 * inch, 2.5 * inch]))
        el.append(Spacer(1, 12))

        el.append(Paragraph("3. FIANZAS", h2))
        el.append(_header_table([
            ["Tipo", "Monto", "Vigencia"],
            ["Fianza de Cumplimiento", "100% ($42M MXN)", "Hasta entrega final + 12 meses"],
            ["Fianza de Pago", "100% ($42M MXN)", "Hasta entrega final"],
        ], [2.0 * inch, 2.0 * inch, 2.5 * inch]))
        return el
    return _build_pdf(story)


# ===================================================================
# 2. BOND SCHEDULES
# ===================================================================

def generate_bond_schedule_regio() -> bytes:
    """Bond Schedule: Constructora Regio — required bonds for Ciénega project."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=16, spaceAfter=12)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("SURETY BOND REQUIREMENTS", title))
        el.append(Paragraph("Constructora Regio, S.A. de C.V. — Ciénega Phase II", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Prepared:</b> January 20, 2026 &nbsp;&nbsp; <b>By:</b> Lumif.ai Insurance Brokers", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("REQUIRED BONDS (PER MSA-2026-0147)", h2))
        el.append(_header_table([
            ["Bond Type", "Required Amount", "Surety Rating", "Duration", "Status"],
            ["Performance Bond", "MXN $185,000,000", "A.M. Best A-", "Final Completion + 12mo", "NOT PLACED"],
            ["Payment Bond", "MXN $185,000,000", "A.M. Best A-", "Final Completion", "NOT PLACED"],
        ], [1.3 * inch, 1.3 * inch, 1.0 * inch, 1.5 * inch, 1.0 * inch], DEEP_BLUE))
        el.append(Spacer(1, 12))

        el.append(Paragraph("CONTRACTOR BONDING HISTORY", h2))
        el.append(_header_table([
            ["Prior Project", "Bond Type", "Amount", "Surety", "Outcome"],
            ["Parque Ciénega Phase I", "Performance", "MXN $120M", "Mapfre Mexico", "Completed — no claims"],
            ["Parque Ciénega Phase I", "Payment", "MXN $120M", "Mapfre Mexico", "Completed — no claims"],
            ["Warehouse Park Saltillo", "Performance", "MXN $75M", "Chubb Mexico", "Completed — no claims"],
            ["Office Complex MTY", "Performance", "MXN $45M", "Mapfre Mexico", "Completed — no claims"],
        ], [1.5 * inch, 1.0 * inch, 1.0 * inch, 1.2 * inch, 1.5 * inch], DEEP_BLUE))
        el.append(Spacer(1, 12))

        el.append(Paragraph("FINANCIAL SUMMARY", h2))
        el.append(Paragraph(
            "Constructora Regio has a clean bonding history with MXN $260M in completed bonded work. "
            "Current work-in-progress: MXN $0 (Phase I completed). Requesting MXN $370M aggregate "
            "for Phase II (Performance + Payment). Financial statements attached separately.", b))
        el.append(Spacer(1, 8))
        el.append(Paragraph(
            "<b>Recommended sureties for solicitation:</b> Mapfre Mexico (prior relationship), "
            "Chubb Mexico (prior relationship), Zurich (new market).", b))
        return el
    return _build_pdf(story)


def generate_bond_schedule_pacific() -> bytes:
    """Bond Schedule: Pacific Builders — active bond portfolio + gaps."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=16, spaceAfter=12)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("SURETY BOND SCHEDULE", title))
        el.append(Paragraph("Pacific Builders LLC — Active Bond Portfolio", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Prepared:</b> February 10, 2026 &nbsp;&nbsp; <b>Surety:</b> Zurich North America (A+, XV)", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("CURRENT BONDS IN FORCE", h2))
        el.append(_header_table([
            ["Bond Type", "Project", "Amount", "Effective", "Expiry", "Status"],
            ["Performance Bond", "Harbor View Tower", "$8,200,000", "2025-06-01", "2027-06-01", "Active"],
            ["Payment Bond", "Harbor View Tower", "$8,200,000", "2025-06-01", "2027-06-01", "Active"],
            ["Performance Bond", "Westside Commons", "$4,500,000", "2025-09-15", "2026-12-15", "Active"],
            ["Payment Bond", "Westside Commons", "$4,500,000", "2025-09-15", "2026-12-15", "Active"],
        ], [1.2 * inch, 1.3 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch, 0.7 * inch], DEEP_BLUE, 7.5))
        el.append(Spacer(1, 12))

        el.append(Paragraph("AGGREGATE BONDING CAPACITY", h2))
        el.append(_header_table([
            ["Metric", "Amount"],
            ["Single Bond Limit", "$15,000,000"],
            ["Aggregate Limit", "$35,000,000"],
            ["Currently Committed", "$25,400,000"],
            ["Available Capacity", "$9,600,000"],
        ], [2.5 * inch, 2.0 * inch], DEEP_BLUE, 9))
        el.append(Spacer(1, 12))

        el.append(Paragraph("GAP ANALYSIS", h2))
        el.append(Paragraph(
            "• <b>Maintenance Bond:</b> Harbor View Tower contract requires 2-year maintenance bond "
            "upon substantial completion. Estimated: $820,000 (10% of contract). NOT PLACED.", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "• <b>Bid Bond:</b> Pre-qualified for Oceanside Civic Center bid (March 2026, est. $12M). "
            "Bid bond at 5% required. NOT PLACED.", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(
            "• <b>Subdivision Bond:</b> Westside Commons may require subdivision improvement bond "
            "per City of Long Beach municipal code. Amount TBD.", b))
        return el
    return _build_pdf(story)


# ===================================================================
# 3. CERTIFICATES OF INSURANCE (COI)
# ===================================================================

def generate_coi_regio() -> bytes:
    """COI: Constructora Regio — current coverage (pre-Ciénega Phase II)."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        small = ParagraphStyle("Small", parent=b, fontSize=7.5)
        el = []

        el.append(Paragraph("CERTIFICATE OF INSURANCE", title))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Certificate Holder:</b> Desarrollo Industrial MX, S.A. de C.V.", b))
        el.append(Paragraph("<b>Insured:</b> Constructora Regio, S.A. de C.V.", b))
        el.append(Paragraph("<b>Date Issued:</b> November 15, 2025", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph(
            "This certificate is issued as a matter of information only and confers no rights upon "
            "the certificate holder. This certificate does not amend, extend, or alter the coverage "
            "afforded by the policies listed below.", small))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Coverage", "Carrier", "Policy No.", "Limit", "Effective", "Expiry"],
            ["CGL", "Mapfre Mexico", "MPF-RC-2025-0998", "$3,000,000", "2025-06-01", "2026-06-01"],
            ["Auto", "AXA Mexico", "AXA-AU-2025-0456", "$1,000,000", "2025-06-01", "2026-06-01"],
            ["Workers' Comp", "AXA Mexico", "AXA-RT-2025-0457", "Statutory", "2025-06-01", "2026-06-01"],
            ["Umbrella", "Mapfre Mexico", "MPF-UMB-2025-0320", "$5,000,000", "2025-06-01", "2026-06-01"],
        ], [0.9 * inch, 1.1 * inch, 1.4 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch], NAVY, 7.5))
        el.append(Spacer(1, 12))

        el.append(Paragraph("<b>NOTES:</b>", b))
        el.append(Paragraph(
            "Current CGL limit is $3M — contract for Ciénega Phase II requires $5M. "
            "Umbrella is $5M — contract requires $10M. Current policies do NOT include "
            "Builders Risk or surety bonds. Gaps must be addressed before project commencement.", b))
        el.append(Spacer(1, 8))
        el.append(Paragraph(
            "<b>Additional Insured:</b> Not currently endorsed for Desarrollo Industrial MX on these policies. "
            "Endorsement will be required upon placement of new project-specific coverage.", b))
        return el
    return _build_pdf(story)


def generate_coi_pacific() -> bytes:
    """COI: Pacific Builders — current coverage."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        b = s["BodyText"]
        small = ParagraphStyle("Small", parent=b, fontSize=7.5)
        el = []

        el.append(Paragraph("CERTIFICATE OF INSURANCE", title))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Certificate Holder:</b> Harbor View Properties LLC", b))
        el.append(Paragraph("<b>Insured:</b> Pacific Builders LLC", b))
        el.append(Paragraph("<b>Date Issued:</b> May 25, 2025", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph(
            "This certificate is issued as a matter of information only.", small))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Coverage", "Carrier", "Policy No.", "Limit", "Effective", "Expiry"],
            ["CGL", "Zurich NA", "ZNA-CGL-2025-1890", "$5,000,000", "2025-05-01", "2026-05-01"],
            ["Auto", "Zurich NA", "ZNA-AU-2025-1891", "$2,000,000", "2025-05-01", "2026-05-01"],
            ["Workers' Comp", "State Fund", "WCCA-2025-34521", "Statutory", "2025-05-01", "2026-05-01"],
            ["Umbrella", "Zurich NA", "ZNA-UMB-2025-0445", "$5,000,000", "2025-05-01", "2026-05-01"],
            ["Builders Risk", "Tokio Marine", "TM-BR-2025-0112", "$8,200,000", "2025-06-01", "2027-06-01"],
        ], [0.9 * inch, 1.0 * inch, 1.5 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch], NAVY, 7.5))
        el.append(Spacer(1, 12))

        el.append(Paragraph("<b>Additional Insured:</b> Harbor View Properties LLC — per CG 20 10 endorsement.", b))
        el.append(Paragraph("<b>Waiver of Subrogation:</b> Included on CGL and WC policies.", b))
        return el
    return _build_pdf(story)


def generate_coi_desarrollo_pre() -> bytes:
    """COI: Desarrollo Industrial project — pre-placement (existing coverage at start)."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("CERTIFICATE OF INSURANCE", title))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Insured:</b> Constructora del Norte, S.A. de C.V.", b))
        el.append(Paragraph("<b>Date Issued:</b> December 15, 2024", b))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Coverage", "Carrier", "Policy No.", "Limit", "Expiry"],
            ["CGL", "AXA Mexico", "AXA-RC-2024-1105", "$2,000,000", "2025-06-01"],
            ["Auto", "AXA Mexico", "AXA-AU-2024-1106", "$500,000", "2025-06-01"],
            ["Workers' Comp", "AXA Mexico", "AXA-RT-2024-1107", "Statutory", "2025-06-01"],
        ], [0.9 * inch, 1.1 * inch, 1.5 * inch, 1.0 * inch, 0.9 * inch], NAVY, 8))
        el.append(Spacer(1, 12))

        el.append(Paragraph("<b>GAPS vs. CONTRACT REQUIREMENTS:</b>", b))
        el.append(Paragraph(
            "• CGL limit $2M — contract requires $3M (gap: $1M)<br/>"
            "• Auto limit $500K — contract requires $1M (gap: $500K)<br/>"
            "• No construction all-risk policy<br/>"
            "• No surety bonds in place", b))
        return el
    return _build_pdf(story)


def generate_coi_desarrollo_final() -> bytes:
    """COI: Desarrollo Industrial project — final bound policies."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("CERTIFICATE OF INSURANCE — FINAL", title))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Certificate Holder:</b> Desarrollo Industrial MX, S.A. de C.V.", b))
        el.append(Paragraph("<b>Insured:</b> Constructora del Norte, S.A. de C.V.", b))
        el.append(Paragraph("<b>Date Issued:</b> January 20, 2025", b))
        el.append(Paragraph("<b>Status:</b> ALL COVERAGES BOUND — PROGRAM COMPLETE", b))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Coverage", "Carrier", "Policy No.", "Limit", "Premium", "Effective", "Expiry"],
            ["CGL", "Mapfre Mexico", "MPF-RC-2025-1122", "$3,000,000", "$22,400", "2025-01-15", "2026-01-15"],
            ["Auto", "AXA Mexico", "AXA-AU-2025-0789", "$1,000,000", "$8,900", "2025-01-15", "2026-01-15"],
            ["Workers' Comp", "AXA Mexico", "AXA-RT-2025-0790", "Statutory", "$15,200", "2025-01-15", "2026-01-15"],
        ], [0.8 * inch, 1.0 * inch, 1.3 * inch, 0.8 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch], NAVY, 7))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Bond", "Surety", "Bond No.", "Amount", "Premium", "Effective", "Expiry"],
            ["Performance", "Mapfre Mexico", "MPF-FC-2025-0334", "$42M MXN", "$63,000", "2025-01-15", "2026-05-30"],
            ["Payment", "Mapfre Mexico", "MPF-FP-2025-0335", "$42M MXN", "$42,000", "2025-01-15", "2026-05-30"],
        ], [0.8 * inch, 1.0 * inch, 1.3 * inch, 0.8 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch], DEEP_BLUE, 7))
        el.append(Spacer(1, 12))

        el.append(Paragraph("<b>Total Annual Premium:</b> $46,500 USD (insurance) + $105,000 MXN (surety)", b))
        el.append(Paragraph("<b>Additional Insured:</b> Desarrollo Industrial MX, S.A. de C.V.", b))
        el.append(Paragraph("<b>Waiver of Subrogation:</b> Included on all applicable policies.", b))
        return el
    return _build_pdf(story)


# ===================================================================
# 4. POLICY DECLARATIONS
# ===================================================================

def generate_policy_dec_regio() -> bytes:
    """Policy Declarations: Constructora Regio — existing CGL with exclusions."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("POLICY DECLARATIONS", title))
        el.append(Paragraph("Commercial General Liability", s["Heading3"]))
        el.append(Spacer(1, 8))

        el.append(_header_table([
            ["Field", "Detail"],
            ["Policy Number", "MPF-RC-2025-0998"],
            ["Named Insured", "Constructora Regio, S.A. de C.V."],
            ["Carrier", "Mapfre Mexico, S.A."],
            ["Policy Period", "June 1, 2025 — June 1, 2026"],
            ["Each Occurrence Limit", "$3,000,000"],
            ["General Aggregate", "$6,000,000"],
            ["Products/Completed Ops", "$3,000,000"],
            ["Personal & Advertising", "$1,000,000"],
            ["Damage to Rented Premises", "$300,000"],
            ["Medical Expense", "$10,000"],
            ["Deductible", "$15,000 per occurrence"],
            ["Annual Premium", "$18,500"],
        ], [2.2 * inch, 3.5 * inch], NAVY, 8.5))
        el.append(Spacer(1, 12))

        el.append(Paragraph("ENDORSEMENTS", h2))
        el.append(Paragraph(
            "• CG 20 10 — Additional Insured (ongoing operations): <i>None currently endorsed</i><br/>"
            "• CG 20 37 — Additional Insured (completed operations): <i>None currently endorsed</i><br/>"
            "• CG 24 04 — Waiver of Subrogation: <i>Included</i><br/>"
            "• CG 25 03 — Designated Construction Project: <i>Not applicable</i>", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("EXCLUSIONS", h2))
        el.append(Paragraph(
            "• Earthquake and volcanic eruption<br/>"
            "• Asbestos-related claims<br/>"
            "• Pollution (standard CGL exclusion — no buyback)<br/>"
            "• Professional liability / design errors<br/>"
            "• EFIS/exterior cladding defects<br/>"
            "• Subsidence, landslide, and earth movement<br/>"
            "• War, terrorism, and nuclear hazard", b))
        el.append(Spacer(1, 12))

        el.append(Paragraph("ANALYSIS NOTES", h2))
        el.append(Paragraph(
            "This policy has a $3M per-occurrence limit. The Ciénega Phase II contract requires $5M. "
            "The current policy does NOT endorse Desarrollo Industrial as additional insured — this "
            "must be added or a new project-specific policy placed. Earthquake exclusion is standard "
            "but may be a concern given the project location.", b))
        return el
    return _build_pdf(story)


def generate_policy_dec_pacific() -> bytes:
    """Policy Declarations: Pacific Builders — existing CGL + Umbrella."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("POLICY DECLARATIONS", title))
        el.append(Paragraph("Commercial General Liability & Umbrella", s["Heading3"]))
        el.append(Spacer(1, 8))

        el.append(Paragraph("<b>CGL POLICY</b>", b))
        el.append(_header_table([
            ["Field", "Detail"],
            ["Policy Number", "ZNA-CGL-2025-1890"],
            ["Named Insured", "Pacific Builders LLC"],
            ["Carrier", "Zurich North America"],
            ["Policy Period", "May 1, 2025 — May 1, 2026"],
            ["Each Occurrence", "$5,000,000"],
            ["General Aggregate", "$10,000,000"],
            ["Deductible", "$25,000"],
            ["Annual Premium", "$48,000"],
        ], [2.0 * inch, 3.5 * inch], NAVY, 8.5))
        el.append(Spacer(1, 8))

        el.append(Paragraph("<b>UMBRELLA POLICY</b>", b))
        el.append(_header_table([
            ["Field", "Detail"],
            ["Policy Number", "ZNA-UMB-2025-0445"],
            ["Carrier", "Zurich North America"],
            ["Each Occurrence", "$5,000,000"],
            ["Aggregate", "$5,000,000"],
            ["SIR", "$10,000"],
            ["Annual Premium", "$15,000"],
        ], [2.0 * inch, 3.5 * inch], DEEP_BLUE, 8.5))
        el.append(Spacer(1, 12))

        el.append(Paragraph("KEY EXCLUSIONS (CGL)", h2))
        el.append(Paragraph(
            "• Mold and fungus (limited sublimit $100K)<br/>"
            "• EIFS/stucco exterior defects<br/>"
            "• Lead paint<br/>"
            "• Pollution (standard exclusion)<br/>"
            "• Professional liability", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("ENDORSEMENTS", h2))
        el.append(Paragraph(
            "• CG 20 10 — Additional Insured: Harbor View Properties LLC<br/>"
            "• CG 24 04 — Waiver of Subrogation: Harbor View Properties LLC<br/>"
            "• CG 20 37 — Additional Insured (completed ops): Included<br/>"
            "• Primary & Non-Contributory: Included", b))
        return el
    return _build_pdf(story)


# ===================================================================
# 5. QUOTE LETTERS
# ===================================================================

def _quote_letter(carrier_name, carrier_addr, quote_ref, quote_date, valid_until,
                  project_name, client_name, coverages_table, total_premium,
                  exclusions, conditions, signoff_name, signoff_title, signoff_email,
                  extra_notes=None):
    """Generic quote letter builder."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph(carrier_name.upper(), title))
        el.append(Paragraph("Commercial Insurance Quotation", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph(f"<b>Quote Ref:</b> {quote_ref} &nbsp;&nbsp; <b>Date:</b> {quote_date} &nbsp;&nbsp; <b>Valid Until:</b> {valid_until}", b))
        el.append(Spacer(1, 4))
        el.append(Paragraph(f"<b>To:</b> Lumif.ai Insurance Brokers", b))
        el.append(Paragraph(f"<b>Re:</b> {client_name} — {project_name}", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph(
            f"Thank you for the submission. We are pleased to quote on the {project_name} project.", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("QUOTED COVERAGES", h2))
        el.append(_header_table(coverages_table,
            [1.3 * inch, 1.0 * inch, 0.9 * inch, 1.0 * inch, 1.4 * inch], NAVY, 7.5))
        el.append(Spacer(1, 4))
        el.append(Paragraph(f"<b>Total Estimated Annual Premium: {total_premium}</b>", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("EXCLUSIONS", h2))
        el.append(Paragraph("<br/>".join(f"• {e}" for e in exclusions), b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("CONDITIONS", h2))
        el.append(Paragraph("<br/>".join(f"• {c}" for c in conditions), b))

        if extra_notes:
            el.append(Spacer(1, 8))
            el.append(Paragraph("SPECIAL NOTES", h2))
            el.append(Paragraph(extra_notes, b))

        el.append(Spacer(1, 16))
        el.append(Paragraph(
            f"Regards,<br/>{signoff_name}<br/>{signoff_title}<br/>{carrier_addr}<br/>{signoff_email}", b))
        return el
    return _build_pdf(story)


def generate_quote_chubb_regio() -> bytes:
    """Quote: Chubb Mexico → Regio project (CGL, Auto, WC, Umbrella)."""
    return _quote_letter(
        "Chubb Mexico", "Chubb Mexico, S.A. de C.V.",
        "CMX-2026-Q-0891", "February 25, 2026", "May 25, 2026 (90 days)",
        "Parque Industrial Ciénega Phase II", "Constructora Regio",
        [
            ["Coverage", "Limit", "Deductible", "Premium", "Notes"],
            ["CGL", "$5,000,000", "$25,000", "$47,500", "Completed ops included"],
            ["Auto", "$2,000,000 CSL", "$10,000", "$12,300", "Hired & non-owned"],
            ["Workers' Comp", "Statutory", "N/A", "$28,700", "Mexican labor law"],
            ["Umbrella", "$10,000,000", "$10,000 SIR", "$18,500", "Follow-form"],
        ],
        "$107,000 USD",
        ["Earthquake damage", "Asbestos remediation", "Professional liability", "Pollution"],
        ["Additional insured: Desarrollo Industrial MX", "Waiver of subrogation included",
         "Policy territory: Mexico", "30-day cancellation notice"],
        "María Elena Gutiérrez", "Senior Underwriter — Construction",
        "maria.gutierrez@chubb.com.mx",
    )


def generate_quote_axa_regio() -> bytes:
    """Quote: AXA Mexico → Regio project (CGL, Auto, WC)."""
    return _quote_letter(
        "AXA Mexico", "AXA Seguros, S.A. de C.V.",
        "AXA-MX-2026-Q-1455", "February 28, 2026", "May 28, 2026 (90 days)",
        "Parque Industrial Ciénega Phase II", "Constructora Regio",
        [
            ["Coverage", "Limit", "Deductible", "Premium", "Notes"],
            ["CGL", "$5,000,000", "$20,000", "$42,800", "Broad form included"],
            ["Auto", "$2,000,000 CSL", "$7,500", "$10,900", "Fleet of 15 vehicles"],
            ["Workers' Comp", "Statutory", "N/A", "$25,100", "250 employees est."],
        ],
        "$78,800 USD",
        ["Earthquake and volcanic", "Asbestos", "Professional liability",
         "Pollution", "Subsidence"],
        ["Additional insured per contract", "Waiver of subrogation on all lines",
         "Premium audit at policy year-end"],
        "Alejandro Vega", "Underwriting Manager — Construction",
        "alejandro.vega@axa.com.mx",
        "Note: We do not write Umbrella/Excess for this class. Recommend pairing with "
        "a separate umbrella carrier. We can provide $10M Builders Risk quote upon request.",
    )


def generate_quote_mapfre_regio_surety() -> bytes:
    """Quote: Mapfre Mexico → Regio project (Surety bonds)."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("MAPFRE MEXICO", title))
        el.append(Paragraph("Surety Bond Quotation", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Quote Ref:</b> MPF-SUR-2026-Q-0223 &nbsp;&nbsp; <b>Date:</b> March 5, 2026 &nbsp;&nbsp; <b>Valid:</b> 60 days", b))
        el.append(Paragraph("<b>Re:</b> Constructora Regio — Parque Industrial Ciénega Phase II", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph(
            "Based on our review of the financial statements and bonding history, we are pleased "
            "to offer the following surety bond terms:", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("QUOTED BONDS", h2))
        el.append(_header_table([
            ["Bond Type", "Amount", "Rate", "Premium", "Duration"],
            ["Performance Bond", "MXN $185,000,000", "0.45%", "MXN $832,500", "Completion + 12mo"],
            ["Payment Bond", "MXN $185,000,000", "0.30%", "MXN $555,000", "Through completion"],
        ], [1.3 * inch, 1.3 * inch, 0.7 * inch, 1.1 * inch, 1.3 * inch], DEEP_BLUE, 8))
        el.append(Spacer(1, 4))
        el.append(Paragraph("<b>Total Bond Premium: MXN $1,387,500</b> (~$77,000 USD)", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("CONDITIONS", h2))
        el.append(Paragraph(
            "• Principal: Constructora Regio, S.A. de C.V.<br/>"
            "• Obligee: Desarrollo Industrial MX, S.A. de C.V.<br/>"
            "• Indemnity agreement required from all shareholders >10%<br/>"
            "• Quarterly financial reporting during bond term<br/>"
            "• Continuation of existing banking relationships<br/>"
            "• No change of ownership without prior written consent", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("UNDERWRITING NOTES", h2))
        el.append(Paragraph(
            "Based on prior relationship (Phase I completed without claims), we have applied "
            "preferred rates. Standard rates would be 0.55% (Performance) and 0.35% (Payment). "
            "Aggregate bonding capacity for this principal: MXN $400M.", b))
        el.append(Spacer(1, 16))
        el.append(Paragraph(
            "Laura Domínguez<br/>Surety Manager<br/>Mapfre Mexico, S.A.<br/>laura.dominguez@mapfre.com.mx", b))
        return el
    return _build_pdf(story)


def generate_quote_zurich_pacific() -> bytes:
    """Quote: Zurich NA → Pacific project (CGL, Umbrella)."""
    return _quote_letter(
        "Zurich North America", "Zurich North America, Schaumburg, IL",
        "ZNA-2026-Q-4521", "March 10, 2026", "June 10, 2026 (90 days)",
        "Harbor View Tower Renovation", "Pacific Builders LLC",
        [
            ["Coverage", "Limit", "Deductible", "Premium", "Notes"],
            ["CGL", "$5,000,000", "$25,000", "$52,000", "Completed ops, XCU"],
            ["Umbrella", "$5,000,000", "$10,000 SIR", "$16,500", "Follow-form"],
        ],
        "$68,500 USD",
        ["Mold/fungus (sublimit $100K)", "EIFS defects", "Lead paint", "Pollution"],
        ["Additional insured: Harbor View Properties LLC", "Primary & non-contributory",
         "Waiver of subrogation", "30-day cancellation notice"],
        "Jennifer Walsh", "Senior Underwriter — Construction",
        "jennifer.walsh@zurichna.com",
    )


def generate_quote_axa_pacific() -> bytes:
    """Quote: AXA → Pacific project (CGL, Auto)."""
    return _quote_letter(
        "AXA XL", "AXA XL Insurance, New York, NY",
        "AXL-2026-Q-7891", "March 12, 2026", "June 12, 2026 (90 days)",
        "Harbor View Tower Renovation", "Pacific Builders LLC",
        [
            ["Coverage", "Limit", "Deductible", "Premium", "Notes"],
            ["CGL", "$5,000,000", "$50,000", "$44,800", "Broad form"],
            ["Auto", "$2,000,000 CSL", "$5,000", "$14,200", "All owned/hired"],
        ],
        "$59,000 USD",
        ["Subsidence and earth movement", "Exterior insulation defects",
         "Mold/fungus", "Professional services"],
        ["Additional insured per contract", "Waiver of subrogation",
         "Premium installment plan available (25% quarterly)"],
        "Michael Torres", "VP Underwriting — West Region",
        "michael.torres@axaxl.com",
        "<b>Important:</b> CGL deductible is $50,000 — contract may require $25,000 or lower. "
        "Please confirm with insured whether this meets contractual obligations.",
    )


def generate_quote_tokio_pacific() -> bytes:
    """Quote: Tokio Marine → Pacific project (Builders Risk)."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("TOKIO MARINE", title))
        el.append(Paragraph("Builders Risk / Course of Construction Quotation", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Quote Ref:</b> TM-BR-2026-Q-0334 &nbsp;&nbsp; <b>Date:</b> March 18, 2026 &nbsp;&nbsp; <b>Valid:</b> 60 days", b))
        el.append(Paragraph("<b>Re:</b> Pacific Builders — Harbor View Tower Renovation", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("BUILDERS RISK COVERAGE", h2))
        el.append(_header_table([
            ["Item", "Detail"],
            ["Completed Value", "$8,200,000"],
            ["Policy Form", "All-Risk (Special Form)"],
            ["Earthquake Coverage", "INCLUDED (5% deductible, $50K minimum)"],
            ["Flood Coverage", "INCLUDED ($250K sublimit)"],
            ["Soft Costs", "$500,000 sublimit"],
            ["Delay in Completion", "$200,000 sublimit"],
            ["Debris Removal", "$250,000"],
            ["Deductible (non-earthquake)", "$25,000"],
            ["Policy Period", "24 months (June 2025 — June 2027)"],
            ["Annual Premium", "$38,500"],
        ], [2.2 * inch, 3.5 * inch], NAVY, 8.5))
        el.append(Spacer(1, 8))

        el.append(Paragraph("<b>Total Premium: $38,500/year ($77,000 for 24-month term)</b>", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("EXCLUSIONS", h2))
        el.append(Paragraph(
            "• Faulty workmanship (resulting damage covered)<br/>"
            "• War, terrorism, nuclear<br/>"
            "• Government action<br/>"
            "• Normal settling, cracking, shrinkage<br/>"
            "• Mechanical/electrical breakdown (existing equipment)", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("SPECIAL CONDITIONS", h2))
        el.append(Paragraph(
            "• Named insureds: Pacific Builders LLC and Harbor View Properties LLC<br/>"
            "• Seismic retrofit work specifically included in scope<br/>"
            "• Existing structure included at replacement cost<br/>"
            "• Monthly reporting of values required<br/>"
            "• Hot work permit program required", b))
        el.append(Spacer(1, 16))
        el.append(Paragraph(
            "Kenji Tanaka<br/>Construction Underwriter<br/>Tokio Marine America<br/>kenji.tanaka@tokiomarine.com", b))
        return el
    return _build_pdf(story)


def generate_quote_mapfre_desarrollo() -> bytes:
    """Quote: Mapfre → Desarrollo project (CGL + Surety) — selected."""
    def story(s):
        title = ParagraphStyle("T", parent=s["Title"], fontSize=14, spaceAfter=8)
        h2 = ParagraphStyle("H", parent=s["Heading2"], spaceAfter=6)
        b = s["BodyText"]
        el = []

        el.append(Paragraph("MAPFRE MEXICO", title))
        el.append(Paragraph("Combined Insurance & Surety Quotation", s["Heading3"]))
        el.append(Spacer(1, 6))
        el.append(Paragraph("<b>Quote Ref:</b> MPF-2024-Q-3345 &nbsp;&nbsp; <b>Date:</b> December 20, 2024", b))
        el.append(Paragraph("<b>Re:</b> Nave Industrial Apodaca Lote 7", b))
        el.append(Spacer(1, 8))

        el.append(Paragraph("INSURANCE", h2))
        el.append(_header_table([
            ["Coverage", "Limit", "Deductible", "Premium"],
            ["CGL", "$3,000,000", "$15,000", "$22,400"],
        ], [1.5 * inch, 1.5 * inch, 1.0 * inch, 1.0 * inch], NAVY, 9))
        el.append(Spacer(1, 8))

        el.append(Paragraph("SURETY BONDS", h2))
        el.append(_header_table([
            ["Bond", "Amount", "Rate", "Premium"],
            ["Performance Bond", "MXN $42,000,000", "0.45%", "MXN $189,000 (~$10,500)"],
            ["Payment Bond", "MXN $42,000,000", "0.30%", "MXN $126,000 (~$7,000)"],
        ], [1.5 * inch, 1.5 * inch, 0.8 * inch, 1.5 * inch], DEEP_BLUE, 9))
        el.append(Spacer(1, 8))

        el.append(Paragraph("<b>Total: $22,400 (insurance) + MXN $315,000 (surety)</b>", b))
        el.append(Spacer(1, 16))
        el.append(Paragraph(
            "Laura Domínguez<br/>Surety & Construction Lines<br/>Mapfre Mexico<br/>laura.dominguez@mapfre.com.mx", b))
        return el
    return _build_pdf(story)


def generate_quote_axa_desarrollo() -> bytes:
    """Quote: AXA → Desarrollo project (Auto, WC) — selected."""
    return _quote_letter(
        "AXA Mexico", "AXA Seguros, S.A. de C.V.",
        "AXA-MX-2024-Q-9012", "December 22, 2024", "March 22, 2025 (90 days)",
        "Nave Industrial Apodaca Lote 7", "Constructora del Norte",
        [
            ["Coverage", "Limit", "Deductible", "Premium", "Notes"],
            ["Auto", "$1,000,000 CSL", "$5,000", "$8,900", "8 vehicles"],
            ["Workers' Comp", "Statutory", "N/A", "$15,200", "120 employees"],
        ],
        "$24,100 USD",
        ["Standard auto exclusions", "Intentional acts"],
        ["Premium audit at year-end for WC", "Vehicle schedule required for auto"],
        "Alejandro Vega", "Underwriting Manager",
        "alejandro.vega@axa.com.mx",
    )


# ===================================================================
# REGISTRY — maps file IDs to generator functions
# ===================================================================

def get_pdf_generators():
    """Return dict mapping logical name → (filename, generator_fn).

    The seed script assigns stable UUIDs and calls these by name.
    """
    return {
        # Contracts
        "msa_regio": ("MSA-2026-0147-Constructora-Regio.pdf", generate_msa_regio),
        "msa_pacific": ("Contract-HVT-2025-001-Pacific-Builders.pdf", generate_msa_pacific),
        "msa_desarrollo": ("Contrato-DIM-NAV-2024-007-Nave-Apodaca.pdf", generate_msa_desarrollo),
        # Bond schedules
        "bond_regio": ("Bond-Requirements-Constructora-Regio-2026.pdf", generate_bond_schedule_regio),
        "bond_pacific": ("Bond-Schedule-Pacific-Builders-2026.pdf", generate_bond_schedule_pacific),
        # COIs
        "coi_regio": ("COI-Constructora-Regio-2025.pdf", generate_coi_regio),
        "coi_pacific": ("COI-Pacific-Builders-2025.pdf", generate_coi_pacific),
        "coi_desarrollo_pre": ("COI-Constructora-Norte-2024-Pre.pdf", generate_coi_desarrollo_pre),
        "coi_desarrollo_final": ("COI-Nave-Apodaca-2025-Final.pdf", generate_coi_desarrollo_final),
        # Policy declarations
        "policy_dec_regio": ("Policy-Dec-CGL-Constructora-Regio.pdf", generate_policy_dec_regio),
        "policy_dec_pacific": ("Policy-Dec-CGL-Umbrella-Pacific-Builders.pdf", generate_policy_dec_pacific),
        # Quote letters
        "quote_chubb_regio": ("Quote-Chubb-Mexico-CMX-2026-Q-0891.pdf", generate_quote_chubb_regio),
        "quote_axa_regio": ("Quote-AXA-Mexico-2026-Q-1455.pdf", generate_quote_axa_regio),
        "quote_mapfre_regio_surety": ("Quote-Mapfre-Surety-2026-Q-0223.pdf", generate_quote_mapfre_regio_surety),
        "quote_zurich_pacific": ("Quote-Zurich-NA-2026-Q-4521.pdf", generate_quote_zurich_pacific),
        "quote_axa_pacific": ("Quote-AXA-XL-2026-Q-7891.pdf", generate_quote_axa_pacific),
        "quote_tokio_pacific": ("Quote-Tokio-Marine-BR-2026-Q-0334.pdf", generate_quote_tokio_pacific),
        "quote_mapfre_desarrollo": ("Quote-Mapfre-2024-Q-3345-Nave-Apodaca.pdf", generate_quote_mapfre_desarrollo),
        "quote_axa_desarrollo": ("Quote-AXA-2024-Q-9012-Nave-Apodaca.pdf", generate_quote_axa_desarrollo),
    }
