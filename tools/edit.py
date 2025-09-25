import os, tempfile, shutil
WORKDIR = os.getcwd()

def _resolve(p):
    if not os.path.isabs(p):
        p = os.path.join(WORKDIR, p)
    p = os.path.realpath(p)
    if os.path.commonpath([WORKDIR, p]) != WORKDIR:
        raise PermissionError("outside workspace")
    return p

def call(file_path, old_string, new_string, replace_all=False):
    try:
        path = _resolve(file_path)
    except Exception as e:
        return {"success": False, "output": f"Invalid path: {e}", "meta": {}}
    if not os.path.exists(path):
        return {"success": False, "output": "File not found", "meta": {}}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
        if replace_all:
            new_txt = txt.replace(old_string, new_string)
        else:
            if txt.count(old_string) != 1:
                return {"success": False, "output": "old_string not unique; use replace_all or provide more context", "meta": {}}
            new_txt = txt.replace(old_string, new_string, 1)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_txt)
        shutil.move(tmp, path)
    except Exception as e:
        return {"success": False, "output": f"Edit error: {e}", "meta": {}}
    return {"success": True, "output": f"Edited {path}", "meta": {"path": path}}
