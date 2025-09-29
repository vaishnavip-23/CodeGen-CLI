"""
Output formatting utilities for CodeGen2 CLI agent.

Provides colored, structured output for user interactions, tool results, and error messages.
"""

import os
import textwrap
from typing import Dict, Any, List
from pathlib import Path
import json
import re

BOX_WIDTH = 78

class Color:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    HEADER = "\033[95m"
    BORDER = "\033[90m"
    SUCCESS = "\033[92m"
    ERROR = "\033[91m"
    TOOL = "\033[96m"
    CODE = "\033[93m"
    KEYWORD = "\033[94m"
    STRING = "\033[92m"
    COMMENT = "\033[90m"
    LINENO = "\033[90m"
    BOLD = "\033[1m"

# ---------------------------
# Box Drawing Helpers
# ---------------------------
def _box_border() -> str:
    """Create top/bottom border for boxes."""
    return f"{Color.BORDER}+{'-' * (BOX_WIDTH - 2)}+{Color.RESET}"

def _box_header(title: str) -> str:
    """Create boxed header with title."""
    return f"{Color.BORDER}+{'-'*(BOX_WIDTH-2)}+{Color.RESET}\n{Color.BORDER}|{Color.RESET} {Color.HEADER}{title.ljust(BOX_WIDTH-4)}{Color.RESET} {Color.BORDER}|{Color.RESET}\n{Color.BORDER}+{'-'*(BOX_WIDTH-2)}+{Color.RESET}"

def _wrap_lines(text: str, width: int = BOX_WIDTH - 4) -> List[str]:
    """Wrap text to specified width."""
    if not text:
        return []
    lines = text.split('\n')
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.wrap(line, width=width))
    return wrapped

def _box_content(lines: List[str]) -> str:
    """Format lines as boxed content."""
    if not lines:
        return ""
    result = []
    for line in lines:
        padded = line.ljust(BOX_WIDTH - 4)
        result.append(f"{Color.BORDER}|{Color.RESET} {padded} {Color.BORDER}|{Color.RESET}")
    return "\n".join(result)

# ---------------------------
# Main Output Functions
# ---------------------------
def print_user_input(text: str):
    """Display user input in a box."""
    print(_box_header("USER"))
    lines = _wrap_lines(text)
    print(_box_content(lines))
    print(_box_border())

def print_agent_action(tool_name: str):
    """Display agent tool usage."""
    print(f"\nAgent : using tool : {Color.TOOL}{tool_name}{Color.RESET}")
    print("-" * 25)

def print_boxed(title: str, content: str):
    """Display content in a box with title."""
    print(f"\n{_box_header(title)}")
    lines = _wrap_lines(content)
    print(_box_content(lines))
    print(_box_border())

def print_error(message: str):
    """Display error message in red box."""
    print(f"\n{_box_header('ERROR')}")
    lines = _wrap_lines(message)
    print(_box_content(lines))
    print(_box_border())

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

This is a universal command-line coding agent that understands any codebase.
It automatically detects your project type and adapts its tools accordingly.

🔑 Setup Required:
 * Set your Gemini API key: export GEMINI_API_KEY="your-api-key"
 * Get your API key from: https://aistudio.google.com/api-keys
 * Or create a .env file with: GEMINI_API_KEY=your-api-key

Current Project:
 * Language: {project_info['language']}
 * Package Manager: {project_info['package_manager'] or 'None detected'}
 * Description: {lang_info['description']}

Core Functionality:

 * Natural Language Interface: Give commands in plain English (e.g., "summarize the codebase," "read the main file").
 * Universal Compatibility: Works with Python, JavaScript, Go, Rust, and other languages.
 * Smart Detection: Automatically detects project type, package manager, and framework.
 * Safety First: Built-in protections prevent accidental damage to your files.

Available Tools:

 * File Operations: read, write, edit, delete, list files
 * Search & Analysis: grep, search, analyze codebase
 * Web Integration: web search, fetch URLs
 * System Operations: bash commands, project management
 * Language-Specific: {lang_info['tools']}

Usage Examples:

 * {lang_info['examples'][0]}
 * {lang_info['examples'][1]}
 * {lang_info['examples'][2]}
 * {lang_info['examples'][3] if len(lang_info['examples']) > 3 else 'analyze project'}

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
def _print_task_summary(output_data: Dict[str, Any]):
    """Display formatted summary from Task tool."""
    bold = Color.BOLD
    reset = Color.RESET

    if "summary" in output_data:
        print(f"{bold}Codebase Summary:{reset}")
        print(output_data["summary"])
        print()

    if "files_count" in output_data:
        print(f"{bold}File Counts:{reset}")
        print(f"  - Total files: {output_data['files_count']}")
        if "files_by_extension" in output_data:
            for ext, count in output_data["files_by_extension"].items():
                print(f"    - {ext}: {count}")
    print()

    if "top_level" in output_data:
        print(f"{bold}Top-Level Files and Directories:{reset}")
        for item in output_data["top_level"]:
            print(f"  - {item}")
    print()

    if "readme_excerpt" in output_data and output_data["readme_excerpt"]:
        print(f"{bold}README Excerpt:{reset}")
        print(output_data["readme_excerpt"])
        print()

    if "behavior_excerpt" in output_data and output_data["behavior_excerpt"]:
        print(f"{bold}Behavior Excerpt:{reset}")
        print(output_data["behavior_excerpt"])
        print()

def print_tool_result(tool_name: str, result: Dict[str, Any]):
    """Display tool execution result."""
    success = result.get("success", False)
    header = f"[{Color.TOOL}{tool_name}{Color.RESET}] {Color.SUCCESS}OK{Color.RESET}" if success else f"[{Color.TOOL}{tool_name}{Color.RESET}] {Color.ERROR}ERROR{Color.RESET}"
    print(header)
    print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
    
    output_data = result.get("output")
    
    # Special handling for Task tool
    if tool_name.lower() == "task" and isinstance(output_data, dict):
        _print_task_summary(output_data)
        print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
        return

    # Display output data
    if isinstance(output_data, (dict, list)):
        try:
            formatted = json.dumps(output_data, indent=2)
            print(formatted)
        except Exception:
            print(str(output_data))
    elif isinstance(output_data, str):
        # Check if it looks like code
        if any(keyword in output_data for keyword in ["def ", "class ", "import ", "from ", "if ", "for ", "while "]):
            print(f"{Color.CODE}```python{Color.RESET}")
            print(_format_code_content(output_data))
            print(f"{Color.CODE}```{Color.RESET}")
        else:
            print(output_data)
    else:
        print(str(output_data) if output_data is not None else "")

# ---------------------------
# Legacy Function Names (for compatibility)
# ---------------------------