"""
Todo Management Tool for CodeGen2

This tool manages a simple todo list stored in a JSON file.
It supports adding, listing, removing, and clearing todos.
"""

import os
from pathlib import Path
import json
from typing import List, Dict, Any

# Resolve persistent storage location (user config by default)
def _resolve_db_paths():
    env_override = os.environ.get("CODEGEN_TODOS_PATH")
    if env_override:
        p = Path(env_override)
        return p.parent, p
    # Always use user config dir by default
    db_dir = Path.home() / ".config" / "codegen"
    db_file = db_dir / "todos.json"
    return db_dir, db_file

DB_DIR_P, DB_FILE_P = _resolve_db_paths()
DB_DIR = str(DB_DIR_P)
DB_FILE = str(DB_FILE_P)

def ensure_database():
    """
    Ensure the database directory and file exist.
    Creates them if they don't exist.
    """
    # Create database directory if it doesn't exist
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    
    # Create empty todos file if it doesn't exist
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def read_todos() -> List[Dict[str, Any]]:
    """
    Read all todos from the database.
    
    Returns:
        List of todo dictionaries
    """
    ensure_database()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is corrupted or missing, return empty list
        return []

def write_todos(todos: List[Dict[str, Any]]):
    """
    Write todos to the database.
    
    Args:
        todos: List of todo dictionaries to save
    """
    ensure_database()
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, indent=2)

def add_todo(text: str) -> Dict[str, Any]:
    """
    Add a new todo item.
    
    Args:
        text: Todo text content
        
    Returns:
        Result dictionary
    """
    if not text.strip():
        return {
            "tool": "todowrite",
            "success": False,
            "output": "Todo text cannot be empty."
        }
    
    todos = read_todos()
    new_todo = {
        "id": str(len(todos) + 1),
        "content": text.strip(),
        "status": "pending"
    }
    todos.append(new_todo)
    write_todos(todos)
    
    return {
        "tool": "todowrite",
        "success": True,
        "output": f"Added todo: {text.strip()}"
    }

def list_todos() -> Dict[str, Any]:
    """
    List all todos.
    
    Returns:
        Result dictionary with todo list
    """
    todos = read_todos()
    return {
        "tool": "todowrite",
        "success": True,
        "output": todos
    }

def remove_first_todo() -> Dict[str, Any]:
    """
    Remove the first todo item.
    
    Returns:
        Result dictionary
    """
    todos = read_todos()
    if not todos:
        return {
            "tool": "todowrite",
            "success": False,
            "output": "No todos to remove."
        }
    
    removed_todo = todos.pop(0)
    write_todos(todos)
    
    return {
        "tool": "todowrite",
        "success": True,
        "output": f"Removed: {removed_todo}"
    }

def clear_todos() -> Dict[str, Any]:
    """
    Clear all todos and delete the database folder.
    
    Returns:
        Result dictionary
    """
    write_todos([])
    
    # Delete the database folder to prevent todo confusion between tasks
    try:
        import shutil
        if os.path.exists(DB_DIR):
            shutil.rmtree(DB_DIR)
    except Exception as e:
        # If deletion fails, continue - the important part is todos are cleared
        pass
    
    return {
        "tool": "todowrite",
        "success": True,
        "output": "Cleared all todos and cleaned up database."
    }

def call(action: str = "list", *args) -> Dict[str, Any]:
    """
    Main function for todo operations.
    
    Args:
        action: Action to perform (add, list, pop, clear)
        *args: Additional arguments (e.g., todo text for 'add')
        
    Returns:
        Result dictionary
    """
    action = action or "list"
    
    if action == "add":
        text = " ".join(args) if args else ""
        return add_todo(text)
    
    elif action == "list":
        return list_todos()
    
    elif action == "pop":
        return remove_first_todo()
    
    elif action == "clear":
        return clear_todos()
    
    else:
        return {
            "tool": "todowrite",
            "success": False,
            "output": f"Unknown action: {action}. Available actions: add, list, pop, clear"
        }
