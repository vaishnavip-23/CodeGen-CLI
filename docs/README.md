# CodeGen-CLI Documentation

A powerful command-line coding agent with **iterative reasoning** capabilities, inspired by Claude Code and Cursor CLI, powered by Google Gemini API.

> Your expert developer assistant that understands any codebase, never gets tired, and continuously learns from results.

## Overview

CodeGen-CLI is a universal coding agent that works with any programming language or framework. It features:

- 🧠 **Intelligent code understanding** with structured explanations
- 🔄 **Iterative reasoning** that learns from results and adapts
- 💬 **Conversation memory** like Claude Code
- 🎯 **Auto-detection** of languages, frameworks, and package managers
- 🛡️ **Safety-first** approach with confirmations and previews

**BYOK (Bring Your Own Key)**: This tool requires you to provide your own Google Gemini API key. CodeGen-CLI does not include or provide API keys.

## Requirements
- Python 3.10 or higher
- Google Gemini API key ([get one free](https://aistudio.google.com/api-keys))

## Key Features

### Smart Understanding
- **Conversation Memory**: Maintains context across tasks - understands "that file", "the comment", "that function" from previous interactions
- **Intelligent Explanations**: Ask "explain the codebase" and get comprehensive analysis including:
  - Overview and main functionality
  - Tech stack breakdown (languages, frameworks, libraries)
  - Project structure and architecture
  - How components work together
- **Auto-detection**: Detects project type and framework automatically:
  - **Languages**: Python, JavaScript, TypeScript, Go, Rust, Java, and more
  - **Frameworks**: React, Vue, Next.js, Angular, Svelte
  - **Package Managers**: pip, poetry, npm, yarn, pnpm, cargo
  - **Nested Projects**: Finds configuration even in subdirectories

### Agentic Loop
- Iterative reasoning where agent sees results and adapts strategy
- Optimized for efficiency: 3-5 iterations for analysis, 2-4 for simple tasks
- Smart error recovery: learns from failures and tries alternative approaches

### Natural Conversations
Multi-turn conversations without repeating context:
```
You: "create test.py with a hello function"
Agent: ✓ Created test.py

You: "add a docstring to that function"
Agent: ✓ [Knows you mean hello() in test.py]

You: "explain what this codebase does"
Agent: [Provides detailed, structured explanation]
```

### Built-in Tools
- **File operations**: read_file, write_file, edit_file, multi_edit, delete_file
- **Search & Discovery**: list_files (ls), find_files (glob), grep
- **Execution**: run_command (bash)
- **Task management**: manage_todos
- **Web helpers**: fetch_url, search_web

### Safety First
- Previews edits before applying
- Filters risky folders (.env, secrets)
- Asks for confirmation before destructive actions
- Clear error messages with recovery suggestions

## API and Installation Guide
Get a Gemini API key from Google AI Studio and choose one of the following options
### Option 1: Use the --set-key command 
```bash
codegen --set-key YOUR_API_KEY
```
This saves the key to `~/.config/codegen/.env` so it's available for all projects.

### Option 2: Project .env file
Create a `.env` file in your project root:
```bash
GEMINI_API_KEY=your_api_key
```
> There's a `.env.example` file for your reference in the project root. Make sure to add `.env` to your `.gitignore` file!

You can use the agent in both ways:
1. Package (PyPI) — users can install and run the published package:
```bash
pip install codegen-cli
codegen
```
2. Local (from source) — users can clone the repo and run it locally:
```bash
git clone https://github.com/vaishnavip-23/CodeGen-CLI.git
cd codegen-cli
python -m codegen_cli.main
```
Or run directly with uv:
```bash 
uv run -m codegen_cli.main
```
## How to Use
Once in the REPL, you can:
- Use natural language: "find all functions named test_*"
- Use tool names directly: "read README.md", "grep 'TODO'"
- Ask for help: Type "help" for guidance
- Exit: Press Ctrl+C or Ctrl+D to exit

## License
This project uses the **MIT License**. See the `LICENSE` file for details.

*Inspired by Claude Code and Cursor CLI. Powered by Gemini.*