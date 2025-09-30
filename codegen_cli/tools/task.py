"""
tools/task.py

A lightweight Task tool for CodeGen-CLI.

Usage:
  call(description, prompt, subagent_type)

This implementation builds a concise, high-level repository summary:
- Does NOT scan every file (avoids deep recursion)
- Lists top-level files and folders
- Highlights key components with one-line descriptions
- Reads short excerpts from README/behavior docs if present
- Produces a professional, structured summary limited to 600 words
"""

from pathlib import Path
from typing import Any, Dict, List
import os
import json
import collections

ROOT = Path.cwd()

def _gather_top_level_entries(root: Path) -> List[Path]:
    """Return only top-level entries (files/dirs) to keep summary high-level."""
    try:
        return [p for p in root.iterdir() if p.name not in ('.git', '.venv', '.env', 'node_modules', 'dist', 'build', '__pycache__')]
    except Exception:
        return []

def _describe_entry(p: Path) -> str:
    """Return a concise one-line description for a top-level entry."""
    name = p.name
    if p.is_dir():
        dir_map = {
            'codegen_cli': 'Python package for the CLI agent (core, tools, config)',
            'docs': 'Project documentation and README',
            'tests': 'Test suite for the CLI agent',
            '.github': 'GitHub workflows and repository configuration',
        }
        return dir_map.get(name, 'Directory')
    # files
    file_map = {
        'pyproject.toml': 'Project metadata, dependencies, entry points',
        'setup.py': 'Legacy setup script for packaging',
        'MANIFEST.in': 'Packaging include rules',
        'LICENSE': 'Project license',
        'quickstart.sh': 'Helper script to bootstrap usage',
        'uv.lock': 'uv resolver lock file',
        '.gitignore': 'Git ignore rules',
        '.python-version': 'Python version pin for tooling',
        'README.md': 'Repository overview',
    }
    return file_map.get(name, 'File')

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

def _count_words(text: str) -> int:
    """Count words in text, ignoring markdown formatting."""
    # Remove markdown formatting for accurate word count
    import re
    clean_text = re.sub(r'[#*`\[\]()]', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return len(clean_text.split())

def _truncate_to_word_limit(text: str, max_words: int = 600) -> str:
    """Truncate text to stay under word limit while ensuring it feels complete."""
    if _count_words(text) <= max_words:
        return text
    
    # Split into sentences to find a good breaking point
    sentences = text.split('. ')
    result = ""
    word_count = 0
    
    for sentence in sentences:
        test_text = result + sentence + ". " if result else sentence + ". "
        if _count_words(test_text) > max_words:
            break
        result = test_text
    
    # Ensure it ends properly
    if result and not result.endswith(('.', '!', '?')):
        result = result.rstrip() + "."
    
    return result

def _summarize_code_text(code_text: str, max_words: int = 500) -> str:
    """Heuristic summary of an inline code block without calling LLM.

    Detects language hints, counts lines, functions, classes, imports, and produces
    a concise explanation outline.
    """
    import re
    text = code_text.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    total_lines = len(lines)
    sample = "\n".join(lines[:50])

    # Naive language detection
    language = "unknown"
    if re.search(r"^\s*def\s+\w+\(", text, re.M):
        language = "python"
    elif re.search(r"^\s*(function|const|let|var)\s+\w+|=>\s*\{", text, re.M):
        language = "javascript"
    elif re.search(r"#include\s+<|int\s+main\s*\(", text):
        language = "c/c++"
    elif re.search(r"class\s+\w+\s*:\s*$", text, re.M):
        language = "python"

    # Feature counts
    functions = len(re.findall(r"(^\s*def\s+\w+\(|^\s*(function\s+\w+\(|\w+\s*=\s*\([^)]*\)\s*=>))", text, re.M))
    classes = len(re.findall(r"^\s*class\s+\w+", text, re.M))
    imports = len(re.findall(r"^\s*(import\s+|from\s+\w+\s+import|#include\s+)", text, re.M))

    # Pull top-level docstring/comment if present
    doc = ""
    m = re.search(r"^\s*([\"\']{3}[\s\S]*?[\"\']{3})", text)
    if m:
        doc = m.group(1)
    else:
        m2 = re.search(r"^\s*//\s*(.+)$", text, re.M)
        if m2:
            doc = m2.group(1)

    summary = []
    summary.append("# Code Block Summary")
    summary.append("")
    summary.append(f"Language: {language}")
    summary.append(f"Lines: {total_lines}")
    summary.append(f"Functions: {functions} | Classes: {classes} | Imports: {imports}")
    if doc:
        summary.append("")
        summary.append("Docstring/Comment excerpt:")
        summary.append(doc[:300] + ("..." if len(doc) > 300 else ""))

    # Outline based on simple cues
    if language == "python":
        if re.search(r"if __name__ == ['\"]__main__['\"]:", text):
            summary.append("\nContains a script entry point guarded by __main__.")
        if classes:
            summary.append("Defines one or more classes; likely object-oriented components.")
        if functions:
            summary.append("Defines helper or API functions to encapsulate logic.")
    elif language == "javascript":
        if re.search(r"module\.exports|export\s+(default|const|function)", text):
            summary.append("\nModule with exported APIs (CommonJS/ESM).")
        if re.search(r"async\s+function|=>\s*\{", text):
            summary.append("Uses asynchronous functions or arrow functions.")

    # Include a small snippet
    snippet = sample[:600] + ("..." if len(sample) > 600 else "")
    summary.append("\nRepresentative snippet:\n" + snippet)

    text_out = "\n".join(summary)
    return _truncate_to_word_limit(text_out, max_words)

def call(description: str = "", prompt: str = "", subagent_type: str = "general-purpose") -> Dict[str, Any]:
    """
    Entrypoint for the Task tool.

    Returns:
      {"tool":"Task", "success": True/False, "output": { ... structured summary ... }}
    """
    try:
        # If called to summarize an inline code block
        if subagent_type in ("code-summary", "code_explain") or (description and "code" in description.lower() and prompt.strip()):
            code_summary = _summarize_code_text(prompt)
            out = {"summary": code_summary}
            return {"tool": "Task", "success": True, "output": out, "args": [description, "<code-block>", subagent_type], "kwargs": {}}

        # High-level only: do not scan entire repo. Inspect top-level entries.
        top_level_paths = _gather_top_level_entries(ROOT)
        top_level = [p.name for p in sorted(top_level_paths, key=lambda x: x.name.lower())]
        # Approximate file type distribution from top-level files only
        by_ext = collections.Counter()
        for p in top_level_paths:
            if p.is_file():
                ext = p.suffix.lower() or "<noext>"
                by_ext[ext] += 1

        # Build one-line descriptions per top-level entry
        described = [f"- {p.name}: {_describe_entry(p)}" for p in sorted(top_level_paths, key=lambda x: x.name.lower())]

        # Try multiple README-like files
        readme_candidates = [
            ROOT / "README.md",
            ROOT / "Readme.md",
            ROOT / "readme.md",
            ROOT / "docs" / "README.md",
        ]
        readme = ""
        for cand in readme_candidates:
            if cand.exists():
                readme = _read_excerpt(cand, 1000)
                break

        behavior_candidates = [
            ROOT / "behavior.md",
            ROOT / "docs" / "behavior.md",
            ROOT / "codegen_cli" / "config" / "behavior.md",
        ]
        behavior = ""
        for cand in behavior_candidates:
            if cand.exists():
                behavior = _read_excerpt(cand, 1000)
                break

        # Precompute display strings to avoid backslashes in f-string expressions
        top_level_display = ", ".join(top_level[:20]) + (" ..." if len(top_level) > 20 else "")
        by_ext_display = dict(by_ext.most_common(10))
        if len(by_ext) > 10:
            by_ext_display_trailer = " ..."
        else:
            by_ext_display_trailer = ""
        readme_section = f"README excerpt:\n{readme}\n\n" if readme else ""
        behavior_section = f"Behavior doc excerpt:\n{behavior}\n\n" if behavior else ""

        # Create a concise, structured summary (<=600 words)
        summary_text = f"""
# Repository Summary

## Overview
This repository contains a repository-aware CLI coding agent. It accepts natural-language requests and executes safe, tool-driven actions against the local project. It emphasizes discover-first planning, clear confirmation for destructive steps, and readable, boxed terminal output.

## Capabilities
- Natural language commands (e.g., "summarize the repo", "find TODOs", "edit file")
- LLM-backed plan generation with strict JSON schema
- Rich tool suite: Read, Write, Edit, MultiEdit, Grep, Glob, LS, Bash (safe), WebFetch, WebSearch, Delete, TodoWrite, Task
- User-friendly REPL with small-talk and dynamic help
- API key management and rate-limit error messages

## Structure
- Top-level entries: {top_level_display}
- File counts by extension: {by_ext_display}{by_ext_display_trailer}
  (High-level view only; not scanning all files)

## Top-level Items (one-line each)
{os.linesep.join(described)}

## Key Components
- codegen_cli/main.py: configuration, plan generation, history handling
- codegen_cli/repl.py: interactive loop, NL routing to Task/tool plans
- codegen_cli/output.py: rendering boxed output and tool results
- codegen_cli/tools/: modular tools used by the agent
- codegen_cli/config/: behavior and system prompt specifications

## Workflow
1. Discover with LS/Glob
2. Inspect with Read/Grep
3. Propose a plan (LLM), validate, ask consent for destructive steps
4. Execute tools and display results

## Documentation Excerpts
{readme_section}{behavior_section}
## Notes
- History and todos are stored in user config (~/.config/codegen), never in the project
- Project-local .codegen override is disabled by default
"""

        # Apply strict 600-word limit to summary
        summary_text = _truncate_to_word_limit(summary_text, 600)
        
        # Return only the composed summary to avoid duplicate sections in renderer
        out = {
            "summary": summary_text
        }
        return {"tool": "Task", "success": True, "output": out, "args": [description, prompt, subagent_type], "kwargs": {}}
    except Exception as e:
        return {"tool": "Task", "success": False, "output": f"Task tool error: {e}", "args": [description, prompt, subagent_type], "kwargs": {}}
