import importlib, os
WORKDIR = os.getcwd()
ALLOWED_TOOLS = {"task","read","grep","ls","glob","bash","write","edit","multiedit","websearch","webfetch","exitplanmode","todowrite"}

def _normalize(payload):
    if not isinstance(payload, dict):
        return False, "payload must be an object"
    if "tool" not in payload:
        return False, "missing 'tool'"
    name = payload["tool"]
    if not isinstance(name, str):
        return False, "tool name must be string"
    name = name.lower()
    if name not in ALLOWED_TOOLS:
        return False, f"tool '{name}' not allowed"
    args = payload.get("args", [])
    kwargs = payload.get("kwargs") or {}
    if isinstance(args, str):
        args = [args]
    if isinstance(args, dict):
        tmp = dict(kwargs); tmp.update(args); kwargs = tmp; args = []
    if not args and isinstance(kwargs.get("args"), dict):
        nested = kwargs.pop("args")
        for k,v in nested.items():
            if k not in kwargs:
                kwargs[k] = v
    if not args and isinstance(kwargs, dict):
        for k in ("file_path","file","path","fname","filename"):
            if k in kwargs and isinstance(kwargs[k], str):
                args = [kwargs.pop(k)]
                break
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        return False, "'args' must be list and 'kwargs' must be object"
    if name == "ls":
        for k in ("names_only","dirs_only","recursive","files_only"):
            if k in kwargs and isinstance(kwargs[k], str):
                kwargs[k] = kwargs[k].lower() == "true"
    return True, {"name": name, "args": args, "kwargs": kwargs}

def _import_module(name):
    try:
        return importlib.import_module(f"tools.{name}")
    except Exception:
        return None

def dispatch_tool(payload):
    ok, parsed = _normalize(payload)
    if not ok:
        return {"success": False, "output": parsed, "meta": {}}
    name = parsed["name"]; args = parsed["args"]; kwargs = parsed["kwargs"]
    mod = _import_module(name)
    if not mod or not hasattr(mod, "call"):
        return {"success": False, "output": f"Tool not found: {name}", "meta": {}}
    try:
        res = mod.call(*args, **kwargs)
    except Exception as e:
        return {"success": False, "output": f"Tool runtime error: {e}", "meta": {}}
    if not isinstance(res, dict) or "success" not in res or "output" not in res:
        return {"success": False, "output": "Invalid tool response shape", "meta": {"raw": res}}
    return res
