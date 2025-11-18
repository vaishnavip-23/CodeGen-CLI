# File Summary: Implementation of the Read tool for inspecting file contents.

"""
Read tool - reads file contents safely within workspace.
Refactored to use Gemini's native Pydantic function calling with from_callable().
"""

import os
from typing import Optional

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import ReadInput, ReadOutput

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace for security."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False


def read_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> ReadOutput:
    """Read the contents of a file in the workspace.
    
    Use this to examine code, configuration, or any text file. Returns file contents
    with line numbers for easy reference.
    
    Args:
        file_path: The absolute path to the file to read
        offset: Line number to start reading from (0-based, optional)
        limit: Maximum number of lines to read (optional)
        
    Returns:
        A Pydantic model containing file content with line numbers, total lines, and lines returned.
    """
    # Validate using Pydantic model
    try:
        input_data = ReadInput(
            file_path=file_path,
            offset=offset,
            limit=limit
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not os.path.isabs(input_data.file_path):
        workspace = os.getcwd()
        raise ValueError(f"file_path must be an absolute path. Got: '{input_data.file_path}'. Use: '{os.path.join(workspace, input_data.file_path)}'")
    
    if not is_safe_path(input_data.file_path):
        raise ValueError(f"Access denied: {input_data.file_path} is outside workspace")
    
    if not os.path.exists(input_data.file_path):
        raise FileNotFoundError(f"File not found: {input_data.file_path}")
    
    try:
        with open(input_data.file_path, "r", encoding="utf-8", errors="replace") as file:
            all_lines = file.readlines()
        
        total_lines = len(all_lines)
        start_line = input_data.offset if input_data.offset is not None else 0
        end_line = start_line + input_data.limit if input_data.limit is not None else total_lines
        
        selected_lines = all_lines[start_line:end_line]
        
        content_with_line_numbers = ""
        for i, line in enumerate(selected_lines, start=start_line + 1):
            content_with_line_numbers += f"{i}: {line}"
        
        output = ReadOutput(
            content=content_with_line_numbers,
            total_lines=total_lines,
            lines_returned=len(selected_lines)
        )
        
        return output
        
    except Exception as e:
        raise IOError(f"Error reading file: {e}")


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    # Use from_callable to automatically generate schema from the function
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=read_file
    )


# Keep backward compatibility - the call function for manual execution
def call(file_path: str, *args, **kwargs) -> dict:
    """Call function for backward compatibility with manual execution."""
    result = read_file(
        file_path=file_path,
        offset=kwargs.get("offset"),
        limit=kwargs.get("limit")
    )
    return result.model_dump()
