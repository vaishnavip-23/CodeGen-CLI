# File Summary: Implementation of the TodoWrite tool for managing task lists.

"""
Todo Management Tool for CodeGen-CLI

This tool manages a simple todo list stored in a JSON file.
It supports adding, listing, removing, and clearing todos.
"""

import os
from pathlib import Path
import json
from typing import List, Dict, Any

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import TodoItem, TodoStats, TodoWriteOutput

# Function declaration for Gemini function calling
FUNCTION_DECLARATION = {
    "name": "manage_todos",
    "description": "Manage todo list - add, list, update, or clear todos. Can accept full todo list for updates.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action: 'add', 'list', 'pop', 'clear', or provide todos array directly"
            },
            "text": {
                "type": "string",
                "description": "Todo text when action is 'add'"
            },
            "todos": {
                "type": "array",
                "description": "Full list of todos to replace current list",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                    }
                }
            }
        }
    }
}

def get_function_declaration():
    """Get Gemini function declaration for this tool."""
    if types is None:
        return None
    
    return types.FunctionDeclaration(
        name=FUNCTION_DECLARATION["name"],
        description="""Manage todo list for MODIFICATION tasks only (8+ files). 

CRITICAL: ONLY use for multi-file MODIFICATION tasks. NEVER for analysis/reading tasks.

For multiple todos: Use 'todos' parameter with full array (BATCH mode - 1 API call).
For single todo: Use 'action=add' with text.

Batch example (PREFERRED for 8+ items):
manage_todos(todos=[
  {"id":"1", "content":"Update file1.py", "status":"pending"},
  {"id":"2", "content":"Update file2.py", "status":"pending"}
])

Single todo example (for 1-2 items only):
manage_todos(action="add", text="Update config.py")""",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "action": types.Schema(type=types.Type.STRING, description="Action: 'add' (create single todo), 'list' (show all), 'pop' (mark first done), 'clear' (remove all). For 8+ todos, use 'todos' parameter instead."),
                "text": types.Schema(type=types.Type.STRING, description="REQUIRED when action='add'. The todo task description."),
                "todos": types.Schema(
                    type=types.Type.ARRAY,
                    description="BATCH MODE: Create multiple todos at once (PREFERRED for 8+ files). Saves API calls! Array of todo objects.",
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "id": types.Schema(type=types.Type.STRING, description="Unique ID"),
                            "content": types.Schema(type=types.Type.STRING, description="Todo description"),
                            "status": types.Schema(type=types.Type.STRING, description="Status: pending, in_progress, or completed")
                        }
                    )
                )
            }
        )
    )

def _resolve_db_paths():
    env_override = os.environ.get("CODEGEN_TODOS_PATH")
    if env_override:
        p = Path(env_override)
        return p.parent, p
                                           
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
                                                   
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    
                                                 
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
    text_normalized = text.strip().lower()
    
    # Check for duplicates (case-insensitive)
    for existing in todos:
        if existing.get("content", "").strip().lower() == text_normalized:
            return {
                "tool": "todowrite",
                "success": True,
                "output": todos  # Return existing list without adding duplicate
            }
    
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
        "output": todos  # Return full list so agent can see current state
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
    
    todos.pop(0)
    write_todos(todos)
    
    return {
        "tool": "todowrite",
        "success": True,
        "output": todos  # Return remaining todos so agent can see what's left
    }

def clear_todos() -> Dict[str, Any]:
    """
    Clear all todos and delete the database folder.
    
    Returns:
        Result dictionary
    """
    write_todos([])
    
                                                                        
    try:
        import shutil
        if os.path.exists(DB_DIR):
            shutil.rmtree(DB_DIR)
    except Exception:
                                                                               
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
                                                          
    try:
        return sorted(by_id.values(), key=lambda x: str(x.get("id")))
    except Exception:
        return list(by_id.values())


def call(action: str = "list", *args, **kwargs) -> Dict[str, Any]:
    """
    Main function for todo operations.
    
    Args:
        action: Action to perform (add, list, pop, clear)
        *args: Additional arguments (e.g., todo text for 'add')
        
    Returns:
        Result dictionary
    """
    # Handle direct list of todos
    if isinstance(action, list):
        # Validate items can be converted to TodoItem objects
        try:
            for t in action:
                TodoItem(
                    content=t.get("content", ""),
                    status=t.get("status", "pending"),
                    priority=t.get("priority"),
                    id=t.get("id")
                )
        except Exception as e:
            raise ValueError(f"Invalid input: {e}")
        
        merge = kwargs.get("merge", False)
        if merge:
            existing = read_todos()
            updated = _merge_by_id(existing, action)
            return _write_full_list(updated)
        return _write_full_list(action)

    # Handle list passed as first argument
    if args and isinstance(args[0], list):
        # Validate items can be converted to TodoItem objects
        try:
            for t in args[0]:
                TodoItem(
                    content=t.get("content", ""),
                    status=t.get("status", "pending"),
                    priority=t.get("priority"),
                    id=t.get("id")
                )
        except Exception as e:
            raise ValueError(f"Invalid input: {e}")
        
        merge = kwargs.get("merge", False)
        if merge:
            existing = read_todos()
            updated = _merge_by_id(existing, args[0])
            return _write_full_list(updated)
        return _write_full_list(args[0])

                                                                           
    if args and isinstance(args[0], dict):
        obj = args[0]
        todos_arg = obj.get("todos")
        if isinstance(todos_arg, list):
            if obj.get("merge"):
                existing = read_todos()
                updated = _merge_by_id(existing, todos_arg)
                return _write_full_list(updated)
            return _write_full_list(todos_arg)

                                                                     
    action = action or "list"
    
    if action == "add":
        text = " ".join(args) if args else kwargs.get("text", "")
        if not text:
            raise ValueError("Please provide todo text")
        return add_todo(text)
    
    elif action == "list":
        todos = read_todos()
        stats = TodoStats(
            total=len(todos),
            pending=len([t for t in todos if t.get("status") == "pending"]),
            in_progress=len([t for t in todos if t.get("status") == "in_progress"]),
            completed=len([t for t in todos if t.get("status") == "completed"])
        )
        output = TodoWriteOutput(
            message=f"Found {len(todos)} todos",
            stats=stats
        )
        return output.model_dump()
    
    elif action == "pop":
        return remove_first_todo()
    
    elif action == "clear":
        return clear_todos()
    
    else:
        raise ValueError(f"Unknown action: {action}. Available actions: add, list, pop, clear")
