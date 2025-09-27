"""
call_tools.py - dispatches tool steps to tools/*.py modules.

Behavior:
- Robust safe-calling of tool.call(...) (tries several signatures).
- Read -> Glob retry: if Read reports "File not found", try Glob("**/<name>") and retry Read with the first match.
- Write safeguard: if Write targets an existing file and kwargs.force is not True, refuse and return a helpful message recommending Edit/MultiEdit.
- Always include the original 'args' and 'kwargs' in the returned result dict so output layers can render richer UI.
"""

import importlib
import traceback
from typing import Any, Dict

def _load_tool_module(name: str):
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
    Try calling module.call with several fallback signatures to tolerate differing tool implementations.

    Order tried:
      1. module.call(*args, **kwargs)
      2. module.call(*args)
      3. module.call(**kwargs)
      4. module.call(args)  # single list arg
      5. module.call()
    """
    last_exc = None
    try:
        return module.call(*args, **(kwargs or {}))
    except TypeError as e:
        last_exc = e
    except Exception:
        # runtime error inside the tool should propagate so we catch it at a higher level
        raise

    try:
        return module.call(*args)
    except Exception as e:
        last_exc = e

    try:
        return module.call(**(kwargs or {}))
    except Exception as e:
        last_exc = e

    try:
        return module.call(args)
    except Exception as e:
        last_exc = e

    try:
        return module.call()
    except Exception as e:
        last_exc = e

    # if nothing worked, re-raise last exception
    raise last_exc

def _exec_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single step dict:
      {"tool": "read", "args": [...], "kwargs": {...}}

    Returns a normalized dict:
      {"tool": tool, "success": True/False, "output": ..., "args": [...], "kwargs": {...}}
    """
    if not isinstance(step, dict) or "tool" not in step:
        return {"tool": "<unknown>", "success": False, "output": "Unsupported step format.", "args": [], "kwargs": {}}

    tool = step["tool"]
    args = step.get("args", []) or []
    kwargs = step.get("kwargs", {}) or {}

    # Safety: prevent accidental overwrites via Write without force
    if tool.lower() == "write":
        target = args[0] if len(args) >= 1 else None
        force_flag = bool(kwargs.get("force", False)) if isinstance(kwargs, dict) else False
        if target:
            try:
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
                        ),
                        "args": args,
                        "kwargs": kwargs
                    }
            except Exception:
                # if checking filesystem fails, continue
                pass

    try:
        module = _load_tool_module(tool)
    except Exception as e:
        return {"tool": tool, "success": False, "output": f"Tool load error: {e}", "args": args, "kwargs": kwargs}

    if not hasattr(module, "call"):
        return {"tool": tool, "success": False, "output": f"Tool '{tool}' missing call(...) function.", "args": args, "kwargs": kwargs}

    try:
        raw_res = _call_module_func_safe(module, args, kwargs)
        # If tool returned dict, augment with args/kwargs and tool name
        if isinstance(raw_res, dict):
            raw_res.setdefault("tool", tool)
            raw_res.setdefault("args", args)
            raw_res.setdefault("kwargs", kwargs)
            # Ensure success key exists
            raw_res.setdefault("success", True)
            return raw_res
        # Otherwise normalize into our shape
        return {"tool": tool, "success": True, "output": raw_res, "args": args, "kwargs": kwargs}
    except Exception:
        tb = traceback.format_exc()
        return {"tool": tool, "success": False, "output": f"Exception while running tool '{tool}': {tb}", "args": args, "kwargs": kwargs}

def _try_read_then_glob_and_retry(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to execute a Read step, and if it reports "File not found",
    try Glob("**/<query>") then retry Read with the first match.
    """
    res = _exec_step(step)
    try:
        out = res.get("output", "")
        if res.get("success") is False and isinstance(out, str) and "File not found" in out:
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
            # normalize glob_res to dict if needed
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
                retry_raw = _call_module_func_safe(read_mod, [first], {})
            except Exception:
                return res
            if isinstance(retry_raw, dict):
                retry_raw.setdefault("tool", "read")
                retry_raw.setdefault("args", [first])
                retry_raw.setdefault("kwargs", {})
                retry_raw.setdefault("note", f"Read retried using glob match: {first}")
                return retry_raw
            return {"tool": "read", "success": True, "output": retry_raw, "args": [first], "kwargs": {}}
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

    return {"tool": "<unknown>", "success": False, "output": "Unsupported payload for dispatch_tool.", "args": [], "kwargs": {}}
