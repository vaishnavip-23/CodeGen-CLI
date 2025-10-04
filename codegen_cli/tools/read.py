# File Summary: Implementation of the Read tool for inspecting file contents.

"""
Read tool - reads file contents safely within workspace.
"""

import os

try:
    from google.genai import types
except ImportError:
    types = None

WORKSPACE = os.getcwd()

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "read_file",
    "description": "Read the contents of a file in the workspace. Use this to examine code, configuration, or any text file.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file from workspace root"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (0-based, optional)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (optional)"
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
                "path": types.Schema(type=types.Type.STRING, description="Relative path to the file from workspace root"),
                "offset": types.Schema(type=types.Type.INTEGER, description="Line number to start reading from (0-based, optional)"),
                "limit": types.Schema(type=types.Type.INTEGER, description="Maximum number of lines to read (optional)")
            },
            required=["path"]
        )
    )

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace."""
    try:
        abs_path = os.path.abspath(os.path.join(WORKSPACE, file_path))
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(path: str, *args, **kwargs) -> dict:
    """Read file contents with optional line limits."""
    offset = kwargs.get("offset")
    limit = kwargs.get("limit")
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            lines = file.readlines()
        
                           
        if offset is not None or limit is not None:
            try:
                start_line = int(offset) if offset is not None else 0
                end_line = start_line + int(limit) if limit is not None else len(lines)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "output": f"Invalid offset or limit values. Expected integers, got offset={offset}, limit={limit}"
                }
            lines = lines[start_line:end_line]
        
        content = "".join(lines)
        return {
            "success": True, 
            "output": content
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error reading file: {e}"
        }
