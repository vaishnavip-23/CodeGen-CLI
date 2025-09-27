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

def print_help():
    """Display help information."""
    help_text = """CodeGen2 - CLI Coding Agent

This project is a command-line coding assistant that understands natural language.
It's designed to be a "repository-aware" agent, meaning it can interact with the
files in your project to perform various tasks.

Core Functionality:

 * Natural Language Interface: You can give it commands in plain English (e.g., "summarize the codebase," "read the README file").
 * LLM Integration: It uses the Google Gemini API to understand your requests and create a plan of action.
 * Tool-Based Architecture: The agent has a set of "tools" it can use to interact with your project. These tools are modular Python scripts located in the tools/ directory.
 * Safety First: The agent is designed with safety in mind. It has built-in protections to prevent accidental damage to your files, and it will ask for your confirmation before making any destructive changes.

Key Components:

 * `main.py`: This is the main entry point of the application. It handles the user input, communicates with the Gemini API, and orchestrates the execution of the tools.
 * `tools/` directory: This directory contains the individual tools that the agent can use, such as read, write, edit, glob, grep, and bash.
 * `system_prompt.txt`: This file contains the instructions and rules that are provided to the Gemini API to guide its behavior.
 * `output.py`: This module is responsible for the user interface, including the colored and boxed output that you see in your terminal.

Workflow:

The agent follows a "discovery-first" approach:

  1. Discover: It uses tools like ls and glob to find files.
  2. Inspect: It uses tools like read and grep to examine the content of files.
  3. Modify: It uses tools like edit and write to make changes to files.

This workflow ensures that the agent's actions are deliberate and predictable.

In short, you have a powerful and well-designed coding agent that you can interact with using natural language.
The summary you generated is a great starting point for understanding the project's capabilities."""
    
    print_boxed("CodeGen2 - CLI Coding Agent", help_text)

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
def print_user_box(text: str):
    """Legacy name for print_user_input."""
    print_user_input(text)

def print_agent_tool_use(tool_name: str):
    """Legacy name for print_agent_action."""
    print_agent_action(tool_name)

def print_result(tool_name: str, result: Dict[str, Any]):
    """Legacy name for print_tool_result."""
    print_tool_result(tool_name, result)

def print_help_box():
    """Legacy name for print_help."""
    print_help()