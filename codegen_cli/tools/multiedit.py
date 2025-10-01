import os
import tempfile
import shutil
from .edit import call as edit_call

def call(file_path=None, edits=None, *args, **kwargs):
    """
    Perform multiple edits on a single file atomically.
    
    Args:
        file_path: Path to the file to edit
        edits: List of edit dictionaries with old_string, new_string, replace_all
        
    Alternative call format:
        call(edits) where edits is a list and first item contains path
        
    Returns:
        Result dictionary with success status and details
    """
    # Handle different calling patterns
    if file_path is None and isinstance(edits, list) and edits:
        # Check if first edit contains path (legacy format)
        first_edit = edits[0]
        if isinstance(first_edit, dict) and "path" in first_edit:
            file_path = first_edit["path"]
            # Remove path from edits to avoid conflicts
            edits = [{k: v for k, v in edit.items() if k != "path"} for edit in edits]
    
    # Handle single argument case where it's a list of edit dicts with paths
    if file_path is None and isinstance(edits, list):
        results = []
        for i, edit_dict in enumerate(edits, 1):
            if not isinstance(edit_dict, dict):
                results.append({
                    "step": i, 
                    "success": False, 
                    "output": "Edit must be a dictionary"
                })
                continue
                
            path = edit_dict.get("path")
            old_str = edit_dict.get("old_string") or edit_dict.get("a")
            new_str = edit_dict.get("new_string") or edit_dict.get("b") 
            replace_all = edit_dict.get("replace_all", False)
            
            if not path:
                results.append({
                    "step": i,
                    "success": False, 
                    "output": "Missing path in edit"
                })
                continue
                
            result = edit_call(path, old_str, new_str, replace_all)
            results.append({
                "step": i,
                "path": path,
                "success": result.get("success", False),
                "output": result.get("output", "")
            })
            
            # Stop on first failure
            if not result.get("success"):
                return {"success": False, "output": results}
                
        return {"success": True, "output": results}
    
    # Validate inputs for single file multi-edit
    if not file_path:
        return {"success": False, "output": "file_path is required"}
        
    if not edits or not isinstance(edits, list):
        return {"success": False, "output": "edits must be a non-empty list"}
    
    # Check if file exists
    if not os.path.exists(file_path):
        return {"success": False, "output": f"File not found: {file_path}"}
    
    # Read original content
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            original_content = f.read()
    except Exception as e:
        return {"success": False, "output": f"Failed to read file: {e}"}
    
    # Create backup and working copy
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(original_content)
            temp_path = temp_file.name
    except Exception as e:
        return {"success": False, "output": f"Failed to create backup: {e}"}
    
    # Apply edits sequentially
    current_content = original_content
    applied_edits = []
    
    try:
        for i, edit_dict in enumerate(edits, 1):
            if not isinstance(edit_dict, dict):
                raise ValueError(f"Edit {i} must be a dictionary")
            
            old_str = edit_dict.get("old_string") or edit_dict.get("a")
            new_str = edit_dict.get("new_string") or edit_dict.get("b")
            replace_all = edit_dict.get("replace_all", False)
            
            if old_str is None or new_str is None:
                raise ValueError(f"Edit {i}: both old_string and new_string are required")
            
            if old_str not in current_content:
                raise ValueError(f"Edit {i}: text '{old_str}' not found in current content")
            
            # Apply the edit
            if replace_all:
                current_content = current_content.replace(old_str, new_str)
                count = original_content.count(old_str)
            else:
                current_content = current_content.replace(old_str, new_str, 1)
                count = 1
                
            applied_edits.append({
                "step": i,
                "old_string": old_str,
                "new_string": new_str,
                "replace_all": replace_all,
                "replacements": count
            })
    
    except Exception as e:
        # Restore from backup on failure
        try:
            os.unlink(temp_path)
        except:
            pass
        return {"success": False, "output": f"Edit failed: {e}"}
    
    # Write the final content
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(current_content)
        
        # Clean up backup
        os.unlink(temp_path)
        
        return {
            "success": True,
            "output": {
                "message": f"Applied {len(applied_edits)} edits to {file_path}",
                "edits": applied_edits,
                "file": file_path
            }
        }
        
    except Exception as e:
        # Restore from backup on write failure
        try:
            shutil.copy2(temp_path, file_path)
            os.unlink(temp_path)
        except:
            pass
        return {"success": False, "output": f"Failed to write changes: {e}"}
