"""
Edit tool - modifies existing files by replacing text safely within workspace.
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
    """Edit file by replacing text."""
    old_string = args[0] if len(args) > 0 else kwargs.get("old_string")
    new_string = args[1] if len(args) > 1 else kwargs.get("new_string")
    replace_all = kwargs.get("replace_all", False)
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    if old_string is None or new_string is None:
        return {
            "success": False, 
            "output": "Both old_string and new_string are required."
        }
    
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            original_content = file.read()
        
        if old_string not in original_content:
            return {
                "success": False, 
                "output": f"Text '{old_string}' not found in file."
            }
        
        if replace_all:
            new_content = original_content.replace(old_string, new_string)
        else:
            new_content = original_content.replace(old_string, new_string, 1)
        
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        
        rel_path = os.path.relpath(full_path, WORKSPACE)
        return {
            "success": True, 
            "output": f"Edited {rel_path}"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error editing file: {e}"
        }