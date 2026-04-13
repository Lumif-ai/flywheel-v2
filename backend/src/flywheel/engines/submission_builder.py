"""
submission_builder.py - Compile project documents into a submission package for a carrier.

Creates SubmissionDocument rows linking a CarrierQuote to the project's uploaded files,
classifying each by document type based on filename heuristics.

Functions:
  build_submission_package(db, project_id, carrier_quote_id) -> list[dict]
    Build submission package for a carrier solicitation.
"""

import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywheel.db.models import BrokerProject, SubmissionDocument, UploadedFile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Document type classification heuristics
# ---------------------------------------------------------------------------

_CLASSIFICATION_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"contrat|poliza|contract", re.IGNORECASE), "contract_excerpt"),
    (re.compile(r"riesgo|risk", re.IGNORECASE), "risk_profile"),
    (re.compile(r"financ|estado", re.IGNORECASE), "financial_statement"),
]


def _classify_document(filename: str, metadata: dict | None = None) -> str:
    """Classify a document based on filename and metadata keywords."""
    search_text = filename
    if metadata:
        search_text += " " + " ".join(str(v) for v in metadata.values() if isinstance(v, str))

    for pattern, doc_type in _CLASSIFICATION_RULES:
        if pattern.search(search_text):
            return doc_type

    return "supporting_document"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def build_submission_package(
    db: AsyncSession,
    project_id: UUID,
    carrier_quote_id: UUID,
) -> list[dict]:
    """Build a submission document package for a carrier quote.

    Loads the BrokerProject's documents array from metadata_, queries the
    corresponding UploadedFile records, creates SubmissionDocument rows for
    each, and returns a summary list.

    Args:
        db: Async database session.
        project_id: The broker project ID.
        carrier_quote_id: The carrier quote being solicited.

    Returns:
        List of dicts: [{"file_id": uuid, "document_type": str,
                         "display_name": str, "included": True}]
        Empty list if project has no documents.
    """
    # Load the project to get document references from metadata_
    project = await db.get(BrokerProject, project_id)
    if not project:
        logger.warning("build_submission_package: project %s not found", project_id)
        return []

    # Documents are stored as an array in project.metadata_["documents"]
    # Each entry has at minimum a "file_id" key
    documents_meta = (project.metadata_ or {}).get("documents", [])
    if not documents_meta:
        logger.info(
            "build_submission_package: project %s has no documents in metadata",
            project_id,
        )
        return []

    # Extract file IDs from the documents array
    file_ids = []
    for doc in documents_meta:
        file_id = doc.get("file_id") or doc.get("id")
        if file_id:
            file_ids.append(UUID(str(file_id)) if not isinstance(file_id, UUID) else file_id)

    if not file_ids:
        return []

    # Query UploadedFile records
    stmt = select(UploadedFile).where(UploadedFile.id.in_(file_ids))
    result = await db.execute(stmt)
    uploaded_files = result.scalars().all()

    # Create SubmissionDocument rows
    package: list[dict] = []

    for uf in uploaded_files:
        doc_type = _classify_document(uf.filename, uf.metadata_)
        display_name = uf.filename

        submission_doc = SubmissionDocument(
            tenant_id=project.tenant_id,
            carrier_quote_id=carrier_quote_id,
            uploaded_file_id=uf.id,
            document_type=doc_type,
            display_name=display_name,
            included=True,
            import_source="auto",
        )
        db.add(submission_doc)

        package.append({
            "file_id": uf.id,
            "document_type": doc_type,
            "display_name": display_name,
            "included": True,
        })

    await db.flush()
    logger.info(
        "build_submission_package: created %d submission documents for quote %s",
        len(package),
        carrier_quote_id,
    )

    return package
