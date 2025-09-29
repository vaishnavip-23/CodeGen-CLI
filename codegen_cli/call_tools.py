"""
Tool dispatcher for CodeGen2 CLI agent.

Handles calling individual tool modules and provides safety checks for file operations.
"""

import importlib
import traceback
from typing import Any, Dict

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

def _read_file_safe(path: str) -> str:
    """Safely read file content."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""

def _glob_retry_read(module, args, kwargs):
    """Try to find file using glob and retry read."""
    if not args:
        return None
    
    target_path = args[0]
    if not isinstance(target_path, str):
        return None
    
    # Try glob to find the file
    try:
        glob_module = importlib.import_module("tools.glob")
        glob_result = glob_module.call(f"**/{target_path}")
        
        if isinstance(glob_result, dict) and glob_result.get("success"):
            output = glob_result.get("output", {})
            if isinstance(output, dict) and "files" in output:
                files = output["files"]
                if files and len(files) > 0:
                    # Retry read with found file
                    new_args = [files[0]] + list(args[1:])
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
    
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return {"tool": "unknown", "success": False, "output": "Plan must contain steps list", "args": [], "kwargs": {}}
    
    if not steps:
        return {"tool": "unknown", "success": True, "output": "No steps to execute", "args": [], "kwargs": {}}
    
    if len(steps) == 1:
        # Single step
        step = steps[0]
        if not isinstance(step, dict):
            return {"tool": "unknown", "success": False, "output": "Step must be a dictionary", "args": [], "kwargs": {}}
        
        tool_name = step.get("tool", "unknown")
        args = step.get("args", [])
        kwargs = step.get("kwargs", {})
        
        try:
            module = _load_tool_module(tool_name)
            
            # Special handling for read tool
            if tool_name.lower() == "read":
                result = _call_module_func_safe(module, args, kwargs)
                if result and isinstance(result, dict) and not result.get("success", True):
                    # Try glob retry
                    retry_result = _glob_retry_read(module, args, kwargs)
                    if retry_result:
                        return retry_result
            
            # Special handling for write tool
            elif tool_name.lower() == "write":
                safe, error_msg = _check_write_safety(args, kwargs)
                if not safe:
                    return {
                        "tool": tool_name,
                        "success": False,
                        "output": error_msg,
                        "args": args,
                        "kwargs": kwargs
                    }
            
            result = _call_module_func_safe(module, args, kwargs)
            if result is None:
                return {
                    "tool": tool_name,
                    "success": False,
                    "output": "Tool returned None",
                    "args": args,
                    "kwargs": kwargs
                }
            
            # Ensure result has required fields
            if isinstance(result, dict):
                if "tool" not in result:
                    result["tool"] = tool_name
                if "args" not in result:
                    result["args"] = args
                if "kwargs" not in result:
                    result["kwargs"] = kwargs
            else:
                result = {
                    "tool": tool_name,
                    "success": True,
                    "output": result,
                    "args": args,
                    "kwargs": kwargs
                }
            
            return result
            
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
            args = step.get("args", [])
            kwargs = step.get("kwargs", {})
            
            try:
                module = _load_tool_module(tool_name)
                
                # Special handling for read tool
                if tool_name.lower() == "read":
                    result = _call_module_func_safe(module, args, kwargs)
                    if result and isinstance(result, dict) and not result.get("success", True):
                        retry_result = _glob_retry_read(module, args, kwargs)
                        if retry_result:
                            result = retry_result
                
                # Special handling for write tool
                elif tool_name.lower() == "write":
                    safe, error_msg = _check_write_safety(args, kwargs)
                    if not safe:
                        results.append({
                            "tool": tool_name,
                            "success": False,
                            "output": error_msg,
                            "args": args,
                            "kwargs": kwargs
                        })
                        continue
                
                result = _call_module_func_safe(module, args, kwargs)
                if result is None:
                    result = {
                        "tool": tool_name,
                        "success": False,
                        "output": "Tool returned None",
                        "args": args,
                        "kwargs": kwargs
                    }
                elif isinstance(result, dict):
                    if "tool" not in result:
                        result["tool"] = tool_name
                    if "args" not in result:
                        result["args"] = args
                    if "kwargs" not in result:
                        result["kwargs"] = kwargs
                else:
                    result = {
                        "tool": tool_name,
                        "success": True,
                        "output": result,
                        "args": args,
                        "kwargs": kwargs
                    }
                
                results.append(result)
                
            except Exception as e:
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "output": f"Tool execution failed: {str(e)}\n{traceback.format_exc()}",
                    "args": args,
                    "kwargs": kwargs
                })
        
        return results