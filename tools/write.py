"""
Write Tool for CodeGen2

This tool creates new files or overwrites existing files in the workspace.
It includes safety checks to prevent writing files outside the workspace.
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
    Write content to a file.
    
    Args:
        path: Path to the file to write (relative to workspace)
        *args: Additional positional arguments (content will be joined)
        **kwargs: Keyword arguments (ignored for now)
        
    Returns:
        Dictionary with success status and message
    """
    # Join all args as content, or use empty string if no args
    content = " ".join(str(arg) for arg in args) if args else ""
    # Check if path is safe
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": f"Access denied: Path outside workspace not allowed."
        }
    
    try:
        # Create directory if it doesn't exist
        full_path = os.path.join(WORKSPACE, path)
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # Write the file
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(str(content))
        
        # Get relative path for display
        rel_path = os.path.relpath(full_path, WORKSPACE)
        
        return {
            "success": True, 
            "output": f"Wrote to {rel_path}"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error writing file: {e}"
        }
