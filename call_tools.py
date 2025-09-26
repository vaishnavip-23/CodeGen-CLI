"""
call_tools.py

Simple dispatcher for tools living in tools/<name>.py.

It accepts:
 - plan dicts: {"steps":[...], "explain":"..."}
 - single-step dict: {"tool":"read","args":[...],"kwargs":{...}}
 - list of steps: [ step1, step2, ... ]

Each tool must implement call(*args, **kwargs) and return a dict:
  {"tool": "<name>", "success": True/False, "output": ...}
"""

import importlib
import traceback
import os

def _load_tool_module(name):
    try:
        module = importlib.import_module(f"tools.{name}")
        return module
    except ModuleNotFoundError:
        raise RuntimeError(f"Tool '{name}' not found. Expected tools/{name}.py")

def _exec_step(step):
    # Determine tool name, args, kwargs
    if isinstance(step, dict) and "tool" in step:
        tool = step["tool"]
        args = step.get("args", []) or []
        kwargs = step.get("kwargs", {}) or {}
    elif isinstance(step, (list, tuple)):
        tool = step[0]
        args = list(step[1:])
        kwargs = {}
    elif isinstance(step, str):
        parts = step.split()
        tool = parts[0]
        args = parts[1:]
        kwargs = {}
    else:
        return {"tool": "<unknown>", "success": False, "output": f"Unsupported step format: {type(step)}"}

    try:
        module = _load_tool_module(tool)
    except Exception as e:
        return {"tool": tool, "success": False, "output": f"Tool load error: {e}"}

    if not hasattr(module, "call"):
        return {"tool": tool, "success": False, "output": f"Tool '{tool}' has no call(...) function."}

    try:
        res = module.call(*args, **kwargs)
        if isinstance(res, dict):
            res.setdefault("tool", tool)
        return res
    except Exception:
        return {"tool": tool, "success": False, "output": f"Exception while running tool '{tool}': {traceback.format_exc()}"}

def dispatch_tool(payload):
    """
    Dispatch plan or steps. Return a single result dict or a list of result dicts.
    """
    if isinstance(payload, list):
        results = []
        for s in payload:
            results.append(_exec_step(s))
        return results
    if isinstance(payload, dict) and "steps" in payload and isinstance(payload["steps"], list):
        results = []
        for s in payload["steps"]:
            results.append(_exec_step(s))
        return results
    if isinstance(payload, dict) and "tool" in payload:
        return _exec_step(payload)
    return _exec_step(payload)
