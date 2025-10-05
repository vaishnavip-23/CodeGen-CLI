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
    
    # Model fallback order - OPTIMIZED FOR COST + RATE LIMITS
    # Total capacity: 10,000 RPM across first 3 models before hitting expensive ones!
    MODEL_FALLBACK_ORDER = [
        "gemini-2.0-flash-lite",     # PRIMARY: Cheapest! $0.075/$0.30, 4000 RPM, 4M TPM, unlimited RPD
        "gemini-2.5-flash-lite",     # FALLBACK 1: $0.10/$0.40, 4000 RPM, 4M TPM, unlimited RPD
        "gemini-2.0-flash",          # FALLBACK 2: $0.10/$0.40, 2000 RPM, 4M TPM, unlimited RPD (more capacity!)
        "gemini-2.5-flash",          # FALLBACK 3: Expensive! $0.30/$2.50, 1000 RPM, 1M TPM, 10K RPD
        "gemini-2.5-pro"             # LAST RESORT: Very expensive! $1.25/$10.00, 150 RPM, 2M TPM, 10K RPD
    ]
    
    def __init__(self, client, output_module=None, conversation_memory=None):
        """Initialize the agentic loop.
        
        Args:
            client: Gemini API client
            output_module: Output module for printing results
            conversation_memory: ConversationMemory instance for cross-task context
        """
        self.client = client
        self.output = output_module
        self.current_model_index = 0  # Track which model we're using
        self.conversation_memory = conversation_memory
        
        # Get function declarations from all tools
        if types:
            self.function_declarations = get_all_function_declarations()
        else:
            self.function_declarations = []
    
    def _extract_retry_time(self, error_str: str) -> Optional[str]:
        """Extract retry time from error message."""
        import re
        # Look for patterns like "retry in 17.686472071s" or "retry in 17s"
        match = re.search(r'retry in (\d+(?:\.\d+)?)\s*s', error_str.lower())
        if match:
            seconds = float(match.group(1))
            if seconds < 60:
                return f"{int(seconds)} seconds"
            else:
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''}"
        return None
    
    def _build_agent_prompt(self, state: AgentState) -> str:
        """Build prompt for next action decision."""
        prompt_parts = []
        
        # Add conversation memory if available (cross-task context)
        if self.conversation_memory:
            context = self.conversation_memory.get_recent_context(limit=5)
            if context:
                prompt_parts.append(context)
                prompt_parts.append("\n---\n")
        
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

**IMPORTANT - USE CONVERSATION MEMORY**:
- When the user says "that file", "the comment", "that function" - refer to the conversation history above
- If we just created/modified a file, subsequent vague references likely refer to that file
- Use context clues from previous tasks to understand ambiguous requests

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
        """Call LLM to decide next action using function calling with model fallback and retries."""
        
        # First iteration: send initial prompt
        if state.iterations == 1:
            prompt = self._build_agent_prompt(state)
            state.llm_messages = [prompt]
        
        # AGGRESSIVE token optimization: Trim conversation history early
        # Keep only last 6 exchanges (12 messages) to minimize token usage
        if len(state.llm_messages) > 12:
            state.llm_messages = state.llm_messages[:1] + state.llm_messages[-11:]
        
        # Try models in fallback order
        for model_index in range(self.current_model_index, len(self.MODEL_FALLBACK_ORDER)):
            model = self.MODEL_FALLBACK_ORDER[model_index]
            
            # Retry logic for transient failures (empty responses, etc.)
            max_retries = 3
            for retry_attempt in range(max_retries):
                try:
                    # Call LLM with conversation history
                    response = self.client.models.generate_content(
                        model=model,
                        contents=state.llm_messages,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(function_declarations=self.function_declarations)],
                            temperature=0.1
                        )
                    )
                    
                    # Success - update current model if we switched
                    if model_index != self.current_model_index:
                        old_model = self.MODEL_FALLBACK_ORDER[self.current_model_index]
                        self.current_model_index = model_index
                        if self.output:
                            self.output.print_warning(
                                f"Switched to backup model due to rate limits",
                                title="Model Fallback"
                            )
                    
                    # Extract function call
                    if not response.candidates:
                        if retry_attempt < max_retries - 1:
                            import time
                            time.sleep(0.5 * (retry_attempt + 1))  # Exponential backoff
                            continue
                        return None
                    
                    content = response.candidates[0].content
                    
                    # Check if content is None (can happen with safety filters or empty responses)
                    if content is None or not hasattr(content, 'parts') or content.parts is None:
                        if retry_attempt < max_retries - 1:
                            if self.output and retry_attempt == 0:
                                self.output.print_warning("Empty response from model, retrying...")
                            import time
                            time.sleep(0.5 * (retry_attempt + 1))  # Exponential backoff
                            continue
                        # After all retries, might be rate limit in disguise
                        if self.output:
                            self.output.print_warning("Persistent empty responses, might be rate limited")
                        return None
                    
                    # Check for function calls BEFORE adding to conversation
                    # Gemini can return MULTIPLE function calls in parallel!
                    function_calls = []
                    
                    for part in content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            function_calls.append({
                                "tool": fc.name,
                                "args": dict(fc.args) if fc.args else {}
                            })
                        elif hasattr(part, 'text') and part.text:
                            # Agent provided reasoning
                            state.add_thought(part.text)
                    
                    # Only add to conversation if we found function call(s)
                    if function_calls:
                        state.llm_messages.append(content)
                        return function_calls
                    
                    # No function call found - retry or return None
                    if retry_attempt < max_retries - 1:
                        if self.output:
                            self.output.print_warning("No function call in response, retrying...")
                        import time
                        time.sleep(0.5 * (retry_attempt + 1))
                        continue
                    return None
                    
                except Exception as e:
                    error_str = str(e).lower()
                    # Check if it's a rate limit error
                    if any(x in error_str for x in ["rate limit", "quota", "429", "resource exhausted"]):
                        if model_index < len(self.MODEL_FALLBACK_ORDER) - 1:
                            # Try next model
                            if self.output:
                                self.output.print_warning(
                                    f"Rate limit reached, trying backup model...",
                                    title="Rate Limit"
                                )
                            break  # Break retry loop, continue to next model
                        else:
                            # No more fallbacks - extract retry time if available
                            retry_time = self._extract_retry_time(str(e))
                            if self.output:
                                msg = "⚠️  Rate limit exceeded: All 5 models exhausted (10,000+ RPM tried!)"
                                if retry_time:
                                    msg += f"\n⏳ Please retry in {retry_time}"
                                msg += "\n💡 Tier 1 with 5-model fallback - this is extremely rare!"
                                self.output.print_error(msg)
                            return None
                    else:
                        # Check if it's the function call/response mismatch error
                        if "function response parts" in error_str or "function call parts" in error_str:
                            # Conversation history is corrupted, reset it
                            if self.output:
                                self.output.print_warning("Conversation history corrupted, resetting...")
                            # Keep only the initial system prompt
                            if len(state.llm_messages) > 0:
                                state.llm_messages = state.llm_messages[:1]
                            # Rebuild prompt with current state
                            prompt = self._build_agent_prompt(state)
                            state.llm_messages = [prompt]
                            # Retry with fresh conversation
                            if retry_attempt < max_retries - 1:
                                import time
                                time.sleep(0.5)
                                continue
                            return None
                        
                        # Non-rate-limit error - retry if attempts left
                        if retry_attempt < max_retries - 1:
                            if self.output:
                                self.output.print_warning(f"Transient error, retrying... ({e})")
                            import time
                            time.sleep(1.0 * (retry_attempt + 1))
                            continue
                        # After all retries
                        if self.output:
                            self.output.print_error(f"LLM call failed after {max_retries} attempts: {e}")
                        return None
        
        # Should never reach here
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
            
            # Get next action(s) from LLM - can return multiple parallel calls!
            tool_calls = self._call_llm_for_next_action(state)
            
            if tool_calls is None:
                state.error = "No tool call returned from LLM"
                break
            
            # Gemini can return multiple function calls in parallel
            # Execute all of them in this iteration
            function_response_parts = []
            task_completed = False
            
            for idx, tool_call in enumerate(tool_calls, 1):
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("args", {})
                
                if self.output:
                    if len(tool_calls) > 1:
                        self.output.print_agent_action(f"{tool_name} (parallel batch {idx}/{len(tool_calls)})")
                    else:
                        self.output.print_agent_action(f"{tool_name}")
                
                # Execute tool
                result = self._execute_tool(tool_name, tool_args)
                
                if self.output:
                    self.output.print_tool_result(tool_name, result)
                
                # AGGRESSIVE truncation to save tokens and costs
                output_str = str(result.get("output", ""))
                if len(output_str) > 800:  # Strict limit: 800 chars max
                    output_str = output_str[:800] + f"... (truncated {len(output_str)-800} chars)"
                
                # Add function response part
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": output_str}
                    )
                )
                
                # Check if task complete
                if result.get("complete") or tool_name == "task_complete":
                    task_completed = True
                
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
            
            # Add all function responses to conversation in one message
            if function_response_parts:
                function_response = types.Content(
                    parts=function_response_parts,
                    role="user"
                )
                state.llm_messages.append(function_response)
            
            # Check if any tool completed the task
            if task_completed:
                state.completed = True
                break
        
        if state.iterations >= state.max_iterations and not state.completed:
            state.error = "Max iterations reached without completion"
        
        return state


def create_agentic_loop(client, output_module=None, conversation_memory=None) -> AgenticLoop:
    """Factory function to create an agentic loop."""
    return AgenticLoop(client, output_module, conversation_memory)
