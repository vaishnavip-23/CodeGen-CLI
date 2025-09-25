import os
WORKDIR = os.getcwd()
MAX_LINES = 2000
MAX_LINE_LEN = 2000

def _resolve(p):
    if not p:
        raise ValueError("empty path")
    if not os.path.isabs(p):
        p = os.path.join(WORKDIR, p)
    p = os.path.realpath(p)
    if os.path.commonpath([WORKDIR, p]) != WORKDIR:
        raise PermissionError("outside workspace")
    return p

def _find_in_workspace(basename):
    for root, _, files in os.walk(WORKDIR):
        if basename in files:
            return os.path.join(root, basename)
    return None

def _truncate_line(line):
    return line if len(line) <= MAX_LINE_LEN else line[:MAX_LINE_LEN] + "\n"

def call(*args, file_path=None, offset=None, limit=None, head=None, tail=None, **kwargs):
    path_candidate = None
    if args:
        first = args[0]
        if isinstance(first, (list,tuple)) and first:
            path_candidate = first[0]
        elif isinstance(first, dict):
            path_candidate = first.get("file_path") or first.get("path") or first.get("file")
        else:
            path_candidate = first
    if not path_candidate:
        path_candidate = file_path or kwargs.get("file") or kwargs.get("path") or kwargs.get("file_path")
    if not path_candidate:
        return {"success": False, "output": "Missing file path", "meta": {}}
    try:
        abs_path = _resolve(path_candidate)
    except Exception:
        basename = os.path.basename(path_candidate)
        found = _find_in_workspace(basename)
        if not found:
            return {"success": False, "output": f"File not found: {path_candidate}", "meta": {}}
        try:
            abs_path = _resolve(found)
        except Exception as e:
            return {"success": False, "output": f"Path resolution error: {e}", "meta": {}}
    if not os.path.exists(abs_path):
        return {"success": False, "output": f"File not found: {path_candidate}", "meta": {}}
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return {"success": False, "output": f"Read error: {e}", "meta": {}}
    total = len(lines)
    if head is not None:
        sel = lines[:head]
    elif tail is not None:
        sel = lines[-tail:]
    elif offset is not None or limit is not None:
        start = (offset-1) if offset and offset>0 else 0
        end = start + (limit or MAX_LINES)
        sel = lines[start:end]
    else:
        sel = lines[:MAX_LINES]
    out = "".join(_truncate_line(l) for l in sel)
    return {"success": True, "output": out, "meta": {"total_lines": total, "returned": len(sel), "path": abs_path}}
