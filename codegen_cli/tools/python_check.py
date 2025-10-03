"""Python syntax checker for CodeGen CLI."""

from __future__ import annotations

import os
import py_compile
import traceback
from typing import Any, Dict

WORKSPACE = os.getcwd()


def _resolve_path(path: str) -> str:
    candidate = os.path.join(WORKSPACE, path)
    return os.path.abspath(candidate)


def call(path: str, *args, **kwargs) -> Dict[str, Any]:
    if not path:
        return {
            "tool": "python_check",
            "success": False,
            "output": "Path to a python file is required.",
        }

    abs_path = _resolve_path(path)
    if not abs_path.endswith(".py"):
        return {
            "tool": "python_check",
            "success": False,
            "output": f"'{path}' is not a .py file.",
        }

    if not os.path.exists(abs_path):
        return {
            "tool": "python_check",
            "success": False,
            "output": f"Path '{path}' does not exist.",
        }

    try:
        py_compile.compile(abs_path, doraise=True)
        return {
            "tool": "python_check",
            "success": True,
            "output": "Syntax OK",
        }
    except py_compile.PyCompileError as exc:  # pragma: no cover - runtime dependent
        return {
            "tool": "python_check",
            "success": False,
            "output": "Syntax error detected.",
            "error": str(exc),
            "details": exc.msg if hasattr(exc, "msg") else None,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "tool": "python_check",
            "success": False,
            "output": f"Unexpected error: {exc}",
            "traceback": traceback.format_exc(),
        }
