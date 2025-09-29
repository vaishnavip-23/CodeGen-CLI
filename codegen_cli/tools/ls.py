"""
List files tool - lists files and directories with filtering options.
"""

import os
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".env", 
    ".cache", ".pytest_cache", "dist", "build"
}

def read_gitignore_patterns(root: Path) -> List[str]:
    """Read .gitignore file and extract simple directory patterns."""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []
    
    patterns = []
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "/" not in line and "*" not in line:
                    patterns.append(line)
    except Exception:
        pass
    
    return patterns

def should_ignore_path(path: Path, ignore_set: set, show_hidden: bool) -> bool:
    """Check if a path should be ignored."""
    if not show_hidden and path.name.startswith("."):
        return True
    
    for part in path.parts:
        if part in ignore_set:
            return True
    
    return False

def walk_directory(root: Path, max_depth: int = None, ignore_set: set = None, show_hidden: bool = False) -> List[str]:
    """Walk through directory and collect file paths."""
    if ignore_set is None:
        ignore_set = DEFAULT_IGNORE_DIRS.copy()
    
    files = []
    
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            current_path = Path(dirpath)
            depth = len(current_path.relative_to(root).parts)
            
            if max_depth is not None and depth >= max_depth:
                dirnames.clear()
                continue
            
            dirnames[:] = [d for d in dirnames if d not in ignore_set]
            
            for filename in filenames:
                file_path = current_path / filename
                if not should_ignore_path(file_path, ignore_set, show_hidden):
                    rel_path = file_path.relative_to(root)
                    files.append(str(rel_path))
    
    except Exception:
        pass
    
    return sorted(files)

def call(path: str = ".", *args, **kwargs) -> Dict[str, Any]:
    """List files and directories in the specified path."""
    options = kwargs
    
    try:
        root_path = Path(path).resolve()
        
        if not root_path.exists():
            return {
                "tool": "ls",
                "success": False,
                "output": f"Path not found: {path}"
            }
        
        if not root_path.is_dir():
            return {
                "tool": "ls",
                "success": False,
                "output": f"Not a directory: {path}"
            }
        
        max_depth = options.get("depth")
        show_hidden = options.get("show_hidden", False)
        
        ignore_set = DEFAULT_IGNORE_DIRS.copy()
        custom_ignore = options.get("ignore", [])
        if isinstance(custom_ignore, list):
            ignore_set.update(custom_ignore)
        
        gitignore_patterns = read_gitignore_patterns(root_path)
        ignore_set.update(gitignore_patterns)
        
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