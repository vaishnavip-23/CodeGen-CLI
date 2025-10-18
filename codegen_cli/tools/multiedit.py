# File Summary: Implementation of the MultiEdit tool for atomic batch edits.

import os

from .edit import call as edit_call

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import MultiEditChange, MultiEditResult, MultiEditOutput

WORKSPACE = os.getcwd()

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "multi_edit",
    "description": "Perform multiple file edits atomically in sequence. All edits must succeed or all fail.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Base file path (if all edits are to same file)"
            },
            "edits": {
                "type": "array",
                "description": "Array of edit operations",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path (overrides base path)"},
                        "old_string": {"type": "string", "description": "Text to find"},
                        "new_string": {"type": "string", "description": "Replacement text"},
                        "replace_all": {"type": "boolean", "description": "Replace all occurrences"}
                    },
                    "required": ["old_string", "new_string"]
                }
            }
        },
        "required": ["edits"]
    }
}

def get_function_declaration():
    """Get Gemini function declaration for this tool."""
    if types is None:
        return None
    
    return types.FunctionDeclaration(
        name=FUNCTION_DECLARATION["name"],
        description=FUNCTION_DECLARATION["description"],
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "path": types.Schema(type=types.Type.STRING, description="Base file path"),
                "edits": types.Schema(
                    type=types.Type.ARRAY,
                    description="Array of edit operations",
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "path": types.Schema(type=types.Type.STRING, description="File path"),
                            "old_string": types.Schema(type=types.Type.STRING, description="Text to find"),
                            "new_string": types.Schema(type=types.Type.STRING, description="Replacement text"),
                            "replace_all": types.Schema(type=types.Type.BOOLEAN, description="Replace all occurrences")
                        }
                    )
                )
            },
            required=["edits"]
        )
    )


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
        raise ValueError("multiedit expects edits")
    
    base_path, entries = _normalize_entries(args[0], args[1] if len(args) > 1 else None, kwargs)
    if entries is None:
        raise ValueError("Unable to determine edits for MultiEdit")
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, (list, tuple)):
        raise ValueError("multiedit expects a list of edit dicts")
    
    # Validate entries can be converted to MultiEditChange objects
    try:
        for e in entries:
            MultiEditChange(
                path=e.get("path"),
                old_string=e.get("old_string", e.get("a")),
                new_string=e.get("new_string", e.get("b")),
                replace_all=e.get("replace_all", False)
            )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")

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

        try:
            res = edit_call(
                path,
                old_value,
                new_value,
                replace_all=replace_all,
                skip_python_check=True,
            )
            result_obj = MultiEditResult(
                step=i,
                path=path,
                success=res.get("success", False),
                message=res.get("output", "")
            )
            summary.append(result_obj)
            if not res.get("success"):
                raise IOError(f"Edit step {i} failed: {res.get('output')}")
        except Exception as e:
            raise IOError(f"Edit step {i} failed: {e}")
        touched_paths.append(path)
    
    output = MultiEditOutput(
        results=summary,
        total_edits=len(summary),
        successful_edits=len([s for s in summary if s.success])
    )
    return output.model_dump()
