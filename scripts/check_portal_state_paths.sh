#!/usr/bin/env bash
# check_portal_state_paths.sh - CI grep-guard for broker portal state paths (Phase 149)
#
# Enforces MIGRATE-03: every portal script's Playwright profile state must resolve
# from Path.home(), never __file__-relative or expanduser("~/.claude").
#
# SCOPED to state/profile patterns ONLY. Config-file loading via
# Path(__file__).parent / "<something>.yaml" is EXEMPT because bundled config
# is a sibling asset of the code (Phase 150 extracts both into the same temp dir),
# not runtime state.
#
# Exit 0 on clean, 1 on violation.

set -euo pipefail

PORTALS_DIR="${1:-skills/broker/portals}"

if [ ! -d "$PORTALS_DIR" ]; then
  echo "ERROR: portals directory not found: $PORTALS_DIR" >&2
  exit 2
fi

FAIL=0

# Forbidden pattern 1: expanduser against ~/.claude — legacy skill-root hack
if grep -rnE 'expanduser\(\s*["'\'']~/\.claude' "$PORTALS_DIR" --include='*.py'; then
  echo "" >&2
  echo "ERROR: portal script uses expanduser(\"~/.claude/...\") — forbidden after MIGRATE-03." >&2
  echo "  Fix: state must resolve from Path.home() / \".flywheel\" / \"broker\" / \"portals\" / \"<carrier>\"" >&2
  FAIL=1
fi

# Forbidden pattern 2: user_data_dir combined with __file__ (state path should NEVER be __file__-relative)
if grep -rnE 'user_data_dir\s*=.*__file__|state_path\s*=.*__file__|_playwright_state' "$PORTALS_DIR" --include='*.py'; then
  echo "" >&2
  echo "ERROR: portal script uses __file__-relative state path — forbidden after MIGRATE-03." >&2
  echo "  Fix: declare STATE_DIR = Path.home() / \".flywheel\" / \"broker\" / \"portals\" / \"<carrier>\"" >&2
  FAIL=1
fi

# Forbidden pattern 3: sys.path.insert into ~/.claude (bundle extraction will fail in Phase 150)
if grep -rnE 'sys\.path\.insert.*\.claude' "$PORTALS_DIR" --include='*.py'; then
  echo "" >&2
  echo "ERROR: portal script hand-rolls sys.path.insert into ~/.claude — forbidden after MIGRATE-03." >&2
  echo "  Fix: remove; Phase 150's fetch-helper puts the bundle root on sys.path." >&2
  FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "check_portal_state_paths.sh: OK (scanned $PORTALS_DIR)"
fi

exit $FAIL
