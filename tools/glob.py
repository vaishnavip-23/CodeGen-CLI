import os, glob, time
WORKDIR = os.getcwd()

def _resolve(p):
    if not p:
        return WORKDIR
    if not os.path.isabs(p):
        p = os.path.join(WORKDIR, p)
    return os.path.realpath(p)

def call(pattern, path=".", limit=None):
    base = _resolve(path)
    matches = glob.glob(os.path.join(base, pattern), recursive=True)
    matches = sorted(matches, key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    if limit:
        matches = matches[:limit]
    return {"success": True, "output": "\n".join(matches), "meta": {"count": len(matches)}}
