"""Meeting processor web engine — async helpers for the meeting intelligence pipeline.

This module provides the core async helpers used by skill_executor's
_execute_meeting_processor() 8-stage pipeline:

- classify_meeting()  — 3-layer classification returning one of 8 meeting types
- extract_intelligence() — Sonnet extraction into 7 MPP-04 context file types
- upload_transcript()  — Upload transcript text to Supabase Storage
- write_context_entries() — Write extracted intelligence to ContextEntry rows
- auto_link_meeting_to_account() — Match attendee domains to existing accounts
- auto_create_prospect() — Auto-create prospect account for unknown external domains
- upsert_account_contacts() — Upsert attendees as AccountContact rows
- apply_post_classification_rules() — Post-classification skip check (MPP-05 rules)
- extract_tasks() — Haiku-based commitment classification from transcripts
- write_task_rows() — Create Task ORM rows from extracted task dicts

Important: this is the WEB implementation (async, ORM-based).
Do NOT import from engines/meeting_processor.py (CLI, sync, storage_backend).
The two implementations coexist permanently.

CONTEXT_FILE_MAP keys align exactly with MPP-04 spec:
    competitive-intel, pain-points, icp-profiles, contacts,
    insights, action-items, product-feedback
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from flywheel.db.models import Account, AccountContact, ContextEntry, Task, Tenant

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_SONNET_MODEL = "claude-sonnet-4-20250514"

# Free email provider domains — never auto-create prospect accounts for these
FREE_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "protonmail.com",
    "aol.com",
    "live.com",
    "msn.com",
    "me.com",
})

# Mail-related subdomains to strip when extracting the root domain for matching
_MAIL_SUBDOMAINS = ("mail.", "email.", "smtp.", "mx.", "www.")

# 8 recognized meeting types (returned by classify_meeting)
MEETING_TYPES = frozenset({
    "discovery",
    "expert",
    "prospect",
    "advisor",
    "investor-pitch",
    "internal",
    "customer-feedback",
    "team-meeting",
})

# Maps extracted intelligence keys → ContextEntry file_names (MPP-04 aligned)
CONTEXT_FILE_MAP: dict[str, str] = {
    "competitive_intel": "competitive-intel",
    "pain_points": "pain-points",
    "icp_profiles": "icp-profiles",
    "contacts": "contacts",
    "insights": "insights",
    "action_items": "action-items",
    "product_feedback": "product-feedback",
}

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are a meeting intelligence extraction engine. Given a meeting transcript and metadata,
extract structured intelligence into exactly the 7 categories below.

Respond ONLY with a valid JSON object using these exact keys:
- competitive_intel: list of {competitor, mention, pricing_signal, switching_signal, speaker}
- pain_points: list of {problem, severity (low/medium/high), speaker, classification (painkiller/vitamin)}
- icp_profiles: list of {segment, buying_signal, decision_maker_info, budget_signal, champion_indicator}
- contacts: list of {name, title, company, role, notes}
- insights: list of {takeaway, type (strategic/tactical/pattern), quote, next_step}
- action_items: list of {action, owner, due_date, type (internal/external)}
- product_feedback: list of {feedback_type (feature_request/reaction/demo_feedback), description, sentiment}
- tldr: string — 2–3 sentence meeting summary
- key_decisions: list of strings — key decisions made in the meeting

Use empty lists for categories with no data. Do not include any prose outside the JSON object.
"""

EXTRACTION_USER_PROMPT = """\
Meeting type: {meeting_type}

Transcript:
{transcript}

AI summary from provider (if available):
{ai_summary}

Existing account context (if available):
{existing_context}

Extract intelligence from this meeting.
"""


# ---------------------------------------------------------------------------
# 3-Layer Meeting Classification
# ---------------------------------------------------------------------------


async def classify_meeting(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    title: str,
    attendees: list[dict],
    transcript: str,
    ai_summary: str | None = None,
    api_key: str | None = None,
) -> str:
    """Classify a meeting into one of 8 types using 3-layer detection.

    Layer 1: Contact match — query AccountContact for attendee emails.
              If found, derive type from parent account's relationship_type.
    Layer 2: Internal check — if all attendees share tenant domain, classify
              as "internal" (<=3 attendees) or "team-meeting" (>3 attendees).
              Skipped if tenant.domain is NULL.
    Layer 3: Haiku LLM call — use title + attendees + first 500 chars of
              transcript to classify meeting type.

    Returns one of the 8 MEETING_TYPES values.
    """
    attendee_emails = [
        a.get("email", "").lower()
        for a in (attendees or [])
        if a.get("email")
    ]

    # -----------------------------------------------------------------------
    # Layer 1: Account contact match
    # -----------------------------------------------------------------------
    if attendee_emails:
        try:
            async with factory() as session:
                await session.execute(
                    sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
                rows = (await session.execute(
                    select(AccountContact, Account)
                    .join(Account, AccountContact.account_id == Account.id)
                    .where(
                        AccountContact.tenant_id == tenant_id,
                        AccountContact.email.in_(attendee_emails),
                    )
                    .limit(1)
                )).first()

            if rows is not None:
                contact, account = rows
                rel_types = account.relationship_type or []
                # Map relationship_type array to meeting type
                for rel in rel_types:
                    rel_lower = rel.lower()
                    if rel_lower == "advisor":
                        return "advisor"
                    elif rel_lower in ("investor", "investor-pitch"):
                        return "investor-pitch"
                    elif rel_lower in ("prospect", "pipeline"):
                        return "prospect"
                    elif rel_lower == "customer":
                        return "customer-feedback"
                    elif rel_lower == "expert":
                        return "expert"
                # Fallback from relationship type — use discovery if we matched a contact
                return "discovery"
        except Exception as exc:
            logger.warning("classify_meeting Layer 1 failed: %s", exc)

    # -----------------------------------------------------------------------
    # Layer 2: Internal domain check
    # -----------------------------------------------------------------------
    if attendee_emails:
        try:
            async with factory() as session:
                # NOTE: tenants is NOT tenant-scoped, no RLS needed
                tenant_row = (await session.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )).scalar_one_or_none()

            if tenant_row and tenant_row.domain:
                tenant_domain = tenant_row.domain.lower().lstrip("@")
                all_internal = all(
                    email.endswith(f"@{tenant_domain}")
                    for email in attendee_emails
                    if email
                )
                if all_internal:
                    return "team-meeting" if len(attendee_emails) > 3 else "internal"
            elif tenant_row and not tenant_row.domain:
                logger.debug(
                    "classify_meeting Layer 2 skipped: tenant %s has NULL domain", tenant_id
                )
        except Exception as exc:
            logger.warning("classify_meeting Layer 2 failed: %s", exc)

    # -----------------------------------------------------------------------
    # Layer 3: Haiku LLM classification
    # -----------------------------------------------------------------------
    try:
        attendees_str = ", ".join(
            a.get("name") or a.get("email") or "Unknown"
            for a in (attendees or [])
        )
        transcript_preview = (transcript or "")[:500]

        prompt = (
            f"Meeting title: {title}\n"
            f"Attendees: {attendees_str}\n"
            f"Transcript preview: {transcript_preview}\n\n"
            "Classify this meeting. Respond with EXACTLY one of these codes:\n"
            "discovery, expert, prospect, advisor, investor-pitch, internal, "
            "customer-feedback, team-meeting\n"
            "Return only the code, nothing else."
        )

        def _call_haiku() -> str:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
            msg = client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip().lower()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _call_haiku)

        if result in MEETING_TYPES:
            return result

        # Fuzzy match in case the model returned something close
        for mtype in MEETING_TYPES:
            if mtype in result:
                return mtype

        logger.warning("classify_meeting Layer 3 returned unexpected value: %r", result)
    except Exception as exc:
        logger.warning("classify_meeting Layer 3 failed: %s", exc)

    # Default fallback
    return "discovery"


# ---------------------------------------------------------------------------
# Sonnet Intelligence Extraction
# ---------------------------------------------------------------------------


async def extract_intelligence(
    transcript: str,
    ai_summary: str | None,
    meeting_type: str,
    existing_context_str: str = "",
    api_key: str | None = None,
) -> dict:
    """Extract structured intelligence from a meeting transcript using Sonnet.

    Extracts 7 MPP-04 context file categories plus tldr and key_decisions
    as top-level summary fields.

    Returns a dict with all keys (empty lists/strings for missing data):
    - competitive_intel, pain_points, icp_profiles, contacts, insights,
      action_items, product_feedback  (map to CONTEXT_FILE_MAP)
    - tldr, key_decisions  (summary-only, NOT written as context entries)
    """
    user_prompt = EXTRACTION_USER_PROMPT.format(
        meeting_type=meeting_type,
        transcript=(transcript or "")[:12000],  # Avoid context window overflow
        ai_summary=ai_summary or "(none)",
        existing_context=existing_context_str or "(none)",
    )

    def _call_sonnet() -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        msg = client.messages.create(
            model=_SONNET_MODEL,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = msg.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("extract_intelligence: JSON parse error: %s — raw: %.200s", e, raw)
            return {}

    loop = asyncio.get_event_loop()
    extracted = await loop.run_in_executor(None, _call_sonnet)

    # Ensure all expected keys exist with empty defaults
    defaults: dict = {
        "competitive_intel": [],
        "pain_points": [],
        "icp_profiles": [],
        "contacts": [],
        "insights": [],
        "action_items": [],
        "product_feedback": [],
        "tldr": "",
        "key_decisions": [],
    }
    for key, default in defaults.items():
        extracted.setdefault(key, default)

    return extracted


# ---------------------------------------------------------------------------
# Supabase Storage Upload
# ---------------------------------------------------------------------------


async def upload_transcript(
    tenant_id: UUID,
    meeting_id: UUID,
    transcript_text: str,
) -> str:
    """Upload a meeting transcript to Supabase Storage.

    Stores at: uploads/transcripts/{tenant_id}/{meeting_id}.txt
    Returns the storage path string.
    """
    from flywheel.config import settings
    supabase_url = settings.supabase_url
    service_role_key = settings.supabase_service_key

    storage_path = f"transcripts/{tenant_id}/{meeting_id}.txt"
    upload_url = f"{supabase_url}/storage/v1/object/uploads/{storage_path}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "text/plain",
            },
            content=transcript_text.encode("utf-8"),
        )
        # 200 = created, 409 = already exists (upsert on conflict)
        if resp.status_code not in (200, 201, 409):
            logger.warning(
                "upload_transcript: unexpected status %s for %s",
                resp.status_code, storage_path,
            )

    return storage_path


# ---------------------------------------------------------------------------
# Context Entry Writer
# ---------------------------------------------------------------------------


def _make_meeting_slug(meeting_date: date | datetime, title: str) -> str:
    """Generate a stable slug for a meeting context entry detail field.

    Format: meeting-{YYYY-MM-DD}-{title_slug}
    title_slug = first 20 chars of title, lowercased, non-alphanumeric → hyphens.
    """
    if isinstance(meeting_date, datetime):
        date_str = meeting_date.date().isoformat()
    else:
        date_str = meeting_date.isoformat()

    title_slug = re.sub(r"[^a-z0-9]+", "-", (title or "untitled")[:20].lower()).strip("-")
    return f"meeting-{date_str}-{title_slug}"


async def write_context_entries(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    user_id: UUID,
    account_id: UUID | None,
    meeting_date: date | datetime,
    meeting_slug: str,
    extracted: dict,
) -> int:
    """Write extracted meeting intelligence to ContextEntry rows.

    - Maps extracted keys to ContextEntry file_names via CONTEXT_FILE_MAP.
    - Skips tldr and key_decisions (summary-only, not written as entries).
    - Deduplicates: skips if a row with (file_name, source, detail, tenant_id)
      already exists.
    - Sets RLS context (app.tenant_id and app.user_id) before writes.
    - Returns the count of new entries written.

    account_id may be None — set directly on ORM object when provided.
    """
    if isinstance(meeting_date, datetime):
        entry_date = meeting_date.date()
    else:
        entry_date = meeting_date

    written = 0

    async with factory() as session:
        # Set RLS context
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            sa_text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        for extract_key, file_name in CONTEXT_FILE_MAP.items():
            value = extracted.get(extract_key)
            if not value:
                continue  # Skip empty / falsy values

            # Serialize list/dict values to JSON string for content field
            if isinstance(value, (list, dict)):
                if not value:
                    continue
                content_str = json.dumps(value, indent=2)
            else:
                content_str = str(value)

            # Dedup check: (file_name, source, detail, tenant_id)
            existing = (await session.execute(
                select(ContextEntry.id).where(
                    ContextEntry.file_name == file_name,
                    ContextEntry.source == "ctx-meeting-processor",
                    ContextEntry.detail == meeting_slug,
                    ContextEntry.tenant_id == tenant_id,
                ).limit(1)
            )).scalar_one_or_none()

            if existing is not None:
                logger.debug(
                    "write_context_entries: skipping duplicate %s/%s for %s",
                    file_name, meeting_slug, tenant_id,
                )
                continue

            entry = ContextEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                file_name=file_name,
                source="ctx-meeting-processor",
                detail=meeting_slug,
                confidence="medium",
                date=entry_date,
                content=content_str,
            )
            if account_id is not None:
                entry.account_id = account_id

            session.add(entry)
            written += 1

        await session.commit()

    logger.info(
        "write_context_entries: wrote %d new entries for meeting %s (tenant=%s)",
        written, meeting_slug, tenant_id,
    )
    return written


# ---------------------------------------------------------------------------
# Post-Classification Processing Rules (MPP-05)
# ---------------------------------------------------------------------------


def apply_post_classification_rules(
    meeting_type: str,
    external_id: str,
    attendees: list[dict],
    processing_rules: dict,
    tenant_domain: str | None = None,
) -> str:
    """Apply post-classification processing rules to determine if a meeting should be skipped.

    Implements all 4 MPP-05 rule types. Returns "skipped" if any rule matches,
    "pending" if the meeting should continue processing.

    Rules checked (from Integration.settings["processing_rules"]):
    1. skip_meetings (manually_skipped): specific external_ids the user has excluded
    2. skip_internal: meetings with no external attendees (default: ON)
    3. skip_domains: meetings where all attendee domains are in the skip list
    4. skip_types (skip_meeting_types): meetings of a specific type

    This is a pure function — no DB access, no async needed.
    """
    if not processing_rules:
        processing_rules = {}

    # Rule 1: skip_meetings (manually skipped by external_id)
    manually_skipped = processing_rules.get("manually_skipped", [])
    if external_id and external_id in manually_skipped:
        return "skipped"

    # Rule 2: skip_internal (default ON per spec)
    # Skip meetings where no attendees have is_external=True
    if processing_rules.get("skip_internal", True):
        has_external = any(a.get("is_external", False) for a in (attendees or []))
        if not has_external:
            return "skipped"

    # Rule 3: skip_domains
    # Skip if all attendee domains are within the skip list (plus optional tenant domain)
    skip_domains = set(processing_rules.get("skip_domains", []))
    if skip_domains:
        allowed_domains = skip_domains | ({tenant_domain} if tenant_domain else set())
        domains: set[str] = set()
        for a in (attendees or []):
            email = (a.get("email") or "").strip()
            if "@" in email:
                domain = email.split("@")[-1].lower()
                if domain:
                    domains.add(domain)
        if domains and domains.issubset(allowed_domains):
            return "skipped"

    # Rule 4: skip_types (skip_meeting_types key per spec)
    skip_meeting_types = processing_rules.get("skip_meeting_types", [])
    if meeting_type in skip_meeting_types:
        return "skipped"

    return "pending"


# ---------------------------------------------------------------------------
# Account Auto-Linking
# ---------------------------------------------------------------------------


def _normalize_domain(raw_domain: str) -> str:
    """Strip common mail subdomains and lowercases the result.

    Examples:
        mail.acme.com  -> acme.com
        www.acme.com   -> acme.com
        ACME.COM       -> acme.com
    """
    domain = raw_domain.lower().strip()
    for prefix in _MAIL_SUBDOMAINS:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
            break
    return domain


def _extract_external_domains(attendees: list[dict]) -> list[str]:
    """Return unique normalized domains from external attendees.

    Filters out free email providers and any attendees missing an email.
    Only includes attendees where is_external=True.
    """
    domains: dict[str, bool] = {}
    for a in (attendees or []):
        if not a.get("is_external"):
            continue
        email = (a.get("email") or "").lower().strip()
        if "@" not in email:
            continue
        domain = _normalize_domain(email.split("@", 1)[1])
        if domain and domain not in FREE_EMAIL_DOMAINS:
            domains[domain] = True
    return list(domains.keys())


async def upsert_account_contacts(
    session: AsyncSession,
    tenant_id: UUID,
    account_id: UUID,
    attendees: list[dict],
    domain: str,
) -> int:
    """Upsert external attendees matching domain as AccountContact rows.

    - Filters attendees to those with is_external=True and email ending in @{domain}.
    - Checks for existing AccountContact by (tenant_id, account_id, email).
    - Creates new contacts only when not already present.
    - Returns count of newly created contacts.

    Caller is responsible for setting RLS context and committing the session.
    """
    created = 0
    target_suffix = f"@{domain}"

    for a in (attendees or []):
        if not a.get("is_external"):
            continue
        email = (a.get("email") or "").lower().strip()
        if not email.endswith(target_suffix):
            continue
        name = (a.get("name") or email.split("@")[0]).strip() or email

        existing = (await session.execute(
            select(AccountContact.id).where(
                AccountContact.tenant_id == tenant_id,
                AccountContact.account_id == account_id,
                AccountContact.email == email,
            ).limit(1)
        )).scalar_one_or_none()

        if existing is None:
            contact = AccountContact(
                tenant_id=tenant_id,
                account_id=account_id,
                name=name,
                email=email,
                source="meeting-auto-discovery",
            )
            session.add(contact)
            created += 1
            logger.debug(
                "upsert_account_contacts: added contact %s to account %s", email, account_id
            )

    return created


async def auto_create_prospect(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    user_id: UUID | None,
    domain: str,
    attendees: list[dict],
    title: str = "",
) -> UUID:
    """Auto-create a prospect Account for an unknown external domain.

    - Derives company name from the domain (e.g. acme.com -> Acme).
    - Computes normalized_name for dedup check.
    - Returns existing account.id if the normalized_name already exists.
    - Creates new Account with all required NOT NULL fields.
    - Calls upsert_account_contacts() for matching attendees.
    - Commits and returns the account UUID.
    """
    company_name = domain.split(".")[0].title()
    normalized = re.sub(r"[^a-z0-9]", "", company_name.lower())

    async with factory() as session:
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

        # Dedup check
        existing_id = (await session.execute(
            select(Account.id).where(
                Account.tenant_id == tenant_id,
                Account.normalized_name == normalized,
            ).limit(1)
        )).scalar_one_or_none()

        if existing_id is not None:
            logger.info(
                "auto_create_prospect: account %s already exists for domain %s (tenant=%s)",
                existing_id, domain, tenant_id,
            )
            return existing_id

        account = Account(
            tenant_id=tenant_id,
            name=company_name,
            normalized_name=normalized,
            domain=domain,
            source="meeting-auto-discovery",
            status="prospect",
            relationship_type=["prospect"],
            relationship_status="new",
            pipeline_stage="identified",
            last_interaction_at=datetime.now(timezone.utc),
        )
        session.add(account)
        await session.flush()  # Populate account.id

        # Upsert contacts for attendees matching this domain
        await upsert_account_contacts(session, tenant_id, account.id, attendees, domain)

        await session.commit()
        logger.info(
            "auto_create_prospect: created prospect '%s' (id=%s) for domain %s (tenant=%s)",
            company_name, account.id, domain, tenant_id,
        )
        return account.id


async def auto_link_meeting_to_account(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    attendees: list[dict],
    user_id: UUID | None = None,
    meeting_title: str = "",
) -> UUID | None:
    """Match meeting attendees to existing accounts by domain, or create prospects.

    Steps:
    1. Extract unique external domains from attendees (excludes free email providers).
    2. Query Account.domain for any of those domains in the tenant.
    3. If single match: return account.id.
    4. If multiple matches: return account with most AccountContacts (first if tied).
    5. If no match: for each external domain, call auto_create_prospect().
       Return the first created account's id.
    6. If no external domains (all internal): return None.

    Args:
        factory: async session factory with RLS.
        tenant_id: Tenant UUID for filtering and RLS.
        attendees: List of attendee dicts with email, name, is_external keys.
        user_id: Optional user UUID (passed to auto_create_prospect).
        meeting_title: Meeting title (passed to auto_create_prospect for context).

    Returns:
        Account UUID if a match or prospect was created, else None.
    """
    external_domains = _extract_external_domains(attendees)

    if not external_domains:
        logger.debug(
            "auto_link_meeting_to_account: no external domains found (all internal or free email)"
        )
        return None

    # Query for existing accounts matching any of the external domains
    async with factory() as session:
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        matched_accounts = (await session.execute(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.domain.in_(external_domains),
            )
        )).scalars().all()

    if len(matched_accounts) == 1:
        account = matched_accounts[0]
        logger.info(
            "auto_link_meeting_to_account: single domain match -> account %s (domain=%s)",
            account.id, account.domain,
        )
        return account.id

    if len(matched_accounts) > 1:
        # Pick account with most contacts; fall back to first if tied
        async with factory() as session:
            await session.execute(
                sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            rows = (await session.execute(
                select(Account.id, func.count(AccountContact.id).label("contact_count"))
                .outerjoin(AccountContact, AccountContact.account_id == Account.id)
                .where(Account.id.in_([a.id for a in matched_accounts]))
                .group_by(Account.id)
                .order_by(func.count(AccountContact.id).desc())
                .limit(1)
            )).first()

        best_id = rows[0] if rows else matched_accounts[0].id
        logger.info(
            "auto_link_meeting_to_account: %d domain matches, picked account %s by contact count",
            len(matched_accounts), best_id,
        )
        return best_id

    # No existing match — auto-create prospect accounts for unknown external domains
    logger.info(
        "auto_link_meeting_to_account: no existing accounts for domains %s — creating prospects",
        external_domains,
    )
    first_account_id: UUID | None = None
    for domain in external_domains:
        try:
            account_id = await auto_create_prospect(
                factory=factory,
                tenant_id=tenant_id,
                user_id=user_id,
                domain=domain,
                attendees=attendees,
                title=meeting_title,
            )
            if first_account_id is None:
                first_account_id = account_id
        except Exception as exc:
            logger.warning(
                "auto_link_meeting_to_account: failed to create prospect for domain %s: %s",
                domain, exc,
            )

    return first_account_id


# ---------------------------------------------------------------------------
# Task Extraction Prompt
# ---------------------------------------------------------------------------

TASK_EXTRACTION_PROMPT = """\
You are a task extraction engine. Given a meeting transcript and extracted intelligence,
identify all commitments, action items, and follow-ups.

For each task, classify:
1. commitment_direction: "yours" (the user/founder committed), "theirs" (other party committed),
   "mutual" (both sides), "signal" (implicit need, nobody committed), "speculation" (might need later)
2. task_type: "followup" (reach back out), "deliverable" (create something), "introduction" (connect people),
   "research" (investigate), "other"
3. suggested_skill: if the task maps to a known skill, suggest it. Known skills:
   - "email-drafter" for follow-up emails
   - "sales-collateral" for one-pagers, decks, proposals
   - "investor-update" for investor updates
   - null if no skill applies
4. trust_level: "auto" (safe to execute without review), "review" (needs user review before execution),
   "confirm" (MUST be explicitly confirmed -- use for ALL email-related tasks)
5. priority: "high" (time-sensitive or explicitly urgent), "medium" (standard), "low" (nice-to-have)
6. due_date: ISO 8601 datetime if mentioned or inferrable, null otherwise

CRITICAL: Any task with suggested_skill containing "email" MUST have trust_level="confirm".

Respond with a JSON array of task objects. Each object:
{
  "title": "short action title",
  "description": "detailed description with context",
  "commitment_direction": "yours|theirs|mutual|signal|speculation",
  "task_type": "followup|deliverable|introduction|research|other",
  "suggested_skill": "skill-name" or null,
  "skill_context": {} or null,
  "trust_level": "auto|review|confirm",
  "priority": "high|medium|low",
  "due_date": "ISO datetime" or null
}

Return an empty array [] if no tasks are found.
"""


# ---------------------------------------------------------------------------
# Task Extraction (Haiku LLM)
# ---------------------------------------------------------------------------


async def extract_tasks(
    transcript: str,
    extracted: dict,
    meeting_type: str,
    api_key: str | None = None,
) -> list[dict]:
    """Extract commitments and tasks from a meeting transcript using Haiku.

    Calls Haiku with TASK_EXTRACTION_PROMPT, parses JSON response, and
    enforces the hard safety rule: email-related tasks always get
    trust_level='confirm'.

    Returns a list of task dicts ready for write_task_rows(), or an empty
    list on parse failure (logs warning, does not crash pipeline).
    """
    user_prompt = (
        f"Meeting type: {meeting_type}\n\n"
        f"Transcript:\n{(transcript or '')[:12000]}\n\n"
        f"Extracted intelligence:\n{json.dumps(extracted, indent=2, default=str)[:4000]}\n\n"
        "Extract all tasks and commitments from this meeting."
    )

    def _call_haiku() -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        msg = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=2048,
            system=TASK_EXTRACTION_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text.strip()

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _call_haiku)

    # Strip markdown code fences if present (same cleanup as extract_intelligence)
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()

    try:
        tasks = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("extract_tasks: JSON parse error: %s -- raw: %.200s", e, raw)
        return []

    if not isinstance(tasks, list):
        logger.warning("extract_tasks: expected list, got %s", type(tasks).__name__)
        return []

    # Post-processing enforcement: email tasks MUST have trust_level='confirm'
    for task in tasks:
        suggested = (task.get("suggested_skill") or "")
        if "email" in suggested.lower():
            task["trust_level"] = "confirm"

    return tasks


# ---------------------------------------------------------------------------
# Task Row Writer
# ---------------------------------------------------------------------------


async def write_task_rows(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: UUID,
    user_id: UUID,
    meeting_id: UUID,
    account_id: UUID | None,
    tasks: list[dict],
) -> int:
    """Create Task ORM rows from extracted task dicts.

    Sets RLS context (app.tenant_id and app.user_id) on the session before
    writing. Returns count of tasks created.
    """
    if not tasks:
        return 0

    created = 0

    async with factory() as session:
        # CRITICAL: set both tenant and user RLS context (Pitfall 2)
        await session.execute(
            sa_text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(
            sa_text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_id)},
        )

        for t in tasks:
            # Parse due_date if present
            parsed_due: datetime | None = None
            raw_due = t.get("due_date")
            if raw_due:
                try:
                    parsed_due = datetime.fromisoformat(raw_due.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    logger.debug("write_task_rows: could not parse due_date %r", raw_due)

            task = Task(
                tenant_id=tenant_id,
                user_id=user_id,
                meeting_id=meeting_id,
                account_id=account_id,
                source="meeting-processor",
                title=t.get("title", "Untitled task"),
                description=t.get("description"),
                task_type=t.get("task_type", "other"),
                commitment_direction=t.get("commitment_direction", "signal"),
                suggested_skill=t.get("suggested_skill"),
                skill_context=t.get("skill_context"),
                trust_level=t.get("trust_level", "review"),
                priority=t.get("priority", "medium"),
                due_date=parsed_due,
            )
            session.add(task)
            created += 1

        await session.flush()
        await session.commit()

    logger.info(
        "write_task_rows: created %d tasks for meeting %s (tenant=%s, user=%s)",
        created, meeting_id, tenant_id, user_id,
    )
    return created
