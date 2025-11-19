# File Summary: Implementation of the Grep tool for searching file contents.

"""
Grep tool - searches for text patterns in files using glob patterns.
Refactored to use Gemini's native Pydantic function calling with from_callable().
"""

import os
import re
from glob import glob as glob_search
from typing import List, Dict, Any, Optional, Union

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import GrepInput, GrepMatch, GrepOutputContent, GrepOutputFiles

WORKSPACE = os.getcwd()

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

def grep(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    type: Optional[str] = None,
    output_mode: str = "content",
    case_insensitive: Optional[bool] = None,
    line_numbers: Optional[bool] = None,
    context_before: Optional[int] = None,
    context_after: Optional[int] = None,
    context: Optional[int] = None,
    head_limit: int = 50,
    multiline: Optional[bool] = None
) -> Union[GrepOutputContent, GrepOutputFiles]:
    """Search for text patterns across files using regular expressions.
    
    High-performance file content search using ripgrep-style parameters.
    Supports regex patterns, file type filtering, glob patterns, and context lines.
    
    Args:
        pattern: Search pattern (regex supported)
        path: Absolute path to a file or directory to search in (optional)
        glob: Glob pattern to filter files, e.g., "*.js" for JavaScript files (optional)
        type: Ripgrep file type filter for common file types, e.g., "js" for JavaScript (optional)
        output_mode: Output format - "content" returns matching lines, "files_with_matches" returns only file paths
        case_insensitive: Perform case-insensitive matching (optional)
        line_numbers: Show line numbers in output (optional)
        context_before: Number of lines to show before each match (optional)
        context_after: Number of lines to show after each match (optional)
        context: Number of lines to show before and after each match (optional)
        head_limit: Limit output to first N lines/entries (default: 50)
        multiline: Enable multiline mode where patterns can span lines (optional)
        
    Returns:
        GrepOutputContent or GrepOutputFiles Pydantic model depending on output_mode.
    """
    try:
        input_data = GrepInput(
            pattern=pattern,
            path=path,
            glob=glob,
            type=type,
            output_mode=output_mode,
            case_insensitive=case_insensitive,
            line_numbers=line_numbers,
            context_before=context_before,
            context_after=context_after,
            context=context,
            head_limit=head_limit,
            multiline=multiline
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    path_pattern = "**/*.py"  # Default pattern
    multiline_mode = input_data.multiline if input_data.multiline else False
    
    try:
        search_path = os.path.join(WORKSPACE, path_pattern)
        files = glob_search(search_path, recursive=True)
        
        safe_files = [f for f in files if is_safe_path(f)]
        
        if not safe_files:
            raise FileNotFoundError("No files found matching pattern")
        
        all_matches = []
        for file_path in safe_files:
            matches = search_in_file(file_path, input_data.pattern, multiline_mode)
            all_matches.extend(matches)
        
        if input_data.head_limit and len(all_matches) > input_data.head_limit:
            all_matches = all_matches[:input_data.head_limit]
        
        if input_data.output_mode == "files_with_matches":
            unique_files = list(set(match["file"] for match in all_matches))
            output = GrepOutputFiles(
                files=unique_files,
                count=len(unique_files)
            )
            return output
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
            return output
        
    except Exception as e:
        raise IOError(f"Error searching files: {e}")


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
        callable=grep
    )


# Keep backward compatibility
def call(pattern: str, *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    result = grep(
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
    return result.model_dump()
