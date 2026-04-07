# Requirements: Flywheel V2

**Defined:** 2026-04-07
**Core Value:** Conversations automatically become tracked commitments and executed deliverables — the founder's daily operating system

## v10.0 Requirements

Requirements for Contact Outreach Pipeline milestone. Each maps to roadmap phases.

### Contact Grid

- [ ] **GRID-01**: Contact-first grid shows one row per contact with: name, company, title, email, channel, variant, step number, outreach status, next step, subject
- [ ] **GRID-02**: "Next Step" column shows AI-computed recommendation derived from activity status + elapsed time (Ready to send / Follow up in Nd / Replied - engage / Bounced - fix email)
- [ ] **GRID-03**: Contacts | Companies toggle at the top of the pipeline page, with Contacts as default
- [ ] **GRID-04**: Contact grid supports filtering by: company, outreach status (drafted/sent/replied/bounced/approved), channel (email/linkedin), variant, step number
- [ ] **GRID-05**: Contact grid supports sorting by: name, company, status, last action date, next step priority

### Contact Detail Panel

- [ ] **PANEL-01**: Panel header shows contact name, title, company, email (editable), LinkedIn URL, phone — with inline field editing
- [ ] **PANEL-02**: Outreach sequence section shows all steps as a vertical timeline (Step 1 ... Step N) with channel icon, subject, status pill per step
- [ ] **PANEL-03**: Each sequence step has full message body in an editable textarea — changes save via API
- [ ] **PANEL-04**: Each step shows email body and LinkedIn message (if applicable) in separate sections
- [ ] **PANEL-05**: Action buttons per step: "Approve" (marks approved for Claude Code to send via Playwright), "Skip", "Mark Replied" — updating activity status
- [ ] **PANEL-06**: "Generate Next Step" button creates a placeholder activity for Claude Code to populate via MCP

### Backend API

- [ ] **API-01**: `GET /pipeline/contacts/` returns flattened contact list with parent company name, latest outreach activity per contact, and computed next_step field
- [ ] **API-02**: `PATCH /pipeline/{entry_id}/contacts/{contact_id}` supports editing contact fields (name, email, title, linkedin_url, phone)
- [ ] **API-03**: `PATCH /pipeline/{entry_id}/activities/{activity_id}` supports editing activity body_preview (message editing) and status changes (drafted -> approved -> sent -> replied)
- [ ] **API-04**: Computed `next_step` field in API response: derives from latest activity status + days since occurred_at

### MCP Tools

- [ ] **MCP-01**: `flywheel_list_pipeline_contacts` tool returns flattened contact list with outreach status, filterable by company/status/channel/variant
- [ ] **MCP-02**: `flywheel_create_outreach_step` tool creates a new activity with step_number = N for a given contact, with channel, subject, body

## Future Requirements (v11+)

### Automation
- **AUTO-01**: Scheduled sequences — auto-send step N after X days if no reply
- **AUTO-02**: Reply detection — poll Gmail for replies matching outreach subjects, auto-update status
- **AUTO-03**: Bounce handling — detect bounced emails via delivery webhook, update status
- **AUTO-04**: Auto-follow-up rules — configurable cadence per variant/lane

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sequence builder UI | AI generates sequences via Claude Code — no config UI needed |
| In-app email/LinkedIn send buttons | Claude Code sends via Playwright — grid is visibility, not execution |
| Auto-send without approval | Founder reviews and approves — AI-first but human-in-the-loop |
| Real-time send status updates | v10 tracks after-the-fact; live WebSocket updates deferred |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GRID-01 | Phase 92 | Pending |
| GRID-02 | Phase 92 | Pending |
| GRID-03 | Phase 92 | Pending |
| GRID-04 | Phase 92 | Pending |
| GRID-05 | Phase 92 | Pending |
| PANEL-01 | Phase 93 | Pending |
| PANEL-02 | Phase 93 | Pending |
| PANEL-03 | Phase 93 | Pending |
| PANEL-04 | Phase 93 | Pending |
| PANEL-05 | Phase 93 | Pending |
| PANEL-06 | Phase 93 | Pending |
| API-01 | Phase 91 | ✓ Done |
| API-02 | Phase 91 | ✓ Done |
| API-03 | Phase 91 | ✓ Done |
| API-04 | Phase 91 | ✓ Done |
| MCP-01 | Phase 94 | Pending |
| MCP-02 | Phase 94 | Pending |

**Coverage:**
- v10 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after roadmap creation*
