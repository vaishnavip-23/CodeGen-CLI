# CodeGen CLI - Universal Coding Agent

A universal command-line coding agent that understands any codebase through natural language. Works with Python, JavaScript, Go, Rust, and other programming languages.

## 🚀 Features

- **Universal Compatibility**: Works with any codebase (Python, JS, Go, Rust, Java, C#, PHP, Ruby)
- **Smart Detection**: Automatically detects project type, package manager, and framework
- **Natural Language Interface**: Give commands in plain English
- **Language-Aware Tools**: Adapts tools based on detected project type
- **Safety First**: Built-in protections prevent accidental damage

## 📦 Installation

### From Source

```bash
git clone https://github.com/your-username/codegen-cli.git
cd codegen-cli
pip install -e .
```

### Direct Usage

```bash
git clone https://github.com/your-username/codegen-cli.git
cd codegen-cli
./codegen
```

## 🔧 Setup

1. **Set up environment variables**:

   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"

   # Get your API key from: https://aistudio.google.com/api-keys
   ```

2. **Navigate to your project**:
   ```bash
   cd /path/to/your/project
   codegen
   ```

## 💡 Usage

### Basic Commands

```bash
# Start the agent
codegen

# Get help (shows project-specific information)
help

# List files
ls

# Read a file
read main.py

# Search for code
grep "function_name"
```

### Natural Language Commands

```bash
# Analyze the codebase
analyze this project

# Run tests
run the test suite

# Format code
format all Python files

# Install dependencies
install project dependencies
```

## 🎯 Supported Languages

| Language   | Package Manager     | Framework Detection          |
| ---------- | ------------------- | ---------------------------- |
| Python     | pip, poetry, pipenv | Django, Flask, FastAPI       |
| JavaScript | npm, yarn           | React, Vue, Angular, Next.js |
| Go         | go modules          | Gin, Echo, Fiber             |
| Rust       | cargo               | Actix, Rocket                |
| Java       | maven, gradle       | Spring, Maven                |
| C#         | nuget               | .NET, ASP.NET                |

## 🛠️ Available Tools

### Universal Tools

- **File Operations**: read, write, edit, delete, list files
- **Search & Analysis**: grep, search, analyze codebase
- **Web Integration**: web search, fetch URLs
- **System Operations**: bash commands, project management

### Language-Specific Tools

- **Python**: pytest, black, flake8, mypy
- **JavaScript**: jest, eslint, prettier, webpack
- **Go**: go test, go build, go fmt
- **Rust**: cargo test, cargo build, cargo fmt

## 🔍 Project Detection

The agent automatically detects:

- **Language**: Based on characteristic files (package.json, requirements.txt, go.mod, etc.)
- **Package Manager**: pip, poetry, npm, yarn, cargo, etc.
- **Framework**: Django, React, Vue, Angular, etc.
- **File Extensions**: Relevant file types for the language

## 📁 File Filtering

Language-aware file filtering:

- **Python**: Ignores `__pycache__`, `.venv`, `build`, `dist`
- **JavaScript**: Ignores `node_modules`, `.next`, `dist`, `build`
- **Go**: Ignores `vendor`, `bin`
- **Rust**: Ignores `target`, `Cargo.lock`

## 🚀 Examples

### Python Project

```bash
$ codegen
🚀 CodeGen CLI - Universal Coding Agent
==================================================
Workspace: /path/to/python-project
Language: python
Package Manager: poetry
==================================================

>>> run tests
>>> format code
>>> check types
```

### JavaScript Project

```bash
$ codegen
🚀 CodeGen CLI - Universal Coding Agent
==================================================
Workspace: /path/to/js-project
Language: javascript
Package Manager: npm
==================================================

>>> run tests
>>> lint code
>>> build project
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by Cursor CLI and Claude Code
- Built with Google Gemini API
- Uses modular tool architecture for extensibility
