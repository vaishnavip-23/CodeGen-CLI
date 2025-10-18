# File Summary: Implementation of the Grep tool for searching file contents.

"""
Grep tool - searches for text patterns in files using glob patterns.
"""

import os
import re
from glob import glob
from typing import List, Dict, Any

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import GrepInput, GrepMatch, GrepOutputContent, GrepOutputFiles

WORKSPACE = os.getcwd()

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "grep",
    "description": "Search for text patterns across files using regular expressions. Great for finding specific code patterns.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search pattern (regex supported)"
            },
            "path_pattern": {
                "type": "string",
                "description": "File pattern to search in (e.g., '**/*.py' for all Python files, default: '**/*.py')"
            },
            "output_mode": {
                "type": "string",
                "description": "Output format: 'content' (default), 'files_with_matches', or 'count'"
            }
        },
        "required": ["pattern"]
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
                "pattern": types.Schema(type=types.Type.STRING, description="Search pattern (regex supported)"),
                "path_pattern": types.Schema(type=types.Type.STRING, description="File pattern to search in (e.g., '**/*.py' for all Python files)"),
                "output_mode": types.Schema(type=types.Type.STRING, description="Output format: 'content', 'files_with_matches', or 'count'")
            },
            required=["pattern"]
        )
    )

def is_safe_path(file_path: str) -> bool:
    """Check if file path is within workspace."""
    try:
        abs_path = os.path.abspath(file_path)
        workspace_path = os.path.abspath(WORKSPACE)
        return os.path.commonpath([workspace_path, abs_path]) == workspace_path
    except (ValueError, OSError):
        return False

def search_in_file(file_path: str, pattern: str, multiline: bool = False) -> List[Dict[str, Any]]:
    """Search for pattern in a single file."""
    matches = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            if multiline:
                content = file.read()
                flags = re.MULTILINE | re.DOTALL
                for match in re.finditer(pattern, content, flags):
                    matches.append({
                        "file": file_path,
                        "line_number": content[:match.start()].count('\n') + 1,
                        "line": match.group(0).strip()
                    })
            else:
                for line_num, line in enumerate(file, 1):
                    if re.search(pattern, line):
                        matches.append({
                            "file": file_path,
                            "line_number": line_num,
                            "line": line.strip()
                        })
    except Exception:
        pass
    return matches

def call(pattern: str, *args, **kwargs) -> Dict[str, Any]:
    """Search for pattern in files matching path pattern."""
    try:
        input_data = GrepInput(
            pattern=pattern,
            path=kwargs.get("path"),
            glob=kwargs.get("glob"),
            type=kwargs.get("type"),
            output_mode=kwargs.get("output_mode", "content"),
            case_insensitive=kwargs.get("case_insensitive"),
            line_numbers=kwargs.get("line_numbers"),
            context_before=kwargs.get("context_before"),
            context_after=kwargs.get("context_after"),
            context=kwargs.get("context"),
            head_limit=kwargs.get("head_limit", 50),
            multiline=kwargs.get("multiline")
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    path_pattern = args[0] if len(args) > 0 else kwargs.get("path_pattern", "**/*.py")
    multiline = input_data.multiline if input_data.multiline else False
    
    try:
        search_path = os.path.join(WORKSPACE, path_pattern)
        files = glob(search_path, recursive=True)
        
        safe_files = [f for f in files if is_safe_path(f)]
        
        if not safe_files:
            raise FileNotFoundError("No files found matching pattern")
        
        all_matches = []
        for file_path in safe_files:
            matches = search_in_file(file_path, input_data.pattern, multiline)
            all_matches.extend(matches)
        
        if input_data.head_limit and len(all_matches) > input_data.head_limit:
            all_matches = all_matches[:input_data.head_limit]
        
        if input_data.output_mode == "files_with_matches":
            unique_files = list(set(match["file"] for match in all_matches))
            output = GrepOutputFiles(
                files=unique_files,
                count=len(unique_files)
            )
            return output.model_dump()
        else:
            grep_matches = [
                GrepMatch(
                    file=m["file"],
                    line_number=m.get("line_number"),
                    line=m.get("line", m.get("match", "")),
                    before_context=None,
                    after_context=None
                )
                for m in all_matches
            ]
            output = GrepOutputContent(
                matches=grep_matches,
                total_matches=len(grep_matches)
            )
            return output.model_dump()
        
    except Exception as e:
        raise IOError(f"Error searching files: {e}")
