"""
List Files Tool for CodeGen2

This tool lists files and directories in the workspace.
It includes options for recursive listing, ignoring common directories,
and showing hidden files.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

# Default directories to ignore when listing files
DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".env", 
    ".cache", ".pytest_cache", ".pytest_cache", "dist", "build"
}

def read_gitignore_patterns(root: Path) -> List[str]:
    """
    Read .gitignore file and extract simple directory patterns.
    
    Args:
        root: Root directory to look for .gitignore
        
    Returns:
        List of directory names to ignore
    """
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []
    
    patterns = []
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Only include simple directory names (no complex patterns)
                if line and not line.startswith("#") and "/" not in line and "*" not in line:
                    patterns.append(line)
    except Exception:
        pass
    
    return patterns

def should_ignore_path(path: Path, ignore_set: set, show_hidden: bool) -> bool:
    """
    Check if a path should be ignored based on ignore rules.
    
    Args:
        path: Path to check
        ignore_set: Set of directory names to ignore
        show_hidden: Whether to show hidden files/directories
        
    Returns:
        True if path should be ignored
    """
    # Check if it's a hidden file/directory
    if not show_hidden and path.name.startswith("."):
        return True
    
    # Check if any parent directory is in ignore set
    for part in path.parts:
        if part in ignore_set:
            return True
    
    return False

def walk_directory(root: Path, max_depth: int = None, ignore_set: set = None, show_hidden: bool = False) -> List[str]:
    """
    Walk through directory and collect file paths.
    
    Args:
        root: Root directory to start from
        max_depth: Maximum depth to recurse (None = unlimited)
        ignore_set: Set of directory names to ignore
        show_hidden: Whether to show hidden files
        
    Returns:
        List of relative file paths
    """
    if ignore_set is None:
        ignore_set = DEFAULT_IGNORE_DIRS.copy()
    
    files = []
    
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Convert to Path object for easier manipulation
            current_path = Path(dirpath)
            
            # Calculate current depth
            depth = len(current_path.relative_to(root).parts)
            
            # Check depth limit
            if max_depth is not None and depth >= max_depth:
                # Remove subdirectories to prevent going deeper
                dirnames.clear()
                continue
            
            # Remove ignored directories from traversal
            dirnames[:] = [d for d in dirnames if d not in ignore_set]
            
            # Add files
            for filename in filenames:
                file_path = current_path / filename
                if not should_ignore_path(file_path, ignore_set, show_hidden):
                    # Get relative path from root
                    rel_path = file_path.relative_to(root)
                    files.append(str(rel_path))
    
    except Exception:
        # If walking fails, return empty list
        pass
    
    return sorted(files)

def call(path: str = ".", *args, **kwargs) -> Dict[str, Any]:
    """
    List files and directories in the specified path.
    
    Args:
        path: Directory path to list (default: current directory)
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments including:
            - depth: Maximum recursion depth (None = unlimited)
            - ignore: List of directory names to ignore
            - show_hidden: Whether to show hidden files (default: False)
        
    Returns:
        Dictionary with success status and file list
    """
    # Use kwargs as options
    options = kwargs
    
    try:
        # Convert path to Path object
        root_path = Path(path).resolve()
        
        # Check if path exists
        if not root_path.exists():
            return {
                "tool": "ls",
                "success": False,
                "output": f"Path not found: {path}"
            }
        
        # Check if it's a directory
        if not root_path.is_dir():
            return {
                "tool": "ls",
                "success": False,
                "output": f"Not a directory: {path}"
            }
        
        # Get options
        max_depth = options.get("depth")
        show_hidden = options.get("show_hidden", False)
        
        # Build ignore set
        ignore_set = DEFAULT_IGNORE_DIRS.copy()
        custom_ignore = options.get("ignore", [])
        if isinstance(custom_ignore, list):
            ignore_set.update(custom_ignore)
        
        # Add .gitignore patterns
        gitignore_patterns = read_gitignore_patterns(root_path)
        ignore_set.update(gitignore_patterns)
        
        # Walk directory and collect files
        files = walk_directory(root_path, max_depth, ignore_set, show_hidden)
        
        return {
            "tool": "ls",
            "success": True,
            "output": files
        }
        
    except Exception as e:
        return {
            "tool": "ls",
            "success": False,
            "output": f"Error listing directory: {e}"
        }
