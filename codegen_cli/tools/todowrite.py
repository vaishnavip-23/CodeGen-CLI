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

from ..models.schema import TodoWriteInput, TodoItem, TodoStats, TodoWriteOutput


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


def manage_todos(todos: List[TodoItem]) -> TodoWriteOutput:
    """Manage todo list for MODIFICATION tasks (8+ files).
    
    Use for tracking multi-file MODIFICATION tasks only. NEVER for analysis/reading.
    Creates or updates multiple todos at once (batch operations).
    
    Args:
        todos: List of TodoItem objects to create/update. Each todo must have content and status.
        
    Returns:
        TodoWriteOutput Pydantic model containing todo list or operation results and statistics.
    
    Example:
        manage_todos(todos=[
            TodoItem(id="1", content="Update file1.py", status="pending"),
            TodoItem(id="2", content="Update file2.py", status="pending")
        ])
    """
    # Validate using Pydantic model
    try:
        input_data = TodoWriteInput(todos=todos or [])
    except Exception as e:
        raise ValueError(f"Invalid input: {e}")
    
    if not input_data.todos:
        # If no todos provided, return current list
        existing_todos = read_todos()
        stats = TodoStats(
            total=len(existing_todos),
            pending=len([t for t in existing_todos if t.get("status") == "pending"]),
            in_progress=len([t for t in existing_todos if t.get("status") == "in_progress"]),
            completed=len([t for t in existing_todos if t.get("status") == "completed"])
        )
        todo_items = [TodoItem(**t) for t in existing_todos]
        return TodoWriteOutput(
            tool="todowrite",
            success=True,
            message=f"Found {len(existing_todos)} todos",
            stats=stats,
            todos=todo_items
        )
    
    # Convert TodoItem objects to dicts for storage
    todos_as_dicts = []
    for idx, todo_item in enumerate(input_data.todos):
        todo_dict = {
            "id": todo_item.id or str(idx + 1),
            "content": todo_item.content,
            "status": todo_item.status,
        }
        if todo_item.priority:
            todo_dict["priority"] = todo_item.priority
        todos_as_dicts.append(todo_dict)
    
    # Always merge by ID to avoid overwriting existing todos
    existing = read_todos()
    updated = _merge_by_id(existing, todos_as_dicts)
    write_todos_to_db(updated)
    
    return TodoWriteOutput(
        tool="todowrite",
        success=True,
        message=f"Updated {len(input_data.todos)} todos",
        count=len(input_data.todos)
    )


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
    
    # Helper to convert dict to TodoItem
    def dict_to_todo_item(d: Dict[str, Any], idx: int = 0) -> TodoItem:
        return TodoItem(
            id=d.get("id", str(idx + 1)),
            content=d.get("content", ""),
            status=d.get("status", "pending"),
            priority=d.get("priority")
        )
    
    # Handle direct list of todos (batch mode)
    if isinstance(action, list):
        todo_items = [dict_to_todo_item(t, i) if isinstance(t, dict) else t 
                     for i, t in enumerate(action)]
        result = manage_todos(todos=todo_items)
        return result.model_dump()
    
    # Handle list passed as first argument
    if args and isinstance(args[0], list):
        todo_items = [dict_to_todo_item(t, i) if isinstance(t, dict) else t 
                     for i, t in enumerate(args[0])]
        result = manage_todos(todos=todo_items)
        return result.model_dump()
    
    # Handle dict with todos key
    if args and isinstance(args[0], dict):
        obj = args[0]
        todos_arg = obj.get("todos")
        if isinstance(todos_arg, list):
            todo_items = [dict_to_todo_item(t, i) if isinstance(t, dict) else t 
                         for i, t in enumerate(todos_arg)]
            result = manage_todos(todos=todo_items)
            return result.model_dump()
    
    # Handle kwargs todos
    if kwargs.get("todos"):
        todos_arg = kwargs.get("todos")
        if isinstance(todos_arg, list):
            todo_items = [dict_to_todo_item(t, i) if isinstance(t, dict) else t 
                         for i, t in enumerate(todos_arg)]
            result = manage_todos(todos=todo_items)
            return result.model_dump()
    
    # Handle individual actions (convert to batch operations)
    action_str = action if isinstance(action, str) else "list"
    
    if action_str == "add":
        # Add a single todo
        text = " ".join(args) if args else kwargs.get("text", "")
        if not text:
            raise ValueError("Todo text cannot be empty for 'add' action")
        
        existing_todos = read_todos()
        new_todo = TodoItem(
            id=str(len(existing_todos) + 1),
            content=text.strip(),
            status="pending"
        )
        result = manage_todos(todos=[new_todo])
        return result.model_dump()
    
    elif action_str == "list":
        # List all todos (empty call)
        result = manage_todos(todos=[])
        return result.model_dump()
    
    elif action_str == "pop":
        # Remove first todo
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
            "output": "Removed first todo"
        }
    
    elif action_str == "clear":
        # Clear all todos
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
    
    # Default: list todos
    result = manage_todos(todos=[])
    return result.model_dump()
