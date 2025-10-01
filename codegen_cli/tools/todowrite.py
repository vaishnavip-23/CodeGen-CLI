"""
Todo Management Tool for CodeGen-CLI

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

def _is_todo_item(obj: Any) -> bool:
    """
    Validate a single todo item shape.

    Expected keys: id, content, status
    """
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in ("id", "content", "status"))


def _write_full_list(new_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Replace the entire todo list with the provided list.
    """
    if not isinstance(new_list, list) or not all(_is_todo_item(it) for it in new_list):
        return {
            "tool": "todowrite",
            "success": False,
            "output": "Invalid todos array. Each item must have id, content, status."
        }
    write_todos(new_list)
    return {
        "tool": "todowrite",
        "success": True,
        "output": {"message": "Todos updated", "count": len(new_list)}
    }


def _merge_by_id(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge incoming todos into existing by id. Replace items with matching ids; add new otherwise.
    """
    by_id = {t.get("id"): t for t in existing if isinstance(t, dict) and t.get("id") is not None}
    for it in incoming:
        if not _is_todo_item(it):
            continue
        by_id[it["id"]] = it
    # Preserve stable order by sorting by id (string-safe)
    try:
        return sorted(by_id.values(), key=lambda x: str(x.get("id")))
    except Exception:
        return list(by_id.values())


def update_todo_status(todo_id: str, new_status: str) -> Dict[str, Any]:
    """
    Update the status of a specific todo item.
    
    Args:
        todo_id: ID of the todo to update
        new_status: New status (pending, in_progress, completed)
        
    Returns:
        Result dictionary
    """
    valid_statuses = {"pending", "in_progress", "completed"}
    if new_status not in valid_statuses:
        return {
            "tool": "todowrite",
            "success": False,
            "output": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        }
    
    todos = read_todos()
    updated = False
    
    for todo in todos:
        if todo.get("id") == todo_id:
            todo["status"] = new_status
            updated = True
            break
    
    if not updated:
        return {
            "tool": "todowrite",
            "success": False,
            "output": f"Todo with ID '{todo_id}' not found"
        }
    
    write_todos(todos)
    return {
        "tool": "todowrite",
        "success": True,
        "output": f"Updated todo {todo_id} status to {new_status}"
    }

def get_active_todos() -> Dict[str, Any]:
    """
    Get todos that are pending or in_progress.
    
    Returns:
        Result dictionary with active todos
    """
    todos = read_todos()
    active = [t for t in todos if t.get("status") in {"pending", "in_progress"}]
    return {
        "tool": "todowrite",
        "success": True,
        "output": {
            "active_todos": active,
            "count": len(active)
        }
    }

def call(action: str = "list", *args, **kwargs) -> Dict[str, Any]:
    """
    Main function for todo operations.
    
    Args:
        action: Action to perform (add, list, pop, clear, update_status, active)
        *args: Additional arguments (e.g., todo text for 'add')
        
    Returns:
        Result dictionary
    """
    # Support system-prompt style: TodoWrite(todos_array) or TodoWrite({merge:bool, todos:[...]})
    # Case 1: action itself was passed as the todos array (dispatcher passes positional only)
    if isinstance(action, list):
        todos_arg = action
        merge = False
        if isinstance(kwargs, dict):
            merge = bool(kwargs.get("merge", False))
        if merge:
            existing = read_todos()
            updated = _merge_by_id(existing, todos_arg)
            return _write_full_list(updated)
        return _write_full_list(todos_arg)

    # If the first positional arg is a list, treat it as the full todos list to write (direct calls)
    if args and isinstance(args[0], list):
        todos_arg = args[0]
        merge = False
        if isinstance(kwargs, dict):
            merge = bool(kwargs.get("merge", False))
        if merge:
            existing = read_todos()
            updated = _merge_by_id(existing, todos_arg)
            return _write_full_list(updated)
        return _write_full_list(todos_arg)

    # If the first positional arg is a dict with {todos:[...], merge?:bool}
    if args and isinstance(args[0], dict):
        obj = args[0]
        todos_arg = obj.get("todos")
        if isinstance(todos_arg, list):
            if obj.get("merge"):
                existing = read_todos()
                updated = _merge_by_id(existing, todos_arg)
                return _write_full_list(updated)
            return _write_full_list(todos_arg)

    # Fallback to legacy subcommand interface
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
    
    elif action == "update_status":
        if len(args) < 2:
            return {
                "tool": "todowrite",
                "success": False,
                "output": "update_status requires todo_id and new_status arguments"
            }
        return update_todo_status(args[0], args[1])
    
    elif action == "active":
        return get_active_todos()
    
    else:
        return {
            "tool": "todowrite",
            "success": False,
            "output": f"Unknown action: {action}. Available actions: add, list, pop, clear, update_status, active"
        }
