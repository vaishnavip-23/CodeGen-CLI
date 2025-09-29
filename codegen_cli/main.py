#!/usr/bin/env python3
"""
CodeGen2 - CLI Coding Agent

A command-line assistant that understands natural language and can interact with your codebase.
Uses Google Gemini API for plan generation and executes actions through modular tools.
"""

import os
import json
import traceback
from datetime import datetime
from typing import Tuple, Any, Dict, List

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Initialize Gemini API client
try:
    from google import genai
except ImportError:
    genai = None

API_KEY = os.environ.get("GEMINI_API_KEY")
CLIENT = None
if genai and API_KEY:
    try:
        CLIENT = genai.Client(api_key=API_KEY)
    except Exception:
        CLIENT = None

# File paths
WORKSPACE_ROOT = os.getcwd()
# Get the directory where this file is located (codegen_cli package)
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(PACKAGE_DIR, "config", "system_prompt.txt")
BEHAVIOR_PATH = os.path.join(PACKAGE_DIR, "config", "behavior.md")
HISTORY_PATH = os.path.join(WORKSPACE_ROOT, "history.json")

# Project type detection
def detect_project_type(workspace_path: str) -> dict:
    """Detect the type of project in the workspace."""
    project_info = {
        "language": "unknown",
        "framework": None,
        "package_manager": None,
        "file_extensions": set()
    }
    
    # Language detection patterns
    language_patterns = {
        'python': {
            'files': ['requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile'],
            'extensions': ['.py', '.pyi'],
            'dirs': ['__pycache__', '.venv', 'venv']
        },
        'javascript': {
            'files': ['package.json', 'yarn.lock', 'package-lock.json'],
            'extensions': ['.js', '.jsx', '.ts', '.tsx', '.mjs'],
            'dirs': ['node_modules', '.next', '.nuxt']
        },
        'go': {
            'files': ['go.mod', 'go.sum'],
            'extensions': ['.go'],
            'dirs': ['vendor']
        },
        'rust': {
            'files': ['Cargo.toml', 'Cargo.lock'],
            'extensions': ['.rs'],
            'dirs': ['target']
        }
    }
    
    # Detect language
    for language, patterns in language_patterns.items():
        for file_pattern in patterns['files']:
            if os.path.exists(os.path.join(workspace_path, file_pattern)):
                project_info['language'] = language
                project_info['file_extensions'] = set(patterns['extensions'])
                break
        if project_info['language'] != 'unknown':
            break
    
    # Detect package manager
    if project_info['language'] == 'python':
        if os.path.exists(os.path.join(workspace_path, 'requirements.txt')):
            project_info['package_manager'] = 'pip'
        elif os.path.exists(os.path.join(workspace_path, 'pyproject.toml')):
            project_info['package_manager'] = 'poetry'
        elif os.path.exists(os.path.join(workspace_path, 'Pipfile')):
            project_info['package_manager'] = 'pipenv'
    elif project_info['language'] == 'javascript':
        if os.path.exists(os.path.join(workspace_path, 'package.json')):
            project_info['package_manager'] = 'npm'
        if os.path.exists(os.path.join(workspace_path, 'yarn.lock')):
            project_info['package_manager'] = 'yarn'
    
    return project_info

# Detect current project
PROJECT_INFO = detect_project_type(WORKSPACE_ROOT)

# Import local modules
from .call_tools import dispatch_tool
from . import output

# Tools that can modify files
DESTRUCTIVE_TOOLS = {"write", "edit", "multiedit", "bash", "delete", "Write", "Edit", "MultiEdit", "Bash", "Delete"}

# ---------------------------
# History Management
# ---------------------------
def load_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Load recent history from JSON file."""
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
    """Save interaction to history file."""
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

# ---------------------------
# LLM Integration
# ---------------------------
def _load_system_behavior_and_history(history_limit: int = 8):
    """Load system prompt, behavior guidelines, and recent history."""
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

def call_llm_structured(user_text: str, max_output_tokens: int = 1024, temperature: float = 0.0) -> Tuple[str, str]:
    """Call Gemini API to generate a structured plan."""
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
            contents=prompt,
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

# ---------------------------
# Plan Validation
# ---------------------------
def validate_plan(plan: Any):
    """Validate that plan has correct structure."""
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
    """Generate and validate a plan from user input."""
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
        reprompt = ('You returned an empty plan. If the user\'s instruction was actionable, produce a JSON plan with steps. Otherwise return {"steps": [], "explain": "No specific action requested."}. Return ONLY JSON.')
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

# ---------------------------
# Small Talk Handlers
# ---------------------------
def handle_small_talk(user_text: str) -> bool:
    """Handle common greetings and questions without using tools."""
    s = user_text.strip().lower()
    
    # Handle various greeting patterns
    greetings = {"hi", "hii", "hiii", "hiiii", "hello", "hey", "heyy", "heyyy", "hiya", "yo", "yo!", "hey!", "hi!"}
    if s in greetings:
        print("Assistant: Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True
    
    # Handle greetings with punctuation or extra characters
    if s.startswith(("hi", "hey", "hello")) and len(s) <= 10:
        print("Assistant: Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True
    
    # Handle casual responses
    if s in {"sup", "what's up", "whats up", "wassup", "howdy", "greetings"}:
        print("Assistant: Hey there! Ready to work on some code? What can I help you with?")
        append_history(user_text, {"steps": [], "explain": "casual_greeting"}, [])
        return True
    
    # Handle thanks and appreciation
    if s in {"thanks", "thank you", "thx", "ty", "appreciate it", "thanks!"}:
        print("Assistant: You're welcome! Happy to help. Anything else you'd like to work on?")
        append_history(user_text, {"steps": [], "explain": "thanks"}, [])
        return True

    if "what can you do" in s or "what do you do" in s or "capabilities" in s:
        reply = """# CodeGen2 - CLI Coding Agent Capabilities

## Core Functionality
I am a repository-aware CLI coding assistant that can interact with your codebase through natural language commands.

## File Operations
- **Read**: Examine file contents with optional line limits
- **Write**: Create new files or overwrite existing ones (with confirmation)
- **Edit**: Modify existing files by replacing text
- **MultiEdit**: Perform multiple file edits in sequence

## Search & Discovery
- **List Files**: Browse directories with filtering options
- **Search Text**: Find patterns across files using grep
- **Pattern Matching**: Locate files using glob patterns

## Web Integration
- **Web Search**: Search the internet using DuckDuckGo
- **Web Fetch**: Download and extract content from URLs

## System Operations
- **Bash Commands**: Execute shell commands safely (with restrictions)
- **Task Management**: Create and manage todo lists
- **Codebase Analysis**: Generate comprehensive project summaries

## Safety Features
- **Path Protection**: Prevents access outside workspace
- **Confirmation Required**: Asks permission for destructive changes
- **Command Security**: Blocks dangerous shell commands

I can help you with code analysis, file management, project organization, and much more!"""
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

# ---------------------------
# Tool Invocation Parser
# ---------------------------
def _simple_split_first_word(line: str) -> str:
    """Get first word from line (for tool detection)."""
    if not line:
        return ""
    return line.strip().split()[0].lower()

def is_likely_natural_language(line: str) -> bool:
    """Check if input looks like natural language vs tool command."""
    first = _simple_split_first_word(line)
    known_tools = {"read", "ls", "glob", "grep", "write", "edit", "multiedit", "todowrite", "webfetch", "websearch", "bash", "task", "delete", "todo"}
    if first in ("help", "exit", "quit"):
        return False
    return first not in known_tools





def parse_as_tool_invocation(line: str):
    """Parse tool command into structured format."""
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
    # Special case: "list files" -> ls command
    if tool.lower() in ("list",) and len(args) >= 1 and args[0].lower().startswith("file"):
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    if tool.lower() == "ls" and not args:
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    return {"tool": tool, "args": args, "kwargs": kwargs}

# ---------------------------
# File Listing
# ---------------------------
def list_repo_files_recursive(root: str = ".", ignore_dirs: List[str] = None) -> List[str]:
    """Get all files in repository, ignoring common build/cache directories."""
    if ignore_dirs is None:
        # Language-specific ignore directories
        base_ignore = {".git", ".env", ".cache"}
        language_ignore = {
            'python': {"__pycache__", ".venv", "venv", ".pytest_cache", "build", "dist"},
            'javascript': {"node_modules", ".next", ".nuxt", "dist", "build"},
            'go': {"vendor", "bin"},
            'rust': {"target", "Cargo.lock"},
            'java': {"target", "build", ".gradle"},
            'csharp': {"bin", "obj", "packages"}
        }
        
        ignore_dirs = base_ignore.copy()
        if PROJECT_INFO['language'] in language_ignore:
            ignore_dirs.update(language_ignore[PROJECT_INFO['language']])
    else:
        ignore_dirs = set(ignore_dirs)
    root_path = os.path.abspath(root)
    files_out = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Remove ignored directories from traversal
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".") or d in (".",)]
        # Skip if path contains ignored components
        rel_dir = os.path.relpath(dirpath, root_path)
        if rel_dir == ".":
            rel_dir = ""
        # Add files
        for fn in filenames:
            if fn in (".env",):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_path)
            files_out.append(rel)
    files_out.sort()
    return files_out

def print_recursive_listing():
    """Print all repository files."""
    files = list_repo_files_recursive(".")
    try:
        output.print_boxed("Repository files (recursive)", "\n".join(files[:5000]))
    except Exception:
        print("--- Repository files (recursive) ---")
        for p in files:
            print(p)

# ---------------------------
# Write to Edit Conversion
# ---------------------------
def maybe_convert_write_to_edit(plan: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    """Convert Write commands to Edit when user wants to change existing files."""
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

# ---------------------------
# Main REPL
# ---------------------------
def print_intro():
    """Print welcome message with project information."""
    print("🚀 CodeGen CLI - Universal Coding Agent")
    print("=" * 50)
    print(f"Workspace: {WORKSPACE_ROOT}")
    print(f"Language: {PROJECT_INFO['language']}")
    if PROJECT_INFO['package_manager']:
        print(f"Package Manager: {PROJECT_INFO['package_manager']}")
    print("Type 'help' for help. Non-destructive steps run immediately. Destructive steps require confirmation.")
    print("=" * 50)

def repl():
    """Main read-eval-print loop."""
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

        # Handle special commands
        low = line.strip().lower()
        if low in ("help", "--help", "-h"):
            try:
                output.print_help(PROJECT_INFO)
            except Exception:
                print("Help: try natural language or tool invocations like 'read README.md' or 'list files'.")
            continue
        if low in ("exit", "quit"):
            print("Bye.")
            break

        # Handle "list files" command
        if low in ("list files", "list all files", "ls -r", "ls -R"):
            print_recursive_listing()
            append_history(line, {"steps": [], "explain": "list_files_recursive"}, [])
            continue


        # Handle "todo" shortcut
        if low.startswith("todo "):
            parsed = parse_as_tool_invocation("todowrite " + line[len("todo "):])
            res = dispatch_tool(parsed)
            output.print_tool_result(parsed.get("tool"), res)
            append_history(line, parsed, [res])
            continue

        # Handle direct tool invocations
        if not is_likely_natural_language(line):
            parsed = parse_as_tool_invocation(line)
            if parsed is None:
                output.print_error("Could not parse tool invocation.")
                continue

            # Handle ls command
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

        # Handle natural language
        user_text = line
        output.print_user_input(user_text)

        # Handle small talk
        if handle_small_talk(user_text):
            continue

        # Generate plan
        ok, plan_or_err = generate_plan(user_text, retries=1)
        if not ok:
            output.print_error(f"LLM plan generation failed: {plan_or_err}")
            append_history(user_text, {"error": str(plan_or_err)}, [])
            continue
        plan = plan_or_err

        # Handle empty plans
        if isinstance(plan, dict) and isinstance(plan.get("steps"), list) and len(plan.get("steps")) == 0:
            explain = plan.get("explain", "").strip()
            if explain:
                print("Assistant:", explain)
                append_history(user_text, plan, [])
                continue

        # Check for destructive steps
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

        # Convert Write to Edit if needed
        plan_for_dispatch = {"steps": steps_to_run, "explain": plan.get("explain", "")}
        plan_for_dispatch = maybe_convert_write_to_edit(plan_for_dispatch, user_text)

        # Execute plan
        to_dispatch = {"steps": plan_for_dispatch.get("steps", [])}
        results = dispatch_tool(to_dispatch)

        # Print results
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

def main():
    """Main entry point with command line argument support."""
    import sys
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--version", "-v", "version"):
            print("CodeGen CLI v0.1.0")
            print("Universal CLI coding agent that understands any codebase")
            return
        elif arg in ("--help", "-h", "help"):
            print("CodeGen CLI - Universal Coding Agent")
            print("")
            print("Usage:")
            print("  codegen                    # Start interactive CLI")
            print("  codegen --help            # Show this help")
            print("  codegen --version         # Show version")
            print("")
            print("Setup Required:")
            print("  • Set GEMINI_API_KEY: export GEMINI_API_KEY=\"your-api-key\"")
            print("  • Get API key from: https://aistudio.google.com/api-keys")
            print("")
            print("Features:")
            print("  • Universal compatibility with any codebase")
            print("  • Natural language interface")
            print("  • Smart project detection")
            print("  • Safety-first approach")
            return
        else:
            print(f"Unknown option: {arg}")
            print("Use 'codegen --help' for usage information")
            return
    
    # Start the REPL
    repl()

if __name__ == "__main__":
    main()