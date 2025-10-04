# CodeGen-CLI - Coding Agent
[CodeGen-CLI PyPI Package](https://pypi.org/project/codegen-cli/)

A powerful command-line coding agent with **iterative reasoning** capabilities, inspired by Claude Code and Cursor CLI, powered by Google Gemini API. Published on PyPI for easy installation and updates.

> Think of it as an expert developer assistant that never gets tired.

**BYOK (Bring Your Own Key)**: This tool requires you to provide your own Google Gemini API key. CodeGen-CLI does not include or provide API keys. You are responsible for obtaining a key and managing your API usage and costs.

## Requirements
- Python 3.10 or higher
- Google Gemini API key (get one at https://aistudio.google.com/api-keys)

## Key features
- **Agentic Loop**: Iterative reasoning where agent sees results and adapts strategy for decision making
- **Natural language REPL**: Ask questions in plain English
- **Auto-detection**: Automatically detects project type (Python, JS, Go, Rust, Java, C#, PHP, Ruby) and package managers (pip, poetry, npm, yarn, cargo, etc.)
- **12 Built-in Tools**:
  - File operations: read_file, write_file, edit_file, multi_edit, delete_file
  - Search tools: list_files (ls), find_files (glob), grep
  - Execution: run_command (bash)
  - Task management: manage_todos
  - Web helpers: fetch_url, search_web
- **Safety-first**: Previews edits, filters risky folders (.env), and asks for confirmation before destructive actions

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