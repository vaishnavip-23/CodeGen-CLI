"""
Delete Tool for CodeGen2

This tool safely deletes files and directories within the workspace.
It includes safety checks to prevent accidental deletion outside the workspace.
"""

import os
import shutil
from typing import Dict, Any
from pathlib import Path

# Get workspace path
WORKSPACE = os.getcwd()

def is_safe_path(path: str) -> bool:
    """
    Check if the path is safe to delete (within workspace).
    
    Args:
        path: Path to check
        
    Returns:
        True if safe, False otherwise
    """
    try:
        # Convert to absolute path
        abs_path = os.path.abspath(path)
        abs_workspace = os.path.abspath(WORKSPACE)
        
        # Check if path is within workspace
        return abs_path.startswith(abs_workspace)
    except Exception:
        return False

def call(path: str, *args, **kwargs) -> Dict[str, Any]:
    """
    Delete a file or directory.
    
    Args:
        path: Path to delete
        *args: Additional arguments (ignored)
        **kwargs: Additional keyword arguments (ignored)
        
    Returns:
        Dictionary with success status and result
    """
    # Validate path
    if not path or not isinstance(path, str):
        return {
            "tool": "delete",
            "success": False,
            "output": "Path is required and must be a string.",
            "args": [path],
            "kwargs": kwargs
        }
    
    # Check if path is safe
    if not is_safe_path(path):
        return {
            "tool": "delete",
            "success": False,
            "output": f"Path '{path}' is outside workspace. Deletion not allowed.",
            "args": [path],
            "kwargs": kwargs
        }
    
    # Check if path exists
    if not os.path.exists(path):
        return {
            "tool": "delete",
            "success": False,
            "output": f"Path '{path}' does not exist.",
            "args": [path],
            "kwargs": kwargs
        }
    
    try:
        # Delete file or directory
        if os.path.isfile(path):
            os.remove(path)
            result_msg = f"Deleted file: {path}"
        elif os.path.isdir(path):
            shutil.rmtree(path)
            result_msg = f"Deleted directory: {path}"
        else:
            return {
                "tool": "delete",
                "success": False,
                "output": f"Path '{path}' is neither a file nor directory.",
                "args": [path],
                "kwargs": kwargs
            }
        
        return {
            "tool": "delete",
            "success": True,
            "output": result_msg,
            "args": [path],
            "kwargs": kwargs
        }
        
    except PermissionError:
        return {
            "tool": "delete",
            "success": False,
            "output": f"Permission denied: Cannot delete '{path}'",
            "args": [path],
            "kwargs": kwargs
        }
    except OSError as e:
        return {
            "tool": "delete",
            "success": False,
            "output": f"OS error: {e}",
            "args": [path],
            "kwargs": kwargs
        }
    except Exception as e:
        return {
            "tool": "delete",
            "success": False,
            "output": f"Unexpected error: {e}",
            "args": [path],
            "kwargs": kwargs
        }
