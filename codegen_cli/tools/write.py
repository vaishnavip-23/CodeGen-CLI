# File Summary: Implementation of the Write tool for creating or overwriting files.

"""
Write tool - creates or overwrites files safely within workspace.
"""

import os

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import WriteInput, WriteOutput

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace for security."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "write_file",
    "description": "Create a new file or overwrite an existing file with content. Use for creating new files only.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write"
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file"
            }
        },
        "required": ["file_path", "content"]
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
                "file_path": types.Schema(type=types.Type.STRING, description="The absolute path to the file to write"),
                "content": types.Schema(type=types.Type.STRING, description="The content to write to the file")
            },
            required=["file_path", "content"]
        )
    )

def call(file_path: str, *args, **kwargs) -> dict:
    """Write content to file, creating directories if needed."""
    try:
        input_data = WriteInput(
            file_path=file_path,
            content=kwargs.get("content", "")
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not os.path.isabs(input_data.file_path):
        workspace = os.getcwd()
        raise ValueError(f"file_path must be an absolute path. Got: '{input_data.file_path}'. Use: '{os.path.join(workspace, input_data.file_path)}'")
    
    if not is_safe_path(input_data.file_path):
        raise ValueError(f"Access denied: {input_data.file_path} is outside workspace")
    
    try:
        directory = os.path.dirname(input_data.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        with open(input_data.file_path, "w", encoding="utf-8") as file:
            file.write(input_data.content)
        
        bytes_written = len(input_data.content.encode('utf-8'))
        
        output = WriteOutput(
            message=f"Successfully wrote to {input_data.file_path}",
            bytes_written=bytes_written,
            file_path=input_data.file_path
        )
        
        return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Error writing file: {e}")
