"""File text extraction service for PDF, DOCX, and TXT uploads.

Provides:
- validate_upload(): Check mimetype and size constraints
- extract_text(): Extract text content from supported file formats
"""

from __future__ import annotations

from io import BytesIO

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

ALLOWED_MIMETYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "txt",
    "text/x-markdown": "txt",
}


def validate_upload(filename: str, content_type: str | None, size: int) -> str:
    """Validate file upload constraints.

    Args:
        filename: Original filename.
        content_type: MIME type from the upload.
        size: File size in bytes.

    Returns:
        Validated mimetype string.

    Raises:
        ValueError: If mimetype is not allowed or file is too large.
    """
    if content_type not in ALLOWED_MIMETYPES:
        raise ValueError(
            f"Unsupported file type: {content_type}. "
            f"Allowed: PDF, DOCX, TXT, Markdown."
        )

    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size} bytes. Maximum: {MAX_FILE_SIZE} bytes (10MB)."
        )

    return content_type


async def extract_text(content: bytes, mimetype: str) -> str:
    """Extract text content from a file.

    Args:
        content: Raw file bytes.
        mimetype: Validated MIME type.

    Returns:
        Extracted text as a string.

    Raises:
        ValueError: If mimetype is not supported.
    """
    file_type = ALLOWED_MIMETYPES.get(mimetype)

    if file_type == "pdf":
        return _extract_pdf(content)
    elif file_type == "docx":
        return _extract_docx(content)
    elif file_type == "txt":
        return content.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported mimetype: {mimetype}")


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber

    pages_text = []
    with pdfplumber.open(BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n\n".join(pages_text)


def _extract_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    import docx

    doc = docx.Document(BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)
