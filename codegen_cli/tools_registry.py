# File Summary: Central registry for all tools with function calling support.

"""
Tools registry for CodeGen CLI.

Provides centralized access to all available tools and their function declarations.
"""

import importlib
from typing import List, Dict, Any, Optional

try:
    from google.genai import types
except ImportError:
    types = None


# Map of tool names to their module names (only the essential tools)
TOOL_MODULES = {
    "read_file": "read",
    "write_file": "write",
    "edit_file": "edit",
    "multi_edit": "multiedit",
    "grep": "grep",
    "list_files": "ls",
    "find_files": "glob",
    "run_command": "bash",
    "delete_file": "delete",
    "manage_todos": "todowrite",
    "fetch_url": "webfetch",
    "search_web": "websearch",
}

# Map of legacy tool names to new names (for backwards compatibility)
LEGACY_TOOL_NAMES = {
    "read": "read_file",
    "write": "write_file",
    "edit": "edit_file",
    "multiedit": "multi_edit",
    "ls": "list_files",
    "glob": "find_files",
    "bash": "run_command",
    "delete": "delete_file",
    "todowrite": "manage_todos",
    "webfetch": "fetch_url",
    "websearch": "search_web",
}


def get_tool_module(tool_name: str):
    """Load a tool module by name (handles both new and legacy names)."""
    # Normalize to new name
    normalized_name = LEGACY_TOOL_NAMES.get(tool_name, tool_name)
    
    # Get module name
    module_name = TOOL_MODULES.get(normalized_name)
    if not module_name:
        # Try using tool name as module name
        module_name = tool_name
    
    try:
        return importlib.import_module(f"codegen_cli.tools.{module_name}")
    except ModuleNotFoundError:
        raise RuntimeError(f"Tool '{tool_name}' not found")


def get_all_function_declarations(client=None):
    """Get function declarations for all tools.
    
    Args:
        client: Gemini client instance (required for from_callable() in tools)
        
    Returns:
        List of FunctionDeclaration objects for all tools
    """
    if types is None:
        return []
    
    declarations = []
    for tool_name, module_name in TOOL_MODULES.items():
        try:
            module = importlib.import_module(f"codegen_cli.tools.{module_name}")
            if hasattr(module, 'get_function_declaration'):
                # Pass client to get_function_declaration for from_callable() support
                decl = module.get_function_declaration(client)
                if decl:
                    declarations.append(decl)
        except Exception as e:
            # Skip tools that fail to load (log error for debugging)
            import traceback
            print(f"Warning: Failed to load tool '{tool_name}': {e}")
            traceback.print_exc()
            continue
    
    # Add special task_complete function
    declarations.append(
        types.FunctionDeclaration(
            name="task_complete",
            description="Call this when the task is fully completed",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "summary": types.Schema(
                        type=types.Type.STRING,
                        description="Summary of what was accomplished"
                    )
                },
                required=["summary"]
            )
        )
    )
    
    return declarations


def get_tool_info(tool_name: str) -> Optional[Dict[str, Any]]:
    """Get information about a specific tool."""
    try:
        module = get_tool_module(tool_name)
        if hasattr(module, 'FUNCTION_DECLARATION'):
            return module.FUNCTION_DECLARATION
    except Exception:
        pass
    return None


def list_available_tools() -> List[str]:
    """List all available tool names."""
    return list(TOOL_MODULES.keys())
