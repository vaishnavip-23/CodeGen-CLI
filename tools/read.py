"""
Read Tool for CodeGen2

This tool reads the contents of files in the workspace.
It includes safety checks to prevent reading files outside the workspace.
"""

import os

# Get the current workspace directory
WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """
    Check if a file path is safe to access (within workspace).
    
    Args:
        file_path: Path to check
        
    Returns:
        True if safe, False if outside workspace
    """
    try:
        # Convert to absolute path
        abs_path = os.path.abspath(os.path.join(WORKSPACE, file_path))
        workspace_path = os.path.abspath(WORKSPACE)
        
        # Check if the file is within the workspace
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(path: str, *args, **kwargs) -> dict:
    """
    Read the contents of a file.
    
    Args:
        path: Path to the file to read (relative to workspace)
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments including:
            offset: Starting line number (0-based, optional)
            limit: Maximum number of lines to read (optional)
        
    Returns:
        Dictionary with success status and file contents
    """
    # Extract offset and limit from kwargs
    offset = kwargs.get("offset")
    limit = kwargs.get("limit")
    # Check if path is safe
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": f"Access denied: Path outside workspace not allowed."
        }
    
    # Check if file exists
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        # Read the file
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()
        
        # Apply offset and limit if specified
        if offset is not None or limit is not None:
            # Convert to integers if they're strings
            try:
                start_line = int(offset) if offset is not None else 0
                end_line = start_line + int(limit) if limit is not None else len(lines)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "output": f"Invalid offset or limit values. Expected integers, got offset={offset}, limit={limit}"
                }
            lines = lines[start_line:end_line]
        
        # Join lines into content
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
