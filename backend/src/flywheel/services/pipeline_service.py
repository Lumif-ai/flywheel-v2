"""Pipeline service — business logic for unified pipeline CRUD.

Handles list, get, create, update, and dedup-check operations on
PipelineEntry. Enforces SCHEMA-05 (person auto-contact), stage
validation, and stage-change activity tracking.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flywheel.auth.jwt import TokenPayload
from flywheel.db.models import (
    Activity,
    Contact,
    ContextEntry,
    Meeting,
    PipelineEntry,
    PipelineEntrySource,
)
from flywheel.utils.normalize import normalize_company_name

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STAGES = [
    "identified",
    "contacted",
    "engaged",
    "qualified",
    "committed",
    "closed",
]

VALID_STATUS_TRANSITIONS = {
    "drafted": {"approved", "drafted"},
    "approved": {"sent", "drafted"},
    "sent": {"replied", "bounced", "sent"},
    "replied": {"replied"},
    "bounced": {"drafted", "bounced"},
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def compute_next_step(
    latest_status: str | None,
    occurred_at: datetime.datetime | None,
    now: datetime.datetime | None = None,
) -> str:
    """Derive a human-readable next-step recommendation from activity status."""
    if latest_status is None:
        return "Ready to send"
    if latest_status == "replied":
        return "Replied - engage"
    if latest_status == "bounced":
        return "Bounced - fix email"
    if latest_status in ("drafted", "approved"):
        return "Ready to send"
    if latest_status == "sent":
        if occurred_at is None:
            return "Follow up now"
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)
        days_since = (now - occurred_at).days
        if days_since >= 7:
            return "Follow up now"
        remaining = 7 - days_since
        return f"Follow up in {remaining}d"
    return "Ready to send"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreatePipelineRequest(BaseModel):
    name: str
    entity_type: str = "company"
    domain: str | None = None
    stage: str = "identified"
    fit_score: float | None = None
    fit_tier: str | None = None
    fit_rationale: str | None = None
    relationship_type: list[str] = ["prospect"]
    source: str = "manual"
    source_ref_id: UUID | None = None
    channels: list[str] = []
    intel: dict | None = None
    ai_summary: str | None = None
    # Person auto-contact fields (SCHEMA-05)
    email: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None


class UpdatePipelineRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    stage: str | None = None
    fit_score: float | None = None
    fit_tier: str | None = None
    fit_rationale: str | None = None
    relationship_type: list[str] | None = None
    source: str | None = None
    channels: list[str] | None = None
    intel: dict | None = None
    ai_summary: str | None = None
    next_action_date: datetime.date | None = None
    next_action_note: str | None = None


class PipelineListItem(BaseModel):
    id: str
    name: str
    domain: str | None
    entity_type: str
    stage: str
    fit_score: float | None
    fit_tier: str | None
    relationship_type: list[str]
    source: str
    channels: list[str]
    last_activity_at: str | None
    created_at: str
    contact_count: int
    primary_contact: dict | None


class PipelineDetail(PipelineListItem):
    intel: dict
    ai_summary: str | None
    fit_rationale: str | None
    contacts: list[dict]
    recent_activities: list[dict]
    sources: list[dict]


class DedupMatch(BaseModel):
    id: str
    name: str
    domain: str | None
    stage: str
    entity_type: str
    similarity_score: float
    match_reasons: list[str]


class CreateContactRequest(BaseModel):
    name: str
    email: str | None = None
    title: str | None = None
    role: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_primary: bool = False


class UpdateContactRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    title: str | None = None
    role: str | None = None
    linkedin_url: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_primary: bool | None = None


class CreateActivityRequest(BaseModel):
    type: str
    channel: str | None = None
    direction: str | None = None
    status: str = "completed"
    subject: str | None = None
    body_preview: str | None = None
    metadata_: dict | None = None
    contact_id: UUID | None = None
    occurred_at: datetime.datetime | None = None


class UpdateActivityRequest(BaseModel):
    type: str | None = None
    channel: str | None = None
    direction: str | None = None
    status: str | None = None
    subject: str | None = None
    body_preview: str | None = None
    metadata_: dict | None = None
    contact_id: UUID | None = None
    occurred_at: datetime.datetime | None = None


class TimelineItem(BaseModel):
    id: str
    source_type: str  # "activity" | "meeting" | "context"
    date: str
    title: str
    summary: str | None = None
    type: str | None = None
    channel: str | None = None
    direction: str | None = None
    status: str | None = None
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PipelineService:
    """Business logic for the unified pipeline."""

    def __init__(self, db: AsyncSession, user: TokenPayload) -> None:
        self.db = db
        self.user = user
        self.tenant_id = user.tenant_id

    # ----- List -----

    async def list_entries(
        self,
        *,
        filters: dict | None = None,
        offset: int = 0,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        search: str | None = None,
        view: str | None = None,
        include_retired: bool = False,
    ) -> tuple[list, int]:
        """Return (entries_with_counts, total) for the pipeline grid."""
        filters = filters or {}

        # Base filter
        base = select(PipelineEntry).where(
            PipelineEntry.tenant_id == self.tenant_id,
        )

        if not include_retired:
            base = base.where(PipelineEntry.retired_at.is_(None))

        # Apply filters
        if filters.get("entity_type"):
            base = base.where(PipelineEntry.entity_type == filters["entity_type"])

        if filters.get("stage"):
            stages = filters["stage"] if isinstance(filters["stage"], list) else [filters["stage"]]
            base = base.where(PipelineEntry.stage.in_(stages))

        if filters.get("fit_tier"):
            tiers = filters["fit_tier"] if isinstance(filters["fit_tier"], list) else [filters["fit_tier"]]
            base = base.where(PipelineEntry.fit_tier.in_(tiers))

        if filters.get("relationship_type"):
            # Array overlap: entry.relationship_type has any of the requested values
            rt = filters["relationship_type"]
            if isinstance(rt, str):
                rt = [rt]
            base = base.where(PipelineEntry.relationship_type.overlap(rt))

        if filters.get("source"):
            base = base.where(PipelineEntry.source == filters["source"])

        # Search
        if search:
            pattern = f"%{search}%"
            base = base.where(
                PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
            )

        # View-based tab filtering
        if view == "needs_action":
            base = base.where(
                (PipelineEntry.last_activity_at.is_(None))
                | (PipelineEntry.last_activity_at < func.now() - text("interval '7 days'"))
            )
        elif view == "replied":
            base = base.where(
                PipelineEntry.stage.in_(["engaged", "qualified", "committed"])
            )
        elif view == "stale":
            base = base.where(
                PipelineEntry.last_activity_at.is_not(None),
                PipelineEntry.last_activity_at < func.now() - text("interval '14 days'"),
            )

        # Count total
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Sort
        sort_columns = {
            "name": PipelineEntry.name,
            "created_at": PipelineEntry.created_at,
            "last_activity_at": PipelineEntry.last_activity_at,
            "next_action_date": PipelineEntry.next_action_date,
            "stage": PipelineEntry.stage,
            "fit_tier": PipelineEntry.fit_tier,
        }
        sort_col = sort_columns.get(sort_by, PipelineEntry.created_at)
        order_expr = sort_col.desc() if sort_dir.lower() != "asc" else sort_col.asc()

        # Contact count correlated subquery
        contact_count_subq = (
            select(func.count())
            .where(Contact.pipeline_entry_id == PipelineEntry.id)
            .correlate(PipelineEntry)
            .scalar_subquery()
        )

        # Primary contact subquery (first is_primary=True, or first by created_at)
        primary_contact_subq = (
            select(Contact)
            .where(
                Contact.pipeline_entry_id == PipelineEntry.id,
                Contact.is_primary.is_(True),
            )
            .correlate(PipelineEntry)
            .limit(1)
            .subquery()
        )

        data_stmt = (
            select(
                PipelineEntry,
                contact_count_subq.label("contact_count"),
            )
            .where(
                PipelineEntry.tenant_id == self.tenant_id,
            )
            .order_by(order_expr)
            .offset(offset)
            .limit(limit)
        )

        if not include_retired:
            data_stmt = data_stmt.where(PipelineEntry.retired_at.is_(None))

        # Re-apply filters on data query
        if filters.get("entity_type"):
            data_stmt = data_stmt.where(PipelineEntry.entity_type == filters["entity_type"])
        if filters.get("stage"):
            stages = filters["stage"] if isinstance(filters["stage"], list) else [filters["stage"]]
            data_stmt = data_stmt.where(PipelineEntry.stage.in_(stages))
        if filters.get("fit_tier"):
            tiers = filters["fit_tier"] if isinstance(filters["fit_tier"], list) else [filters["fit_tier"]]
            data_stmt = data_stmt.where(PipelineEntry.fit_tier.in_(tiers))
        if filters.get("relationship_type"):
            rt = filters["relationship_type"]
            if isinstance(rt, str):
                rt = [rt]
            data_stmt = data_stmt.where(PipelineEntry.relationship_type.overlap(rt))
        if filters.get("source"):
            data_stmt = data_stmt.where(PipelineEntry.source == filters["source"])
        if search:
            pattern = f"%{search}%"
            data_stmt = data_stmt.where(
                PipelineEntry.name.ilike(pattern) | PipelineEntry.domain.ilike(pattern)
            )

        # Re-apply view filter on data query
        if view == "needs_action":
            data_stmt = data_stmt.where(
                (PipelineEntry.last_activity_at.is_(None))
                | (PipelineEntry.last_activity_at < func.now() - text("interval '7 days'"))
            )
        elif view == "replied":
            data_stmt = data_stmt.where(
                PipelineEntry.stage.in_(["engaged", "qualified", "committed"])
            )
        elif view == "stale":
            data_stmt = data_stmt.where(
                PipelineEntry.last_activity_at.is_not(None),
                PipelineEntry.last_activity_at < func.now() - text("interval '14 days'"),
            )

        result = await self.db.execute(data_stmt)
        rows = result.all()

        # For each row, fetch primary contact info
        entries = []
        for row in rows:
            entry = row[0]
            cc = row[1] or 0

            # Get primary contact
            pc_result = await self.db.execute(
                select(Contact)
                .where(
                    Contact.pipeline_entry_id == entry.id,
                    Contact.is_primary.is_(True),
                )
                .limit(1)
            )
            pc = pc_result.scalar_one_or_none()
            primary_contact = None
            if pc:
                primary_contact = {
                    "name": pc.name,
                    "email": pc.email,
                    "title": pc.title,
                }

            entries.append((entry, cc, primary_contact))

        # Batch-fetch outreach summaries for all entries on this page
        entry_ids = [e[0].id for e in entries]
        outreach_map: dict[str, dict[str, int]] = {}
        if entry_ids:
            outreach_stats_result = await self.db.execute(
                select(
                    Activity.pipeline_entry_id,
                    Activity.status,
                    func.count().label("cnt"),
                )
                .where(
                    Activity.pipeline_entry_id.in_(entry_ids),
                    Activity.type == "outreach",
                )
                .group_by(Activity.pipeline_entry_id, Activity.status)
            )
            for row in outreach_stats_result.all():
                eid = str(row[0])
                s = row[1]
                cnt = row[2]
                outreach_map.setdefault(eid, {})[s] = cnt

        # Return 4-tuples: (entry, contact_count, primary_contact, outreach_summary)
        entries_with_outreach = [
            (entry, cc, pc, outreach_map.get(str(entry.id)))
            for entry, cc, pc in entries
        ]

        return entries_with_outreach, total

    # ----- List contacts (flat) -----

    async def list_contacts_flat(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        sort_by: str = "name",
        sort_dir: str = "asc",
        filters: dict | None = None,
        include_retired: bool = False,
    ) -> tuple[list[dict], int]:
        """Return flattened contact rows with parent company and latest outreach activity."""
        filters = filters or {}

        # Base query: contacts joined to pipeline entries
        base = (
            select(Contact)
            .join(PipelineEntry, Contact.pipeline_entry_id == PipelineEntry.id)
            .where(PipelineEntry.tenant_id == self.tenant_id)
        )

        if not include_retired:
            base = base.where(PipelineEntry.retired_at.is_(None))

        # Apply filters
        if filters.get("company"):
            base = base.where(PipelineEntry.name.ilike(f"%{filters['company']}%"))
        if filters.get("status"):
            # Filter by latest activity status — handled post-query for correctness
            pass  # Applied after fetching (see below)
        if filters.get("channel"):
            pass  # Applied after fetching (see below)

        # Count total (before status/channel filters which are post-query)
        # We'll adjust count after if status/channel filters are active
        has_post_filters = bool(
            filters.get("status") or filters.get("channel")
            or filters.get("variant") or filters.get("step_number")
        )

        # Post-query sort fields (derived from latest activity, not SQL columns)
        POST_QUERY_SORT_FIELDS = {"status", "occurred_at", "next_step_priority"}
        needs_post_sort = sort_by in POST_QUERY_SORT_FIELDS

        if not has_post_filters and not needs_post_sort:
            count_stmt = select(func.count()).select_from(base.subquery())
            total_result = await self.db.execute(count_stmt)
            total = total_result.scalar() or 0

        # Sort
        sort_columns = {
            "name": Contact.name,
            "email": Contact.email,
            "created_at": Contact.created_at,
            "company_name": PipelineEntry.name,
        }
        if not needs_post_sort:
            sort_col = sort_columns.get(sort_by, Contact.name)
            order_expr = sort_col.desc() if sort_dir.lower() != "asc" else sort_col.asc()
        else:
            # Default SQL ordering; real sort applied post-query
            order_expr = Contact.name.asc()

        # Fetch contacts with pipeline entry data
        data_stmt = (
            select(
                Contact,
                PipelineEntry.name.label("company_name"),
                PipelineEntry.domain.label("company_domain"),
                PipelineEntry.id.label("pipeline_entry_id"),
                PipelineEntry.source.label("entry_source"),
            )
            .join(PipelineEntry, Contact.pipeline_entry_id == PipelineEntry.id)
            .where(PipelineEntry.tenant_id == self.tenant_id)
        )

        if not include_retired:
            data_stmt = data_stmt.where(PipelineEntry.retired_at.is_(None))

        if filters.get("company"):
            data_stmt = data_stmt.where(
                PipelineEntry.name.ilike(f"%{filters['company']}%")
            )

        data_stmt = data_stmt.order_by(order_expr)

        if not has_post_filters and not needs_post_sort:
            data_stmt = data_stmt.offset(offset).limit(limit)

        result = await self.db.execute(data_stmt)
        rows = result.all()

        # Collect contact IDs for batch activity fetch
        contact_ids = [row[0].id for row in rows]

        # Batch-fetch latest outreach activity per contact
        latest_activities: dict = {}
        contact_channels: dict = {}
        if contact_ids:
            # Use a window function to rank activities per contact
            from sqlalchemy import desc as sa_desc

            activity_stmt = (
                select(Activity)
                .where(
                    Activity.contact_id.in_(contact_ids),
                    Activity.type.in_(["message", "outreach", "email"]),
                )
                .order_by(Activity.contact_id, Activity.occurred_at.desc())
            )
            act_result = await self.db.execute(activity_stmt)
            all_activities = act_result.scalars().all()

            # Keep only the latest per contact_id + collect all channels
            for act in all_activities:
                cid = act.contact_id
                if cid not in latest_activities:
                    latest_activities[cid] = act
                if act.channel:
                    contact_channels.setdefault(cid, set()).add(act.channel)

        # Build result dicts
        items = []
        for row in rows:
            contact = row[0]
            company_name = row[1]
            company_domain = row[2]
            pe_id = row[3]
            entry_source = row[4]

            latest_act = latest_activities.get(contact.id)

            latest_activity_dict = None
            act_status = None
            act_occurred = None
            act_channel = None

            if latest_act:
                act_status = latest_act.status
                act_occurred = latest_act.occurred_at
                act_channel = latest_act.channel
                latest_activity_dict = {
                    "id": str(latest_act.id),
                    "channel": latest_act.channel,
                    "variant": (latest_act.metadata_ or {}).get("variant"),
                    "variant_theme": (latest_act.metadata_ or {}).get("variant_theme"),
                    "step_number": (latest_act.metadata_ or {}).get("step_number"),
                    "status": latest_act.status,
                    "subject": latest_act.subject,
                    "occurred_at": (
                        latest_act.occurred_at.isoformat()
                        if latest_act.occurred_at
                        else None
                    ),
                }

            # Apply post-query filters
            if filters.get("status") and act_status != filters["status"]:
                continue
            if filters.get("channel") and act_channel != filters["channel"]:
                continue
            if filters.get("variant"):
                act_variant = (latest_act.metadata_ or {}).get("variant") if latest_act else None
                if act_variant != filters["variant"]:
                    continue
            if filters.get("step_number"):
                act_step = (latest_act.metadata_ or {}).get("step_number") if latest_act else None
                if act_step != filters["step_number"]:
                    continue

            next_step = compute_next_step(act_status, act_occurred)

            items.append(
                {
                    "id": str(contact.id),
                    "name": contact.name,
                    "email": contact.email,
                    "title": contact.title,
                    "linkedin_url": contact.linkedin_url,
                    "phone": contact.phone,
                    "is_primary": contact.is_primary,
                    "company_name": company_name,
                    "company_domain": company_domain,
                    "pipeline_entry_id": str(pe_id),
                    "channels": sorted(contact_channels.get(contact.id, set())),
                    "source": entry_source,
                    "campaign": (latest_act.metadata_ or {}).get("lane") if latest_act else None,
                    "latest_activity": latest_activity_dict,
                    "next_step": next_step,
                    "created_at": (
                        contact.created_at.isoformat()
                        if contact.created_at
                        else None
                    ),
                }
            )

        # Post-query sorting (fields derived from latest activity)
        NEXT_STEP_PRIORITY = {
            "Replied - engage": 0,
            "Bounced - fix email": 1,
            "Follow up now": 2,
            "Ready to send": 4,
        }

        if needs_post_sort:
            reverse = sort_dir.lower() != "asc"
            if sort_by == "next_step_priority":
                items.sort(
                    key=lambda x: NEXT_STEP_PRIORITY.get(x["next_step"], 3),
                    reverse=reverse,
                )
            elif sort_by == "status":
                items.sort(
                    key=lambda x: (x.get("latest_activity") or {}).get("status") or "zzz",
                    reverse=reverse,
                )
            elif sort_by == "occurred_at":
                items.sort(
                    key=lambda x: (x.get("latest_activity") or {}).get("occurred_at") or "",
                    reverse=reverse,
                )

        if has_post_filters or needs_post_sort:
            total = len(items)
            items = items[offset : offset + limit]

        return items, total

    # ----- Get -----

    async def get_entry(self, entry_id: UUID) -> PipelineEntry:
        """Load a single pipeline entry with contacts, activities, and sources."""
        result = await self.db.execute(
            select(PipelineEntry)
            .where(
                PipelineEntry.id == entry_id,
                PipelineEntry.tenant_id == self.tenant_id,
            )
            .options(
                selectinload(PipelineEntry.contacts),
                selectinload(PipelineEntry.sources),
            )
        )
        entry = result.scalar_one_or_none()

        if entry is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Pipeline entry not found")

        # Load recent activities separately (limit 10, ordered desc)
        act_result = await self.db.execute(
            select(Activity)
            .where(Activity.pipeline_entry_id == entry_id)
            .order_by(Activity.occurred_at.desc())
            .limit(10)
        )
        entry._recent_activities = act_result.scalars().all()

        return entry

    # ----- Create -----

    async def create_entry(
        self, data: CreatePipelineRequest
    ) -> tuple[PipelineEntry, bool]:
        """Create a pipeline entry with dedup check.

        Returns (entry, was_dedup) where was_dedup=True means an existing
        entry was returned instead of creating new.
        """
        # Validate stage
        if data.stage not in VALID_STAGES:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=f"Invalid stage '{data.stage}'. Must be one of: {VALID_STAGES}",
            )

        normalized = normalize_company_name(data.name)

        # Dedup check
        dedup_matches = await self.check_dedup(data.name, data.domain)
        for match in dedup_matches:
            if match.similarity_score > 0.7:
                # Check domain condition: domain matches OR no domain provided
                if data.domain is None or match.domain == data.domain:
                    # Return existing entry
                    existing = await self.get_entry(UUID(match.id))
                    return existing, True

        # Create new entry
        new_entry = PipelineEntry(
            tenant_id=self.tenant_id,
            owner_id=self.user.sub,
            entity_type=data.entity_type,
            name=data.name,
            normalized_name=normalized,
            domain=data.domain,
            stage=data.stage,
            fit_score=data.fit_score,
            fit_tier=data.fit_tier,
            fit_rationale=data.fit_rationale,
            relationship_type=data.relationship_type,
            source=data.source,
            channels=data.channels,
            intel=data.intel or {},
            ai_summary=data.ai_summary,
        )
        self.db.add(new_entry)
        await self.db.flush()

        # SCHEMA-05: Person auto-contact
        if data.entity_type == "person":
            contact = Contact(
                tenant_id=self.tenant_id,
                pipeline_entry_id=new_entry.id,
                name=data.name,
                email=data.email,
                title=data.title,
                linkedin_url=data.linkedin_url,
                phone=data.phone,
                is_primary=True,
            )
            self.db.add(contact)

        # Create provenance source record
        source_record = PipelineEntrySource(
            tenant_id=self.tenant_id,
            pipeline_entry_id=new_entry.id,
            source_type=data.source,
            source_ref_id=data.source_ref_id,
        )
        self.db.add(source_record)

        await self.db.flush()
        await self.db.refresh(new_entry)
        await self.db.commit()

        return new_entry, False

    # ----- Source append -----

    async def add_source(
        self,
        entry_id: UUID,
        source_type: str,
        source_ref_id: UUID | None = None,
    ) -> PipelineEntrySource:
        """Append a provenance source to an existing pipeline entry.

        Idempotent: if (entry_id, source_type, source_ref_id) already exists,
        returns the existing row without creating a duplicate.
        """
        await self._verify_entry_ownership(entry_id)

        # Dedup check: exact match on all three columns
        stmt = select(PipelineEntrySource).where(
            PipelineEntrySource.pipeline_entry_id == entry_id,
            PipelineEntrySource.source_type == source_type,
        )
        if source_ref_id is not None:
            stmt = stmt.where(PipelineEntrySource.source_ref_id == source_ref_id)
        else:
            stmt = stmt.where(PipelineEntrySource.source_ref_id.is_(None))

        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        source = PipelineEntrySource(
            tenant_id=self.tenant_id,
            pipeline_entry_id=entry_id,
            source_type=source_type,
            source_ref_id=source_ref_id,
        )
        self.db.add(source)
        await self.db.flush()
        return source

    # ----- Upsert from source -----

    async def upsert_from_source(
        self, data: CreatePipelineRequest
    ) -> tuple[PipelineEntry, bool]:
        """Create or find entry; always ensure source is recorded.

        Returns (entry, was_existing). If dedup matched an existing entry,
        appends a new source row (SOURCE-05: never replaces). If created new,
        source was already written by create_entry().
        """
        entry, was_dedup = await self.create_entry(data)
        if was_dedup:
            # Existing entry found -- append this new source
            await self.add_source(entry.id, data.source, data.source_ref_id)
            await self.db.commit()
        return entry, was_dedup

    # ----- Update -----

    async def update_entry(
        self, entry_id: UUID, data: UpdatePipelineRequest
    ) -> PipelineEntry:
        """Update pipeline entry fields. Tracks stage changes as activities."""
        result = await self.db.execute(
            select(PipelineEntry).where(
                PipelineEntry.id == entry_id,
                PipelineEntry.tenant_id == self.tenant_id,
            )
        )
        entry = result.scalar_one_or_none()

        if entry is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Pipeline entry not found")

        # CRITICAL: Read old_stage BEFORE applying updates (pitfall 2)
        old_stage = entry.stage

        # Validate new stage if provided
        if data.stage is not None and data.stage not in VALID_STAGES:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail=f"Invalid stage '{data.stage}'. Must be one of: {VALID_STAGES}",
            )

        # Apply non-None fields
        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(entry, field, value)

        # Recalculate normalized_name if name changed
        if data.name is not None:
            entry.normalized_name = normalize_company_name(data.name)

        # Track stage change
        if data.stage is not None and old_stage != data.stage:
            stage_activity = Activity(
                tenant_id=self.tenant_id,
                pipeline_entry_id=entry_id,
                type="stage_change",
                status="completed",
                subject=f"Stage changed: {old_stage} -> {data.stage}",
                metadata_={"old_stage": old_stage, "new_stage": data.stage},
            )
            self.db.add(stage_activity)

        entry.updated_at = datetime.datetime.now(datetime.timezone.utc)

        await self.db.commit()
        await self.db.refresh(entry)

        return entry

    # ----- Dedup Check -----

    async def check_dedup(
        self, name: str, domain: str | None = None
    ) -> list[DedupMatch]:
        """Find potential duplicate pipeline entries using pg_trgm similarity."""
        normalized = normalize_company_name(name)

        if not normalized:
            return []

        # Use pg_trgm similarity function
        similarity_expr = func.similarity(PipelineEntry.normalized_name, normalized)

        stmt = (
            select(PipelineEntry, similarity_expr.label("sim_score"))
            .where(
                PipelineEntry.tenant_id == self.tenant_id,
                similarity_expr > 0.3,
            )
            .order_by(similarity_expr.desc())
            .limit(5)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        matches = []
        for row in rows:
            entry = row[0]
            sim_score = float(row[1])

            match_reasons = []
            if sim_score > 0.3:
                match_reasons.append("name_fuzzy")
            entry_normalized = normalize_company_name(entry.name)
            if entry_normalized == normalized:
                match_reasons.append("name_exact")
            if domain and entry.domain and entry.domain.lower() == domain.lower():
                match_reasons.append("domain_exact")
                # Boost score for domain match
                sim_score = min(sim_score + 0.3, 1.0)

            matches.append(
                DedupMatch(
                    id=str(entry.id),
                    name=entry.name,
                    domain=entry.domain,
                    stage=entry.stage,
                    entity_type=entry.entity_type,
                    similarity_score=round(sim_score, 3),
                    match_reasons=match_reasons,
                )
            )

        # Re-sort by boosted score
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:5]

    # ----- Timeline -----

    async def get_timeline(
        self, entry_id: UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[TimelineItem], int]:
        """Merge activities, meetings, and context_entries into a single chronological feed."""
        # Verify entry belongs to tenant
        await self._verify_entry_ownership(entry_id)

        items: list[TimelineItem] = []

        # 1. Activities
        act_result = await self.db.execute(
            select(Activity).where(
                Activity.pipeline_entry_id == entry_id,
                Activity.tenant_id == self.tenant_id,
            )
        )
        for a in act_result.scalars().all():
            items.append(TimelineItem(
                id=str(a.id),
                source_type="activity",
                date=a.occurred_at.isoformat() if a.occurred_at else "",
                title=a.subject or a.type,
                summary=a.body_preview,
                type=a.type,
                channel=a.channel,
                direction=a.direction,
                status=a.status,
                metadata=a.metadata_ or {},
            ))

        # 2. Meetings
        mtg_result = await self.db.execute(
            select(Meeting).where(
                Meeting.pipeline_entry_id == entry_id,
                Meeting.tenant_id == self.tenant_id,
                Meeting.deleted_at.is_(None),
            )
        )
        for m in mtg_result.scalars().all():
            items.append(TimelineItem(
                id=str(m.id),
                source_type="meeting",
                date=m.meeting_date.isoformat() if m.meeting_date else "",
                title=m.title or "Meeting",
                summary=m.ai_summary,
                type="meeting",
            ))

        # 3. Context entries
        ctx_result = await self.db.execute(
            select(ContextEntry).where(
                ContextEntry.pipeline_entry_id == entry_id,
                ContextEntry.tenant_id == self.tenant_id,
                ContextEntry.deleted_at.is_(None),
            )
        )
        for c in ctx_result.scalars().all():
            items.append(TimelineItem(
                id=str(c.id),
                source_type="context",
                date=c.created_at.isoformat() if c.created_at else "",
                title=(c.content[:100] if c.content else "Context entry"),
                summary=c.content,
                type="context",
            ))

        # Sort by date DESC
        items.sort(key=lambda x: x.date, reverse=True)

        total = len(items)
        paginated = items[offset : offset + limit]
        return paginated, total

    # ----- Search -----

    async def search_entries(
        self, query: str, offset: int = 0, limit: int = 50
    ) -> tuple[list, int]:
        """Search pipeline entries across name, domain, contact names, and AI summary."""
        pattern = f"%{query}%"

        # Subquery: pipeline_entry_ids that have a matching contact name
        contact_match_subq = (
            select(Contact.pipeline_entry_id)
            .where(Contact.name.ilike(pattern))
            .correlate(None)
            .subquery()
        )

        base = (
            select(PipelineEntry)
            .where(
                PipelineEntry.tenant_id == self.tenant_id,
                PipelineEntry.retired_at.is_(None),
            )
            .where(
                PipelineEntry.name.ilike(pattern)
                | PipelineEntry.domain.ilike(pattern)
                | PipelineEntry.ai_summary.ilike(pattern)
                | PipelineEntry.id.in_(select(contact_match_subq.c.pipeline_entry_id))
            )
        )

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch paginated
        data_stmt = base.order_by(PipelineEntry.created_at.desc()).offset(offset).limit(limit)

        # Contact count correlated subquery (same as list_entries)
        contact_count_subq = (
            select(func.count())
            .where(Contact.pipeline_entry_id == PipelineEntry.id)
            .correlate(PipelineEntry)
            .scalar_subquery()
        )

        data_stmt = (
            select(PipelineEntry, contact_count_subq.label("contact_count"))
            .where(
                PipelineEntry.tenant_id == self.tenant_id,
                PipelineEntry.retired_at.is_(None),
            )
            .where(
                PipelineEntry.name.ilike(pattern)
                | PipelineEntry.domain.ilike(pattern)
                | PipelineEntry.ai_summary.ilike(pattern)
                | PipelineEntry.id.in_(select(contact_match_subq.c.pipeline_entry_id))
            )
            .order_by(PipelineEntry.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(data_stmt)
        rows = result.all()

        entries = []
        for row in rows:
            entry = row[0]
            cc = row[1] or 0

            # Get primary contact
            pc_result = await self.db.execute(
                select(Contact)
                .where(
                    Contact.pipeline_entry_id == entry.id,
                    Contact.is_primary.is_(True),
                )
                .limit(1)
            )
            pc = pc_result.scalar_one_or_none()
            primary_contact = None
            if pc:
                primary_contact = {
                    "name": pc.name,
                    "email": pc.email,
                    "title": pc.title,
                }

            entries.append((entry, cc, primary_contact))

        return entries, total

    # ----- Contacts CRUD -----

    async def list_contacts(self, entry_id: UUID) -> list:
        """List all contacts for a pipeline entry, primary first."""
        await self._verify_entry_ownership(entry_id)

        result = await self.db.execute(
            select(Contact)
            .where(Contact.pipeline_entry_id == entry_id)
            .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
        )
        return result.scalars().all()

    async def create_contact(
        self, entry_id: UUID, data: CreateContactRequest
    ) -> Contact:
        """Create a contact under a pipeline entry."""
        await self._verify_entry_ownership(entry_id)

        contact = Contact(
            tenant_id=self.tenant_id,
            pipeline_entry_id=entry_id,
            name=data.name,
            email=data.email,
            title=data.title,
            role=data.role,
            linkedin_url=data.linkedin_url,
            phone=data.phone,
            notes=data.notes,
            is_primary=data.is_primary,
        )
        self.db.add(contact)
        await self.db.flush()
        await self.db.refresh(contact)
        await self.db.commit()
        return contact

    async def update_contact(
        self, entry_id: UUID, contact_id: UUID, data: UpdateContactRequest
    ) -> Contact:
        """Update a contact, verifying it belongs to the entry and tenant."""
        contact = await self._load_contact(entry_id, contact_id)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(contact, field, value)

        contact.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await self.db.commit()
        await self.db.refresh(contact)
        return contact

    async def delete_contact(self, entry_id: UUID, contact_id: UUID) -> None:
        """Delete a contact, verifying ownership."""
        contact = await self._load_contact(entry_id, contact_id)
        await self.db.delete(contact)
        await self.db.commit()

    # ----- Activities CRUD -----

    async def list_activities(
        self,
        entry_id: UUID,
        offset: int = 0,
        limit: int = 50,
        contact_id: UUID | None = None,
    ) -> tuple[list, int]:
        """List activities for a pipeline entry, paginated.

        If *contact_id* is provided, only activities linked to that contact
        are returned.
        """
        await self._verify_entry_ownership(entry_id)

        # Count
        count_stmt = select(func.count()).where(
            Activity.pipeline_entry_id == entry_id,
        )
        if contact_id is not None:
            count_stmt = count_stmt.where(Activity.contact_id == contact_id)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch
        fetch_stmt = (
            select(Activity)
            .where(Activity.pipeline_entry_id == entry_id)
            .order_by(Activity.occurred_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if contact_id is not None:
            fetch_stmt = fetch_stmt.where(Activity.contact_id == contact_id)
        result = await self.db.execute(fetch_stmt)
        return result.scalars().all(), total

    async def create_activity(
        self, entry_id: UUID, data: CreateActivityRequest
    ) -> Activity:
        """Create an activity under a pipeline entry."""
        await self._verify_entry_ownership(entry_id)

        activity = Activity(
            tenant_id=self.tenant_id,
            pipeline_entry_id=entry_id,
            type=data.type,
            channel=data.channel,
            direction=data.direction,
            status=data.status,
            subject=data.subject,
            body_preview=data.body_preview,
            metadata_=data.metadata_ or {},
            contact_id=data.contact_id,
        )
        if data.occurred_at is not None:
            activity.occurred_at = data.occurred_at

        self.db.add(activity)
        await self.db.flush()
        await self.db.refresh(activity)
        await self.db.commit()
        return activity

    async def update_activity(
        self, entry_id: UUID, activity_id: UUID, data: UpdateActivityRequest
    ) -> Activity:
        """Update an activity, verifying it belongs to the entry and tenant."""
        activity = await self._load_activity(entry_id, activity_id)

        update_fields = data.model_dump(exclude_unset=True)

        # Validate status transition if status is being changed
        if "status" in update_fields:
            new_status = update_fields["status"]
            current_status = activity.status
            allowed = VALID_STATUS_TRANSITIONS.get(current_status)
            if allowed is not None and new_status not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot transition from '{current_status}' to '{new_status}'",
                )

        for field, value in update_fields.items():
            setattr(activity, field, value)

        await self.db.commit()
        await self.db.refresh(activity)
        return activity

    async def delete_activity(self, entry_id: UUID, activity_id: UUID) -> None:
        """Delete an activity, verifying ownership."""
        activity = await self._load_activity(entry_id, activity_id)
        await self.db.delete(activity)
        await self.db.commit()

    # ----- Retire / Reactivate -----

    async def retire_entry(self, entry_id: UUID) -> PipelineEntry:
        """Manually retire a pipeline entry."""
        entry = await self._verify_entry_ownership(entry_id)
        entry.retired_at = datetime.datetime.now(datetime.timezone.utc)

        activity = Activity(
            tenant_id=self.tenant_id,
            pipeline_entry_id=entry_id,
            type="retirement",
            status="completed",
            subject="Entry retired",
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def reactivate_entry(self, entry_id: UUID) -> PipelineEntry:
        """Reactivate a retired pipeline entry, clearing stale and retired flags."""
        entry = await self._verify_entry_ownership(entry_id)
        entry.retired_at = None
        entry.stale_notified_at = None

        activity = Activity(
            tenant_id=self.tenant_id,
            pipeline_entry_id=entry_id,
            type="reactivation",
            status="completed",
            subject="Entry reactivated",
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    # ----- Private helpers -----

    async def _verify_entry_ownership(self, entry_id: UUID) -> PipelineEntry:
        """Verify pipeline entry exists and belongs to tenant. Returns entry."""
        result = await self.db.execute(
            select(PipelineEntry).where(
                PipelineEntry.id == entry_id,
                PipelineEntry.tenant_id == self.tenant_id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Pipeline entry not found")
        return entry

    async def _load_contact(self, entry_id: UUID, contact_id: UUID) -> Contact:
        """Load a contact and verify it belongs to the entry and tenant."""
        await self._verify_entry_ownership(entry_id)
        result = await self.db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.pipeline_entry_id == entry_id,
            )
        )
        contact = result.scalar_one_or_none()
        if contact is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Contact not found")
        return contact

    async def _load_activity(self, entry_id: UUID, activity_id: UUID) -> Activity:
        """Load an activity and verify it belongs to the entry and tenant."""
        await self._verify_entry_ownership(entry_id)
        result = await self.db.execute(
            select(Activity).where(
                Activity.id == activity_id,
                Activity.pipeline_entry_id == entry_id,
            )
        )
        activity = result.scalar_one_or_none()
        if activity is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Activity not found")
        return activity
