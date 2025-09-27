"""
output.py - nicer console output helpers for CodeGen2 (updated)

This file provides a consistent set of printing helpers that main.py expects.
Key behaviors:
- Show user input inside a boxed header (print_user_box).
- Show generic boxed messages (print_boxed).
- Pretty-print tool results (print_result) using code blocks with line numbers
  when the output looks like file/code content.
- Provide small helpers: print_agent_tool_use, print_help_box, print_error.
- Keep functions simple and readable for beginners.
"""

import os
import textwrap
from typing import Dict, Any, List
from pathlib import Path
import json
import re

BOX_WIDTH = 78

class Color:
    """ANSI color codes"""
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
# Low-level helpers
# ---------------------------
def _box_border() -> str:
    return f"{Color.BORDER}+{'-' * (BOX_WIDTH - 2)}+{Color.RESET}"

def _box_header(title: str) -> str:
    """Return a small boxed header string with the given title."""
    return f"{Color.BORDER}+{'-'*(BOX_WIDTH-2)}+{Color.RESET}\n{Color.BORDER}|{Color.RESET} {Color.HEADER}{title.ljust(BOX_WIDTH-4)}{Color.RESET} {Color.BORDER}|{Color.RESET}\n{Color.BORDER}+{'-'*(BOX_WIDTH-2)}+{Color.RESET}"

def _wrap_lines(text: str, width: int = BOX_WIDTH - 4) -> List[str]:
    """Wrap text to the given width and return list of lines."""
    return textwrap.wrap(text, width=width) if text else [""]

# ---------------------------
# Visible UI helpers (used by main.py)
# ---------------------------
def print_user_box(text: str):
    """Show the user's input inside a boxed USER header."""
    print(_box_header("USER"))
    for line in _wrap_lines(text):
        print(f"{Color.BORDER}|{Color.RESET} {line.ljust(BOX_WIDTH-4)} {Color.BORDER}|{Color.RESET}")
    print(_box_border())

def print_boxed(title: str, body: str):
    """Show a small boxed panel with a title and a body (body may be multi-line)."""
    print(_box_header(title))
    for line in body.splitlines():
        for wrapped in _wrap_lines(line):
            print(f"{Color.BORDER}|{Color.RESET} {wrapped.ljust(BOX_WIDTH-4)} {Color.BORDER}|{Color.RESET}")
    print(_box_border())

def print_help_box():
    """Show a short help box describing common commands (keeps it minimal)."""
    body = (
        "Quick help:\n"
        "- Ask in natural language (e.g. 'change README to hello')\n"
        "- Or call tools directly: read <path>, ls <path>, write <path> <content>\n"
        "- 'list files' shows a recursive listing\n"
        "- Destructive changes ask for confirmation first"
    )
    print_boxed("HELP", body)

def print_agent_tool_use(tool_name: str):
    """Show which tool the agent is using (small inline header)."""
    header = f"Agent : using tool : {Color.TOOL}{tool_name}{Color.RESET}"
    print("\n" + header)
    print("-" * (len(header) - len(Color.TOOL) - len(Color.RESET)))


# ---------------------------
# Code / file content rendering
# ---------------------------
def _is_likely_file_content(s: str) -> bool:
    """
    Heuristic to decide whether a string looks like code/file content.
    Returns True for multi-line text that contains common code tokens.
    """
    if not isinstance(s, str):
        return False
    if "\n" not in s:
        return False
    indicators = ["def ", "class ", "import ", "{", ";", "function ", "=>", "console.", "printf(", "package ", "public ", "#include", "async ", "await "]
    score = sum(1 for i in indicators if i in s)
    return score >= 1

def _colorize_python_code(line: str) -> str:
    """Apply simple syntax highlighting to a line of Python code."""
    line = re.sub(r'\b(def|class|import|from|return|if|else|elif|for|while|with|try|except|finally|and|or|not|in|is|as|assert|del|global|nonlocal|lambda|pass|raise|yield|True|False|None)\b', f'{Color.KEYWORD}\\1{Color.CODE}', line)
    line = re.sub('(\'\'\'.*?\'\'\'|\"\"\".*?\"\"\"|\'.*?\'|\".*?\")', f'{Color.STRING}\\1{Color.CODE}', line)
    line = re.sub(r'(#.*)', f'{Color.COMMENT}\\1{Color.CODE}', line)
    return line

def _print_code_block_with_line_numbers(text: str, lang: str = ""):
    """
    Print simple numbered code block for terminal viewing.
    Keeps indentation intact and prints line numbers in a readable column.
    """
    lines = text.splitlines()
    width = max(2, len(str(len(lines))))
    print(f"{Color.CODE}```{(lang or '')}{Color.RESET}")
    for i, line in enumerate(lines, start=1):
        lineno = str(i).rjust(width)
        if lang == 'python':
            line = _colorize_python_code(line)
        print(f"{Color.LINENO}{lineno} | {Color.CODE}{line.rstrip()}{Color.RESET}")
    print(f"{Color.CODE}```{Color.RESET}")

def _print_task_summary(output_data: Dict[str, Any]):
    """Prints a formatted summary from the Task tool's output."""
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

# ---------------------------
# Main result printing (compatibility wrappers)
# ---------------------------
def print_result(tool_name: str, result: Dict[str, Any]):
    """
    Main entrypoint for printing a tool's result.

    Expected result shape:
      {"tool": "...", "success": bool, "output": ..., "args": [...], "kwargs": {...}}

    This function normalizes the output and uses code-block rendering for file-like content.
    """
    success = bool(result.get("success", False))
    status = f"{Color.SUCCESS}OK{Color.RESET}" if success else f"{Color.ERROR}ERROR{Color.RESET}"
    header = f"[{Color.TOOL}{tool_name}{Color.RESET}] {status}"
    print("\n" + header)
    print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))

    output_data = result.get("output")

    if tool_name.lower() == "task" and isinstance(output_data, dict):
        _print_task_summary(output_data)
        print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
        return

    if isinstance(output_data, (dict, list)):
        try:
            pretty = json.dumps(output_data, indent=2)
            print(pretty)
        except Exception:
            print(str(output_data))
        print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
        return

    if isinstance(output_data, str) and _is_likely_file_content(output_data):
        _print_code_block_with_line_numbers(output_data, lang='python' if '.py' in (result.get('args', [''])[0] or '') else '')
        print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
        return

    if tool_name.lower() in ("write", "edit", "multiedit") and success:
        args = result.get("args", []) or []
        if len(args) >= 1 and isinstance(args[0], str):
            target = args[0]
            try:
                p = Path(target)
                if not p.is_absolute():
                    p = Path.cwd() / p
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        print(f"File preview: {os.path.relpath(p, Path.cwd())}")
                        if _is_likely_file_content(content):
                            _print_code_block_with_line_numbers(content, lang='python' if '.py' in target else '')
                        else:
                            preview = "\n".join(content.splitlines()[:200])
                            print(preview)
                    except Exception as e:
                        print(f"Note: wrote to {target} (but couldn't read file for preview: {e})")
                else:
                    print(str(output_data or ""))
            except Exception:
                print(str(output_data or ""))
            print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))
            return

    if output_data is None:
        print("(no output)")
    else:
        out_str = str(output_data)
        if len(out_str) > BOX_WIDTH * 6:
            preview = "\n".join(out_str.splitlines()[:200])
            print(preview)
            print("... (output truncated)")
        else:
            for line in out_str.splitlines():
                for wrapped in _wrap_lines(line):
                    print(wrapped)
    print("-" * (len(header) - (len(Color.TOOL) + len(Color.SUCCESS) + 2*len(Color.RESET)) if success else len(header) - (len(Color.TOOL) + len(Color.ERROR) + 2*len(Color.RESET))))


# Backwards-compat: some code calls print_tool_result/print_agent_action names
def print_tool_result(tool_name: str, result: Dict[str, Any]):
    """Compatibility wrapper (old name)."""
    print_result(tool_name, result)

def print_agent_action(tool_name: str):
    """Compatibility wrapper (old name)."""
    print_agent_tool_use(tool_name)


# ---------------------------
# Error and misc helpers
# ---------------------------
def print_error(message: str):
    """Pretty-print errors in a boxed format."""
    border = f"{Color.ERROR}+{'-' * (BOX_WIDTH - 2)}+{Color.RESET}"
    print("\n" + border)
    title = f"{Color.ERROR}| {Color.HEADER}ERROR{Color.RESET}{' ' * (BOX_WIDTH - 10)}{Color.ERROR}|{Color.RESET}"
    print(title)
    print(border)
    for line in message.splitlines():
        for wrapped in _wrap_lines(line):
            print(f"{Color.ERROR}|{Color.RESET} {wrapped.ljust(BOX_WIDTH - 4)} {Color.ERROR}|{Color.RESET}")
    print(border + "\n")

def print_agent_message(msg: str):
    """Generic short message from the agent (not a tool result)."""
    print_boxed("AGENT", msg)
