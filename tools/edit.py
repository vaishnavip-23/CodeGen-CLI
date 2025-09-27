"""
Edit Tool for CodeGen2

This tool modifies existing files by replacing text within them.
It includes safety checks to prevent editing files outside the workspace.
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
    Edit a file by replacing text.
    
    Args:
        path: Path to the file to edit (relative to workspace)
        *args: Additional positional arguments (old_string, new_string)
        **kwargs: Keyword arguments including:
            old_string: Text to find and replace
            new_string: Text to replace it with
            replace_all: If True, replace all occurrences; if False, replace only the first
        
    Returns:
        Dictionary with success status and message
    """
    # Extract parameters from args and kwargs
    old_string = args[0] if len(args) > 0 else kwargs.get("old_string")
    new_string = args[1] if len(args) > 1 else kwargs.get("new_string")
    replace_all = kwargs.get("replace_all", False)
    # Check if path is safe
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": f"Access denied: Path outside workspace not allowed."
        }
    
    # Validate required parameters
    if old_string is None or new_string is None:
        return {
            "success": False, 
            "output": "Both old_string and new_string are required."
        }
    
    # Check if file exists
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        # Read the current file content
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            original_content = file.read()
        
        # Check if old_string exists in the file
        if old_string not in original_content:
            return {
                "success": False, 
                "output": f"Text '{old_string}' not found in file."
            }
        
        # Perform the replacement
        if replace_all:
            new_content = original_content.replace(old_string, new_string)
        else:
            new_content = original_content.replace(old_string, new_string, 1)
        
        # Write the modified content back to the file
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        
        # Get relative path for display
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
