# Pitfalls Research

**Domain:** AI Email Copilot integration into existing multi-tenant SaaS (Flywheel V2)
**Researched:** 2026-03-24
**Confidence:** HIGH — research verified with official Gmail API docs, Google dev forums, academic security research, and community post-mortems

---

## Critical Pitfalls

### Pitfall 1: historyId Expiry Without Full-Sync Fallback

**What goes wrong:**
The Gmail sync worker stores a `historyId` watermark and calls `history.list(startHistoryId=...)` on each cycle. After a weekend outage, token expiry, or any gap longer than ~1 week, the stored historyId falls outside Gmail's available range. Gmail returns HTTP 404. The worker catches a generic exception, logs it, and continues with the stale watermark — silently missing every email received during the gap. Users never see these emails in the copilot.

**Why it happens:**
Developers treat historyId like a reliable pagination cursor (analogous to database sequence IDs). It isn't. Google documents that "records may be available for at least one week and often longer, but sometimes significantly less." A historyId is also non-contiguous — there are gaps between valid IDs, and a push notification historyId often cannot be used directly in `history.list` (returns empty results). The 404 is the documented failure mode, but developers handle it as a generic error rather than a full-sync trigger.

**How to avoid:**
- Explicitly catch HTTP 404 from `history.list` as a distinct code path — not a generic exception.
- On 404: delete the stored `history_id` from `integration.settings`, set `initial_sync_done = False`, and re-run the initial sync for that integration.
- After full sync completes, capture the new historyId from the response's `historyId` field.
- Track `last_full_sync_at` in `integration.settings` to monitor gap recovery.
- Never trust that the current historyId will work after more than 3 days of inactivity.

**Warning signs:**
- A user reports "I had emails that weren't scored" after being offline or after a deploy.
- The sync worker logs 404 errors for an integration but doesn't reset its watermark.
- Monitoring shows zero new emails ingested over a 2-hour window during business hours.

**Phase to address:** Phase 1 (Gmail Read Service + Sync Worker) — the fallback must be built into `sync_inbox()` from day one. Adding it later requires careful state migration for all existing integration rows.

---

### Pitfall 2: OAuth Scope Expansion Breaks Existing Users

**What goes wrong:**
The existing `google_gmail.py` grants `gmail.send` scope. A developer adds `gmail.readonly` to the existing `SCOPES` list (the obvious path). Existing users have refresh tokens for `gmail.send` only. On the next token refresh, the API call includes the new scope — Google detects scope mismatch and returns `invalid_grant`. The send integration goes red for all connected users. Now to reconnect Gmail send, every user must re-authorize from scratch.

**Why it happens:**
`gmail.readonly` is a **restricted scope** (it grants access to the entire inbox). Google's OAuth 2.0 requires explicit user consent for each new scope grant. There is no background upgrade path. The scope set in the OAuth flow must exactly match what the user consented to. Adding a new scope to an existing flow silently requests something the stored token never authorized.

**How to avoid:**
- NEVER modify the `SCOPES` list in `google_gmail.py`. The send integration is already in production.
- Create a completely separate OAuth flow (`gmail_read.py`) with `SCOPES = [gmail.readonly, gmail.modify]`.
- Store as `provider="gmail-read"` in the `Integration` table — a new row, not an update.
- The integration settings page shows two separate Gmail entries: "Gmail (Send)" and "Gmail (Inbox)."
- Users explicitly opt in to the inbox reading integration. It is never auto-enabled.
- Before shipping: verify the new OAuth app passes Google's restricted scope verification for `gmail.readonly`. This process takes 2-6 weeks if the app is in "Testing" mode or has fewer than 100 verified users.

**Warning signs:**
- Any PR that modifies the `SCOPES` variable in `google_gmail.py`.
- A developer proposes "combining the scopes for simplicity."
- The OAuth consent screen is updated in Google Cloud Console without documenting the change.

**Phase to address:** Phase 1 (Gmail OAuth expansion) — the architectural decision to use separate Integration rows must be enforced before any code is written for `gmail_read.py`.

---

### Pitfall 3: The 5-Minute Polling Wall at 200+ Users

**What goes wrong:**
The `email_sync_loop()` iterates over all connected integrations sequentially. At 50 users it takes ~50 seconds per cycle, well within the 5-minute window. At 200 users it takes 3-4 minutes. At 500+ users, one full cycle takes longer than 5 minutes — the next scheduled cycle starts before the first finishes, connections pile up, DB pool exhausts, and the system slogs into a semi-deadlock where most users get stale data indefinitely.

**Why it happens:**
The calendar sync clone pattern works for a small user base. The asyncio sleep-based loop has no built-in sharding or per-user concurrency. Each `sync_inbox()` call blocks the loop until it completes (even though it's async, it still runs sequentially if awaited serially).

**How to avoid:**
- Build `email_sync_loop()` to iterate users in batches of 20-50, running each batch concurrently with `asyncio.gather()`.
- Add a hard timeout per integration (e.g., 30 seconds) to prevent one slow API call from blocking the batch.
- Track `last_synced_at` per integration so you can skip recently-synced ones if the loop is overloaded.
- When the loop iteration time exceeds 60% of `SYNC_INTERVAL`, emit a warning metric.
- At the architecture level, the transition to Gmail Pub/Sub push notifications is documented as the correct solution above 500 users — plan the migration path in the data model (add `pubsub_subscription_id` to Integration) even if you don't implement it immediately.

**Warning signs:**
- Total sync cycle time logged as approaching 4+ minutes.
- `asyncio.sleep(300)` effectively sleeping for 0 seconds because cycle takes 5+ min.
- DB connection pool errors appearing in logs during sync cycles.

**Phase to address:** Phase 1 (Sync Worker) — the concurrency structure must be correct from the start. Refactoring from sequential to concurrent at scale requires careful state management and is expensive to do after the fact.

---

### Pitfall 4: Tenant Context Leakage via Shared LLM Prompt Context

**What goes wrong:**
The email scorer runs as a batch SkillRun. The system prompt is assembled with context entries for the current tenant. If the skill executor's context loading is not strictly tenant-scoped, entries from another tenant's context store can appear in the assembled prompt. The LLM generates a score referencing a competitor's deal (from tenant B) while processing tenant A's emails. This is a silent, hard-to-detect data breach.

**Why it happens:**
RLS protects direct SQL queries, but RLS does not protect LLM prompt context. The skill executor's `context_tools` may execute FTS queries that inherit the current DB session's `app.tenant_id` setting — but if the session is reused across batch jobs, the tenant setting can carry over. Additionally, the voice profile JSONB contains training examples from specific users; if the profile lookup uses `user_id` without also filtering by `tenant_id`, cross-tenant profile reads are possible in multi-tenant deployments.

**How to avoid:**
- Every `context_tools` call inside a skill execution must explicitly pass `tenant_id` as a filter parameter, not rely solely on session-level RLS.
- The `EmailVoiceProfile` lookup in the drafter skill must always `WHERE tenant_id = $1 AND user_id = $2` — both conditions, never just `user_id`.
- The email scorer's system prompt must never include raw email content from any source other than the current batch's emails.
- Write an integration test that creates two tenants, syncs emails for both, and asserts that tenant A's score prompt contains zero content from tenant B's context store.
- Use separate DB sessions per SkillRun execution — never share a session across different tenants' skill runs.

**Warning signs:**
- Skill run logs showing context entries with `tenant_id` different from the current run's tenant.
- A user reports a draft referencing people or companies they don't know.
- Missing `AND tenant_id = $1` clause in any context query within skill execution.

**Phase to address:** Phase 2 (Email Scorer Skill) — tenant isolation must be verified in the scorer before the drafter is built. The drafter inherits all scorer context, so a leak in the scorer cascades into drafts.

---

### Pitfall 5: Voice Profile Poisoned by Auto-Replies and Out-of-Office Messages

**What goes wrong:**
The voice profile initializer pulls the user's last 100 sent emails to learn their tone. The batch includes: 15 out-of-office auto-replies ("I am out of the office until..."), 8 calendar invite acceptances ("Accepted: Your meeting request"), 12 form confirmations ("Thank you for contacting us"), and 3 bounce notifications. The model learns a stilted, robotic, impersonal voice. Drafts sound like system messages. Users dismiss every draft and distrust the feature.

**Why it happens:**
The Gmail API `messages.list` with `in:sent` returns ALL sent messages, including those sent by Gmail automation (calendar invites, auto-responders, Workspace rules). Developers assume "sent by the user" means "written by the user."

**How to avoid:**
- Filter sent messages before passing to voice profile analysis:
  - Exclude messages where `Auto-Submitted` header is present (RFC 3834 standard for auto-replies).
  - Exclude messages shorter than 3 sentences (captures one-liners and form confirmations).
  - Exclude messages where the sender is a noreply/no-reply address pattern.
  - Exclude messages that match common auto-reply phrases: "Out of office", "automatic reply", "on vacation", "I will be back", "do not reply to this email."
  - Prefer messages with at least one sentence of original content (exclude pure quote replies).
- After filtering, if fewer than 30 quality samples remain, flag the profile as `low_confidence: true` and surface a UI prompt asking the user to add writing samples or confirm the extracted style.
- Log how many emails were filtered vs. used so you can tune the filter over time.

**Warning signs:**
- Voice profile JSONB shows `samples_analyzed < 20` after initialization on a user with 200+ sent emails.
- Profile `tone` field is blank or shows "formal, brief."
- First draft generated is under 50 words for a scenario that requires a substantive reply.

**Phase to address:** Phase 2 (Voice Profile Init in Sync Worker) — the filter logic must ship with the initial voice profile extraction. Reprocessing 100 sent emails after users have had a bad first experience doesn't recover trust.

---

### Pitfall 6: Email Body in Error Logs (GDPR Time Bomb)

**What goes wrong:**
The drafter skill fetches the email body on demand. A MIME parsing error throws an exception. The exception handler does `logger.exception("Failed to parse email body: %s", raw_mime_payload)`. The raw email body — which contains names, financial figures, private health information, or legal communications — is now in the application log, which is shipped to Datadog/CloudWatch/Sentry. The log retention is 90 days. A routine security audit discovers the PII. Legal is involved.

**Why it happens:**
Developer instinct during debugging is to log the value that caused the error. This is correct for most data. Email bodies are categorically different — they are not application data, they are user-owned communication content with GDPR/CCPA implications.

**How to avoid:**
- Establish a hard rule at project kickoff: email body content NEVER appears in log output at any level (DEBUG, INFO, WARNING, ERROR).
- The body fetch function `get_message_body()` wraps all operations in a try/except that logs only the message ID and error type, never the content.
- Use structured logging with an `email_body` field that is always redacted: `logger.error("body_parse_failed", extra={"gmail_message_id": msg_id, "error": str(e), "body": "[REDACTED]"})`.
- The Sentry/error tracking integration must have a before-send hook that strips any field named `body`, `content`, `text`, or `snippet` from event payloads.
- Apply the same rule to email metadata (subject lines can contain sensitive information): log message IDs, never subjects in error paths.
- Write a linting rule (pre-commit hook or CI check) that scans skill files and service files for log statements that reference body/content variables.

**Warning signs:**
- Any log line containing more than 100 characters of free-form text from an email processing context.
- Sentry events that have large string payloads from Gmail processing functions.
- A developer adding `print(body)` debug statements during local testing that aren't removed before commit.

**Phase to address:** Phase 1 (Gmail Read Service) — the log redaction pattern must be enforced in `gmail_read.py` from the first line. Every subsequent file that touches email content inherits this pattern.

---

### Pitfall 7: On-Demand Body Fetch Fails Silently During Draft Review

**What goes wrong:**
A user sees a draft in the UI and clicks "View full email" to read what the draft is responding to. The frontend makes a request. The backend calls `gmail_read.get_message_body(integration, gmail_message_id)`. The Gmail access token has expired (user hasn't touched the app in a week). The fetch fails. The UI shows a loading spinner that never resolves, or returns an empty email body. The user tries to review the draft against an empty original — approves a contextually wrong reply, sending it to a business contact.

**Why it happens:**
Token expiry between sync and draft review is not an edge case — it's the normal case for users who check the copilot weekly. The on-demand body fetch creates a live dependency on a valid auth token at the moment of review, which is harder to guarantee than at sync time.

**How to avoid:**
- On any 401/403 from the Gmail API during body fetch: return a structured error, not an empty string. The frontend must distinguish "body unavailable due to auth" from "body is empty."
- Surface a re-authorization prompt when body fetch fails: "Your Gmail connection needs to be refreshed to show the original email."
- Implement proactive token refresh in `gmail_read.py`: if the access token is within 5 minutes of expiry, refresh it before the fetch attempt.
- Store the 200-character Gmail snippet (already in the `emails` table) as a fallback — if body fetch fails, show the snippet in the review UI so the user has minimal context.
- The `EmailDraft` row should record `body_fetched_at` — if the draft was generated more than 7 days ago, treat the stored body reference as potentially stale and re-fetch.

**Warning signs:**
- Draft approval rate drops below 30% — users are approving without proper context.
- Error logs show body fetch failures with 401 responses but no re-auth prompts in the UI.
- User support tickets: "I approved a draft that made no sense."

**Phase to address:** Phase 3 (Email Drafter) and Phase 4 (Review API) — the auth failure path must be specced in both the skill execution and the API layer before the frontend is built.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store email body in DB instead of fetching on-demand | Simpler drafting, no live API dependency | GDPR liability, PII archive, storage growth at scale | Never — privacy minimization is a hard requirement |
| Single historyId with no 404 fallback | 20 lines less code | Silent sync gaps after any outage or gap | Never — the fallback IS the feature |
| Score one email per SkillRun (not batched) | Simpler logic, easier debugging | LLM cost 10-20x higher, quota exhaustion at 50+ users | Only in earliest dev/demo mode — remove before beta |
| Block sync loop on skill execution (await inline) | Simpler control flow | Sync backs up for all users when one LLM call is slow | Never — decoupling via job_queue is the architectural requirement |
| Voice profile from all sent emails (unfiltered) | Dead simple implementation | Robotic voice from auto-replies poisons the model | Never — filtering is part of the feature correctness |
| Use same DB session across tenants in batch scoring | Avoids session overhead | Cross-tenant context leakage via RLS session state | Never — always use per-tenant sessions |
| Log email content in DEBUG mode only | Easier debugging | Debug logs get shipped to logging infra; GDPR violation | Never — environment-conditional PII logging is still a violation |
| Polling forever (no Pub/Sub migration plan) | No GCP Pub/Sub setup | Architecture cliff at 500 users, costly migration | Acceptable for Phase 1, but add `pubsub_subscription_id` column now |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gmail API `history.list` | Treating historyId as stable indefinitely | Always handle HTTP 404 as full-sync trigger; store `initial_sync_done: false` on 404 |
| Gmail API scopes | Adding new scope to existing OAuth client | Create separate Integration row with separate OAuth flow; never modify existing scope set |
| Gmail Pub/Sub watch | Assuming the watch auto-renews forever | Schedule explicit re-watch call every 5 days (watch expires at 7 days); monitor silently-expired watches |
| Gmail API quota | Assuming per-project quota is the bottleneck | Per-user limit is 15,000 units/minute; at 1000 users polling every 5 min, aggregate is fine but a single user's initial backfill can exhaust their per-user quota instantly |
| Gmail `messages.get` | Fetching full message on every email in sync | Use `format=METADATA` with `metadataHeaders=[From,Subject,Date,Message-ID,References]` during sync; only fetch full body on-demand for drafting |
| Anthropic API | One SkillRun per email | Batch 15-20 emails per SkillRun; one LLM call scores the batch; cross-email pattern reasoning improves quality |
| Anthropic API | Passing full context store dump to scorer | Targeted retrieval — lookup sender entity + 3 most relevant context entries per email; do not send the entire context store |
| OAuth token storage | Refreshing token synchronously on every API call | Cache access tokens in memory (or Redis for multi-process); refresh only when within 5 minutes of expiry |
| Gmail API MIME | Assuming `payload.body.data` is always the email body | Multipart emails have `payload.parts[]`; some have nested multipart; always walk the parts tree recursively |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential sync loop (no concurrency) | Sync cycle time creeps toward 5 min; users report stale data | Run integrations in concurrent batches using `asyncio.gather()`; add per-integration timeout | ~200 connected users |
| Scoring every email on every sync | LLM costs spike; Anthropic rate limit errors appear | Filter to `WHERE scored = false`; idempotency key on `(tenant_id, gmail_message_id)` | ~50 active users with busy inboxes |
| No per-tenant scoring cap | One high-volume user consumes all Anthropic quota | Add `daily_score_budget` per tenant; queue overflow emails for next day | First power user with 200+ emails/day |
| Unbounded email table growth | DB queries slow; full-text index bloat | Add retention policy: soft-delete emails older than 90 days that are `is_replied=true` and have no pending draft | ~6 months of production data for 100 users |
| Thread view GROUP BY without index | Thread list page times out | Composite index on `(tenant_id, gmail_thread_id, received_at DESC)` — must exist at migration time | ~5000 emails per tenant |
| Voice profile update on every draft approval | Profile JSONB grows unbounded; every approval triggers a re-analysis LLM call | Debounce: update profile only after 5 new approvals accumulate, or once daily | Individually acceptable; multiplied across 100 users it's background noise |
| Fetch full message body in metadata for all emails | API quota consumed on useless data | Always request `format=METADATA` in sync; only `format=FULL` on-demand for drafting | Initial backfill for a user with 1000 emails |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Email body in application logs | GDPR violation, PII in logging infrastructure | Hard rule: never log body content; log only message IDs; add Sentry before-send hook to strip body fields |
| Shared LLM context across tenants | Cross-tenant data leak — Tenant A sees Tenant B's contact details in AI outputs | Explicit `tenant_id` filter on every context query; separate DB sessions per SkillRun; integration test verifying isolation |
| Voice profile accessible by user_id alone | User data accessible across tenants in edge cases | Always query `WHERE tenant_id = $1 AND user_id = $2` — both conditions required |
| Draft body stored indefinitely after approval | Approved draft body is an archived copy of the original email content (indirect PII) | Null out `EmailDraft.body` after `status=sent`; retain only metadata (approved_at, edit_count) |
| HTML email rendering without sanitization | XSS via crafted email displayed in UI | Never render raw HTML from email bodies in the review UI; use plain text extraction only; if HTML preview is needed, use DOMPurify in the frontend |
| OAuth tokens in application error responses | Token exposed in Sentry or error tracking | Ensure no token data reaches exception context; scrub credential objects from Sentry payloads |
| Email sender data in client-side state without scoping | Frontend Zustand store holds all email threads; XSS could expose them | Emails are user-specific; ensure auth middleware validates all email API responses are scoped to the authenticated user |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Bad first draft kills feature adoption permanently | User dismisses every draft for a week; turns off feature; never returns | Gate draft visibility behind a 3-day confidence-building delay; only surface drafts when confidence is established from initial voice profile |
| Urgency inflation (everything scored high) | User ignores all urgency signals after the first false alarm; feature becomes noise | Score conservatively; fewer P1 alerts with high precision beats many P1 alerts with low precision; calibrate thresholds on real inbox before shipping |
| No explanation for why an email was scored high | User distrusts score; cannot act on it | Always show 1-2 sentence reasoning with the score: "This is from your largest account and mentions contract renewal — matched 3 context entries." |
| Draft approval with no original context visible | User approves a contextually wrong reply; sends to a business contact; embarrassment | Show Gmail snippet (already stored) alongside draft; add "View full email" that fetches body on-demand with clear auth-failure handling |
| Voice learning from edited drafts without diff | Profile drifts toward the AI's own style (circular reinforcement) | Learn from edits, not from the final approved text; the delta between draft and user edit is the signal; the approved text has model influence baked in |
| Notification for every new email synced | Notification fatigue within 24 hours; user disables all copilot notifications | Notify only on genuine P1s (priority 5, immediate action required); batch P2-P3 into a daily digest; never notify on routine emails |
| Re-auth prompt appearing mid-workflow | User interrupted during draft review; loses context; frustration | Proactive token refresh on app load; surface re-auth banner in the email UI header, not as a blocking modal mid-review |
| "AI wrote this" visible to email recipients | Recipients trust messages less when they know AI drafted them | Drafts are for the user to send as their own; no AI footprint in outbound email; no "drafted with Flywheel" signature added by default |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Gmail Sync:** Full-sync fallback on 404 — verify historyId invalidation is handled, not just logged
- [ ] **Gmail Sync:** Concurrent integration processing — verify loop doesn't run integrations serially
- [ ] **Email Scorer:** `scored = true` idempotency check — verify emails are never scored twice
- [ ] **Email Scorer:** Tenant isolation — verify SkillRun for tenant A cannot read context entries from tenant B
- [ ] **Email Drafter:** Voice profile filter — verify auto-replies excluded before profile generation
- [ ] **Email Drafter:** Body fetch failure handling — verify UI shows snippet when body fetch fails, not blank
- [ ] **Voice Profile:** `low_confidence` flag — verify profile shows cold-start disclaimer when < 30 quality samples
- [ ] **Privacy:** Log redaction — verify no email body content appears in any log at any log level
- [ ] **Privacy:** Draft body nulled on send — verify `EmailDraft.body` is cleared after `status=sent`
- [ ] **OAuth:** Separate Integration row — verify `google_gmail.py` SCOPES list was not modified
- [ ] **OAuth:** Token proactive refresh — verify tokens are refreshed before expiry, not reactively on failure
- [ ] **Scale:** Per-tenant daily scoring cap — verify a single tenant cannot exhaust platform-wide Anthropic quota
- [ ] **Scale:** Retention policy — verify email table has scheduled cleanup for replied+old emails
- [ ] **UX:** Score reasoning surfaced — verify every `EmailScore` row has a `reasoning` string visible to the user

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| historyId expiry and missed emails | LOW | Set `initial_sync_done = false` for affected integration; next sync cycle runs full backfill; emails processed in priority order |
| Scope expansion breaking send integration | HIGH | Rollback scope change; restore original SCOPES list; trigger forced re-consent for affected users via email; create separate read integration correctly |
| Voice profile poisoned by auto-replies | MEDIUM | Delete `EmailVoiceProfile` row; re-run voice profile init with corrected filter; requires one LLM call per user |
| Email body in logs (GDPR incident) | HIGH | Identify affected log entries; purge from logging system; assess retention period; notify DPA if required under GDPR Article 33; patch log redaction before re-deploy |
| Cross-tenant context leakage in LLM | HIGH | Audit all skill_runs from affected time window; identify which tenants could have been exposed; notify affected users per GDPR; patch session isolation; regression test |
| Score fatigue / adoption loss | MEDIUM | Reset user's notification preferences to default (conservative); adjust scoring thresholds downward for that user; offer manual calibration mode |
| Draft approval of wrong reply | LOW | User can recall/correct manually; no automated recovery; improve draft quality via voice profile re-init |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| historyId expiry without full-sync fallback | Phase 1: Gmail Read Service | Integration test: invalidate stored historyId; verify full sync runs on next cycle |
| OAuth scope expansion breaks existing users | Phase 1: Gmail OAuth Integration | Code review: grep for any modification to `google_gmail.py` SCOPES list |
| Polling wall at 200+ users | Phase 1: Sync Worker | Load test: simulate 200 integrations; verify cycle completes in < 3 min |
| Tenant context leakage | Phase 2: Email Scorer Skill | Cross-tenant isolation test: two tenants, verify no context bleed in SkillRun prompts |
| Voice profile poisoned by auto-replies | Phase 2: Voice Profile Init | Unit test: feed known auto-reply corpus; verify all filtered; check samples_analyzed count |
| Email body in error logs | Phase 1: Gmail Read Service | Log audit: run MIME error scenario; grep logs for email content strings |
| On-demand body fetch auth failure | Phase 3: Email Drafter + Phase 4: Review API | Integration test: revoke token; attempt body fetch; verify structured error + snippet fallback |
| Score at message level vs thread display | Phase 2: Scorer + Phase 4: API | Edge case test: thread where first email is low priority, reply is high priority; verify thread shows high priority |
| Notification fatigue | Phase 4: Review UI | Dogfood with real inbox for 1 week before release; count P1 alerts surfaced vs. genuinely urgent |
| Draft body retained after send | Phase 3: Email Drafter | DB audit: verify `body IS NULL` for all `status=sent` rows |
| LLM cost at scale | Phase 2: Scorer | Cost test: score 100 emails; verify < $0.10 per user per day at current token rates |

---

## Sources

- Gmail API Sync documentation: [Synchronize clients with Gmail](https://developers.google.com/workspace/gmail/api/guides/sync) — historyId availability window, 404 error behavior
- Gmail API Quota documentation: [Usage limits](https://developers.google.com/workspace/gmail/api/reference/quota) — per-user 15,000 units/minute, per-project 1,200,000 units/minute
- Gmail API Scopes: [Choose Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) — restricted scope classification for `gmail.readonly`
- Google OAuth Restricted Scope Verification: [Restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification) — verification timeline and requirements
- OAuth invalid_grant: [Google OAuth invalid grant](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked) — token revocation causes including scope mismatch
- Multi-tenant LLM leakage: [Cross Session Leak detection](https://www.giskard.ai/knowledge/cross-session-leak-when-your-ai-assistant-becomes-a-data-breach) — cross-tenant data exposure in AI systems
- Multi-tenant LLM security: [Burn-After-Use architecture](https://arxiv.org/abs/2601.06627) — preventing data leakage in enterprise LLM systems
- PII in logs: [PII in Logs is a GDPR Time Bomb](https://dev.to/polliog/pii-in-your-logs-is-a-gdpr-time-bomb-heres-how-to-defuse-it-307l) — practical log sanitization strategies
- Gmail Pub/Sub watch expiry: [gmailpush library](https://github.com/byeokim/gmailpush), [openclaw watch renewal issue](https://github.com/openclaw/openclaw/issues/24765) — silent failure on watch expiry
- Gmail API performance: [Performance Tips](https://developers.google.com/workspace/gmail/api/guides/performance) — batching, metadata-only fetches
- Trust erosion in AI email: [AI transparency kills trust](https://www.nobodycaresaboutethics.com/blog/ai-disclosure-trust-research), [Workplace email AI trust study](https://completeaitraining.com/news/why-relying-on-ai-for-workplace-emails-can-erode-trust-between-managers-and-employees/)
- HTML email XSS: [HTML Injection in email](https://github.com/eladnava/mailgen/security/advisories/GHSA-xw6r-chmh-vpmj), OWASP XSS Prevention Cheat Sheet
- Codebase inspection: `backend/src/flywheel/services/calendar_sync.py`, `google_gmail.py`, `email_dispatch.py` — existing patterns being extended

---

*Pitfalls research for: AI Email Copilot added to Flywheel V2 multi-tenant SaaS*
*Researched: 2026-03-24*
