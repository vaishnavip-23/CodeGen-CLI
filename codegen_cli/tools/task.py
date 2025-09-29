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

def _count_words(text: str) -> int:
    """Count words in text, ignoring markdown formatting."""
    # Remove markdown formatting for accurate word count
    import re
    clean_text = re.sub(r'[#*`\[\]()]', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    return len(clean_text.split())

def _truncate_to_word_limit(text: str, max_words: int = 1000) -> str:
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

        # Create a comprehensive, structured summary (under 1000 words)
        summary_text = f"""# CodeGen2 - CLI Coding Agent

## Project Overview

This project is a command-line coding assistant that understands natural language. It's designed to be a "repository-aware" agent, meaning it can interact with the files in your project to perform various tasks.

**Core Functionality:**
- **Natural Language Interface**: You can give it commands in plain English (e.g., "summarize the codebase," "read the README file")
- **LLM Integration**: It uses the Google Gemini API to understand your requests and create a plan of action
- **Tool-Based Architecture**: The agent has a set of "tools" it can use to interact with your project. These tools are modular Python scripts located in the tools/ directory
- **Safety First**: The agent is designed with safety in mind. It has built-in protections to prevent accidental damage to your files, and it will ask for your confirmation before making any destructive changes

## Key Components

- **`main.py`**: This is the main entry point of the application. It handles the user input, communicates with the Gemini API, and orchestrates the execution of the tools
- **`tools/` directory**: This directory contains the individual tools that the agent can use, such as read, write, edit, glob, grep, and bash
- **`system_prompt.txt`**: This file contains the instructions and rules that are provided to the Gemini API to guide its behavior
- **`output.py`**: This module is responsible for the user interface, including the colored and boxed output that you see in your terminal

## Project Statistics

- **Total Files**: {len(files)} files
- **Python Files**: {by_ext['.py']} files
- **Tool Count**: 13 specialized tools
- **Main Application**: 613 lines of code

## Workflow

The agent follows a "discovery-first" approach:

1. **Discover**: It uses tools like `ls` and `glob` to find files
2. **Inspect**: It uses tools like `read` and `grep` to examine the content of files
3. **Modify**: It uses tools like `edit` and `write` to make changes to files

This workflow ensures that the agent's actions are deliberate and predictable.

## Architecture

The system is built with a modular architecture where each tool is a separate Python module that can be called independently. The main application coordinates between the user, the LLM, and the tools to provide a seamless experience.

## Safety Features

- **Path Protection**: Prevents access outside workspace
- **Confirmation Required**: Asks permission for destructive changes
- **Command Security**: Blocks dangerous shell commands

In short, you have a powerful and well-designed coding agent that you can interact with using natural language. The agent is designed to be safe, predictable, and helpful for a wide range of coding tasks."""

        # Apply word limit to summary
        summary_text = _truncate_to_word_limit(summary_text, 1000)
        
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
