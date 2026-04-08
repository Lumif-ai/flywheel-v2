"""SQLAlchemy 2.0 ORM models for all Flywheel tables.

Schema matches V2-PRODUCT-SPEC.md. Tables are divided into:
- System tables (tenants, profiles) -- NOT tenant-scoped, no RLS
- Tenant-scoped tables (9 tables) -- all have tenant_id FK, RLS enforced
- Focus tables (2 tables) -- focus/lens scoping for context
- Context graph tables (3 tables) -- entity graph layer on top of context_entries
- CRM tables (4 tables) -- accounts, contacts, outreach activities, meetings for v2.0 GTM CRM
- Unified pipeline tables (4 tables) -- pipeline_entries, contacts, activities, sources for v9.0 unified CRM
- Saved views (1 table) -- user-created pipeline view configurations
"""

from __future__ import annotations

import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ---------------------------------------------------------------------------
# SYSTEM TABLES (not tenant-scoped, no RLS)
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    company_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    trial_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now() + interval '90 days'"),
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    company: Mapped["Company | None"] = relationship(lazy="selectin")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    last_briefing_visit: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class Company(Base):
    """Shared company intel cache -- NOT tenant-scoped, no RLS.

    Stores structured intelligence per domain so any tenant can get an
    instant cache hit without cross-tenant queries.
    """
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    domain: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    intel: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    crawled_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# TENANT-SCOPED TABLES (all have tenant_id FK, RLS enforced)
# ---------------------------------------------------------------------------


class UserTenant(Base):
    __tablename__ = "user_tenants"
    __table_args__ = (
        Index(
            "idx_one_active_tenant",
            "user_id",
            unique=True,
            postgresql_where=text("active = true"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), primary_key=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, server_default="member")
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    joined_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id"))
    type: Mapped[str] = mapped_column(Text, server_default="anonymous")
    data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    expires_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now() + interval '7 days'"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    invited_by: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, server_default="member")
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str | None] = mapped_column(Text)  # raw token for invite URL copy
    accepted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    expires_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now() + interval '7 days'"),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class ContextEntry(Base):
    __tablename__ = "context_entries"
    __table_args__ = (
        Index("idx_context_tenant_file", "tenant_id", "file_name"),
        Index("idx_context_visibility", "tenant_id", "visibility"),
        Index(
            "idx_context_not_deleted",
            "tenant_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(Text, server_default="team")
    date: Mapped[datetime.date] = mapped_column(
        Date, server_default=text("CURRENT_DATE")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text, server_default="medium")
    evidence_count: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    focus_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("focuses.id"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    flag_reason: Mapped[str | None] = mapped_column(Text)
    flag_related_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entries.id")
    )
    flag_related: Mapped["ContextEntry | None"] = relationship(
        "ContextEntry", remote_side="ContextEntry.id", foreign_keys=[flag_related_id]
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    # GENERATED ALWAYS AS -- SQLAlchemy Computed prevents INSERT/UPDATE
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(detail, '') || ' ' || content)",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account: Mapped["Account | None"] = relationship()
    pipeline_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pipeline_entry: Mapped["PipelineEntry | None"] = relationship()


class ContextCatalog(Base):
    __tablename__ = "context_catalog"
    __table_args__ = (
        Index("idx_catalog_tags", "tags", postgresql_using="gin"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), primary_key=True
    )
    file_name: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(Text, server_default="empty")


class ContextEvent(Base):
    __tablename__ = "context_events"
    __table_args__ = (
        Index("idx_events_tenant_time", "tenant_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID | None] = mapped_column()
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("context_entries.id"))
    detail: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class SkillRun(Base):
    __tablename__ = "skill_runs"
    __table_args__ = (
        Index(
            "idx_runs_pending",
            "status",
            "scheduled_for",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    rendered_html: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    reasoning_trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    events_log: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    locked_by: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    scheduled_for: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EnrichmentCache(Base):
    __tablename__ = "enrichment_cache"
    __table_args__ = (
        UniqueConstraint("tenant_id", "query_hash", name="uq_enrichment_tenant_hash"),
        Index("idx_enrichment_cache_ttl", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(nullable=False)
    query_hash: Mapped[str] = mapped_column(Text, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mimetype: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="connected")
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    last_synced_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        Index(
            "idx_work_items_upcoming",
            "tenant_id",
            "scheduled_at",
            postgresql_where=text("status = 'upcoming'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="upcoming")
    data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    external_id: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# FOCUS TABLES (focus/lens scoping for context)
# ---------------------------------------------------------------------------


class Focus(Base):
    __tablename__ = "focuses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_focus_tenant_name"),
        Index("idx_focuses_tenant", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    archived_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class UserFocus(Base):
    __tablename__ = "user_focuses"
    __table_args__ = (
        Index(
            "idx_one_active_focus",
            "user_id",
            "tenant_id",
            unique=True,
            postgresql_where=text("active = true"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), primary_key=True
    )
    focus_id: Mapped[UUID] = mapped_column(
        ForeignKey("focuses.id"), primary_key=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    joined_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class SuggestionDismissal(Base):
    __tablename__ = "suggestion_dismissals"
    __table_args__ = (
        Index(
            "idx_suggestion_dismissals_lookup",
            "tenant_id",
            "user_id",
            "suggestion_type",
            "suggestion_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    suggestion_type: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_key: Mapped[str] = mapped_column(Text, nullable=False)
    dismissed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now() + interval '7 days'"),
    )


# ---------------------------------------------------------------------------
# CONTEXT GRAPH TABLES (entity graph layer on top of context_entries)
# ---------------------------------------------------------------------------


class ContextEntity(Base):
    __tablename__ = "context_entities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", "entity_type",
            name="uq_entity_tenant_name_type",
        ),
        Index("idx_entities_aliases", "aliases", postgresql_using="gin"),
        Index("idx_entities_tenant_type", "tenant_id", "entity_type"),
        Index("idx_entities_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    mention_count: Mapped[int] = mapped_column(
        Integer, server_default=text("1")
    )
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class ContextRelationship(Base):
    __tablename__ = "context_relationships"
    __table_args__ = (
        Index("idx_relationships_tenant_a", "tenant_id", "entity_a_id"),
        Index("idx_relationships_tenant_b", "tenant_id", "entity_b_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    entity_a_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_entities.id", ondelete="CASCADE"), nullable=False
    )
    entity_b_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_entities.id", ondelete="CASCADE"), nullable=False
    )
    relationship: Mapped[str] = mapped_column(Text, nullable=False)
    source_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entries.id")
    )
    focus_id: Mapped[UUID | None] = mapped_column(ForeignKey("focuses.id"))
    directional: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true")
    )
    confidence: Mapped[str] = mapped_column(Text, server_default="medium")
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# WORK STREAM TABLES (work stream organizing principle for v3.0)
# ---------------------------------------------------------------------------


class WorkStream(Base):
    __tablename__ = "work_streams"
    __table_args__ = (
        Index("idx_streams_tenant", "tenant_id"),
        Index(
            "idx_streams_tenant_active",
            "tenant_id",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index(
            "uq_stream_tenant_name",
            "tenant_id",
            "name",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("idx_streams_parent", "parent_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_streams.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    density_score: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default=text("0.00")
    )
    density_details: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    archived_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class WorkStreamEntity(Base):
    __tablename__ = "work_stream_entities"
    __table_args__ = (
        Index("idx_wse_tenant", "tenant_id"),
        Index("idx_wse_entity", "entity_id"),
    )

    stream_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_streams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    linked_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class DensitySnapshot(Base):
    __tablename__ = "density_snapshots"
    __table_args__ = (
        Index("idx_ds_stream_week", "stream_id", "week_start"),
        UniqueConstraint("stream_id", "week_start", name="uq_ds_stream_week"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    stream_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_streams.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    density_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    details: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class NudgeInteraction(Base):
    __tablename__ = "nudge_interactions"
    __table_args__ = (
        Index("idx_ni_tenant_user", "tenant_id", "user_id"),
        Index("idx_ni_tenant_type", "tenant_id", "nudge_type", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    nudge_type: Mapped[str] = mapped_column(Text, nullable=False)
    nudge_key: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class MeetingClassification(Base):
    __tablename__ = "meeting_classifications"
    __table_args__ = (
        Index("idx_mc_tenant_domain", "tenant_id", "email_domain"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    work_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    stream_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_streams.id", ondelete="SET NULL")
    )
    email_domain: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class ContextEntityEntry(Base):
    __tablename__ = "context_entity_entries"

    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("context_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    mention_type: Mapped[str] = mapped_column(
        Text, server_default="explicit"
    )


# ---------------------------------------------------------------------------
# SKILL REGISTRY TABLES (DB-backed skill definitions and tenant access)
# ---------------------------------------------------------------------------


class SkillDefinition(Base):
    __tablename__ = "skill_definitions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_skill_defs_name"),
        Index("idx_skill_defs_name", "name"),
        Index(
            "idx_skill_defs_enabled",
            "enabled",
            postgresql_where=text("enabled = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    version: Mapped[str] = mapped_column(Text, nullable=False, server_default="0.0.0")
    description: Mapped[str | None] = mapped_column(Text)
    web_tier: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    system_prompt: Mapped[str | None] = mapped_column(Text)
    contract_reads: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    contract_writes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    engine_module: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    protected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    token_budget: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class TenantSkill(Base):
    __tablename__ = "tenant_skills"
    __table_args__ = (
        Index(
            "idx_ts_tenant_enabled",
            "tenant_id",
            postgresql_where=text("enabled = true"),
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), primary_key=True
    )
    skill_id: Mapped[UUID] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    pricing_tier: Mapped[str] = mapped_column(Text, server_default="included")
    activated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# DOCUMENT TABLES (persistent, shareable document artifacts from skill runs)
# ---------------------------------------------------------------------------


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_tenant", "tenant_id"),
        Index("idx_documents_type", "tenant_id", "document_type"),
        Index(
            "idx_documents_share",
            "share_token",
            unique=True,
            postgresql_where=text("share_token IS NOT NULL"),
        ),
        # Note: GIN index on metadata column is created in the migration, not here,
        # because the ORM attribute name (metadata_) differs from the DB column (metadata).
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="text/html"
    )
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    skill_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("skill_runs.id", ondelete="SET NULL")
    )
    share_token: Mapped[str | None] = mapped_column(Text, unique=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )


# ---------------------------------------------------------------------------
# EMAIL COPILOT TABLES (tenant-scoped, RLS enforced)
# ---------------------------------------------------------------------------


class Email(Base):
    """Synced Gmail message metadata. No body stored — fetched on-demand."""

    __tablename__ = "emails"
    __table_args__ = (
        Index("idx_emails_tenant_received", "tenant_id", text("received_at DESC")),
        Index("idx_emails_tenant_user", "tenant_id", "user_id"),
        Index("idx_emails_thread", "tenant_id", "gmail_thread_id"),
        UniqueConstraint(
            "tenant_id", "gmail_message_id", name="uq_email_tenant_message"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    gmail_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    sender_email: Mapped[str] = mapped_column(Text, nullable=False)
    sender_name: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    labels: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    is_replied: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
    synced_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    context_extracted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class EmailScore(Base):
    """AI-generated priority score and category for a synced email."""

    __tablename__ = "email_scores"
    __table_args__ = (
        Index("idx_email_scores_tenant_priority", "tenant_id", text("priority DESC")),
        UniqueConstraint("email_id", name="uq_email_score_email"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("emails.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)
    context_refs: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    sender_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entities.id"), nullable=True
    )
    scored_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EmailDraft(Base):
    """AI-generated draft reply for a synced email. Body nulled after send."""

    __tablename__ = "email_drafts"
    __table_args__ = (
        Index("idx_email_drafts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("emails.id"), nullable=False
    )
    draft_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    context_used: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    user_edits: Mapped[str | None] = mapped_column(Text)
    visible_after: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EmailContextReview(Base):
    """Low-confidence context extractions pending human review."""

    __tablename__ = "email_context_reviews"
    __table_args__ = (
        Index("idx_context_reviews_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    email_id: Mapped[UUID] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    extracted_data: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        Text, server_default=text("'pending'")
    )
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


class EmailVoiceProfile(Base):
    """Learned writing voice profile for a user within a tenant."""

    __tablename__ = "email_voice_profiles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", name="uq_voice_profile_tenant_user"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    tone: Mapped[str | None] = mapped_column(Text)
    avg_length: Mapped[int | None] = mapped_column(Integer)
    sign_off: Mapped[str | None] = mapped_column(Text)
    phrases: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    formality_level: Mapped[str | None] = mapped_column(
        Text, server_default=text("'conversational'")
    )
    greeting_style: Mapped[str | None] = mapped_column(
        Text, server_default=text("'Hi {name},'")
    )
    question_style: Mapped[str | None] = mapped_column(
        Text, server_default=text("'direct'")
    )
    paragraph_pattern: Mapped[str | None] = mapped_column(
        Text, server_default=text("'short single-line'")
    )
    emoji_usage: Mapped[str | None] = mapped_column(
        Text, server_default=text("'never'")
    )
    avg_sentences: Mapped[int | None] = mapped_column(
        Integer, server_default=text("3")
    )
    samples_analyzed: Mapped[int] = mapped_column(
        Integer, server_default=text("0")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )


# ---------------------------------------------------------------------------
# CRM TABLES (tenant-scoped, RLS enforced)
# ---------------------------------------------------------------------------


class Account(Base):
    """Prospect or customer company tracked in the GTM CRM."""

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="uq_account_tenant_normalized"),
        Index("idx_account_tenant_status", "tenant_id", "status"),
        Index(
            "idx_account_next_action",
            "tenant_id",
            "next_action_due",
            postgresql_where=text("next_action_due IS NOT NULL"),
        ),
        Index("idx_account_relationship_type", "relationship_type", postgresql_using="gin"),
        Index("idx_account_relationship_status", "tenant_id", "relationship_status"),
        Index("idx_account_pipeline_stage", "tenant_id", "pipeline_stage"),
        Index(
            "idx_account_graduated_at",
            "graduated_at",
            postgresql_where=text("graduated_at IS NOT NULL"),
        ),
        Index("idx_account_tenant_visibility", "tenant_id", "visibility"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id"), nullable=True
    )
    visibility: Mapped[str] = mapped_column(Text, server_default="team")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="prospect")
    fit_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fit_tier: Mapped[str | None] = mapped_column(Text)
    intel: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    relationship_type: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{prospect}'::text[]")
    )
    entity_level: Mapped[str] = mapped_column(
        Text, server_default=text("'company'")
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_updated_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    graduated_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    relationship_status: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(Text, nullable=False)
    last_interaction_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    next_action_due: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    next_action_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    contacts: Mapped[list["AccountContact"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    outreach_activities: Mapped[list["OutreachActivity"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class Lead(Base):
    """A GTM pipeline lead — a company being prospected before it becomes an account."""

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_id", "normalized_name", name="uq_lead_tenant_owner_normalized"),
        Index("idx_lead_tenant_purpose", "purpose", postgresql_using="gin"),
        Index("idx_lead_tenant_fit", "tenant_id", "fit_tier"),
        Index("idx_lead_owner", "tenant_id", "owner_id"),
        Index(
            "idx_lead_graduated",
            "graduated_at",
            postgresql_where=text("graduated_at IS NOT NULL"),
        ),
        Index(
            "idx_lead_tenant_campaign",
            "tenant_id",
            "campaign",
            postgresql_where=text("campaign IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{sales}'::text[]")
    )
    fit_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fit_tier: Mapped[str | None] = mapped_column(Text)
    fit_rationale: Mapped[str | None] = mapped_column(Text)
    intel: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(Text, nullable=False)
    campaign: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    graduated_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    lead_contacts: Mapped[list["LeadContact"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    account: Mapped["Account | None"] = relationship()


class LeadContact(Base):
    """A person at a lead company — tracks individual outreach pipeline stage."""

    __tablename__ = "lead_contacts"
    __table_args__ = (
        Index("idx_lead_contact_lead", "lead_id"),
        Index("idx_lead_contact_tenant_stage", "tenant_id", "pipeline_stage"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    pipeline_stage: Mapped[str] = mapped_column(
        Text, server_default=text("'scraped'")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    lead: Mapped["Lead"] = relationship(back_populates="lead_contacts")
    messages: Mapped[list["LeadMessage"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class LeadMessage(Base):
    """An outreach message in a sequence for a lead contact."""

    __tablename__ = "lead_messages"
    __table_args__ = (
        UniqueConstraint("contact_id", "step_number", "channel", name="uq_lead_message_step"),
        Index("idx_lead_message_contact", "contact_id"),
        Index("idx_lead_message_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("lead_contacts.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'drafted'"))
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str | None] = mapped_column(Text)
    drafted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    replied_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    contact: Mapped["LeadContact"] = relationship(back_populates="messages")


class AccountContact(Base):
    """A person at an account relevant to a deal or relationship."""

    __tablename__ = "account_contacts"
    __table_args__ = (
        Index("idx_contact_account", "account_id"),
        Index(
            "idx_contact_tenant_email",
            "tenant_id",
            "email",
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    role_in_deal: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    account: Mapped["Account"] = relationship(back_populates="contacts")


class OutreachActivity(Base):
    """A single outreach touchpoint (email sent, call made, LinkedIn message, etc.)."""

    __tablename__ = "outreach_activities"
    __table_args__ = (
        Index("idx_outreach_account", "account_id"),
        Index("idx_outreach_tenant_sent", "tenant_id", text("sent_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("account_contacts.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="sent")
    subject: Mapped[str | None] = mapped_column(Text)
    body_preview: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    account: Mapped["Account"] = relationship(back_populates="outreach_activities")
    contact: Mapped["AccountContact | None"] = relationship()


class Meeting(Base):
    """A meeting ingested from an external source (Granola, Fathom, etc.)
    or uploaded manually. First-class entity in the CRM data model.

    Privacy model: metadata is tenant-visible, transcript is user-scoped.
    """

    __tablename__ = "meetings"
    __table_args__ = (
        Index(
            "idx_meetings_dedup",
            "tenant_id", "provider", "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "idx_meetings_account",
            "account_id", text("meeting_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_meetings_user",
            "tenant_id", "user_id", text("meeting_date DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_meetings_processable",
            "tenant_id", "processing_status",
            postgresql_where=text(
                "processing_status IN ('pending', 'scheduled', 'recorded')"
            ),
        ),
        Index(
            "idx_meetings_calendar_dedup",
            "tenant_id", "calendar_event_id",
            unique=True,
            postgresql_where=text("calendar_event_id IS NOT NULL"),
        ),
        Index(
            "idx_meetings_granola_dedup",
            "tenant_id", "granola_note_id",
            unique=True,
            postgresql_where=text("granola_note_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    calendar_event_id: Mapped[str | None] = mapped_column(Text)
    granola_note_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    meeting_date: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    duration_mins: Mapped[int | None] = mapped_column(Integer)
    attendees: Mapped[dict | None] = mapped_column(JSONB)
    transcript_url: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    meeting_type: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    skill_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("skill_runs.id"), nullable=True
    )
    processed_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    processing_status: Mapped[str] = mapped_column(
        Text, server_default=text("'pending'"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    account: Mapped["Account | None"] = relationship()
    skill_run: Mapped["SkillRun | None"] = relationship()
    pipeline_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="SET NULL"), nullable=True
    )
    pipeline_entry: Mapped["PipelineEntry | None"] = relationship()


class Task(Base):
    """A task or commitment extracted from a meeting or created manually.

    Tasks are personal (user-level RLS isolation). Each user sees only their
    own tasks. The commitment_direction field captures who made the commitment
    (yours, theirs, mutual, signal, speculation).
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "tenant_id", "user_id", "status"),
        Index(
            "idx_tasks_due",
            "tenant_id", "user_id", "due_date",
            postgresql_where=text(
                "due_date IS NOT NULL AND status NOT IN ('done', 'dismissed')"
            ),
        ),
        Index("idx_tasks_meeting", "meeting_id"),
        Index("idx_tasks_email", "email_id"),
        Index("idx_tasks_source", "tenant_id", "user_id", "source"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id"), nullable=False
    )
    meeting_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    email_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("emails.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    commitment_direction: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_skill: Mapped[str | None] = mapped_column(Text)
    skill_context: Mapped[dict | None] = mapped_column(JSONB)
    trust_level: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, server_default=text("'detected'"), nullable=False
    )
    priority: Mapped[str] = mapped_column(
        Text, server_default=text("'medium'"), nullable=False
    )
    due_date: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    meeting: Mapped["Meeting | None"] = relationship()
    account: Mapped["Account | None"] = relationship()
    email: Mapped["Email | None"] = relationship()
    pipeline_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="SET NULL"), nullable=True
    )
    pipeline_entry: Mapped["PipelineEntry | None"] = relationship()


# ---------------------------------------------------------------------------
# UNIFIED PIPELINE TABLES (v9.0 — replaces leads + accounts)
# ---------------------------------------------------------------------------


class PipelineEntry(Base):
    """Unified pipeline entry — company or person tracked in the GTM CRM.

    Replaces the dual leads/accounts model. entity_type distinguishes
    company vs person entries.
    """

    __tablename__ = "pipeline_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "owner_id", "normalized_name",
            name="uq_pipeline_tenant_owner_normalized",
        ),
        Index("idx_pipeline_tenant_stage", "tenant_id", "stage"),
        Index("idx_pipeline_tenant_fit", "tenant_id", "fit_tier"),
        Index(
            "idx_pipeline_relationship_type",
            "relationship_type",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(
        Text, server_default=text("'company'"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(
        Text, server_default=text("'identified'"), nullable=False
    )
    fit_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fit_tier: Mapped[str | None] = mapped_column(Text)
    fit_rationale: Mapped[str | None] = mapped_column(Text)
    relationship_type: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{prospect}'::text[]")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    channels: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    intel: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_cache_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True
    )
    context_entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("context_entities.id"), nullable=True
    )
    referred_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_entries.id"), nullable=True
    )
    next_action_date: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True
    )
    next_action_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    stale_notified_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    retired_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    # Relationships
    company: Mapped["Company | None"] = relationship(lazy="selectin")
    context_entity: Mapped["ContextEntity | None"] = relationship(lazy="selectin")
    referrer: Mapped["PipelineEntry | None"] = relationship(
        remote_side="PipelineEntry.id", lazy="selectin"
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="pipeline_entry", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="pipeline_entry", cascade="all, delete-orphan"
    )
    sources: Mapped[list["PipelineEntrySource"]] = relationship(
        back_populates="pipeline_entry", cascade="all, delete-orphan"
    )


class Contact(Base):
    """A person associated with a pipeline entry.

    For person-type pipeline entries, a self-referencing contact row
    (is_primary=True) represents the person themselves.
    """

    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    pipeline_entry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    pipeline_entry: Mapped["PipelineEntry | None"] = relationship(
        back_populates="contacts"
    )


class Activity(Base):
    """A timeline event for a pipeline entry (email, meeting, call, stage change, etc.).

    INSERT triggers a SECURITY DEFINER function that updates
    pipeline_entries.last_activity_at.
    """

    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    pipeline_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, server_default=text("'completed'"), nullable=False
    )
    subject: Mapped[str | None] = mapped_column(Text)
    body_preview: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    pipeline_entry: Mapped["PipelineEntry"] = relationship(
        back_populates="activities"
    )
    contact: Mapped["Contact | None"] = relationship(lazy="selectin")


class PipelineEntrySource(Base):
    """Provenance record for how a pipeline entry was discovered."""

    __tablename__ = "pipeline_entry_sources"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    pipeline_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    pipeline_entry: Mapped["PipelineEntry"] = relationship(
        back_populates="sources"
    )


# ---------------------------------------------------------------------------
# SAVED VIEWS (user-created pipeline view configurations)
# ---------------------------------------------------------------------------


class SavedView(Base):
    """A named filter/sort/column configuration for the pipeline grid.

    Each user can save multiple views that persist across sessions
    and appear in the sidebar navigation.
    """

    __tablename__ = "saved_views"
    __table_args__ = (
        Index("idx_saved_views_tenant_owner", "tenant_id", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"), nullable=False
    )
    owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    sort: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    columns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )
