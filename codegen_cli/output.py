# File Summary: Console rendering helpers for styled and boxed output.

"""
Output formatting utilities for CodeGen2 CLI agent.

Provides colored, structured output for user interactions, tool results, and error messages.
"""

import os
import re
import shutil
import sys
import textwrap
from typing import Any, Dict, List

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()                              
    except Exception:
        return False


USE_COLOR = _supports_color()


def _color(code: str) -> str:
    return code if USE_COLOR else ""


class Color:
    """ANSI color codes for terminal output."""

    RESET = _color("\033[0m")
    BOLD = _color("\033[1m")
    BORDER = _color("\033[38;5;244m")
    HEADER = _color("\033[38;5;213m")
    TITLE = _color("\033[38;5;81m")
    SUCCESS = _color("\033[38;5;82m")
    ERROR = _color("\033[38;5;203m")
    TOOL = _color("\033[38;5;117m")
    CODE = _color("\033[38;5;215m")
    KEYWORD = _color("\033[38;5;208m")
    STRING = _color("\033[38;5;150m")
    COMMENT = _color("\033[38;5;244m")
    LINENO = _color("\033[38;5;240m")
    TEXT = _color("\033[38;5;252m")
    MUTED = _color("\033[38;5;245m")
    ACCENT = _color("\033[38;5;141m")


MIN_BOX_WIDTH = 48
MAX_BOX_WIDTH = 110


def _visible_len(text: str) -> int:
    return len(ANSI_ESCAPE_RE.sub("", text))


def _contains_ansi(text: str) -> bool:
    return bool(ANSI_ESCAPE_RE.search(text))


def _current_box_width() -> int:
    env_width = os.environ.get("CODEGEN_BOX_WIDTH")
    if env_width:
        try:
            forced = int(env_width)
            if forced >= 40:
                return min(forced, MAX_BOX_WIDTH)
        except ValueError:
            pass

    columns = shutil.get_terminal_size(fallback=(96, 24)).columns
    available = max(columns - 4, 40)
    width = min(max(available, MIN_BOX_WIDTH), MAX_BOX_WIDTH)
    if width % 2:
        width -= 1
    return max(width, 40)


def _wrap_lines(text: str, width: int) -> List[str]:
    if not text:
        return []
    wrapped: List[str] = []
    for raw in text.splitlines():
        if raw == "":
            wrapped.append("")
            continue
        if _contains_ansi(raw) or _visible_len(raw) <= width:
            wrapped.append(raw)
            continue
        segments = textwrap.wrap(raw, width=width, drop_whitespace=False, replace_whitespace=False)
        wrapped.extend(segments if segments else [""])
    return wrapped


BOX_STYLES: Dict[str, Dict[str, str]] = {
    "info": {"border": Color.BORDER, "title": Color.TITLE + Color.BOLD, "text": Color.TEXT},
    "input": {"border": Color.HEADER, "title": Color.HEADER + Color.BOLD, "text": Color.TEXT},
    "error": {"border": Color.ERROR, "title": Color.ERROR + Color.BOLD, "text": Color.TEXT},
    "success": {"border": Color.SUCCESS, "title": Color.SUCCESS + Color.BOLD, "text": Color.TEXT},
    "action": {"border": Color.TOOL, "title": Color.TOOL + Color.BOLD, "text": Color.TEXT},
    "banner": {"border": Color.ACCENT, "title": Color.ACCENT + Color.BOLD, "text": Color.TEXT},
    "assistant": {"border": Color.ACCENT, "title": Color.ACCENT + Color.BOLD, "text": Color.TEXT},
    "warning": {"border": Color.CODE, "title": Color.CODE + Color.BOLD, "text": Color.TEXT},
    "question": {"border": Color.STRING, "title": Color.STRING + Color.BOLD, "text": Color.TEXT},
}


def _render_panel(title: str, lines: List[str], style: str = "info") -> str:
    width = _current_box_width()
    inner = width - 4
    palette = BOX_STYLES.get(style, BOX_STYLES["info"])
    border = palette["border"]
    title_color = palette["title"]
    text_color = palette["text"]

    parts: List[str] = []
    parts.append(f"{border}╭{'─' * (width - 2)}╮{Color.RESET}")

    if title:
        header = title.upper().strip()
        centered = header.center(inner)
        parts.append(f"{border}│{Color.RESET} {title_color}{centered}{Color.RESET} {border}│{Color.RESET}")
        parts.append(f"{border}├{'─' * (width - 2)}┤{Color.RESET}")

    if not lines:
        lines = [""]

    for line in lines:
        visible = line
        if _visible_len(line) > inner and not _contains_ansi(line):
            visible = line[:inner]
        pad = max(0, inner - _visible_len(visible))
        if _contains_ansi(visible):
            content = f"{visible}{Color.RESET}{' ' * pad}"
        else:
            content = f"{text_color}{visible}{' ' * pad}{Color.RESET}"
        parts.append(f"{border}│{Color.RESET} {content} {border}│{Color.RESET}")

    parts.append(f"{border}╰{'─' * (width - 2)}╯{Color.RESET}")
    return "\n".join(parts)


def _print_panel(title: str, content: str, style: str = "info") -> None:
    width = _current_box_width()
    lines = _wrap_lines(content, width - 4)
    print()
    print(_render_panel(title, lines, style=style))

                             
                       
                             
def print_user_input(text: str):
    """Display user input - COMPACT."""
    print(f"\n{Color.HEADER}> {text}{Color.RESET}")


def print_agent_action(tool_name: str, tool_args: dict = None):
    """Display agent tool usage with arguments - TRANSPARENT."""
    if tool_args:
        # Show key arguments for transparency
        args_display = _format_tool_args(tool_name, tool_args)
        if args_display:
            print(f"{Color.TOOL}→ {tool_name}{Color.RESET}: {Color.CODE}{args_display}{Color.RESET}", end="", flush=True)
        else:
            print(f"{Color.TOOL}→ {tool_name}{Color.RESET}", end="", flush=True)
    else:
        print(f"{Color.TOOL}→ {tool_name}{Color.RESET}", end="", flush=True)


def _format_tool_args(tool_name: str, args: dict) -> str:
    """Format tool arguments for display (show key info only)."""
    if tool_name == "run_command":
        # ALWAYS show bash commands for transparency
        cmd = args.get("command", "")
        return cmd[:100] + "..." if len(cmd) > 100 else cmd
    
    elif tool_name in ("read_file", "write_file", "edit_file", "delete_file"):
        # Show file path
        file_path = args.get("file_path", "")
        if file_path:
            # Show just filename or last 2 path components
            parts = file_path.split("/")
            if len(parts) > 2:
                return "/".join(parts[-2:])
            return file_path
    
    elif tool_name == "find_files":
        # Show pattern
        pattern = args.get("pattern", "")
        return f"pattern={pattern}" if pattern else ""
    
    elif tool_name == "grep":
        # Show pattern and file type if specified
        pattern = args.get("pattern", "")
        file_type = args.get("type", "")
        if file_type:
            return f'"{pattern}" --type {file_type}'
        return f'"{pattern}"'
    
    elif tool_name == "list_files":
        # Show path
        path = args.get("path", ".")
        return path if path != "." else ""
    
    elif tool_name == "edit_file":
        # Show what's being replaced (first 40 chars)
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        if old and new:
            old_preview = old[:40] + "..." if len(old) > 40 else old
            new_preview = new[:40] + "..." if len(new) > 40 else new
            return f'"{old_preview}" → "{new_preview}"'
    
    return ""


def print_agent_thinking(thought: str):
    """Display agent's reasoning/summary - COMPACT."""
    # Wrap long thoughts to 80 chars
    wrapped = textwrap.fill(thought, width=80, initial_indent="  ", subsequent_indent="  ")
    print(f"\n{Color.COMMENT}💭 {wrapped}{Color.RESET}")


def print_boxed(title: str, content: str, *, style: str = "info"):
    """Display content in a box with title."""
    _print_panel(title, content, style=style)


def print_error(message: str):
    """Display error message - COMPACT."""
    print(f"\n{Color.ERROR}✗ Error: {message}{Color.RESET}")


def print_info(message: str, *, title: str = "Info"):
    """Display informational text - COMPACT."""
    print(f"\n{Color.TITLE}[{message}]{Color.RESET}")


def print_success(message: str, *, title: str = "Success"):
    """Display success feedback - COMPACT."""
    print(f"\n{Color.SUCCESS}✓ {message}{Color.RESET}")


def print_warning(message: str, *, title: str = "Warning"):
    """Display warnings - COMPACT."""
    print(f"\n{Color.KEYWORD}⚠ {message}{Color.RESET}")


def print_assistant(message: str, *, title: str = "Assistant"):
    """Display assistant chat responses - COMPACT."""
    print(f"\n{Color.BOLD}{message}{Color.RESET}")


def print_prompt(message: str, *, title: str = "Confirm"):
    """Display prompts requiring user confirmation."""
    _print_panel(title, message, style="question")


def print_help(project_info=None):
    """Display help information."""
    if project_info is None:
        project_info = {"language": "unknown", "package_manager": None, "framework": None}
    
    # Build language display with framework
    lang_display = project_info.get('language', 'unknown')
    if project_info.get('framework'):
        lang_display = f"{lang_display} ({project_info['framework']})"
    
    help_text = f"""CodeGen CLI - Universal Coding Agent

A coding agent that understands any codebase and learns from results.

{Color.ACCENT}Current Project:{Color.RESET}
  Language: {Color.BOLD}{lang_display}{Color.RESET}
  Package Manager: {Color.BOLD}{project_info.get('package_manager') or 'None detected'}{Color.RESET}

{Color.ACCENT}Quick Start:{Color.RESET}
  • Use natural language: "explain the codebase", "find all TODO comments"
  • Ask questions: "how does authentication work?", "what does this function do?"
  • Request changes: "add error handling to fetchData", "create a Header component"

{Color.ACCENT}Common Commands:{Color.RESET}
  • {Color.CODE}explain the codebase{Color.RESET}     Get detailed project analysis
  • {Color.CODE}read path/to/file{Color.RESET}        View file contents
  • {Color.CODE}grep "pattern"{Color.RESET}           Search across files
  • {Color.CODE}list files{Color.RESET}               Show project structure
  • {Color.CODE}find **/*.test.js{Color.RESET}        Find files by pattern

{Color.ACCENT}Available Tools:{Color.RESET}
  File Ops:  read_file, write_file, edit_file, multi_edit, delete_file
  Search:    list_files, find_files, grep
  System:    run_command (bash)
  Web:       fetch_url, search_web
  Tasks:     manage_todos

{Color.ACCENT}Example Requests:{Color.RESET}
  • "explain how the authentication system works"
  • "find all functions that handle API requests"
  • "create a new component called UserProfile"
  • "add type hints to all functions in utils.py"
  • "rename getUserData to fetchUserProfile in all files"

{Color.ACCENT}Features:{Color.RESET}
  ✓ Conversation memory - remembers context from previous requests
  ✓ Smart detection - auto-detects languages, frameworks, package managers
  ✓ Safety first - previews changes and asks for confirmation
  ✓ Iterative reasoning - learns from results and adapts approach

{Color.ACCENT}Setup:{Color.RESET}
  API Key:  codegen --set-key YOUR_KEY
  Version:  codegen --version
  Updates:  codegen --check-update
  Exit:     Ctrl+C or type 'exit'

Get your free Gemini API key: {Color.CODE}https://aistudio.google.com/api-keys{Color.RESET}"""
    
    print_boxed("CodeGen CLI - Universal Coding Agent", help_text)

                             
                          
                             
def _colorize_python_code(line: str) -> str:
    """Apply simple syntax highlighting to Python code."""
              
    line = re.sub(r'\b(def|class|import|from|return|if|else|elif|for|while|with|try|except|finally|and|or|not|in|is|as|assert|del|global|nonlocal|lambda|pass|raise|yield|True|False|None)\b', f'{Color.KEYWORD}\\1{Color.CODE}', line)
             
    line = re.sub(r'(\'\'\'.*?\'\'\'|\"\"\".*?\"\"\"|\'.*?\'|\".*?\")', f'{Color.STRING}\\1{Color.CODE}', line)
              
    line = re.sub(r'(#.*)', f'{Color.COMMENT}\\1{Color.CODE}', line)
    return line

def _format_code_content(content: str, language: str = "python") -> str:
    """Format code content with syntax highlighting."""
    if language.lower() == "python":
        lines = content.split('\n')
        colored_lines = []
        for i, line in enumerate(lines, 1):
            colored_line = _colorize_python_code(line)
            colored_lines.append(f"{Color.LINENO}{i:3} |{Color.RESET} {colored_line}")
        return '\n'.join(colored_lines)
    else:
        lines = content.split('\n')
        numbered_lines = []
        for i, line in enumerate(lines, 1):
            numbered_lines.append(f"{Color.LINENO}{i:3} |{Color.RESET} {line}")
        return '\n'.join(numbered_lines)

                             
                     
                             
def _task_summary_lines(output_data: Dict[str, Any]) -> List[str]:
    """Build formatted summary lines for the Task tool."""
    if not isinstance(output_data, dict):
        return []

    lines: List[str] = []

    summary = output_data.get("summary")
    if summary:
        lines.append(f"{Color.ACCENT}Summary{Color.RESET}")
        lines.append(summary.strip())

    files_count = output_data.get("files_count")
    files_by_ext = output_data.get("files_by_extension", {})
    if files_count is not None:
        if lines:
            lines.append("")
        lines.append(f"{Color.ACCENT}File Counts{Color.RESET}")
        lines.append(f"  • Total files: {files_count}")
        if isinstance(files_by_ext, dict):
            for ext, count in files_by_ext.items():
                lines.append(f"  • {ext}: {count}")

    top_level = output_data.get("top_level")
    if isinstance(top_level, list) and top_level:
        if lines:
            lines.append("")
        lines.append(f"{Color.ACCENT}Top-Level Items{Color.RESET}")
        for item in top_level:
            lines.append(f"  • {item}")

    readme_excerpt = output_data.get("readme_excerpt")
    if readme_excerpt:
        if lines:
            lines.append("")
        lines.append(f"{Color.ACCENT}README Excerpt{Color.RESET}")
        lines.append(readme_excerpt.strip())

    behavior_excerpt = output_data.get("behavior_excerpt")
    if behavior_excerpt:
        if lines:
            lines.append("")
        lines.append(f"{Color.ACCENT}Behavior Excerpt{Color.RESET}")
        lines.append(behavior_excerpt.strip())

    return lines


def _looks_like_code(text: str) -> bool:
    keywords = ("def ", "class ", "import ", "from ", "if ", "for ", "while ")
    return any(keyword in text for keyword in keywords)


def print_tool_result(tool_name: str, result: Dict[str, Any]):
    """Display tool execution result with structured schema support - ENHANCED."""
    success = bool(result.get("success", False))
    status = "✓" if success else "✗"
    status_color = Color.SUCCESS if success else Color.ERROR
    
    # Compact output: tool_name [status] + brief result
    print(f"\n{status_color}{status} {tool_name}{Color.RESET}", end="")
    
    output_data = result.get("output")
    
    # Handle structured schema outputs
    if isinstance(output_data, dict):
        # ReadOutput schema
        if "total_lines" in output_data and "lines_returned" in output_data:
            print(f" → Read {output_data['lines_returned']}/{output_data['total_lines']} lines")
            return
        
        # WriteOutput schema
        if "bytes_written" in output_data and "file_path" in output_data:
            print(f" → Wrote {output_data['bytes_written']} bytes to {output_data['file_path']}")
            return
        
        # EditOutput schema
        if "replacements" in output_data:
            print(f" → {output_data['replacements']} replacement(s) in {output_data.get('file_path', 'file')}")
            return
        
        # DeleteOutput schema
        if "deleted_items" in output_data:
            print(f" → Deleted {output_data['count']} item(s)")
            for item in output_data['deleted_items'][:3]:
                print(f"  • {item}")
            return
        
        # BashOutput schema - ENHANCED with stderr/stdout
        if "exitCode" in output_data:
            exit_code = output_data['exitCode']
            output_text = output_data.get('output', '')
            
            # Color code exit code
            if exit_code == 0:
                print(f" → Exit code: {Color.SUCCESS}{exit_code}{Color.RESET}")
            else:
                print(f" → Exit code: {Color.ERROR}{exit_code}{Color.RESET}")
            
            # Show output if present (first 300 chars)
            if output_text:
                # Check if it looks like an error
                is_error = exit_code != 0 or any(word in output_text.lower() for word in ['error', 'traceback', 'exception', 'failed'])
                
                # Split by lines and show first few
                lines = output_text.strip().split('\n')
                
                if is_error and len(output_text) > 100:
                    # For errors, show STDERR prominently
                    print(f"   {Color.ERROR}STDERR:{Color.RESET}")
                    for line in lines[:5]:  # Show first 5 lines
                        if line.strip():
                            truncated = line[:120] + "..." if len(line) > 120 else line
                            print(f"   {truncated}")
                else:
                    # For successful output, show compactly
                    preview = output_text[:300]
                    # Remove newlines and compress whitespace
                    preview = ' '.join(preview.split())
                    if len(output_text) > 300:
                        preview += "..."
                    print(f"   {preview}")
            return
        
        # GlobOutput schema
        if "matches" in output_data and "search_path" in output_data:
            print(f" → Found {output_data['count']} matches")
            for match in output_data['matches'][:5]:
                print(f"  • {match}")
            return
        
        # LsOutput schema
        if "files" in output_data and isinstance(output_data['files'], list):
            print(f" → {output_data['count']} files in {output_data.get('path', '')}")
            for f in output_data['files'][:5]:
                print(f"  • {f}")
            return
        
        # GrepOutput schemas
        if "total_matches" in output_data:
            print(f" → {output_data['total_matches']} matches")
            for match in output_data.get('matches', [])[:5]:
                if isinstance(match, dict):
                    print(f"  • {match.get('file')}:{match.get('line_number', '?')}")
            return
        
        # WebSearchOutput schema
        if "results" in output_data and "query" in output_data:
            print(f" → {output_data['total_results']} results for '{output_data['query']}'")
            for res in output_data['results'][:3]:
                if isinstance(res, dict):
                    print(f"  • {res.get('title', '')[:60]}")
            return
        
        # TodoWriteOutput schema
        if "stats" in output_data:
            stats = output_data['stats']
            print(f" → {stats['total']} todos ({stats['pending']} pending, {stats['completed']} done)")
            return
        
        # MultiEditOutput schema
        if "total_edits" in output_data:
            print(f" → {output_data['successful_edits']}/{output_data['total_edits']} edits successful")
            return
        
        # Generic dict output
        print(f" → {len(output_data)} fields")
    
    # Handle list outputs
    elif isinstance(output_data, list):
        count = len(output_data)
        print(f" → {count} items")
        if count > 0 and count <= 5:
            for item in output_data[:5]:
                item_str = str(item) if not isinstance(item, dict) else item.get("file", str(item))
                print(f"  • {item_str[:80]}")
    
    # Handle string outputs
    elif isinstance(output_data, str):
        preview = output_data[:200].replace('\n', ' ')
        print(f" → {preview}..." if len(output_data) > 200 else f" → {preview}")
    
    # Handle other types
    elif output_data is not None:
        print(f" → {str(output_data)[:100]}")
    
    # Fallback to message
    else:
        msg = result.get("message", "")
        if msg:
            print(f" → {msg[:100]}")

                             
                                           
                             
