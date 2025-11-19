# Changelog

All notable changes to CodeGen-CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2025-11-19

### 🎉 100% Pydantic Native Function Calling Compliance

This release achieves **100% compliance** with the Gemini API Pydantic Native Function Calling update**, implementing full Pydantic validation for both inputs and outputs across all 12 tools.

### Added - Pydantic Native Function Calling

#### **Full Input Validation** (12/12 tools)

- All tools now use Pydantic models for input validation
- Type-safe parameters with automatic validation
- Clear error messages for invalid inputs
- Validation happens before processing

#### **Pydantic Output Models** (12/12 tools)

- All tools return Pydantic models directly
- Automatic schema generation via `FunctionDeclaration.from_callable()`
- Type-safe outputs throughout the system
- Consistent model structure across all tools

#### **Updated Tool Signatures**

- `multi_edit`: Now uses `MultiEditInput` model with `MultiEditChange` objects
- `manage_todos`: Simplified to use `TodoWriteInput` model with `TodoItem` objects
- Both tools now have full Pydantic validation

### Changed

#### **Enhanced Schema Models**

- All 27 schema models defined in centralized `schema.py`
- Input models for all tools: `ReadInput`, `WriteInput`, `EditInput`, etc.
- Output models for all tools: `ReadOutput`, `WriteOutput`, `EditOutput`, etc.
- Complex nested models: `MultiEditChange`, `TodoItem`, `GrepMatch`, etc.

#### **Function Declaration Pattern**

```python
def get_function_declaration(client):
    return types.FunctionDeclaration.from_callable(
        client=client,
        callable=tool_function  # Gemini infers schema automatically
    )
```

#### **Backward Compatibility**

- `call()` functions maintained for legacy code
- Automatic conversion from dicts to Pydantic models
- All existing code continues to work without changes

### Technical Details

#### **All 12 Tools Updated:**

1. `read_file` - ReadInput → ReadOutput
2. `write_file` - WriteInput → WriteOutput
3. `edit_file` - EditInput → EditOutput
4. `delete_file` - DeleteInput → DeleteOutput
5. `run_command` - BashInput → BashOutput
6. `find_files` - GlobInput → GlobOutput
7. `grep` - GrepInput → Union[GrepOutputContent, GrepOutputFiles]
8. `list_files` - LsInput → LsOutput
9. `multi_edit` - MultiEditInput → MultiEditOutput ⭐ Updated
10. `manage_todos` - TodoWriteInput → TodoWriteOutput ⭐ Updated
11. `fetch_url` - WebFetchInput → WebFetchOutput
12. `search_web` - WebSearchInput → WebSearchOutput



### Benefits

- **Type Safety**: Full type checking throughout the system
- **Auto Schema**: Gemini generates function schemas automatically
- **Validation**: Input validation before processing prevents errors
- **Consistency**: Uniform pattern across all 12 tools
- **Compatibility**: Legacy code still works via `call()` functions
- **Future-Proof**: Aligned with latest Gemini API capabilities

### Performance

- Automatic schema generation reduces manual maintenance
- Type validation catches errors early
- Cleaner, more maintainable codebase
- Better IDE support with full type hints

### References

- **Documentation**: https://blog.google/technology/developers/gemini-api-structured-outputs/

---

## [0.4.0] - 2024-10-18

### 🎉 Major Intelligence & Transparency Upgrade

This release transforms CodeGen-CLI into a significantly smarter, more capable, and more transparent coding agent inspired by Claude Code and Cursor AI.

### Added - Intelligence Features

#### **Example-Driven Prompts** (40% token reduction)

- Rewrote agent prompts with concrete examples showing correct behavior
- Reduced token usage while improving output quality
- Agent learns from examples rather than abstract rules

#### **Chain-of-Thought Display**

- Agent now shows its reasoning: "💭 Need to find auth.py first..."
- Helps users understand what the agent is thinking
- Makes debugging and learning easier

#### **Self-Correction Loop**

- Stores failure context when tools fail
- Next prompt includes: what failed, why it failed, how to fix it
- Agent automatically tries alternative approaches
- Never repeats the same failing action

#### **Auto-Validation After Edits**

- Automatically checks Python syntax after file modifications
- Catches errors immediately before they cause problems
- Uses `python3 -m py_compile` for instant validation

#### **Smart Context Compression**

- Keeps first message + last 15 messages in conversation history
- Summarizes middle content to save tokens
- Maintains context while reducing API costs

#### **Tool Usage Statistics & Hints**

- Tracks success/failure rates for each tool
- Provides hints when tools consistently fail
- Example: "⚠️ edit_file has been failing - double-check arguments"

#### **Parallel Execution Support**

- Can use multiple tools in parallel when no dependencies exist
- Significantly faster for independent operations
- Smart dependency detection prevents conflicts

#### **Intent Detection - Explain vs Fix**

- Understands difference between "explain error" and "fix error"
- "explain" → Analyzes and describes the problem without changing files
- "fix" → Actually modifies code to resolve issues
- Prevents unwanted changes when you just want analysis

### Added - Transparency Features

#### **Show Bash Commands**

- Every command execution now displays: `→ run_command: python3 script.py`
- See exactly what the agent is running
- No hidden operations

#### **Show All Tool Arguments**

- All tool calls show their arguments: `→ find_files: pattern=**/*.py`
- `→ edit_file: old_code → new_code`
- Complete transparency in agent actions

#### **Enhanced Error Display**

- STDERR output shown prominently in red
- Exit codes color-coded (green=success, red=error)
- Clearer error messages with context

### Added - Completeness Features

#### **Iterative Fix-Validate Loop**

- Fixes ALL errors in files, not just the first one
- Pattern: Fix error #1 → Validate → Fix error #2 → Validate → Repeat
- Only completes when exit code = 0
- Python stops at first error, but agent keeps going until file is clean

#### **Context-Aware Pronouns**

- Understands "fix it", "repair that", "solve this" from conversation context
- Tracks recent tasks and files
- Natural conversation flow like Claude Code
- Example: "explain errors" → "fix it" (agent knows "it" = those errors)

### Changed

- Function calling now uses `mode='ANY'` for more reliable tool execution
- Prompt engineering completely rewritten with example-driven approach
- Output formatting enhanced with better color-coding and structure
- Agent state tracking improved with tool statistics

### Fixed

- Function calling reliability issues resolved
- Agent now correctly distinguishes between analysis and modification tasks
- Multi-error files now fully fixed instead of stopping at first error
- Context references properly resolved from conversation history

### Performance

- 40% reduction in prompt tokens through better engineering
- Faster execution through parallel tool usage
- Reduced API calls through smart context management

---

## [0.2.0] - 2024-10-04

### Added

- **Agentic Loop**: Iterative decision-making system for complex multi-step tasks
- **Automatic Todo Management**: Agent breaks down complex tasks into trackable subtasks
- **Conversation History**: LLM maintains context across iterations
- **Enhanced bash_command**: Full shell support (pipes, redirections, stderr capture)
- **Multi-tool Workflows**: Seamless chaining of multiple tools
- **Task Completion**: Proper completion with summary reporting

### Changed

- **Compact Output**: Removed boxes, cleaner terminal display
- **Improved Error Handling**: Better error messages and recovery
- **System Prompt**: Rewritten for agentic approach with iterative reasoning
- **Tool Integration**: All 11 tools tested and verified working

### Fixed

- bash_command now supports shell features (|, >, <, 2>&1, &&, ||)
- Conversation history properly maintained between iterations
- Todo tool parameter handling improved
- File operations (write, edit, delete) fully functional
- Syntax error detection and fixing workflow verified

### Security

- Command validation maintained even with shell=True mode
- Path validation for all file operations
- Confirmation prompts for destructive actions

## [0.1.0] - 2024-09-30

### Added

- Initial release
- Basic file operations (read, write, edit, delete)
- Search tools (grep, find, list)
- Bash command execution
- Web search and fetch capabilities
- Natural language REPL interface
- Multi-language support (Python, JS, Go, Rust, Java, etc.)

### Core Features

- 11 core tools for code manipulation
- Gemini API integration
- Safe file operations with workspace validation
- .gitignore awareness
- Todo list management

---

## Version History
- **v0.5.0** (Current): 100% Pydantic Native Function Calling compliance
- **v0.4.0**: Major intelligence & transparency upgrade
- **v0.2.0**: Agentic loop with iterative reasoning
- **v0.1.0** (Initial): Basic CLI agent with tool support
