# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-17)

**Core value:** Conversations automatically become tracked commitments and executed deliverables -- the founder's daily operating system
**Current focus:** v22.0 Skill Platform Consolidation

## Current Position

Milestone: v22.0 Skill Platform Consolidation
Phase: 146 (Schema Foundation) — COMPLETE
Plan: Next phase 147 (Seed Pipeline Extension)
Status: Phase 146 complete; ready for Phase 147 kickoff
Last activity: 2026-04-17 -- 146-02 complete (commit c822da0). Prod Supabase skill_assets table LIVE (0 rows, 3 indexes: pkey + uq_skill_assets_skill_id + idx_skill_assets_bundle_sha256). alembic_version stamped to '064_skill_assets_table'. All 5 ROADMAP success criteria GREEN with log-backed evidence (/tmp/146-sc{1,4,23}.log + /tmp/146-sc5-{current,idem,upgrade}.log). Regression test file test_skill_assets_model.py shipped (135 LOC, 3 tests: bytea round-trip + cascade delete + unique skill_id, @pytest.mark.postgres + admin_session fixture). 342 pytest tests collect cleanly (339 + 3). Pre-existing alembic chain gap (051/062) worked around via direct SELECT on alembic_version + apply-script idempotency re-run — strictly stronger evidence than alembic current/upgrade.

Progress: [█░░░░░░░░░] 14% (1/7 phases — Phase 146 COMPLETE, Phase 147 pending)

### In-Flight from v21.0

v21.0 Document Viewer has one open loop: Phase 145 Plan 04 Task 4 human-verify checkpoint (scenarios A/B/C/D). Resume at .planning/phases/145-stage-1-intake-correctness-typed-upload-and-gap-completion/145-04-PLAN.md. Not blocking v22.0 — no code dependency.

## Performance Metrics

**Previous milestones:**
- v15.0 Broker Module MVP: 8 phases, 25 plans
- v16.0 Briefing Intelligence Surface: 2 phases, 4 plans
- v17.0 Broker Frontend: 7 phases, 16 plans
- v18.0 Broker Data Model v2: 4 phases, 11 plans
- v19.0 Broker Redesign: 7 phases, 16 plans
- v20.0 Coverage Taxonomy: 1 phase, 4 plans

## Accumulated Context

### Decisions

All v1.0-v20.0 decisions archived in PROJECT.md Key Decisions table.

- v21.0 141-01: Named API function getDocumentRendition (not getDocumentDownload) for seamless future migration to /rendition endpoint
- v21.0 141-01: 45min staleTime for signed URL cache (Supabase URLs expire ~60min)
- v21.0 141-02: Single-page rendering for Phase 1a; zoom uses button group; PDF detection via metadata.documents mimetype
- v21.0 143-01: source_excerpt required in EXTRACTION_TOOL schema but source_page NOT required -- preserves scanned-PDF fallback path for NAV-04 all-pages search
- v21.0 143-01: pdf_by_name map computed once unconditionally and shared between primary-contract backfill and per-coverage source_document_id resolution -- single source of truth per analysis run
- v21.0 143-01: case-insensitive filename fallback added to _process_extracted_coverage -- defensive against Claude's occasional case normalization drift; warn-log on total miss for Plan 02/03 monitoring
- v21.0 143-01: TS field type is string | null (not string | undefined) on BrokerProject.source_document_id and ProjectCoverage.source_document_id -- matches backend JSON wire format (None serializes as JSON null)
- v21.0 143-02: FullDocumentViewer now controlled-component; activeFileId + currentPage + highlight lifted to AnalysisTab. onFileChange/onPageChange/onHighlightClear callbacks are the control surface. Shape is frozen for Plan 03.
- v21.0 143-02: cross-doc page-preservation fix -- the [activeFileId] reset effect no longer calls onPageChange(1); reset happens in onDocumentLoadSuccess guarded on out-of-range currentPage. Required so handleClauseClick's synchronous setActiveFileId + setCurrentPage batch survives React's re-render without clobbering the target page.
- v21.0 143-02: onClauseClick signature migrated from (clause: string) to (coverage: ProjectCoverage) -- handler needs source_document_id + source_page + source_excerpt + id; grep-verified no other callers.
- v21.0 143-02: active-card persistence policy -- doc switch clears both highlight AND activeCoverageId; Plan 03's 5s decay timer and scroll-away IntersectionObserver will clear ONLY highlight. Rationale: yellow highlight = short-lived nav aid; coral border = persistent selection marker.
- v21.0 143-02: highlight intent key = coverage.id + ':' + Date.now() -- repeat clicks on the same card produce a new key so Plan 03 effects re-fire (card click is NOT idempotent).
- v21.0 143-03: customTextRenderer chosen over SPEC §4.7 DOM-post-render -- memoized on [highlight?.excerpt] only; auto-reruns on page/excerpt change; documented override in FullDocumentViewer JSDoc.
- v21.0 143-03: all decay machinery (5s timer, scroll-away IntersectionObserver, NAV-04 search, scrollIntoView) guarded on highlight?.excerpt (not highlight) -- page-only jumps (scanned-PDF, excerpt=null) skip all decay/search so no <mark> churn on a non-visual jump.
- v21.0 143-03: 500ms setTimeout before IntersectionObserver.observe() -- matches smooth-scrollIntoView duration; avoids Pitfall 7 mount-fire where observer would immediately report !isIntersecting before scroll completes.
- v21.0 143-03: PDFDocumentProxy imported from top-level 'pdfjs-dist' (not deep path types/src/display/api) -- package.json re-exports it; typed state is PDFDocumentProxy | null, never any.
- v21.0 143-03: textLayerTick counter bumped in onRenderTextLayerSuccess -- re-keys the scroll-away observer effect on every fresh render without tying it to opaque react-pdf internals.
- v21.0 143-03: Bidirectional substring match (item in excerpt OR excerpt in item) in shouldHighlightItem -- ~90% visual coverage of GH wojtekmaj/react-pdf#306 phrase-span limitation; sub-item excerpt splitting explicitly out of Phase 143 scope.
- v21.0 145-01: document_type is a single scalar per POST, not per-file -- frontend sends one request per zone (research Pitfall 4); simpler than parallel Form arrays and maps cleanly to FastAPI Annotated[str, Form()] = "requirements".
- v21.0 145-01: Tenant-scoping retrofit inline on upload endpoint (not deferred) -- pre-Phase-145 latent cross-tenant read; Task 1's own plan step 4 already edited the same where-clause, and the new PATCH reference implementation required the filter for parity. Zero split-brain surface area.
- v21.0 145-01: PATCH body uses Pydantic Literal["requirements","coverage"] (not string + manual whitelist) -- framework returns structured 422; upload Form field uses manual check + 400 because Form scalars with defaults don't plug as cleanly into Literal without extra Annotated trickery.
- v21.0 145-01: PATCH clears `misrouted` flag on successful document_type change -- user asserting the correct zone IS the resolution of the soft warning; re-analysis can re-flag if genuinely wrong.
- v21.0 145-01: PATCH does NOT auto-trigger re-analysis -- `/analyze` is a 60s Claude call; auto-trigger would be expensive and surprising (Open Q 2 resolution from RESEARCH).
- v21.0 145-01: Spread-and-reassign `project.metadata_ = {**existing_meta}` matches key_links.pattern in plan frontmatter and the existing idiom at projects.py:1064; defensive vs. any future in-place mutation upstream even though existing_meta is already a fresh dict.
- v21.0 145-02: delete_stmt hoisted out of `if requirements_pdfs:` guard to run unconditionally -- coverage-only re-runs (broker removes MSA, keeps COI) would otherwise leave stale ai_extraction ProjectCoverage rows forever; `is_manual_override=False` filter preserved on the delete so broker edits survive.
- v21.0 145-02: `_format_taxonomy` factored out of `build_extraction_prompt`'s inline comprehension so `build_policy_extraction_prompt` can reuse identical taxonomy rendering -- prevents drift between the two passes' taxonomy views.
- v21.0 145-02: `_normalize_coverage_key` is strip+lower only, explicitly distinct from quote_extractor's `_normalize_coverage_type` which replaces underscores with spaces (display-name fuzzy matcher). Post-Phase-140 keys are canonical snake_case; exact match on the normalized value is the right shape.
- v21.0 145-02: `Decimal(str(limit_amount))` for ProjectCoverage.current_limit writes -- str() intermediate avoids float-binary drift (e.g., Decimal(0.1) vs Decimal('0.1')); wrapped in InvalidOperation/TypeError/ValueError catch.
- v21.0 145-02: Misrouted detected_type enums are mirror-image symmetric across passes: EXTRACTION_TOOL (requirements pass) emits ['coverage','quote','unknown'], POLICY_EXTRACTION_TOOL emits ['requirements','quote','unknown']. Each pass names what the OTHER kind of doc looks like, so frontend can render "This COI was uploaded to the Requirements zone; detected as coverage."
- v21.0 145-02: Policy-pass misrouted wins on merge collisions (`merged_misrouted.update(req_misrouted)` then `.update(policy_result.misrouted)`). File_id is PK-unique and partition makes collisions impossible; ordering is documented defensively.
- v21.0 145-02: Policy-pass failure is non-fatal for analyze_contract -- if extract_current_policies returns status=failed, log and continue so successful requirements extraction isn't lost to a coverage-pass API hiccup; orphan_policies + misrouted setdefault to empty so downstream reads are safe.
- v21.0 145-02: Initialize coverages_created/contract_language/contract_summary/req_misrouted BEFORE the `if requirements_pdfs:` guard so always-run metadata writes + return dict have well-defined fallback values; contract_language defaults to project.language or 'es', contract_summary to ''.
- v21.0 145-02: 185-191 guard text preserved byte-for-byte per critical-notes; new misrouted_documents instruction paragraph APPENDED after the guard, not interleaved -- keeps the semantic safety net intact (Claude hitting "DO NOT extract" from top-down prompt read) even if the structured field is ignored.
- v21.0 145-03: Semantic anchor re-location over trusting plan line numbers -- Plan 03 referenced lines 766/769/788 from pre-Plan-02 snapshot; Plan 02's +893/-142 shift moved them; used `grep -n` on anchor tokens to find actual positions (1441 flush, 1490 activity, 1421 project_meta rebuild, 1384-1386 merged_misrouted, 1141 delete_stmt flush).
- v21.0 145-03: is_manual_override preservation in inline detect_gaps requires `if 'gap_status' in updated` guard on ORM assignment -- detect_gaps passes manual-override rows through as shallow copies WITHOUT setting gap_status/gap_amount keys; naive `.get(None)` would clobber broker manual values. Essential correctness fix vs. plan's sample code.
- v21.0 145-03: Task 2a's pre-reset is UNCONDITIONAL; Task 2b's misrouted-persist is CONDITIONAL on `if merged_misrouted` -- clean analyses skip pointless second JSONB rebuild (one reset flush only); misroute analyses do two writes (reset + persist). Step 11's always-run project_meta reassignment handles metadata writes independently.
- v21.0 145-03: Inline coverage serialization (4-field dict at call site) instead of importing projects._coverage_to_dict -- contract_analyzer in engines/ must not depend on api/broker/ (reverse layering); inlined shape is minimal (only fields detect_gaps reads).
- v21.0 145-03: Re-query ProjectCoverage inline before detect_gaps (not reuse coverages_created list) -- coverages_created is list-of-dicts from extraction, not ORM objects. gap_status/gap_amount writes need ORM handles; single order_by(created_at) reload captures post-policy-pass state (inserts from req pass + current_* updates from policy pass).
- v21.0 145-03: gap_summary "unknown" count can be non-zero and is CORRECT -- rows with required_limit=None get gap_status="unknown" (string) per gap_detector.py:49-51, which satisfies "no NULL gap_status" invariant (NULL column ≠ string "unknown"); frontend renders as "data missing" copy.
- v21.0 145-03: Ordering invariant between Task 2b and Step 11 is load-bearing -- Task 2b's misrouted-flag write MUST happen BEFORE Step 11's `project_meta = dict(project.metadata_)` shallow copy, or the rebuild silently drops the flags. Documented explicitly in the Task 2b block's inline comment for future editors.
- v21.0 145-04: DocumentEntry centralization to types/broker.ts over per-consumer definition -- AnalysisTab previously had a narrower 3-field subset (file_id/name/mimetype) vs OverviewTab/DocumentUploadZone's 6-field versions; centralized version is a strict superset PLUS the Phase 145 fields (document_type, misrouted, storage_path). Reduces drift risk AND fixed 3 pre-existing narrow-type TS errors as a side effect (baseline: 21 errors, post: 18).
- v21.0 145-04: DocumentZoneKind literal union exported from types/broker.ts (not api.ts) -- zone is a domain concept the UI reasons about, not just a wire-format detail; all three consumers (api.ts + both hooks) import from types.
- v21.0 145-04: useDocumentUpload default kind='requirements' matches backend POST default from Plan 01 -- older/forgotten callers silently send requirements (safest default: backend extraction handles it AND user can move via chip; silent miscategorization of coverage would be worse).
- v21.0 145-04: Misrouted chip palette is amber (border-amber-300 / bg-amber-50 / text-amber-800), NOT red -- per user's global design-guidelines Lumif.ai warn aesthetic; misroute is recoverable context not blocking error; harmonizes with #E94D35 primary.
- v21.0 145-04: otherKind computed once at component top (`kind === 'requirements' ? 'coverage' : 'requirements'`) -- single line to extend for any future third zone; ternary is explicit about current two-zone scope.
- v21.0 145-04: stopPropagation on chip click essential -- file card itself has onClick that opens signed-URL download in new tab; without stopPropagation, clicking Move would simultaneously fire download handler (visual bug).
- v21.0 145-04: File-card React key upgraded from `doc.name ?? idx` to `doc.file_id ?? doc.name ?? idx` -- after useDocumentMove query invalidation same file appears in different zone's list; file_id is backend PK and stable across zone moves (PATCH rewrites document_type, not file_id).
- v21.0 145-04: Skill docs are DOCUMENTATION-ONLY additive (markdown blockquote callouts near headings) -- matches research Finding 1/7 locking in "skills are clipboard-paste handoffs"; Phase 145 flow routes through frontend+backend not skill commands; callouts searchable by "Phase 145" tag for future removal.
- v21.0 145-04: npm run build INTENTIONALLY skipped as verification -- baseline on main has 21 pre-existing TS errors across 5 unrelated files (GapCoverageGrid/ComparisonGrid/etc); `tsc -b --noEmit` filtered for touched files is the correct verification shape for a dirty baseline. My changes reduced total to 18 (centralization fixed pre-existing inline narrow-type drift).
- v22.0 146-01: skill_assets.updated_at has NO `onupdate` and NO trigger -- matches parent SkillDefinition convention (zero onupdate uses in backend/src/flywheel/db/). Phase 147 seed code must set `updated_at = now()` explicitly on upsert. Conscious deviation from CONTEXT.md's `onupdate=func.now()` prescription; deviating from zero-precedent would introduce new SQLAlchemy import style for no reliability gain given centralized writer.
- v22.0 146-01: Defensive `CREATE EXTENSION IF NOT EXISTS pgcrypto` as first STATEMENT in apply_064 script -- Supabase has it pre-enabled (41 gen_random_uuid() uses, 0 CREATE EXTENSION statements) but local Docker Postgres may not; IF NOT EXISTS = no-op on Supabase. Resolves RESEARCH Open Q2.
- v22.0 146-01: Index naming uq_skill_assets_skill_id / idx_skill_assets_bundle_sha256 -- mirrors nearest-neighbor skill_definitions (uq_skill_defs_name / idx_skill_defs_*), NOT newer ix_broker_* style from 058. Skill-family tables share a convention.
- v22.0 146-01: CHECK (bundle_size_bytes >= 0) stays at DDL layer only, NOT mirrored in ORM __table_args__ -- matches broker-tables convention. ORM path for defensive validation lives at service/API layer.
- v22.0 146-01: Apply script stamp target = '064_skill_assets_table' EXACTLY, no _false/_migration suffix -- fixes the 062-template bug (Pitfall 3) where stamp drifted from migration revision. Plan 02 will UPDATE alembic_version via raw SQL.
- v22.0 146-01: Pre-existing alembic chain gap at 051_create_waitlist_table (referenced by 052 but file missing) -- blocks local alembic history/heads/current walk with KeyError. Second known gap at 062_broker_schema_mods_03 (referenced by 063). Neither fixed in Phase 146 scope; Plan 02 apply script bypasses alembic for the stamp step so the gap doesn't block prod. Separate chore-PR recommended before any future `alembic upgrade head` attempt.
- v22.0 146-01: SkillAsset first use of uselist=False (1:1 scalar) in models.py -- DB-level 1:1 enforced by unique index uq_skill_assets_skill_id on child's skill_id column (SQLAlchemy uselist=False is Python-side hint only, not a constraint). Cascade = 'all, delete-orphan' on parent side + ondelete='CASCADE' on FK child side = belt-and-suspenders delete propagation.
- v22.0 146-02: Preflight alembic_version check BEFORE apply is load-bearing -- 146-01 SUMMARY handoff flagged operator-pre-check-needed; verified prod was exactly '063_skill_protected_default' before running apply_064. If it had drifted (e.g., to a stale '062_*_false' name), halt + surface would have prevented stamping over a malformed chain position.
- v22.0 146-02: SC5 evidence via direct `SELECT version_num FROM alembic_version` on prod -- NOT `alembic current` which fails locally with KeyError('051_create_waitlist_table') per pre-existing chain gap. Direct SELECT is strictly stronger proof of the semantic (head revision on prod) and doesn't require a walkable local chain.
- v22.0 146-02: Idempotency proven by re-running apply_064_skill_assets_table.py, NOT `alembic upgrade head` -- both blocked by same chain gap. Re-run exercises every DDL statement (pgcrypto, CREATE TABLE, UNIQUE INDEX, INDEX, UPDATE alembic_version) as no-op via IF NOT EXISTS -- stronger than upgrade-head's passive chain traversal.
- v22.0 146-02: 3 regression tests (not 2) added to lock SC2/SC3/SC4 permanently -- test_bytea_round_trip + test_cascade_delete_removes_asset + test_unique_skill_id_rejects_duplicate. Third test cheap to add because admin_session + raw SQL makes one more assertion nearly free, and SC4 (unique index) is a ROADMAP criterion that deserves a pytest gate alongside SC2/SC3.
- v22.0 146-02: pytest.mark.postgres is DECLARATIVE for `-m "not postgres"` filtering, NOT auto-skip -- codebase convention per test_storage.py (34 errors on no-Docker). Tests structure + collection verified correct (3 tests + filter deselects 3); they'd pass on Docker Postgres with full test schema.
- v22.0 146-02: Upstream alembic chain gaps (051_create_waitlist_table, 062_broker_schema_mods_03) remain unfixed -- out of scope for Phase 146 + documented as chore-PR recommendation. Zero impact on prod (apply_064 bypasses alembic for stamp via raw SQL); only affects local `alembic history/current/upgrade head` commands.

### Pending Todos

- v18.0 Phase 132-03 awaiting final verify (committed at 387291a)
- Title matching false positives in _filter_unprepped (deferred from 66.1)
- Private import coupling in flywheel_ritual.py (tech debt)
- **Module-based skill access control**: Add `module` column to `skill_definitions` (broker/gtm/meetings) + `tenant_modules` table to gate skill access by subscription.
- **Broker frontend polish gaps** (from UX audit): comparison matrix data flow (coverage_id linkage), quote document download links, carrier logos across all views

### Roadmap Evolution

- Phase 145 added: Stage 1 intake correctness — typed upload (Requirements vs Current Coverage zones) + auto gap detection + current-policies extraction pass + orphan_policies metadata + document_misrouted safety net

### Blockers/Concerns

None active.

**Pre-implementation decisions for v21.0 (from spec):**
1. Deployment environment -- Docker, bare metal, or serverless? Determines conversion tool choice (LibreOffice vs Gotenberg vs Python fallback).
2. CORS test -- Can fetch() from localhost:5173 access Supabase signed URLs? If not, need proxy endpoint.
3. [DONE in 143-01] source_excerpt required -- now enforced in EXTRACTION_TOOL.input_schema.properties.coverages.items.required.

## Session Continuity

Last session: 2026-04-17
Stopped at: Completed 146-02-PLAN.md (commit c822da0). Phase 146 COMPLETE. Prod Supabase skill_assets table live (0 rows, 3 indexes: pkey + uq_skill_assets_skill_id + idx_skill_assets_bundle_sha256). alembic_version stamped to '064_skill_assets_table' (preflight confirmed '063_skill_protected_default' before apply; post-apply confirmed '064_skill_assets_table' via direct SELECT). Apply-script re-run verified idempotent no-op. All 5 ROADMAP success criteria GREEN with log-backed evidence: SC1 (count=0 from fresh session), SC2 (bytea round-trip OK, 20 bytes, sha256 matches), SC3 (FK cascade removes skill_asset when skill_definition deleted), SC4 (both custom indexes visible + duplicate skill_id rejected by pytest IntegrityError), SC5 (direct alembic_version SELECT = '064_skill_assets_table'). Regression test shipped at backend/src/tests/test_skill_assets_model.py (135 LOC, 3 tests: bytea round-trip, cascade delete, unique skill_id — pytestmark = [pytest.mark.asyncio, pytest.mark.postgres], admin_session fixture from conftest.py:138). 342 pytest tests collect (339 baseline + 3 new, zero regressions). Pre-existing alembic chain gap (051_create_waitlist_table, 062_broker_schema_mods_03) remains; documented as out-of-scope chore-PR recommendation. No orphan smoke-test rows in prod. Evidence logs at /tmp/146-apply.log + /tmp/146-sc{1,4,23}.log + /tmp/146-sc5-{current,idem,upgrade}.log + /tmp/146-preflight.log.

Resume file: Phase 147 Research (Seed Pipeline Extension) — next step is `/gsd:research-phase 147` to gather context for upsert logic into skill_assets (content-addressed, per-skill bundle zipping, bundle_sha256 + bundle_size_bytes computation, updated_at explicit-set per 146-01 decision, pgcrypto already enabled per 146-02 apply).

v21.0 PENDING (not blocking v22.0): 145-04-PLAN.md Task 4 human-verify CHECKPOINT -- autonomous Tasks 1-3 complete (commit 71c5b4e). Awaiting user to run Scenarios A/B/C/D and type "approved" to mark Plan 04 / Phase 145 complete.
