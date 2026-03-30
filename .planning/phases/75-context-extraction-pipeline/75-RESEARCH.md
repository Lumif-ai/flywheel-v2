# Phase 75: Context Extraction Pipeline - Research

**Researched:** 2026-03-30
**Domain:** Gmail sync loop integration, confidence routing, human review queue, daily caps
**Confidence:** HIGH

## Summary

Phase 75 wires the email context extractor (built in Phase 74) into the live gmail sync loop. The core work is: (1) adding a `context_extracted_at` column to the `emails` table to prevent re-extraction, (2) creating an `email_context_reviews` table for low-confidence extractions that need human approval, (3) inserting extraction into the sync loop after scoring with a separate 200/day per-tenant cap, and (4) building API endpoints for the review queue (list/approve/reject).

The existing sync loop in `gmail_sync.py` follows a clear pattern: sync emails -> commit -> score -> commit -> draft -> commit. Context extraction slots in after scoring, following the same non-fatal pattern. The existing `_check_daily_scoring_cap()` function (500/day for scoring) provides the exact template for the 200/day extraction cap. The email context extractor (`extract_email_context()`) already handles priority >= 3 filtering, body fetching, Claude extraction, and writing to context store -- Phase 75 wraps it with cap checking, confidence routing, and tracking.

**Primary recommendation:** Add extraction as a new step in the sync pipeline after scoring/drafting, using the same commit-then-process pattern. Split confidence routing at the point where `extract_email_context()` returns: high/medium items get written directly (already done by the extractor), low-confidence items get routed to `email_context_reviews`. The review API lives on the existing `/email` router.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (async) | 2.x | DB operations, new table, new column | All existing models/engines use this |
| Alembic | 1.x | Migration for new table + column | All schema changes use hand-written migrations |
| FastAPI | 0.100+ | Review queue API endpoints | All API endpoints follow this pattern |
| Pydantic | 2.x | Request/response models for review API | Used by all existing API endpoints |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| anthropic (AsyncAnthropic) | latest | Already used by extractor | No new usage -- extractor handles it |
| logging (stdlib) | - | Structured logging (no PII) | Cap reached messages, extraction tracking |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `context_extracted_at` on emails table | Separate tracking table | Column is simpler, matches `synced_at` pattern, one fewer join |
| Review table with full extracted JSON | Storing only low-confidence items individually | Full JSON is simpler -- one review per extraction, not per item |
| Cap in code (hardcoded 200) | Cap in tenant.settings JSONB | Code is simpler now, settings allows per-tenant override later |

## Architecture Patterns

### Recommended Project Structure
```
backend/
  alembic/versions/
    037_context_extraction_pipeline.py    # NEW - migration
  src/flywheel/
    db/models.py                          # MODIFY - add EmailContextReview, context_extracted_at
    services/gmail_sync.py                # MODIFY - add extraction step after scoring
    engines/email_context_extractor.py    # MODIFY - add confidence routing logic
    api/email.py                          # MODIFY - add review endpoints
```

### Pattern 1: Post-Score Extraction Step in Sync Loop
**What:** Context extraction runs after scoring and drafting, using the same non-fatal wrapper pattern.
**When to use:** Both `_full_sync()` and `sync_gmail()` (incremental) -- same pattern in both places.
**Why after drafting:** Extraction is lower priority than drafting; if the per-integration timeout fires, we want scores and drafts to have completed first.

```python
# In gmail_sync.py, after the drafting block in both _full_sync() and sync_gmail():

# Extract context from scored emails AFTER drafting
if new_email_ids:
    try:
        extracted = await _extract_email_contexts(
            db, integration.tenant_id, integration, new_email_ids
        )
        logger.info(
            "Extracted context from %d emails for integration %s",
            extracted, integration.id,
        )
    except Exception:
        logger.exception(
            "Context extraction failed for integration %s", integration.id
        )
        # Non-fatal -- sync, scoring, and drafting already committed
```

### Pattern 2: Daily Cap Check (mirrors _check_daily_scoring_cap)
**What:** Count today's extractions per tenant, return remaining budget.
**Key difference from scoring cap:** Uses `context_extracted_at` on emails table, not a separate scores table.

```python
async def _check_daily_extraction_cap(
    db: AsyncSession,
    tenant_id: UUID,
    cap: int = 200,
) -> int:
    """Return remaining extraction budget for today. Default cap: 200/day."""
    today_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        sa_text(
            "SELECT COUNT(*) FROM emails "
            "WHERE tenant_id = :tid AND context_extracted_at >= :today"
        ).bindparams(tid=tenant_id, today=today_utc)
    )
    count = result.scalar_one()
    return max(0, cap - count)
```

### Pattern 3: Confidence Routing
**What:** After extraction, route items based on per-item confidence levels.
**Key insight:** The extractor already writes high/medium items to context store. For low-confidence, we intercept BEFORE writing and route to the review table instead.

Two approaches:
1. **Pre-write routing (recommended):** Modify `_write_extracted_context()` to skip low-confidence items and return them separately. Then the caller inserts them into `email_context_reviews`.
2. **Post-write routing:** Let extractor write everything, then move low-confidence items to review table and soft-delete from context store. More complex, more DB operations.

```python
# Recommended: modify extract_email_context() return to include confidence breakdown
# Then in the sync loop wrapper:

result = await extract_email_context(db, tenant_id, email_obj, integration)
if result is None:
    continue

# Route low-confidence items to review table
low_confidence_items = [
    item for category in result["extracted"].values()
    for item in category
    if isinstance(item, dict) and item.get("confidence") == "low"
]
if low_confidence_items:
    review = EmailContextReview(
        tenant_id=tenant_id,
        email_id=email_obj.id,
        user_id=email_obj.user_id,
        extracted_data={"low_confidence_items": low_confidence_items},
        status="pending",
    )
    db.add(review)

# Mark email as extracted
email_obj.context_extracted_at = datetime.now(timezone.utc)
```

### Pattern 4: Review API Endpoints (mirrors draft approve/dismiss)
**What:** CRUD-like endpoints for the review queue, following the existing draft lifecycle pattern.
**Endpoints:**
- `GET /email/context-reviews` -- list pending reviews (paginated)
- `POST /email/context-reviews/{id}/approve` -- write items to context store, set status="approved"
- `POST /email/context-reviews/{id}/reject` -- set status="rejected", do not write

### Pattern 5: RLS on New Table
**What:** Hand-written RLS policies in the migration, matching the email_scores pattern exactly.
**Template:** 4 policies (SELECT, INSERT, UPDATE, DELETE) all using `tenant_id = current_setting('app.tenant_id', true)::uuid`.

### Anti-Patterns to Avoid
- **Do NOT modify the extractor's core prompt or parsing logic** -- Phase 74 is verified and working. Only wrap the existing functions.
- **Do NOT add extraction inside the sync commit transaction** -- extraction involves an LLM call and can be slow. Run it AFTER the sync commit, same as scoring.
- **Do NOT store email body in the review table** -- PII posture. Store only the extracted structured data.
- **Do NOT make the cap configurable per-tenant yet** -- hardcode 200, add configurability later when needed (YAGNI).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Daily cap counting | Custom counter/cache | SQL COUNT with date filter | Matches existing `_check_daily_scoring_cap()` pattern, no cache invalidation issues |
| Context store writes | Direct INSERT | Existing `context_store_writer.py` functions | Dedup + evidence counting already handled |
| Extraction logic | New extraction code | Existing `extract_email_context()` | Already handles priority guard, body fetch, Claude call, parsing, writing |
| RLS policies | Application-level tenant filtering | PostgreSQL RLS | All tenant tables use RLS, not application filtering |
| Review approval writes | Custom write logic | Existing `write_contact()`, `write_insight()`, etc. | Same writer functions used by initial extraction |

## Common Pitfalls

### Pitfall 1: Double Extraction on Retry
**What goes wrong:** If extraction succeeds but commit fails, next sync re-extracts the same email (LLM cost + duplicate context entries).
**Why it happens:** `context_extracted_at` isn't set until after extraction completes, but extraction writes to context store.
**How to avoid:** Set `context_extracted_at` BEFORE calling the extractor (optimistic marking), or set it immediately after extraction returns (before commit). The context store writer's dedup (`_write_entry()`) handles duplicate writes gracefully via evidence_count increment.
**Warning signs:** Evidence counts growing rapidly on the same entries.

### Pitfall 2: Extraction Blocking Sync Timeout
**What goes wrong:** Extraction involves LLM calls (slow). If many emails need extraction, the per-integration timeout (60s) fires before extraction completes.
**Why it happens:** Each extraction = 1 Claude API call. 10 emails = 10 serial API calls.
**How to avoid:** Process extraction AFTER sync commit (already the pattern). Also consider: (a) batch limit per sync cycle (e.g., max 10 extractions per cycle), (b) extraction runs in its own timeout budget separate from the sync timeout.
**Warning signs:** Timeout warnings in logs for integrations with many new high-priority emails.

### Pitfall 3: Review Table Growing Unbounded
**What goes wrong:** Low-confidence reviews accumulate with no cleanup.
**Why it happens:** Users may never review low-confidence items.
**How to avoid:** Add a `created_at` column with server_default. Future phases can add auto-expiry (e.g., reject after 30 days). For now, just having the timestamp is sufficient.
**Warning signs:** Review count growing monotonically per tenant.

### Pitfall 4: Confidence Routing Splits Extraction Results
**What goes wrong:** An extraction returns a mix of high, medium, and low confidence items. If you route the entire extraction to review on any low item, you lose the high/medium items.
**Why it happens:** Extraction returns a single JSON with mixed confidences.
**How to avoid:** Route per-item, not per-extraction. High/medium items write immediately. Only low-confidence items go to the review table. The review table stores the low-confidence subset, not the full extraction.
**Warning signs:** Context store missing items that were in the extraction response.

### Pitfall 5: Foreign Key Cascade on Email Deletion
**What goes wrong:** When gmail sync removes an email (INBOX label removed), the cascade deletes email_scores and email_drafts. But `email_context_reviews` has no cascade -- orphaned reviews.
**Why it happens:** New FK on `email_context_reviews.email_id` without ON DELETE CASCADE.
**How to avoid:** Add `ON DELETE CASCADE` to the email_id FK in the migration. Also handle in the reconciliation code in `_full_sync()` and incremental sync.
**Warning signs:** Reviews referencing deleted emails.

## Code Examples

### Migration: email_context_reviews table + context_extracted_at column
```python
# 037_context_extraction_pipeline.py

def upgrade() -> None:
    # 1. Add context_extracted_at to emails
    op.add_column(
        "emails",
        sa.Column(
            "context_extracted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_emails_context_extracted",
        "emails",
        ["tenant_id"],
        postgresql_where=sa.text("context_extracted_at IS NULL"),
    )

    # 2. Create email_context_reviews table
    op.execute("""
        CREATE TABLE email_context_reviews (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            email_id        UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES profiles(id),
            extracted_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
            status          TEXT NOT NULL DEFAULT 'pending',
            reviewed_at     TIMESTAMP WITH TIME ZONE,
            created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_context_reviews_tenant_status
            ON email_context_reviews (tenant_id, status);
    """)

    # 3. RLS (4 policies)
    op.execute("ALTER TABLE email_context_reviews ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE email_context_reviews FORCE ROW LEVEL SECURITY;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON email_context_reviews TO app_user;")

    for action in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
        using_or_check = "WITH CHECK" if action == "INSERT" else "USING"
        op.execute(f"""
            CREATE POLICY tenant_isolation_{action.lower()} ON email_context_reviews
                FOR {action}
                {using_or_check} (tenant_id = current_setting('app.tenant_id', true)::uuid);
        """)
```

### Sync Loop Integration Point
```python
# In gmail_sync.py -- new function
async def _extract_email_contexts(
    db: AsyncSession,
    tenant_id: UUID,
    integration: Integration,
    email_ids: list[UUID],
) -> int:
    """Extract context from newly scored emails. Returns count extracted."""
    if not email_ids:
        return 0

    # Check daily cap
    remaining = await _check_daily_extraction_cap(db, tenant_id)
    if remaining == 0:
        logger.warning(
            "Daily extraction cap (200) reached for tenant %s -- skipping %d email(s)",
            tenant_id, len(email_ids),
        )
        return 0

    # Load emails not yet extracted, with priority >= 3
    result = await db.execute(
        select(Email)
        .join(EmailScore, EmailScore.email_id == Email.id)
        .where(
            Email.id.in_(email_ids[:remaining]),
            Email.context_extracted_at.is_(None),
            EmailScore.priority >= 3,
        )
    )
    emails = result.scalars().all()

    extracted_count = 0
    for email_obj in emails:
        try:
            extraction = await extract_email_context(
                db, tenant_id, email_obj, integration
            )
            if extraction is not None:
                # Route low-confidence items to review
                await _route_low_confidence(
                    db, tenant_id, email_obj, extraction["extracted"]
                )
                extracted_count += 1

            # Mark as extracted regardless (even if None = skipped)
            email_obj.context_extracted_at = datetime.now(timezone.utc)
        except Exception:
            logger.exception(
                "Context extraction failed for email_id=%s", email_obj.id
            )

    await db.commit()
    return extracted_count
```

### Review API Endpoints
```python
# In api/email.py

class ContextReviewOut(BaseModel):
    id: UUID
    email_id: UUID
    extracted_data: dict
    status: str
    created_at: datetime

@router.get("/context-reviews", response_model=list[ContextReviewOut])
async def list_context_reviews(
    status: str = Query("pending"),
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    result = await db.execute(
        select(EmailContextReview)
        .where(EmailContextReview.status == status)
        .order_by(EmailContextReview.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()

@router.post("/context-reviews/{review_id}/approve")
async def approve_context_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
    user: TokenPayload = Depends(require_tenant),
):
    review = await db.get(EmailContextReview, review_id)
    if not review or review.status != "pending":
        raise HTTPException(404, "Review not found or already processed")

    # Write low-confidence items to context store via shared writer
    for item in review.extracted_data.get("low_confidence_items", []):
        # Route to appropriate writer based on item type
        ...

    review.status = "approved"
    review.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "approved"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No context extraction | Phase 74 built extractor + writer | Phase 74 (just completed) | Extraction engine ready, needs wiring |
| Manual context entry | AI extraction from email bodies | Phase 74 | Context store enriches automatically |
| No confidence routing | Per-item confidence from LLM | Phase 74 | Enables Phase 75's routing logic |

## Open Questions

1. **Should the 200/day cap be hardcoded or configurable per-tenant?**
   - What we know: Phase description says "200/day per-tenant cap". Prior decisions note this is pending.
   - Recommendation: Hardcode 200 as default parameter in `_check_daily_extraction_cap(db, tenant_id, cap=200)`. Easy to make configurable later by reading from `tenant.settings` if needed.

2. **Should review approval write items with original confidence or upgraded confidence?**
   - What we know: Items in review are "low" confidence. User approving them implies they're valid.
   - Recommendation: Write approved items with confidence="medium" (upgraded from "low") since human review validates them.

3. **Should extraction have its own per-cycle batch limit?**
   - What we know: Per-integration timeout is 60s. Each extraction = 1 Claude API call (~2-5s).
   - Recommendation: Limit to 10 extractions per sync cycle to stay well within timeout. Remaining emails get extracted on subsequent cycles.

4. **How should the review table store item types for approval routing?**
   - What we know: Extraction returns 5 categories (contacts, topics, deal_signals, relationship_signals, action_items). Each has different writer functions.
   - Recommendation: Store as `{"items": [{"type": "contact", "data": {...}}, {"type": "insight", "data": {...}}]}` so the approval endpoint can route to the correct writer function.

## Sources

### Primary (HIGH confidence)
- `backend/src/flywheel/services/gmail_sync.py` -- sync loop, scoring cap, drafting pattern (read in full)
- `backend/src/flywheel/engines/email_context_extractor.py` -- extraction engine built in Phase 74 (read in full)
- `backend/src/flywheel/engines/context_store_writer.py` -- shared writer with dedup (read in full)
- `backend/src/flywheel/db/models.py` -- Email, EmailScore, ContextEntry models (read relevant sections)
- `backend/src/flywheel/api/email.py` -- existing email API endpoints (read header/structure)
- `backend/alembic/versions/020_email_models.py` -- RLS pattern for email tables (read in full)
- `backend/alembic/versions/036_voice_profile_expansion.py` -- recent migration pattern (read in full)

### Secondary (MEDIUM confidence)
- `.planning/phases/74-email-context-extractor/74-RESEARCH.md` -- Phase 74 research for architecture context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- follows exact patterns from existing sync loop (scoring cap, drafting step, non-fatal wrappers)
- Pitfalls: HIGH -- identified from reading actual codebase (timeout budget, cascade, confidence splitting)
- Migration: HIGH -- RLS pattern verified from 020_email_models.py, column pattern from 036

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- internal codebase patterns don't change externally)
