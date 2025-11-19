"""
Multi-Edit Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

Performs multiple file edits atomically in sequence. All edits must succeed or all fail.
"""

import os
from typing import List, Dict, Any, Optional

from .edit import edit_file

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import MultiEditInput, MultiEditChange, MultiEditResult, MultiEditOutput

WORKSPACE = os.getcwd()


def multi_edit(path: Optional[str] = None, edits: List[MultiEditChange] = None) -> MultiEditOutput:
    """Perform multiple file edits atomically in sequence.
    
    Applies multiple edits to one or more files in sequence. All edits must succeed
    or the operation fails. Each edit can specify its own path or use the base path.
    
    Args:
        path: Base file path used if individual edits don't specify their own path (optional)
        edits: List of edit operations (MultiEditChange objects). Each edit must have 'old_string' 
               and 'new_string', and can optionally have 'path' (overrides base path) and 'replace_all' (bool).
        
    Returns:
        MultiEditOutput Pydantic model containing results for each edit, total edits, and successful count.
        
    Example:
        multi_edit(path="/path/to/file.py", edits=[
            MultiEditChange(old_string="old1", new_string="new1"),
            MultiEditChange(old_string="old2", new_string="new2")
        ])
        
        multi_edit(edits=[
            MultiEditChange(path="/path/to/file1.py", old_string="old1", new_string="new1"),
            MultiEditChange(path="/path/to/file2.py", old_string="old2", new_string="new2")
        ])
    """
    # Validate using Pydantic model
    try:
        input_data = MultiEditInput(
            path=path,
            edits=edits or []
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not input_data.edits:
        raise ValueError("At least one edit operation is required")
    
    summary = []
    
    for i, edit_change in enumerate(input_data.edits, start=1):
        # Get the path for this edit (use edit's path or fall back to base path)
        edit_path = edit_change.path or input_data.path
        
        if not edit_path:
            raise ValueError(f"Edit #{i} is missing 'path' and no base path provided")
        
        old_value = edit_change.old_string
        new_value = edit_change.new_string
        replace_all = edit_change.replace_all if edit_change.replace_all is not None else False
        
        try:
            res = edit_file(
                file_path=edit_path,
                old_string=old_value,
                new_string=new_value,
                replace_all=replace_all
            )
            result_obj = MultiEditResult(
                step=i,
                path=edit_path,
                success=True,
                message=res.message
            )
            summary.append(result_obj)
        except Exception as e:
            result_obj = MultiEditResult(
                step=i,
                path=edit_path,
                success=False,
                message=str(e)
            )
            summary.append(result_obj)
            raise IOError(f"Edit step {i} failed: {e}")
    
    output = MultiEditOutput(
        results=summary,
        total_edits=len(summary),
        successful_edits=len([s for s in summary if s.success])
    )
    return output


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
    
    # Convert dict entries to MultiEditChange objects
    edit_changes = []
    for entry in entries:
        if isinstance(entry, MultiEditChange):
            edit_changes.append(entry)
        elif isinstance(entry, dict):
            # Support legacy format with old_string/new_string or a/b
            edit_changes.append(MultiEditChange(
                path=entry.get("path"),
                old_string=entry.get("old_string", entry.get("a")),
                new_string=entry.get("new_string", entry.get("b")),
                replace_all=entry.get("replace_all", False)
            ))
        else:
            raise ValueError(f"Invalid edit entry: {entry}")
    
    result = multi_edit(path=base_path, edits=edit_changes)
    return result.model_dump()
