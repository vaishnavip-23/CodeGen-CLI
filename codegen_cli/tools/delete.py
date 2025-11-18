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

from ..models.schema import DeleteInput, DeleteOutput

WORKSPACE = Path(os.getcwd())

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "delete_file",
    "description": "Delete a file or directory (including all contents). Directories are deleted recursively with all files inside. Use with caution - this is destructive and cannot be undone.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to file or directory to delete. If directory, all contents will be deleted recursively."
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
                "path": types.Schema(type=types.Type.STRING, description="Path to file or directory to delete. If directory, all contents will be deleted recursively.")
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
    if not path:
        raise ValueError("Path is required")
    
    try:
        input_data = DeleteInput(path=path)
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not is_safe_path(input_data.path):
        raise ValueError(f"Path '{input_data.path}' is outside workspace. Deletion not allowed.")
    
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
        output = DeleteOutput(
            message="\n".join(deleted),
            deleted_items=deleted,
            count=len(deleted)
        )
        return output.model_dump()

    raise IOError("Deletion cancelled." if skipped else "No deletions performed.")
