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

BOX_WIDTH = 78


# ---------------------------
# Low-level helpers
# ---------------------------
def _box_border() -> str:
    return "+" + "-" * (BOX_WIDTH - 2) + "+"

def _box_header(title: str) -> str:
    """Return a small boxed header string with the given title."""
    return f"+{'-'*(BOX_WIDTH-2)}+\n| {title.ljust(BOX_WIDTH-4)} |\n+{'-'*(BOX_WIDTH-2)}+"

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
        print(f"| {line.ljust(BOX_WIDTH-4)} |")
    print(_box_border())

def print_boxed(title: str, body: str):
    """Show a small boxed panel with a title and a body (body may be multi-line)."""
    print(_box_header(title))
    for line in body.splitlines():
        for wrapped in _wrap_lines(line):
            print(f"| {wrapped.ljust(BOX_WIDTH-4)} |")
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
    header = f"Agent : using tool : {tool_name}"
    print("\n" + header)
    print("-" * len(header))


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

def _print_code_block_with_line_numbers(text: str, lang: str = ""):
    """
    Print simple numbered code block for terminal viewing.
    Keeps indentation intact and prints line numbers in a readable column.
    """
    lines = text.splitlines()
    width = max(2, len(str(len(lines))))
    # fence
    print("```" + (lang or ""))
    for i, line in enumerate(lines, start=1):
        lineno = str(i).rjust(width)
        print(f"{lineno} | {line.rstrip()}")
    print("```")


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
    # normalize
    success = bool(result.get("success", False))
    status = "OK" if success else "ERROR"
    header = f"[{tool_name}] {status}"
    print("\n" + header)
    print("-" * len(header))

    output_data = result.get("output")

    # Structured dict/list -> pretty JSON
    if isinstance(output_data, (dict, list)):
        try:
            pretty = json.dumps(output_data, indent=2)
            print(pretty)
        except Exception:
            print(str(output_data))
        print("-" * len(header))
        return

    # If tool output itself is a string that looks like file content -> render as code
    if isinstance(output_data, str) and _is_likely_file_content(output_data):
        _print_code_block_with_line_numbers(output_data)
        print("-" * len(header))
        return

    # If write/edit succeeded and args[0] is a path, try to preview the file we wrote
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
                        # print a small header to indicate file preview
                        print(f"File preview: {os.path.relpath(p, Path.cwd())}")
                        if _is_likely_file_content(content):
                            _print_code_block_with_line_numbers(content)
                        else:
                            # for non-code text show the first N lines
                            preview = "\n".join(content.splitlines()[:200])
                            print(preview)
                    except Exception as e:
                        print(f"Note: wrote to {target} (but couldn't read file for preview: {e})")
                else:
                    # file doesn't exist: fall back to printing tool output message
                    print(str(output_data or ""))
            except Exception:
                print(str(output_data or ""))
            print("-" * len(header))
            return

    # Default: print a short textual representation
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
    print("-" * len(header))


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
    border = "+" + "-" * (BOX_WIDTH - 2) + "+"
    print("\n" + border)
    title = "| " + "ERROR".ljust(BOX_WIDTH - 4) + " |"
    print(title)
    print(border)
    for line in message.splitlines():
        for wrapped in _wrap_lines(line):
            print("| " + wrapped.ljust(BOX_WIDTH - 4) + " |")
    print(border + "\n")

def print_agent_message(msg: str):
    """Generic short message from the agent (not a tool result)."""
    print_boxed("AGENT", msg)
