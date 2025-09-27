#!/usr/bin/env python3
"""
main.py - CLI coding agent (updated)

This file implements:
- REPL for natural language and direct tool invocations
- Plan generation via Gemini (google.genai) client
- Plan validation, confirmation for destructive steps
- Conservative Write->Edit conversion when user intent suggests "change"
- History persistence in history.json

Note: This version uses output.print_user_box(...) (backwards-compatible name).
"""

import os
import json
import traceback
from datetime import datetime
from typing import Tuple, Any, Dict, List

# optional: load .env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# try import google genai
try:
    from google import genai  # type: ignore
except Exception:
    genai = None

API_KEY = os.environ.get("GEMINI_API_KEY")
CLIENT = None
if genai is not None and API_KEY:
    try:
        CLIENT = genai.Client(api_key=API_KEY)
    except Exception:
        CLIENT = None

# repo paths
WORKSPACE_ROOT = os.getcwd()
SYSTEM_PROMPT_PATH = os.path.join(WORKSPACE_ROOT, "system_prompt.txt")
BEHAVIOR_PATH = os.path.join(WORKSPACE_ROOT, "behavior.md")
HISTORY_PATH = os.path.join(WORKSPACE_ROOT, "history.json")

# internal modules (must exist)
from call_tools import dispatch_tool
import output  # assumed present in repo for pretty printing

# destructive tool names
DESTRUCTIVE_TOOLS = {"write", "edit", "multiedit", "bash", "Write", "Edit", "MultiEdit", "Bash"}

# -------------------------
# History helpers
# -------------------------
def load_history(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data[-limit:]
    except FileNotFoundError:
        return []
    except Exception:
        return []

def append_history(user_text: str, agent_plan: Any, results: Any):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user_text,
        "agent_plan": agent_plan,
        "results": results
    }
    hist = load_history(limit=1000)
    hist.append(entry)
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2)
    except Exception:
        pass

# -------------------------
# Prompt building
# -------------------------
def _load_system_behavior_and_history(history_limit: int = 8):
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_text = f.read()
    except Exception:
        system_text = "SYSTEM PROMPT MISSING"

    try:
        with open(BEHAVIOR_PATH, "r", encoding="utf-8") as f:
            behavior_text = f.read()
    except Exception:
        behavior_text = ""

    hist = load_history(limit=history_limit)
    lines = []
    for h in hist:
        t = h.get("timestamp", "")
        u = h.get("user", "")
        plan = h.get("agent_plan", "")
        if isinstance(plan, dict):
            steps = plan.get("steps", [])
            tools = [s.get("tool") for s in steps if isinstance(s, dict)]
            explain = plan.get("explain", "")
            plan_snip = f"tools={tools}, explain={explain}"
        else:
            plan_snip = str(plan)
        lines.append(f"[{t}] USER: {u}\n[{t}] AGENT_PLAN: {plan_snip}")
    history_block = "\n\n".join(lines) if lines else "(no recent history)"
    return system_text, behavior_text, history_block

# -------------------------
# LLM call (single-string contents)
# -------------------------
def call_llm_structured(user_text: str, max_output_tokens: int = 1024, temperature: float = 0.0) -> Tuple[str, str]:
    """
    Compose single-string prompt and call genai.Client.models.generate_content.
    Returns ("OK", text) or ("ERROR:CODE", message).
    """
    if CLIENT is None:
        if genai is None:
            return ("ERROR:NO_CLIENT", "google.genai not available. Install google-genai==1.12.1.")
        if not API_KEY:
            return ("ERROR:NO_KEY", "GEMINI_API_KEY not set in environment or .env.")
        try:
            client = genai.Client(api_key=API_KEY)
        except Exception as e:
            return ("ERROR:CLIENT_INIT", f"Failed to init genai.Client: {e}")
    else:
        client = CLIENT

    system_text, behavior_text, history_block = _load_system_behavior_and_history(history_limit=8)

    parts = []
    parts.append("<SYSTEM_PROMPT_START>")
    parts.append(system_text.strip())
    parts.append("<SYSTEM_PROMPT_END>\n")

    if behavior_text:
        parts.append("<BEHAVIOR_START>")
        parts.append(behavior_text.strip())
        parts.append("<BEHAVIOR_END>\n")

    if history_block:
        parts.append("<RECENT_HISTORY_START>")
        parts.append(history_block.strip())
        parts.append("<RECENT_HISTORY_END>\n")

    parts.append("<USER_INSTRUCTION_START>")
    parts.append(user_text.strip())
    parts.append("<USER_INSTRUCTION_END>\n")

    parts.append("IMPORTANT: Return ONLY a single valid JSON object that matches the plan schema exactly.")
    prompt = "\n\n".join(parts)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,  # single string for compatibility
            config={"temperature": float(temperature), "max_output_tokens": int(max_output_tokens)}
        )
    except Exception as e:
        return ("ERROR:CALL_FAILED", f"LLM call failed: {e}\n{traceback.format_exc()}")

    try:
        text = getattr(response, "text", None)
        if text:
            return ("OK", text)
        out = getattr(response, "output", None) or getattr(response, "outputs", None)
        if isinstance(out, str):
            return ("OK", out)
        if isinstance(out, (list, tuple)) and len(out) > 0:
            first = out[0]
            if isinstance(first, dict):
                content = first.get("content") or first.get("text")
                if isinstance(content, str):
                    return ("OK", content)
            return ("OK", str(first))
        if isinstance(response, dict) and "candidates" in response:
            cands = response.get("candidates", [])
            if isinstance(cands, list) and cands:
                cand0 = cands[0]
                if isinstance(cand0, dict):
                    cont = cand0.get("content") or cand0.get("text")
                    if isinstance(cont, str):
                        return ("OK", cont)
                else:
                    return ("OK", str(cand0))
        return ("OK", str(response))
    except Exception as e:
        return ("ERROR:EXTRACTION", f"Failed to extract text: {e}\n{traceback.format_exc()}")

# -------------------------
# Plan validation & parsing
# -------------------------
def validate_plan(plan: Any):
    if not isinstance(plan, dict):
        return False, ["Plan must be a JSON object."]
    if "steps" not in plan or not isinstance(plan["steps"], list):
        return False, ["Plan must contain 'steps' list."]
    msgs = []
    for i, step in enumerate(plan["steps"], start=1):
        if not isinstance(step, dict):
            msgs.append(f"Step {i} must be an object.")
            continue
        tool = step.get("tool")
        if not tool or not isinstance(tool, str):
            msgs.append(f"Step {i}: missing or invalid 'tool'.")
        args = step.get("args", [])
        if not isinstance(args, list):
            msgs.append(f"Step {i}: 'args' must be a list.")
        kwargs = step.get("kwargs", {})
        if kwargs is not None and not isinstance(kwargs, dict):
            msgs.append(f"Step {i}: 'kwargs' must be an object.")
    return (len(msgs) == 0), msgs

def generate_plan(user_text: str, retries: int = 1):
    status, reply = call_llm_structured(user_text, max_output_tokens=1024, temperature=0.0)
    if not status.startswith("OK"):
        return False, reply

    raw = reply.strip()
    plan = None
    try:
        plan = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start:end+1]
            try:
                plan = json.loads(candidate)
            except Exception:
                if retries > 0:
                    reprompt = ("Your previous response could not be parsed as JSON. Return ONLY a single valid JSON object matching the schema.")
                    s2, r2 = call_llm_structured(reprompt, max_output_tokens=256)
                    if not s2.startswith("OK"):
                        return False, r2
                    try:
                        plan = json.loads(r2.strip())
                    except Exception:
                        return False, f"Failed to parse JSON after retry. Raw output:\n{r2}"
                else:
                    return False, f"Failed to parse JSON. Raw output:\n{raw}"
        else:
            return False, "Model output did not contain JSON."

    valid, msgs = validate_plan(plan)
    if not valid:
        return False, {"validation_errors": msgs}

    if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and len(plan.get("steps")) == 0:
        reprompt = ("You returned an empty plan. If the user's instruction was actionable, produce a JSON plan with steps. Otherwise return {\"steps\": [], \"explain\": \"No specific action requested.\"}. Return ONLY JSON.")
        s2, r2 = call_llm_structured(reprompt, max_output_tokens=256)
        if s2.startswith("OK"):
            try:
                plan2 = json.loads(r2.strip())
                valid2, _ = validate_plan(plan2)
                if valid2:
                    return True, plan2
            except Exception:
                pass

    return True, plan

# -------------------------
# Small-talk handlers
# -------------------------
def read_behavior_snippet(max_chars: int = 1200) -> str:
    try:
        with open(BEHAVIOR_PATH, "r", encoding="utf-8") as f:
            t = f.read()
            return (t[:max_chars] + "...") if len(t) > max_chars else t
    except Exception:
        return ""

def last_agent_explain() -> str:
    hist = load_history(limit=20)
    for e in reversed(hist):
        plan = e.get("agent_plan", {})
        if isinstance(plan, dict):
            explain = plan.get("explain")
            if explain:
                return explain
    return ""

def handle_small_talk(user_text: str) -> bool:
    s = user_text.strip().lower()
    greetings = {"hi", "hii", "hello", "hey", "heyy", "hiya", "yo"}
    if s in greetings:
        print("Assistant: Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True

    if "what can you do" in s or "what do you do" in s or "capabilities" in s:
        reply = "I can inspect, search, modify, and manage files in this repository (read, ls, glob, grep, write, edit, multiedit, todowrite, webfetch, websearch, bash)."
        print("Assistant:", reply)
        append_history(user_text, {"steps": [], "explain": "capabilities_reply"}, [])
        return True

    if "your name" in s or "who are you" in s:
        print("Assistant: I am a local CLI coding assistant (Agent). I work on this repo's files.")
        append_history(user_text, {"steps": [], "explain": "name_reply"}, [])
        return True

    short_small = {"thanks", "thank you", "bye", "goodbye"}
    for marker in short_small:
        if marker in s:
            print("Assistant: You're welcome.")
            append_history(user_text, {"steps": [], "explain": "small_talk_reply"}, [])
            return True

    return False

# -------------------------
# Simple tokenization & parsing (avoid shlex on freeform text)
# -------------------------
def _simple_split_first_word(line: str) -> str:
    """
    Return the first whitespace-separated token (lowercased).
    This avoids shlex parsing errors on natural language.
    """
    if not line:
        return ""
    return line.strip().split()[0].lower()

def is_likely_natural_language(line: str) -> bool:
    """
    Heuristic: if first token matches a known tool name, treat as tool invocation.
    Otherwise treat as natural language instruction.
    """
    first = _simple_split_first_word(line)
    known_tools = {"read", "ls", "glob", "grep", "write", "edit", "multiedit", "todowrite", "webfetch", "websearch", "bash", "task", "exitplanmode", "todo"}
    if first in ("help", "exit", "quit"):
        return False
    return first not in known_tools

def parse_as_tool_invocation(line: str):
    """
    Very simple parser for tool invocations:
      read path
      ls /abs/path
      write file.txt "some content"
    We use basic whitespace splitting to avoid shlex-related errors.
    If the user provides JSON (starts with { or [), parse with json.loads.
    """
    s = line.strip()
    if not s:
        return None
    if s.startswith("{") or s.startswith("["):
        try:
            return json.loads(s)
        except Exception:
            return None
    parts = s.split()
    tool = parts[0]
    args = parts[1:]
    kwargs = {}
    # Special-case: if user typed "list files" or "list all files", handle separately
    if tool.lower() in ("list",) and len(args) >= 1 and args[0].lower().startswith("file"):
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    if tool.lower() == "ls" and not args:
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    return {"tool": tool, "args": args, "kwargs": kwargs}

# -------------------------
# Helper: recursive repo listing (ignores noisy dirs)
# -------------------------
def list_repo_files_recursive(root: str = ".", ignore_dirs: List[str] = None) -> List[str]:
    """
    Walk the workspace root and return a sorted list of repo-relative file paths.
    Ignores typical noisy directories.
    """
    if ignore_dirs is None:
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", ".env", ".cache", ".pytest_cache"}
    else:
        ignore_dirs = set(ignore_dirs)
    root_path = os.path.abspath(root)
    files_out = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # compute relative path parts
        # remove ignored directories from traversal in-place
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".") or d in (".",)]
        # also skip if path contains ignored components
        rel_dir = os.path.relpath(dirpath, root_path)
        if rel_dir == ".":
            rel_dir = ""
        # add files
        for fn in filenames:
            if fn in (".env",):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_path)
            files_out.append(rel)
    files_out.sort()
    return files_out

def print_recursive_listing():
    files = list_repo_files_recursive(".")
    try:
        output.print_boxed("Repository files (recursive)", "\n".join(files[:5000]))
    except Exception:
        print("--- Repository files (recursive) ---")
        for p in files:
            print(p)

# -------------------------
# Convert Write->Edit when user intent is "change"
# -------------------------
def maybe_convert_write_to_edit(plan: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        return plan
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return plan

    change_verbs = {"change", "modify", "replace", "update", "edit"}
    lower_user = user_text.lower()
    intends_change = any(v in lower_user for v in change_verbs)

    new_steps = []
    for step in steps:
        if not isinstance(step, dict):
            new_steps.append(step)
            continue
        tool = step.get("tool", "").lower()
        if tool == "write":
            args = step.get("args", []) or []
            kwargs = step.get("kwargs", {}) or {}
            target = args[0] if len(args) >= 1 else None
            new_content = args[1] if len(args) >= 2 else ""
            force_flag = bool(kwargs.get("force", False))
            if target and not force_flag and intends_change:
                from pathlib import Path
                p = Path(target)
                if not p.is_absolute():
                    p = Path.cwd() / p
                if p.exists():
                    read_res = dispatch_tool({"tool": "read", "args": [str(target)]})
                    existing = ""
                    if isinstance(read_res, dict) and read_res.get("success"):
                        out = read_res.get("output", {})
                        if isinstance(out, dict):
                            existing = out.get("content", "")
                        elif isinstance(out, str):
                            existing = out
                    else:
                        try:
                            with open(p, "r", encoding="utf-8", errors="replace") as f:
                                existing = f.read()
                        except Exception:
                            existing = ""
                    edit_step = {
                        "tool": "Edit",
                        "args": [str(target), existing, new_content, {"replace_all": False}],
                        "kwargs": {}
                    }
                    new_steps.append(edit_step)
                    continue
        new_steps.append(step)
    plan["steps"] = new_steps
    return plan

# -------------------------
# REPL
# -------------------------
def print_intro():
    print("CLI Coding Agent — workspace:", WORKSPACE_ROOT)
    print("Type 'help' for help. Non-destructive steps run immediately. Destructive steps require confirmation.")

def repl():
    print_intro()
    while True:
        try:
            line = input("\n>>> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if line is None:
            continue
        line = line.rstrip("\n")
        if not line.strip():
            continue

        # Handle special-case commands (exact)
        low = line.strip().lower()
        if low in ("help", "--help", "-h"):
            try:
                output.print_help_box()
            except Exception:
                print("Help: try natural language or tool invocations like 'read README.md' or 'list files'.")
            continue
        if low in ("exit", "quit"):
            print("Bye.")
            break

        # Special-case list files phrases and handle locally with recursive listing
        if low in ("list files", "list all files", "ls -r", "ls -R"):
            print_recursive_listing()
            append_history(line, {"steps": [], "explain": "list_files_recursive"}, [])
            continue

        # shortcut: todo
        if low.startswith("todo "):
            parsed = parse_as_tool_invocation("todowrite " + line[len("todo "):])
            res = dispatch_tool(parsed)
            output.print_result(parsed.get("tool"), res)
            append_history(line, parsed, [res])
            continue

        # If looks like direct tool invocation, parse & dispatch
        if not is_likely_natural_language(line):
            parsed = parse_as_tool_invocation(line)
            if parsed is None:
                output.print_error("Could not parse tool invocation.")
                continue

            # if ls with args empty default to recursive listing
            if parsed.get("tool", "").lower() == "ls":
                try:
                    res = dispatch_tool(parsed)
                    output.print_result(parsed.get("tool"), res)
                    append_history(line, parsed, [res])
                except Exception as e:
                    output.print_error(f"LS tool failed: {e}")
                continue

            results = dispatch_tool(parsed)
            output.print_result(parsed.get("tool"), results)
            append_history(line, parsed, [results])
            continue

        # Natural language path
        user_text = line
        # <-- changed here: use print_user_box (Option A)
        output.print_user_box(user_text)

        # Small talk handled locally
        if handle_small_talk(user_text):
            continue

        # Generate plan
        ok, plan_or_err = generate_plan(user_text, retries=1)
        if not ok:
            output.print_error(f"LLM plan generation failed: {plan_or_err}")
            append_history(user_text, {"error": str(plan_or_err)}, [])
            continue
        plan = plan_or_err

        # If plan empty and explain present, show explain
        if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and len(plan.get("steps")) == 0:
            explain = plan.get("explain", "").strip()
            if explain:
                print("Assistant:", explain)
                append_history(user_text, plan, [])
                continue

        # detect destructive steps
        destructive = []
        for i, s in enumerate(plan.get("steps", []), start=1):
            tool_name = s.get("tool", "").lower() if isinstance(s, dict) else ""
            if tool_name in DESTRUCTIVE_TOOLS:
                destructive.append((i, s))

        run_full_plan = True
        if destructive:
            output.print_boxed("Plan Summary (before execution)", plan.get("explain", "(no explain)"))
            print("Can I make these changes?")
            for idx, step in destructive:
                print(f"  {idx}. {step.get('tool')} args={step.get('args')}")
            ans = input("(y/n) ").strip().lower()
            if ans not in ("y", "yes"):
                run_full_plan = False

        steps_to_run = plan.get("steps", [])
        if not run_full_plan and destructive:
            steps_to_run = [s for s in steps_to_run if not (isinstance(s, dict) and s.get("tool", "").lower() in DESTRUCTIVE_TOOLS)]
            if not steps_to_run:
                print("No non-destructive steps to run. Skipping.")
                append_history(user_text, plan, [])
                continue
            print("Running non-destructive steps only (destructive skipped).")

        # Convert Write -> Edit conservatively for "change"-like user intents
        plan_for_dispatch = {"steps": steps_to_run, "explain": plan.get("explain", "")}
        plan_for_dispatch = maybe_convert_write_to_edit(plan_for_dispatch, user_text)

        # Dispatch steps
        to_dispatch = {"steps": plan_for_dispatch.get("steps", [])}
        results = dispatch_tool(to_dispatch)

        # Print results
        if isinstance(results, list):
            for r in results:
                tool_name = r.get("tool", "<unknown>")
                output.print_agent_tool_use(tool_name)
                output.print_result(tool_name, r)
        else:
            tool_name = results.get("tool", "<unknown>")
            output.print_agent_tool_use(tool_name)
            output.print_result(tool_name, results)

        append_history(user_text, plan, results if isinstance(results, list) else [results])

if __name__ == "__main__":
    repl()
