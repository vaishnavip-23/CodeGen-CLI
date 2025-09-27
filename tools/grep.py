"""
Search Tool for CodeGen2

This tool searches for text patterns in files within the workspace.
It supports glob patterns for file selection and includes safety checks.
"""

import os
import re
from glob import glob
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

def find_matching_files(path_pattern: str) -> List[str]:
    """
    Find files matching the given glob pattern.
    
    Args:
        path_pattern: Glob pattern to match files
        
    Returns:
        List of file paths that match the pattern and are safe to access
    """
    # Create full pattern path
    full_pattern = os.path.join(WORKSPACE, path_pattern)
    
    # Find matching files
    matches = glob(full_pattern, recursive=True)
    
    # Filter to only include files (not directories) and safe paths
    safe_files = []
    for match in matches:
        if (os.path.isfile(match) and 
            is_safe_path(match) and 
            os.path.commonpath([WORKSPACE, os.path.normpath(match)]) == WORKSPACE):
            safe_files.append(match)
    
    return safe_files

def search_in_file(file_path: str, pattern: str, max_matches: int = 50) -> List[Dict[str, Any]]:
    """
    Search for pattern in a single file.
    
    Args:
        file_path: Path to the file to search
        pattern: Text pattern to search for
        max_matches: Maximum number of matches to return
        
    Returns:
        List of match dictionaries with line number and text
    """
    matches = []
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            for line_number, line in enumerate(file, start=1):
                if pattern in line:
                    matches.append({
                        "line": line_number,
                        "text": line.rstrip("\n")
                    })
                    
                    # Stop if we've found enough matches
                    if len(matches) >= max_matches:
                        break
    except Exception:
        # If we can't read the file, return empty list
        pass
    
    return matches

def call(pattern: str, *args, **kwargs) -> Dict[str, Any]:
    """
    Search for a pattern in files matching the given path pattern.
    
    Args:
        pattern: Text pattern to search for
        *args: Additional positional arguments (first one used as path_pattern)
        **kwargs: Keyword arguments including:
            path_pattern: Glob pattern for files to search (default: "**/*.py")
            head_limit: Maximum number of matches per file (default: 50)
            output_mode: Output format (default: "content")
            multiline: Whether to use multiline search (default: False)
        
    Returns:
        Dictionary with success status and search results
    """
    # Extract parameters from args and kwargs
    path_pattern = args[0] if len(args) > 0 else kwargs.get("path_pattern", "**/*.py")
    head_limit = kwargs.get("head_limit", 50)
    output_mode = kwargs.get("output_mode", "content")
    multiline = kwargs.get("multiline", False)
    # Validate inputs
    if not pattern:
        return {
            "tool": "grep",
            "success": False,
            "output": "Search pattern cannot be empty."
        }
    
    try:
        # Find files matching the pattern
        matching_files = find_matching_files(path_pattern)
        
        if not matching_files:
            return {
                "tool": "grep",
                "success": True,
                "output": "No files found matching the pattern."
            }
        
        # Search in each file
        results = {}
        total_matches = 0
        
        for file_path in matching_files:
            # Get relative path for display
            rel_path = os.path.relpath(file_path, WORKSPACE)
            
            # Search for pattern in file
            matches = search_in_file(file_path, pattern, head_limit)
            
            if matches:
                results[rel_path] = matches
                total_matches += len(matches)
        
        # Return results
        if not results:
            return {
                "tool": "grep",
                "success": True,
                "output": f"No matches found for '{pattern}' in {len(matching_files)} files."
            }
        
        return {
            "tool": "grep",
            "success": True,
            "output": results,
            "meta": {
                "pattern": pattern,
                "files_searched": len(matching_files),
                "files_with_matches": len(results),
                "total_matches": total_matches
            }
        }
        
    except Exception as e:
        return {
            "tool": "grep",
            "success": False,
            "output": f"Error during search: {e}"
        }
