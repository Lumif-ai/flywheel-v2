"""Fix document metadata field names in broker_projects.

Renames 'filename' -> 'name' and 'size_bytes' -> 'size' in the
metadata_->'documents' array so existing uploads display their actual
filenames instead of 'Untitled' in the frontend.

Usage:
    cd backend && uv run python scripts/fix_document_field_names.py
"""

import asyncio
import json

from sqlalchemy import text

from flywheel.db.session import get_session_factory


async def main() -> None:
    factory = get_session_factory()

    async with factory() as session:
        # Find all projects that have documents in metadata
        rows = await session.execute(
            text("""
                SELECT id, metadata
                FROM broker_projects
                WHERE metadata -> 'documents' IS NOT NULL
                  AND jsonb_array_length(metadata -> 'documents') > 0
                  AND deleted_at IS NULL
            """)
        )
        projects = rows.fetchall()

        if not projects:
            print("No projects with documents found. Nothing to migrate.")
            return

        updated = 0
        for project_id, metadata in projects:
            docs = metadata.get("documents", [])
            changed = False

            for doc in docs:
                if "filename" in doc and "name" not in doc:
                    doc["name"] = doc.pop("filename")
                    changed = True
                if "size_bytes" in doc and "size" not in doc:
                    doc["size"] = doc.pop("size_bytes")
                    changed = True

            if changed:
                metadata["documents"] = docs
                await session.execute(
                    text("""
                        UPDATE broker_projects
                        SET metadata = :meta
                        WHERE id = :pid
                    """),
                    {"meta": json.dumps(metadata), "pid": str(project_id)},
                )
                updated += 1

        await session.commit()
        print(f"Migrated {updated}/{len(projects)} projects.")


if __name__ == "__main__":
    asyncio.run(main())
