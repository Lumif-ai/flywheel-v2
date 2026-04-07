# Phase 79: MCP Tools - Research

**Researched:** 2026-03-30
**Domain:** FastMCP tool implementation, response formatting for Claude Code, tool description optimization
**Confidence:** HIGH

## Summary

Phase 79 adds 10 `@mcp.tool()` functions to `server.py` that wrap the `FlywheelClient` methods built in Phase 78. The existing codebase has 3 tools that establish the exact pattern: sync functions with `-> str` return type, fresh `FlywheelClient()` per call, two-level exception handling (FlywheelAPIError then generic Exception), and docstrings that become Claude Code's tool descriptions.

The primary research questions are: (1) how to format responses so Claude Code can effectively use the data, (2) how to write tool descriptions that match natural language intent, (3) how to handle the `flywheel_fetch_account` name-search requirement when the api_client only has `fetch_account(account_id)`, and (4) how to organize 13 tools (3 existing + 10 new) in a single file without it becoming unwieldy.

Two significant gaps were discovered: (a) `flywheel_fetch_account` needs a `search_accounts()` client method for name search (backend supports `GET /accounts/?search=`), and (b) `flywheel_fetch_meetings` for unprocessed meetings needs careful handling -- the list endpoint does NOT return `ai_summary` or `transcript_url` (those are owner-only on the detail endpoint), but it DOES return `processing_status` which can be used to filter for `pending`/`recorded` meetings.

**Primary recommendation:** Follow the existing `@mcp.tool()` pattern exactly. Format responses as structured text (not raw JSON) with clear labels. Add a `search_accounts(name)` method to `FlywheelClient` for MCP-06. Use `?processing_status=pending` for MCP-03 unprocessed meeting filtering. Group tools by domain (discovery, read, write) with comment headers.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastmcp | >=2.0 | MCP server framework, `@mcp.tool()` decorator | Already in use |
| httpx | >=0.27 | Synchronous HTTP via FlywheelClient | Already in use |

### Supporting
No new dependencies. All 10 tools use only FlywheelClient (httpx) and stdlib string formatting.

## Architecture Patterns

### Tool Organization in server.py

Group tools with section headers matching their domain. Keep all tools in one file (13 total is manageable).

```python
# --------------------------------------------------------------------------
# Skill Discovery Tools (MCP-01, MCP-02)
# --------------------------------------------------------------------------

@mcp.tool()
def flywheel_fetch_skills(...) -> str: ...

@mcp.tool()
def flywheel_fetch_skill_prompt(...) -> str: ...

# --------------------------------------------------------------------------
# Data Read Tools (MCP-03, MCP-04, MCP-05, MCP-06)
# --------------------------------------------------------------------------

@mcp.tool()
def flywheel_fetch_meetings(...) -> str: ...

@mcp.tool()
def flywheel_fetch_upcoming(...) -> str: ...

@mcp.tool()
def flywheel_fetch_tasks(...) -> str: ...

@mcp.tool()
def flywheel_fetch_account(...) -> str: ...

# --------------------------------------------------------------------------
# Action/Sync Tools (MCP-07)
# --------------------------------------------------------------------------

@mcp.tool()
def flywheel_sync_meetings() -> str: ...

# --------------------------------------------------------------------------
# Write Tools (MCP-08, MCP-09, MCP-10)
# --------------------------------------------------------------------------

@mcp.tool()
def flywheel_save_document(...) -> str: ...

@mcp.tool()
def flywheel_save_meeting_summary(...) -> str: ...

@mcp.tool()
def flywheel_update_task(...) -> str: ...
```

### Response Formatting Pattern

Claude Code processes MCP tool responses as text context. The existing `flywheel_read_context` tool formats results as labeled text blocks, not raw JSON. This is the pattern to follow.

**Principle:** Format responses as structured text that a human (or Claude) can read naturally. Use headers, labels, and separators -- not JSON dumps.

```python
# GOOD: Structured text Claude can read and reason about
def flywheel_fetch_skills() -> str:
    client = FlywheelClient()
    result = client.fetch_skills()
    skills = result.get("items", [])
    if not skills:
        return "No skills found."

    lines = []
    for s in skills:
        triggers = ", ".join(s.get("triggers", []))
        lines.append(
            f"**{s['name']}** ({s.get('tags', ['uncategorized'])[0]})\n"
            f"  {s.get('description', 'No description')}\n"
            f"  Triggers: {triggers}"
        )
    return "\n\n".join(lines)

# BAD: Raw JSON dump
def flywheel_fetch_skills() -> str:
    client = FlywheelClient()
    result = client.fetch_skills()
    return json.dumps(result)  # Claude has to parse this mentally
```

**Key formatting rules:**
1. **Lists:** One item per block with bold name, description on next line, metadata indented
2. **Single entities:** Key-value pairs with clear labels, sections for nested data
3. **Empty results:** Descriptive message with suggestion for what to try next
4. **Error results:** Returned as plain text (already handled by exception pattern)
5. **IDs:** Always include entity IDs so Claude can chain tools (e.g., fetch account -> save document with account_id)

### Tool Description Pattern (Docstrings)

The spec provides pre-written tool descriptions for all 10 tools. These become the docstring. The existing tools show the pattern: first line is a brief summary, then multi-line detail about when to use, what it returns, and what NOT to use it for.

**What makes a good MCP tool description for Claude Code:**

1. **First line = intent match.** Claude Code selects tools based on description relevance to user's request. The first line should cover the most common way a user would ask for this.
2. **"Use for" / "Use this when" lines.** Help Claude Code match intent to the right tool.
3. **"Returns" line.** Tell Claude Code what to expect so it can plan multi-tool workflows.
4. **"After this, do X" lines.** Guide Claude Code to chain tools correctly (e.g., "After fetching, prepare each meeting using the meeting-prep skill").
5. **"NOT for" lines.** Prevent misrouting. Critical when tools have overlapping descriptions.

Example from existing code:
```python
@mcp.tool()
def flywheel_read_context(query: str) -> str:
    """Search Flywheel's business knowledge base.

    Use for: company intel, people profiles, market signals, competitive
    intelligence, deal context, meeting history.
    Returns stored business knowledge that compounds over time.
    NOT for code documentation, README files, or project configs.
    """
```

These descriptions should be used **verbatim** from the spec as docstrings. Do not rewrite them.

### The flywheel_fetch_account Name Search Problem

**Problem:** MCP-06 requires searching by name (fuzzy match) or UUID. The `FlywheelClient.fetch_account(account_id)` only takes a UUID. The backend `GET /accounts/?search=name` supports ILIKE name search.

**Solution:** Add a `search_accounts(name)` method to `FlywheelClient` that calls `GET /accounts/?search={name}&limit=5`. The MCP tool tries UUID first (if input looks like a UUID), then falls back to name search.

```python
# New method needed in api_client.py
def search_accounts(self, name: str, limit: int = 5) -> dict:
    """GET /api/v1/accounts/?search=name -- search accounts by name."""
    return self._request(
        "get", "/api/v1/accounts/", params={"search": name, "limit": limit}
    )
```

```python
# MCP tool logic
@mcp.tool()
def flywheel_fetch_account(identifier: str) -> str:
    """..."""
    client = FlywheelClient()
    # Try UUID first
    try:
        from uuid import UUID as _UUID
        _UUID(identifier)  # validates format
        result = client.fetch_account(identifier)
        return _format_account(result)
    except ValueError:
        pass  # Not a UUID, search by name

    results = client.search_accounts(identifier)
    items = results.get("items", [])
    if not items:
        return f"No account found matching '{identifier}'."
    if len(items) == 1:
        # Fetch full detail for the matched account
        full = client.fetch_account(items[0]["id"])
        return _format_account(full)
    # Multiple matches -- list them
    lines = [f"Multiple accounts match '{identifier}':"]
    for a in items[:5]:
        lines.append(f"  - {a['name']} (ID: {a['id']}, status: {a.get('status', '?')})")
    lines.append("\nSpecify the account ID for full details.")
    return "\n".join(lines)
```

### The flywheel_fetch_meetings Transcript Problem (CRITICAL)

**Discovery:** The list endpoint `GET /meetings/` does NOT return `ai_summary` or `transcript_url`. Those are owner-only fields on the detail endpoint `GET /meetings/{id}`. The list endpoint DOES return `processing_status`.

**What the spec says:** MCP-03 acceptance criteria state "Each meeting includes: id, title, start_time, attendees, transcript text" and "Full transcript returned."

**What the backend provides:**
- `GET /meetings/?processing_status=pending` -- returns list with metadata (id, title, meeting_date, attendees, processing_status) but NO transcript/ai_summary
- `GET /meetings/{id}` -- returns full detail including `transcript_url` (owner-only) and `ai_summary` (owner-only)
- `transcript_url` is a Supabase Storage URL, not inline text

**Approach for MCP-03:**
1. Use `?processing_status=pending` to find unprocessed meetings (NOT `ai_summary IS NULL` client-side filtering -- the list endpoint doesn't return ai_summary)
2. For each unprocessed meeting, the FlywheelClient would need a `get_meeting(meeting_id)` method to fetch detail with transcript_url
3. The transcript_url points to Supabase Storage -- the MCP tool returns the URL, and Claude Code can potentially fetch it, OR the tool returns just the meeting metadata and lets Claude Code decide to process

**Recommended approach:** Add a `get_meeting(meeting_id)` method to FlywheelClient. The `flywheel_fetch_meetings` tool first lists unprocessed meetings (metadata only), then for each meeting fetches the detail endpoint to get the `transcript_url`. Return the transcript URL in the response -- Claude Code or the skill prompt can handle downloading it. Do NOT attempt to download/inline the transcript in the MCP tool itself (it's a Supabase signed URL that may require different auth).

**Alternative simpler approach:** Return meeting metadata WITHOUT transcripts from `flywheel_fetch_meetings`. The tool description says "including full transcripts" but the actual workflow is: Claude reads the meeting list, then for each meeting it needs to process, it could call `flywheel_read_context` or the backend's existing meeting processing. This aligns better with the "Claude Code is the brain" architecture.

**API Client gaps for this:**
```python
# Needed in api_client.py
def get_meeting(self, meeting_id: str) -> dict:
    """GET /api/v1/meetings/{meeting_id} -- get full meeting detail."""
    return self._request("get", f"/api/v1/meetings/{meeting_id}")
```

### The flywheel_fetch_tasks Multi-Status Problem

**Discovery:** The backend `GET /tasks/?status=X` supports only a SINGLE status value. MCP-05 wants status IN ('detected', 'in_review', 'confirmed', 'in_progress', 'deferred').

**Solution:** Fetch ALL tasks (no status filter), then filter client-side to exclude 'done' and 'dismissed'. This is simpler and more robust than making 5 separate API calls.

```python
# In the MCP tool
result = client.fetch_tasks(limit=50)  # no status filter = all
items = result.get("items", [])
actionable = [t for t in items if t.get("status") not in ("done", "dismissed")]
```

### Parameter Design

Keep parameters simple and match what Claude Code would naturally provide:

| Tool | Parameters | Notes |
|------|-----------|-------|
| flywheel_fetch_skills | (none) | No params needed |
| flywheel_fetch_skill_prompt | skill_name: str | Required |
| flywheel_fetch_meetings | limit: int = 10 | Unprocessed only (processing_status=pending) |
| flywheel_fetch_upcoming | limit: int = 10 | Today's upcoming |
| flywheel_fetch_tasks | status: str = "" | Empty = all actionable statuses |
| flywheel_fetch_account | identifier: str | UUID or name |
| flywheel_sync_meetings | (none) | No params needed |
| flywheel_save_document | title: str, content: str, skill_name: str = "", account_id: str = "" | Empty strings = optional |
| flywheel_save_meeting_summary | meeting_id: str, summary: str | Both required |
| flywheel_update_task | task_id: str, status: str = "", priority: str = "" | At least one field |

**Use empty strings for optional params, not Optional[str].** FastMCP maps parameters to JSON Schema. Empty string defaults are clearer for Claude Code than None defaults -- Claude sees a string field and provides a string.

### Anti-Patterns to Avoid
- **Returning raw JSON:** Claude Code reads text better than JSON. Format as readable text.
- **Giant monolithic responses:** Trim to what's useful. Don't return 50 fields when 8 matter.
- **Missing IDs in responses:** Always include entity IDs so Claude can chain tool calls.
- **Overly complex parameters:** Keep params flat and simple. No nested objects.
- **Using Optional[str] = None:** Use `str = ""` for optional string params in MCP tools for cleaner schema.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UUID detection | Regex matching | `uuid.UUID(identifier)` in try/except | Standard library handles all UUID formats |
| Response formatting | JSON serialization | f-string text formatting | Claude reads text better than JSON |
| Error handling | Custom error classes | Existing FlywheelAPIError pattern | Already handles 401, timeouts, parsing |
| Tool registration | Manual tool routing | `@mcp.tool()` decorator | FastMCP handles JSON Schema, transport |
| Unprocessed meeting filter | Client-side ai_summary check | `?processing_status=pending` query param | Backend already supports this filter |

## Common Pitfalls

### Pitfall 1: Tool Description Too Vague for Intent Matching
**What goes wrong:** Claude Code picks the wrong tool because descriptions overlap or are too generic.
**Why it happens:** "Fetch data" could match multiple tools. Claude Code uses semantic similarity on descriptions.
**How to avoid:** Use specific trigger phrases in descriptions. The spec provides optimized descriptions for each tool -- use them verbatim. Include "NOT for" lines to disambiguate.
**Warning signs:** Claude Code calls flywheel_fetch_meetings when user asks about tasks.

### Pitfall 2: Missing Entity IDs Break Tool Chaining
**What goes wrong:** Claude fetches meetings but can't save summaries because meeting IDs weren't in the response.
**Why it happens:** Formatting code omits IDs to keep output "clean."
**How to avoid:** ALWAYS include entity IDs in formatted output. Format as `(ID: abc-123)` after names.
**Warning signs:** Claude asks "what's the meeting ID?" after fetching meetings.

### Pitfall 3: Empty Results Return Confusing Messages
**What goes wrong:** Tool returns empty string or "[]" when no results found.
**Why it happens:** Naive formatting of empty lists.
**How to avoid:** Return descriptive messages: "No unprocessed meetings found. All meetings have been summarized." with actionable suggestions.
**Warning signs:** Claude gets confused by empty/minimal responses.

### Pitfall 4: Transcript URL vs Transcript Text Confusion
**What goes wrong:** MCP tool returns a Supabase storage URL instead of transcript text, and Claude can't read it.
**Why it happens:** The DB stores `transcript_url` (a URL to Supabase Storage), not inline transcript text. The detail endpoint returns this URL.
**How to avoid:** For Phase 79, return the `transcript_url` in the response and note it's a download link. The meeting's `summary` field (from Granola) may contain enough context for many use cases. In a future phase, consider adding a `/meetings/{id}/transcript` endpoint that returns the actual text.
**Warning signs:** Claude tries to use a URL as if it were transcript content.

### Pitfall 5: flywheel_fetch_account Double-Fetch Inefficiency
**What goes wrong:** Name search returns list items (minimal fields), then we fetch full detail -- two API calls.
**Why it happens:** GET /accounts/ returns list items, GET /accounts/{id} returns full detail with contacts/timeline.
**How to avoid:** This is acceptable and by design. The list endpoint doesn't return contacts/timeline. Two calls is correct for name search.
**Warning signs:** None -- this is the intended pattern.

### Pitfall 6: save_document Missing Frontend URL
**What goes wrong:** Document saved but Claude can't tell the user where to view it.
**Why it happens:** API response includes run_id but not the full URL.
**How to avoid:** Construct the library URL using `client.frontend_url` just like `flywheel_run_skill` does.
**Warning signs:** Claude says "Document saved" with no link.

### Pitfall 7: List Endpoint Doesn't Return Detail Fields
**What goes wrong:** Assuming `GET /meetings/` returns transcript or ai_summary, then filtering client-side on fields that aren't there.
**Why it happens:** List endpoints return summary/metadata, detail endpoints return full data. This is standard REST but easy to forget.
**How to avoid:** Check what each endpoint returns. `GET /meetings/` returns: id, title, meeting_date, duration_mins, attendees, meeting_type, processing_status, account_id, summary, provider, location. Does NOT return: transcript_url, ai_summary.
**Warning signs:** Filtering on `m.get("ai_summary")` always returns all items because the field is never present.

## Code Examples

### Complete Tool Implementation: flywheel_fetch_skills (MCP-01)
```python
@mcp.tool()
def flywheel_fetch_skills() -> str:
    """List all available Flywheel skills with descriptions, categories, and trigger
    phrases. Call this to discover what Flywheel can do for the user, or to find
    the right skill for a user's request. Returns skill names, descriptions,
    categories, trigger phrases, and context store contracts (what each skill
    reads/writes). Use trigger phrases to match natural language requests to skills."""
    try:
        client = FlywheelClient()
        result = client.fetch_skills()
        skills = result.get("items", [])
        if not skills:
            return "No skills available. Check that skills are seeded and enabled."

        lines = [f"Found {len(skills)} available skills:\n"]
        for s in skills:
            name = s.get("name", "unknown")
            desc = s.get("description", "No description")
            tags = s.get("tags", [])
            category = tags[0] if tags else "uncategorized"
            triggers = s.get("triggers", [])
            trigger_str = ", ".join(triggers) if triggers else "none"
            reads = ", ".join(s.get("contract_reads", [])) or "none"
            writes = ", ".join(s.get("contract_writes", [])) or "none"
            lines.append(
                f"**{name}** [{category}]\n"
                f"  {desc}\n"
                f"  Triggers: {trigger_str}\n"
                f"  Reads: {reads} | Writes: {writes}"
            )
        return "\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching skills: {exc}"
```

### Complete Tool Implementation: flywheel_fetch_meetings (MCP-03)
```python
@mcp.tool()
def flywheel_fetch_meetings(limit: int = 10) -> str:
    """Fetch meetings that haven't been processed yet, including transcripts.
    Use this during the morning brief to find meetings that need summarization
    and insight extraction. Returns meeting title, time, attendees, and transcript
    URL. Process each meeting's transcript, then save the summary via
    flywheel_save_meeting_summary."""
    try:
        client = FlywheelClient()
        # Use processing_status filter -- list endpoint doesn't return ai_summary
        result = client.fetch_meetings(processing_status="pending", limit=limit)
        meetings = result.get("items", [])
        if not meetings:
            return "No unprocessed meetings found. All meetings have been summarized."

        total = result.get("total", len(meetings))
        lines = [f"Found {len(meetings)} unprocessed meetings (of {total} total):\n"]
        for m in meetings:
            mid = m.get("id", "?")
            title = m.get("title", "Untitled")
            date = m.get("meeting_date", "?")
            attendees = m.get("attendees", [])
            att_str = ", ".join(
                a.get("name", a.get("email", "?"))
                for a in (attendees if isinstance(attendees, list) else [])
            ) if attendees else "none listed"
            summary = m.get("summary", "")

            lines.append(
                f"## {title}\n"
                f"ID: {mid}\n"
                f"Date: {date}\n"
                f"Attendees: {att_str}\n"
                f"Provider summary: {summary if summary else '(none)'}"
            )
        return "\n\n---\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching meetings: {exc}"
```

**Note:** The `fetch_meetings` client method needs a `processing_status` parameter. Currently it only has `time` and `limit`. This is an api_client gap (see below).

### Complete Tool Implementation: flywheel_fetch_account (MCP-06)
```python
@mcp.tool()
def flywheel_fetch_account(identifier: str) -> str:
    """Fetch detailed information about an account (prospect, customer, or partner).
    Search by account ID or name (fuzzy match). Returns company details, contacts,
    recent meetings, context store entries, and outreach history. Use this before
    meeting prep, outreach drafting, or any account-specific skill execution."""
    try:
        client = FlywheelClient()
        # Try UUID first
        try:
            from uuid import UUID as _UUID
            _UUID(identifier)
            result = client.fetch_account(identifier)
            return _format_account_detail(result)
        except ValueError:
            pass

        # Name search
        results = client.search_accounts(identifier)
        items = results.get("items", [])
        if not items:
            return f"No account found matching '{identifier}'."
        if len(items) == 1:
            full = client.fetch_account(items[0]["id"])
            return _format_account_detail(full)

        lines = [f"Multiple accounts match '{identifier}':"]
        for a in items[:5]:
            lines.append(
                f"  - {a['name']} (ID: {a['id']}, status: {a.get('status', '?')})"
            )
        lines.append("\nSpecify the account ID for full details.")
        return "\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching account: {exc}"


def _format_account_detail(data: dict) -> str:
    """Format account detail response for Claude Code consumption."""
    name = data.get("name", "Unknown")
    aid = data.get("id", "?")
    domain = data.get("domain", "none")
    status = data.get("status", "?")
    fit_score = data.get("fit_score")
    fit_tier = data.get("fit_tier", "?")
    intel = data.get("intel", {})

    lines = [
        f"# {name}",
        f"ID: {aid}",
        f"Domain: {domain}",
        f"Status: {status}",
        f"Fit: {fit_tier}" + (f" ({fit_score})" if fit_score else ""),
    ]

    contacts = data.get("contacts", [])
    if contacts:
        lines.append(f"\n## Contacts ({len(contacts)})")
        for c in contacts:
            lines.append(f"  - {c.get('name', '?')} ({c.get('email', 'no email')})")

    timeline = data.get("recent_timeline", [])
    if timeline:
        lines.append(f"\n## Recent Activity ({len(timeline)} items)")
        for t in timeline[:5]:
            lines.append(f"  - [{t.get('type', '?')}] {t.get('summary', '?')}")

    return "\n".join(lines)
```

### Complete Tool Implementation: flywheel_save_document (MCP-08)
```python
@mcp.tool()
def flywheel_save_document(
    title: str,
    content: str,
    skill_name: str = "",
    account_id: str = "",
) -> str:
    """Save a skill's output to the Flywheel library. Send the raw content
    (markdown or structured text) -- Flywheel renders it with the design system.
    The document appears in the library UI immediately. Use this after every
    skill execution to persist the deliverable. Optionally link to a skill name
    and account."""
    try:
        client = FlywheelClient()
        metadata = {}
        if account_id:
            metadata["account_id"] = account_id
        result = client.save_document(
            title=title,
            skill_name=skill_name or "mcp-manual",
            markdown_content=content,
            metadata=metadata,
        )
        run_id = result.get("run_id") or result.get("id", "?")
        url = f"{client.frontend_url}/library"
        return f"Document '{title}' saved. View: {url}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error saving document: {exc}"
```

### Complete Tool Implementation: flywheel_update_task (MCP-10)
```python
@mcp.tool()
def flywheel_update_task(
    task_id: str,
    status: str = "",
    priority: str = "",
) -> str:
    """Update a task's status, priority, or suggested skill. Use this to confirm
    tasks, mark them done, assign a skill for execution, or change priority.
    Call this after executing a task's skill to mark it complete, or during
    triage to confirm or dismiss detected tasks."""
    try:
        fields = {}
        if status:
            fields["status"] = status
        if priority:
            fields["priority"] = priority
        if not fields:
            return "No fields to update. Provide status and/or priority."
        client = FlywheelClient()
        result = client.update_task(task_id, **fields)
        title = result.get("title", "Unknown task")
        new_status = result.get("status", "?")
        return f"Task '{title}' updated. Status: {new_status}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error updating task: {exc}"
```

## API Client Gaps (Beyond Phase 78)

Phase 78 adds 10 methods to FlywheelClient. Phase 79 needs two additional methods:

### 1. search_accounts (for MCP-06 name search)
```python
def search_accounts(self, name: str, limit: int = 5) -> dict:
    """GET /api/v1/accounts/ -- search accounts by name (ILIKE)."""
    return self._request(
        "get", "/api/v1/accounts/", params={"search": name, "limit": limit}
    )
```
Maps to existing backend endpoint `GET /accounts/?search=` which does `Account.name.ilike(f"%{search}%") | Account.domain.ilike(f"%{search}%")`. Verified in `backend/src/flywheel/api/accounts.py` lines 213-216.

### 2. fetch_meetings needs processing_status param
The Phase 78 `fetch_meetings(time, limit, offset)` method does not expose the `processing_status` query parameter that the backend supports. Either:
- (a) Add `processing_status` param to the existing method, or
- (b) The MCP tool passes it manually

Option (a) is cleaner. The method signature becomes:
```python
def fetch_meetings(
    self, time: str | None = None, processing_status: str | None = None,
    limit: int = 50, offset: int = 0,
) -> dict:
    """GET /api/v1/meetings/ -- list meetings with optional filters."""
    params: dict = {"limit": limit, "offset": offset}
    if time is not None:
        params["time"] = time
    if processing_status is not None:
        params["processing_status"] = processing_status
    return self._request("get", "/api/v1/meetings/", params=params)
```

### 3. get_meeting (for meeting detail with transcript_url)
```python
def get_meeting(self, meeting_id: str) -> dict:
    """GET /api/v1/meetings/{meeting_id} -- get full meeting detail."""
    return self._request("get", f"/api/v1/meetings/{meeting_id}")
```
Needed if we want to return transcript_url for individual meetings. The list endpoint does not include it.

## Response Format Reference

Each tool should follow this response structure:

| Tool | Success Response Pattern |
|------|------------------------|
| flywheel_fetch_skills | "Found N skills:" + formatted list with triggers |
| flywheel_fetch_skill_prompt | Raw system_prompt text (Claude will follow it as instructions) |
| flywheel_fetch_meetings | "Found N unprocessed meetings:" + per-meeting metadata blocks (no inline transcript) |
| flywheel_fetch_upcoming | "N upcoming meetings today:" + per-meeting blocks |
| flywheel_fetch_tasks | "N tasks need attention:" + per-task blocks |
| flywheel_fetch_account | Full account detail with contacts section |
| flywheel_sync_meetings | "Synced: N new, N updated meetings." |
| flywheel_save_document | "Document 'title' saved. View: URL" |
| flywheel_save_meeting_summary | "Summary saved for 'meeting title'." |
| flywheel_update_task | "Task 'title' updated. Status: new_status" |

**Special case -- flywheel_fetch_skill_prompt:** Return the system_prompt as-is (raw text). Do NOT format or summarize it. Claude Code needs the full prompt to execute the skill.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| flywheel_run_skill (backend execution) | flywheel_fetch_skill_prompt (Claude Code execution) | This phase | Claude Code becomes the brain, uses its own Opus subscription |
| Polling for skill completion | Direct tool responses | This phase | Instant feedback, no 10-minute polling loops |
| 3 MCP tools | 13 MCP tools | This phase | Full Flywheel platform access from Claude Code |

## Open Questions

1. **Transcript access for MCP-03**
   - What we know: `transcript_url` is a Supabase Storage URL on the meeting detail endpoint. List endpoint doesn't include it.
   - What's unclear: Can the MCP tool (or Claude Code) download from Supabase Storage without separate auth? Is the URL a signed URL with temporary access?
   - Recommendation: For Phase 79, return meeting metadata + provider `summary` from list endpoint. If Claude needs the full transcript, it can be told to use `flywheel_read_context` to search for meeting intelligence (which was extracted from the transcript during processing). Adding a `/meetings/{id}/transcript` text endpoint is a future enhancement.

2. **Document save response shape**
   - What we know: POST /documents/from-content is being added (possibly in a parallel phase).
   - What's unclear: Whether response includes `run_id`, `document_id`, or a direct URL.
   - Recommendation: Use whatever ID field is returned and construct a library URL with `client.frontend_url`.

3. **Task status validation**
   - What we know: The backend validates status transitions (e.g., can't go from 'done' to 'detected').
   - What's unclear: Exact valid transitions.
   - Recommendation: Let the backend validate. If the MCP tool sends an invalid transition, the API returns an error, which the tool passes back to Claude as a string.

## Sources

### Primary (HIGH confidence)
- `cli/flywheel_mcp/server.py` - Existing 3 MCP tools, exact pattern to follow
- `cli/flywheel_mcp/api_client.py` - FlywheelClient with all methods
- `.planning/SPEC-flywheel-platform-architecture.md` lines 38-176 - All 10 tool descriptions and acceptance criteria
- `backend/src/flywheel/api/accounts.py` lines 189-252 - GET /accounts/ with search parameter (ILIKE)
- `backend/src/flywheel/api/meetings.py` lines 128-207 - GET /meetings/ with processing_status filter
- `backend/src/flywheel/api/meetings.py` lines 210-261 - GET /meetings/{id} with owner-only transcript_url/ai_summary
- `backend/src/flywheel/api/tasks.py` lines 234-268 - GET /tasks/ with single status filter
- `.planning/phases/78-mcp-infrastructure/78-RESEARCH.md` - Phase 78 research (api_client patterns)

### Secondary (MEDIUM confidence)
- FastMCP documentation - `@mcp.tool()` decorator behavior, docstring-to-description mapping

## Metadata

**Confidence breakdown:**
- Tool implementation pattern: HIGH - 3 existing tools provide exact template
- Response formatting: HIGH - existing flywheel_read_context shows the pattern
- Tool descriptions: HIGH - spec provides verbatim descriptions
- Account name search: HIGH - backend endpoint verified in source code
- Meeting transcript handling: HIGH - verified list vs detail endpoint field differences
- Task multi-status filtering: HIGH - verified backend supports single status only, client-side filter needed

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable domain, patterns established in codebase)
