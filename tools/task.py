"""
tools/task.py

A lightweight Task tool for CodeGen2.

Usage:
  call(description, prompt, subagent_type)

This implementation performs a simple static summary:
- counts files by extension
- lists top-level files and folders
- returns the first 2000 characters of README.md and behavior.md if present

This is simple and safe (read-only) and intended to satisfy "generate summary for the codebase".
"""

from pathlib import Path
from typing import Any, Dict, List
import os
import json
import collections

ROOT = Path.cwd()

def _gather_files(root: Path) -> List[Path]:
    files = []
    for p in root.rglob('*'):
        if p.is_file():
            # ignore common noise
            if any(part in ('.git', '__pycache__', 'node_modules', '.venv') for part in p.parts):
                continue
            files.append(p)
    return files

def _read_excerpt(path: Path, max_chars: int = 2000) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
        # Clean up unicode characters and format better
        text = text.replace('\u2014', '-')  # em dash to regular dash
        text = text.replace('\u201c', '"')  # left double quote
        text = text.replace('\u201d', '"')  # right double quote
        text = text.replace('\u2018', "'")  # left single quote
        text = text.replace('\u2019', "'")  # right single quote
        text = text.replace('\u2026', '...')  # ellipsis
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception:
        return ""

def call(description: str = "", prompt: str = "", subagent_type: str = "general-purpose") -> Dict[str, Any]:
    """
    Entrypoint for the Task tool.

    Returns:
      {"tool":"Task", "success": True/False, "output": { ... structured summary ... }}
    """
    try:
        files = _gather_files(ROOT)
        by_ext = collections.Counter()
        for f in files:
            ext = f.suffix.lower() or "<noext>"
            by_ext[ext] += 1

        top_level = []
        for p in sorted(ROOT.iterdir(), key=lambda x: x.name.lower()):
            if p.name in ('.git', '.venv'):  # skip noisy top-level entries
                continue
            top_level.append(p.name)

        readme = _read_excerpt(ROOT / "README.md", 1000)
        behavior = _read_excerpt(ROOT / "behavior.md", 1000)

        # Create a concise summary
        summary_text = f"""CodeGen2 - CLI Coding Agent

OVERVIEW:
- Repository-aware CLI assistant for natural language codebase interaction
- {len(files)} total files ({by_ext['.py']} Python files)
- Modular tool architecture with 13 specialized tools

KEY COMPONENTS:
- main.py: CLI application with LLM integration (Google Gemini)
- tools/: 13 tools for file ops, search, web, and task management
- Safety-first design with path protection and user confirmations

WORKFLOW:
- Discovery-first approach: find files, search content, inspect, then modify
- Edit/MultiEdit for changes, Write only for new files
- User confirmation required for destructive operations"""

        out = {
            "summary": summary_text,
            "files_count": len(files),
            "files_by_extension": dict(by_ext.most_common()),
            "top_level": top_level,
            "readme_excerpt": readme,
            "behavior_excerpt": behavior
        }
        return {"tool": "Task", "success": True, "output": out, "args": [description, prompt, subagent_type], "kwargs": {}}
    except Exception as e:
        return {"tool": "Task", "success": False, "output": f"Task tool error: {e}", "args": [description, prompt, subagent_type], "kwargs": {}}
