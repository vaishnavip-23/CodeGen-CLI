import os, json, tempfile, uuid
WORKDIR = os.getcwd()
DBDIR = os.path.join(WORKDIR, "db")
os.makedirs(DBDIR, exist_ok=True)
def _id():
    return uuid.uuid4().hex[:8]
def call(todos):
    if not isinstance(todos, list):
        return {"success": False, "output": "Expected list of todos", "meta": {}}
    normalized = []
    for t in todos:
        if not isinstance(t, dict) or "content" not in t:
            return {"success": False, "output": "Each todo must be dict with 'content'", "meta": {}}
        content = str(t.get("content", "")).strip()
        if not content:
            return {"success": False, "output": "Todo 'content' cannot be empty", "meta": {}}
        normalized.append({"id": t.get("id", _id()), "content": content, "status": t.get("status","pending")})
    fd, tmp = tempfile.mkstemp(dir=DBDIR, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"todos": normalized}, f, indent=2, ensure_ascii=False)
        with open(tmp, "r", encoding="utf-8") as f:
            _ = f.read()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return {"success": True, "output": f"Stored {len(normalized)} todos (ephemeral).", "meta": {"todos": normalized}}
