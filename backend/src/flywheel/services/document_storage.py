"""Supabase Storage integration for documents and uploaded files.

Public API:
    get_document_url(storage_path, expires_in) -> str   -- signed URL for "documents" bucket (legacy)
    upload_file(tenant_id, file_id, filename, ...) -> str -- upload to "uploads" bucket
    get_file_url(storage_path, expires_in) -> str        -- signed URL for "uploads" bucket
    _generate_title(skill_name, input_text, metadata) -> str
    _extract_document_metadata(skill_name, input_text, output) -> dict
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path

import httpx

from flywheel.config import settings

logger = logging.getLogger(__name__)

BUCKET = "documents"
UPLOADS_BUCKET = "uploads"

# Local file storage fallback directory
_LOCAL_STORAGE_DIR = Path(os.environ.get(
    "FLYWHEEL_LOCAL_STORAGE_DIR",
    Path(__file__).resolve().parents[3] / "storage" / "uploads",
))


async def get_document_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for a document in Supabase Storage."""
    supabase_url = settings.supabase_url
    service_key = settings.supabase_service_key

    url = f"{supabase_url}/storage/v1/object/sign/{BUCKET}/{storage_path}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"expiresIn": expires_in},
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    signed_path = data.get("signedURL", "")
    if signed_path.startswith("/"):
        return f"{supabase_url}{signed_path}"
    return signed_path


async def upload_file(
    tenant_id: str,
    file_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> str:
    """Upload raw file bytes to the 'uploads' bucket. Returns storage path.

    Falls back to local file storage if Supabase Storage is unavailable.
    Local paths are prefixed with ``local://`` so download_file can route correctly.
    """
    storage_path = f"{tenant_id}/{file_id}/{filename}"

    # Try Supabase Storage first
    supabase_url = settings.supabase_url
    service_key = settings.supabase_service_key

    try:
        url = f"{supabase_url}/storage/v1/object/{UPLOADS_BUCKET}/{storage_path}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                content=content,
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": mime_type,
                },
            )
            resp.raise_for_status()
        logger.info("Uploaded file to Supabase: %s (%d bytes)", storage_path, len(content))
        return storage_path
    except Exception as exc:
        logger.warning("Supabase upload failed (%s), falling back to local storage", exc)

    # Local fallback — write bytes to disk
    local_path = _LOCAL_STORAGE_DIR / storage_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    logger.info("Uploaded file to local: %s (%d bytes)", local_path, len(content))
    return f"local://{storage_path}"


async def download_file(storage_path: str) -> bytes | None:
    """Download file bytes from Supabase Storage or local fallback.

    Handles both Supabase paths (``tenant/file_id/name``) and local paths
    (``local://tenant/file_id/name``).
    """
    if storage_path.startswith("local://"):
        # Local fallback
        relative = storage_path[len("local://"):]
        local_path = _LOCAL_STORAGE_DIR / relative
        if not local_path.exists():
            logger.error("Local file not found: %s", local_path)
            return None
        return local_path.read_bytes()

    # Supabase Storage
    supabase_url = settings.supabase_url
    service_key = settings.supabase_service_key
    url = f"{supabase_url}/storage/v1/object/{UPLOADS_BUCKET}/{storage_path}"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {service_key}"},
        )
        if resp.status_code != 200:
            logger.error("Supabase download failed: %s -> %d", storage_path, resp.status_code)
            return None
        return resp.content


async def get_file_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for a file in the 'uploads' bucket."""
    supabase_url = settings.supabase_url
    service_key = settings.supabase_service_key

    url = f"{supabase_url}/storage/v1/object/sign/{UPLOADS_BUCKET}/{storage_path}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"expiresIn": expires_in},
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    signed_path = data.get("signedURL", "")
    if signed_path.startswith("/"):
        return f"{supabase_url}{signed_path}"
    return signed_path


def _generate_title(
    skill_name: str, input_text: str | None, metadata: dict
) -> str:
    """Generate a human-readable title for a document."""
    if skill_name == "meeting-prep":
        contacts = metadata.get("contacts", [])
        if contacts:
            return f"Meeting Prep: {contacts[0]}"
        if input_text:
            # Try to extract a name from the input
            name = input_text.strip().split("\n")[0][:80]
            return f"Meeting Prep: {name}"
        return f"Meeting Prep - {date.today().isoformat()}"

    if skill_name == "company-intel":
        companies = metadata.get("companies", [])
        if companies:
            return f"Company Intel: {companies[0]}"
        if input_text:
            name = input_text.strip().split("\n")[0][:80]
            return f"Company Intel: {name}"
        return f"Company Intel - {date.today().isoformat()}"

    # Fallback for any skill
    display_name = skill_name.replace("-", " ").replace("_", " ").title()
    return f"{display_name} - {date.today().isoformat()}"


def _extract_document_metadata(
    skill_name: str, input_text: str | None, output: str | None
) -> dict:
    """Extract structured metadata from skill run inputs/outputs."""
    contacts: list[str] = []
    companies: list[str] = []
    tags: list[str] = [skill_name]

    if not input_text:
        return {"contacts": contacts, "companies": companies, "tags": tags}

    if skill_name == "meeting-prep":
        # Parse contact names from input_text
        # Common patterns: "meeting with John Smith", "prep for Jane Doe"
        lines = input_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                # First non-empty, non-header line is likely the contact/topic
                contacts.append(line[:100])
                break
        tags.append("meeting")

    elif skill_name == "company-intel":
        # Parse company name from input_text
        lines = input_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                companies.append(line[:100])
                break
        # Try to extract URL
        url_match = re.search(r"https?://[^\s]+", input_text)
        if url_match:
            tags.append("has-url")

    return {"contacts": contacts, "companies": companies, "tags": tags}
