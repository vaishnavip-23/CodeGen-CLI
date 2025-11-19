# File Summary: Implementation of the Bash tool for executing shell commands safely.

"""
Bash tool - executes shell commands safely with security restrictions.
Refactored to use Gemini's native Pydantic function calling with from_callable().
"""

import shlex
import subprocess
from typing import List, Dict, Any, Union, Optional

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import BashInput, BashOutput

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


def run_command(command: str, timeout: Optional[int] = None, description: str = "", run_in_background: bool = False) -> BashOutput:
    """Execute a shell command safely.
    
    Runs a shell command and returns the output. Use for running tests, building,
    or any command-line operations. Dangerous commands are blocked for security.
    
    Args:
        command: The command to execute
        timeout: Optional timeout in milliseconds (default 120000, max 600000)
        description: Clear, concise description of what this command does
        run_in_background: Set to true to run in background (not implemented yet)
        
    Returns:
        BashOutput Pydantic model containing output, exit code, and optional shell ID.
    """
    # Validate using Pydantic model
    try:
        input_data = BashInput(
            command=command,
            timeout=timeout,
            description=description,
            run_in_background=run_in_background
        )
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    timeout_ms = input_data.timeout if input_data.timeout else 120000
    cmd = input_data.command
    
    # Check if command contains shell features (pipes, redirections, etc.)
    shell_features = ['|', '>', '<', '&', ';', '&&', '||', '2>&1']
    use_shell = False
    
    if isinstance(cmd, str):
        # Check if we need shell mode
        use_shell = any(feature in cmd for feature in shell_features)
        
        if not use_shell:
            try:
                command_parts = shlex.split(cmd)
            except ValueError as e:
                return {
                    "tool": "bash",
                    "success": False,
                    "output": f"Invalid command syntax: {e}"
                }
        else:
            # For shell commands, keep as string
            command_parts = cmd
    else:
        command_parts = cmd
    
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
        
        output = BashOutput(
            output=output_text,
            exitCode=result.returncode,
            killed=False,
            shellId=None
        )
        return output
        
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout_ms}ms")
    except Exception as e:
        raise IOError(f"Error executing command: {e}")


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=run_command
    )


# Keep backward compatibility
def call(command: Union[str, List[str]], *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    cmd_str = command if isinstance(command, str) else " ".join(command)
    result = run_command(
        command=cmd_str,
        timeout=kwargs.get("timeout"),
        description=kwargs.get("description", ""),
        run_in_background=kwargs.get("run_in_background", False)
    )
    return result.model_dump()
