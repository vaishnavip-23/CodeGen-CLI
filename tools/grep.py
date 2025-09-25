import os, re
WORKDIR = os.getcwd()

def _walk_files(path):
    for root, _, files in os.walk(path):
        for f in files:
            yield os.path.join(root, f)

def call(pattern, path=".", glob=None, output_mode="files_with_matches", head_limit=None, **_):
    try:
        base = path if os.path.isabs(path) else os.path.join(WORKDIR, path)
    except Exception:
        base = WORKDIR
    matches = []
    regex = re.compile(pattern, re.MULTILINE)
    for fp in _walk_files(base):
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
        except Exception:
            continue
        if regex.search(txt):
            if output_mode == "content":
                lines = []
                for i,l in enumerate(txt.splitlines(), start=1):
                    if regex.search(l):
                        lines.append(f"{fp}:{i}:{l}")
                matches.extend(lines)
            else:
                matches.append(fp)
    if head_limit:
        matches = matches[:head_limit]
    return {"success": True, "output": "\n".join(matches), "meta": {"count": len(matches)}}
