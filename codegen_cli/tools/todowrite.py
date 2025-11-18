"""
Todo Management Tool for CodeGen-CLI
Refactored to use Gemini's native Pydantic function calling with from_callable().

This tool manages a simple todo list stored in a JSON file.
It supports adding, listing, removing, and clearing todos.
"""

import os
from pathlib import Path
import json
from typing import List, Dict, Any, Optional, Union

try:
    from google.genai import types
except ImportError:
    types = None

from ..models.schema import TodoItem, TodoStats, TodoWriteOutput


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
    """Ensure the database directory and file exist."""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def read_todos() -> List[Dict[str, Any]]:
    """Read all todos from the database."""
    ensure_database()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def write_todos_to_db(todos: List[Dict[str, Any]]):
    """Write todos to the database."""
    ensure_database()
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, indent=2)


def _is_todo_item(obj: Any) -> bool:
    """Validate a single todo item shape."""
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in ("id", "content", "status"))


def _merge_by_id(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge incoming todos into existing by id."""
    by_id = {t.get("id"): t for t in existing if isinstance(t, dict) and t.get("id") is not None}
    for it in incoming:
        if not _is_todo_item(it):
            continue
        by_id[it["id"]] = it
    try:
        return sorted(by_id.values(), key=lambda x: str(x.get("id")))
    except Exception:
        return list(by_id.values())


def manage_todos(
    action: Optional[str] = "list",
    text: Optional[str] = None,
    todos: Optional[List[Dict[str, Any]]] = None,
    merge: bool = False
) -> Dict[str, Any]:
    """Manage todo list for MODIFICATION tasks (8+ files).
    
    Use for tracking multi-file MODIFICATION tasks only. NEVER for analysis/reading.
    Supports batch operations (preferred for 8+ files) and individual actions.
    
    Args:
        action: Action to perform - 'add' (create single todo), 'list' (show all), 
                'pop' (mark first done), 'clear' (remove all). For 8+ todos, use 'todos' parameter instead.
        text: Todo text when action='add' (required for add action)
        todos: BATCH MODE - create/update multiple todos at once (PREFERRED for 8+ files). 
               Array of todo objects with id, content, and status fields. Saves API calls!
        merge: If True with todos parameter, merges with existing todos by id (optional)
        
    Returns:
        A dictionary containing todo list or operation results and statistics.
    
    Examples:
        Batch mode (PREFERRED for 8+ items):
            manage_todos(todos=[
                {"id":"1", "content":"Update file1.py", "status":"pending"},
                {"id":"2", "content":"Update file2.py", "status":"pending"}
            ])
        
        Single todo (for 1-2 items only):
            manage_todos(action="add", text="Update config.py")
        
        List all:
            manage_todos(action="list")
    """
    # Handle batch mode - todos array provided
    if todos is not None:
        # Validate todos can be converted to TodoItem objects
        try:
            for t in todos:
                TodoItem(
                    content=t.get("content", ""),
                    status=t.get("status", "pending"),
                    priority=t.get("priority"),
                    id=t.get("id")
                )
        except Exception as e:
            raise ValueError(f"Invalid todo items: {e}")
        
        if merge:
            existing = read_todos()
            updated = _merge_by_id(existing, todos)
            write_todos_to_db(updated)
        else:
            if not isinstance(todos, list) or not all(_is_todo_item(it) for it in todos):
                raise ValueError("Invalid todos array. Each item must have id, content, status.")
            write_todos_to_db(todos)
        
        return {
            "tool": "todowrite",
            "success": True,
            "output": {"message": "Todos updated", "count": len(todos)}
        }
    
    # Handle individual actions
    if action == "add":
        if not text or not text.strip():
            raise ValueError("Todo text cannot be empty for 'add' action")
        
        existing_todos = read_todos()
        text_normalized = text.strip().lower()
        
        # Check for duplicates (case-insensitive)
        for existing in existing_todos:
            if existing.get("content", "").strip().lower() == text_normalized:
                return {
                    "tool": "todowrite",
                    "success": True,
                    "output": existing_todos
                }
        
        new_todo = {
            "id": str(len(existing_todos) + 1),
            "content": text.strip(),
            "status": "pending"
        }
        existing_todos.append(new_todo)
        write_todos_to_db(existing_todos)
        
        return {
            "tool": "todowrite",
            "success": True,
            "output": existing_todos
        }
    
    elif action == "list":
        existing_todos = read_todos()
        stats = TodoStats(
            total=len(existing_todos),
            pending=len([t for t in existing_todos if t.get("status") == "pending"]),
            in_progress=len([t for t in existing_todos if t.get("status") == "in_progress"]),
            completed=len([t for t in existing_todos if t.get("status") == "completed"])
        )
        output = TodoWriteOutput(
            message=f"Found {len(existing_todos)} todos",
            stats=stats
        )
        return output.model_dump()
    
    elif action == "pop":
        existing_todos = read_todos()
        if not existing_todos:
            return {
                "tool": "todowrite",
                "success": False,
                "output": "No todos to remove."
            }
        
        existing_todos.pop(0)
        write_todos_to_db(existing_todos)
        
        return {
            "tool": "todowrite",
            "success": True,
            "output": existing_todos
        }
    
    elif action == "clear":
        write_todos_to_db([])
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
    
    else:
        raise ValueError(f"Unknown action: {action}. Available actions: add, list, pop, clear")


def get_function_declaration(client):
    """Get Gemini function declaration using from_callable().
    
    Args:
        client: Gemini client instance (required by from_callable)
        
    Returns:
        FunctionDeclaration object for this tool
    """
    if types is None:
        return None
    
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=manage_todos
    )


# Keep backward compatibility
def call(action: Union[str, list, dict] = "list", *args, **kwargs) -> Dict[str, Any]:
    """Call function for backward compatibility with manual execution."""
    # Handle direct list of todos
    if isinstance(action, list):
        return manage_todos(todos=action, merge=kwargs.get("merge", False))
    
    # Handle list passed as first argument
    if args and isinstance(args[0], list):
        return manage_todos(todos=args[0], merge=kwargs.get("merge", False))
    
    # Handle dict with todos key
    if args and isinstance(args[0], dict):
        obj = args[0]
        todos_arg = obj.get("todos")
        if isinstance(todos_arg, list):
            return manage_todos(todos=todos_arg, merge=obj.get("merge", False))
    
    # Handle individual actions
    action_str = action if isinstance(action, str) else "list"
    
    if action_str == "add":
        text = " ".join(args) if args else kwargs.get("text", "")
        return manage_todos(action="add", text=text)
    
    return manage_todos(
        action=action_str,
        text=kwargs.get("text"),
        todos=kwargs.get("todos"),
        merge=kwargs.get("merge", False)
    )
