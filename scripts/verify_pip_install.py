#!/usr/bin/env python3
"""Verify that the built flywheel-ai wheel installs cleanly and exposes the
expected import surface for the router MCP migration (phase 152.1).

Usage:
    python3 scripts/verify_pip_install.py
    python3 scripts/verify_pip_install.py --wheel cli/dist/flywheel_ai-0.4.0-py3-none-any.whl

Checks (idempotent, safe to re-run):
  1. Wheel layout — required paths present, forbidden paths absent.
  2. Fresh venv install — uv creates a throwaway venv, installs the wheel.
  3. Import surface — flywheel.broker, portals, templates, CLI, MCP all importable.
  4. Resource access — broker portal YAML and router-SKILL.md reachable via
     importlib.resources.

Exits 0 on success, 1 on failure. Prints a clear PASS/FAIL banner.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WHEEL = REPO_ROOT / "cli" / "dist" / "flywheel_ai-0.4.0-py3-none-any.whl"

REQUIRED_WHEEL_PATHS = [
    "flywheel/broker/__init__.py",
    "flywheel/broker/api_client.py",
    "flywheel/broker/field_validator.py",
    "flywheel/broker/portals/__init__.py",
    "flywheel/broker/portals/base.py",
    "flywheel/broker/portals/mapfre.py",
    "flywheel/broker/portals/mapfre.yaml",
    "flywheel/broker/templates/router-SKILL.md",
    "flywheel_cli/main.py",
    "flywheel_mcp/server.py",
]

# Paths that MUST NOT be in the wheel.
# - top-level "broker/..." means packages config captured the wrong dir
# - "flywheel/__init__.py" would turn flywheel into a regular package and
#   break downstream namespace extensions
FORBIDDEN_WHEEL_PATHS = [
    "broker/",
    "flywheel/__init__.py",
]


class VerificationError(RuntimeError):
    """Raised when a verification step fails."""


def _log(msg: str) -> None:
    print(f"[verify] {msg}", flush=True)


def check_wheel_contents(wheel_path: Path) -> None:
    """Inspect the wheel archive and assert the layout is correct."""
    if not wheel_path.is_file():
        raise VerificationError(f"wheel not found: {wheel_path}")

    with zipfile.ZipFile(wheel_path) as zf:
        names = zf.namelist()

    missing = [p for p in REQUIRED_WHEEL_PATHS if p not in names]
    if missing:
        raise VerificationError(
            "wheel is missing required paths:\n  - " + "\n  - ".join(missing)
        )

    bad = []
    for forbidden in FORBIDDEN_WHEEL_PATHS:
        if forbidden.endswith("/"):
            hits = [n for n in names if n.startswith(forbidden)]
        else:
            hits = [n for n in names if n == forbidden]
        if hits:
            bad.extend(hits)
    if bad:
        raise VerificationError(
            "wheel contains forbidden paths:\n  - " + "\n  - ".join(bad)
        )

    _log(f"wheel layout OK ({len(names)} entries)")


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    _log("$ " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise VerificationError(
            f"command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}"
        )


def check_fresh_install(wheel_path: Path) -> None:
    """Install the wheel into a fresh uv-managed venv and exercise imports."""
    if shutil.which("uv") is None:
        raise VerificationError("uv is required but not on PATH")

    with tempfile.TemporaryDirectory(prefix="flywheel-verify-") as tmpdir:
        venv_dir = Path(tmpdir) / "venv"
        _run(["uv", "venv", str(venv_dir)])

        python_bin = venv_dir / "bin" / "python"
        if not python_bin.exists():
            # Windows fallback — not supported but guard anyway.
            python_bin = venv_dir / "Scripts" / "python.exe"

        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python_bin),
                str(wheel_path),
            ]
        )

        smoke_script = Path(tmpdir) / "smoke.py"
        smoke_script.write_text(
            dedent(
                """
                import sys
                import importlib
                import importlib.resources as pkg_resources

                failures = []

                def check(label, fn):
                    try:
                        fn()
                        print(f"  ok   {label}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"  FAIL {label}: {exc!r}")
                        failures.append(label)

                # 1. Core broker imports
                check(
                    "import flywheel.broker.api_client",
                    lambda: importlib.import_module("flywheel.broker.api_client"),
                )
                check(
                    "import flywheel.broker.field_validator",
                    lambda: importlib.import_module("flywheel.broker.field_validator"),
                )
                check(
                    "from flywheel.broker import api_client, field_validator",
                    lambda: __import__("flywheel.broker", fromlist=["api_client", "field_validator"]),
                )

                # 2. Portals import + data file access
                check(
                    "import flywheel.broker.portals.mapfre",
                    lambda: importlib.import_module("flywheel.broker.portals.mapfre"),
                )

                def _portal_yaml():
                    path = pkg_resources.files("flywheel.broker.portals").joinpath("mapfre.yaml")
                    assert path.is_file(), f"mapfre.yaml not found at {path}"

                check("resource: flywheel.broker.portals/mapfre.yaml", _portal_yaml)

                # 3. Template access
                def _router_skill():
                    path = pkg_resources.files("flywheel.broker.templates").joinpath("router-SKILL.md")
                    assert path.is_file(), f"router-SKILL.md not found at {path}"

                check("resource: flywheel.broker.templates/router-SKILL.md", _router_skill)

                # 4. CLI and MCP still importable
                check(
                    "from flywheel_cli.main import cli",
                    lambda: getattr(importlib.import_module("flywheel_cli.main"), "cli"),
                )
                check(
                    "from flywheel_mcp.server import main",
                    lambda: getattr(importlib.import_module("flywheel_mcp.server"), "main"),
                )

                if failures:
                    print(f"\\n{len(failures)} check(s) failed")
                    sys.exit(1)
                print("\\nall import checks passed")
                """
            ).strip()
            + "\n"
        )

        _run([str(python_bin), str(smoke_script)])
        _log("fresh-install import surface OK")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel",
        type=Path,
        default=DEFAULT_WHEEL,
        help=f"path to the wheel to verify (default: {DEFAULT_WHEEL})",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="only check wheel contents, do not create a venv or install",
    )
    args = parser.parse_args(argv)

    try:
        _log(f"verifying wheel: {args.wheel}")
        check_wheel_contents(args.wheel)
        if args.skip_install:
            _log("skipping fresh-install step (--skip-install)")
        else:
            check_fresh_install(args.wheel)
    except VerificationError as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1

    print("\nPASS: flywheel-ai wheel is publishable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
