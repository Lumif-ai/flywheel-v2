"""Locked user-facing error-message copy for Phase 151 resilience.

These strings are regression-tested. Changing them requires a phase note +
follow-up regression-test update. They are the sole source of truth for
user-facing stderr lines + ``BundleFetchError`` / ``BundleCacheError`` /
``BundleIntegrityError`` reason strings.

**Two invocation forms intentionally coexist** (see Phase 151 CONTEXT
§Error taxonomy locked table — do NOT normalize):

- **Underscored** ``flywheel_refresh_skills`` (MCP tool form, invoked from
  inside Claude Code) appears in ``ERR_404_TEMPLATE`` + ``ERR_503_TERMINAL``.
- **Hyphenated** ``flywheel refresh-skills`` (CLI subcommand form, invoked
  in a terminal) appears in ``ERR_CHECKSUM_TEMPLATE`` + ``ERR_OFFLINE_EXPIRED``.

Both are valid UX surface areas. The constants below MUST match CONTEXT
byte-for-byte; ``cli/tests/test_error_messages.py`` asserts byte-exact
equality against a hard-coded literal RHS (NOT the constant itself — that
would be a tautology that silently swallows drift).
"""

# 401: session expired — bundle fetch after one-shot refresh still returned 401.
ERR_401 = "Session expired. Run `flywheel login` and retry."

# 403: skill not in tenant's module license.
ERR_403 = "Skill not licensed for your tenant. Contact your admin."

# 404: {name} interpolated at raise site. Uses UNDERSCORED form
# (MCP-tool invocation — the user is inside Claude Code).
ERR_404_TEMPLATE = (
    "Skill not found: {name}. Check spelling or run `flywheel_refresh_skills`."
)

# 503: retry phase ({delay} interpolated at raise site). Stderr line emitted
# BEFORE the sleep on each retry attempt.
ERR_503_RETRY_TEMPLATE = "Flywheel backend unreachable. Retrying in {delay}s..."

# 503: terminal message after 3 failed attempts. Uses UNDERSCORED form
# (MCP-tool invocation — the user is inside Claude Code).
ERR_503_TERMINAL = (
    "Flywheel backend unreachable after 3 attempts. "
    "Retry in a moment or run `flywheel_refresh_skills` when online."
)

# Checksum mismatch: {skill} interpolated at raise site. Uses HYPHENATED form
# (CLI subcommand — checksum errors are typically surfaced during install /
# manual invocation where a terminal is at hand).
ERR_CHECKSUM_TEMPLATE = (
    "Bundle integrity check failed for {skill}. "
    "Run `flywheel refresh-skills` to re-fetch."
)

# Offline + expired cache: fail-closed. Uses HYPHENATED form
# (CLI subcommand — user is diagnosing a network issue from the terminal).
ERR_OFFLINE_EXPIRED = (
    "Cached bundle expired (>24h) and backend unreachable. "
    "Connect to network and retry, or run `flywheel refresh-skills` when online."
)

# Convenience list for parametrized regression tests. Order matches CONTEXT
# §Error taxonomy locked table top-to-bottom.
ALL_ERROR_MESSAGES = [
    ("401", ERR_401),
    ("403", ERR_403),
    ("404", ERR_404_TEMPLATE.format(name="broker-parse-contract")),
    ("503_retry", ERR_503_RETRY_TEMPLATE.format(delay=0.5)),
    ("503_terminal", ERR_503_TERMINAL),
    ("checksum", ERR_CHECKSUM_TEMPLATE.format(skill="broker-parse-contract")),
    ("offline_expired", ERR_OFFLINE_EXPIRED),
]

__all__ = [
    "ERR_401",
    "ERR_403",
    "ERR_404_TEMPLATE",
    "ERR_503_RETRY_TEMPLATE",
    "ERR_503_TERMINAL",
    "ERR_CHECKSUM_TEMPLATE",
    "ERR_OFFLINE_EXPIRED",
    "ALL_ERROR_MESSAGES",
]
