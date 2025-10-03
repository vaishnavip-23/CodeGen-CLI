import os
import py_compile
import traceback

from .edit import call as edit_call

WORKSPACE = os.getcwd()


def _check_python_files(paths):
    errors = []
    for rel_path in sorted(set(p for p in paths if p.endswith(".py"))):
        abs_path = os.path.abspath(os.path.join(WORKSPACE, rel_path))
        try:
            py_compile.compile(abs_path, doraise=True)
        except py_compile.PyCompileError as exc:  # pragma: no cover - runtime dependent
            errors.append({
                "path": rel_path,
                "error": str(exc),
                "details": exc.msg if hasattr(exc, "msg") else None,
            })
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({
                "path": rel_path,
                "error": f"Unexpected compile error: {exc}",
                "traceback": traceback.format_exc(),
            })
    return errors


def _normalize_entries(first_arg, maybe_entries, kwargs):
    if isinstance(first_arg, list):
        return None, first_arg
    if isinstance(first_arg, tuple):
        return None, list(first_arg)
    if isinstance(first_arg, dict):
        return None, [first_arg]
    base_path = None
    entries = None
    if isinstance(first_arg, str):
        base_path = first_arg
        if isinstance(maybe_entries, list):
            entries = maybe_entries
        elif isinstance(maybe_entries, tuple):
            entries = list(maybe_entries)
        elif isinstance(maybe_entries, dict):
            entries = [maybe_entries]
        else:
            entries = kwargs.get("edits")
    return base_path, entries


def call(*args, **kwargs):
    if not args:
        return {"success": False, "output": "multiedit expects edits."}
    base_path, entries = _normalize_entries(args[0], args[1] if len(args) > 1 else None, kwargs)
    if entries is None:
        return {"success": False, "output": "Unable to determine edits for MultiEdit."}
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, (list, tuple)):
        return {"success": False, "output": "multiedit expects a list of edit dicts."}

    summary = []
    touched_paths = []
    for i, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            return {"success": False, "output": f"Edit #{i} is not a dict."}
        edit_data = dict(entry)
        path = edit_data.get("path") or base_path
        if not path:
            return {"success": False, "output": f"Edit #{i} is missing 'path'."}

        old_value = edit_data.get("old_string")
        if old_value is None:
            old_value = edit_data.get("a")
        new_value = edit_data.get("new_string")
        if new_value is None:
            new_value = edit_data.get("b")
        replace_all = bool(edit_data.get("replace_all", False))

        res = edit_call(
            path,
            old_value,
            new_value,
            replace_all=replace_all,
            skip_python_check=True,
        )
        summary.append({"step": i, "path": path, "result": res})
        if not res.get("success"):
            return {"success": False, "output": summary}
        touched_paths.append(path)

    syntax_errors = _check_python_files(touched_paths)
    if syntax_errors:
        return {"success": False, "output": summary, "errors": syntax_errors}

    return {"success": True, "output": summary}
