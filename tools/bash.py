"""
Bash Command Tool for CodeGen2

This tool executes bash commands safely within the workspace.
It includes security checks to prevent dangerous operations.
"""

import shlex
import subprocess
from typing import List, Dict, Any, Union

# Commands that are not allowed for security reasons
DISALLOWED_COMMANDS = {
    "sudo", "ssh", "scp", "rm -rf", "reboot", "shutdown", "poweroff",
    "su", "passwd", "chmod 777", "chown", "dd", "mkfs", "fdisk"
}

def is_command_allowed(command: List[str]) -> tuple[bool, str]:
    """
    Check if a command is allowed to execute.
    
    Args:
        command: List of command parts
        
    Returns:
        Tuple of (is_allowed, blocked_reason)
    """
    # Join command parts and convert to lowercase for checking
    joined_command = " ".join(command).lower()
    
    # Check against disallowed commands
    for disallowed in DISALLOWED_COMMANDS:
        if disallowed in joined_command:
            return False, disallowed
    
    return True, None

def call(command: Union[str, List[str]], *args, **kwargs) -> Dict[str, Any]:
    """
    Execute a bash command safely.
    
    Args:
        command: Command to execute (string or list)
        *args: Additional positional arguments (ignored)
        **kwargs: Keyword arguments including:
            timeout_ms: Timeout in milliseconds (default: 120000 = 2 minutes)
            description: Optional description of what the command does
        
    Returns:
        Dictionary with success status and command output
    """
    # Extract parameters from kwargs
    timeout_ms = kwargs.get("timeout_ms", 120000)
    description = kwargs.get("description")
    # Validate input
    if not command:
        return {
            "tool": "bash",
            "success": False,
            "output": "No command provided."
        }
    
    # Parse command into list
    if isinstance(command, str):
        try:
            cmd_list = shlex.split(command)
        except ValueError as e:
            return {
                "tool": "bash",
                "success": False,
                "output": f"Invalid command syntax: {e}"
            }
    elif isinstance(command, list):
        cmd_list = []
        for part in command:
            if isinstance(part, str):
                try:
                    cmd_list.extend(shlex.split(part))
                except ValueError:
                    cmd_list.append(part)
            else:
                cmd_list.append(str(part))
    else:
        return {
            "tool": "bash",
            "success": False,
            "output": "Command must be a string or list."
        }
    
    # Check if command is allowed
    allowed, blocked_reason = is_command_allowed(cmd_list)
    if not allowed:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Command blocked for security: '{blocked_reason}'"
        }
    
    # Execute the command
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,  # Convert to seconds
            cwd=None  # Use current working directory
        )
        
        # Get output (stdout or stderr if stdout is empty)
        output = result.stdout.strip() or result.stderr.strip()
        
        return {
            "tool": "bash",
            "success": True,
            "output": output,
            "meta": {
                "command": " ".join(cmd_list),
                "return_code": result.returncode,
                "timeout_ms": timeout_ms
            }
        }
        
    except subprocess.TimeoutExpired:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Command timed out after {timeout_ms}ms"
        }
    except FileNotFoundError:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Command not found: {cmd_list[0]}"
        }
    except Exception as e:
        return {
            "tool": "bash",
            "success": False,
            "output": f"Command execution error: {e}"
        }
