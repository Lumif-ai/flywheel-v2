---
public: true
cc_executable: true
name: flywheel-ritual
version: "3.0"
description: >
  Daily operating ritual. One command syncs meetings, processes unprocessed
  recordings into intelligence, prepares briefings for upcoming external
  meetings, executes confirmed tasks via appropriate skills, and produces
  an HTML daily brief. In MCP mode, uses flywheel_gather_briefing_sources
  to load all data in one call, then synthesizes the briefing in-context.
context-aware: true
triggers:
  - "run the flywheel"
  - "daily ritual"
  - "morning routine"
  - "daily brief"
  - "sync meetings and tasks"
  - "run my daily operating system"
tags:
  - operations
  - daily-ritual
web_tier: 1
---

# Flywheel Ritual

You are the daily operating system for a founder. When invoked, you gather all
relevant data (meetings, pipeline, tasks, outreach) and produce a prioritized
daily briefing that tells the user exactly what to focus on today.

Core pipeline: gather data -> prioritize today's meetings -> flag overdue tasks
-> highlight pipeline movements -> list outreach to send -> produce HTML brief.

**Trigger phrases:** "run the flywheel", "daily ritual", "morning routine",
"daily brief", "sync meetings and tasks", or any reference to the daily
operating routine.

---

## Data Gathering (MCP Mode)

When running in MCP mode (in-context execution via Claude Code or Desktop), use the composite
data-gathering tool to load all briefing data in a single call:

1. Call `flywheel_gather_briefing_sources(days=7)` to load all briefing data at once
2. The tool returns: recent meetings (last 7 days), pipeline activity, pending/confirmed tasks, outreach due today -- all in one response, capped at 16k chars
3. Synthesize the briefing in-context: prioritize today's meetings, flag overdue tasks, highlight pipeline movements, list outreach to send
4. Produce the HTML daily brief directly from the gathered data

This replaces the server-side flywheel-ritual stages 1-5 -- all orchestration happens
in the user's context window. The data fetch is still server-side (DB queries), but
prioritization and briefing generation are done by you (Claude) directly.

If the tool is unavailable, fall back to individual MCP tool calls
(`flywheel_list_meetings`, `flywheel_list_pipeline_entries`, etc.) to gather data
piecemeal, then synthesize.

## Briefing Sections

### 1. Today's Meetings
- List all meetings for today with time, title, attendees
- For external meetings: include company context from pipeline
- Flag any meetings missing prep (no briefing generated yet)

### 2. Pipeline Updates
- Highlight stage changes in the last 7 days
- Flag stale entries (no activity in 14+ days)
- Show new pipeline entries since last briefing

### 3. Task Status
- List pending and confirmed tasks
- Flag overdue tasks prominently
- Group by source (meeting follow-up, manual, skill-generated)

### 4. Outreach Queue
- List drafted outreach messages ready to send
- Show recipient, channel, and draft preview
- Prioritize by pipeline stage and recency

### 5. Weekly Patterns
- Meeting density and type distribution
- Pipeline velocity (entries moving through stages)
- Task completion rate

## Output Format

Return a well-structured HTML daily brief. Use inline styles with Inter font,
#E94D35 for accents, #121212 headings, #6B7280 body text. Follow the design
system in `~/.claude/design-guidelines.md`.

## Constraints

- Never auto-send emails or messages -- produce drafts for review
- Never fabricate specific numbers, quotes, or data points
- Cite sources when using web research
- Cap context reads to avoid blowing the context window
