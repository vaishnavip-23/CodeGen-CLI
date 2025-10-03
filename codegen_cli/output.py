"""
Output formatting utilities for CodeGen2 CLI agent.

Provides colored, structured output for user interactions, tool results, and error messages.
"""

import json
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
        return sys.stdout.isatty()  # type: ignore[attr-defined]
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

# ---------------------------
# Main Output Functions
# ---------------------------
def print_user_input(text: str):
    """Display user input in a styled panel."""
    _print_panel("User", text, style="input")


def print_agent_action(tool_name: str):
    """Display agent tool usage."""
    message = f"Using tool: {Color.TOOL}{tool_name}{Color.RESET}"
    _print_panel("Agent", message, style="action")


def print_boxed(title: str, content: str, *, style: str = "info"):
    """Display content in a box with title."""
    _print_panel(title, content, style=style)


def print_error(message: str):
    """Display error message in a red box."""
    _print_panel("Error", message, style="error")


def print_info(message: str, *, title: str = "Info"):
    """Display informational text in standard styling."""
    _print_panel(title, message, style="info")


def print_success(message: str, *, title: str = "Success"):
    """Display success feedback."""
    _print_panel(title, message, style="success")


def print_warning(message: str, *, title: str = "Warning"):
    """Display warnings or cautionary notes."""
    _print_panel(title, message, style="warning")


def print_assistant(message: str, *, title: str = "Assistant"):
    """Display assistant chat responses."""
    _print_panel(title, message, style="assistant")


def print_prompt(message: str, *, title: str = "Confirm"):
    """Display prompts requiring user confirmation."""
    _print_panel(title, message, style="question")


def print_help(project_info=None):
    """Display help information."""
    if project_info is None:
        project_info = {"language": "unknown", "package_manager": None}
    
    # Language-specific help
    language_help = {
        'python': {
            'description': 'Python project with support for pip, poetry, and pipenv',
            'tools': 'Python-specific tools: pytest, black, flake8, mypy',
            'examples': ['run tests', 'format code', 'check types', 'install dependencies']
        },
        'javascript': {
            'description': 'JavaScript/TypeScript project with npm/yarn support',
            'tools': 'JS-specific tools: jest, eslint, prettier, webpack',
            'examples': ['run tests', 'lint code', 'build project', 'install packages']
        },
        'go': {
            'description': 'Go project with go modules support',
            'tools': 'Go-specific tools: go test, go build, go fmt',
            'examples': ['run tests', 'build binary', 'format code', 'get dependencies']
        },
        'rust': {
            'description': 'Rust project with cargo support',
            'tools': 'Rust-specific tools: cargo test, cargo build, cargo fmt',
            'examples': ['run tests', 'build project', 'check code', 'update dependencies']
        }
    }
    
    lang_info = language_help.get(project_info['language'], {
        'description': 'Generic project',
        'tools': 'Universal tools available',
        'examples': ['read files', 'search code', 'edit files', 'analyze project']
    })
    
    help_text = f"""CodeGen CLI - Universal Coding Agent

This universal CLI coding agent understands any codebase.
It auto-detects your project type and adapts tools accordingly.

Quick Start:
  1. codegen --set-key   (saves your key to ~/.config/codegen/.env)
  2. codegen             (run inside your project)
  3. Try: help, list files, read README.md

API Key:
  • Auto-loads from ./.env, ~/.env, ~/.config/codegen/.env
  • Or export GEMINI_API_KEY in your shell
  • Get a key at: https://aistudio.google.com/api-keys

Current Project:
 * Language: {project_info['language']}
 * Package Manager: {project_info['package_manager'] or 'None detected'}
 * Description: {lang_info['description']}

Common Commands:
  • help                      Show this help
  • list files                List repository files
  • read path/to/file         Print file contents
  • grep "pattern"            Search across files
  • write <file> <content>    Create/overwrite file (asks to confirm)
  • edit <file>               Modify content safely
  • delete <path>             Delete file or folder (asks to confirm)

Core Functionality:
  • Natural language interface: "summarize the repo", "find TODOs"
  • Universal compatibility across languages
  • Smart project detection
  • Safety-first changes with confirmation

Available Tools:

 * File Operations: read, write, edit, delete, list files
 * Search & Analysis: grep, search, analyze codebase
 * Web Integration: web search, fetch URLs
 * System Operations: bash commands, project management
 * Language-Specific: {lang_info['tools']}

Examples:
  • {lang_info['examples'][0]}
  • {lang_info['examples'][1]}
  • {lang_info['examples'][2]}
  • {lang_info['examples'][3] if len(lang_info['examples']) > 3 else 'analyze project'}

Workflow:

The agent follows a "discovery-first" approach:

  1. Discover: Find files and understand project structure
  2. Inspect: Examine code and identify patterns
  3. Modify: Make changes safely with confirmation

This ensures deliberate and predictable actions across any codebase."""
    
    print_boxed("CodeGen CLI - Universal Coding Agent", help_text)

# ---------------------------
# Code Syntax Highlighting
# ---------------------------
def _colorize_python_code(line: str) -> str:
    """Apply simple syntax highlighting to Python code."""
    # Keywords
    line = re.sub(r'\b(def|class|import|from|return|if|else|elif|for|while|with|try|except|finally|and|or|not|in|is|as|assert|del|global|nonlocal|lambda|pass|raise|yield|True|False|None)\b', f'{Color.KEYWORD}\\1{Color.CODE}', line)
    # Strings
    line = re.sub(r'(\'\'\'.*?\'\'\'|\"\"\".*?\"\"\"|\'.*?\'|\".*?\")', f'{Color.STRING}\\1{Color.CODE}', line)
    # Comments
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

# ---------------------------
# Tool Result Display
# ---------------------------
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
    """Display tool execution result in a styled panel."""
    success = bool(result.get("success", False))
    style = "success" if success else "error"
    status_label = "OK" if success else "ERROR"
    status_color = Color.SUCCESS if success else Color.ERROR
    status_line = f"{status_color}Status: {status_label}{Color.RESET}"

    content_blocks: List[str] = [status_line]

    message = result.get("message")
    if isinstance(message, str) and message.strip():
        content_blocks.append(message.strip())

    if not success and result.get("error"):
        content_blocks.append(str(result["error"]))

    output_data = result.get("output")

    if tool_name.lower() == "task" and isinstance(output_data, dict):
        task_lines = _task_summary_lines(output_data)
        if task_lines:
            content_blocks.append("\n".join(task_lines))
    elif isinstance(output_data, (dict, list)):
        try:
            content_blocks.append(json.dumps(output_data, indent=2))
        except Exception:
            content_blocks.append(str(output_data))
    elif isinstance(output_data, str):
        text = output_data.strip("\n")
        if _looks_like_code(text):
            code_block = "\n".join([
                f"{Color.CODE}```python{Color.RESET}",
                _format_code_content(text),
                f"{Color.CODE}```{Color.RESET}",
            ])
            content_blocks.append(code_block)
        elif text:
            content_blocks.append(text)
    elif output_data is not None:
        content_blocks.append(str(output_data))

    title = f"{tool_name} • {status_label}"
    body = "\n\n".join(block for block in content_blocks if block)
    print_boxed(title, body if body else status_line, style=style)

# ---------------------------
# Legacy Function Names (for compatibility)
# ---------------------------