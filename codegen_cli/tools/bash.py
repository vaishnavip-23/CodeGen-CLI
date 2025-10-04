# File Summary: Implementation of the Bash tool for executing shell commands safely.

"""
Bash tool - executes shell commands safely with security restrictions.
"""

import shlex
import subprocess
from typing import List, Dict, Any, Union

try:
    from google.genai import types
except ImportError:
    types = None

DISALLOWED_COMMANDS = {
    "sudo", "ssh", "scp", "rm -rf", "reboot", "shutdown", "poweroff",
    "su", "passwd", "chmod 777", "chown", "dd", "mkfs", "fdisk"
}

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "run_command",
    "description": "Execute a shell command safely. Use only when no specialized tool exists. Dangerous commands are blocked.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute"
            },
            "description": {
                "type": "string",
                "description": "Description of what this command does"
            }
        },
        "required": ["command"]
    }
}

def get_function_declaration():
    """Get Gemini function declaration for this tool."""
    if types is None:
        return None
    
    return types.FunctionDeclaration(
        name=FUNCTION_DECLARATION["name"],
        description=FUNCTION_DECLARATION["description"],
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "command": types.Schema(type=types.Type.STRING, description="Shell command to execute"),
                "description": types.Schema(type=types.Type.STRING, description="Description of what this command does")
            },
            required=["command"]
        )
    )

def is_command_allowed(command: List[str]) -> tuple[bool, str]:
    """Check if command is allowed to execute."""
    joined_command = " ".join(command).lower()
    
    for disallowed in DISALLOWED_COMMANDS:
        if disallowed in joined_command:
            return False, f"Command '{disallowed}' is not allowed for security reasons"
    
    return True, ""

def call(command: Union[str, List[str]], *args, **kwargs) -> Dict[str, Any]:
    """Execute bash command safely."""
    timeout_ms = kwargs.get("timeout_ms", 120000)
    description = kwargs.get("description")
    
    # Check if command contains shell features (pipes, redirections, etc.)
    shell_features = ['|', '>', '<', '&', ';', '&&', '||', '2>&1']
    use_shell = False
    
    if isinstance(command, str):
        # Check if we need shell mode
        use_shell = any(feature in command for feature in shell_features)
        
        if not use_shell:
            try:
                command_parts = shlex.split(command)
            except ValueError as e:
                return {
                    "tool": "bash",
                    "success": False,
                    "output": f"Invalid command syntax: {e}"
                }
        else:
            # For shell commands, keep as string
            command_parts = command
    else:
        command_parts = command
    
    if not command_parts:
        return {
            "tool": "bash",
            "success": False,
            "output": "No command provided"
        }
    
    # Security check
    check_cmd = command_parts if isinstance(command_parts, str) else " ".join(command_parts)
    allowed, reason = is_command_allowed([check_cmd])
    if not allowed:
        return {
            "tool": "bash",
            "success": False,
            "output": reason
        }
    
    try:
        if use_shell:
            # Use shell mode for complex commands
            result = subprocess.run(
                command_parts,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0
            )
        else:
            # Use array mode for simple commands (safer)
            result = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0
            )
        
        output_text = result.stdout
        if result.stderr:
            output_text += f"\nSTDERR:\n{result.stderr}"
        
        return {
            "tool": "bash",
            "success": result.returncode == 0,
            "output": output_text,
            "return_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Command timed out after {timeout_ms}ms"
        }
    except Exception as e:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Error executing command: {e}"
        }
