# File Summary: Implementation of the Glob tool for path discovery.

"""
File Pattern Matching Tool for CodeGen-CLI

This tool finds files matching glob patterns within the workspace.
It includes safety checks to prevent access outside the workspace.
"""

import os
import glob
from typing import Dict, Any

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import GlobInput, GlobOutput

WORKSPACE = os.getcwd()

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "find_files",
    "description": "Find files using glob patterns. Use for finding specific file types or names.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g., '**/*.py' for all Python files, default: '**/*')"
            }
        },
        "required": []
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
                "pattern": types.Schema(type=types.Type.STRING, description="Glob pattern (e.g., '**/*.py' for all Python files)")
            },
            required=[]
        )
    )

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
        input_data = GlobInput(
            pattern=pattern,
            path=kwargs.get("path")
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
        return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Error matching pattern: {e}")
