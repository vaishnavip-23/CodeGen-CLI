"""
call_tools.py - dispatches tool steps to tools/*.py modules.

Features:
- Robust safe-calling of tool.call(...) with several fallbacks to avoid TypeError
  when tools have slightly different function signatures.
- Read -> Glob retry: if Read reports "File not found", try Glob("**/<name>") and
  retry Read with the first match.
- Write safeguard: if Write targets an existing file and kwargs.force is not True,
  refuse and return a helpful message recommending Edit/MultiEdit.
- Simple, clear outputs: each result is a dict {"tool": ..., "success": bool, "output": ...}
"""

import importlib
import traceback
from typing import Any, Dict

def _load_tool_module(name: str):
    """
    Import a module from tools.<name> (case-insensitive fallback).
    Raises RuntimeError if not found.
    """
    try:
        module = importlib.import_module(f"tools.{name}")
    except ModuleNotFoundError:
        try:
            module = importlib.import_module(f"tools.{name.lower()}")
        except Exception as e:
            raise RuntimeError(f"Tool '{name}' not found.") from e
    return module

def _call_module_func_safe(module, args, kwargs):
    """
    Try calling module.call with several fallback signatures to tolerate
    differing tool implementations.

    Trying order:
      1. module.call(*args, **kwargs)
      2. module.call(*args)
      3. module.call(**kwargs)
      4. module.call(args)  # single list arg
      5. module.call()
    If all fail, re-raise the last exception.
    """
    last_exc = None
    # 1) normal call
    try:
        return module.call(*args, **(kwargs or {}))
    except TypeError as e:
        last_exc = e
    except Exception:
        # runtime error inside tool should propagate
        raise

    # 2) try positional only
    try:
        return module.call(*args)
    except Exception as e:
        last_exc = e

    # 3) try kwargs only
    try:
        return module.call(**(kwargs or {}))
    except Exception as e:
        last_exc = e

    # 4) try passing args as single list
    try:
        return module.call(args)
    except Exception as e:
        last_exc = e

    # 5) try no-arg call
    try:
        return module.call()
    except Exception as e:
        last_exc = e

    # if we get here, re-raise the last exception
    raise last_exc

def _exec_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single step dict:
      {"tool": "read", "args": [...], "kwargs": {...}}
    Returns:
      {"tool": tool, "success": True/False, "output": ...}
    """
    if not isinstance(step, dict) or "tool" not in step:
        return {"tool": "<unknown>", "success": False, "output": "Unsupported step format."}

    tool = step["tool"]
    args = step.get("args", []) or []
    kwargs = step.get("kwargs", {}) or {}

    # Safety: prevent accidental overwrites via Write without force
    if tool.lower() == "write":
        target = args[0] if len(args) >= 1 else None
        force_flag = False
        if isinstance(kwargs, dict):
            force_flag = bool(kwargs.get("force", False))
        if target:
            try:
                import os
                from pathlib import Path
                p = Path(target)
                if not p.is_absolute():
                    p = Path().resolve() / p
                if p.exists() and not force_flag:
                    return {
                        "tool": "Write",
                        "success": False,
                        "output": (
                            f"File exists: {str(p)}. Prefer using Edit or MultiEdit to change an existing file. "
                            "If you intend to overwrite, call Write with kwargs={'force': True}."
                        )
                    }
            except Exception:
                # if checking filesystem fails for any reason, continue (tool will decide)
                pass

    try:
        module = _load_tool_module(tool)
    except Exception as e:
        return {"tool": tool, "success": False, "output": f"Tool load error: {e}"}

    if not hasattr(module, "call"):
        return {"tool": tool, "success": False, "output": f"Tool '{tool}' missing call(...) function."}

    try:
        raw_res = _call_module_func_safe(module, args, kwargs)
        # Normalize returned result into expected dict form
        if isinstance(raw_res, dict):
            raw_res.setdefault("tool", tool)
            return raw_res
        return {"tool": tool, "success": True, "output": raw_res}
    except Exception:
        tb = traceback.format_exc()
        return {"tool": tool, "success": False, "output": f"Exception while running tool '{tool}': {tb}"}

def _try_read_then_glob_and_retry(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to execute a Read step, and if it reports "File not found",
    try Glob("**/<query>") then retry Read with the first match.
    """
    res = _exec_step(step)
    try:
        out = res.get("output", "")
        if res.get("success") is False and isinstance(out, str) and "File not found" in out:
            # attempt glob
            try:
                glob_mod = _load_tool_module("glob")
            except Exception:
                return res
            args = step.get("args", [])
            if not args:
                return res
            query = args[0]
            try:
                glob_res = _call_module_func_safe(glob_mod, [f"**/{query}"], {})
            except Exception:
                return res
            if not isinstance(glob_res, dict):
                return res
            matches = glob_res.get("output", [])
            if not matches:
                return res
            first = matches[0]
            try:
                read_mod = _load_tool_module("read")
            except Exception:
                return res
            try:
                retry_res = _call_module_func_safe(read_mod, [first], {})
            except Exception:
                return res
            if isinstance(retry_res, dict):
                retry_res.setdefault("tool", "read")
                retry_res.setdefault("note", f"Read retried using glob match: {first}")
                return retry_res
            return {"tool": "read", "success": True, "output": retry_res}
        else:
            return res
    except Exception:
        return res

def dispatch_tool(payload: Any) -> Any:
    """
    Dispatch payload to tools.

    Acceptable shapes:
      - {"steps": [ step1, step2, ... ]}
      - single step dict: {"tool":"read", "args":[...], "kwargs":{...}}
      - a list of step dicts

    Returns:
      - list of result dicts for multi-step payloads
      - single result dict for single-step payload
    """
    # Multi-step plan
    if isinstance(payload, dict) and "steps" in payload and isinstance(payload["steps"], list):
        results = []
        for s in payload["steps"]:
            if isinstance(s, dict) and s.get("tool", "").lower() == "read":
                results.append(_try_read_then_glob_and_retry(s))
            else:
                results.append(_exec_step(s))
        return results

    # Single-step dict
    if isinstance(payload, dict) and "tool" in payload:
        if payload.get("tool", "").lower() == "read":
            return _try_read_then_glob_and_retry(payload)
        return _exec_step(payload)

    # List of steps
    if isinstance(payload, list):
        results = []
        for s in payload:
            if isinstance(s, dict) and s.get("tool", "").lower() == "read":
                results.append(_try_read_then_glob_and_retry(s))
            else:
                results.append(_exec_step(s))
        return results

    return {"tool": "<unknown>", "success": False, "output": "Unsupported payload for dispatch_tool."}
