# File Summary: Implementation of the Edit tool for modifying existing files.

"""Edit tool - modifies existing files safely within the workspace.

Now includes optional Python syntax checking after edits.
"""

import os
import py_compile
import re
import traceback

try:
    from google.genai import types
except ImportError:
    types = None

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "edit_file",
    "description": "Edit an existing file by finding and replacing text. Read the file first to know exact text to replace.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to file to edit"
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find and replace"
            },
            "new_string": {
                "type": "string",
                "description": "New text to insert"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)"
            }
        },
        "required": ["path", "old_string", "new_string"]
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
                "path": types.Schema(type=types.Type.STRING, description="Path to file to edit"),
                "old_string": types.Schema(type=types.Type.STRING, description="Exact text to find and replace"),
                "new_string": types.Schema(type=types.Type.STRING, description="New text to insert"),
                "replace_all": types.Schema(type=types.Type.BOOLEAN, description="Replace all occurrences (default: false)")
            },
            required=["path", "old_string", "new_string"]
        )
    )

def _check_python_syntax(file_path: str) -> dict:
    if not file_path.endswith(".py"):
        return {"checked": False}
    try:
        py_compile.compile(file_path, doraise=True)
        return {"checked": True, "ok": True}
    except py_compile.PyCompileError as exc:                                                 
        return {
            "checked": True,
            "ok": False,
            "error": str(exc),
            "details": exc.msg if hasattr(exc, "msg") else None,
        }
    except Exception as exc:                                
        return {
            "checked": True,
            "ok": False,
            "error": f"Unexpected compile error: {exc}",
            "traceback": traceback.format_exc(),
        }


WORKSPACE = os.getcwd()

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace."""
    try:
        abs_path = os.path.abspath(os.path.join(WORKSPACE, file_path))
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def call(path: str, *args, **kwargs) -> dict:
    """Edit file by replacing text."""
    old_string = args[0] if len(args) > 0 else kwargs.get("old_string")
    new_string = args[1] if len(args) > 1 else kwargs.get("new_string")
    replace_all = kwargs.get("replace_all", False)
    smart = kwargs.get("smart", True)
    skip_check = kwargs.get("skip_python_check", False)
    
    if not is_safe_path(path):
        return {
            "success": False, 
            "output": "Access denied: Path outside workspace not allowed."
        }
    
    if old_string is None or new_string is None:
        return {
            "success": False, 
            "output": "Both old_string and new_string are required."
        }
    
    full_path = os.path.join(WORKSPACE, path)
    if not os.path.exists(full_path):
        return {
            "success": False, 
            "output": f"File not found: {path}"
        }
    
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            original_content = file.read()
        
                                                                                         
        if isinstance(old_string, str) and old_string == "":
            with open(full_path, "w", encoding="utf-8") as file:
                file.write(new_string)
            rel_path = os.path.relpath(full_path, WORKSPACE)
            report = _check_python_syntax(full_path) if not skip_check else {"checked": False}
            if report.get("checked") and not report.get("ok", True):
                return {
                    "success": False,
                    "output": f"Edited {rel_path}, but syntax errors detected.",
                    "errors": report,
                }
            return {
                "success": True,
                "output": f"Edited {rel_path}",
                "python_check": report if report.get("checked") else None,
            }

        if old_string not in original_content:
            if smart and isinstance(old_string, str):
                                                                                                      
                words = [w for w in re.split(r"\s+", old_string.strip()) if w]
                if words:
                    pattern = r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b"
                    count = 0 if replace_all else 1
                    new_content, n = re.subn(pattern, new_string, original_content, count=count, flags=re.IGNORECASE)
                    if n > 0:
                        with open(full_path, "w", encoding="utf-8") as file:
                            file.write(new_content)
                        rel_path = os.path.relpath(full_path, WORKSPACE)
                        return {
                            "success": True,
                            "output": f"Edited {rel_path}"
                        }
            return {
                "success": False, 
                "output": f"Text '{old_string}' not found in file."
            }
        
        if replace_all:
            new_content = original_content.replace(old_string, new_string)
        else:
            new_content = original_content.replace(old_string, new_string, 1)
        
        with open(full_path, "w", encoding="utf-8") as file:
            file.write(new_content)
        
        rel_path = os.path.relpath(full_path, WORKSPACE)
        report = _check_python_syntax(full_path) if not skip_check else {"checked": False}
        if report.get("checked") and not report.get("ok", True):
            return {
                "success": False,
                "output": f"Edited {rel_path}, but syntax errors detected.",
                "errors": report,
            }
        return {
            "success": True,
            "output": f"Edited {rel_path}",
            "python_check": report if report.get("checked") else None,
        }
        
    except Exception as e:
        return {
            "success": False, 
            "output": f"Error editing file: {e}"
        }
