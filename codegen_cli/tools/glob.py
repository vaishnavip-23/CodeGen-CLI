"""
File Pattern Matching Tool for CodeGen2

This tool finds files matching glob patterns within the workspace.
It includes safety checks to prevent access outside the workspace.
"""

import os
import glob
from typing import List, Dict, Any

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
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        
        # Check if the file is within the workspace
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(pattern: str = "**/*", *args, **kwargs) -> Dict[str, Any]:
    """
    Find files matching the given glob pattern.
    
    Args:
        pattern: Glob pattern to match files (default: "**/*" for all files)
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments (ignored for now)
        
    Returns:
        Dictionary with success status and list of matching files
    """
    try:
        # Create full pattern path
        full_pattern = os.path.join(WORKSPACE, pattern)
        
        # Find matching files
        matches = glob.glob(full_pattern, recursive=True)
        
        # Filter to only include safe paths
        safe_matches = []
        for match in matches:
            if is_safe_path(match):
                # Get relative path for display
                rel_path = os.path.relpath(match, WORKSPACE)
                safe_matches.append(rel_path)
        
        # Sort results for consistent output
        safe_matches.sort()
        
        return {
            "tool": "glob",
            "success": True,
            "output": safe_matches,
            "meta": {
                "pattern": pattern,
                "matches_found": len(safe_matches)
            }
        }
        
    except Exception as e:
        return {
            "tool": "glob",
            "success": False,
            "output": f"Error matching pattern: {e}"
        }
