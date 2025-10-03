#!/usr/bin/env python3
# File Summary: Primary application bootstrap handling environment setup and REPL startup.

"""
CodeGen-CLI - Universal Coding Agent

A command-line assistant that understands natural language and can interact with your codebase.
Uses Google Gemini API for plan generation and executes actions through modular tools.
"""

import os
import json
import traceback
from datetime import datetime
from typing import Tuple, Any, Dict, List
from pathlib import Path
import sys

                            
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
                                                              
    try:
        from dotenv import load_dotenv                
        load_dotenv()
    except Exception:
        pass

                                                
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

                             
                        
                             
def _get_installed_version() -> str:
    try:
        import importlib.metadata as _m
        return _m.version("codegen-cli")
    except Exception:
        return "unknown"

def _get_pypi_latest_version(package_name: str = "codegen-cli") -> str:
    """Fetch latest version string from PyPI JSON API."""
    try:
        import requests                
        url = f"https://pypi.org/pypi/{package_name}/json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("info", {}).get("version", "unknown"))
    except Exception:
        return "unknown"

def _compare_versions(v1: str, v2: str) -> int:
    """Return -1 if v1<v2, 0 if equal, 1 if v1>v2 using loose semantic compare."""
    def _split(v: str):
        import re
        return [int(x) if x.isdigit() else x for x in re.split(r"[\.-]", v)]
    try:
        a, b = _split(v1), _split(v2)
        for i in range(max(len(a), len(b))):
            ai = a[i] if i < len(a) else 0
            bi = b[i] if i < len(b) else 0
            if isinstance(ai, int) and isinstance(bi, int):
                if ai < bi:
                    return -1
                if ai > bi:
                    return 1
            else:
                ai_s, bi_s = str(ai), str(bi)
                if ai_s < bi_s:
                    return -1
                if ai_s > bi_s:
                    return 1
        return 0
    except Exception:
        return 0

def _check_update():
    """Print update status comparing installed vs PyPI latest."""
    installed = _get_installed_version()
    latest = _get_pypi_latest_version("codegen-cli")
    color = output.Color

    lines = [
        f"{color.MUTED}Installed:{color.RESET} {installed}",
        f"{color.MUTED}Latest on PyPI:{color.RESET} {latest}",
    ]

    style = "info"

    if installed == "unknown" or latest == "unknown":
        lines.append("Could not determine versions. Ensure internet connectivity and that the package is installed.")
    else:
        cmp = _compare_versions(installed, latest)
        if cmp < 0:
            style = "warning"
            lines.append(f"{color.CODE}A newer version is available.{color.RESET}")
            lines.append("Upgrade with:")
            lines.append("  • pip install -U codegen-cli")
            lines.append("  • pipx upgrade codegen-cli")
        elif cmp == 0:
            style = "success"
            lines.append(f"{color.SUCCESS}You are up to date.{color.RESET}")
        else:
            lines.append("You are ahead of the latest PyPI release (pre-release or local build).")

    output.print_boxed("Version Check", "\n".join(lines), style=style)

            
WORKSPACE_ROOT = os.getcwd()
                                                                    
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(PACKAGE_DIR, "config", "system_prompt.txt")
BEHAVIOR_PATH = os.path.join(PACKAGE_DIR, "config", "behavior.md")

                                                                               
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

                        
def detect_project_type(workspace_path: str) -> dict:
    """Detect the type of project in the workspace."""
    project_info = {
        "language": "unknown",
        "framework": None,
        "package_manager": None,
        "file_extensions": set()
    }
    
                                 
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
    
                     
    for language, patterns in language_patterns.items():
        for file_pattern in patterns['files']:
            if os.path.exists(os.path.join(workspace_path, file_pattern)):
                project_info['language'] = language
                project_info['file_extensions'] = set(patterns['extensions'])
                break
        if project_info['language'] != 'unknown':
            break
    
                            
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

                        
PROJECT_INFO = detect_project_type(WORKSPACE_ROOT)

                      
from .call_tools import dispatch_tool
from . import output
from . import faq as faq_handlers
from .repl import run_repl

                             
DESTRUCTIVE_TOOLS = {"write", "edit", "multiedit", "bash", "delete", "Write", "Edit", "MultiEdit", "Bash", "Delete"}

                             
                    
                             
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
                              
        parent = os.path.dirname(HISTORY_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=2)
    except Exception:
        pass

                             
                 
                             
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

                             
                     
                             
def handle_small_talk(user_text: str) -> bool:
    """Handle common greetings and questions without using tools."""
    s = user_text.strip().lower()
    
                                      
    greetings = {"hi", "hii", "hiii", "hiiii", "hello", "hey", "heyy", "heyyy", "hiya", "yo", "yo!", "hey!", "hi!"}
    if s in greetings:
        output.print_assistant("Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True
    
                                                           
    if s.startswith(("hi", "hey", "hello")) and len(s) <= 10:
        output.print_assistant("Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True
    
                             
    if s in {"sup", "what's up", "whats up", "wassup", "howdy", "greetings"}:
        output.print_assistant("Hey there! Ready to work on some code? What can I help you with?")
        append_history(user_text, {"steps": [], "explain": "casual_greeting"}, [])
        return True
    
                                    
    if s in {"thanks", "thank you", "thx", "ty", "appreciate it", "thanks!"}:
        output.print_assistant("You're welcome! Happy to help. Anything else you'd like to work on?")
        append_history(user_text, {"steps": [], "explain": "thanks"}, [])
        return True

                              
    api_markers = ("api key", "apikey", "gemini key", "gemini api", "gemini")
    status_markers = ("set", "configured", "present", "available", "loaded", "right", "proper")
    if any(m in s for m in api_markers) and ("set" in s or "configured" in s or "present" in s or "loaded" in s or "right" in s or "proper" in s or "ok" in s):
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        if has_key:
            output.print_assistant("Yes — GEMINI_API_KEY is set and will be used. 'codegen --set-key' is a one-time user-level setup and can be run from any directory.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_yes"}, [])
        else:
            output.print_assistant("No — GEMINI_API_KEY is not set. Run 'codegen --set-key' in your terminal or add it to your .env.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_no"}, [])
        return True

    if "what can you do" in s or "what do you do" in s or "capabilities" in s:
        reply = """# CodeGen-CLI - Universal Coding Agent Capabilities

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
        output.print_assistant(reply)
        append_history(user_text, {"steps": [], "explain": "capabilities_reply"}, [])
        return True

    if "your name" in s or "who are you" in s:
        output.print_assistant("I am a local CLI coding assistant (Agent). I work on this repo's files.")
        append_history(user_text, {"steps": [], "explain": "name_reply"}, [])
        return True

    short_small = {"thanks", "thank you", "bye", "goodbye"}
    for marker in short_small:
        if marker in s:
            output.print_assistant("You're welcome.")
            append_history(user_text, {"steps": [], "explain": "small_talk_reply"}, [])
            return True

    return False

                             
                        
                             
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
                                              
    if tool.lower() in ("list",) and len(args) >= 1 and args[0].lower().startswith("file"):
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    if tool.lower() == "ls" and not args:
        return {"tool": "ls", "args": [".", {"depth": None}], "kwargs": {}}
    return {"tool": tool, "args": args, "kwargs": kwargs}

                             
              
                             
def list_repo_files_recursive(root: str = ".", ignore_dirs: List[str] = None) -> List[str]:
    """Get all files in repository, ignoring common build/cache directories."""
    if ignore_dirs is None:
                                              
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
                                                   
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".") or d in (".",)]
                                                  
        rel_dir = os.path.relpath(dirpath, root_path)
        if rel_dir == ".":
            rel_dir = ""
                   
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
    output.print_boxed("Repository files (recursive)", "\n".join(files[:5000]))

                             
           
                             
def repl():
    deps = {
        "workspace_root": WORKSPACE_ROOT,
        "project_info": PROJECT_INFO,
        "dispatch_tool": dispatch_tool,
        "output": output,
        "faq_handlers": faq_handlers,
        "append_history": append_history,
        "list_repo_files_recursive": list_repo_files_recursive,
        "generate_plan": generate_plan,
        "destructive_tools": DESTRUCTIVE_TOOLS,
        "ensure_client": _ensure_client,
    }
    run_repl(deps)

def main():
    """Main entry point with command line argument support."""
    import sys
    
                                   
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--version", "-v", "version"):
            try:
                import importlib.metadata as _m
                ver = _m.version("codegen-cli")
            except Exception:
                ver = "unknown"
            body = "\n".join([
                f"{output.Color.ACCENT}{output.Color.BOLD}CodeGen-CLI v{ver}{output.Color.RESET}",
                "Universal CLI coding agent that understands any codebase",
            ])
            output.print_boxed("Version", body, style="info")
            return
        elif arg in ("--check-update", "check-update", "update", "--update"):
            _check_update()
            return
        elif arg in ("--help", "-h", "help"):
            try:
                output.print_help(PROJECT_INFO)
            except Exception:
                output.print_info("CodeGen-CLI - Universal Coding Agent", title="Help")
            return
        elif arg in ("--set-key", "set-key"):
                                                          
            key = None
            if len(sys.argv) >= 3 and sys.argv[2]:
                key = sys.argv[2]
            if not key:
                try:
                    key = input("Enter your Gemini API key: ").strip()
                except (EOFError, KeyboardInterrupt):
                    output.print_warning("Aborted.", title="Setup")
                    return
            if not key:
                output.print_warning("No key provided.", title="Setup")
                return
            cfg_dir = Path.home() / ".config" / "codegen"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / ".env"
            try:
                with cfg_file.open("w", encoding="utf-8") as f:
                    f.write(f"GEMINI_API_KEY={key}\n")
                output.print_success(f"Saved API key to {cfg_file}", title="Setup")
                                                       
                os.environ["GEMINI_API_KEY"] = key
                global API_KEY
                API_KEY = key
                _ensure_client()
                output.print_success("You're all set! Run 'codegen' in any project.", title="Setup")
            except Exception as e:
                output.print_error(f"Failed to save API key: {e}")
            return
        else:
            output.print_warning(f"Unknown option: {arg}", title="CLI")
            output.print_info("Use 'codegen --help' for usage information", title="CLI")
            return
    
                    
    repl()

if __name__ == "__main__":
    main()
