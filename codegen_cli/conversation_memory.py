"""
Conversation memory for maintaining context across tasks.

Stores recent tasks, file modifications, and important context to enable
natural multi-turn conversations like Claude Code.
"""

from dataclasses import dataclass, field
from typing import List, Any, Set
from collections import deque


@dataclass
class TaskMemory:
    """Memory of a single completed task."""
    user_request: str
    iterations: int
    completed: bool
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    summary: str = ""
    key_outcomes: List[str] = field(default_factory=list)


class ConversationMemory:
    """Maintains conversation context across multiple tasks."""
    
    def __init__(self, max_tasks: int = 10):
        """Initialize conversation memory.
        
        Args:
            max_tasks: Maximum number of recent tasks to remember
        """
        self.max_tasks = max_tasks
        self.tasks: deque[TaskMemory] = deque(maxlen=max_tasks)
        self.all_files_touched: Set[str] = set()
        
    def add_task(self, task: TaskMemory):
        """Add a completed task to memory."""
        self.tasks.append(task)
        self.all_files_touched.update(task.files_created)
        self.all_files_touched.update(task.files_modified)
    
    def get_recent_context(self, limit: int = 5) -> str:
        """Get formatted string of recent tasks for LLM context.
        
        Args:
            limit: Maximum number of recent tasks to include
            
        Returns:
            Formatted string describing recent conversation history
        """
        if not self.tasks:
            return ""
        
        recent_tasks = list(self.tasks)[-limit:]
        lines = ["## Previous Conversation (Recent Tasks)"]
        lines.append("This is our conversation history from earlier in this session:\n")
        
        for i, task in enumerate(recent_tasks, 1):
            lines.append(f"**Task {i}**: {task.user_request}")
            
            if task.files_created:
                lines.append(f"  - Created: {', '.join(task.files_created)}")
            
            if task.files_modified:
                lines.append(f"  - Modified: {', '.join(task.files_modified)}")
            
            if task.summary:
                lines.append(f"  - Result: {task.summary}")
            
            if task.key_outcomes:
                for outcome in task.key_outcomes:
                    lines.append(f"  - {outcome}")
            
            lines.append("")  # Blank line between tasks
        
        # Add summary of all touched files
        if self.all_files_touched:
            lines.append(f"**Files we've worked with this session**: {', '.join(sorted(self.all_files_touched))}")
        
        return "\n".join(lines)
    
    def extract_from_state(self, user_request: str, state: Any) -> TaskMemory:
        """Extract task memory from AgentState after task completion.
        
        Args:
            user_request: The original user request
            state: AgentState from completed task
            
        Returns:
            TaskMemory object with extracted information
        """
        files_created = []
        files_modified = []
        key_outcomes = []
        summary = ""
        
        # Extract from conversation history
        for item in state.conversation_history:
            if item.get("type") != "tool_result":
                continue
            
            result = item.get("result", {})
            if not isinstance(result, dict):
                continue
            
            tool = item.get("tool")
            
            # Track file operations
            if tool == "write_file":
                output = result.get("output", "")
                if "Wrote to" in output:
                    path = output.replace("Wrote to", "").strip()
                    files_created.append(path)
                    key_outcomes.append(f"Created {path}")
            
            elif tool == "edit_file":
                output = result.get("output", "")
                if "Edited" in output:
                    path = output.replace("Edited", "").split("(")[0].strip()
                    if path not in files_modified:
                        files_modified.append(path)
            
            elif tool == "multi_edit":
                output = result.get("output", [])
                if isinstance(output, list):
                    for step in output:
                        if isinstance(step, dict):
                            path = step.get("path", "")
                            if path and path not in files_modified:
                                files_modified.append(path)
            
            elif tool == "run_command":
                output = result.get("output", "")
                # Track directory creation
                if "mkdir" in user_request.lower() or "folder" in user_request.lower():
                    # Try to extract directory name from user request
                    words = user_request.split()
                    for word in words:
                        if word not in ["create", "make", "folder", "directory", "mkdir", "a", "the"]:
                            if "/" not in word and "." not in word:
                                key_outcomes.append(f"Created directory {word}")
                                break
            
            # Extract summary from task_complete
            elif tool == "task_complete":
                summary = result.get("output", "")
        
        return TaskMemory(
            user_request=user_request,
            iterations=state.iterations,
            completed=state.completed,
            files_created=files_created,
            files_modified=files_modified,
            summary=summary,
            key_outcomes=key_outcomes
        )
    
    def clear(self):
        """Clear all memory (for testing or reset)."""
        self.tasks.clear()
        self.all_files_touched.clear()
