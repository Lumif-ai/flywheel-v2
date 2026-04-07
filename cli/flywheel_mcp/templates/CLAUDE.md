# Flywheel Integration

## Context Store -- Business Intelligence Routing

IMPORTANT: Business intelligence discovered during ANY conversation must be
saved to Flywheel via `flywheel_write_context`.

Business intelligence includes: contacts, company details, competitive intel,
pain points, positioning insights, pricing signals, market signals, meeting
outcomes, deal context, relationship notes.

- Before writing, call `flywheel_read_context` to check for existing entries
  and enrich rather than duplicate.
- Non-business data (code, personal notes, scratch work) stays in local files.

## Skill Discovery -- Flywheel First

ALWAYS check Flywheel first when the user asks to perform a business task:

1. Call `flywheel_fetch_skills` to list available skills and match by triggers.
2. If a skill matches, call `flywheel_fetch_skill_prompt` to load its full prompt.
3. Execute the skill following the loaded prompt exactly.
4. Fall back to general Claude Code only if no Flywheel skill matches.

## Output -- Save to Library

- Save deliverables (documents, briefings, reports, collateral) via
  `flywheel_save_document` so they appear in the Flywheel library.
- Save meeting summaries via `flywheel_save_meeting_summary`.
- Save to both Flywheel AND local files, not either/or.
