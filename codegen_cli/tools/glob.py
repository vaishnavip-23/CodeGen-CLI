# File Summary: Implementation of the Glob tool for path discovery.

"""
File Pattern Matching Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

This tool finds files matching glob patterns within the workspace.
It includes safety checks to prevent access outside the workspace.
"""

import os
import glob
from typing import Dict, Any, Optional

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import GlobInput, GlobOutput

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
                                  
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        
                                                   
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False


def find_files(pattern: str = "**/*", path: Optional[str] = None) -> GlobOutput:
    """Find files matching a glob pattern.
    
    Searches for files matching the specified glob pattern in the given directory or workspace.
    Use for finding specific file types or names.
    
    Args:
        pattern: Glob pattern to match files (e.g., '**/*.py' for all Python files, '**/*' for all files)
        path: The directory to search in (optional, defaults to current working directory)
        
    Returns:
        GlobOutput Pydantic model containing matching file paths, count, and search path.
    """
    # Validate using Pydantic model
    try:
        input_data = GlobInput(
            pattern=pattern,
            path=path
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    try:
        search_path = input_data.path if input_data.path else WORKSPACE
        full_pattern = os.path.join(search_path, input_data.pattern)
        
                             
        matches = glob.glob(full_pattern, recursive=True)
        
                                           
        safe_matches = []
        for match in matches:
            if is_safe_path(match):
                                               
                rel_path = os.path.relpath(match, WORKSPACE)
                safe_matches.append(rel_path)
        
                                            
        safe_matches.sort()
        
        output = GlobOutput(
            matches=safe_matches,
            count=len(safe_matches),
            search_path=search_path
        )
        return output
        
    except Exception as e:
        raise IOError(f"Error matching pattern: {e}")


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=find_files
    )


# Keep backward compatibility
def call(pattern: str = "**/*", *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    result = find_files(
        pattern=pattern,
        path=kwargs.get("path")
    )
    return result.model_dump()
