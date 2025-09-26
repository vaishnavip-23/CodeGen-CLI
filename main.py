#!/usr/bin/env python3
"""
main.py

Full CLI coding agent with history logging.

Behavior:
 - Uses Gemini (from google import genai) to convert user instructions into JSON plans.
 - Includes recent history entries from history.json into the LLM prompt so the agent can recall previous turns.
 - Runs non-destructive steps immediately.
 - If a plan contains destructive steps (write/edit/multiedit/bash), asks for plain-English confirmation.
 - If the user declines, runs only non-destructive steps.
 - After execution, appends an entry to history.json containing user, agent_plan, and results.

This file is kept simple and commented for beginners.
"""

import os
import json
import shlex
import traceback
import time
from datetime import datetime

# Files in repo root
SYSTEM_PROMPT_PATH = os.path.join(os.getcwd(), "system_prompt.txt")
BEHAVIOR_PATH = os.path.join(os.getcwd(), "behavior.md")
HISTORY_PATH = os.path.join(os.getcwd(), "history.json")

from call_tools import dispatch_tool
import output

WORKSPACE_ROOT = os.getcwd()
DESTRUCTIVE_TOOLS = {"write", "edit", "multiedit", "bash"}

# === History helpers ===
def load_history(limit=20):
    """Load history.json and return the last `limit` entries as a list."""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data[-limit:]
    except FileNotFoundError:
        return []
    except Exception:
        # In case of corrupt file, return empty list
        return []

def append_history(user_text, agent_plan, results):
    """Append an entry to history.json. agent_plan is a dict or error string. results is list/dict."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user_text,
        "agent_plan": agent_plan,
        "results": results
    }
    history = load_history(limit=1000)
    history.append(entry)
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print("Warning: failed to write history:", e)

# === LLM call (Gemini only) ===
def call_llm(prompt, max_output_tokens=1024, temperature=0.0):
    """
    Call Gemini (gemini-2.5-flash) via google.genai.
    Returns (status, text). Status starts with "OK" on success.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return ("ERROR:NO_KEY", "GEMINI_API_KEY not set. Please set it and try again.")
    try:
        from google import genai  # type: ignore
    except Exception as e:
        return ("ERROR:NO_CLIENT", "Could not import google.genai. Install google-generativeai. Import error:\n" + str(e))

    try:
        if hasattr(genai, "configure"):
            genai.configure(api_key=key)
        if hasattr(genai, "generate_text"):
            resp = genai.generate_text(model="gemini-2.5-flash", prompt=prompt, max_output_tokens=max_output_tokens, temperature=temperature)
            text = getattr(resp, "text", None) or getattr(resp, "output", None) or str(resp)
            return ("OK", text)
        elif hasattr(genai, "TextGeneration") and hasattr(genai.TextGeneration, "create"):
            resp = genai.TextGeneration.create(model="gemini-2.5-flash", prompt=prompt, max_output_tokens=max_output_tokens, temperature=temperature)
            if isinstance(resp, dict) and "candidates" in resp:
                text = resp["candidates"][0].get("content", "")
            else:
                text = str(resp)
            return ("OK", text)
        else:
            resp = genai.generate_text(model="gemini-2.5-flash", prompt=prompt, max_output_tokens=max_output_tokens)
            text = getattr(resp, "text", None) or str(resp)
            return ("OK", text)
    except Exception as e:
        return ("ERROR:CALL_FAILED", f"Gemini call failed: {e}\n{traceback.format_exc()}")

# === Build prompt: include system prompt, behavior, and recent history ===
def build_prompt_with_history(user_text, history_limit=8):
    """
    Read system_prompt.txt and behavior.md (both standalone files) and include the last
    `history_limit` history entries as a short log (user + agent plan).
    Return the full prompt string to send to Gemini.
    """
    # read system prompt
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            system_text = f.read()
    except Exception:
        system_text = "SYSTEM PROMPT MISSING"

    # read behavior file
    try:
        with open(BEHAVIOR_PATH, "r", encoding="utf-8") as f:
            behavior_text = f.read()
    except Exception:
        behavior_text = ""

    # load recent history
    history = load_history(limit=history_limit)
    # Build a small human-readable history summary
    history_lines = []
    for h in history:
        t = h.get("timestamp", "")
        u = h.get("user", "")
        # agent_plan may be dict: show short string
        plan = h.get("agent_plan", "")
        plan_snippet = ""
        if isinstance(plan, dict):
            # show tools used and explain
            steps = plan.get("steps", [])
            tool_list = [s.get("tool") for s in steps if isinstance(s, dict)]
            explain = plan.get("explain", "")
            plan_snippet = f"tools={tool_list}, explain={explain}"
        else:
            plan_snippet = str(plan)
        history_lines.append(f"[{t}] USER: {u}\n[{t}] AGENT_PLAN: {plan_snippet}")

    history_block = "\n\n".join(history_lines) if history_lines else "(no recent history)"

    # Compose final prompt: system + behavior + history + user instruction
    prompt = (
        system_text
        + "\n\nBEHAVIOR.md (short policy):\n"
        + behavior_text
        + "\n\nRECENT_HISTORY:\n"
        + history_block
        + "\n\nUSER_INSTRUCTION:\n\"\"\"\n"
        + user_text
        + "\n\"\"\"\n"
    )
    return prompt

# === Plan generation and parsing ===
def generate_plan(user_text, retries=1):
    """
    Generate a plan by calling Gemini with system + behavior + history + user instruction.
    Parse JSON strictly; on failure do one retry with a small re-prompt.
    Returns (ok, plan_or_error)
    """
    prompt = build_prompt_with_history(user_text, history_limit=8)
    status, reply = call_llm(prompt)
    if not status.startswith("OK"):
        return False, reply

    raw = reply.strip()
    # try parse as JSON
    try:
        plan = json.loads(raw)
    except Exception:
        # try to extract first {...} block
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start:end+1]
            try:
                plan = json.loads(candidate)
            except Exception:
                if retries > 0:
                    reprompt = ("Your previous response could not be parsed as JSON. "
                                "Please return ONLY a single valid JSON object matching the schema described earlier — nothing else.")
                    status2, reply2 = call_llm(reprompt)
                    if not status2.startswith("OK"):
                        return False, reply2
                    try:
                        plan = json.loads(reply2.strip())
                    except Exception:
                        return False, f"Failed to parse JSON after retry. Raw output:\n{reply2}"
                else:
                    return False, f"Failed to parse JSON. Raw output:\n{raw}"
        else:
            return False, "Model output did not contain JSON."

    valid, messages = validate_plan(plan)
    if not valid:
        return False, {"validation_errors": messages}
    return True, plan

def validate_plan(plan):
    """Simple validation for plan shape and step types."""
    if not isinstance(plan, dict):
        return False, ["Plan must be a JSON object (dict)."]
    if "steps" not in plan or not isinstance(plan["steps"], list):
        return False, ["Plan must contain 'steps' which is a list."]
    messages = []
    for i, step in enumerate(plan["steps"], start=1):
        if not isinstance(step, dict):
            messages.append(f"Step {i} must be an object.")
            continue
        tool = step.get("tool")
        if not tool or not isinstance(tool, str):
            messages.append(f"Step {i}: missing or invalid 'tool'.")
        args = step.get("args", [])
        if not isinstance(args, list):
            messages.append(f"Step {i}: 'args' must be a list.")
        kwargs = step.get("kwargs", {})
        if kwargs is not None and not isinstance(kwargs, dict):
            messages.append(f"Step {i}: 'kwargs' must be an object/dict.")
    return (len(messages) == 0), messages

# === Utility: detect destructive steps ===
def get_destructive_steps(plan):
    destructive = []
    for i, step in enumerate(plan.get("steps", []), start=1):
        if not isinstance(step, dict):
            continue
        tool = step.get("tool", "").lower()
        if tool in DESTRUCTIVE_TOOLS:
            destructive.append((i, step))
    return destructive

# === REPL helpers ===
def is_likely_natural_language(line):
    tokens = shlex.split(line) if line else []
    if not tokens:
        return False
    known_tools = {"read","ls","grep","glob","write","edit","multiedit","todowrite","webfetch","websearch","bash","exitplanmode"}
    first = tokens[0].lower()
    if first in ("help","exit","quit","todo"):
        return False
    return first not in known_tools

def parse_as_tool_invocation(line):
    s = line.strip()
    if not s:
        return None
    if s.startswith("{") or s.startswith("["):
        try:
            return json.loads(s)
        except Exception:
            return None
    parts = shlex.split(s)
    tool = parts[0]
    args = parts[1:]
    return {"tool": tool, "args": args, "kwargs": {}}

def print_intro():
    print("CLI Coding Agent (Gemini 2.5-flash). Workspace:", WORKSPACE_ROOT)
    print("Type 'help' for quick help. The agent logs recent interactions to history.json.")
    print("Non-destructive steps run immediately. Destructive steps require confirmation.")

# === Main REPL ===
def repl():
    print_intro()
    while True:
        try:
            line = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not line:
            continue
        if line.lower() in ("help","--help","-h"):
            output.print_help_box()
            continue
        if line.lower() in ("exit","quit"):
            print("Bye.")
            break

        # todo shortcut
        if line.startswith("todo "):
            parsed = parse_as_tool_invocation("todowrite " + line[len("todo "):])
            res = dispatch_tool(parsed)
            output.print_result(parsed.get("tool"), res)
            # append history for todo actions (agent_plan = parsed)
            append_history(line, parsed, [res])
            continue

        # If looks like a direct tool invocation, run it
        if not is_likely_natural_language(line):
            parsed = parse_as_tool_invocation(line)
            if parsed is None:
                output.print_error("Could not parse that as a tool invocation.")
                continue
            results = dispatch_tool(parsed)
            output.print_result(parsed.get("tool"), results)
            append_history(line, parsed, [results])
            continue

        # Natural language: get plan from LLM
        user_text = line
        output.print_user_box(user_text)
        ok, plan_or_err = generate_plan(user_text, retries=1)
        if not ok:
            output.print_error(f"LLM plan generation failed: {plan_or_err}")
            # append history noting failure
            append_history(user_text, {"error": str(plan_or_err)}, [])
            continue
        plan = plan_or_err  # dict

        # see if plan has destructive steps
        destructive = get_destructive_steps(plan)
        run_full_plan = True
        if destructive:
            # Ask user in plain English whether to run the destructive steps
            output.print_boxed("Plan Summary (before execution)", plan.get("explain", "(no explain)"))
            print("This plan includes destructive steps that will modify files or run shell commands.")
            print("Destructive steps:")
            for idx, step in destructive:
                print(f"  {idx}. {step.get('tool')} args={step.get('args')}")
            # ask for yes/no
            confirm = input("Run the entire plan including destructive steps? (y/n) ").strip().lower()
            if confirm not in ("y", "yes"):
                run_full_plan = False

        # Execute steps based on confirmation
        steps_to_run = plan.get("steps", [])
        if not run_full_plan and destructive:
            # filter out destructive steps
            steps_to_run = [s for s in steps_to_run if not (isinstance(s, dict) and s.get("tool","").lower() in DESTRUCTIVE_TOOLS)]
            if not steps_to_run:
                print("No non-destructive steps to run. Skipping execution.")
                append_history(user_text, plan, [])
                continue
            print("Running non-destructive steps only (destructive steps skipped).")

        # dispatch steps; whether a single step dict or a plan dict, dispatch_tool can accept plan dicts
        # we'll normalize and call dispatch_tool with a plan dict for consistent behavior
        to_dispatch = {"steps": steps_to_run}
        results = dispatch_tool(to_dispatch)
        # results is a list of result dicts
        if isinstance(results, list):
            for r in results:
                tool_name = r.get("tool", "<unknown>")
                output.print_agent_tool_use(tool_name)
                output.print_result(tool_name, r)
        else:
            tool_name = results.get("tool", "<unknown>")
            output.print_agent_tool_use(tool_name)
            output.print_result(tool_name, results)
        # append to history: store plan (dict) and results (list)
        append_history(user_text, plan, results if isinstance(results, list) else [results])

if __name__ == "__main__":
    repl()
