# CodeGen-CLI - Coding Agent
A simple command-line coding agent inspired by Claude Code and Cursor CLI, and powered by Google Gemini API. Published on PyPI for easy installation and updates.
> Think of it as an expert developer assistant that never gets tired.

1. [CodeGen-CLI PyPI Package](https://pypi.org/project/codegen-cli/)


## What is CodeGen-CLI?
CodeGen-CLI is a small, easy-to-use agent that helps you explore and work with codebases using plain English. Instead of remembering many commands, you can ask the tool to find, read, or change code for you.

## Key features
- **Natural language REPL**: Ask questions in plain English.
- **Multi-language support**: Works with Python, JS, Go, Rust, Java, C#, PHP, Ruby.
- **File tools**: read, write, edit, multiedit, delete.
- **Search tools**: ls, glob, grep.
- **Web helpers**: simple web search and fetch for documentation/examples.
- **Safety-first**: previews edits, filters risky folders (.env), and asks for confirmation before destructive actions.

## Quick start
Get a Gemini API key from Google AI Studio and store it in your codebase root:
> Make sure you add the API key to your gitignore file.
```bash
GEMINI_API_KEY=your_api_key
```
Locally and packaged, users can use it both ways:
1. Package (PyPI) — users can install and run the published package:
```bash
pip install codegen-cli
codegen
```
2. Local (from source) — users can clone the repo and run it locally:
```bash
git clone https://github.com/vaishnavip-23/CodeGen-CLI.git
cd codegen-cli
uv run -m codegen_cli.cli 
```
If uv run -m is not available in your environment, you can use 
```bash 
python -m codegen_cli.cli 
```

## Usage Examples

🚀 CodeGen CLI - Quick Demo

- Workspace: path/to/workspace
- Language: python
- Package Manager: poetry
- Gemini API key: set
- Type 'help' for help. Try natural language like 'summarize the repo'.
- Non-destructive steps run immediately. Destructive steps require confirmation.

```text
help
ls
read README.md
grep "def my_function"
can you create a file called hello.py with the hello world code
```

## License
This project uses the **MIT License**. See the `LICENSE` file for details.

*Inspired by Claude Code and Cursor CLI. Powered by Gemini.*


