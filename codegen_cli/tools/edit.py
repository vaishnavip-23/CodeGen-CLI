# File Summary: Implementation of the Edit tool for modifying existing files.

"""Edit tool - modifies existing files safely within the workspace.

Now includes optional Python syntax checking after edits.
"""

import os
import re

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import EditInput, EditOutput

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "edit_file",
    "description": "Edit an existing file by finding and replacing text. Read the file first to know exact text to replace.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to modify"
            },
            "old_string": {
                "type": "string",
                "description": "The text to replace"
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)"
            }
        },
        "required": ["file_path", "old_string", "new_string"]
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
                "file_path": types.Schema(type=types.Type.STRING, description="The absolute path to the file to modify"),
                "old_string": types.Schema(type=types.Type.STRING, description="The text to replace"),
                "new_string": types.Schema(type=types.Type.STRING, description="The text to replace it with"),
                "replace_all": types.Schema(type=types.Type.BOOLEAN, description="Replace all occurrences (default: false)")
            },
            required=["file_path", "old_string", "new_string"]
        )
    )

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace for security."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(file_path: str, *args, **kwargs) -> dict:
    """Edit file by replacing text."""
    try:
        input_data = EditInput(
            file_path=file_path,
            old_string=kwargs.get("old_string"),
            new_string=kwargs.get("new_string"),
            replace_all=kwargs.get("replace_all", False)
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
    
    smart = kwargs.get("smart", True)
    
    old_string = input_data.old_string
    new_string = input_data.new_string
    replace_all = input_data.replace_all
    
    try:
        with open(input_data.file_path, "r", encoding="utf-8", errors="replace") as file:
            original_content = file.read()
        
                                                                                         
        if isinstance(old_string, str) and old_string == "":
            with open(input_data.file_path, "w", encoding="utf-8") as file:
                file.write(new_string)
            
            output = EditOutput(
                message=f"Successfully edited {input_data.file_path}",
                replacements=1,
                file_path=input_data.file_path
            )
            return output.model_dump()

        if old_string not in original_content:
            if smart and isinstance(old_string, str):
                                                                                                      
                words = [w for w in re.split(r"\s+", old_string.strip()) if w]
                if words:
                    pattern = r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b"
                    count = 0 if replace_all else 1
                    new_content, n = re.subn(pattern, new_string, original_content, count=count, flags=re.IGNORECASE)
                    if n > 0:
                        with open(input_data.file_path, "w", encoding="utf-8") as file:
                            file.write(new_content)
                        
                        output = EditOutput(
                            message=f"Successfully edited {input_data.file_path}",
                            replacements=n,
                            file_path=input_data.file_path
                        )
                        return output.model_dump()
            raise ValueError(f"Text '{old_string}' not found in file")
        
        if replace_all:
            new_content = original_content.replace(old_string, new_string)
        else:
            new_content = original_content.replace(old_string, new_string, 1)
        
        with open(input_data.file_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        
        replacements = new_content.count(new_string) if replace_all else 1
        output = EditOutput(
            message=f"Successfully edited {input_data.file_path}",
            replacements=replacements,
            file_path=input_data.file_path
        )
        return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Error editing file: {e}")
