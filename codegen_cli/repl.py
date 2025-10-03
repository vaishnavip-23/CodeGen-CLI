"""
REPL loop for CodeGen CLI.

This module contains the interactive loop and related helpers, keeping
`main.py` focused on configuration and orchestration.
"""

from typing import Any, Dict


def _print_intro(workspace_root: str, project_info: Dict[str, Any], has_key: bool, output_module):
    color = output_module.Color

    title_line = f"{color.ACCENT}{color.BOLD}CodeGen CLI{color.RESET} {color.MUTED}— Universal Coding Agent{color.RESET}"

    details = [
        f"{color.MUTED}Workspace:{color.RESET} {workspace_root}",
        f"{color.MUTED}Language:{color.RESET} {project_info['language']}",
    ]

    if project_info.get('package_manager'):
        details.append(f"{color.MUTED}Package Manager:{color.RESET} {project_info['package_manager']}")

    key_color = color.SUCCESS if has_key else color.ERROR
    key_label = "set" if has_key else "missing"
    details.append(f"{color.MUTED}Gemini API key:{color.RESET} {key_color}{key_label}{color.RESET}")

    tips = [
        f"{color.ACCENT}Tips{color.RESET}:",
        "  • Type 'help' for guidance or ask in natural language.",
        "  • Non-destructive steps run immediately; destructive ones ask first.",
        "  • Keep CodeGen-CLI up to date:",
        "      - Check latest: codegen --check-update",
        "      - Upgrade: pip install -U codegen-cli",
        "      - Pin specific: pip install codegen-cli==<version>",
        "      - PyPI: https://pypi.org/project/codegen-cli/",
    ]

    if not has_key:
        tips.append(f"  • {color.ERROR}Tip:{color.RESET} run 'codegen --set-key' or add GEMINI_API_KEY to your .env")

    banner_body = "\n".join([title_line, ""] + details + [""] + tips)

    output_module.print_boxed("Welcome", banner_body, style="banner")


def _simple_split_first_word(line: str) -> str:
    if not line:
        return ""
    return line.strip().split()[0].lower()


def _is_likely_natural_language(line: str) -> bool:
    first = _simple_split_first_word(line)
    known_tools = {
        "read", "ls", "glob", "grep", "write", "edit", "multiedit",
        "todowrite", "webfetch", "websearch", "bash", "task", "delete", "todo"
    }
    if first in ("help", "exit", "quit"):
        return False
    return first not in known_tools


def _parse_as_tool_invocation(line: str):
    s = line.strip()
    if not s:
        return None
    if s.startswith("{") or s.startswith("["):
        import json
        try:
            return json.loads(s)
        except Exception:
            return None
    parts = s.split()
    tool = parts[0]
    args = parts[1:]
    kwargs: Dict[str, Any] = {}
    if tool.lower() in ("list",) and len(args) >= 1 and args[0].lower().startswith("file"):
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    if tool.lower() == "ls" and not args:
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    return {"tool": tool, "args": args, "kwargs": kwargs}


def _print_recursive_listing(list_repo_files_recursive, output):
    files = list_repo_files_recursive(".")
    output.print_boxed("Repository files (recursive)", "\n".join(files[:5000]))


def run_repl(deps: Dict[str, Any]) -> None:
    """Run the interactive REPL.

    Expected deps:
      - workspace_root: str
      - project_info: dict
      - dispatch_tool: callable
      - output: module with print_* functions
      - faq_handlers: module with handle_small_talk(user_text, append_history)
      - append_history: callable(user_text, agent_plan, results)
      - list_repo_files_recursive: callable
      - maybe_convert_write_to_edit: callable
      - generate_plan: callable
      - destructive_tools: set[str]
      - ensure_client: callable -> client or None
    """
    workspace_root = deps["workspace_root"]
    project_info = deps["project_info"]
    dispatch_tool = deps["dispatch_tool"]
    output = deps["output"]
    faq_handlers = deps["faq_handlers"]
    append_history = deps["append_history"]
    list_repo_files_recursive = deps["list_repo_files_recursive"]
    maybe_convert_write_to_edit = deps["maybe_convert_write_to_edit"]
    generate_plan = deps["generate_plan"]
    destructive_tools = deps["destructive_tools"]
    ensure_client = deps["ensure_client"]

    ensure_client()
    import os
    _print_intro(workspace_root, project_info, bool(os.environ.get("GEMINI_API_KEY")), output)

    while True:
        try:
            line = input("\n>>> ")
        except (EOFError, KeyboardInterrupt):
            output.print_info("Exiting session.", title="Session")
            break
        if line is None:
            continue
        line = line.rstrip("\n")
        if not line.strip():
            continue

        low = line.strip().lower()
        if low in ("help", "--help", "-h"):
            try:
                output.print_help(project_info)
            except Exception:
                output.print_assistant("Help: try natural language or tool invocations like 'read README.md' or 'list files'.")
            continue
        if low in ("exit", "quit"):
            output.print_assistant("Bye.")
            break

        if low in ("list files", "list all files", "ls -r", "ls -R"):
            _print_recursive_listing(list_repo_files_recursive, output)
            append_history(line, {"steps": [], "explain": "list_files_recursive"}, [])
            continue

        if low.startswith("todo "):
            parsed = _parse_as_tool_invocation("todowrite " + line[len("todo "):])
            res = dispatch_tool(parsed)
            output.print_tool_result(parsed.get("tool"), res)
            append_history(line, parsed, [res])
            continue

        if not _is_likely_natural_language(line):
            parsed = _parse_as_tool_invocation(line)
            if parsed is None:
                output.print_error("Could not parse tool invocation.")
                continue

            if parsed.get("tool", "").lower() == "ls":
                try:
                    res = dispatch_tool(parsed)
                    output.print_tool_result(parsed.get("tool"), res)
                    append_history(line, parsed, [res])
                except Exception as e:
                    output.print_error(f"LS tool failed: {e}")
                continue

            results = dispatch_tool(parsed)
            output.print_tool_result(parsed.get("tool"), results)
            append_history(line, parsed, [results])
            continue

        user_text = line
        output.print_user_input(user_text)

        if faq_handlers.handle_small_talk(user_text, append_history):
            continue

        # Shortcut: common summaries/explanations -> Task tool directly (no LLM)
        lowered = user_text.lower().strip()
        summary_triggers = (
            "summarize the repo",
            "summarize repository",
            "summarize project",
            "summarize the entire repo",
            "summarize codebase",
            "summarize the codebase",
            "analyze repo",
            "analyze repository",
            "explain the codebase",
            "explain the repo",
            "explain project",
            "what does it do",
            "describe the repo",
            "describe the codebase",
            "overview of the repo",
            "overview of the codebase",
        )
        if any(k in lowered for k in summary_triggers):
            task_plan = {"steps": [{"tool": "task", "args": ["summarize repo", "", "general-purpose"], "kwargs": {}}]}
            results = dispatch_tool(task_plan)
            output.print_agent_action("Task")
            output.print_tool_result("Task", results if isinstance(results, dict) else results[0])
            append_history(user_text, task_plan, results if isinstance(results, list) else [results])
            continue

        # Inline code explanation: detect fenced code blocks and summarize without LLM
        if "```" in user_text:
            try:
                # Extract code between first pair of fences
                parts = user_text.split("```")
                code_text = parts[1] if len(parts) >= 3 else ""
                if code_text.strip():
                    task_plan = {"steps": [{"tool": "task", "args": ["explain code", code_text, "code-summary"], "kwargs": {}}]}
                    results = dispatch_tool(task_plan)
                    output.print_agent_action("Task")
                    output.print_tool_result("Task", results if isinstance(results, dict) else results[0])
                    append_history(user_text, task_plan, results if isinstance(results, list) else [results])
                    continue
            except Exception:
                pass

        ok, plan_or_err = generate_plan(user_text, retries=1)
        if not ok:
            output.print_error(f"LLM plan generation failed: {plan_or_err}")
            append_history(user_text, {"error": str(plan_or_err)}, [])
            continue
        plan = plan_or_err

        if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and len(plan.get("steps")) == 0:
            explain = plan.get("explain", "").strip()
            if explain:
                output.print_assistant(explain)
                append_history(user_text, plan, [])
                continue

        destructive = []
        for i, s in enumerate(plan.get("steps", []), start=1):
            tool_name = s.get("tool", "").lower() if isinstance(s, dict) else ""
            if tool_name in destructive_tools:
                destructive.append((i, s))

        run_full_plan = True
        if destructive:
            output.print_boxed("Plan Summary (before execution)", plan.get("explain", "(no explain)"))
            prompt_lines = ["Can I make these changes?"]
            for idx, step in destructive:
                prompt_lines.append(f"  {idx}. {step.get('tool')} args={step.get('args')}")
            output.print_prompt("\n".join(prompt_lines), title="Confirm Changes")
            ans = input("(y/n) ").strip().lower()
            if ans not in ("y", "yes"):
                run_full_plan = False

        steps_to_run = plan.get("steps", [])
        if not run_full_plan and destructive:
            steps_to_run = [s for s in steps_to_run if not (isinstance(s, dict) and s.get("tool", "").lower() in destructive_tools)]
            if not steps_to_run:
                output.print_warning("No non-destructive steps to run. Skipping.", title="Plan")
                append_history(user_text, plan, [])
                continue
            output.print_warning("Running non-destructive steps only (destructive skipped).", title="Plan")

        plan_for_dispatch = {"steps": steps_to_run, "explain": plan.get("explain", "")}
        plan_for_dispatch = maybe_convert_write_to_edit(plan_for_dispatch, user_text)
        from .main import (
            filter_invalid_read_steps,
            inject_pre_delete_glob,
            resolve_edit_entire_old_content,
        )  # local import to avoid cycle at module load
        plan_for_dispatch = resolve_edit_entire_old_content(plan_for_dispatch, user_text)
        plan_for_dispatch = inject_pre_delete_glob(plan_for_dispatch)
        plan_for_dispatch = filter_invalid_read_steps(plan_for_dispatch)

        to_dispatch = {"steps": plan_for_dispatch.get("steps", [])}
        results = dispatch_tool(to_dispatch)

        if isinstance(results, list):
            for r in results:
                tool_name = r.get("tool", "<unknown>")
                output.print_agent_action(tool_name)
                output.print_tool_result(tool_name, r)
        else:
            tool_name = results.get("tool", "<unknown>")
            output.print_agent_action(tool_name)
            output.print_tool_result(tool_name, results)

        append_history(user_text, plan, results if isinstance(results, list) else [results])


