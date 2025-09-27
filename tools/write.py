"""
Write tool - creates or overwrites files safely within workspace.
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
    """Write content to file, creating directories if needed."""
    content = " ".join(str(arg) for arg in args) if args else ""
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    try:
        full_path = os.path.join(WORKSPACE, path)
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(str(content))
        
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