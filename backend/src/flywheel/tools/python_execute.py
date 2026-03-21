"""Python subprocess sandbox for skill execution.

Runs user-provided Python code in an isolated subprocess with:
- 30-second timeout (subprocess.run timeout + RLIMIT_CPU)
- 256MB memory limit (RLIMIT_AS)
- Cleared environment variables (no API keys, no DATABASE_URL)
- Temporary directory isolation (cwd set to temp dir)
- asyncio.to_thread wrapping (non-blocking for async event loop)

SECURITY NOTES:
- This is NOT a true sandbox. It prevents casual credential leakage
  and resource exhaustion for trusted early users.
- Full Docker sandboxing deferred to backlog item "Python Sandbox Hardening".
- On macOS (current deployment), /proc doesn't exist, so env clearing
  is sufficient to prevent credential discovery.
- For future Linux deployment, consider cgroups or Docker containers.

Handler:
    handle_python_execute(tool_input, context) -> str
"""

from __future__ import annotations

import asyncio
import resource
import subprocess
import tempfile
from pathlib import Path

from flywheel.tools.registry import RunContext


def _set_limits() -> None:
    """Set resource limits for the child subprocess.

    Called as preexec_fn in subprocess.run() -- runs in the child
    process before exec. Must be a regular function (not async).

    Note: RLIMIT_AS is not supported on macOS ARM64 (Apple Silicon).
    We attempt to set it but gracefully skip if the platform doesn't support it.
    RLIMIT_CPU is supported on all POSIX platforms.
    """
    # 256MB virtual memory limit (may not be available on macOS ARM64)
    mem_limit = 256 * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    except (ValueError, OSError):
        # macOS ARM64 doesn't support RLIMIT_AS -- skip gracefully.
        # The 30s timeout + env clearing still provide adequate protection.
        pass

    # 30 second CPU time limit (supported on all POSIX platforms)
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))


_CLEAN_ENV: dict[str, str] = {
    "PATH": "/usr/bin:/usr/local/bin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
}
"""Minimal environment for subprocess execution.

REPLACES (not extends) the parent environment. No API keys,
no DATABASE_URL, no encryption keys leak to the child process.
"""


_MAX_OUTPUT_CHARS = 10_000


async def handle_python_execute(tool_input: dict, context: RunContext) -> str:
    """Execute Python code in a sandboxed subprocess.

    Args:
        tool_input: {"code": "print('hello')"}
        context: RunContext (used for future audit logging)

    Returns:
        Combined stdout + stderr output, or error string. Never raises.
    """
    try:
        code = tool_input.get("code")
        if not code:
            return "Error: code is required"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to script file
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(code, encoding="utf-8")

            # Build clean env with temp dir paths
            clean_env = dict(_CLEAN_ENV)
            clean_env["HOME"] = tmpdir
            clean_env["TMPDIR"] = tmpdir

            # Run in thread to avoid blocking the async event loop
            result = await asyncio.to_thread(
                subprocess.run,
                ["python3", "script.py"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
                env=clean_env,
                preexec_fn=_set_limits,
            )

            # Collect output
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(result.stderr)
            if result.returncode != 0:
                output_parts.append(f"[exit code: {result.returncode}]")

            output = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate if too long
            if len(output) > _MAX_OUTPUT_CHARS:
                output = output[:_MAX_OUTPUT_CHARS] + "\n[Output truncated]"

            return output

    except subprocess.TimeoutExpired:
        return "Execution timed out (30 second limit)"
    except Exception as e:
        return f"Execution error: {e}"
