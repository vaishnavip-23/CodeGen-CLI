"""
Output formatting utilities for CodeGen2

This module provides functions to format and display output in a user-friendly way.
All output is formatted with boxes and clear headers for better readability.
"""

import textwrap
import json
from typing import Dict, Any

# Maximum width for text boxes
BOX_WIDTH = 78

# ============================================================================
# TEXT FORMATTING HELPERS
# ============================================================================

def wrap_text(text: str, width: int = None) -> list:
    """
    Wrap text to fit within a specified width.
    
    Args:
        text: Text to wrap
        width: Maximum width (defaults to BOX_WIDTH)
        
    Returns:
        List of wrapped lines
    """
    if width is None:
        width = BOX_WIDTH
    
    return textwrap.wrap(text, width=width-4) or [""]

def create_box(text: str, title: str = None) -> str:
    """
    Create a text box with optional title.
    
    Args:
        text: Main text content
        title: Optional title for the box
        
    Returns:
        Formatted box as string
    """
    lines = wrap_text(text)
    
    # Create top border
    top_border = "+" + "-" * (BOX_WIDTH - 2) + "+"
    box_parts = [top_border]
    
    # Add title if provided
    if title:
        title_line = "| " + title.ljust(BOX_WIDTH - 4) + " |"
        box_parts.append(title_line)
        box_parts.append("|" + "-" * (BOX_WIDTH - 2) + "|")
    
    # Add content lines
    for line in lines:
        content_line = "| " + line.ljust(BOX_WIDTH - 4) + " |"
        box_parts.append(content_line)
    
    # Add bottom border
    box_parts.append(top_border)
    
    return "\n".join(box_parts)

# ============================================================================
# MAIN OUTPUT FUNCTIONS
# ============================================================================

def print_boxed(title: str, text: str):
    """
    Print text in a box with a title.
    
    Args:
        title: Title for the box
        text: Text content to display
    """
    print(create_box(text, title=title))

def print_user_input(text: str):
    """
    Print user input in a special box.
    
    Args:
        text: What the user typed
    """
    print()
    print(create_box(text, title="USER"))
    print()

def print_agent_action(tool_name: str):
    """
    Print when the agent is using a tool.
    
    Args:
        tool_name: Name of the tool being used
    """
    message = f"Agent: using tool: {tool_name}"
    print("\n" + message)
    print("-" * len(message))

def print_tool_result(tool_name: str, result: Dict[str, Any]):
    """
    Print the result from a tool execution.
    
    Args:
        tool_name: Name of the tool that was executed
        result: Result dictionary from the tool
    """
    # Create header
    success = result.get("success", False)
    status = "OK" if success else "ERROR"
    header = f"[{tool_name}] {status}"
    
    print("\n" + header)
    print("-" * len(header))
    
    # Print output
    output_data = result.get("output")
    if isinstance(output_data, (dict, list)):
        try:
            print(json.dumps(output_data, indent=2))
        except (TypeError, ValueError):
            print(str(output_data))
    else:
        print(textwrap.fill(str(output_data or ""), width=BOX_WIDTH))
    
    # Print metadata if present
    meta = result.get("meta")
    if meta:
        print("\nMeta:")
        print(json.dumps(meta, indent=2))
    
    print("-" * len(header) + "\n")

def print_error(message: str):
    """
    Print an error message.
    
    Args:
        message: Error message to display
    """
    print("\n[ERROR]")
    print(message)
    print()

def print_help():
    """
    Print help information in a formatted box.
    """
    help_content = (
        "Commands:\n"
        "  help              Show this help\n"
        "  exit              Exit the program\n"
        "  list files        List all files in the repository\n"
        "\n"
        "Natural language examples:\n"
        "  'read main.py'                    - Read a file\n"
        "  'find all TODO comments'          - Search for text\n"
        "  'create a new file called test.py' - Create a file\n"
        "  'edit main.py to add a comment'   - Edit a file\n"
        "\n"
        "Direct tool commands:\n"
        "  read filename     - Read a file\n"
        "  grep pattern      - Search for text\n"
        "  ls [directory]    - List files\n"
        "  write file content - Create a file"
    )
    print_boxed("HELP", help_content)
