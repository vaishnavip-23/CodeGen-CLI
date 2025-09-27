"""
Exit Plan Mode Tool for CodeGen2

This tool saves plans to a file for external review and approval.
It's used when the AI needs to exit plan mode and save work for later.
"""

import os
import json
import uuid
from typing import Dict, Any, Optional

# Get workspace and database paths
WORKSPACE = os.getcwd()
DB_DIR = os.path.join(WORKSPACE, "db")

def ensure_database():
    """
    Ensure the database directory exists.
    """
    os.makedirs(DB_DIR, exist_ok=True)

def call(plan: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Save a plan to a file for external review.
    
    Args:
        plan: Plan string to save (can also be passed via kwargs)
        **kwargs: Additional arguments (plan can be passed here too)
        
    Returns:
        Dictionary with success status and plan information
    """
    # Get plan from arguments
    plan_text = plan or kwargs.get("plan")
    
    # Validate plan
    if not plan_text or not isinstance(plan_text, str):
        return {
            "tool": "exitplanmode",
            "success": False,
            "output": "Parameter 'plan' is required and must be a string.",
            "meta": {}
        }
    
    if not plan_text.strip():
        return {
            "tool": "exitplanmode",
            "success": False,
            "output": "Plan cannot be empty.",
            "meta": {}
        }
    
    try:
        # Ensure database directory exists
        ensure_database()
        
        # Generate unique plan ID
        plan_id = uuid.uuid4().hex[:8]
        
        # Create plan file path
        plan_file = os.path.join(DB_DIR, f"plan_{plan_id}.json")
        
        # Prepare plan data
        plan_data = {
            "id": plan_id,
            "plan": plan_text.strip(),
            "timestamp": str(uuid.uuid4().time_low),  # Simple timestamp
            "status": "pending_approval"
        }
        
        # Save plan to file
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)
        
        return {
            "tool": "exitplanmode",
            "success": True,
            "output": "Plan saved and awaiting approval.",
            "meta": {
                "plan_id": plan_id,
                "file_path": plan_file,
                "plan_length": len(plan_text)
            }
        }
        
    except Exception as e:
        return {
            "tool": "exitplanmode",
            "success": False,
            "output": f"Failed to save plan: {e}",
            "meta": {}
        }
