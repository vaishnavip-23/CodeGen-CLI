# CodeGen-CLI - Universal Coding Agent

[![PyPI](https://img.shields.io/pypi/v/codegen-cli)](https://pypi.org/project/codegen-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful command-line coding agent with **iterative reasoning** capabilities, inspired by Claude Code and Cursor CLI, powered by Google Gemini API. Published on PyPI for easy installation and updates.

> Your expert developer assistant that understands any codebase, never gets tired, and continuously learns from results.

**BYOK (Bring Your Own Key)**: This tool requires you to provide your own Google Gemini API key. CodeGen-CLI does not include or provide API keys. You are responsible for obtaining a key and managing your API usage and costs.

## ✨ Key Features

### **Smart Understanding**
- **Conversation Memory**: Like Claude Code! Maintains context across tasks - understands "that file", "the comment", "that function" from previous interactions
- **Intelligent Explanations**: Ask "explain the codebase" and get comprehensive, structured analysis with:
  - Overview and main functionality
  - Tech stack breakdown (languages, frameworks, libraries)
  - Project structure and architecture
  - How components work together
- **Auto-detection**: Automatically detects project type and framework:
  - **Languages**: Python, JavaScript, TypeScript, Go, Rust, Java, and more
  - **Frameworks**: React, Vue, Next.js, Angular, Svelte
  - **Package Managers**: pip, poetry, npm, yarn, pnpm, cargo, etc.
  - **Nested Projects**: Finds configuration even in subdirectories (e.g., `my-app/package.json`)

###  **Agentic Loop**
- Iterative reasoning where agent sees results and adapts strategy
- Optimized for efficiency: 3-5 iterations for analysis, 2-4 for simple tasks
- Smart error recovery: learns from failures and tries alternative approaches

###  **Natural Conversations**
Multi-turn conversations without repeating context:
```
You: "create test.py with a hello function"
Agent: ✓ Created test.py

You: "add a docstring to that function"
Agent: ✓ [Knows you mean hello() in test.py]

You: "explain what this codebase does"
Agent: [Provides detailed, structured explanation with tech stack, architecture, etc.]
```

###  **12 Built-in Tools**
- **File operations**: read_file, write_file, edit_file, multi_edit, delete_file
- **Search & Discovery**: list_files (ls), find_files (glob), grep
- **Execution**: run_command (bash)
- **Task management**: manage_todos
- **Web helpers**: fetch_url, search_web

###  **Safety First**
- Previews edits before applying
- Filters risky folders (.env, secrets)
- Asks for confirmation before destructive actions
- Clear error messages with recovery suggestions

##  Requirements
- Python 3.10 or higher
- Google Gemini API key ([get one free](https://aistudio.google.com/api-keys))

##  Quick Start

### Installation

**Option 1: Install from PyPI (Recommended)**
```bash
pip install codegen-cli
```

**Option 2: Install with pipx (Isolated environment)**
```bash
pipx install codegen-cli
```

**Option 3: From source**
```bash
git clone https://github.com/vaishnavip-23/CodeGen-CLI.git
cd CodeGen-CLI
pip install -e .
```

### API Key Setup

Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/api-keys), then choose one of these methods:

**Method 1: Interactive Setup (Easiest)**
```bash
codegen --set-key YOUR_API_KEY
```
This saves the key to `~/.config/codegen/.env` so it's available for all projects.

**Method 2: Project-specific .env file**
Create a `.env` file in your project root:
```bash
GEMINI_API_KEY=your_api_key
```

**Method 3: Environment variable**
```bash
export GEMINI_API_KEY=your_api_key
```

> 💡 **Tip**: The agent auto-loads keys from `./.env`, `~/.env`, or `~/.config/codegen/.env`

### First Run

```bash
# Navigate to any project
cd /path/to/your/project

# Start the agent
codegen
```

You'll see a welcome screen with detected project info:
```
╭────────────────────────────────────────╮
│              WELCOME                   │
├────────────────────────────────────────┤
│ Workspace: /path/to/your/project      │
│ Language: javascript (react)           │
│ Package Manager: npm                   │
│ Gemini API key: set ✓                  │
╰────────────────────────────────────────╯
```

## 📖 Usage Examples

### Natural Language Interface
```bash
You: "explain the codebase"
Agent: [Provides detailed, structured analysis]

You: "find all TODO comments"
Agent: [Searches and lists all TODOs]

You: "create a new component called Header"
Agent: ✓ Created Header.jsx

You: "add PropTypes to that component"
Agent: ✓ [Knows you mean Header.jsx]
```

### Direct Tool Usage
```bash
You: "read README.md"
You: "grep 'import React'"
You: "list files"
You: "find **/*.test.js"
```

### Common Tasks
```bash
# Code analysis
"summarize the main.py file"
"explain how authentication works"
"find all API endpoints"

# Code generation
"create a login component with email and password fields"
"add error handling to the fetchData function"
"write unit tests for the utils module"

# Refactoring
"rename getUserData to fetchUserProfile across all files"
"update all console.log to use the logger"
"add TypeScript types to this file"
```

## 🎯 Commands

| Command | Description |
|---------|-------------|
| `help` | Show help information |
| `exit` or `Ctrl+C` | Exit the REPL |
| `codegen --version` | Show version |
| `codegen --check-update` | Check for updates |
| `codegen --set-key` | Save API key |

## License
This project uses the **MIT License**. See the `LICENSE` file for details.

*Inspired by Claude Code and Cursor CLI. Powered by Gemini.*