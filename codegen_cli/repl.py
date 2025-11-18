# File Summary: New REPL using agentic loop instead of one-shot planning.

"""
REPL for CodeGen CLI.

Uses iterative decision-making with Gemini function calling.
"""

import os
import shutil
import sys
import textwrap
from typing import Any, Dict

from .call_tools import create_agentic_loop
from .conversation_memory import ConversationMemory


def _prompt_user_input_box(output_module) -> str:
    """Prompt user for input with styled box."""
    color = output_module.Color
    border = color.BORDER
    reset = color.RESET
    title = "Prompt"
    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    target_width = output_module._current_box_width()
    width = max(40, min(term_width - 2, target_width))
    inner = width - 4
    top = f"{border}╭{'─' * (width - 2)}╮{reset}"
    header = title.upper().center(inner)
    header_line = f"{border}│{reset} {color.TITLE}{header}{reset} {border}│{reset}"
    bottom = f"{border}╰{'─' * (width - 2)}╯{reset}"

    print()
    print(top)
    print(header_line)
    instructions = [
        "Type your instruction and press Enter.",
        "Natural language requests are welcome; commands are optional."
    ]
    for line in instructions:
        wrapped = textwrap.wrap(line, inner) or [""]
        for segment in wrapped:
            print(f"{border}│{reset} {color.TEXT}{segment.ljust(inner)}{reset} {border}│{reset}")

    print(f"{border}│{reset} {' ' * inner} {border}│{reset}")
    prompt_prefix = f"{border}│{reset} "

    sys.stdout.write(prompt_prefix)
    sys.stdout.flush()

    raw = sys.stdin.readline()
    if raw == "":
        print(bottom)
        raise EOFError
    user_line = raw.rstrip("\n")

    wrapped_input = textwrap.wrap(user_line, inner) or [""]
    sys.stdout.write("\x1b[1A")
    for idx, segment in enumerate(wrapped_input):
        if idx > 0:
            sys.stdout.write(f"{border}│{reset} {' ' * inner} {border}│{reset}\n")
        line_content = f"{border}│{reset} {color.TEXT}{segment.ljust(inner)}{reset} {border}│{reset}"
        sys.stdout.write("\r\x1b[2K" + line_content + "\n")
    print(bottom)
    return user_line


def _print_intro(workspace_root: str, project_info: Dict[str, Any], has_key: bool, output_module):
    """Print welcome banner."""
    color = output_module.Color

    title_line = f"{color.ACCENT}{color.BOLD}CodeGen CLI{color.RESET} {color.MUTED}— Universal Coding Agent{color.RESET}"

    # Build language display with framework if available
    lang_display = project_info['language']
    if project_info.get('framework'):
        lang_display = f"{project_info['language']} ({project_info['framework']})"
    
    details = [
        f"{color.MUTED}Workspace:{color.RESET} {workspace_root}",
        f"{color.MUTED}Language:{color.RESET} {lang_display}",
    ]

    if project_info.get('package_manager'):
        details.append(f"{color.MUTED}Package Manager:{color.RESET} {project_info['package_manager']}")

    key_color = color.SUCCESS if has_key else color.ERROR
    key_label = "set" if has_key else "missing"
    details.append(f"{color.MUTED}Gemini API key:{color.RESET} {key_color}{key_label}{color.RESET}")

    tips = [
        f"{color.ACCENT}Tips{color.RESET}:",
        "  • Keep CodeGen updated to get latest improvements",
        "  • Agent works iteratively: discovers, plans, executes",
        "  • Type 'help' for guidance",
    ]

    if not has_key:
        tips.append(f"  • {color.ERROR}Tip:{color.RESET} run 'codegen --set-key' or add GEMINI_API_KEY to your .env")

    banner_body = "\n".join([title_line, ""] + details + [""] + tips)

    output_module.print_boxed("Welcome", banner_body, style="banner")


def run_repl(deps: Dict[str, Any]) -> None:
    """Run the REPL with agentic loop and function calling.
    
    Expected deps:
      - workspace_root: str
      - project_info: dict
      - output: module with print_* functions
      - handle_small_talk: function for small talk handling
      - append_history: callable
      - ensure_client: callable -> client or None
    """
    workspace_root = deps["workspace_root"]
    project_info = deps["project_info"]
    output = deps["output"]
    handle_small_talk = deps["handle_small_talk"]
    append_history = deps["append_history"]
    ensure_client = deps["ensure_client"]

    client = ensure_client()
    if client is None:
        output.print_error("Failed to initialize Gemini client. Check your API key.")
        return

    # Initialize conversation memory (maintains context across tasks)
    conversation_memory = ConversationMemory(max_tasks=10)
    
    # Initialize agentic loop (tools are loaded automatically from registry)
    agent = create_agentic_loop(client, output, conversation_memory)

    _print_intro(workspace_root, project_info, bool(os.environ.get("GEMINI_API_KEY")), output)

    while True:
        try:
            line = _prompt_user_input_box(output)
        except (EOFError, KeyboardInterrupt):
            output.print_info("Exiting session.", title="Session")
            break
        if line is None:
            continue
        line = line.rstrip("\n")
        if not line.strip():
            continue

        low = line.strip().lower()
        
        # Handle built-in commands
        if low in ("help", "--help", "-h"):
            try:
                output.print_help(project_info)
            except Exception:
                output.print_assistant("Help: try natural language or tool invocations.")
            continue
        if low in ("exit", "quit"):
            output.print_assistant("Bye.")
            break

        # Handle small talk
        if handle_small_talk(line, append_history):
            continue

        # Run agentic loop
        try:
            # Clear todos at start of each new task for fresh slate
            from .tools.todowrite import clear_todos
            clear_todos()
            
            print(f"\n{output.Color.TITLE}Starting task: {line}{output.Color.RESET}")
            
            # Max iterations = max API calls = max cost
            # Simple: 2-4, Analysis: 3-5, Modification: 10-30, Massive: 30-50
            # 50 iterations at $0.075/1M tokens ≈ $0.0075 (0.75 cents)
            state = agent.run(line, max_iterations=50)
            
            # Print summary
            if state.completed:
                # Extract summary from last observation if task_complete was called
                summary = ""
                for obs in reversed(state.conversation_history):
                    if obs.get("type") == "tool_result" and obs.get("tool") == "task_complete":
                        result = obs.get("result", {})
                        if isinstance(result, dict):
                            summary = result.get("output", "")
                        break
                
                # Simple completion message (efficiency metrics only in verbose/debug mode)
                output.print_success(f"✓ Task completed in {state.iterations} iterations")
                
                if summary:
                    print(f"\n{output.Color.BOLD}Summary:{output.Color.RESET}\n{summary}\n")
            else:
                error_msg = state.error or "Task incomplete"
                output.print_warning(f"Task stopped after {state.iterations} iterations: {error_msg}")
            
            # Extract and save task memory for conversation continuity
            task_memory = conversation_memory.extract_from_state(line, state)
            conversation_memory.add_task(task_memory)
            
            # Save to history
            history_summary = {
                "steps": [
                    {"iteration": i, "summary": "agentic_loop"} 
                    for i in range(state.iterations)
                ],
                "explain": f"Agentic loop completed in {state.iterations} iterations",
                "completed": state.completed
            }
            append_history(line, history_summary, state.conversation_history)
            
        except Exception as e:
            import traceback
            output.print_error(f"Agentic loop error: {e}\n{traceback.format_exc()}")
            append_history(line, {"error": str(e)}, [])
