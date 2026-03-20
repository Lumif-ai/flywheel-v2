#!/usr/bin/env python3
"""Recipe store CLI wrapper.

Delegates all recipe operations to the flywheel core recipe_store.py
via the engines/ symlink. This file is a thin proxy -- no logic here.

Usage:
    python3 recipe_utils.py lookup --domain linkedin.com --task search-people
    python3 recipe_utils.py list [--status active]
    python3 recipe_utils.py save --domain X --task Y --file recipe.yaml
    python3 recipe_utils.py log-visit --domain X --task Y
    python3 recipe_utils.py check-visits --domain X --task Y
    python3 recipe_utils.py check-staleness --domain X --task Y --count N --fill-rates '{...}'
    python3 recipe_utils.py update-verified --domain X --task Y
    python3 recipe_utils.py health
"""
import os
import sys

# Add the engines path (symlink to ~/Projects/flywheel/src/)
_engines_dir = os.path.join(os.path.dirname(__file__), "engines")
_engines_real = os.path.realpath(_engines_dir)
if _engines_real not in sys.path:
    sys.path.insert(0, _engines_real)

from recipe_store import _cli

if __name__ == "__main__":
    _cli()
