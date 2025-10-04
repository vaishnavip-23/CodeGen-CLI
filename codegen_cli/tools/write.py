# File Summary: Implementation of the Write tool for creating or overwriting files.

"""
Write tool - creates or overwrites files safely within workspace.
"""

import os

try:
    from google.genai import types
except ImportError:
    types = None

WORKSPACE = os.getcwd()

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "write_file",
    "description": "Create a new file or overwrite an existing file with content. Use for creating new files only.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path where file should be created"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            }
        },
        "required": ["path", "content"]
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
                "path": types.Schema(type=types.Type.STRING, description="Path where file should be created"),
                "content": types.Schema(type=types.Type.STRING, description="Content to write to the file")
            },
            required=["path", "content"]
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
    """Write content to file, creating directories if needed."""
    # Get content from kwargs first, then args
    content = kwargs.get("content", "")
    if not content and args:
        content = " ".join(str(arg) for arg in args)
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    try:
        full_path = os.path.join(WORKSPACE, path)
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(str(content))
        
        rel_path = os.path.relpath(full_path, WORKSPACE)
        return {
            "success": True, 
            "output": f"Wrote to {rel_path}"
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error writing file: {e}"
        }
