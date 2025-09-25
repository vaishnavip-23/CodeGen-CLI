import os, fnmatch, time
WORKDIR = os.getcwd()

def _resolve(p):
    if not p:
        return WORKDIR
    if not os.path.isabs(p):
        p = os.path.join(WORKDIR, p)
    p = os.path.realpath(p)
    if os.path.commonpath([WORKDIR, p]) != WORKDIR:
        raise PermissionError("outside workspace")
    return p

def call(path=".", ignore=None, names_only=True, dirs_only=False, recursive=False, files_only=False):
    try:
        abs_p = _resolve(path)
    except Exception as e:
        return {"success": False, "output": f"Invalid path: {e}", "meta": {}}
    if not os.path.exists(abs_p):
        return {"success": False, "output": f"Path not found: {path}", "meta": {}}
    # Default ignore patterns to reduce noise when unspecified
    if ignore is None:
        ignore = [
            "__pycache__", "*.pyc", "*.pyo", ".DS_Store",
            ".git", ".git/**", ".venv", ".venv/**",
            "node_modules", "node_modules/**",
            "*.dist-info", "*.egg-info", "*~",
        ]
    else:
        ignore = list(ignore)

    def _is_ignored(name, full_path):
        rel = None
        try:
            rel = os.path.relpath(full_path, WORKDIR)
        except Exception:
            rel = full_path
        for pat in ignore:
            if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
                return True
        return False
    entries = []
    if recursive:
        for root, dirs, files in os.walk(abs_p):
            for name in files + dirs:
                full = os.path.join(root, name)
                if _is_ignored(name, full):
                    continue
                is_dir = os.path.isdir(full)
                entries.append({"name": name, "type":"dir" if is_dir else "file", "path": full, "mtime": os.path.getmtime(full)})
    else:
        for e in os.scandir(abs_p):
            name = e.name
            if _is_ignored(name, e.path):
                continue
            entries.append({"name": name, "type":"dir" if e.is_dir() else "file", "path": e.path, "mtime": os.path.getmtime(e.path)})
    if dirs_only:
        entries = [e for e in entries if e["type"]=="dir"]
    if files_only:
        entries = [e for e in entries if e["type"]=="file"]
    if names_only:
        # Return only basenames regardless of recursive setting
        names = sorted({e["name"] for e in entries})
        output = "\n".join(names)
    else:
        lines = []
        for e in sorted(entries, key=lambda x: x["name"]):
            m = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(e["mtime"]))
            lines.append(f"{e['name']}\t{e['type']}\t{m}")
        output = "\n".join(lines)
    return {"success": True, "output": output, "meta": {"count": len(entries), "path": abs_p}}
