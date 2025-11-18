
# File Summary: Primary application bootstrap handling environment setup and REPL startup.


"""
CodeGen-CLI - Universal Coding Agent

A command-line assistant that understands natural language and can interact with your codebase.
Uses Google Gemini API for plan generation and executes actions through modular tools.
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path

from . import output

                            
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
SYSTEM_PROMPT_PATH = os.path.join(PACKAGE_DIR, "config", "system_prompt.md")
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
            'extensions': ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'],
            'dirs': ['node_modules', '.next', '.nuxt', 'dist', 'build']
        },
        'typescript': {
            'files': ['tsconfig.json', 'package.json'],
            'extensions': ['.ts', '.tsx'],
            'dirs': ['node_modules', 'dist']
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
        },
        'java': {
            'files': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
            'extensions': ['.java'],
            'dirs': ['target', 'build']
        }
    }
    
    # Helper to check if file exists in workspace or immediate subdirectories
    def find_file(filename):
        # Check root
        if os.path.exists(os.path.join(workspace_path, filename)):
            return True
        # Check immediate subdirectories (one level deep)
        try:
            for item in os.listdir(workspace_path):
                subdir = os.path.join(workspace_path, item)
                if os.path.isdir(subdir) and not item.startswith('.'):
                    if os.path.exists(os.path.join(subdir, filename)):
                        return True
        except (PermissionError, OSError):
            pass
        return False
    
    # Check for language-specific files
    for language, patterns in language_patterns.items():
        for file_pattern in patterns['files']:
            if find_file(file_pattern):
                project_info['language'] = language
                project_info['file_extensions'] = set(patterns['extensions'])
                break
        if project_info['language'] != 'unknown':
            break
    
    # Detect framework if JavaScript/TypeScript
    if project_info['language'] in ['javascript', 'typescript']:
        package_json_path = os.path.join(workspace_path, 'package.json')
        if not os.path.exists(package_json_path):
            # Check subdirectories
            try:
                for item in os.listdir(workspace_path):
                    subdir = os.path.join(workspace_path, item)
                    if os.path.isdir(subdir) and not item.startswith('.'):
                        sub_package = os.path.join(subdir, 'package.json')
                        if os.path.exists(sub_package):
                            package_json_path = sub_package
                            break
            except (PermissionError, OSError):
                pass
        
        # Read package.json to detect framework
        try:
            import json
            with open(package_json_path, 'r', encoding='utf-8') as f:
                pkg_data = json.load(f)
                deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                
                if 'react' in deps:
                    project_info['framework'] = 'react'
                elif 'vue' in deps:
                    project_info['framework'] = 'vue'
                elif 'next' in deps:
                    project_info['framework'] = 'next.js'
                elif '@angular/core' in deps:
                    project_info['framework'] = 'angular'
                elif 'svelte' in deps:
                    project_info['framework'] = 'svelte'
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass
    
    # Detect package manager
    if project_info['language'] == 'python':
        if find_file('requirements.txt'):
            project_info['package_manager'] = 'pip'
        elif find_file('pyproject.toml'):
            project_info['package_manager'] = 'poetry'
        elif find_file('Pipfile'):
            project_info['package_manager'] = 'pipenv'
    elif project_info['language'] in ['javascript', 'typescript']:
        if find_file('yarn.lock'):
            project_info['package_manager'] = 'yarn'
        elif find_file('pnpm-lock.yaml'):
            project_info['package_manager'] = 'pnpm'
        elif find_file('package-lock.json'):
            project_info['package_manager'] = 'npm'
        elif find_file('package.json'):
            project_info['package_manager'] = 'npm'
    
    # Fallback: scan for common file extensions if still unknown
    if project_info['language'] == 'unknown':
        try:
            ext_counts = {}
            for root, dirs, files in os.walk(workspace_path):
                # Skip hidden and common ignored directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.venv', 'target', 'build', 'dist']]
                
                for file in files:
                    if file.startswith('.'):
                        continue
                    _, ext = os.path.splitext(file)
                    if ext:
                        ext_counts[ext] = ext_counts.get(ext, 0) + 1
                
                # Only scan first 100 files for performance
                if sum(ext_counts.values()) > 100:
                    break
            
            # Determine language by most common extension
            if ext_counts:
                top_ext = max(ext_counts, key=ext_counts.get)
                if top_ext in ['.py', '.pyi']:
                    project_info['language'] = 'python'
                elif top_ext in ['.js', '.jsx', '.mjs', '.cjs']:
                    project_info['language'] = 'javascript'
                elif top_ext in ['.ts', '.tsx']:
                    project_info['language'] = 'typescript'
                elif top_ext in ['.go']:
                    project_info['language'] = 'go'
                elif top_ext in ['.rs']:
                    project_info['language'] = 'rust'
                elif top_ext in ['.java']:
                    project_info['language'] = 'java'
        except Exception:
            pass
    
    return project_info

                        
PROJECT_INFO = detect_project_type(WORKSPACE_ROOT)

                             
                
                             
def handle_small_talk(user_text: str, append_history) -> bool:
    """Handle common greetings, capability questions, and API key status."""
    s = user_text.strip().lower()
    
    greetings = {"hi", "hii", "hello", "hey", "heyy", "heyyy", "hiya", "yo", "yo!", "hey!", "hi!"}
    if s in greetings or (s.startswith(("hi", "hey", "hello")) and len(s) <= 10):
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
    
    if ("what can you do" in s) or ("what do you do" in s) or ("capabilities" in s):
        reply = """# CodeGen CLI - Capabilities

I am a repository-aware CLI coding assistant that can interact with your codebase.

File Operations: read, write, edit, multi_edit
Search & Discovery: list_files, find_files, grep
Web: fetch_url, search_web
System: run_command, manage_todos

Try: 'read README.md', 'find **/*.py', 'grep TODO'"""
        output.print_assistant(reply)
        append_history(user_text, {"steps": [], "explain": "capabilities_reply"}, [])
        return True
    
    if "your name" in s or "who are you" in s:
        output.print_assistant("I am CodeGen, a CLI coding assistant.")
        append_history(user_text, {"steps": [], "explain": "name_reply"}, [])
        return True
    
    return False



                             
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
  
def repl():
    """Start the interactive REPL."""
    from .repl import run_repl
    
    deps = {
        "workspace_root": WORKSPACE_ROOT,
        "project_info": PROJECT_INFO,
        "output": output,
        "handle_small_talk": handle_small_talk,
        "append_history": append_history,
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
                "CLI coding agent that understands any codebase",
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
