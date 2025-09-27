"""
Bash tool - executes shell commands safely with security restrictions.
"""

import shlex
import subprocess
from typing import List, Dict, Any, Union

DISALLOWED_COMMANDS = {
    "sudo", "ssh", "scp", "rm -rf", "reboot", "shutdown", "poweroff",
    "su", "passwd", "chmod 777", "chown", "dd", "mkfs", "fdisk"
}

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
    
    if isinstance(command, str):
        try:
            command_parts = shlex.split(command)
        except ValueError as e:
            return {
                "tool": "bash",
                "success": False,
                "output": f"Invalid command syntax: {e}"
            }
    else:
        command_parts = command
    
    if not command_parts:
        return {
            "tool": "bash",
            "success": False,
            "output": "No command provided"
        }
    
    # Check if command is allowed
    allowed, reason = is_command_allowed(command_parts)
    if not allowed:
        return {
            "tool": "bash",
            "success": False,
            "output": reason
        }
    
    try:
        # Execute command
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