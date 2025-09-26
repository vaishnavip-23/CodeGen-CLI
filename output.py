"""
output.py

Simple formatting helpers. Keeps UI formatting separate from logic.
"""

import textwrap
import json

BOX_WIDTH = 80

def _boxed_lines(text, width):
    wrapped = textwrap.wrap(text, width=width - 4) or [""]
    return wrapped

def _boxed(text, title=None):
    lines = _boxed_lines(text, BOX_WIDTH)
    top = "+" + "-"*(BOX_WIDTH-2) + "+"
    parts = [top]
    if title:
        title_line = "| " + title.ljust(BOX_WIDTH-4) + " |"
        parts.append(title_line)
        parts.append("|" + "-"*(BOX_WIDTH-2) + "|")
    for l in lines:
        parts.append("| " + l.ljust(BOX_WIDTH-4) + " |")
    parts.append(top)
    return "\n".join(parts)

def print_boxed(title, text):
    print(_boxed(text, title=title))

def print_user_box(text):
    print()
    print(_boxed(text, title="USER"))
    print()

def print_agent_tool_use(tool_name):
    msg = f"Agent : using tool : {tool_name}"
    print("\n" + msg + "\n" + ("-"*len(msg)))

def print_result(tool_name, result):
    header = f"[{tool_name}] {'OK' if result.get('success') else 'ERROR'}"
    print("\n" + header)
    print("-"*len(header))
    out = result.get("output")
    if isinstance(out, (dict, list)):
        try:
            print(json.dumps(out, indent=2))
        except Exception:
            print(str(out))
    else:
        print(textwrap.fill(str(out or ""), width=BOX_WIDTH))
    meta = result.get("meta")
    if meta:
        print("\nMeta:")
        print(json.dumps(meta, indent=2))
    print("-"*len(header) + "\n")

def print_error(msg):
    print("\n[ERROR]")
    print(msg)
    print()

def print_help_box():
    help_text = (
        "Commands:\n"
        "  help              Show this help\n"
        "  exit              Exit the REPL\n"
        "  todo add <text>   Add a todo (shortcut)\n\n"
        "Natural language:\n"
        "  Type an instruction like:\n"
        "    Find all TODO comments and create TODO_SUMMARY.md\n"
    )
    print_boxed("HELP", help_text)
