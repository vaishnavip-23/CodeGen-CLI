import os
def call(file_path, edits):
    if not isinstance(edits, list) or not edits:
        return {"success": False, "output": "edits must be a non-empty list", "meta": {}}
    if not os.path.exists(file_path):
        return {"success": False, "output": "file not found", "meta": {}}
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
        for e in edits:
            old = e["old_string"]; new = e["new_string"]; replace_all = e.get("replace_all", False)
            if replace_all:
                txt = txt.replace(old, new)
            else:
                if txt.count(old) != 1:
                    return {"success": False, "output": "old_string not unique in sequential multiedit", "meta": {}}
                txt = txt.replace(old, new, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(txt)
    except Exception as e:
        return {"success": False, "output": f"MultiEdit error: {e}", "meta": {}}
    return {"success": True, "output": f"Applied {len(edits)} edits to {file_path}", "meta": {}}
