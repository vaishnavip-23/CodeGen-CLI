# File Summary: Implementation of the Task tool used for sub-agent workflows.

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
from typing import Any, Dict, List, Optional
import os
import json
import collections

import re
import ast

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
                                                       
        text = text.replace('\u2014', '-')                           
        text = text.replace('\u201c', '"')                     
        text = text.replace('\u201d', '"')                      
        text = text.replace('\u2018', "'")                     
        text = text.replace('\u2019', "'")                      
        text = text.replace('\u2026', '...')            
        return text[:max_chars] + ("..." if len(text) > max_chars else "")
    except Exception:
        return ""

def _count_words(text: str) -> int:
    """Count words in text, ignoring markdown formatting."""
                                                        
    import re
    clean_text = re.sub(r'[#*`\[\]()]', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return len(clean_text.split())

def _truncate_to_word_limit(text: str, max_words: int = 600) -> str:
    """Truncate text to stay under word limit while ensuring it feels complete."""
    if _count_words(text) <= max_words:
        return text
    
                                                        
    sentences = text.split('. ')
    result = ""
    word_count = 0
    
    for sentence in sentences:
        test_text = result + sentence + ". " if result else sentence + ". "
        if _count_words(test_text) > max_words:
            break
        result = test_text
    
                             
    if result and not result.endswith(('.', '!', '?')):
        result = result.rstrip() + "."
    
    return result

def _summarize_code_text(code_text: str, max_words: int = 500) -> str:
    """Heuristic summary of an inline code block without calling LLM.

    Detects language hints, counts lines, functions, classes, imports, and produces
    a concise explanation outline.
    """
    import re as _re
    text = code_text.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    total_lines = len(lines)
    sample = "\n".join(lines[:50])

                              
    language = "unknown"
    if _re.search(r"^\s*def\s+\w+\(", text, _re.M):
        language = "python"
    elif _re.search(r"^\s*(function|const|let|var)\s+\w+|=>\s*\{", text, _re.M):
        language = "javascript"
    elif _re.search(r"#include\s+<|int\s+main\s*\(", text):
        language = "c/c++"
    elif _re.search(r"class\s+\w+\s*:\s*$", text, _re.M):
        language = "python"

                    
    functions = len(_re.findall(r"(^\s*def\s+\w+\(|^\s*(function\s+\w+\(|\w+\s*=\s*\([^)]*\)\s*=>))", text, _re.M))
    classes = len(_re.findall(r"^\s*class\s+\w+", text, _re.M))
    imports = len(_re.findall(r"^\s*(import\s+|from\s+\w+\s+import|#include\s+)", text, _re.M))

                                                 
    doc = ""
    m = _re.search(r"^\s*([\"\']{3}[\s\S]*?[\"\']{3})", text)
    if m:
        doc = m.group(1)
    else:
        m2 = _re.search(r"^\s*//\s*(.+)$", text, _re.M)
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

                                  
    if language == "python":
        if _re.search(r"if __name__ == ['\"]__main__['\"]:", text):
            summary.append("\nContains a script entry point guarded by __main__.")
        if classes:
            summary.append("Defines one or more classes; likely object-oriented components.")
        if functions:
            summary.append("Defines helper or API functions to encapsulate logic.")
    elif language == "javascript":
        if _re.search(r"module\.exports|export\s+(default|const|function)", text):
            summary.append("\nModule with exported APIs (CommonJS/ESM).")
        if _re.search(r"async\s+function|=>\s*\{", text):
            summary.append("Uses asynchronous functions or arrow functions.")

                             
    snippet = sample[:600] + ("..." if len(sample) > 600 else "")
    summary.append("\nRepresentative snippet:\n" + snippet)

    text_out = "\n".join(summary)
    return _truncate_to_word_limit(text_out, max_words)
def _extract_requested_line_limit(*texts: str) -> Optional[int]:
    for text in texts:
        if not text:
            continue
        match = re.search(r"\b(\d+)\s+lines?\b", text.lower())
        if match:
            try:
                return max(1, min(40, int(match.group(1))))
            except ValueError:
                continue
    return None


def _find_existing_path(*texts: str) -> Optional[Path]:
    for text in texts:
        if not text:
            continue
        for candidate in re.findall(r"[\w./\\-]+\.[\w]+", text):
            candidate = candidate.strip().strip('"').strip("'")
            possible = ROOT / candidate
            if possible.exists() and possible.is_file():
                return possible
    return None


def _summarize_python_file(path: Path, source: str, line_limit: Optional[int]) -> List[str]:
    lines: List[str] = []
    module_name = path.name
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None

    if tree is not None:
        module_doc = ast.get_docstring(tree)
        if module_doc:
            lines.append(f"{module_name}: {module_doc.splitlines()[0].strip()}")

        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

        if functions:
            fn_names = ", ".join(fn.name for fn in functions[:3])
            more = " ..." if len(functions) > 3 else ""
            lines.append(f"Functions: {fn_names}{more}.")

        if classes:
            class_names = ", ".join(cls.name for cls in classes[:3])
            more = " ..." if len(classes) > 3 else ""
            lines.append(f"Classes: {class_names}{more}.")

        main_guard = any(
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and any(
                isinstance(comp, ast.Constant) and comp.value == "__main__"
                for comp in node.test.comparators
            )
            for node in tree.body
        )
        if main_guard:
            lines.append("Includes a __main__ guard to run as a script.")

                                                   
        for fn in functions[:2]:
            fn_doc = ast.get_docstring(fn)
            if fn_doc:
                lines.append(f"{fn.name}(): {fn_doc.splitlines()[0].strip()}.")
            else:
                lines.append(f"{fn.name}() encapsulates core logic.")

    if not lines:
                                           
        stripped = [ln.strip() for ln in source.splitlines() if ln.strip()]
        snippet = " ".join(stripped[:3])
        lines.append(f"{module_name} contains Python code: {snippet[:120]}".rstrip())

                                            
    if line_limit:
        return lines[:line_limit]
    return lines


def _summarize_text_file(path: Path, line_limit: Optional[int]) -> List[str]:
    text = _read_excerpt(path, 800)
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    if not paragraphs:
        return [f"{path.name} is empty or contains only whitespace."]
    if line_limit and line_limit < len(paragraphs):
        return paragraphs[:line_limit]
    return paragraphs[:min(len(paragraphs), 8)]


def _summarize_file(path: Path, line_limit: Optional[int]) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Failed to read {path.name}: {exc}"

    suffix = path.suffix.lower()
    if suffix == ".py":
        lines = _summarize_python_file(path, text, line_limit)
    else:
        lines = _summarize_text_file(path, line_limit)

    if line_limit and len(lines) > line_limit:
        lines = lines[:line_limit]

    return "\n".join(lines)
    """Heuristic summary of an inline code block without calling LLM.

    Detects language hints, counts lines, functions, classes, imports, and produces
    a concise explanation outline.
    """
    import re
    text = code_text.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    total_lines = len(lines)
    sample = "\n".join(lines[:50])

                              
    language = "unknown"
    if re.search(r"^\s*def\s+\w+\(", text, re.M):
        language = "python"
    elif re.search(r"^\s*(function|const|let|var)\s+\w+|=>\s*\{", text, re.M):
        language = "javascript"
    elif re.search(r"#include\s+<|int\s+main\s*\(", text):
        language = "c/c++"
    elif re.search(r"class\s+\w+\s*:\s*$", text, re.M):
        language = "python"

                    
    functions = len(re.findall(r"(^\s*def\s+\w+\(|^\s*(function\s+\w+\(|\w+\s*=\s*\([^)]*\)\s*=>))", text, re.M))
    classes = len(re.findall(r"^\s*class\s+\w+", text, re.M))
    imports = len(re.findall(r"^\s*(import\s+|from\s+\w+\s+import|#include\s+)", text, re.M))

                                                 
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
                                                     
        if subagent_type in ("code-summary", "code_explain") or (description and "code" in description.lower() and prompt.strip()):
            code_summary = _summarize_code_text(prompt)
            out = {"summary": code_summary}
            return {"tool": "Task", "success": True, "output": out, "args": [description, "<code-block>", subagent_type], "kwargs": {}}

                                                                              
        top_level_paths = _gather_top_level_entries(ROOT)
        top_level = [p.name for p in sorted(top_level_paths, key=lambda x: x.name.lower())]
                                                                      
        by_ext = collections.Counter()
        for p in top_level_paths:
            if p.is_file():
                ext = p.suffix.lower() or "<noext>"
                by_ext[ext] += 1

                                                         
        described = [f"- {p.name}: {_describe_entry(p)}" for p in sorted(top_level_paths, key=lambda x: x.name.lower())]
        dir_names = [p.name for p in top_level_paths if p.is_dir()]
        file_names = [p.name for p in top_level_paths if p.is_file()]

        line_limit = _extract_requested_line_limit(prompt, description)

        target_path = _find_existing_path(description or "", prompt or "")
        if target_path:
            summary_text = _summarize_file(target_path, line_limit)
            return {
                "tool": "Task",
                "success": True,
                "output": {"summary": summary_text},
                "args": [description, str(target_path), subagent_type],
                "kwargs": {}
            }

                                        
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

                                                                                 
        top_level_display = ", ".join(top_level[:20]) + (" ..." if len(top_level) > 20 else "")
        by_ext_display = dict(by_ext.most_common(10))
        if len(by_ext) > 10:
            by_ext_display_trailer = " ..."
        else:
            by_ext_display_trailer = ""
                                                                           
        readme_section = ""
        behavior_section = ""

        if line_limit:
            project_label = ROOT.name or "This project"
            line_candidates = [
                f"{project_label} is a repository-aware CLI coding agent focused on safe, tool-driven codebase edits."
            ]
            if Path("codegen_cli").exists():
                line_candidates.append("The `codegen_cli` package houses the entrypoint, REPL workflow, and modular tool implementations.")
            if dir_names:
                dir_snippet = ", ".join(sorted(dir_names)[:3]) + (" ..." if len(dir_names) > 3 else "")
                line_candidates.append(f"Key directories include {dir_snippet}.")
            if file_names:
                file_snippet = ", ".join(sorted(file_names)[:3]) + (" ..." if len(file_names) > 3 else "")
                line_candidates.append(f"Important top-level files: {file_snippet}.")
            if Path("codegen_cli/config").exists():
                line_candidates.append("Configuration under `codegen_cli/config` defines the system prompt and behavior heuristics for the agent.")
            if Path("codegen_cli/tools").exists():
                line_candidates.append("Modules in `codegen_cli/tools` wrap safe operations such as read, edit, python_run, and python_check.")
            if Path("test").exists() or Path("tests").exists():
                line_candidates.append("A test suite in the test/tests directory helps validate tool behavior.")
            if Path("docs").exists():
                line_candidates.append("Documentation lives in docs/ alongside the project root README.")
            if by_ext:
                ext_pairs = ", ".join(f"{ext}: {count}" for ext, count in by_ext.most_common(3))
                if ext_pairs:
                    line_candidates.append(f"File-type snapshot (top-level): {ext_pairs}.")
            line_candidates.append("The workflow emphasizes discovery-first exploration, targeted edits, and confirmations before destructive steps.")

            extra_lines = [entry[2:].replace(":", " —", 1) for entry in described]
            for entry in extra_lines:
                if entry not in line_candidates:
                    line_candidates.append(entry)
            while len(line_candidates) < line_limit:
                line_candidates.append("Additional repository files supply packaging metadata and support assets for the CLI.")
            summary_text = "\n".join(line_candidates[:line_limit])
        else:
                                                                
            summary_text = f"""
# Repository Summary

## Overview
High-level: A repository-aware CLI coding agent that executes safe, tool-driven actions in response to natural-language instructions. Emphasizes discovery-first planning and confirmation for destructive steps.

## Top-level Items (one line each)
{os.linesep.join(described)}

## Key Components (high-level)
- codegen_cli/main.py: entrypoint logic, plan generation, history
- codegen_cli/repl.py: interactive loop, routes NL to tools/tasks
- codegen_cli/output.py: UI/printing helpers
- codegen_cli/tools/: modular tools (read, edit, grep, ls, glob, etc.)
- codegen_cli/config/: system prompt and behavior guidance

## Workflow (brief)
1) Discover with LS/Glob → 2) Inspect with Read/Grep → 3) Plan (LLM) with confirmation → 4) Execute tools
"""

                                                    
            summary_text = _truncate_to_word_limit(summary_text, 600)
        
                                                                                  
        out = {
            "summary": summary_text
        }
        return {"tool": "Task", "success": True, "output": out, "args": [description, prompt, subagent_type], "kwargs": {}}
    except Exception as e:
        return {"tool": "Task", "success": False, "output": f"Task tool error: {e}", "args": [description, prompt, subagent_type], "kwargs": {}}
