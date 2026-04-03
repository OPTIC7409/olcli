# OLCLI — Claude Code-style AI Assistant for Ollama

```
  ██████╗ ██╗      ██████╗██╗     ██╗
 ██╔═══██╗██║     ██╔════╝██║     ██║
 ██║   ██║██║     ██║     ██║     ██║
 ██║   ██║██║     ██║     ██║     ██║
 ╚██████╔╝███████╗╚██████╗███████╗██║
  ╚═════╝ ╚══════╝ ╚═════╝╚══════╝╚═╝
```

**OLCLI** is a powerful, Claude Code-inspired terminal AI assistant that runs entirely locally via [Ollama](https://ollama.com). It features an interactive REPL, slash commands, built-in tools (file operations, shell execution, web search), and a full sub-agent system — all with a beautiful Rich terminal UI.

---

## Features

| Feature | Description |
|---|---|
| **Interactive REPL** | Persistent chat session with history, autocomplete, and streaming |
| **Slash Commands** | 30+ built-in commands for every workflow |
| **Built-in Tools** | File read/write/edit, shell exec, glob, grep, web search, diff |
| **Sub-Agent System** | 6 built-in agents + create custom agents via Markdown files |
| **Streaming** | Real-time token streaming with Rich markdown rendering |
| **Thinking Display** | Shows model reasoning (for models that support it) |
| **Session Management** | Save, load, compact, and export conversations |
| **Safe Mode** | Approval prompts before destructive tool calls |
| **One-shot Mode** | Run a single prompt or agent task from the command line |

---

## Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### Install from source

```bash
git clone https://github.com/yourname/olcli
cd olcli
pip install -e .
```

### Install dependencies only

```bash
pip install ollama rich prompt_toolkit pyyaml pydantic
```

---

## Quick Start

```bash
# Start Ollama (if not already running)
ollama serve

# Pull a model
ollama pull llama3.2

# Launch OLCLI
olcli

# Or with a specific model
olcli -m qwen2.5-coder:7b
```

---

## Slash Commands

### Conversation

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/clear` | Clear conversation history |
| `/new` | Start a fresh session |
| `/history [n]` | Show last N messages |
| `/compact [n]` | Keep only last N messages |
| `/export [file]` | Export conversation to Markdown |
| `/multiline` | Enter multi-line input mode (end with `.`) |

### Session & Config

| Command | Description |
|---|---|
| `/session` | Show session info (tokens, tool calls, etc.) |
| `/save [name]` | Save session to `~/.olcli/sessions/` |
| `/load [name]` | Load a saved session |
| `/model [name]` | List or switch models |
| `/config [key] [val]` | View or set configuration |
| `/system [prompt]` | View or set the system prompt |
| `/status` | Check Ollama connection |

### File Operations

| Command | Description |
|---|---|
| `/read <path>` | Read and display a file with syntax highlighting |
| `/write <path>` | Open a file in `$EDITOR` |
| `/ls [path]` | List directory contents |
| `/grep <pattern> [path]` | Search files for a regex pattern |
| `/diff <file_a> <file_b>` | Show unified diff between files |
| `/cd [path]` | Change working directory |
| `/pwd` | Print working directory |

### Shell & Search

| Command | Description |
|---|---|
| `/run <command>` | Run a shell command (alias: `!<command>`) |
| `/search <query>` | Search the web via DuckDuckGo |

### Agents & Tools

| Command | Description |
|---|---|
| `/agents` | List all available agents |
| `/agents run <name> <task>` | Run a sub-agent on a task |
| `/agents new` | Create a new agent interactively |
| `/agents show <name>` | Show agent details |
| `/agents delete <name>` | Delete a custom agent |
| `/tools` | List all available tools |
| `/safe` | Toggle safe mode (approval prompts) |
| `/approve` | Toggle auto-approve for tools |
| `/think` | Toggle thinking display |

---

## Sub-Agent System

OLCLI includes 6 built-in specialized agents:

| Agent | Color | Purpose |
|---|---|---|
| `explorer` | Blue | Read-only codebase search and analysis |
| `coder` | Green | Write, edit, and refactor code |
| `researcher` | Yellow | Web research and documentation lookup |
| `reviewer` | Magenta | Code review and quality analysis |
| `debugger` | Red | Diagnose errors and fix bugs |
| `shell` | Cyan | Shell commands and system operations |

### Running an Agent

```
# In the REPL:
/agents run coder implement a binary search function in Python

# From the command line:
olcli --agent coder "implement a binary search function in Python"
```

### Creating a Custom Agent

Agents are Markdown files with YAML frontmatter. Create one interactively:

```
/agents new
```

Or create a file manually at `~/.olcli/agents/my-agent.md` or `.olcli/agents/my-agent.md`:

```markdown
---
name: my-agent
description: A specialized agent for data analysis tasks
model: llama3.2
tools:
  - read_file
  - run_shell
  - write_file
max_turns: 30
memory: false
color: yellow
scope: user
---

You are a data analysis expert. You analyze datasets, generate statistics,
create visualizations, and provide insights. You prefer Python with pandas
and matplotlib.
```

---

## Built-in Tools

| Tool | Approval | Description |
|---|---|---|
| `read_file` | Auto | Read file contents (with optional line range) |
| `write_file` | Required | Write or append to a file |
| `edit_file` | Required | Replace specific text in a file |
| `list_files` | Auto | List directory contents |
| `glob_files` | Auto | Find files by glob pattern |
| `grep_files` | Auto | Search files by regex pattern |
| `run_shell` | Required | Execute shell commands |
| `web_search` | Auto | Search the web via DuckDuckGo |
| `diff_files` | Auto | Show diff between files or text |
| `get_file_info` | Auto | Get file metadata |
| `delete_file` | Required | Delete a file |
| `move_file` | Required | Move or rename a file |
| `make_directory` | Required | Create directories |

---

## Configuration

Config is stored at `~/.olcli/config.json`.

```bash
# View all config
/config

# Set a value
/config model llama3.2
/config temperature 0.5
/config stream true
/config safe_mode false
/config max_tool_iterations 30
```

| Key | Default | Description |
|---|---|---|
| `model` | `llama3.2` | Default Ollama model |
| `host` | `http://localhost:11434` | Ollama server URL |
| `temperature` | `0.7` | Model temperature |
| `context_length` | `8192` | Context window size |
| `stream` | `true` | Enable streaming |
| `safe_mode` | `true` | Require approval for destructive tools |
| `auto_approve_tools` | `false` | Skip all approval prompts |
| `show_thinking` | `true` | Show model thinking tokens |
| `max_tool_iterations` | `20` | Max tool call loop iterations |
| `theme` | `monokai` | Syntax highlighting theme |

---

## Command-Line Usage

```bash
# Interactive REPL
olcli

# Specify model
olcli -m qwen2.5-coder:7b

# One-shot prompt
olcli -p "explain async/await in Python"

# Run a specific agent
olcli --agent coder "add type hints to all functions in main.py"

# List models
olcli --list-models

# List agents
olcli --list-agents

# Disable tools
olcli --no-tools

# Disable approval prompts
olcli --safe-off
```

---

## Directory Structure

```
~/.olcli/
├── config.json          # Global configuration
├── history              # REPL input history
├── agents/              # User-level agent definitions
│   └── my-agent.md
├── sessions/            # Saved sessions
│   └── session-*.json
└── memory/              # Agent memory (future)

.olcli/                  # Project-level (in your project dir)
├── agents/              # Project-specific agents
└── commands/            # Project-specific commands (future)
```

---

## Tips & Tricks

**Use `!` as a shortcut for shell commands:**
```
! git status
! npm test
! python -m pytest
```

**Multi-line input:**
```
/multiline
Write a function that...
takes a list of numbers...
and returns the sorted unique values.
.
```

**Chain agents with context:**
The main assistant automatically delegates to sub-agents based on your request. You can also invoke them explicitly with `/agents run`.

**Save context when working on large projects:**
```
/compact 20    # Keep only last 20 messages
```

---

## License

MIT License — use freely, modify as needed.
