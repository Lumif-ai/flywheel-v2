"""File I/O tools for skill execution.

Provides UUID-based file read/write handlers. No filesystem paths accepted --
all storage is via UploadedFile DB records with UUID-based storage paths.

SECURITY:
- file_read never exposes storage_path to the LLM
- file_write never accepts a path parameter (UUID-based storage only)
- Both handlers are tenant-scoped via RLS

Handlers:
    handle_file_read(tool_input, context) -> str
    handle_file_write(tool_input, context) -> str
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import text as sa_text
from sqlalchemy import select

from flywheel.db.models import UploadedFile
from flywheel.tools.registry import RunContext


async def handle_file_read(tool_input: dict, context: RunContext) -> str:
    """Read an uploaded file's extracted text by UUID.

    Args:
        tool_input: {"file_id": "<uuid>"}
        context: RunContext with tenant_id and session_factory

    Returns:
        Extracted text content, or error string. Never raises.
    """
    try:
        file_id_str = tool_input.get("file_id")
        if not file_id_str:
            return "Error: file_id is required"

        try:
            file_uuid = UUID(file_id_str)
        except ValueError:
            return "Error: invalid file_id format"

        session = context.session_factory()
        try:
            # Set tenant RLS context (belt-and-suspenders with explicit WHERE)
            await session.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(context.tenant_id)},
            )

            result = await session.execute(
                select(UploadedFile).where(
                    UploadedFile.id == file_uuid,
                    UploadedFile.tenant_id == context.tenant_id,
                )
            )
            uploaded = result.scalar_one_or_none()

            if uploaded is None:
                return f"File not found: {file_id_str}"

            if uploaded.extracted_text is not None:
                return uploaded.extracted_text

            # Binary file -- no text content available
            return (
                f"File '{uploaded.filename}' is a binary file. "
                "Text content is not available."
            )
        finally:
            await session.close()

    except Exception as e:
        return f"Error reading file: {e}"


async def handle_file_write(tool_input: dict, context: RunContext) -> str:
    """Write a generated file as an UploadedFile DB record.

    Stores text content in extracted_text column (interim approach --
    Supabase Storage upload deferred). Returns download URL.

    Args:
        tool_input: {"filename": "output.html", "content": "...", "mimetype": "text/html"}
        context: RunContext with tenant_id, user_id, run_id, session_factory

    Returns:
        Success message with download URL, or error string. Never raises.

    SECURITY: No 'path' parameter accepted. UUID-based storage only.
    """
    try:
        filename = tool_input.get("filename", "output.html")
        content = tool_input.get("content")
        mimetype = tool_input.get("mimetype", "text/html")

        if not content:
            return "Error: content is required"

        file_uuid = uuid4()
        storage_path = (
            f"generated/{context.tenant_id}/{context.run_id}/"
            f"{file_uuid}/{filename}"
        )

        # Determine if content is text-based for extracted_text storage
        is_text = mimetype.startswith("text/") or mimetype in (
            "application/json",
            "application/xml",
            "application/xhtml+xml",
        )

        size_bytes = len(content.encode("utf-8"))

        session = context.session_factory()
        try:
            # Set tenant RLS context
            await session.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(context.tenant_id)},
            )

            uploaded = UploadedFile(
                id=file_uuid,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                filename=filename,
                mimetype=mimetype,
                size_bytes=size_bytes,
                extracted_text=content if is_text else None,
                storage_path=storage_path,
            )
            session.add(uploaded)
            await session.commit()

            return (
                f"File saved: {filename}\n"
                f"Download: /api/v1/files/{file_uuid}"
            )
        finally:
            await session.close()

    except Exception as e:
        return f"Error writing file: {e}"
