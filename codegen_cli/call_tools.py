# File Summary: Tool calling with agentic loop for iterative execution.

"""
Tool calling and agentic loop for CodeGen CLI.

Implements iterative reasoning with Gemini function calling:
- Agent sees tool results before deciding next action
- Uses native Gemini function calling (no JSON parsing)
- Self-corrects on failures
- Maintains conversation history for context
"""

import os
import traceback
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from .tools_registry import get_all_function_declarations, get_tool_module


@dataclass
class AgentState:
    """Tracks the agent's state during execution."""
    goal: str
    iterations: int = 0
    max_iterations: int = 15
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    completed: bool = False
    error: Optional[str] = None
    working_memory: Dict[str, Any] = field(default_factory=dict)
    llm_messages: List[Any] = field(default_factory=list)  # Actual LLM conversation
    
    def add_observation(self, tool: str, result: Any):
        """Add a tool result to history."""
        self.conversation_history.append({
            "type": "tool_result",
            "tool": tool,
            "result": result,
            "iteration": self.iterations
        })
    
    def add_thought(self, thought: str):
        """Add agent's reasoning to history."""
        self.conversation_history.append({
            "type": "thought",
            "content": thought,
            "iteration": self.iterations
        })
    
    def get_recent_context(self, limit: int = 5) -> str:
        """Get recent history as formatted string."""
        recent = self.conversation_history[-limit:]
        lines = []
        for item in recent:
            if item["type"] == "thought":
                lines.append(f"Thought: {item['content']}")
            elif item["type"] == "tool_result":
                lines.append(f"Tool: {item['tool']}")
                lines.append(f"Result: {str(item['result'])[:200]}...")
        return "\n".join(lines)


class AgenticLoop:
    """Iterative agent that decides next action based on results."""
    
    def __init__(self, client, output_module=None):
        """Initialize the agentic loop.
        
        Args:
            client: Gemini API client
            output_module: Output module for printing results
        """
        self.client = client
        self.output = output_module
        
        # Get function declarations from all tools
        if types:
            self.function_declarations = get_all_function_declarations()
        else:
            self.function_declarations = []
    
    def _build_agent_prompt(self, state: AgentState) -> str:
        """Build prompt for next action decision."""
        prompt_parts = []
        
        prompt_parts.append(f"""You are an iterative coding agent. Your goal is:
{state.goal}

You will accomplish this by deciding ONE action at a time, seeing the result, and then deciding the next action.

IMPORTANT RULES:
1. **For multi-step tasks (3+ steps)**: FIRST use manage_todos to break down the task into a checklist
2. Choose ONE tool to call next (not a full plan)
3. Use discovery tools (list_files, find_files, grep) before making changes
4. Read files before editing them to understand context
5. **Update todos**: After completing each subtask, call manage_todos(action="pop") to mark it done
6. **When all todos are done**, call task_complete with your summary

**For analysis tasks** (summarize, explain, analyze, find):
- Create 3-5 todos for what to discover
- Gather information 
- Mark todos done as you go
- When all todos complete, call task_complete with your synthesized findings

**TODO WORKFLOW EXAMPLE**:
- Task: "Update version in setup.py"
- First: manage_todos(action="add", text="Find setup.py")
- Then: manage_todos(action="add", text="Read current version")
- Then: manage_todos(action="add", text="Update to new version")
- Do work, calling manage_todos(action="pop") after each step
- Finally: task_complete(summary="...")

Current progress: iteration {state.iterations}/{state.max_iterations}
""")
        
        # Add recent context if available
        if state.conversation_history:
            recent = state.get_recent_context(limit=5)
            prompt_parts.append(f"\nRecent history:\n{recent}")
        
        # Add working memory
        if state.working_memory:
            memory_str = "\n".join(f"- {k}: {v}" for k, v in state.working_memory.items())
            prompt_parts.append(f"\nWhat I know so far:\n{memory_str}")
        
        prompt_parts.append("\nWhat should I do next? Choose ONE tool to call.")
        
        return "\n".join(prompt_parts)
    
    def _call_llm_for_next_action(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Call LLM to decide next action using function calling."""
        
        try:
            # First iteration: send initial prompt
            if state.iterations == 1:
                prompt = self._build_agent_prompt(state)
                state.llm_messages = [prompt]
            
            # Call LLM with conversation history
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=state.llm_messages,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=self.function_declarations)],
                    temperature=0.1
                )
            )
            
            # Extract function call
            if not response.candidates:
                return None
            
            content = response.candidates[0].content
            
            # Add assistant response to conversation
            state.llm_messages.append(content)
            
            # Check for function call
            for part in content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    return {
                        "tool": fc.name,
                        "args": dict(fc.args) if fc.args else {}
                    }
                elif hasattr(part, 'text') and part.text:
                    # Agent provided reasoning
                    state.add_thought(part.text)
            
            return None
            
        except Exception as e:
            if self.output:
                self.output.print_error(f"LLM call failed: {e}\n{traceback.format_exc()}")
            return None
    
    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result."""
        if tool_name == "task_complete":
            return {
                "tool": "task_complete",
                "success": True,
                "output": args.get("summary", "Task completed"),
                "complete": True
            }
        
        try:
            # Get tool module and call its function
            module = get_tool_module(tool_name)
            
            # Extract positional args if needed (for backwards compat)
            # Most tools use kwargs now, but some may need positional
            result = module.call(**args)
            
            # Ensure result has required fields
            if not isinstance(result, dict):
                result = {"success": True, "output": result}
            
            result.setdefault("tool", tool_name)
            result.setdefault("success", True)
            
            return result
            
        except Exception as e:
            return {
                "tool": tool_name,
                "success": False,
                "output": f"Tool execution error: {e}\n{traceback.format_exc()}"
            }
    
    def _should_reflect(self, result: Dict[str, Any]) -> bool:
        """Decide if agent should reflect on result."""
        # Reflect on failures or surprising results
        if not result.get("success", False):
            return True
        return False
    
    def _reflection_prompt(self, tool_call: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Build reflection prompt."""
        return f"""The last action didn't work as expected:

Tool called: {tool_call.get('tool')}
Arguments: {tool_call.get('args')}
Result: {result}

What went wrong? What should I try instead?
Provide a brief analysis and suggest the next action."""
    
    def run(self, user_goal: str, max_iterations: int = 15) -> AgentState:
        """Run the agentic loop until task complete or max iterations.
        
        Args:
            user_goal: The user's natural language goal
            max_iterations: Maximum number of iterations
            
        Returns:
            Final AgentState with full history
        """
        state = AgentState(goal=user_goal, max_iterations=max_iterations)
        
        while state.iterations < state.max_iterations and not state.completed:
            state.iterations += 1
            
            if self.output:
                self.output.print_info(
                    f"Iteration {state.iterations}/{state.max_iterations}",
                    title="Agent Thinking"
                )
            
            # Get next action from LLM
            tool_call = self._call_llm_for_next_action(state)
            
            if tool_call is None:
                state.error = "No tool call returned from LLM"
                break
            
            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("args", {})
            
            if self.output:
                self.output.print_agent_action(f"{tool_name}")
            
            # Execute tool
            result = self._execute_tool(tool_name, tool_args)
            
            if self.output:
                self.output.print_tool_result(tool_name, result)
            
            # Add function response to LLM conversation
            output_str = str(result.get("output", ""))
            if len(output_str) > 2000:  # Truncate large outputs
                output_str = output_str[:2000] + "... (truncated)"
            
            function_response = types.Content(
                parts=[
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": output_str}
                    )
                ],
                role="user"
            )
            state.llm_messages.append(function_response)
            
            # Check if task complete
            if result.get("complete") or tool_name == "task_complete":
                state.completed = True
                state.add_observation(tool_name, result)
                break
            
            # Add to history
            state.add_observation(tool_name, result)
            
            # Update working memory with important info
            if tool_name == "grep" and result.get("success"):
                files = result.get("output", [])
                if isinstance(files, list) and files:
                    state.working_memory["files_found"] = [
                        f.get("file") if isinstance(f, dict) else f 
                        for f in files[:5]
                    ]
            
            # Reflection on failures
            if self._should_reflect(result):
                if self.output:
                    self.output.print_warning("Tool failed, agent will reflect and retry")
                
                # Give agent a chance to analyze and retry
                reflection_prompt = self._reflection_prompt(tool_call, result)
                state.add_thought(reflection_prompt)
        
        if state.iterations >= state.max_iterations and not state.completed:
            state.error = "Max iterations reached without completion"
        
        return state


def create_agentic_loop(client, output_module=None) -> AgenticLoop:
    """Factory function to create an agentic loop."""
    return AgenticLoop(client, output_module)
