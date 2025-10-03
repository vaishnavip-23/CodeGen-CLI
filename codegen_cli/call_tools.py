"""
Tool dispatcher for CodeGen2 CLI agent.

Handles calling individual tool modules and provides safety checks for file operations.
"""

import importlib
import os
import traceback
from typing import Any, Dict, List, Tuple

def _load_tool_module(name: str):
    """Load a tool module by name."""
    try:
        module = importlib.import_module(f"codegen_cli.tools.{name}")
    except ModuleNotFoundError:
        try:
            module = importlib.import_module(f"codegen_cli.tools.{name.lower()}")
        except Exception as e:
            raise RuntimeError(f"Tool '{name}' not found.") from e
    return module

def _call_module_func_safe(module, args, kwargs):
    """Safely call module.call with various argument patterns."""
    last_exc = None
    
    # Try different calling patterns
    patterns = [
        lambda: module.call(*args, **(kwargs or {})),
        lambda: module.call(*args),
        lambda: module.call(**kwargs) if kwargs else None,
        lambda: module.call(args) if args else None,
        lambda: module.call()
    ]
    
    for pattern in patterns:
        try:
            result = pattern()
            if result is not None:
                return result
        except TypeError as e:
            last_exc = e
        except Exception:
            # Runtime errors should propagate
            raise
    
    if last_exc:
        raise last_exc
    return None


def _execute_tool_call(tool_name: str, args, kwargs):
    module = _load_tool_module(tool_name)
    args = _normalize_args(tool_name, args, kwargs)

    # Special handling for read tool
    if tool_name.lower() == "read":
        result = _call_module_func_safe(module, args, kwargs)
        if result and isinstance(result, dict) and not result.get("success", True):
            retry_result = _glob_retry_read(module, args, kwargs)
            if retry_result:
                result = retry_result
        
        if result is None:
            result = {
                "tool": tool_name,
                "success": False,
                "output": "Tool returned None",
                "args": args,
                "kwargs": kwargs,
            }
        elif isinstance(result, dict):
            result.setdefault("tool", tool_name)
            result.setdefault("args", args)
            result.setdefault("kwargs", kwargs)
        else:
            result = {
                "tool": tool_name,
                "success": True,
                "output": result,
                "args": args,
                "kwargs": kwargs,
            }
        return result

    if tool_name.lower() == "write":
        safe, error_msg = _check_write_safety(args, kwargs)
        if not safe:
            return {
                "tool": tool_name,
                "success": False,
                "output": error_msg,
                "args": args,
                "kwargs": kwargs,
            }

    result = _call_module_func_safe(module, args, kwargs)
    if result is None:
        return {
            "tool": tool_name,
            "success": False,
            "output": "Tool returned None",
            "args": args,
            "kwargs": kwargs,
        }

    if isinstance(result, dict):
        result.setdefault("tool", tool_name)
        result.setdefault("args", args)
        result.setdefault("kwargs", kwargs)
        return result

    return {
        "tool": tool_name,
        "success": True,
        "output": result,
        "args": args,
        "kwargs": kwargs,
    }


def _extract_args_kwargs_from_use(tool_name: str, use: Dict[str, Any]) -> Tuple[List[Any], Dict[str, Any]]:
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}

    if not isinstance(use, dict):
        return args, kwargs

    params = use.get("parameters")
    if isinstance(params, dict):
        if isinstance(params.get("args"), list):
            args = list(params["args"])
        if isinstance(params.get("kwargs"), dict):
            kwargs = dict(params["kwargs"])
        else:
            for key, value in params.items():
                if key in {"args", "kwargs"}:
                    continue
                kwargs[key] = value
    elif isinstance(params, list):
        args = list(params)

    if "args" in use and isinstance(use["args"], list):
        args = list(use["args"])
    if "kwargs" in use and isinstance(use["kwargs"], dict):
        kwargs = dict(use["kwargs"])

    # Convert commonly used keyword names to positional arguments for our tools
    lowered = tool_name.lower()
    def _pop_first(keys):
        for key in keys:
            if key in kwargs:
                value = kwargs.pop(key)
                args.append(value)
                return True
        return False

    if not args:
        if lowered in {"read", "write", "edit", "delete", "ls", "python_run", "python_check"}:
            if not _pop_first(["path", "file_path", "target", "directory"]):
                _pop_first(["pattern"])
        elif lowered == "glob":
            _pop_first(["pattern", "glob"])
        elif lowered == "grep":
            _pop_first(["pattern"])

    if lowered == "grep" and "path" not in kwargs:
        if "path_pattern" in kwargs:
            kwargs["path"] = kwargs.pop("path_pattern")

    if lowered == "todowrite" and not args and "todos" in kwargs:
        args.append(kwargs.pop("todos"))

    return args, kwargs


def _execute_parallel_tool(step: Dict[str, Any]):
    tool_uses = step.get("tool_uses", [])
    if not isinstance(tool_uses, list):
        return {
            "tool": step.get("tool", "multi_tool_use.parallel"),
            "success": False,
            "output": "tool_uses must be a list",
            "args": [],
            "kwargs": {},
        }

    aggregated_results = []
    for use in tool_uses:
        if not isinstance(use, dict):
            aggregated_results.append({
                "tool": "unknown",
                "success": False,
                "output": "Invalid tool specification",
                "args": [],
                "kwargs": {},
            })
            continue

        raw_name = use.get("recipient_name") or use.get("tool")
        if not raw_name:
            aggregated_results.append({
                "tool": "unknown",
                "success": False,
                "output": "Missing tool name",
                "args": [],
                "kwargs": {},
            })
            continue

        tool_name = raw_name.split(".")[-1]
        args, kwargs = _extract_args_kwargs_from_use(tool_name, use)
        try:
            result = _execute_tool_call(tool_name, args, kwargs)
        except Exception as e:
            result = {
                "tool": tool_name,
                "success": False,
                "output": f"Tool execution failed: {e}\n{traceback.format_exc()}",
                "args": args,
                "kwargs": kwargs,
            }
        aggregated_results.append(result)

    return {
        "tool": step.get("tool", "multi_tool_use.parallel"),
        "success": all(r.get("success", False) for r in aggregated_results),
        "output": aggregated_results,
        "args": [],
        "kwargs": {},
    }

def _glob_retry_read(module, args, kwargs):
    """Try to find file using glob and retry read."""
    if not args:
        return None
    
    target_path = args[0]
    if not isinstance(target_path, str):
        return None
    
    # Try glob to find the file
    try:
        glob_module = importlib.import_module("codegen_cli.tools.glob")
        glob_result = glob_module.call(f"**/{target_path}")

        if isinstance(glob_result, dict) and glob_result.get("success"):
            output = glob_result.get("output")
            # Our Glob tool returns a list of relative paths in 'output'
            if isinstance(output, list) and output:
                # Retry read with first match
                new_args = [output[0]] + list(args[1:])
                return _call_module_func_safe(module, new_args, kwargs)
    except Exception:
        pass
    
    return None

def _check_write_safety(args, kwargs):
    """Check if write operation is safe."""
    if not args:
        return True, None
    
    target_path = args[0]
    if not isinstance(target_path, str):
        return True, None
    
    # Check if file exists
    try:
        import os
        if os.path.exists(target_path):
            force = kwargs.get("force", False) if kwargs else False
            if not force:
                return False, f"File '{target_path}' already exists. Use Edit/MultiEdit to modify existing files, or set force=True to overwrite."
    except Exception:
        pass
    
    return True, None

def _looks_like_path(token: str) -> bool:
    """Heuristic to detect a path-like token from natural phrases."""
    if not isinstance(token, str):
        return False
    t = token.strip().strip(",.!")
    if not t:
        return False
    return "/" in t or "." in t or os.path.exists(t)

def _normalize_args(tool_name: str, args, kwargs):
    """Normalize arguments for certain tools when users type natural phrases.

    Heuristics only; keeps original args if we can't confidently improve them.
    """
    if not isinstance(args, list):
        return args
    name = tool_name.lower()
    stopwords = {"the", "a", "an", "file", "folder", "directory", "named", "called"}
    linkers = {"with", "containing", "that", "says", "content", "text"}

    tokens = [str(a) for a in args]
    cleaned = [t.strip().strip(",.!") for t in tokens if t.strip()]

    # Helper: pick first path-like candidate
    def pick_path(cands):
        for c in cands:
            if _looks_like_path(c):
                return c
        for c in cands:
            if "." in c:
                return c
        return cands[0] if cands else None

    if name in ("delete", "read", "ls", "glob") and cleaned:
        candidates = [c for c in cleaned if c.lower() not in stopwords]
        path = pick_path(candidates)
        if path:
            return [path] + ([] if name in ("delete", "read") else cleaned[1:])
        # If delete and no direct path, attempt a filesystem search for likely file
        if name == "delete":
            found = None
            tokens = [c.lower() for c in candidates if c]
            for dirpath, dirnames, filenames in os.walk(os.getcwd()):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for fn in filenames:
                    low = fn.lower()
                    if any(t in low for t in tokens):
                        found = os.path.relpath(os.path.join(dirpath, fn), os.getcwd())
                        break
                if found:
                    break
            if found:
                if isinstance(kwargs, dict):
                    kwargs.setdefault("suggested_path", found)
                return args
        return args

    if name == "write" and cleaned:
        candidates = [c for c in cleaned if c.lower() not in stopwords]
        path = pick_path(candidates)
        if path:
            # content = remaining tokens excluding path and stop/linker words
            remaining = [c for c in candidates if c != path and c.lower() not in linkers]
            content = " ".join(remaining).strip()
            return [path] + ([content] if content else [])
        return args

    if name == "edit":
        # Preserve original args to avoid losing empty strings ("" used to signal overwrite)
        return args

    if name == "grep" and cleaned:
        # Pattern [in PATH]
        if "in" in [c.lower() for c in cleaned]:
            idx = [c.lower() for c in cleaned].index("in")
            pattern = " ".join(cleaned[:idx]).strip()
            after = cleaned[idx+1:]
            path = pick_path([c for c in after if c.lower() not in stopwords])
            if pattern and path:
                # our grep tool expects pattern first; path passed via kwargs in our dispatcher
                if isinstance(kwargs, dict):
                    kwargs.setdefault("path", path)
                return [pattern]
        return args

    return args

def dispatch_tool(plan: Dict[str, Any]) -> Any:
    """
    Execute a tool plan and return results.
    
    Args:
        plan: Dictionary with 'steps' containing list of tool calls
        
    Returns:
        Single result dict or list of result dicts
    """
    if not isinstance(plan, dict):
        return {"tool": "unknown", "success": False, "output": "Invalid plan format", "args": [], "kwargs": {}}
    
    # Support both {tool, args, kwargs} and {steps: [...]} formats
    if "tool" in plan and isinstance(plan.get("tool"), str):
        step = {
            "tool": plan.get("tool"),
            "args": plan.get("args", []),
            "kwargs": plan.get("kwargs", {}),
        }
        if "tool_uses" in plan:
            step["tool_uses"] = plan.get("tool_uses")
        steps = [step]
    else:
        steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return {"tool": "unknown", "success": False, "output": "Plan must contain steps list", "args": [], "kwargs": {}}
    
    if not steps:
        return {"tool": plan.get("tool", "unknown"), "success": True, "output": "No steps to execute", "args": plan.get("args", []), "kwargs": plan.get("kwargs", {})}
    
    if len(steps) == 1:
        # Single step
        step = steps[0]
        if not isinstance(step, dict):
            return {"tool": "unknown", "success": False, "output": "Step must be a dictionary", "args": [], "kwargs": {}}
        
        tool_name = step.get("tool", "unknown")
        if tool_name.lower() == "multi_tool_use.parallel" or "tool_uses" in step:
            return _execute_parallel_tool(step)

        args = step.get("args", [])
        kwargs = step.get("kwargs", {})
        
        try:
            return _execute_tool_call(tool_name, args, kwargs)
        except Exception as e:
            return {
                "tool": tool_name,
                "success": False,
                "output": f"Tool execution failed: {str(e)}\n{traceback.format_exc()}",
                "args": args,
                "kwargs": kwargs
            }
    
    else:
        # Multiple steps
        results = []
        for step in steps:
            if not isinstance(step, dict):
                results.append({
                    "tool": "unknown",
                    "success": False,
                    "output": "Step must be a dictionary",
                    "args": [],
                    "kwargs": {}
                })
                continue
            
            tool_name = step.get("tool", "unknown")

            if tool_name.lower() == "multi_tool_use.parallel" or "tool_uses" in step:
                results.append(_execute_parallel_tool(step))
                continue

            args = step.get("args", [])
            kwargs = step.get("kwargs", {})
            
            try:
                results.append(_execute_tool_call(tool_name, args, kwargs))
                
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "output": f"Tool execution failed: {str(e)}\n{traceback.format_exc()}",
                    "args": args,
                    "kwargs": kwargs
                })
        
        return results