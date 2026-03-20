"""Launch Flywheel web app with an isolated copy of the context store.

Usage:
    python3 src/run_test.py

This script:
1. Copies ~/.claude/context/ to /tmp/flywheel-test/context/ (read-only snapshot)
2. Copies ~/.claude/users/ to /tmp/flywheel-test/users/ (if exists)
3. Patches CONTEXT_ROOT and USERS_ROOT in all modules to use the temp copy
4. Starts uvicorn on port 8000

Your real context store is NEVER touched. Delete /tmp/flywheel-test/ when done.
"""

import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 0. Load .env file (for ANTHROPIC_API_KEY, etc.)
# ---------------------------------------------------------------------------

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _val = _val.strip().strip('"').strip("'")
                os.environ.setdefault(_key.strip(), _val)

# ---------------------------------------------------------------------------
# 1. Create isolated test environment
# ---------------------------------------------------------------------------

TEST_ROOT = Path("/tmp/flywheel-test")
TEST_CONTEXT = TEST_ROOT / "context"
TEST_USERS = TEST_ROOT / "users"
TEST_LOGS = TEST_ROOT / "logs"

REAL_CONTEXT = Path.home() / ".claude" / "context"
REAL_USERS = Path.home() / ".claude" / "users"

def setup_test_env():
    """Copy real data to isolated temp directory."""
    # Clean previous test run
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)

    # Copy context store
    if REAL_CONTEXT.exists():
        shutil.copytree(REAL_CONTEXT, TEST_CONTEXT)
        print(f"  Copied context store ({sum(1 for f in TEST_CONTEXT.iterdir())} files)")
    else:
        TEST_CONTEXT.mkdir(parents=True)
        print("  Created empty context store")

    # Copy users directory
    if REAL_USERS.exists():
        shutil.copytree(REAL_USERS, TEST_USERS)
        print(f"  Copied users directory")
    else:
        TEST_USERS.mkdir(parents=True)
        print("  Created empty users directory")

    # Create logs directory
    TEST_LOGS.mkdir(parents=True, exist_ok=True)

    print(f"  Test root: {TEST_ROOT}")


# ---------------------------------------------------------------------------
# 2. Patch all modules to use test paths
# ---------------------------------------------------------------------------

def patch_modules():
    """Override CONTEXT_ROOT and USERS_ROOT in all flywheel modules."""
    # Add src/ to path
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # Patch context_utils
    import context_utils
    context_utils.CONTEXT_ROOT = TEST_CONTEXT
    print(f"  context_utils.CONTEXT_ROOT -> {TEST_CONTEXT}")

    # Patch user_memory (if available)
    try:
        import user_memory
        user_memory.USERS_ROOT = TEST_USERS
        print(f"  user_memory.USERS_ROOT -> {TEST_USERS}")
    except ImportError:
        pass

    # Patch work_items (if available)
    try:
        import work_items
        work_items.WORK_ITEMS_ROOT = TEST_USERS
        print(f"  work_items.WORK_ITEMS_ROOT -> {TEST_USERS}")
    except ImportError:
        pass

    # Patch token_logger (if available)
    try:
        import token_logger
        token_logger.LOG_DIR = TEST_LOGS
        print(f"  token_logger.LOG_DIR -> {TEST_LOGS}")
    except ImportError:
        pass

    # Patch scheduler (if available)
    try:
        import scheduler
        scheduler.SCHEDULES_ROOT = TEST_USERS
        print(f"  scheduler.SCHEDULES_ROOT -> {TEST_USERS}")
    except ImportError:
        pass

    # Patch skill_runner_web (if available)
    try:
        import skill_runner_web
        skill_runner_web.OUTPUTS_ROOT = TEST_USERS
        print(f"  skill_runner_web.OUTPUTS_ROOT -> {TEST_USERS}")
    except ImportError:
        pass

    # Patch background_runner (if available)
    try:
        import background_runner
        background_runner.WORK_ITEMS_ROOT = TEST_USERS
        print(f"  background_runner.WORK_ITEMS_ROOT -> {TEST_USERS}")
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# 3. Launch
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n🧪 Flywheel Test Mode")
    print("=" * 50)
    print("\n Setting up isolated environment...")
    setup_test_env()

    print("\n Patching modules...")
    patch_modules()

    print(f"\n Your real data at ~/.claude/context/ is UNTOUCHED.")
    print(f" All writes go to {TEST_ROOT}/")
    print(f"\n Starting server on http://localhost:8000")
    print("=" * 50 + "\n")

    import uvicorn
    from web_app import app
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
