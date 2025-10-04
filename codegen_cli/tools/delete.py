# File Summary: Implementation of the Delete tool for removing files and directories.

"""Delete tool with glob discovery and confirmation safeguards."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

try:
    from google.genai import types
except ImportError:
    types = None

WORKSPACE = Path(os.getcwd())

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "delete_file",
    "description": "Delete a file or directory. Use with caution - this is destructive.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to file or directory to delete"
            }
        },
        "required": ["path"]
    }
}

def get_function_declaration():
    """Get Gemini function declaration for this tool."""
    if types is None:
        return None
    
    return types.FunctionDeclaration(
        name=FUNCTION_DECLARATION["name"],
        description=FUNCTION_DECLARATION["description"],
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "path": types.Schema(type=types.Type.STRING, description="Path to file or directory to delete")
            },
            required=["path"]
        )
    )


def _paths_for_pattern(pattern: str) -> List[Path]:
    candidate = WORKSPACE / pattern
    if candidate.exists():
        return [candidate]

    glob_pattern = pattern
    if not any(ch in pattern for ch in "*?[]"):
        glob_pattern = f"**/{pattern}"
    return list(WORKSPACE.glob(glob_pattern))

def is_safe_path(path: str) -> bool:
    """
    Check if the path is safe to delete (within workspace).
    
    Args:
        path: Path to check
        
    Returns:
        True if safe, False otherwise
    """
    try:
        abs_path = os.path.abspath(path)
        abs_workspace = str(WORKSPACE)
        return abs_path.startswith(abs_workspace)
    except Exception:
        return False

def call(path: str = None, *args, **kwargs) -> Dict[str, Any]:
    """
    Delete a file or directory.
    
    Args:
        path: Path to delete
        *args: Additional arguments (ignored)
        **kwargs: Additional keyword arguments (ignored)
        
    Returns:
        Dictionary with success status and result
    """
                                                                
    suggested = kwargs.pop("suggested_path", None)

                   
    if (not path or not isinstance(path, str)) and not suggested:
        return {
            "tool": "delete",
            "success": False,
            "output": "Path is required. If you meant a file by name, try specifying it.",
            "args": [path],
            "kwargs": kwargs
        }

                                                                                     
    if (not path or not isinstance(path, str)) and suggested:
        try:
            ans = input(f"Did you mean to delete '{suggested}'? (y/n) ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans not in ("y", "yes"):
            return {"tool": "delete", "success": False, "output": "Deletion cancelled.", "args": [suggested], "kwargs": {}}
        path = suggested
    
                           
    if not is_safe_path(path):
        return {
            "tool": "delete",
            "success": False,
            "output": f"Path '{path}' is outside workspace. Deletion not allowed.",
            "args": [path],
            "kwargs": kwargs
        }
    
    matches = _paths_for_pattern(path)
    if not matches:
        return {
            "tool": "delete",
            "success": False,
            "output": f"No matches found for '{path}'.",
            "args": [path],
            "kwargs": kwargs,
        }

    confirmations = []
    deleted = []
    skipped = []
    # Check for confirmation bypass from kwargs or environment
    auto_confirm = kwargs.get("confirm", False) or os.environ.get("CODEGEN_AUTO_CONFIRM") == "1"

    for match in matches:
        rel = match.relative_to(WORKSPACE)
        if not auto_confirm:
            try:
                ans = input(f"Delete '{rel}'? (y/n) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
        else:
            ans = "y"
        confirmations.append({"path": str(rel), "answer": ans})
        if ans not in ("y", "yes"):
            skipped.append(str(rel))
            continue

        target = match
        try:
            if target.is_file():
                target.unlink()
                deleted.append(f"Deleted file: {rel}")
            elif target.is_dir():
                shutil.rmtree(target)
                deleted.append(f"Deleted directory: {rel}")
            else:
                skipped.append(str(rel))
        except PermissionError:
            skipped.append(f"Permission denied: {rel}")
        except OSError as exc:
            skipped.append(f"OS error for {rel}: {exc}")
        except Exception as exc:                                
            skipped.append(f"Unexpected error for {rel}: {exc}")

    if deleted:
        return {
            "tool": "delete",
            "success": True,
            "output": "\n".join(deleted),
            "confirmations": confirmations,
            "skipped": skipped,
        }

    return {
        "tool": "delete",
        "success": False,
        "output": "Deletion cancelled." if skipped else "No deletions performed.",
        "confirmations": confirmations,
        "skipped": skipped,
    }
