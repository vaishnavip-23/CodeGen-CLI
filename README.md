# CodeGen-CLI - Coding Agent

Version 0.2.0 | [PyPI Package](https://pypi.org/project/codegen-cli/)

A powerful command-line coding agent with **iterative reasoning** capabilities, inspired by Claude Code and Cursor CLI, powered by Google Gemini API. Published on PyPI for easy installation and updates. 

> Think of it as an expert developer assistant that never gets tired.


## What is CodeGen-CLI?
CodeGen-CLI is a small, easy-to-use agent that helps you explore and work with codebases using plain English. Instead of remembering many commands, you can ask the tool to find, read, or change code for you.

**BYOK (Bring Your Own Key)**: This tool requires you to provide your own Google Gemini API key. CodeGen-CLI does not include or provide API keys. You are responsible for obtaining a key and managing your API usage and costs.

## Requirements
- Python 3.10 or higher
- Google Gemini API key (get one at https://aistudio.google.com/api-keys)

## Key features
- **Agentic Loop**: Iterative reasoning where agent sees results and adapts strategy
- **Natural language REPL**: Ask questions in plain English
- **Auto-detection**: Automatically detects project type (Python, JS, Go, Rust, Java, C#, PHP, Ruby) and package managers (pip, poetry, npm, yarn, cargo, etc.)
- **12 Built-in Tools**:
  - File operations: read_file, write_file, edit_file, multi_edit, delete_file
  - Search tools: list_files (ls), find_files (glob), grep
  - Execution: run_command (bash)
  - Task management: manage_todos
  - Web helpers: fetch_url, search_web
- **Safety-first**: Previews edits, filters risky folders (.env), and asks for confirmation before destructive actions

## Installation

### From PyPI (Recommended)
```bash
pip install codegen-cli
```

### From Source
```bash
git clone https://github.com/vaishnavip-23/CodeGen-CLI.git
cd CodeGen-CLI
pip install -e .
```

Or run directly with uv:
```bash
uv run -m codegen_cli.main
```

## API Key Setup (BYOK - Bring Your Own Key)

CodeGen-CLI requires you to provide your own Google Gemini API key. The tool does not include API access.

**Get your free API key**: Visit https://aistudio.google.com/api-keys to create your key. Google offers a free tier to get started.

> **Note**: You are responsible for your API usage and any associated costs. Review Google's pricing at https://ai.google.dev/pricing

### Option 1: Use the --set-key command (Recommended)
```bash
codegen --set-key YOUR_API_KEY
```
This saves the key to `~/.config/codegen/.env` so it's available for all projects.

### Option 2: Environment variable
```bash
export GEMINI_API_KEY=your_api_key
```

### Option 3: Project .env file
Create a `.env` file in your project root:
```bash
GEMINI_API_KEY=your_api_key
```
> Make sure to add `.env` to your `.gitignore` file!

The tool searches for API keys in this order:
1. Current environment variables
2. Project `.env` file (current directory)
3. User `.env` file (`~/.env`)
4. Config `.env` file (`~/.config/codegen/.env`)

## Quick Start

1. Install and set up your API key:
```bash
pip install codegen-cli
codegen --set-key YOUR_API_KEY
```

2. Navigate to your project and run:
```bash
cd your-project
codegen
```

3. Start coding with natural language:
```text
help
list files in src/
read main.py
find all TODO comments
add type hints to all functions in utils.py
```

## How to Use

Once in the REPL, you can:
- Use natural language: "find all functions named test_*"
- Use tool names directly: "read README.md", "grep 'TODO'"
- Ask for help: Type "help" for guidance
- Exit: Press Ctrl+C or Ctrl+D to exit

## What's New in v0.2.0

- **Agentic Loop**: Iterative decision-making system for complex multi-step tasks
- **Automatic Todo Management**: Agent breaks down complex tasks into trackable subtasks
- **Conversation History**: LLM maintains context across iterations
- **Enhanced bash_command**: Full shell support (pipes, redirections, stderr capture)
- **Multi-tool Workflows**: Seamless chaining of multiple tools

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## License
This project uses the **MIT License**. See the `LICENSE` file for details.

*Inspired by Claude Code and Cursor CLI. Powered by Gemini.*