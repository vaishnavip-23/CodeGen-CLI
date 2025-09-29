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
from pathlib import Path

# Load environment variables
def _try_parse_env_file(path: Path) -> Dict[str, str]:
    """Parse simple .env files supporting lines like KEY=VALUE or export KEY=VALUE.

    Returns a mapping of keys to values. Ignores comments and blank lines.
    """
    env: Dict[str, str] = {}
    try:
        if not path.exists() or not path.is_file():
            return env
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    env[key] = value
    except Exception:
        # Best-effort only
        return {}
    return env

def _load_additional_env():
    """Load environment variables from project and user locations if not already set.

    Load order (first non-empty wins for GEMINI_API_KEY):
      1) Existing process environment
      2) Project .env (cwd/.env)
      3) User .env (~/\.env)
      4) User config .env (~/.config/codegen/.env)
    """
    # Try python-dotenv if present (loads cwd/.env by default)
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

    # If key still missing, try additional files
    if not os.environ.get("GEMINI_API_KEY"):
        cwd_env = _try_parse_env_file(Path.cwd() / ".env")
        if cwd_env.get("GEMINI_API_KEY"):
            os.environ.setdefault("GEMINI_API_KEY", cwd_env["GEMINI_API_KEY"])

    if not os.environ.get("GEMINI_API_KEY"):
        home = Path.home()
        home_env = _try_parse_env_file(home / ".env")
        if home_env.get("GEMINI_API_KEY"):
            os.environ.setdefault("GEMINI_API_KEY", home_env["GEMINI_API_KEY"])

    if not os.environ.get("GEMINI_API_KEY"):
        cfg_env = _try_parse_env_file(Path.home() / ".config" / "codegen" / ".env")
        if cfg_env.get("GEMINI_API_KEY"):
            os.environ.setdefault("GEMINI_API_KEY", cfg_env["GEMINI_API_KEY"])

# Initialize Gemini API client
_load_additional_env()
try:
    from google import genai
except ImportError:
    genai = None

API_KEY = os.environ.get("GEMINI_API_KEY")
CLIENT = None

def _ensure_client():
    """Ensure a genai client exists if possible. Refreshes API_KEY from env."""
    global CLIENT, API_KEY
    if CLIENT is not None:
        return CLIENT
    _load_additional_env()
    API_KEY = os.environ.get("GEMINI_API_KEY")
    if genai and API_KEY:
        try:
            CLIENT = genai.Client(api_key=API_KEY)
        except Exception:
            CLIENT = None
    return CLIENT

# File paths
WORKSPACE_ROOT = os.getcwd()
# Get the directory where this file is located (codegen_cli package)
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(PACKAGE_DIR, "config", "system_prompt.txt")
BEHAVIOR_PATH = os.path.join(PACKAGE_DIR, "config", "behavior.md")

# History storage: write to user config dir by default (project-local disabled)
def _resolve_history_path() -> str:
    env_override = os.environ.get("CODEGEN_HISTORY_PATH")
    if env_override:
        return env_override
    user_cfg = os.path.join(Path.home(), ".config", "codegen")
    try:
        os.makedirs(user_cfg, exist_ok=True)
    except Exception:
        pass
    return os.path.join(user_cfg, "history.json")

HISTORY_PATH = _resolve_history_path()

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
from . import faq as faq_handlers
from .repl import run_repl

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
        # Ensure parent exists
        parent = os.path.dirname(HISTORY_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
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
    client = _ensure_client()
    if client is None:
        if genai is None:
            return ("ERROR:NO_CLIENT", "google.genai not available. Install google-genai.")
        if not os.environ.get("GEMINI_API_KEY"):
            return ("ERROR:NO_KEY", "GEMINI_API_KEY not set. Run 'codegen --set-key' in your terminal or add it to .env.")
        return ("ERROR:CLIENT_INIT", "Failed to initialize Gemini client. Check your API key.")

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
        msg = str(e)
        # Friendly handling for common free-tier/rate-limit errors
        rate_markers = [
            "rate limit", "429", "quota", "Resource has been exhausted", "Too Many Requests"
        ]
        if any(m.lower() in msg.lower() for m in rate_markers):
            return ("ERROR:RATE_LIMIT", "You've hit the free-tier rate limit. Please wait a minute and try again, or set a paid quota in Google AI Studio.")
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

    # API key status questions
    api_markers = ("api key", "apikey", "gemini key", "gemini api", "gemini")
    status_markers = ("set", "configured", "present", "available", "loaded", "right", "proper")
    if any(m in s for m in api_markers) and ("set" in s or "configured" in s or "present" in s or "loaded" in s or "right" in s or "proper" in s or "ok" in s):
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        if has_key:
            print("Assistant: Yes — GEMINI_API_KEY is set and will be used. 'codegen --set-key' is a one-time user-level setup and can be run from any directory.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_yes"}, [])
        else:
            print("Assistant: No — GEMINI_API_KEY is not set. Run 'codegen --set-key' in your terminal or add it to your .env.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_no"}, [])
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
# Plan Post-Processing Filters
# ---------------------------
def filter_invalid_read_steps(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Remove read steps that target non-existent files.

    This prevents attempts to read files that aren't present (e.g., README.md when missing).
    """
    try:
        steps = plan.get("steps", [])
        filtered = []
        for s in steps:
            if not isinstance(s, dict):
                filtered.append(s)
                continue
            tool = s.get("tool", "").lower()
            args = s.get("args", []) or []
            if tool == "read" and args:
                target = args[0]
                if isinstance(target, str) and not os.path.exists(target):
                    # skip this read step
                    continue
            filtered.append(s)
        plan["steps"] = filtered
        return plan
    except Exception:
        return plan

# ---------------------------
# Main REPL
# ---------------------------
def repl():
    deps = {
        "workspace_root": WORKSPACE_ROOT,
        "project_info": PROJECT_INFO,
        "dispatch_tool": dispatch_tool,
        "output": output,
        "faq_handlers": faq_handlers,
        "append_history": append_history,
        "list_repo_files_recursive": list_repo_files_recursive,
        "maybe_convert_write_to_edit": maybe_convert_write_to_edit,
        "generate_plan": generate_plan,
        "destructive_tools": DESTRUCTIVE_TOOLS,
        "ensure_client": _ensure_client,
    }
    run_repl(deps)

def main():
    """Main entry point with command line argument support."""
    import sys
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--version", "-v", "version"):
            try:
                import importlib.metadata as _m
                ver = _m.version("codegen-cli")
            except Exception:
                ver = "unknown"
            print(f"CodeGen CLI v{ver}")
            print("Universal CLI coding agent that understands any codebase")
            return
        elif arg in ("--help", "-h", "help"):
            print("CodeGen CLI - Universal Coding Agent")
            print("")
            print("Usage:")
            print("  codegen                    # Start interactive CLI")
            print("  codegen --help            # Show this help")
            print("  codegen --version         # Show version")
            print("  codegen --set-key [KEY]   # Save GEMINI_API_KEY to user config")
            print("")
            print("Setup Required:")
            print("  • Run 'codegen --set-key' and paste your Gemini API key")
            print("  • Or set GEMINI_API_KEY via shell export or .env files")
            print("  • Get API key from: https://aistudio.google.com/api-keys")
            print("")
            print("Features:")
            print("  • Universal compatibility with any codebase")
            print("  • Natural language interface")
            print("  • Smart project detection")
            print("  • Safety-first approach")
            return
        elif arg in ("--set-key", "set-key"):
            # Accept key from argv or prompt interactively
            key = None
            if len(sys.argv) >= 3 and sys.argv[2]:
                key = sys.argv[2]
            if not key:
                try:
                    key = input("Enter your Gemini API key: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("Aborted.")
                    return
            if not key:
                print("No key provided.")
                return
            cfg_dir = Path.home() / ".config" / "codegen"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / ".env"
            try:
                with cfg_file.open("w", encoding="utf-8") as f:
                    f.write(f"GEMINI_API_KEY={key}\n")
                print(f"Saved API key to {cfg_file}")
                # Update current process env and client
                os.environ["GEMINI_API_KEY"] = key
                global API_KEY
                API_KEY = key
                _ensure_client()
                print("You're all set! Run 'codegen' in any project.")
            except Exception as e:
                print(f"Failed to save API key: {e}")
            return
        else:
            print(f"Unknown option: {arg}")
            print("Use 'codegen --help' for usage information")
            return
    
    # Start the REPL
    repl()

if __name__ == "__main__":
    main()