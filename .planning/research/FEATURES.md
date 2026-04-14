# Feature Landscape — Broker Data Model: Clients, Contacts & Intelligence

**Domain:** Insurance broker client/contact management, solicitation approval workflows, CRM-style intelligence bridging
**Researched:** 2026-04-14
**Context:** Subsequent milestone adding client/contact entities, structural extractions, context store intelligence, and solicitation workflow to existing broker module (6 tables, 29 endpoints, 37 components already built)

## Table Stakes

Features that any commercial insurance broker tool must have at this maturity level. Missing = broker cannot manage real client relationships through the system.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| Client entity with dedup | Every AMS (Applied Epic, HawkSoft, AMS360) groups projects by client. Without a client entity, the broker cannot answer "how many projects does Alaya have?" or "who is my contact at Tracsa?" The current system has projects floating in isolation — no client grouping. | Med | New `broker_clients` table, normalized_name logic, client CRUD endpoints, client list page | Normalized name dedup with legal suffix stripping (S.A. de C.V., Inc., LLC) is essential for Mexico market. RFC/EIN tax_id is mandatory on Mexican insurance policies per SAT requirements. |
| Client contacts with roles | Brokers communicate with different people at a client company for different purposes: the CFO approves coverage decisions, the project manager handles technical questions, the billing contact processes invoices. One email per client is inadequate. | Low | New `broker_client_contacts` table, contact CRUD endpoints, role enum (primary, billing, technical, legal, executive) | Role constraints prevent misrouted communications. The `is_primary` flag ensures automated emails go to the right person. Unique constraint on (client_id, email) prevents duplicate contacts. |
| Carrier contacts with roles | Currently carriers have a single `email_address` string. In practice, a broker sends solicitations to the submissions desk, negotiates with the underwriter, and manages the relationship through an account manager. Different people, different purposes. | Low | New `carrier_contacts` table, migrate existing `email_address` to contact row, role enum (submissions, account_manager, underwriter, claims, billing) | Critical for solicitation routing — sending a solicitation to the claims email is a waste of everyone's time. Dropping `carrier_configs.email_address` (no production data) eliminates dual source of truth. |
| Client-project link | Projects must be attributable to a client for portfolio views, renewal tracking, and cross-project analysis. "Show me all Alaya projects" is a basic query that cannot work without this FK. | Low | `client_id` FK on `broker_projects` (nullable), join in project list/detail endpoints | Nullable by design: don't block project creation. Application-layer gate: `client_id` required before status transitions past `analyzing`. This matches real workflow — broker creates project from contract email, links client later. |
| Solicitation approval workflow (separate approve from send) | The current system combines approve and send into one action. Insurance communications have professional and potentially legal weight. A broker must be able to approve a draft (confirming content), then decide WHEN to send (coordinating across carriers for timing). | Med | New `solicitation_drafts` table extracted from CarrierQuote columns, approval status tracking, `approved_by_user_id` + `approved_at` audit trail | Regulatory requirement: insurance solicitations are business communications that may need compliance review. Separation of approve/send also enables batch operations — approve 5 drafts, then send all at once. |
| Recommendation as proper entity | Currently recommendation_subject, recommendation_body, recommendation_status live as columns on BrokerProject. This means: no version history, no audit trail on who approved what, no ability to revise and resend. In a regulated domain, this is unacceptable. | Med | New `broker_recommendations` table, 1:N from project, partial unique index (one approved at a time), extract existing columns | If a client disputes a recommendation, the broker needs version history showing what was sent, when, by whom, and what changed between versions. This is E&O (errors and omissions) liability protection. |
| Project email thread tracking | Currently `email_thread_ids` is a TEXT[] array column on BrokerProject. Arrays cannot be queried efficiently, cannot carry metadata (direction, timestamp), and cannot be joined. | Low | New `broker_project_emails` table replacing TEXT[] column, thread_id + direction + received_at per row | Proper entity enables "show all emails for this project" queries, inbound/outbound filtering, and timeline reconstruction. Foundation for future email intelligence features. |
| Audit columns on all tables | Missing `created_by_user_id` and `updated_by_user_id` on existing tables (broker_projects, carrier_quotes, project_coverages, carrier_configs, submission_documents). In a regulated insurance domain, "who did what when" is not optional. | Low | ALTER TABLE additions across 5 existing tables, populate from session context on all write operations | Applied Epic, AMS360, and every enterprise AMS tracks user attribution on every record. Without this, no compliance audit trail. |
| Status lifecycle: binding phase | Current status enum jumps from `recommended` to `delivered` to `bound`. Insurance placement requires an active binding phase where the broker confirms coverage, negotiates final terms, and executes the binder. This is a distinct workflow state. | Low | Add `binding` status to CHECK constraint, update frontend status displays and gate logic | BindHQ, Applied Epic, and ExpertInsured all model binding as an explicit workflow step. Without it, the system cannot distinguish "we sent the recommendation" from "we are actively placing coverage" from "coverage is bound." |

## Differentiators

Features that separate this from standard AMS/CRM tools and create the switching cost moat.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| Context store intelligence bridge | Every broker entity (client, carrier, project) links to the context store via `context_entity_id`. Meeting notes, email signals, and relationship context automatically surface where they matter. No major AMS does this — they store policy data but not relationship intelligence. | High | Context store entity creation (eager), `context_entity_id` on broker_clients, carrier_configs, broker_projects, bidirectional data flow | This is the moat mechanism. A broker who uses the system for 18 months has accumulated intelligence that makes every AI-drafted solicitation, recommendation, and carrier match more accurate. Competitors cannot replicate accumulated context. McKinsey confirms: "MGAs that combine strong relationships with data ownership and advanced AI use will differentiate themselves most sharply." |
| AI-powered solicitation personalization from context | When drafting a solicitation for a carrier, the system reads the carrier's context entity to pull: past response times, preferred submission formats, underwriter preferences from past meetings, and relationship notes. The draft is customized to the specific carrier relationship, not generic. | Med | Context store intelligence bridge (above), solicitation_drafter engine enhancement, carrier context entity populated with signals | No broker tool personalizes solicitations based on accumulated carrier relationship intelligence. Applied Epic sends templated emails. This sends relationship-aware emails. "Based on your previous feedback, we've included the seismic risk assessment upfront." |
| Client intelligence surfacing | Client detail page shows not just contact info and projects, but AI-surfaced insights: "In last meeting, client mentioned expanding to Monterrey — consider regional carrier options" or "Client prefers lowest deductible over lowest premium based on 3 conversations." | Med | Context store intelligence bridge, client detail page with intelligence panel, context entity query on page load | Standard AMS shows policy data. This shows relationship intelligence. The broker walks into a client meeting already knowing what was discussed last time, what the client cares about, and what opportunities exist. |
| Carrier response pattern tracking | Over time, the system learns which carriers respond fastest, which ones offer competitive rates for construction projects, and which underwriters are responsive. This intelligence feeds carrier matching and selection. | Med | Context store signals accumulated from solicitation/quote lifecycle, carrier matching engine enhancement | "Carrier X responded in 2 days on the last 3 solicitations. Carrier Y averages 14 days." This data-driven carrier selection replaces the broker's mental Rolodex. GenasysTech confirms: "Speed-to-quote becomes a competitive moat" — the system helps brokers route to fast-responding carriers. |
| Normalized name dedup with legal suffix stripping | Mexican legal entities have structured suffixes: S.A. de C.V., S.A.S. de C.V., S.A.P.I., S. de R.L. de C.V. Simple lowercase comparison fails. Aggressive normalization strips these suffixes from a configurable list, preventing "Alaya Construcciones" and "Alaya Construcciones S.A. de C.V." from creating duplicate client records. | Low | Configurable suffix list in code/config, normalization function applied at insert/update, unique constraint on (tenant_id, normalized_name) | No US-focused AMS handles Mexican legal entity suffixes. This is a genuine competitive advantage in the Mexico construction insurance market. Must be extensible for US expansion (Inc., LLC, Corp., L.P.). |
| Solicitation draft versioning with audit trail | Multiple drafts per project+carrier, with revision history preserved. Partial unique index ensures only one active draft at a time. Every sent draft is immutable. If a carrier claims they never received a solicitation, the broker has timestamped evidence. | Low | `solicitation_drafts` table with status enum, partial unique index on (project_id, carrier_id) WHERE status IN ('draft', 'pending', 'approved') | Insurance communications retention is a regulatory expectation. Applied Epic stores sent emails but not draft history. This system preserves the full revision chain — valuable for E&O defense. |

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Unified contact table (polymorphic) | Structurally identical tables (client contacts and carrier contacts) tempt DRY refactoring into one table with a `type` discriminator. This is wrong: FK constraints cannot enforce correct parentage, runtime type checks replace compile-time guarantees, and the role enums are different (client: primary/billing/technical/legal/executive vs carrier: submissions/account_manager/underwriter/claims/billing). | Keep separate tables. The FK IS the type system. Document merge trigger: revisit if a 3rd stakeholder type appears. |
| Contact sync with external CRM | Tempting to sync broker contacts with Salesforce, HubSpot, or the GTM pipeline. Broker clients are insured parties, not sales prospects. Different domain, different lifecycle, different data sensitivity. Cross-module coupling creates maintenance burden for zero user value at this stage. | Context store is the intelligence bridge — not direct CRM integration. If a contact exists in GTM AND broker, the context store links them by company domain/name without tight coupling. |
| Policy management / AMS features | The product boundary is clear: placement workflow tool, NOT an agency management system. No policy issuance, no commission tracking, no renewal management, no certificate issuance. Once bound, the broker enters the policy into their existing AMS. | Status lifecycle ends at `bound`. Post-binding features are a separate product decision. |
| Real-time contact lookup / enrichment | Auto-filling contact details from LinkedIn, Clearbit, or similar enrichment APIs adds complexity, external dependencies, and potential PII compliance issues (especially in Mexico with LFPDPPP regulations). | Manual contact entry. Broker knows their contacts. Context store accumulates intelligence about contacts over time through natural usage (emails, meetings). |
| Multi-tenant contact sharing | Some contacts (especially at large carriers like Zurich or Chubb) might be shared across tenants. Building a shared contact directory adds massive complexity around data isolation, permission models, and conflict resolution. | Each tenant has their own contact records. If two tenants have the same carrier contact, they each maintain their own copy. Tenant isolation is sacrosanct. |
| Client portal / self-service | Letting clients log in to see their projects, approve recommendations, or upload documents is a separate product. The current system is broker-facing only. | Broker sends deliverables via email (Excel export, recommendation email). Client interaction is through the broker, not through the system. |
| Contact import from CSV/Excel | Bulk import is a onboarding convenience feature that adds edge cases (duplicate handling, validation, error reporting). Not needed when starting with zero data and the broker creates clients as projects arrive. | Manual creation via UI. Broker creates ~10-20 clients over the first month. A create form is sufficient. |

## Feature Dependencies

```
Context Store Intelligence Bridge
  <- Context store entity type for "insured company" (may need creation)
  <- Context store entity type for "insurance carrier" (may need creation)
  <- Context store entity type for "insurance project" (may need creation)
  <- Eager entity creation at BrokerClient/CarrierConfig/BrokerProject creation
  <- Failure handling: fail client creation if context entity creation fails
  <- Background reconciliation job for healing NULL context_entity_ids

Client Entity
  <- broker_clients table (DDL)
  <- Normalized name function (legal suffix stripping)
  <- Client CRUD endpoints (list, create, get, update)
  <- Client list page (ag-grid)
  <- Client detail page (profile + contacts + projects)
  <- Sidebar navigation item

Client Contacts
  <- broker_client_contacts table (DDL)
  <- Contact CRUD endpoints (nested under client)
  <- Client detail page contacts section
  <- Client entity (parent FK)

Carrier Contacts
  <- carrier_contacts table (DDL)
  <- Migrate email_address to contact row
  <- Drop email_address from carrier_configs
  <- Contact CRUD endpoints (nested under carrier)
  <- Carrier detail/expand with contacts section
  <- Update solicitation drafter to use carrier contact email

Client-Project Link
  <- client_id FK on broker_projects (DDL)
  <- Update project create endpoint (accept optional client_id)
  <- Update project list endpoint (include client_name via join)
  <- Client select/create widget in CreateProjectDialog
  <- Client entity (must exist first)

Solicitation Drafts (Proper Entity)
  <- solicitation_drafts table (DDL)
  <- Extract draft_subject/body/status from carrier_quotes
  <- Drop old columns from carrier_quotes
  <- Update draft-solicitations endpoint to write new table
  <- Update approve-send endpoint to read new table
  <- Solicitation list endpoint per project

Recommendations (Proper Entity)
  <- broker_recommendations table (DDL)
  <- Extract recommendation_* from broker_projects
  <- Drop old columns from broker_projects
  <- Update send-recommendation endpoint to use new table
  <- Recommendation list endpoint per project
  <- Approval workflow (approve_by_user_id, approved_at)

Project Email Tracking
  <- broker_project_emails table (DDL)
  <- Migrate email_thread_ids array data (if any exists)
  <- Drop email_thread_ids column from broker_projects
  <- Email list endpoint per project

Audit Columns
  <- ALTER TABLE additions across 5 existing tables
  <- Update all write operations to set created_by/updated_by from session
  <- No frontend changes (backend-only)

Binding Status
  <- Update CHECK constraint on broker_projects.status
  <- Update frontend StatusBadge component
  <- Update gate logic / step indicator
```

## MVP Recommendation

Prioritize (in dependency order):

1. **Database schema changes (all 6 new tables + 5 table modifications)** — Foundation for everything else. Single Alembic migration (executed statement-by-statement via Supabase SQL Editor per established workaround). No data to migrate = clean execution. Includes CHECK constraints, audit columns, and binding status.

2. **Client entity + contacts** — The highest-visibility gap. Broker needs to see and manage clients before anything else makes sense. Client CRUD, contact CRUD, client list page, client detail page. Links projects to clients via nullable FK.

3. **Carrier contacts + email_address migration** — Enables role-based solicitation routing. Update solicitation drafter to use carrier contacts (submissions role) instead of the old email_address column. Drop the old column.

4. **Solicitation drafts + recommendations as proper entities** — Structural extractions that enable approval workflows and version history. Update existing endpoints to read/write new tables. Drop old columns.

5. **Context store intelligence bridge** — The differentiator. Eager entity creation on client/carrier/project. This can be implemented incrementally: first just create entities and link them (low effort), then build intelligence surfacing in the UI (higher effort, can be phased).

6. **Project email tracking entity** — Lowest priority table stakes item. Replace TEXT[] with proper table. Minimal frontend impact.

Defer:
- **AI-powered solicitation personalization from context**: Requires accumulated context data. Build the bridge first, personalization second.
- **Carrier response pattern tracking**: Requires historical solicitation/quote data. Instrument first, surface patterns later.
- **Client intelligence panel on detail page**: Requires context entities to have accumulated signals. Ship the entity creation, let signals accumulate, build the panel in a subsequent phase.

## Domain-Specific Insights

### What the insurance broker CRM landscape looks like

The market is bifurcated: on one side, full AMS platforms (Applied Epic, AMS360, HawkSoft) that manage the entire agency lifecycle but have weak placement workflow tooling. On the other side, modern placement tools (BindHQ, BrokerEdge, ExpertInsured) that handle submission-to-bind but lack CRM-depth client intelligence.

No tool in either category bridges accumulated relationship intelligence (from meetings, emails, conversations) into the placement workflow. Applied Epic knows your policy data but not that the client mentioned earthquake concerns in last week's meeting. BindHQ automates submissions but doesn't personalize them based on carrier relationship history.

The context store intelligence bridge is genuinely novel. It occupies the gap between "AMS that stores data" and "AI tool that processes documents." It creates an intelligence layer where every interaction makes the next placement smarter.

### Mexico construction specifics relevant to this milestone

- **RFC (Registro Federal de Contribuyentes)** is mandatory on all Mexican insurance policies and business transactions. The `tax_id` field on `broker_clients` directly maps to this requirement. SAT requires exact RFC + legal name + postal code match for CFDI (electronic invoice) validation. Storing both `name` (display) and `legal_name` (for policies/invoices) is domain-correct.

- **Legal entity suffixes** (S.A. de C.V., S.A.S. de C.V., S.A.P.I. de C.V., S. de R.L. de C.V.) are not just formatting — they indicate the legal structure of the company. The normalized_name function must strip these for dedup purposes but preserve them in `legal_name`.

- **Carrier contact structures in Mexico** differ from US: Mexican carriers often have regional offices with different submission contacts per state/region. The carrier_contacts model (multiple contacts per carrier with roles) handles this correctly.

### Solicitation workflow in regulated insurance

Industry-standard workflow at mature brokerages:
1. Draft solicitation (AI-generated or manual)
2. Internal review (compliance or senior broker reviews content)
3. Approve (confirms content is accurate and professional)
4. Schedule/send (may coordinate timing across multiple carriers)

The current system combines steps 2-4 into one "approve and send" action. The new solicitation_drafts entity with separate `approved` and `sent` statuses correctly models the real workflow. This is not overengineering — it is how BrokerEdge, Applied Epic, and BindHQ all handle outbound communications.

## Sources

- [Best Insurance Broker CRM Software 2025](https://agencymate.com/insights/insurance-broker-crm/) — Feature comparison of top broker CRM platforms
- [Best Insurance Broker Management Systems 2025](https://stratoflow.com/insurance-broker-management-system/) — Core feature expectations for broker management
- [Brokerage Workflow Management](https://www.expertinsured.com/key-features/workflow-and-task-management/brokerage-workflow) — Intake through bind workflow stages
- [BindHQ - AMS & Operations Platform](https://www.bindhq.com/) — Submission to binding automation, carrier connectivity
- [BrokerEdge - Insurance Broker Software](https://www.damcogroup.com/insurance/brokeredge-broker-management-software) — Task management, workflow automation, contact management
- [AI Insurance Distribution: How Brokers Will Win in 2026](https://www.genasystech.com/ai-insurance-distribution-brokers-2026/) — Speed-to-quote moat, carrier relationships
- [AI-driven transformation in commercial insurance](https://www.deloitte.com/us/en/Industries/financial-services/articles/commercial-insurance-industry-ai-driven-transformation.html) — Data ownership as competitive advantage
- [McKinsey: AI in Insurance](https://www.mckinsey.com/industries/financial-services/our-insights/ai-in-insurance-understanding-the-implications-for-investors) — Data ownership, AI differentiation
- [Mexico RFC Number Guide](https://www.signzy.com/blogs/mexico-rfc-for-business-owners) — RFC structure, SAT validation requirements
- [Salesforce Financial Services for Insurance Brokerages](https://www.salesforce.com/financial-services/insurance-brokerage-management-software/) — Enterprise CRM features for brokerages
- [Insurance Workflow Software Guide](https://www.herondata.io/blog/insurance-workflow-software) — Workflow automation patterns
- PROPOSAL-BROKER-DATA-MODEL.md — Internal schema proposal (board-reviewed, all questions resolved)
- CONCEPT-BRIEF-BROKER-DATA-MODEL.md — Advisory board analysis (14 advisors, 4 rounds)
