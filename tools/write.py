import os
WORKDIR = os.getcwd()

def _resolve(p):
    if not os.path.isabs(p):
        p = os.path.join(WORKDIR, p)
    p = os.path.realpath(p)
    if os.path.commonpath([WORKDIR, p]) != WORKDIR:
        raise PermissionError("outside workspace")
    return p

def call(file_path, content):
    try:
        path = _resolve(file_path)
    except Exception as e:
        return {"success": False, "output": f"Invalid path: {e}", "meta": {}}
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return {"success": False, "output": f"Write error: {e}", "meta": {}}
    return {"success": True, "output": f"Wrote {path}", "meta": {"path": path}}
