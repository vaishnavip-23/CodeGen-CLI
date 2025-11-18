"""
Multi-Edit Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

Performs multiple file edits atomically in sequence. All edits must succeed or all fail.
"""

import os
from typing import List, Dict, Any, Optional

from .edit import call as edit_call

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import MultiEditChange, MultiEditResult, MultiEditOutput

WORKSPACE = os.getcwd()


def multi_edit(edits: List[Dict[str, Any]], path: Optional[str] = None) -> Dict[str, Any]:
    """Perform multiple file edits atomically in sequence.
    
    Applies multiple edits to one or more files in sequence. All edits must succeed
    or the operation fails. Each edit can specify its own path or use the base path.
    
    Args:
        edits: Array of edit operations. Each edit must have 'old_string' and 'new_string',
               and can optionally have 'path' (overrides base path) and 'replace_all' (bool).
        path: Base file path used if individual edits don't specify their own path (optional)
        
    Returns:
        A dictionary containing results for each edit, total edits, and successful count.
        
    Example:
        multi_edit(edits=[
            {"old_string": "old1", "new_string": "new1"},
            {"old_string": "old2", "new_string": "new2"}
        ], path="/path/to/file.py")
        
        multi_edit(edits=[
            {"path": "/path/to/file1.py", "old_string": "old1", "new_string": "new1"},
            {"path": "/path/to/file2.py", "old_string": "old2", "new_string": "new2"}
        ])
    """
    if not edits:
        raise ValueError("At least one edit operation is required")
    
    if not isinstance(edits, list):
        raise ValueError("edits must be a list of edit operations")
    
    # Validate all edits can be converted to MultiEditChange objects
    try:
        for e in edits:
            MultiEditChange(
                path=e.get("path"),
                old_string=e.get("old_string", e.get("a")),
                new_string=e.get("new_string", e.get("b")),
                replace_all=e.get("replace_all", False)
            )
    except Exception as e:
        raise ValueError(f"Invalid edit structure: {e}")
    
    summary = []
    
    for i, entry in enumerate(edits, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Edit #{i} is not a dictionary")
        
        edit_data = dict(entry)
        edit_path = edit_data.get("path") or path
        
        if not edit_path:
            raise ValueError(f"Edit #{i} is missing 'path' and no base path provided")
        
        old_value = edit_data.get("old_string")
        if old_value is None:
            old_value = edit_data.get("a")
        
        new_value = edit_data.get("new_string")
        if new_value is None:
            new_value = edit_data.get("b")
        
        if old_value is None or new_value is None:
            raise ValueError(f"Edit #{i} is missing 'old_string' or 'new_string'")
        
        replace_all = bool(edit_data.get("replace_all", False))
        
        try:
            res = edit_call(
                edit_path,
                old_value,
                new_value,
                replace_all=replace_all,
                skip_python_check=True,
            )
            result_obj = MultiEditResult(
                step=i,
                path=edit_path,
                success=res.get("success", False),
                message=res.get("output", "")
            )
            summary.append(result_obj)
            
            if not res.get("success"):
                raise IOError(f"Edit step {i} failed: {res.get('output')}")
        except Exception as e:
            raise IOError(f"Edit step {i} failed: {e}")
    
    output = MultiEditOutput(
        results=summary,
        total_edits=len(summary),
        successful_edits=len([s for s in summary if s.success])
    )
    return output.model_dump()


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=multi_edit
    )


# Keep backward compatibility
def call(*args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    if not args:
        raise ValueError("multiedit expects edits")
    
    # Helper to normalize different input formats
    def _normalize_entries(first_arg, maybe_entries, kwargs_dict):
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
                entries = kwargs_dict.get("edits")
        return base_path, entries
    
    base_path, entries = _normalize_entries(
        args[0],
        args[1] if len(args) > 1 else None,
        kwargs
    )
    
    if entries is None:
        raise ValueError("Unable to determine edits for MultiEdit")
    
    if isinstance(entries, dict):
        entries = [entries]
    
    if not isinstance(entries, (list, tuple)):
        raise ValueError("multiedit expects a list of edit dicts")
    
    return multi_edit(edits=list(entries), path=base_path)
