"""Test configuration for flywheel v2 backend.

Sets up sys.path and module aliasing so v1 tests work unchanged.
The v1 tests use `import context_utils` directly, but in v2 the module
lives at `flywheel.context_utils`. We add a sys.modules alias so both
import paths resolve to the same module.
"""

import os
import sys

# Ensure FLYWHEEL_BACKEND is set to flatfile for tests
os.environ.setdefault("FLYWHEEL_BACKEND", "flatfile")

# Add the flywheel package's parent to sys.path so `import flywheel` works
_src_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(_src_dir))

# Import the real module and alias it so `import context_utils` works
import flywheel.context_utils  # noqa: E402

sys.modules["context_utils"] = flywheel.context_utils
