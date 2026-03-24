# Stack Research

**Domain:** Email Copilot — Gmail sync, scoring, drafting, review UI
**Researched:** 2026-03-24
**Confidence:** HIGH (backend), MEDIUM (frontend components)

---

## Context: What Already Exists (Do Not Re-add)

The following are already in `pyproject.toml` or `package.json` and serve the Email Copilot directly:

| Existing Dependency | Email Copilot Use |
|---------------------|-------------------|
| `google-api-python-client>=2.150` | Gmail API calls (already imported in `google_gmail.py`) |
| `google-auth-oauthlib>=1.2` | OAuth flow for Gmail (already in use) |
| `google-auth-httplib2>=0.2` | Transport layer for Google auth |
| `html2text>=2024.2.26` | HTML-to-text (already installed, usable for email bodies) |
| `beautifulsoup4>=4.12` | HTML parsing (already installed) |
| `anthropic>=0.86.0` | LLM calls for scoring + drafting (skill executor pattern) |
| `cryptography>=46.0.5` | AES-256-GCM credential encryption (already used for Gmail creds) |
| `@tanstack/react-query` v5 | API state management for review UI |
| `zustand` v5 | Client state (draft approvals, filter state) |
| `lucide-react` | Icons for email UI |
| `dompurify` | Sanitize email HTML bodies when rendering on-demand fetches |
| `tailwindcss` v4, `shadcn` | Existing component system for review UI |

---

## New Backend Dependencies

### Core — Gmail Read Capabilities

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `google-api-python-client` | `>=2.193` (bump from `>=2.150`) | Gmail `messages.list`, `messages.get`, `history.list`, `users.watch` | Already installed; bump version constraint to get `history.list` incremental sync fixes from 2.160+. The single library handles all Gmail API surface. No separate package needed. |

**No new Gmail library needed.** `google-api-python-client` already provides the full Gmail API surface including `users().messages().list()`, `users().messages().get()`, `users().history().list()`, and `users().watch()`. The existing `google_gmail.py` uses `build("gmail", "v1", credentials=creds)` and `asyncio.to_thread` — this exact pattern scales to read/list/fetch. Confidence: HIGH (official Google docs).

### Email Parsing

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `markdownify` | `>=1.2.2` | HTML email body → clean text for LLM context | Better than `html2text` for email HTML: handles nested structures, `<blockquote>` chains, inline styles, and forwarded-message trees more cleanly. BeautifulSoup4 backend means it handles malformed email HTML gracefully. Used only during on-demand body fetch for drafting — not for stored data. |

**For MIME parsing: use Python stdlib `email` module.** Gmail API returns message bodies as base64url-encoded strings — no external MIME library needed. The stdlib `email.message_from_bytes()` + `email.policy.default` handles multipart MIME, charset decoding, and part extraction reliably. `beautifulsoup4` (already installed) handles HTML part cleanup. Confidence: HIGH (Python docs, official Gmail API docs).

**Do NOT add:** `mailparser`, `imaplib`, `imapclient` — Gmail API returns pre-parsed payloads in JSON format with `parts[]` array. Raw IMAP/MIME parsing libraries are for IMAP connections, not Gmail API. Confidence: HIGH.

### Voice Profile Learning (NLP)

**Recommendation: Use Claude (already installed) as the NLP engine for voice extraction, not spaCy or NLTK.**

Rationale: Voice profile extraction requires understanding semantic patterns ("this person writes formally, uses 'Let me know if...' closings, averages 3 paragraphs"). This is a language understanding task, not a feature extraction task. Claude haiku (cheap, fast) extracting structured `EmailVoiceProfile` JSON from a batch of sent emails outperforms any statistical NLP library for this use case. The skill executor pattern (already built) makes this a natural fit.

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `anthropic` | `>=0.86.0` (already installed) | Voice profile extraction from sent emails | Prompt `claude-haiku-4-5` with 10-20 sent email samples → structured `{tone, avg_length, phrases[], sign_off}` JSON. Costs ~$0.001 per profile build. Re-run when 50+ new sent emails accumulate. |

**Do NOT add:** `spacy`, `nltk`, `transformers`, `sentence-transformers` — heavyweight installs, require model downloads, add 500MB+ to container. Claude API already present; use it. spaCy is appropriate for entity extraction at scale, but the context store already handles entity extraction via the existing entity extraction pipeline. Confidence: MEDIUM (training data supports this; Claude's structured output capability is HIGH confidence from official docs).

### Sync Architecture

No new infrastructure libraries needed for Phase 1 (polling). The `calendar_sync.py` pattern using `asyncio` + SQLAlchemy + background worker is the correct template.

For Phase 5+ only (Gmail push notifications — NOT needed for MVP):

| Library | Version | Purpose | Condition |
|---------|---------|---------|-----------|
| `google-cloud-pubsub` | `>=2.34` | Receive Gmail `users.watch()` push notifications via Pub/Sub | Only add if polling latency becomes a user-visible problem. Adds GCP Pub/Sub dependency, requires public webhook endpoint, watch renewals every 7 days. Premature for MVP. |

**Decision: Poll, don't push.** 5-minute polling matches `calendar_sync.py` pattern, requires zero new infrastructure, and is sufficient for the trust-earning MVP phase. Gmail's `history.list` with `startHistoryId` makes incremental polling efficient — only changed messages are fetched, not full mailbox scans. Confidence: HIGH (Gmail API docs on `history.list`).

---

## New Frontend Dependencies

### Core Review UI

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@tanstack/react-virtual` | `^3.13.23` | Virtualized email thread list | A user with 1,000 emails in their inbox cannot render 1,000 DOM nodes. `@tanstack/react-virtual` (same TanStack family as already-installed `react-query`) renders only visible items. Headless, integrates cleanly with existing Tailwind layout. Not needed for draft queue (typically <20 items) but essential for thread list. |

**Do NOT add:** `react-virtualized` (archived, unmaintained), `react-window` (lighter but less maintained, TanStack Virtual supersedes it). Confidence: HIGH (npm, TanStack official docs, confirmed current version 3.13.23 as of March 2026).

### Email Body Rendering

No new library needed. `dompurify` (already installed) sanitizes on-demand fetched HTML bodies before rendering via `dangerouslySetInnerHTML`. This is the only safe approach for rendering external email HTML in React.

**Pattern:**
```tsx
// Sanitize fetched email HTML before rendering
const clean = DOMPurify.sanitize(emailBody, { USE_PROFILES: { html: true } });
<div dangerouslySetInnerHTML={{ __html: clean }} className="prose prose-sm" />
```

Requires `@tailwindcss/typography` for `prose` classes — see below.

### Typography for Email Body Rendering

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@tailwindcss/typography` | `^0.5.15` | `prose` class for email body rendering | Email bodies rendered as HTML need opinionated typographic defaults (paragraph spacing, list styles, link colors). The `prose` class handles this correctly without hand-rolling CSS for all possible email HTML structures. |

**Install as dev dependency** (Tailwind plugin, build-time only after Tailwind v4 migration). Confidence: MEDIUM (Tailwind v4 plugin API changed; verify plugin integration with `@tailwindcss/vite` during implementation).

---

## Installation

```bash
# Backend — bump version constraint in pyproject.toml
# google-api-python-client is already present; update constraint:
# "google-api-python-client>=2.193"

# Add markdownify
uv add markdownify

# Frontend
npm install @tanstack/react-virtual
npm install -D @tailwindcss/typography
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `markdownify` for HTML→text | `html2text` (already installed) | `html2text` is already present and usable as a fallback, but produces noisier output on email HTML with inline styles, `<blockquote>` nesting, and email signatures. Use `markdownify` as primary, `html2text` as fallback if parse fails. |
| Claude for voice extraction | `spacy` + statistical NLP | spaCy requires model download (50-500MB), is better for entity/POS tasks than style understanding. Claude already present, cheaper to operate, and semantically richer for style characterization. |
| Polling (`history.list`) for sync | Gmail Pub/Sub push | Push requires GCP Pub/Sub setup, public webhook, 7-day watch renewals, and more failure modes. Polling is simpler, proven by `calendar_sync.py`, and sufficient for 5-minute freshness. |
| `@tanstack/react-virtual` | `react-window` | `react-window` is stable but has reduced maintenance activity. `@tanstack/react-virtual` is actively maintained, headless, and part of the already-adopted TanStack family. |
| Python stdlib `email` module for MIME | `mailparser`, `imaplib` | Gmail API returns JSON payloads with pre-parsed message parts. MIME libraries solve the wrong problem — they're for raw IMAP connections. |
| `dompurify` (already installed) for HTML sanitization | Custom HTML stripping | DOMPurify is the standard; re-implementing HTML sanitization introduces XSS risk. Already installed. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `aiogoogle` | Async wrapper around Google APIs — adds a dependency for a problem already solved by `asyncio.to_thread(build(...).execute)` | `google-api-python-client` + `asyncio.to_thread` (already established pattern in `google_gmail.py`) |
| `imaplib` / `imapclient` | Raw IMAP access — Gmail API returns structured JSON, IMAP is the wrong abstraction | `google-api-python-client` Gmail v1 API |
| `simplegmail` | Thin wrapper that hides API details and hasn't been updated to handle `history.list` properly | `google-api-python-client` directly |
| `spacy` / `nltk` / `transformers` | 100-500MB model downloads, K8s resource pressure, no better than Claude for this use case | Anthropic Claude haiku via existing `anthropic` client |
| Embedding-based email scoring | Requires a vector index, embedding model, and similarity search pipeline — high infrastructure cost | LLM scoring via skill executor using context store text search (already built) |
| Permanent raw email body storage | PII liability, GDPR exposure, unnecessary data duplication | Extract context entries, fetch body on-demand from Gmail API |
| `react-quill` / `draft-js` for draft editing | Full rich-text editors are overkill for email draft review; add 100KB+ to bundle | `<textarea>` with auto-resize (CSS) or `contenteditable` div — drafts are plain text |

---

## Scope Boundaries for Each Phase

| Phase | New Backend Libraries | New Frontend Libraries |
|-------|-----------------------|------------------------|
| Phase 1: Gmail Sync | `markdownify` (for voice learning pipeline) | None |
| Phase 2: Scoring | None (all scoring via existing `anthropic` + context store) | None |
| Phase 3: Drafting | None | None |
| Phase 4: Review UI | None | `@tanstack/react-virtual`, `@tailwindcss/typography` |
| Phase 5: Feedback | None | None |

Total new dependencies: **1 backend** (`markdownify`), **2 frontend** (`@tanstack/react-virtual`, `@tailwindcss/typography`).

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `google-api-python-client>=2.193` | Python 3.12, `google-auth>=2.x` | Already in venv. `history.list` has been stable since v2; bump just ensures latest quota handling fixes. |
| `markdownify>=1.2.2` | `beautifulsoup4>=4.12` (already installed) | No conflicts. Uses existing BS4 installation. |
| `@tanstack/react-virtual^3.13.23` | React 19 (already in use), `@tanstack/react-query` v5 | Same TanStack family; no version conflicts expected. |
| `@tailwindcss/typography^0.5.15` | Tailwind v4 (in use via `@tailwindcss/vite`) | Tailwind v4 changed the plugin API. **Verify** `@tailwindcss/typography` v0.5.x works with `@tailwindcss/vite` v4 during Phase 4 setup. May need `@tailwindcss/typography@next` if v4 plugin API requires it. Flag as needing implementation verification. |

---

## Gmail API Scope Changes Required

The existing `google_gmail.py` uses `gmail.send` scope only. Email Copilot requires:

```python
# Current (send-only)
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Required for Email Copilot
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",   # read/list/fetch
    "https://www.googleapis.com/auth/gmail.modify",     # label, mark read
]
```

**Architecture note:** Per the comment in `google_gmail.py`, Gmail and Calendar use SEPARATE Integration rows. The Email Copilot should create a NEW Gmail Read integration (separate from the existing Gmail Send integration) to avoid breaking existing `gmail.send` grants. Users who already connected Gmail for sending should not be forced to re-grant — the Email Copilot OAuth flow is a separate grant with broader scopes. This is an architectural decision, not a library decision, but it affects how the OAuth flow is implemented.

**Re-auth requirement:** Existing Gmail OAuth tokens with only `gmail.send` cannot be upgraded in-place. Users must perform a new OAuth consent flow for the expanded scopes. `prompt="consent"` and `access_type="offline"` (already set in the existing flow) ensure a new refresh token is issued.

---

## Sources

- [Google Gmail API — Method: users.messages.list](https://developers.google.com/workspace/gmail/api/guides/list-messages) — confirmed `messages.list`, `history.list` pagination patterns
- [Google Gmail API — Synchronize clients](https://developers.google.com/workspace/gmail/api/guides/sync) — confirmed `historyId` incremental sync approach, 404 full-re-sync handling
- [google-api-python-client PyPI](https://pypi.org/project/google-api-python-client/) — confirmed latest version 2.193.0, Python 3.12 support
- [markdownify PyPI](https://pypi.org/project/markdownify/) — confirmed version 1.2.2 (Nov 2025), BeautifulSoup4 dependency
- [Gmail API — Configure push notifications](https://developers.google.com/workspace/gmail/api/guides/push) — confirmed Pub/Sub push complexity, 7-day watch renewal requirement
- [@tanstack/react-virtual npm](https://www.npmjs.com/package/@tanstack/react-virtual) — confirmed version 3.13.23, React 19 support
- [Gmail API Usage Limits](https://developers.google.com/workspace/gmail/api/reference/quota) — confirmed 250 quota units/user/second burst limit
- [Google API Python client — async issue #1637](https://github.com/googleapis/google-api-python-client/issues/1637) — confirmed no native async support; `asyncio.to_thread` is the established workaround
- Python stdlib `email` module — standard library, no external source needed
- Anthropic API (existing dependency) — Claude haiku for voice extraction, same client used by skill executor

---
*Stack research for: Email Copilot milestone on Flywheel V2*
*Researched: 2026-03-24*
