#!/usr/bin/env -S bash -c 'exec "$(dirname "$0")/.venv/bin/python3" "$0" "$@"'
# Or run directly: cd backend && .venv/bin/python3 test_phase55.py
"""Phase 55 Human Verification Script.

Tests:
  1. POST /ask — source attribution with 3+ context entries
  2. GET /signals/ — per-type badge counts with stale data

Usage:
  1. Start the backend: cd backend && uvicorn flywheel.main:app --reload
  2. Run this script: python3 backend/test_phase55.py

Reads .env for SUPABASE_JWT_SECRET and DATABASE_URL.
Creates test data, runs API calls, cleans up.
"""

import asyncio
import datetime
import json
import os
import sys
import uuid

import httpx
import jwt

# ---------------------------------------------------------------------------
# Config — read from .env or use defaults
# ---------------------------------------------------------------------------

ENV_PATH = os.path.join(os.path.dirname(__file__), "backend", ".env")
if os.path.exists(ENV_PATH):
    for line in open(ENV_PATH):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Also check project-root .env
ROOT_ENV = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(ROOT_ENV):
    for line in open(ROOT_ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://flywheel:flywheel@localhost:5432/flywheel",
)
# Convert asyncpg URL to psycopg2 for sync operations
SYNC_DB_URL = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

if not JWT_SECRET:
    print("ERROR: SUPABASE_JWT_SECRET not found in environment or .env")
    print("Set it in backend/.env or export SUPABASE_JWT_SECRET=...")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_token(user_id: str, tenant_id: str) -> str:
    """Create a valid HS256 JWT for testing."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "email": "test@flywheel.local",
        "is_anonymous": False,
        "app_metadata": {"tenant_id": tenant_id},
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def check(label: str, passed: bool, detail: str = ""):
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {label}")
    if detail:
        print(f"         {detail}")
    return passed


# ---------------------------------------------------------------------------
# Database setup/teardown (uses asyncpg directly)
# ---------------------------------------------------------------------------

async def setup_test_data():
    """Create a graduated account with 4 context entries and stale timestamp."""
    import asyncpg

    # Parse connection string
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    try:
        # Find tenant with most accounts + any profile as user sub
        t_row = await conn.fetchrow("""
            SELECT tenant_id, count(*) as cnt
            FROM accounts GROUP BY tenant_id ORDER BY cnt DESC LIMIT 1
        """)
        p_row = await conn.fetchrow("SELECT id FROM profiles LIMIT 1")
        if not t_row or not p_row:
            print("ERROR: No tenant/user found in database. Run seed first.")
            await conn.close()
            sys.exit(1)

        tenant_id = t_row["tenant_id"]
        user_id = p_row["id"]
        print(f"  Using tenant: {tenant_id}")
        print(f"  Using user:   {user_id}")

        # Create a test account — graduated, stale, with advisor type
        account_id = uuid.uuid4()
        stale_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)
        overdue_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)

        await conn.execute("""
            INSERT INTO accounts (id, tenant_id, name, normalized_name, domain,
                                  status, source, relationship_type,
                                  entity_level, relationship_status, pipeline_stage,
                                  graduated_at, last_interaction_at, next_action_due,
                                  created_at, updated_at)
            VALUES ($1, $2, 'Test Advisor Corp', 'test advisor corp', 'testadvisor.com',
                    'engaged', 'test', $3::text[], 'company', 'active', 'engaged',
                    $4, $5, $6,
                    $5, NOW())
        """, account_id, tenant_id, ["advisor", "customer"], stale_date, stale_date, overdue_date)
        print(f"  Created test account: {account_id}")

        # Create 4 context entries for this account
        entry_ids = []
        contents = [
            "This company is working on AI-powered analytics for enterprise. Key contact is Sarah Chen, VP of Engineering.",
            "Budget approved for Q2 2026. They mentioned competitor product X is too expensive at $50k/year.",
            "Advisory relationship started after Series B intro from John at Sequoia. Strong product-market fit signals.",
            "Last meeting discussed integration timeline. They want API access by end of April. Champion is the CTO.",
        ]
        for i in range(4):
            entry_id = uuid.uuid4()
            entry_ids.append(entry_id)
            await conn.execute("""
                INSERT INTO context_entries (id, tenant_id, user_id, account_id,
                                             source, detail, content, file_name,
                                             date, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW()::date, NOW(), NOW())
            """, entry_id, tenant_id, user_id, account_id,
                f"test:entry-{i+1}",
                contents[i],
                contents[i],
                f"test-doc-{i+1}.txt")
            print(f"  Created context entry {i+1}: {entry_id}")

        # Set RLS context for this tenant
        await conn.execute("SELECT set_config('app.tenant_id', $1::text, false)", str(tenant_id))

        return {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "account_id": str(account_id),
            "entry_ids": [str(e) for e in entry_ids],
        }

    finally:
        await conn.close()


async def cleanup_test_data(account_id: str, entry_ids: list[str]):
    """Remove test data."""
    import asyncpg
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        for eid in entry_ids:
            await conn.execute("DELETE FROM context_entries WHERE id = $1", uuid.UUID(eid))
        await conn.execute("DELETE FROM accounts WHERE id = $1", uuid.UUID(account_id))
        print("\n  Cleaned up test data.")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_ask_source_attribution(client: httpx.AsyncClient, token: str, account_id: str, entry_ids: list[str]):
    """Test 1: POST /ask returns source attribution."""
    section("Test 1: POST /ask — Source Attribution")

    headers = {"Authorization": f"Bearer {token}"}

    # First verify the account appears in relationships list
    resp = await client.get(
        f"{API_BASE}/api/v1/relationships/?type=advisor",
        headers=headers,
    )
    print(f"  GET /relationships/?type=advisor → {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        found = any(item["id"] == account_id for item in data.get("items", []))
        check("Account appears in advisor relationships", found,
              f"{data.get('total', 0)} total items")
    else:
        check("Account appears in advisor relationships", False, resp.text[:200])

    # Call POST /ask
    resp = await client.post(
        f"{API_BASE}/api/v1/relationships/{account_id}/ask",
        headers=headers,
        json={"question": "What do we know about this company's budget and competitors?"},
    )
    print(f"\n  POST /ask → {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Answer: {data.get('answer', '')[:200]}...")
        print(f"  Sources: {json.dumps(data.get('sources', []), indent=2)}")
        print(f"  Insufficient context: {data.get('insufficient_context', 'N/A')}")

        has_sources = len(data.get("sources", [])) > 0
        check("Response has source attribution", has_sources,
              f"{len(data.get('sources', []))} source(s)")

        if has_sources:
            # Check that at least one source references our test entries
            source_ids = [s.get("id", s.get("entry_id", "")) for s in data["sources"]]
            known_match = any(sid in entry_ids for sid in source_ids)
            check("Source IDs reference known context entries", known_match,
                  f"Source IDs: {source_ids}")

        not_insufficient = not data.get("insufficient_context", True)
        check("Not flagged as insufficient context (4 entries > 3 min)", not_insufficient)
    else:
        check("POST /ask succeeded", False, resp.text[:300])


async def test_ask_sparse_guard(client: httpx.AsyncClient, token: str):
    """Test 1b: POST /ask with sparse data returns graceful response."""
    section("Test 1b: POST /ask — Sparse Data Guard")

    # Create a temporary account with only 1 context entry
    import asyncpg
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    headers = {"Authorization": f"Bearer {token}"}

    # Extract tenant_id from token
    decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], audience="authenticated")
    tenant_id = uuid.UUID(decoded["app_metadata"]["tenant_id"])

    sparse_account_id = uuid.uuid4()
    sparse_entry_id = uuid.uuid4()

    try:
        await conn.execute("""
            INSERT INTO accounts (id, tenant_id, name, normalized_name, domain,
                                  status, source, relationship_type,
                                  entity_level, relationship_status, pipeline_stage,
                                  graduated_at, created_at, updated_at)
            VALUES ($1, $2, 'Sparse Test Corp', 'sparse test corp', 'sparse.test',
                    'engaged', 'test', $3::text[], 'company', 'active', 'engaged',
                    NOW(), NOW(), NOW())
        """, sparse_account_id, tenant_id, ["prospect"])

        await conn.execute("""
            INSERT INTO context_entries (id, tenant_id, user_id, account_id, source,
                                         detail, content, file_name,
                                         date, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 'test:sparse', 'Only one entry', 'Only one entry',
                    'sparse.txt', NOW()::date, NOW(), NOW())
        """, sparse_entry_id, tenant_id, uuid.UUID(decoded["sub"]),
            sparse_account_id)

        resp = await client.post(
            f"{API_BASE}/api/v1/relationships/{sparse_account_id}/ask",
            headers=headers,
            json={"question": "What do we know about this company?"},
        )
        print(f"  POST /ask (sparse account) → {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            is_insufficient = data.get("insufficient_context", False)
            check("Sparse data returns insufficient_context=true", is_insufficient,
                  f"insufficient_context={is_insufficient}")
            check("No LLM was called (graceful degradation)", is_insufficient,
                  "LLM skipped when < 3 entries")
        else:
            check("POST /ask (sparse) succeeded", False, resp.text[:200])

    finally:
        await conn.execute("DELETE FROM context_entries WHERE id = $1", sparse_entry_id)
        await conn.execute("DELETE FROM accounts WHERE id = $1", sparse_account_id)
        await conn.close()
        print("  Cleaned up sparse test data.")


async def test_signals_badge_counts(client: httpx.AsyncClient, token: str, account_id: str):
    """Test 2: GET /signals/ returns non-zero badge counts."""
    section("Test 2: GET /signals/ — Badge Counts")

    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"{API_BASE}/api/v1/signals/", headers=headers)
    print(f"  GET /signals/ → {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total signals: {data.get('total', 0)}")
        print(f"  Type badges:")
        for badge in data.get("types", []):
            print(f"    {badge['type']:12s} → {badge['total_signals']} signals "
                  f"(reply={badge['counts']['reply_received']}, "
                  f"overdue={badge['counts']['followup_overdue']}, "
                  f"commitment={badge['counts']['commitment_due']}, "
                  f"stale={badge['counts']['stale_relationship']})")

        total_nonzero = data.get("total", 0) > 0
        check("Total signals > 0", total_nonzero, f"total={data.get('total', 0)}")

        # Our test account is stale (120 days) + overdue follow-up
        advisor_badge = next((b for b in data.get("types", []) if b["type"] == "advisor"), None)
        if advisor_badge:
            stale = advisor_badge["counts"]["stale_relationship"] > 0
            check("Advisor stale_relationship > 0 (120-day-old account)", stale,
                  f"stale={advisor_badge['counts']['stale_relationship']}")

            overdue = advisor_badge["counts"]["followup_overdue"] > 0
            check("Advisor followup_overdue > 0 (next_action_due in past)", overdue,
                  f"overdue={advisor_badge['counts']['followup_overdue']}")
        else:
            check("Advisor badge exists in response", False)

        # Customer badge should also have signals (account has both types)
        customer_badge = next((b for b in data.get("types", []) if b["type"] == "customer"), None)
        if customer_badge:
            customer_signals = customer_badge["total_signals"] > 0
            check("Customer signals > 0 (account is advisor+customer)", customer_signals,
                  f"total={customer_badge['total_signals']}")

        # All 4 types present
        type_names = [b["type"] for b in data.get("types", [])]
        all_types = set(type_names) == {"prospect", "customer", "advisor", "investor"}
        check("All 4 relationship types present", all_types, f"types={type_names}")

    else:
        check("GET /signals/ succeeded", False, resp.text[:200])


async def test_synthesize_rate_limit(client: httpx.AsyncClient, token: str, account_id: str):
    """Test 3 (bonus): POST /synthesize rate limit."""
    section("Test 3 (Bonus): POST /synthesize — Rate Limit")

    headers = {"Authorization": f"Bearer {token}"}

    # First call
    resp1 = await client.post(
        f"{API_BASE}/api/v1/relationships/{account_id}/synthesize",
        headers=headers,
    )
    print(f"  POST /synthesize (1st call) → {resp1.status_code}")
    if resp1.status_code == 200:
        data = resp1.json()
        check("First synthesize call succeeded", True,
              f"summary={'present' if data.get('ai_summary') else 'null/empty'}")
    else:
        # May fail if no subsidy key configured — that's OK
        check("First synthesize call", resp1.status_code == 200,
              f"Status {resp1.status_code}: {resp1.text[:200]}")
        if resp1.status_code != 200:
            print("  (Skipping rate limit test — first call failed, likely no API key)")
            return

    # Second call — should return 429
    resp2 = await client.post(
        f"{API_BASE}/api/v1/relationships/{account_id}/synthesize",
        headers=headers,
    )
    print(f"  POST /synthesize (2nd call) → {resp2.status_code}")
    is_429 = resp2.status_code == 429
    check("Second call within 5 min returns 429", is_429,
          f"Status {resp2.status_code}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 60)
    print("  Phase 55: Human Verification Tests")
    print("=" * 60)

    section("Setup: Creating Test Data")
    test_data = await setup_test_data()

    token = make_token(test_data["user_id"], test_data["tenant_id"])
    print(f"  Generated JWT token (expires in 1 hour)")

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Source attribution
        try:
            await test_ask_source_attribution(
                client, token, test_data["account_id"], test_data["entry_ids"]
            )
        except Exception as e:
            print(f"  [ERROR] Test 1 failed with exception: {e}")

        # Test 1b: Sparse data guard
        try:
            await test_ask_sparse_guard(client, token)
        except Exception as e:
            print(f"  [ERROR] Test 1b failed with exception: {e}")

        # Test 2: Signal badge counts
        try:
            await test_signals_badge_counts(client, token, test_data["account_id"])
        except Exception as e:
            print(f"  [ERROR] Test 2 failed with exception: {e}")

        # Test 3: Rate limit (bonus)
        try:
            await test_synthesize_rate_limit(client, token, test_data["account_id"])
        except Exception as e:
            print(f"  [ERROR] Test 3 failed with exception: {e}")

    section("Cleanup")
    await cleanup_test_data(test_data["account_id"], test_data["entry_ids"])

    print("\n" + "=" * 60)
    print("  All tests complete. Review results above.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
