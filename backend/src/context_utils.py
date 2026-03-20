"""Compatibility shim: makes `import context_utils` resolve to flywheel.context_utils.

This allows v1 test code (and multiprocessing subprocesses) to use
`import context_utils` when backend/src/ is on sys.path.

The trick: we replace THIS module in sys.modules with the real one,
so `import context_utils` and `import flywheel.context_utils` return
the exact same module object. Attribute mutations (like setting
CONTEXT_ROOT in tests) are shared.
"""

import sys
from pathlib import Path

# Ensure flywheel package is importable (needed for multiprocessing subprocesses)
_src_dir = str(Path(__file__).resolve().parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import flywheel.context_utils as _real  # noqa: E402

# Replace this shim module with the real one
sys.modules[__name__] = _real
