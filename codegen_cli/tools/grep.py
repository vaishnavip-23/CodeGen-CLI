"""
Grep tool - searches for text patterns in files using glob patterns.
"""

import os
import re
from glob import glob
from typing import List, Dict, Any

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def search_in_file(file_path: str, pattern: str, multiline: bool = False) -> List[Dict[str, Any]]:
    """Search for pattern in a single file."""
    matches = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            if multiline:
                content = file.read()
                flags = re.MULTILINE | re.DOTALL
                for match in re.finditer(pattern, content, flags):
                    matches.append({
                        "file": file_path,
                        "line": content[:match.start()].count('\n') + 1,
                        "text": match.group(0).strip()
                    })
            else:
                for line_num, line in enumerate(file, 1):
                    if re.search(pattern, line):
                        matches.append({
                            "file": file_path,
                            "line": line_num,
                            "text": line.strip()
                        })
    except Exception:
        pass
    return matches

def call(pattern: str, *args, **kwargs) -> Dict[str, Any]:
    """Search for pattern in files matching path pattern."""
    path_pattern = args[0] if len(args) > 0 else kwargs.get("path_pattern", "**/*.py")
    head_limit = kwargs.get("head_limit", 50)
    output_mode = kwargs.get("output_mode", "content")
    multiline = kwargs.get("multiline", False)
    
    if not pattern:
        return {
            "tool": "grep",
            "success": False,
            "output": "Pattern is required"
        }
    
    try:
        # Find files matching pattern
        search_path = os.path.join(WORKSPACE, path_pattern)
        files = glob(search_path, recursive=True)
        
        # Filter to only safe paths
        safe_files = [f for f in files if is_safe_path(f)]
        
        if not safe_files:
            return {
                "tool": "grep",
                "success": True,
                "output": "No files found matching pattern"
            }
        
        # Search in files
        all_matches = []
        for file_path in safe_files:
            matches = search_in_file(file_path, pattern, multiline)
            all_matches.extend(matches)
        
        # Apply head limit
        if head_limit and len(all_matches) > head_limit:
            all_matches = all_matches[:head_limit]
        
        if output_mode == "files_with_matches":
            unique_files = list(set(match["file"] for match in all_matches))
            return {
                "tool": "grep",
                "success": True,
                "output": unique_files
            }
        elif output_mode == "count":
            return {
                "tool": "grep",
                "success": True,
                "output": len(all_matches)
            }
        else:  # content mode
            return {
                "tool": "grep",
                "success": True,
                "output": all_matches
            }
        
    except Exception as e:
        return {
            "tool": "grep",
            "success": False,
            "output": f"Error searching files: {e}"
        }