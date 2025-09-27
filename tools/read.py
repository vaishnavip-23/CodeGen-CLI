"""
Read tool - reads file contents safely within workspace.
"""

import os

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace."""
    try:
        abs_path = os.path.abspath(os.path.join(WORKSPACE, file_path))
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(path: str, *args, **kwargs) -> dict:
    """Read file contents with optional line limits."""
    offset = kwargs.get("offset")
    limit = kwargs.get("limit")
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()
        
        # Apply line limits
        if offset is not None or limit is not None:
            try:
                start_line = int(offset) if offset is not None else 0
                end_line = start_line + int(limit) if limit is not None else len(lines)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "output": f"Invalid offset or limit values. Expected integers, got offset={offset}, limit={limit}"
                }
            lines = lines[start_line:end_line]
        
        content = "".join(lines)
        return {
            "success": True, 
            "output": content
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error reading file: {e}"
        }