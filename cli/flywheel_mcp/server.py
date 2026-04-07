"""Flywheel MCP server -- exposes Flywheel skills and context to Claude Code."""

from __future__ import annotations

import logging
import sys
import time

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

from flywheel_mcp.api_client import FlywheelAPIError, FlywheelClient

# --------------------------------------------------------------------------
# Logging (stderr -- MCP protocol uses stdout)
# --------------------------------------------------------------------------

logger = logging.getLogger("flywheel_mcp")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# --------------------------------------------------------------------------
# Invocation logging middleware
# --------------------------------------------------------------------------


class InvocationLogger(Middleware):
    """Log every MCP tool call with name, params, duration, and status."""

    async def on_call_tool(self, context, call_next):
        tool_name = context.message.name
        args = context.message.arguments
        start = time.time()
        try:
            result = await call_next(context)
            duration = time.time() - start
            logger.info(
                "tool_call tool=%s params=%s duration_ms=%d success=true",
                tool_name, args, round(duration * 1000),
            )
            return result
        except Exception as exc:
            duration = time.time() - start
            logger.error(
                "tool_call tool=%s params=%s duration_ms=%d success=false error=%s",
                tool_name, args, round(duration * 1000), exc,
            )
            raise


mcp = FastMCP("Flywheel")
mcp.add_middleware(InvocationLogger())


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_run_skill(
    skill_name: str = "meeting-prep",
    input_text: str = "",
) -> str:
    """Run a Flywheel skill like meeting-prep, company-intel, or flywheel.

    Use for business intelligence: preparing for meetings, researching
    companies, analyzing competitors, gathering market signals.
    Use 'flywheel' for the daily operating ritual: syncs meetings,
    processes recordings, preps upcoming meetings, and executes tasks.
    Returns a link to view the full results in the Flywheel web app.
    NOT for coding, file operations, or development tasks.
    """
    try:
        client = FlywheelClient()
        result = client.start_skill_run(skill_name, input_text)
        run_id = result.get("run_id") or result.get("id")
        if not run_id:
            return f"Skill run started but no run_id returned: {result}"

        # Poll with exponential backoff: 3s, 5s, 8s, then 10s intervals
        intervals = [3, 5, 8] + [10] * 57  # ~10 min total
        elapsed = 0
        for wait in intervals:
            time.sleep(wait)
            elapsed += wait
            run = client.get_run(run_id)
            status = run.get("status", "unknown")

            if status == "completed":
                url = f"{client.frontend_url}/library"
                return f"Skill '{skill_name}' completed. View results: {url}"

            if status == "failed":
                error = run.get("error") or run.get("error_message") or "Unknown error"
                return f"Skill '{skill_name}' failed: {error}"

        # Timeout
        url = f"{client.frontend_url}/library"
        return (
            f"Skill '{skill_name}' still running after {elapsed}s. "
            f"Check status: {url}"
        )
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error running skill: {exc}"


@mcp.tool()
def flywheel_read_context(query: str) -> str:
    """Search Flywheel's business knowledge base.

    Use for: company intel, people profiles, market signals, competitive
    intelligence, deal context, meeting history.
    Returns stored business knowledge that compounds over time.
    NOT for code documentation, README files, or project configs.
    """
    try:
        client = FlywheelClient()
        results = client.search_context(query)
        items = results.get("items", [])

        if not items:
            return (
                f"No context found for '{query}'. "
                "Try a different search term, or add context with flywheel_write_context."
            )

        lines = []
        for entry in items[:10]:
            file_name = entry.get("file_name", "unknown")
            confidence = entry.get("confidence", "?")
            content = entry.get("content", "")
            lines.append(f"[{file_name}] ({confidence}) {content}")

        return "\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error reading context: {exc}"


@mcp.tool()
def flywheel_write_context(
    content: str,
    file_name: str = "market-signals",
) -> str:
    """Store business knowledge in Flywheel's context store.

    Use for: facts about people, companies, deals, markets, competitors,
    industry signals, relationship notes, meeting outcomes.
    NOT for coding preferences, tool configs, or project setup.
    Common file names: market-signals, competitive-intel, icp-profiles,
    leadership, company-details, positioning.
    """
    try:
        client = FlywheelClient()
        result = client.write_context(file_name, content)
        entry = result.get("entry", {})
        entry_id = entry.get("id", "unknown")
        return f"Added to {file_name}. Entry ID: {entry_id}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error writing context: {exc}"


# --------------------------------------------------------------------------
# Skill Discovery Tools (MCP-01, MCP-02)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_fetch_skills() -> str:
    """List all available Flywheel skills with descriptions, categories, and trigger phrases. Call this to discover what Flywheel can do for the user, or to find the right skill for a user's request. Returns skill names, descriptions, categories, trigger phrases, and context store contracts (what each skill reads/writes). Use trigger phrases to match natural language requests to skills."""
    try:
        client = FlywheelClient()
        result = client.fetch_skills()
        skills = result.get("items", [])

        if not skills:
            return "No skills available. Check that skills are seeded and enabled."

        lines = [f"Found {len(skills)} available skills:\n"]
        for s in skills:
            name = s.get("name", "unknown")
            tags = s.get("tags", [])
            category = tags[0] if tags else "uncategorized"
            description = s.get("description", "")
            triggers = ", ".join(s.get("triggers", []))
            contract_reads = ", ".join(s.get("contract_reads", []))
            contract_writes = ", ".join(s.get("contract_writes", []))
            lines.append(
                f"**{name}** [{category}]\n"
                f"  {description}\n"
                f"  Triggers: {triggers}\n"
                f"  Reads: {contract_reads} | Writes: {contract_writes}"
            )

        return "\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching skills: {exc}"


@mcp.tool()
def flywheel_fetch_skill_prompt(skill_name: str) -> str:
    """Load the full execution instructions for a Flywheel skill by name. Returns the system prompt that you should follow to execute the skill. Call this after identifying which skill to run via flywheel_fetch_skills. The prompt contains step-by-step instructions, output format, and quality criteria."""
    try:
        client = FlywheelClient()
        result = client.fetch_skill_prompt(skill_name)
        system_prompt = result.get("system_prompt", "")

        if not system_prompt:
            return f"No prompt found for skill '{skill_name}'. Check the skill name with flywheel_fetch_skills."

        return system_prompt
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching skill prompt: {exc}"


# --------------------------------------------------------------------------
# Data Read Tools — Meetings (MCP-03, MCP-04)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_fetch_meetings(limit: int = 10) -> str:
    """Fetch meetings that haven't been processed yet, including full transcripts. Use this during the morning brief to find meetings that need summarization and insight extraction. Returns meeting title, time, attendees, and transcript. Process each meeting's transcript, then save the summary via flywheel_save_meeting_summary."""
    try:
        client = FlywheelClient()
        result = client.fetch_meetings(processing_status="pending", limit=limit)
        meetings = result.get("items", [])
        total = result.get("total", len(meetings))

        if not meetings:
            return "No unprocessed meetings found. All meetings have been summarized."

        lines = [f"Found {len(meetings)} unprocessed meetings (of {total} total):\n"]
        for m in meetings:
            title = m.get("title", "Untitled")
            mid = m.get("id", "?")
            meeting_date = m.get("meeting_date", "?")
            raw_attendees = m.get("attendees", [])
            if not isinstance(raw_attendees, list):
                raw_attendees = []
            attendee_names = [
                a.get("name", a.get("email", "?")) for a in raw_attendees
            ]
            summary = m.get("summary") or "(none)"
            lines.append(
                f"## {title}\n"
                f"ID: {mid}\n"
                f"Date: {meeting_date}\n"
                f"Attendees: {', '.join(attendee_names)}\n"
                f"Provider summary: {summary}"
            )

        return "\n\n---\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching meetings: {exc}"


@mcp.tool()
def flywheel_fetch_upcoming(limit: int = 10) -> str:
    """Fetch today's upcoming meetings with attendee details and linked accounts. Use this to identify meetings that need preparation. Returns meeting title, time, attendees (name + email), meeting type, and linked account if any. After fetching, prepare each meeting using the meeting-prep skill."""
    try:
        client = FlywheelClient()
        result = client.fetch_upcoming(limit=limit)
        meetings = result.get("items", [])

        if not meetings:
            return "No upcoming meetings today."

        lines = [f"{len(meetings)} upcoming meetings today:\n"]
        for m in meetings:
            title = m.get("title", "Untitled")
            mid = m.get("id", "?")
            meeting_date = m.get("meeting_date", "?")
            meeting_type = m.get("meeting_type") or "unclassified"
            raw_attendees = m.get("attendees", [])
            if not isinstance(raw_attendees, list):
                raw_attendees = []
            attendee_strs = [
                f"{a.get('name', '?')} ({a.get('email', '?')})"
                for a in raw_attendees
            ]
            account_id = m.get("account_id") or "none linked"
            lines.append(
                f"## {title}\n"
                f"ID: {mid}\n"
                f"Time: {meeting_date}\n"
                f"Type: {meeting_type}\n"
                f"Attendees: {', '.join(attendee_strs)}\n"
                f"Account: {account_id}"
            )

        return "\n\n---\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching upcoming meetings: {exc}"


# --------------------------------------------------------------------------
# Data Read Tools -- Tasks & Accounts (MCP-05, MCP-06)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_fetch_tasks(status: str = "") -> str:
    """Fetch tasks that need attention -- pending triage, confirmed for execution, or deferred. Returns task title, status, priority, due date, and suggested skill if any. Use this during morning brief to surface action items, or anytime the user asks about their tasks or commitments."""
    try:
        client = FlywheelClient()
        if status:
            result = client.fetch_tasks(status=status, limit=50)
        else:
            result = client.fetch_tasks(limit=50)

        items = result.get("items", [])
        if not status:
            items = [t for t in items if t.get("status") not in ("done", "dismissed")]

        if not items:
            return "No actionable tasks found."

        priority_order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda t: (
            (0, t.get("due_date", "")) if t.get("due_date") else (1, ""),
            priority_order.get(t.get("priority", "medium"), 1),
        ))

        lines = [f"{len(items)} tasks need attention:\n"]
        for t in items:
            title = t.get("title", "Untitled")
            t_status = t.get("status", "?")
            priority = t.get("priority", "medium")
            task_id = t.get("id", "?")
            due_date = t.get("due_date") or "none"
            direction = t.get("commitment_direction") or "?"
            skill = t.get("suggested_skill") or "none"
            desc = t.get("description", "")
            snippet = desc[:100] if desc else ""

            entry = (
                f"**{title}** [{t_status}] {priority}\n"
                f"ID: {task_id}\n"
                f"Due: {due_date}\n"
                f"Direction: {direction}\n"
                f"Skill: {skill}"
            )
            if snippet:
                entry += f"\n{snippet}"
            lines.append(entry)

        return "\n\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching tasks: {exc}"


def _format_pipeline_detail(data: dict) -> str:
    """Format pipeline entry detail response for Claude Code consumption."""
    name = data.get("name", "Unknown")
    aid = data.get("id", "?")
    domain = data.get("domain", "none")
    stage = data.get("stage", "?")
    fit_score = data.get("fit_score")
    fit_tier = data.get("fit_tier", "?")

    lines = [
        f"# {name}",
        f"ID: {aid}",
        f"Domain: {domain}",
        f"Stage: {stage}",
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


# --------------------------------------------------------------------------
# Action Tools (MCP-07)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_sync_meetings() -> str:
    """Sync meetings from Granola calendar integration. Call this at the start of the morning brief or when the user asks to refresh their meeting data. Returns count of new and updated meetings. After syncing, use flywheel_fetch_meetings to get unprocessed meetings."""
    try:
        client = FlywheelClient()
        result = client.sync_meetings()
        new_count = result.get("new", 0)
        updated_count = result.get("updated", 0)
        if isinstance(new_count, int) and isinstance(updated_count, int):
            return f"Meeting sync complete. {new_count} new, {updated_count} updated meetings."
        # Fallback if response shape differs
        return f"Meeting sync triggered. Response: {result}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error syncing meetings: {exc}"


# --------------------------------------------------------------------------
# Write Tools (MCP-08, MCP-09, MCP-10)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_save_document(
    title: str,
    content: str,
    skill_name: str = "",
    account_id: str = "",
) -> str:
    """Save a skill's output to the Flywheel library. Send the raw content (markdown or structured text) -- Flywheel renders it with the design system. The document appears in the library UI immediately. Use this after every skill execution to persist the deliverable. Optionally link to a skill name and account."""
    try:
        client = FlywheelClient()
        metadata: dict = {}
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
        return f"Document '{title}' saved (id: {run_id}). View: {url}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error saving document: {exc}"


@mcp.tool()
def flywheel_save_meeting_summary(
    meeting_id: str,
    summary: str,
) -> str:
    """Save a processed meeting summary back to Flywheel. Call this after you've analyzed a meeting transcript and extracted insights. Updates the meeting record so the summary appears on the meeting detail page. Write extracted business intelligence to the context store separately via flywheel_write_context."""
    try:
        client = FlywheelClient()
        result = client.save_meeting_summary(meeting_id, summary)
        title = result.get("title", "meeting")
        return f"Summary saved for '{title}'. Meeting status updated to completed."
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error saving meeting summary: {exc}"


@mcp.tool()
def flywheel_update_task(
    task_id: str,
    status: str = "",
    priority: str = "",
) -> str:
    """Update a task's status, priority, or suggested skill. Use this to confirm tasks, mark them done, assign a skill for execution, or change priority. Call this after executing a task's skill to mark it complete, or during triage to confirm or dismiss detected tasks."""
    try:
        client = FlywheelClient()
        fields: dict = {}
        if status:
            fields["status"] = status
        if priority:
            fields["priority"] = priority
        if not fields:
            return "No fields to update. Provide status and/or priority."
        result = client.update_task(task_id, **fields)
        title = result.get("title", "Unknown task")
        new_status = result.get("status", "?")
        return f"Task '{title}' updated. Status: {new_status}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error updating task: {exc}"


# --------------------------------------------------------------------------
# Pipeline Tools (unified CRM)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_upsert_pipeline_entry(
    name: str,
    domain: str = "",
    entity_type: str = "company",
    source: str = "mcp",
    stage: str = "identified",
    relationship_type: str = "prospect",
    fit_score: float = 0,
    fit_tier: str = "",
    intel: str = "",
) -> str:
    """Create or update an entry in the Flywheel pipeline (unified CRM).

    Finds existing entry by company name (dedup). Use after scraping, scoring,
    or researching a company or person.

    Args:
        name: Company or person name (required)
        domain: Company website domain
        entity_type: "company" or "person"
        source: What created this entry (e.g. "gtm-web-scraper", "manual")
        stage: Pipeline stage: identified, contacted, engaged, qualified, committed, closed
        relationship_type: prospect, customer, investor, advisor, partner
        fit_score: Fit score 0-100
        fit_tier: "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit", "No Fit"
        intel: JSON string with additional intel (industry, size, description, etc.)
    """
    try:
        import json as _json

        client = FlywheelClient()
        fields: dict = {
            "name": name,
            "entity_type": entity_type,
            "stage": stage,
            "relationship_type": relationship_type,
        }
        if domain:
            fields["domain"] = domain
        if source:
            fields["source"] = source
        if fit_score:
            fields["fit_score"] = fit_score
        if fit_tier:
            fields["fit_tier"] = fit_tier
        if intel:
            try:
                fields["intel"] = _json.loads(intel)
            except _json.JSONDecodeError:
                fields["intel"] = {"raw": intel}

        result = client.create_pipeline_entry(**fields)
        entry_stage = result.get("stage", stage)
        tier = result.get("fit_tier", "unscored")
        return (
            f"Pipeline entry '{result.get('name', name)}' saved (stage: {entry_stage}, "
            f"tier: {tier})"
        )
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error saving pipeline entry: {exc}"


@mcp.tool()
def flywheel_list_pipeline(
    stage: str = "",
    fit_tier: str = "",
    relationship_type: str = "",
    source: str = "",
    search: str = "",
    limit: int = 20,
) -> str:
    """List entries from the Flywheel pipeline with filters.

    Use to find pipeline entries that need processing, or to browse
    the CRM by stage, tier, or relationship type.

    Args:
        stage: Filter by stage: identified, contacted, engaged, qualified, committed, closed
        fit_tier: Filter by tier: "Strong Fit", "Good Fit", etc.
        relationship_type: Filter: prospect, customer, investor, advisor, partner
        source: Filter by source
        search: Free-text search across name, domain, summary
        limit: Max results (default 20)
    """
    try:
        client = FlywheelClient()
        params: dict = {"limit": limit}
        if stage:
            params["stage"] = stage
        if fit_tier:
            params["fit_tier"] = fit_tier
        if relationship_type:
            params["relationship_type"] = relationship_type
        if source:
            params["source"] = source
        if search:
            params["search"] = search

        result = client.list_pipeline(**params)
        items = result.get("items", [])
        total = result.get("total", 0)

        if not items:
            return f"No pipeline entries found (total: {total})"

        lines = [f"**{total} entries** in pipeline (showing {len(items)}):\n"]
        for i, item in enumerate(items, 1):
            entry_name = item.get("name", "?")
            entry_domain = item.get("domain") or ""
            entry_stage = item.get("stage", "?")
            tier = item.get("fit_tier") or "unscored"
            contacts = item.get("contact_count", 0)
            lines.append(
                f"{i}. **{entry_name}** ({entry_domain}) -- {entry_stage} | {tier} | {contacts} contacts"
            )
        return "\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error listing pipeline: {exc}"


@mcp.tool()
def flywheel_fetch_pipeline_entry(identifier: str) -> str:
    """Fetch detailed information about a pipeline entry (prospect, customer, investor, etc.).

    Search by entry ID (UUID) or name (fuzzy match). Returns entry details,
    contacts, recent activities, and timeline. Use before meeting prep,
    outreach drafting, or any entry-specific work.

    Args:
        identifier: Pipeline entry UUID or name (fuzzy search)
    """
    try:
        from uuid import UUID as _UUID

        client = FlywheelClient()

        # Try UUID first
        try:
            _UUID(identifier)
            is_uuid = True
        except ValueError:
            is_uuid = False

        if is_uuid:
            result = client.fetch_pipeline_entry(identifier)
            return _format_pipeline_detail(result)

        # Name search (fuzzy)
        result = client.search_pipeline(identifier)
        items = result.get("items", [])

        if not items:
            return f"No pipeline entry found matching '{identifier}'."

        if len(items) == 1:
            detail = client.fetch_pipeline_entry(items[0]["id"])
            return _format_pipeline_detail(detail)

        # Multiple matches -- disambiguation
        lines = [f"Found {len(items)} entries matching '{identifier}':\n"]
        for a in items:
            lines.append(
                f"  - **{a.get('name', '?')}** "
                f"(ID: {a.get('id', '?')}) [{a.get('stage', '?')}]"
            )
        lines.append("\nSpecify the entry ID for full details.")
        return "\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error fetching pipeline entry: {exc}"


@mcp.tool()
def flywheel_add_pipeline_contact(
    entry_name: str,
    contact_name: str,
    email: str = "",
    title: str = "",
    linkedin_url: str = "",
    role: str = "",
) -> str:
    """Add a contact person to a pipeline entry. Finds entry by name.

    Deduplicates by email within the entry. Use after researching a company
    to add decision-makers, champions, or other stakeholders.

    Args:
        entry_name: Company/person name to add contact to
        contact_name: Person's full name
        email: Email address
        title: Job title
        linkedin_url: LinkedIn profile URL
        role: Role in deal: decision-maker, champion, influencer, blocker
    """
    try:
        client = FlywheelClient()
        # Find entry by name search
        results = client.search_pipeline(entry_name, limit=1)
        items = results.get("items", [])
        if not items:
            return f"No pipeline entry found matching '{entry_name}'. Create it first with flywheel_upsert_pipeline_entry."
        entry_id = items[0]["id"]

        fields: dict = {"name": contact_name}
        if email:
            fields["email"] = email
        if title:
            fields["title"] = title
        if linkedin_url:
            fields["linkedin_url"] = linkedin_url
        if role:
            fields["role"] = role

        result = client.add_pipeline_contact(entry_id, **fields)
        return f"Contact '{result.get('name')}' added to '{entry_name}' ({result.get('email', 'no email')})"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error adding contact: {exc}"


@mcp.tool()
def flywheel_draft_pipeline_message(
    entry_name: str,
    contact_email: str = "",
    contact_linkedin: str = "",
    channel: str = "email",
    step_number: int = 1,
    subject: str = "",
    body: str = "",
    cadence_days: int = 3,
) -> str:
    """Draft an outreach message for a pipeline entry contact.

    Creates an activity with type='outreach' containing message details.
    Step 1 is typically a connection request or cold email. Step 2+ are follow-ups.

    Args:
        entry_name: Company/person name
        contact_email: Contact's email to identify them
        contact_linkedin: Contact's LinkedIn URL (fallback if no email)
        channel: "email" or "linkedin"
        step_number: Sequence step (1=initial outreach, 2=follow-up 1, etc.)
        subject: Email subject line (for email channel)
        body: Message content
        cadence_days: Days to wait before sending after previous step (default 3)
    """
    try:
        client = FlywheelClient()
        results = client.search_pipeline(entry_name, limit=1)
        items = results.get("items", [])
        if not items:
            return f"No pipeline entry found matching '{entry_name}'."

        entry_id = items[0]["id"]
        detail = client.fetch_pipeline_entry(entry_id)

        # Find contact by email or LinkedIn URL
        contacts = detail.get("contacts", [])
        contact = None
        identifier = ""
        if contact_email:
            contact = next((c for c in contacts if c.get("email") and c["email"].lower() == contact_email.lower()), None)
            identifier = contact_email
        if not contact and contact_linkedin:
            contact = next((c for c in contacts if c.get("linkedin_url") and contact_linkedin in c["linkedin_url"]), None)
            identifier = contact_linkedin
        if not contact:
            return f"No contact matching '{identifier or 'empty'}' found on '{entry_name}'."

        metadata = {
            "step_number": step_number,
            "channel": channel,
            "subject": subject or None,
            "body": body or None,
            "cadence_days": cadence_days,
            "status": "drafted",
            "contact_id": contact.get("id"),
            "contact_email": contact.get("email"),
        }

        result = client.create_pipeline_activity(
            entry_id,
            type="outreach",
            summary=f"Draft: step {step_number} via {channel} to {contact.get('name', identifier)}",
            metadata=metadata,
        )
        cadence_note = f" (follow-up in {cadence_days}d)" if cadence_days > 0 and step_number > 1 else ""
        return (
            f"Draft created: step {step_number} via {channel} "
            f"for {contact.get('name', identifier)} at {entry_name}{cadence_note}"
        )
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error drafting message: {exc}"


@mcp.tool()
def flywheel_send_pipeline_message(
    entry_name: str,
    contact_email: str = "",
    contact_linkedin: str = "",
    channel: str = "email",
    step_number: int = 1,
) -> str:
    """Mark a drafted outreach message as sent.

    Finds the drafted activity for the given step/channel and updates its
    metadata status to 'sent' with a sent_at timestamp.

    Args:
        entry_name: Company/person name
        contact_email: Contact's email
        contact_linkedin: Contact's LinkedIn URL (fallback if no email)
        channel: "email" or "linkedin"
        step_number: Which step in the sequence was sent
    """
    try:
        import datetime

        client = FlywheelClient()
        results = client.search_pipeline(entry_name, limit=1)
        items = results.get("items", [])
        if not items:
            return f"No pipeline entry found matching '{entry_name}'."

        entry_id = items[0]["id"]
        detail = client.fetch_pipeline_entry(entry_id)

        # Find contact by email or LinkedIn URL
        contacts = detail.get("contacts", [])
        contact = None
        identifier = ""
        if contact_email:
            contact = next((c for c in contacts if c.get("email") and c["email"].lower() == contact_email.lower()), None)
            identifier = contact_email
        if not contact and contact_linkedin:
            contact = next((c for c in contacts if c.get("linkedin_url") and contact_linkedin in c["linkedin_url"]), None)
            identifier = contact_linkedin
        if not contact:
            return f"No contact matching '{identifier or 'empty'}' found on '{entry_name}'."

        # Find the drafted activity for this step/channel/contact
        activities = detail.get("activities", detail.get("recent_timeline", []))
        draft = None
        for act in activities:
            meta = act.get("metadata", {})
            if (
                act.get("type") == "outreach"
                and meta.get("step_number") == step_number
                and meta.get("channel") == channel
                and meta.get("status") == "drafted"
                and meta.get("contact_id") == contact.get("id")
            ):
                draft = act
                break

        if not draft:
            return f"No drafted message found for step {step_number} via {channel}. Draft it first."

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_meta = {**(draft.get("metadata", {})), "status": "sent", "sent_at": now}
        client.update_pipeline_activity(
            entry_id,
            draft["id"],
            metadata=updated_meta,
        )
        return f"Message marked as sent: step {step_number} via {channel} to {contact.get('name', identifier)}"
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error sending message: {exc}"


# --------------------------------------------------------------------------
# Contact Outreach Tools (batch operations)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_list_pipeline_contacts(
    company: str = "",
    status: str = "",
    channel: str = "",
    variant: str = "",
    limit: int = 50,
) -> str:
    """List contacts in the outreach pipeline with their current status and AI-computed next step.

    Returns a table of contacts showing: name, company, email, channel, variant,
    step number, outreach status, and recommended next action.

    Use for batch outreach operations like:
    - "Show all contacts at step 1 that are ready to send"
    - "List all contacts with status 'sent' for follow-up"
    - "Find all email contacts for variant A"

    After listing, use flywheel_create_outreach_step to generate the next step
    for selected contacts.

    Args:
        company: Filter by company name (fuzzy match)
        status: Filter by outreach status: drafted, approved, sent, replied, bounced
        channel: Filter by channel: email, linkedin
        variant: Filter by variant/campaign tag
        limit: Max contacts to return (default 50, max 200)
    """
    try:
        client = FlywheelClient()
        params: dict = {"limit": limit}
        if company:
            params["company"] = company
        if status:
            params["status"] = status
        if channel:
            params["channel"] = channel
        if variant:
            params["variant"] = variant

        result = client.list_pipeline_contacts(**params)
        items = result.get("items", [])
        total = result.get("total", 0)

        if not items:
            return f"No contacts found (total in pipeline: {total})"

        lines = [f"**{total} contacts** (showing {len(items)}):\n"]
        for i, c in enumerate(items, 1):
            name = c.get("name", "?")
            company_name = c.get("company_name", "?")
            email = c.get("email") or "no email"
            next_step = c.get("next_step", "?")
            act = c.get("latest_activity")
            if act:
                act_status = act.get("status", "?")
                act_channel = act.get("channel", "?")
                act_variant = act.get("variant") or "-"
                act_step = act.get("step_number") or "?"
            else:
                act_status = "none"
                act_channel = "-"
                act_variant = "-"
                act_step = "-"

            contact_id = c.get("id", "?")
            entry_id = c.get("pipeline_entry_id", "?")

            lines.append(
                f"{i}. **{name}** ({company_name}) -- {email}\n"
                f"   Status: {act_status} | Channel: {act_channel} | "
                f"Variant: {act_variant} | Step: {act_step}\n"
                f"   Next: {next_step}\n"
                f"   IDs: contact={contact_id}, entry={entry_id}"
            )
        return "\n".join(lines)
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error listing contacts: {exc}"


@mcp.tool()
def flywheel_create_outreach_step(
    pipeline_entry_id: str,
    contact_id: str,
    step_number: int,
    channel: str = "email",
    subject: str = "",
    body: str = "",
    variant: str = "",
    status: str = "drafted",
) -> str:
    """Create a new outreach step (activity) for a pipeline contact.

    Creates an activity with type='outreach' containing the message details.
    Use after flywheel_list_pipeline_contacts to batch-create outreach steps.

    The step appears immediately in the contact's outreach sequence in the UI.
    Status 'drafted' means it needs review/approval before sending.

    Example batch workflow:
    1. flywheel_list_pipeline_contacts(status="sent") -- find contacts needing follow-up
    2. For each contact: flywheel_create_outreach_step(entry_id, contact_id, step_number=2, ...)

    Args:
        pipeline_entry_id: Pipeline entry UUID (from flywheel_list_pipeline_contacts)
        contact_id: Contact UUID (from flywheel_list_pipeline_contacts)
        step_number: Step in the sequence (1=initial, 2=first follow-up, etc.)
        channel: "email" or "linkedin"
        subject: Email subject line (for email channel)
        body: Message body content
        variant: Campaign variant tag (e.g. "A", "B")
        status: Initial status (default: "drafted")
    """
    try:
        client = FlywheelClient()
        metadata = {
            "step_number": step_number,
            "variant": variant or None,
            "cadence_days": 3,
            "body": body or None,
        }

        result = client.create_pipeline_activity(
            pipeline_entry_id,
            type="outreach",
            channel=channel,
            status=status,
            subject=subject or None,
            body_preview=(body[:200] if body else None),
            contact_id=contact_id,
            metadata=metadata,
        )

        return (
            f"Outreach step {step_number} created via {channel} "
            f"(status: {status}, id: {result.get('id', '?')})"
        )
    except FlywheelAPIError as exc:
        return str(exc)
    except Exception as exc:
        return f"Error creating outreach step: {exc}"


# --------------------------------------------------------------------------
# Deprecated Tools (backward compat)
# --------------------------------------------------------------------------


@mcp.tool()
def flywheel_upsert_lead(
    name: str,
    domain: str = "",
    source: str = "mcp",
    fit_score: float = 0,
    fit_tier: str = "",
    fit_rationale: str = "",
    intel: str = "",
    purpose: str = "sales",
    campaign: str = "",
) -> str:
    """[DEPRECATED -- use flywheel_upsert_pipeline_entry] Create or update a pipeline entry."""
    relationship_type = {"sales": "prospect", "fundraising": "investor", "advisors": "advisor"}.get(
        purpose.split(",")[0].strip(), "prospect"
    )
    return flywheel_upsert_pipeline_entry(
        name=name, domain=domain, source=source, fit_score=fit_score,
        fit_tier=fit_tier, intel=intel, relationship_type=relationship_type,
    )


@mcp.tool()
def flywheel_list_leads(
    pipeline_stage: str = "",
    fit_tier: str = "",
    purpose: str = "",
    limit: int = 20,
) -> str:
    """[DEPRECATED -- use flywheel_list_pipeline] List pipeline entries."""
    return flywheel_list_pipeline(stage=pipeline_stage, fit_tier=fit_tier, limit=limit)


@mcp.tool()
def flywheel_graduate_lead(lead_name: str) -> str:
    """[DEPRECATED] Graduation is no longer needed in the unified pipeline."""
    return (
        f"Graduation is no longer needed -- '{lead_name}' is already in the unified pipeline. "
        f"All entries are full pipeline entries from creation."
    )


@mcp.tool()
def flywheel_add_lead_contact(
    lead_name: str,
    contact_name: str,
    email: str = "",
    title: str = "",
    linkedin_url: str = "",
    role: str = "",
) -> str:
    """[DEPRECATED -- use flywheel_add_pipeline_contact] Add a contact to a pipeline entry."""
    return flywheel_add_pipeline_contact(
        entry_name=lead_name, contact_name=contact_name, email=email,
        title=title, linkedin_url=linkedin_url, role=role,
    )


@mcp.tool()
def flywheel_fetch_account(identifier: str) -> str:
    """[DEPRECATED -- use flywheel_fetch_pipeline_entry] Fetch pipeline entry details."""
    return flywheel_fetch_pipeline_entry(identifier=identifier)


@mcp.tool()
def flywheel_draft_lead_message(
    lead_name: str,
    contact_email: str = "",
    contact_linkedin: str = "",
    channel: str = "email",
    step_number: int = 1,
    subject: str = "",
    body: str = "",
    cadence_days: int = 3,
) -> str:
    """[DEPRECATED -- use flywheel_draft_pipeline_message] Draft an outreach message."""
    return flywheel_draft_pipeline_message(
        entry_name=lead_name, contact_email=contact_email,
        contact_linkedin=contact_linkedin, channel=channel,
        step_number=step_number, subject=subject, body=body,
        cadence_days=cadence_days,
    )


@mcp.tool()
def flywheel_send_lead_message(
    lead_name: str,
    contact_email: str = "",
    contact_linkedin: str = "",
    channel: str = "email",
    step_number: int = 1,
) -> str:
    """[DEPRECATED -- use flywheel_send_pipeline_message] Mark a drafted message as sent."""
    return flywheel_send_pipeline_message(
        entry_name=lead_name, contact_email=contact_email,
        contact_linkedin=contact_linkedin, channel=channel,
        step_number=step_number,
    )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main():
    """Start the Flywheel MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
