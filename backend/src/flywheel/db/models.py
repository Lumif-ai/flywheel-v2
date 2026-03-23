"""SQLAlchemy 2.0 ORM models for all 16 Flywheel tables.

Schema matches V2-PRODUCT-SPEC.md. Tables are divided into:
- System tables (tenants, users) -- NOT tenant-scoped, no RLS
- Tenant-scoped tables (9 tables) -- all have tenant_id FK, RLS enforced
- Focus tables (2 tables) -- focus/lens scoping for context
- Context graph tables (3 tables) -- entity graph layer on top of context_entries
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
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
        ForeignKey("users.id"), primary_key=True
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
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
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
        ForeignKey("users.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, server_default="member")
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
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
        ForeignKey("users.id"), nullable=False
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
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
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
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mimetype: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
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
        ForeignKey("users.id"), nullable=False
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
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
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
        ForeignKey("users.id"), nullable=False
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
        ForeignKey("users.id"), primary_key=True
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
        ForeignKey("users.id"), nullable=False
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
        ForeignKey("users.id"), nullable=False
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
        ForeignKey("users.id"), nullable=False
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
