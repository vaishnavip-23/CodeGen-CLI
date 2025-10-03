"""Python execution tool for CodeGen CLI.

Allows running Python scripts within the workspace while providing
optional stdin data. Useful for quickly verifying behavior of helper
scripts that rely on interactive input.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, Iterable, Optional

WORKSPACE = os.getcwd()


def _is_safe_path(path: str) -> bool:
    try:
        abs_path = os.path.abspath(os.path.join(WORKSPACE, path))
        return os.path.commonpath([WORKSPACE, abs_path]) == WORKSPACE
    except (ValueError, OSError):
        return False


def _format_input(data: Optional[Any] = None) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, str):
        return data if data.endswith("\n") else data + "\n"
    if isinstance(data, Iterable):
        parts = []
        for item in data:
            if item is None:
                continue
            text = str(item)
            parts.append(text if text.endswith("\n") else text + "\n")
        return "".join(parts) if parts else None
    return str(data)


def call(
    script_path: str,
    *args: str,
    python_executable: Optional[str] = None,
    stdin: Optional[Any] = None,
    inputs: Optional[Iterable[Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Run a Python script, optionally providing stdin data.

    Args:
        script_path: Relative path to the Python script.
        *args: Additional positional arguments passed to the script.
        python_executable: Override Python executable (defaults to sys.executable).
        stdin: Raw stdin data (string or iterable) passed to the script.
        inputs: Convenience iterable of input lines appended to stdin.
        timeout: Execution timeout in seconds.

    Returns:
        Dict with keys success, output, stderr, returncode.
    """

    if not script_path:
        return {
            "tool": "python_run",
            "success": False,
            "output": "Script path is required.",
        }

    if not _is_safe_path(script_path):
        return {
            "tool": "python_run",
            "success": False,
            "output": "Access denied: script must be inside the workspace.",
        }

    abs_path = os.path.abspath(os.path.join(WORKSPACE, script_path))
    if not os.path.exists(abs_path):
        return {
            "tool": "python_run",
            "success": False,
            "output": f"Script not found: {script_path}",
        }

    if os.path.isdir(abs_path):
        return {
            "tool": "python_run",
            "success": False,
            "output": f"'{script_path}' is a directory, expected a file.",
        }

    if python_executable is None:
        python_executable = os.environ.get("PYTHON_EXEC", "python")

    combined_input = _format_input(stdin)
    supplemental = _format_input(inputs)
    if supplemental:
        combined_input = (combined_input or "") + supplemental

    cmd = [python_executable, abs_path]
    if args:
        cmd.extend(args)

    try:
        completed = subprocess.run(
            cmd,
            input=combined_input,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "tool": "python_run",
            "success": False,
            "output": "Execution timed out.",
            "stderr": exc.stdout if exc.stdout else "",
            "returncode": None,
        }
    except FileNotFoundError:
        return {
            "tool": "python_run",
            "success": False,
            "output": f"Python executable not found: {python_executable}",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "tool": "python_run",
            "success": False,
            "output": f"Execution failed: {exc}",
        }

    return {
        "tool": "python_run",
        "success": completed.returncode == 0,
        "output": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
    }
