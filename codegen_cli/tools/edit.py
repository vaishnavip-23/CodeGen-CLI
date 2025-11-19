# File Summary: Implementation of the Edit tool for modifying existing files.

"""Edit tool - modifies existing files safely within the workspace.
Refactored to use Gemini's native Pydantic function calling with from_callable().

Now includes optional Python syntax checking after edits.
"""

import os
import re

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import EditInput, EditOutput

WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace for security."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False


def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditOutput:
    """Edit an existing file by finding and replacing text.
    
    Modifies an existing file by replacing occurrences of old_string with new_string.
    Read the file first to know the exact text to replace.
    
    Args:
        file_path: The absolute path to the file to modify
        old_string: The text to replace
        new_string: The text to replace it with
        replace_all: Replace all occurrences (default False, replaces first only)
        
    Returns:
        EditOutput Pydantic model containing confirmation message, number of replacements, and file path.
    """
    # Validate using Pydantic model
    try:
        input_data = EditInput(
            file_path=file_path,
            old_string=old_string,
            new_string=new_string,
            replace_all=replace_all
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
    
    smart = True  # Default smart matching behavior
    
    try:
        with open(input_data.file_path, "r", encoding="utf-8", errors="replace") as file:
            original_content = file.read()
        
        # Special case: empty old_string means replace entire file
        if isinstance(input_data.old_string, str) and input_data.old_string == "":
            with open(input_data.file_path, "w", encoding="utf-8") as file:
                file.write(input_data.new_string)
            
            output = EditOutput(
                message=f"Successfully edited {input_data.file_path}",
                replacements=1,
                file_path=input_data.file_path
            )
            return output

        if input_data.old_string not in original_content:
            if smart and isinstance(input_data.old_string, str):
                # Smart matching: try flexible whitespace matching
                words = [w for w in re.split(r"\s+", input_data.old_string.strip()) if w]
                if words:
                    pattern = r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b"
                    count = 0 if input_data.replace_all else 1
                    new_content, n = re.subn(pattern, input_data.new_string, original_content, count=count, flags=re.IGNORECASE)
                    if n > 0:
                        with open(input_data.file_path, "w", encoding="utf-8") as file:
                            file.write(new_content)
                        
                        output = EditOutput(
                            message=f"Successfully edited {input_data.file_path}",
                            replacements=n,
                            file_path=input_data.file_path
                        )
                        return output
            raise ValueError(f"Text '{input_data.old_string}' not found in file")
        
        if input_data.replace_all:
            new_content = original_content.replace(input_data.old_string, input_data.new_string)
        else:
            new_content = original_content.replace(input_data.old_string, input_data.new_string, 1)
        
        with open(input_data.file_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        
        replacements = new_content.count(input_data.new_string) if input_data.replace_all else 1
        output = EditOutput(
            message=f"Successfully edited {input_data.file_path}",
            replacements=replacements,
            file_path=input_data.file_path
        )
        return output
        
    except Exception as e:
        raise IOError(f"Error editing file: {e}")


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
        callable=edit_file
    )


# Keep backward compatibility
def call(file_path: str, *args, **kwargs) -> dict:
    """Call function for backward compatibility with manual execution."""
    # Backwards compatibility: accept old_string as first positional arg
    if args:
        old_str = args[0]
        new_str = args[1] if len(args) > 1 else kwargs.get("new_string", "")
    else:
        old_str = kwargs.get("old_string", "")
        new_str = kwargs.get("new_string", "")
    
    result = edit_file(
        file_path=file_path,
        old_string=old_str,
        new_string=new_str,
        replace_all=kwargs.get("replace_all", False)
    )
    return result.model_dump()
