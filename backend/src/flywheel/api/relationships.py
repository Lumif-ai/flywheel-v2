"""Relationships REST API.

Endpoints (no prefix on router — paths are explicit):

RAPI-01: GET  /relationships/              -- list graduated accounts (partition predicate enforced)
RAPI-02: GET  /relationships/{id}          -- detail with contacts, timeline, cached ai_summary, intel
RAPI-03: PATCH /relationships/{id}/type   -- update relationship_type (validated)
RAPI-04: POST  /relationships/{id}/graduate -- graduate a prospect into relationships
RAPI-05: POST  /relationships/{id}/notes   -- create a ContextEntry note linked to account
RAPI-06: POST  /relationships/{id}/files   -- upload file to Supabase Storage and log ContextEntry
RAPI-07: POST  /relationships/{id}/synthesize -- trigger AI summary generation (rate-limited)
RAPI-08: POST  /relationships/{id}/ask    -- Q&A with source attribution from context entries

PARTITION CONTRACT: Every query targeting graduated accounts MUST include
`Account.graduated_at.isnot(None)`. The only exception is POST /graduate,
which intentionally targets un-graduated accounts.

AI SUMMARY CONTRACT: GET endpoints return `ai_summary` from the column as-is
(may be NULL). LLM synthesis is NEVER triggered on read.

RATE-LIMIT CONTRACT: POST /synthesize enforces a 5-minute rate limit via
`ai_summary_updated_at`. enforce_rate_limit() is ALWAYS called BEFORE generate().
"""

from __future__ import annotations

import datetime
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flywheel.api.deps import get_tenant_db, require_tenant
from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import Account, AccountContact, ContextEntry, Meeting, SkillRun
from flywheel.services.synthesis_engine import SynthesisEngine

# No prefix — endpoints use full path segments directly
router = APIRouter(tags=["relationships"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_TYPES: frozenset[str] = frozenset({"prospect", "customer", "advisor", "investor"})

# ContextEntry file_name values from CONTEXT_FILE_MAP in meeting_processor_web.py.
# These are used to enrich the intel dict in the relationship detail endpoint.
# "contacts" is intentionally excluded — contact data surfaces via AccountContact (PeopleTab).
INTEL_FILES: list[str] = [
    "competitive-intel",
    "pain-points",
    "icp-profiles",
    "insights",
    "action-items",
    "product-feedback",
]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RelationshipListItem(BaseModel):
    id: UUID
    name: str
    domain: str | None
    relationship_type: list[str]
    entity_level: str
    relationship_status: str
    ai_summary: str | None
    signal_count: int
    primary_contact_name: str | None
    last_interaction_at: datetime.datetime | None
    created_at: datetime.datetime


class ContactItem(BaseModel):
    id: UUID
    name: str
    title: str | None
    email: str | None
    linkedin_url: str | None
    role: str | None
    created_at: datetime.datetime


class TimelineItem(BaseModel):
    id: UUID
    source: str
    content: str
    date: datetime.date
    created_at: datetime.datetime
    direction: str | None = None      # "inbound", "outbound", "internal", "bidirectional"
    contact_name: str | None = None   # derived from content or source context


class RelationshipDetail(RelationshipListItem):
    ai_summary_updated_at: datetime.datetime | None
    contacts: list[ContactItem]
    recent_timeline: list[TimelineItem]
    commitments: list  # reserved for future use
    intel: dict  # JSONB intelligence data


class UpdateTypeRequest(BaseModel):
    types: list[str]

    @field_validator("types")
    @classmethod
    def validate_types(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one relationship type required")
        unknown = [t for t in v if t not in ALLOWED_TYPES]
        if unknown:
            allowed_str = ", ".join(sorted(ALLOWED_TYPES))
            raise ValueError(f"Unknown type: {unknown[0]}. Allowed: {allowed_str}")
        return v


class GraduateRequest(BaseModel):
    types: list[str]
    entity_level: str = "company"

    @field_validator("types")
    @classmethod
    def validate_types(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one relationship type required")
        unknown = [t for t in v if t not in ALLOWED_TYPES]
        if unknown:
            allowed_str = ", ".join(sorted(ALLOWED_TYPES))
            raise ValueError(f"Unknown type: {unknown[0]}. Allowed: {allowed_str}")
        return v


class CreateNoteRequest(BaseModel):
    content: str = ""
    source: str = "manual:note"

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or len(v.strip()) < 1:
            raise ValueError("content must not be empty")
        if len(v) > 5000:
            raise ValueError("content must be 5000 characters or fewer")
        return v


class NoteResponse(BaseModel):
    id: UUID
    content: str
    source: str
    date: datetime.date
    created_at: datetime.datetime


class FileUploadResponse(BaseModel):
    id: UUID
    file_name: str
    storage_path: str
    source: str
    date: datetime.date
    created_at: datetime.datetime


class SynthesizeResponse(BaseModel):
    ai_summary: str | None
    ai_summary_updated_at: datetime.datetime | None
    insufficient_context: bool = False


class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("question must be at least 5 characters")
        if len(v) > 1000:
            raise ValueError("question must be 1000 characters or fewer")
        return v


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    insufficient_context: bool


class PrepRequest(BaseModel):
    meeting_id: str | None = None  # optional — enriches prompt with meeting-specific context


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

_CONTACT_NAME_PATTERN = re.compile(
    r'^(?:Email from|Meeting with|Call with)\s+(.+?)(?:\s*[-:])',
    re.IGNORECASE,
)


def _derive_direction(source: str) -> str | None:
    """Derive interaction direction from ContextEntry.source."""
    if source.startswith("email:inbound") or "reply" in source:
        return "inbound"
    if source.startswith("email:outbound") or source.startswith("email:sent"):
        return "outbound"
    if source == "meeting" or source.startswith("meeting:"):
        return "bidirectional"
    if (
        source == "manual:note"
        or source.startswith("manual:")
    ):
        return "internal"
    return None


def _extract_contact_name(content: str) -> str | None:
    """Extract contact name from common content patterns."""
    match = _CONTACT_NAME_PATTERN.match(content)
    return match.group(1).strip() if match else None


def _serialize_timeline_item(entry: ContextEntry) -> dict:
    """Serialize a ContextEntry to a timeline item dict with derived fields."""
    return {
        "id": entry.id,
        "source": entry.source,
        "content": entry.content,
        "date": entry.date,
        "created_at": entry.created_at,
        "direction": _derive_direction(entry.source),
        "contact_name": _extract_contact_name(entry.content),
    }


def _account_to_list_item(
    account: Account,
    signal_count: int,
    primary_contact_name: str | None,
) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "domain": account.domain,
        "relationship_type": account.relationship_type or [],
        "entity_level": account.entity_level,
        "relationship_status": account.relationship_status,
        "ai_summary": account.ai_summary,
        "signal_count": signal_count,
        "primary_contact_name": primary_contact_name,
        "last_interaction_at": account.last_interaction_at,
        "created_at": account.created_at,
    }


# ---------------------------------------------------------------------------
# RAPI-01: List graduated accounts
# ---------------------------------------------------------------------------


@router.get("/relationships/")
async def list_relationships(
    type: str | None = Query(default=None, description="Filter by relationship type"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """List graduated accounts. PARTITION PREDICATE: graduated_at IS NOT NULL always applied."""
    # Correlated subquery: primary contact name (earliest created)
    primary_contact_sq = (
        select(AccountContact.name)
        .where(AccountContact.account_id == Account.id)
        .correlate(Account)
        .order_by(AccountContact.created_at.asc())
        .limit(1)
        .scalar_subquery()
    )

    # Correlated subquery: signal count (context entries not deleted)
    signal_count_sq = (
        select(func.count())
        .select_from(ContextEntry)
        .where(
            ContextEntry.account_id == Account.id,
            ContextEntry.deleted_at.is_(None),
        )
        .correlate(Account)
        .scalar_subquery()
    )

    # Base query — PARTITION PREDICATE ALWAYS PRESENT
    base_where = [
        Account.tenant_id == user.tenant_id,
        Account.graduated_at.isnot(None),
    ]

    # Optional type filter
    if type is not None and type in ALLOWED_TYPES:
        base_where.append(Account.relationship_type.any(type))

    # Count query
    count_stmt = (
        select(func.count())
        .select_from(Account)
        .where(*base_where)
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Data query
    data_stmt = (
        select(
            Account,
            signal_count_sq.label("signal_count"),
            primary_contact_sq.label("primary_contact_name"),
        )
        .where(*base_where)
        .order_by(Account.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(data_stmt)
    rows = result.all()

    items = []
    for row in rows:
        account = row[0]
        sc = row[1] or 0
        pc = row[2]
        items.append(_account_to_list_item(account, sc, pc))

    return {"items": items, "total": total, "offset": offset, "limit": limit}


# ---------------------------------------------------------------------------
# RAPI-02: Relationship detail
# ---------------------------------------------------------------------------


@router.get("/relationships/{id}")
async def get_relationship(
    id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Get relationship detail. Returns cached ai_summary — never calls LLM."""
    # Fetch with contacts eagerly loaded — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account)
        .where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
        .options(selectinload(Account.contacts))
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Correlated subquery for signal count
    signal_count_result = await db.execute(
        select(func.count())
        .select_from(ContextEntry)
        .where(
            ContextEntry.account_id == id,
            ContextEntry.deleted_at.is_(None),
        )
    )
    signal_count = signal_count_result.scalar_one() or 0

    # Primary contact name (first created)
    primary_contact_name: str | None = None
    if account.contacts:
        sorted_contacts = sorted(account.contacts, key=lambda c: c.created_at)
        primary_contact_name = sorted_contacts[0].name

    # Recent timeline: last 10 context entries
    timeline_result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.account_id == id,
            ContextEntry.deleted_at.is_(None),
        )
        .order_by(ContextEntry.date.desc())
        .limit(10)
    )
    timeline_entries = timeline_result.scalars().all()

    # Meeting timeline: last 20 meetings linked to this account
    meeting_rows = (await db.execute(
        select(Meeting)
        .where(
            Meeting.account_id == id,
            Meeting.tenant_id == user.tenant_id,
            Meeting.deleted_at.is_(None),
        )
        .order_by(Meeting.meeting_date.desc())
        .limit(20)
    )).scalars().all()

    # ContextEntry intel rows from meeting processing (INTEL_FILES file names only)
    intel_entries_result = await db.execute(
        select(ContextEntry)
        .where(
            ContextEntry.account_id == id,
            ContextEntry.tenant_id == user.tenant_id,
            ContextEntry.deleted_at.is_(None),
            ContextEntry.file_name.in_(INTEL_FILES),
        )
        .order_by(ContextEntry.date.desc())
        .limit(50)
    )
    intel_entries = intel_entries_result.scalars().all()

    # Serialize contacts
    contacts = [
        {
            "id": c.id,
            "name": c.name,
            "title": c.title,
            "email": c.email,
            "linkedin_url": c.linkedin_url,
            "role": c.role_in_deal,
            "created_at": c.created_at,
        }
        for c in account.contacts
    ]

    # Serialize timeline with derived direction and contact_name fields
    recent_timeline = [_serialize_timeline_item(e) for e in timeline_entries]

    # Append meeting rows as timeline items.
    # direction is set directly (not via _derive_direction) because we build the
    # dict manually rather than going through _serialize_timeline_item().
    for m in meeting_rows:
        attendees_list = m.attendees or []
        tldr = (m.summary or {}).get("tldr") or ""
        display_content = m.title or "Untitled meeting"
        if tldr:
            display_content += f" -- {tldr}"
        recent_timeline.append({
            "id": m.id,
            "source": f"meeting:{m.meeting_type or 'unclassified'}",
            "content": display_content,
            "date": m.meeting_date,
            "created_at": m.created_at,
            "direction": "bidirectional",
            "contact_name": f"{len(attendees_list)} attendees" if attendees_list else None,
        })

    # Sort combined timeline by date desc and cap at 20 entries
    recent_timeline.sort(
        key=lambda x: (x.get("date") or x.get("created_at")),
        reverse=True,
    )
    recent_timeline = recent_timeline[:20]

    # Build enriched intel dict.
    # CRITICAL: existing account.intel values take precedence — meeting intel fills gaps only.
    intel = dict(account.intel or {})
    for entry in intel_entries:
        key = entry.file_name.replace("-", "_")  # "pain-points" -> "pain_points"
        if key not in intel or not intel[key]:
            intel[key] = entry.content  # most recent entry wins (query ordered by date desc)

    return {
        **_account_to_list_item(account, signal_count, primary_contact_name),
        "ai_summary_updated_at": account.ai_summary_updated_at,
        "contacts": contacts,
        "recent_timeline": recent_timeline,
        "commitments": [],
        "intel": intel,
    }


# ---------------------------------------------------------------------------
# RAPI-03: Update relationship type
# ---------------------------------------------------------------------------


@router.patch("/relationships/{id}/type")
async def update_relationship_type(
    id: UUID,
    body: UpdateTypeRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Update relationship_type. Validates non-empty and allowed values. PARTITION PREDICATE enforced."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    account.relationship_type = body.types
    account.updated_at = now

    await db.commit()
    await db.refresh(account)

    return {
        "id": account.id,
        "name": account.name,
        "relationship_type": account.relationship_type,
        "updated_at": account.updated_at,
    }


# ---------------------------------------------------------------------------
# RAPI-04: Graduate a prospect into relationships
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/graduate", status_code=status.HTTP_200_OK)
async def graduate_to_relationship(
    id: UUID,
    body: GraduateRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Graduate an account into the relationships surface.

    NO graduated_at partition predicate here — we're targeting un-graduated accounts.
    Returns 409 if already graduated.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = datetime.date.today()

    # Fetch account (no graduated_at filter — intentionally targets un-graduated)
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account.graduated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already graduated",
        )

    # Graduate: set timestamp, types, level
    account.graduated_at = now
    account.relationship_type = body.types
    account.entity_level = body.entity_level or "company"
    account.updated_at = now

    # Log ContextEntry for audit trail
    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name="account-events",
        source="manual:graduate",
        content=(
            f"Account '{account.name}' graduated into relationships "
            f"with types: {', '.join(body.types)}"
        ),
        date=today,
        account_id=account.id,
    )
    db.add(entry)

    await db.commit()
    await db.refresh(account)

    return {
        "id": account.id,
        "name": account.name,
        "domain": account.domain,
        "relationship_type": account.relationship_type,
        "entity_level": account.entity_level,
        "graduated_at": account.graduated_at,
        "updated_at": account.updated_at,
    }


# ---------------------------------------------------------------------------
# RAPI-05: Add a note to a relationship
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/notes", status_code=status.HTTP_201_CREATED)
async def create_relationship_note(
    id: UUID,
    body: CreateNoteRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> NoteResponse:
    """Create a ContextEntry note linked to a graduated account.

    PARTITION CONTRACT: graduated_at IS NOT NULL enforced.
    """
    today = datetime.date.today()

    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name="relationship-notes",
        source=body.source,
        content=body.content,
        date=today,
        account_id=account.id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return NoteResponse(
        id=entry.id,
        content=entry.content,
        source=entry.source,
        date=entry.date,
        created_at=entry.created_at,
    )


# ---------------------------------------------------------------------------
# RAPI-06: Upload a file to a relationship
# ---------------------------------------------------------------------------

# Maximum upload size: 10 MB
_MAX_FILE_SIZE = 10 * 1024 * 1024  # bytes
_STORAGE_BUCKET = "documents"


@router.post("/relationships/{id}/files", status_code=status.HTTP_201_CREATED)
async def upload_relationship_file(
    id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> FileUploadResponse:
    """Upload a file to Supabase Storage and log a ContextEntry for a graduated account.

    PARTITION CONTRACT: graduated_at IS NOT NULL enforced.
    File size limit: 10 MB.
    """
    today = datetime.date.today()

    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Read file content and validate size
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {len(content)} bytes exceeds 10 MB limit",
        )

    # Upload to Supabase Storage using httpx (matches existing document_storage.py pattern)
    from flywheel.config import settings
    supabase_url = settings.supabase_url
    service_key = settings.supabase_service_key
    storage_path = f"relationships/{user.tenant_id}/{account.id}/{file.filename}"
    upload_url = (
        f"{supabase_url}/storage/v1/object/{_STORAGE_BUCKET}/{storage_path}"
    )
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            upload_url,
            content=content,
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type": file.content_type or "application/octet-stream",
            },
        )
        resp.raise_for_status()

    # Log ContextEntry for audit trail and timeline visibility
    entry = ContextEntry(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        file_name=file.filename,
        source="manual:file-upload",
        content=f"File uploaded: {file.filename}",
        detail=storage_path,
        date=today,
        account_id=account.id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return FileUploadResponse(
        id=entry.id,
        file_name=file.filename,
        storage_path=storage_path,
        source=entry.source,
        date=entry.date,
        created_at=entry.created_at,
    )


# ---------------------------------------------------------------------------
# RAPI-07: AI synthesis trigger (rate-limited)
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/synthesize", status_code=status.HTTP_200_OK)
async def synthesize_relationship(
    id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> SynthesizeResponse:
    """Trigger AI summary generation for a graduated account.

    RATE-LIMIT CONTRACT: enforce_rate_limit() is called BEFORE generate().
    This means the 429 is returned before any LLM call — even when ai_summary is NULL.

    PARTITION CONTRACT: graduated_at IS NOT NULL enforced.
    """
    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # CRITICAL ORDER: rate limit check FIRST, generate SECOND
    # This ensures 429 is returned before any LLM call — see rate-limit contract above.
    await SynthesisEngine.enforce_rate_limit(account)
    summary = await SynthesisEngine.generate(db, account)

    await db.commit()
    await db.refresh(account)

    return SynthesizeResponse(
        ai_summary=account.ai_summary,
        ai_summary_updated_at=account.ai_summary_updated_at,
        insufficient_context=(summary is None),
    )


# ---------------------------------------------------------------------------
# RAPI-08: Relationship Q&A with source attribution
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/ask", status_code=status.HTTP_200_OK)
async def ask_relationship(
    id: UUID,
    body: AskRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> AskResponse:
    """Answer a question about a relationship using context entries.

    No rate limit — ask is stateless (does not write to the account).
    Returns graceful "insufficient context" response when fewer than 3 entries exist.

    PARTITION CONTRACT: graduated_at IS NOT NULL enforced.
    """
    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    result_dict = await SynthesisEngine.ask(db, account, body.question)
    return AskResponse(**result_dict)


# ---------------------------------------------------------------------------
# RAPI-09: Trigger meeting prep briefing generation
# ---------------------------------------------------------------------------


@router.post("/relationships/{id}/prep", status_code=status.HTTP_202_ACCEPTED)
async def prep_relationship(
    id: UUID,
    body: PrepRequest | None = None,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
) -> dict:
    """Create a SkillRun for account-scoped meeting prep and return a stream URL.

    Follows the same pattern as POST /meetings/{id}/process: creates a pending
    SkillRun and returns run_id + stream_url for SSE consumption.

    PARTITION CONTRACT: graduated_at IS NOT NULL enforced.
    Returns 404 for non-existent or non-graduated accounts (never 403).
    """
    # Fetch account — PARTITION PREDICATE enforced
    result = await db.execute(
        select(Account).where(
            Account.id == id,
            Account.tenant_id == user.tenant_id,
            Account.graduated_at.isnot(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Build input_text with Account-ID prefix so skill_executor dispatches to
    # _execute_account_meeting_prep (not the onboarding _execute_meeting_prep)
    input_lines = [
        f"Account-ID: {id}",
        f"Account-Name: {account.name}",
    ]
    meeting_id = (body.meeting_id if body else None)
    if meeting_id:
        input_lines.append(f"Meeting-ID: {meeting_id}")

    run = SkillRun(
        tenant_id=user.tenant_id,
        user_id=user.sub,
        skill_name="meeting-prep",
        input_text="\n".join(input_lines),
        status="pending",
    )
    db.add(run)
    await db.flush()
    await db.commit()

    return {
        "run_id": str(run.id),
        "stream_url": f"/api/v1/skills/runs/{run.id}/stream",
    }
