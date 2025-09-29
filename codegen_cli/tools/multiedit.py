from .edit import call as edit_call

def call(edits):
    if not isinstance(edits, (list, tuple)):
        return {"success": False, "output": "multiedit expects a list of edit dicts."}
    summary = []
    for i, e in enumerate(edits, start=1):
        path = e.get("path")
        mode = e.get("mode", "replace")
        a = e.get("a")
        b = e.get("b")
        # reuse edit.call semantics
        res = edit_call(path, a, b, e.get("replace_all", False))
        summary.append({"step": i, "path": path, "result": res})
        if not res.get("success"):
            return {"success": False, "output": summary}
    return {"success": True, "output": summary}
