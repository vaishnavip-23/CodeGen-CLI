"""
Centralized schemas for all CodeGen CLI tools.

All input and output schemas using Pydantic models.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# READ TOOL
# ============================================================================

class ReadInput(BaseModel):
    """Input schema for the Read tool."""
    file_path: str = Field(..., description="The absolute path to the file to read")
    offset: Optional[int] = Field(None, description="The line number to start reading from (0-based)")
    limit: Optional[int] = Field(None, description="The number of lines to read")
    
    @field_validator('offset', 'limit')
    @classmethod
    def validate_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("offset and limit must be non-negative")
        return v


class ReadOutput(BaseModel):
    """Output schema for the Read tool."""
    content: str = Field(..., description="File contents with line numbers")
    total_lines: int = Field(..., description="Total number of lines in file")
    lines_returned: int = Field(..., description="Lines actually returned")


# ============================================================================
# WRITE TOOL
# ============================================================================

class WriteInput(BaseModel):
    """Input schema for the Write tool."""
    file_path: str = Field(..., description="The absolute path to the file to write")
    content: str = Field(..., description="The content to write to the file")


class WriteOutput(BaseModel):
    """Output schema for the Write tool."""
    message: str = Field(..., description="Success message")
    bytes_written: int = Field(..., description="Number of bytes written")
    file_path: str = Field(..., description="File path that was written")


# ============================================================================
# EDIT TOOL
# ============================================================================

class EditInput(BaseModel):
    """Input schema for the Edit tool."""
    file_path: str = Field(..., description="The absolute path to the file to modify")
    old_string: str = Field(..., description="The text to replace")
    new_string: str = Field(..., description="The text to replace it with")
    replace_all: Optional[bool] = Field(False, description="Replace all occurrences (default False)")


class EditOutput(BaseModel):
    """Output schema for the Edit tool."""
    message: str = Field(..., description="Confirmation message")
    replacements: int = Field(..., description="Number of replacements made")
    file_path: str = Field(..., description="File path that was edited")


# ============================================================================
# DELETE TOOL
# ============================================================================

class DeleteInput(BaseModel):
    """Input schema for the Delete tool."""
    path: str = Field(..., description="Path to file or directory to delete")


class DeleteOutput(BaseModel):
    """Output schema for the Delete tool."""
    message: str = Field(..., description="Success message")
    deleted_items: List[str] = Field(..., description="List of deleted items")
    count: int = Field(..., description="Number of items deleted")


# ============================================================================
# BASH TOOL
# ============================================================================

class BashInput(BaseModel):
    """Input schema for the Bash tool."""
    command: str = Field(..., description="The command to execute")
    timeout: Optional[int] = Field(None, description="Optional timeout in milliseconds (max 600000)")
    description: Optional[str] = Field(None, description="Clear, concise description (5-10 words)")
    run_in_background: Optional[bool] = Field(False, description="Set to true to run in background")


class BashOutput(BaseModel):
    """Output schema for the Bash tool."""
    output: str = Field(..., description="Combined stdout and stderr output")
    exitCode: int = Field(..., description="Exit code of the command")
    killed: Optional[bool] = Field(None, description="Whether command was killed due to timeout")
    shellId: Optional[str] = Field(None, description="Shell ID for background processes")


# ============================================================================
# GLOB TOOL
# ============================================================================

class GlobInput(BaseModel):
    """Input schema for the Glob tool."""
    pattern: str = Field(..., description="The glob pattern to match files against")
    path: Optional[str] = Field(None, description="The directory to search in (defaults to cwd)")


class GlobOutput(BaseModel):
    """Output schema for the Glob tool."""
    matches: List[str] = Field(..., description="Array of matching file paths")
    count: int = Field(..., description="Number of matches found")
    search_path: str = Field(..., description="Search directory used")


# ============================================================================
# GREP TOOL
# ============================================================================

class GrepInput(BaseModel):
    """Input schema for the Grep tool."""
    pattern: str = Field(..., description="The regular expression pattern")
    path: Optional[str] = Field(None, description="File or directory to search in")
    glob: Optional[str] = Field(None, description="Glob pattern to filter files")
    type: Optional[str] = Field(None, description="File type to search")
    output_mode: Optional[str] = Field(None, description="'content', 'files_with_matches', or 'count'")
    case_insensitive: Optional[bool] = Field(None, description="Case insensitive search")
    line_numbers: Optional[bool] = Field(None, description="Show line numbers")
    context_before: Optional[int] = Field(None, description="Lines to show before each match")
    context_after: Optional[int] = Field(None, description="Lines to show after each match")
    context: Optional[int] = Field(None, description="Lines to show before and after")
    head_limit: Optional[int] = Field(None, description="Limit output to first N lines/entries")
    multiline: Optional[bool] = Field(None, description="Enable multiline mode")


class GrepMatch(BaseModel):
    """Single match result in Grep output."""
    file: str = Field(..., description="File path")
    line_number: Optional[int] = Field(None, description="Line number")
    line: str = Field(..., description="Matching line")
    before_context: Optional[List[str]] = Field(None, description="Lines before match")
    after_context: Optional[List[str]] = Field(None, description="Lines after match")


class GrepOutputContent(BaseModel):
    """Output schema for Grep tool (content mode)."""
    matches: List[GrepMatch] = Field(..., description="List of matches")
    total_matches: int = Field(..., description="Total number of matches")


class GrepOutputFiles(BaseModel):
    """Output schema for Grep tool (files_with_matches mode)."""
    files: List[str] = Field(..., description="Files containing matches")
    count: int = Field(..., description="Number of files with matches")


# ============================================================================
# LS TOOL
# ============================================================================

class LsInput(BaseModel):
    """Input schema for the LS tool."""
    path: Optional[str] = Field(".", description="Directory path to list (default: '.')")
    depth: Optional[int] = Field(None, description="Maximum depth to traverse")
    show_hidden: Optional[bool] = Field(False, description="Show hidden files")


class LsOutput(BaseModel):
    """Output schema for the LS tool."""
    files: List[str] = Field(..., description="List of files and directories")
    count: int = Field(..., description="Number of items")
    path: str = Field(..., description="Path that was listed")


# ============================================================================
# MULTIEDIT TOOL
# ============================================================================

class MultiEditChange(BaseModel):
    """Single edit change in MultiEdit."""
    path: Optional[str] = Field(None, description="File path (overrides base path)")
    old_string: str = Field(..., description="Text to find")
    new_string: str = Field(..., description="Replacement text")
    replace_all: Optional[bool] = Field(False, description="Replace all occurrences")


class MultiEditInput(BaseModel):
    """Input schema for the MultiEdit tool."""
    path: Optional[str] = Field(None, description="Base file path (if all edits are to same file)")
    edits: List[MultiEditChange] = Field(..., description="List of edits to apply")


class MultiEditResult(BaseModel):
    """Single edit result in MultiEdit output."""
    step: int = Field(..., description="Edit step number")
    path: str = Field(..., description="File path")
    success: bool = Field(..., description="Whether edit succeeded")
    message: str = Field(..., description="Result message")


class MultiEditOutput(BaseModel):
    """Output schema for the MultiEdit tool."""
    results: List[MultiEditResult] = Field(..., description="Results for each edit")
    total_edits: int = Field(..., description="Total number of edits attempted")
    successful_edits: int = Field(..., description="Number of successful edits")


# ============================================================================
# WEBSEARCH TOOL
# ============================================================================

class WebSearchInput(BaseModel):
    """Input schema for the WebSearch tool."""
    query: str = Field(..., description="The search query to use")
    allowed_domains: Optional[List[str]] = Field(None, description="Only include results from these domains")
    blocked_domains: Optional[List[str]] = Field(None, description="Never include results from these domains")


class WebSearchResult(BaseModel):
    """Single search result."""
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(..., description="Result snippet/description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WebSearchOutput(BaseModel):
    """Output schema for the WebSearch tool."""
    results: List[WebSearchResult] = Field(..., description="List of search results")
    total_results: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Search query used")


# ============================================================================
# WEBFETCH TOOL
# ============================================================================

class WebFetchInput(BaseModel):
    """Input schema for the WebFetch tool."""
    url: str = Field(..., description="The URL to fetch content from")
    prompt: str = Field(..., description="The prompt to run on the fetched content")


class WebFetchOutput(BaseModel):
    """Output schema for the WebFetch tool."""
    response: str = Field(..., description="AI model's response to the prompt")
    url: str = Field(..., description="URL that was fetched")
    final_url: Optional[str] = Field(None, description="Final URL after redirects")
    status_code: Optional[int] = Field(None, description="HTTP status code")


# ============================================================================
# TODOWRITE TOOL
# ============================================================================

class TodoItem(BaseModel):
    """Single todo item."""
    content: str = Field(..., description="The task description")
    status: Literal["pending", "in_progress", "completed"] = Field(
        ..., description="Task status"
    )
    priority: Optional[Literal["high", "medium", "low"]] = Field(
        None, description="Task priority"
    )
    id: Optional[str] = Field(None, description="Unique identifier for the todo item")


class TodoWriteInput(BaseModel):
    """Input schema for the TodoWrite tool."""
    todos: List[TodoItem] = Field(..., description="List of todo items")


class TodoStats(BaseModel):
    """Statistics for todo items."""
    total: int = Field(..., description="Total number of todos")
    pending: int = Field(..., description="Number of pending todos")
    in_progress: int = Field(..., description="Number of in-progress todos")
    completed: int = Field(..., description="Number of completed todos")


class TodoWriteOutput(BaseModel):
    """
    Unified output schema for the TodoWrite tool.

    Used for all todo operations (add, list, pop, clear, batch updates).
    """
    tool: Literal["todowrite"] = Field(
        "todowrite", description="Tool name that produced this result"
    )
    success: bool = Field(..., description="Whether the operation succeeded")
    message: Optional[str] = Field(
        None, description="Human-readable message about the result"
    )
    stats: Optional[TodoStats] = Field(
        None, description="Todo statistics (usually set for 'list')"
    )
    todos: Optional[List[TodoItem]] = Field(
        None, description="Current todo list after the operation"
    )
    count: Optional[int] = Field(
        None,
        description="Number of todos affected/updated (used in batch operations)",
    )
