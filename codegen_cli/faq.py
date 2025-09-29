"""
FAQ and small-talk handlers for CodeGen CLI.

Keeps conversational, non-tool responses separate from the core REPL logic.
"""

import os
from typing import Callable


def handle_small_talk(user_text: str, append_history: Callable[[str, dict, list], None]) -> bool:
    """Handle common greetings, capability questions, and API key status.

    Returns True if handled (no tools needed), otherwise False.
    """
    s = user_text.strip().lower()

    # Greetings
    greetings = {
        "hi", "hii", "hiii", "hiiii", "hello", "hey", "heyy", "heyyy",
        "hiya", "yo", "yo!", "hey!", "hi!"
    }
    if s in greetings or (s.startswith(("hi", "hey", "hello")) and len(s) <= 10):
        print("Assistant: Hello! How can I help you with your repository?")
        append_history(user_text, {"steps": [], "explain": "greeting"}, [])
        return True

    # Casual greetings
    if s in {"sup", "what's up", "whats up", "wassup", "howdy", "greetings"}:
        print("Assistant: Hey there! Ready to work on some code? What can I help you with?")
        append_history(user_text, {"steps": [], "explain": "casual_greeting"}, [])
        return True

    # Thanks
    if s in {"thanks", "thank you", "thx", "ty", "appreciate it", "thanks!"}:
        print("Assistant: You're welcome! Happy to help. Anything else you'd like to work on?")
        append_history(user_text, {"steps": [], "explain": "thanks"}, [])
        return True

    # Capabilities
    if "what can you do" in s or "what do you do" in s or "capabilities" in s:
        reply = """# CodeGen CLI - Capabilities

## Core Functionality
I am a repository-aware CLI coding assistant that can interact with your codebase through natural language commands.

## File Operations
- Read: Examine file contents
- Write: Create or overwrite files (with confirmation)
- Edit: Modify existing files
- MultiEdit: Perform multiple edits in sequence

## Search & Discovery
- List Files: Browse directories
- Search Text: Find patterns using grep
- Pattern Matching: Locate files using glob

## Web Integration
- Web Search and Fetch

## System Operations
- Bash commands (safe)
- Task management
- Codebase analysis

## Safety Features
- Path protection, confirmation for destructive changes, and safe command handling."""
        print("Assistant:", reply)
        append_history(user_text, {"steps": [], "explain": "capabilities_reply"}, [])
        return True

    # Name
    if "your name" in s or "who are you" in s:
        print("Assistant: I am a local CLI coding assistant (Agent). I work on this repo's files.")
        append_history(user_text, {"steps": [], "explain": "name_reply"}, [])
        return True

    # Short small talk
    for marker in {"thanks", "thank you", "bye", "goodbye"}:
        if marker in s:
            print("Assistant: You're welcome.")
            append_history(user_text, {"steps": [], "explain": "small_talk_reply"}, [])
            return True

    # API key status questions
    api_markers = ("api key", "apikey", "gemini key", "gemini api", "gemini")
    if any(m in s for m in api_markers) and (
        "set" in s or "configured" in s or "present" in s or "loaded" in s or "right" in s or "proper" in s or "ok" in s
    ):
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        if has_key:
            print("Assistant: Yes — GEMINI_API_KEY is set and will be used.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_yes"}, [])
        else:
            print("Assistant: No — GEMINI_API_KEY is not set. Run 'codegen --set-key' in your terminal or add it to your .env.")
            append_history(user_text, {"steps": [], "explain": "api_key_status_no"}, [])
        return True

    return False


