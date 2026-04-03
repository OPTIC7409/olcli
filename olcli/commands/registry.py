"""
OLCLI Slash Commands Registry
All built-in /commands and the framework for custom commands.
"""

import os
import sys
import json
import time
import uuid
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..repl import REPL


# ── Command Definition ────────────────────────────────────────────────────────
class Command:
    def __init__(self, name: str, description: str, usage: str,
                 handler: Callable, aliases: list = None, example: str = ""):
        self.name = name
        self.description = description
        self.usage = usage
        self.handler = handler
        self.aliases = aliases or []
        self.example = example

    def matches(self, cmd: str) -> bool:
        return cmd == self.name or cmd in self.aliases


# ── Command Registry ──────────────────────────────────────────────────────────
class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command):
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def list_unique(self) -> list[Command]:
        seen = set()
        result = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return sorted(result, key=lambda c: c.name)

    def execute(self, repl: "REPL", raw: str) -> bool:
        """Parse and execute a slash command. Returns True if handled."""
        parts = raw.strip().split(None, 1)
        cmd_name = parts[0].lstrip("/").lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self.get(cmd_name)
        if cmd:
            cmd.handler(repl, args)
            return True
        return False

    def get_display_name(self, cmd: "Command") -> str:
        return f"/{cmd.name}"


# ── Built-in Command Handlers ─────────────────────────────────────────────────

def cmd_help(repl: "REPL", args: str):
    cmds = [
        {
            "name": f"/{c.name}",
            "description": c.description,
            "example": c.example,
        }
        for c in repl.commands.list_unique()
    ]
    repl.ui.print_help(cmds)



def cmd_exit(repl: "REPL", args: str):
    repl.ui.print_info("Goodbye!")
    repl.running = False


def cmd_clear(repl: "REPL", args: str):
    repl.session.clear()
    repl.ui.print_success("Conversation history cleared.")


def cmd_cls(repl: "REPL", args: str):
    repl.ui.clear()


def cmd_model(repl: "REPL", args: str):
    args = args.strip()
    if not args:
        models = repl.client.list_models()
        repl.ui.print_models(models, repl.config.model)
        return

    # Switch model
    repl.config.model = args
    repl.config.save()
    repl.session.model = args
    repl.ui.print_success(f"Switched to model: [bold]{args}[/]")


def cmd_config(repl: "REPL", args: str):
    parts = args.strip().split(None, 1)
    if not parts:
        repl.ui.print_config(repl.config.as_dict())
        return

    if len(parts) == 1:
        key = parts[0]
        val = repl.config.get(key)
        if val is not None:
            repl.ui.print_info(f"{key} = {val}")
        else:
            repl.ui.print_error(f"Unknown config key: {key}")
        return

    key, value = parts[0], parts[1]
    if repl.config.set(key, value):
        repl.ui.print_success(f"Set {key} = {value}")
    else:
        repl.ui.print_error(f"Unknown config key: {key}")


def cmd_session(repl: "REPL", args: str):
    repl.ui.print_session_info(repl.session)


def cmd_save(repl: "REPL", args: str):
    from ..config import GLOBAL_SESSIONS_DIR
    filename = args.strip() or f"session-{int(time.time())}.json"
    if not filename.endswith(".json"):
        filename += ".json"
    path = GLOBAL_SESSIONS_DIR / filename
    data = {
        "session_id": repl.session.session_id,
        "model": repl.session.model,
        "system_prompt": repl.session.system_prompt,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_name": m.tool_name,
                "timestamp": m.timestamp,
            }
            for m in repl.session.messages
        ],
    }
    path.write_text(json.dumps(data, indent=2))
    repl.ui.print_success(f"Session saved to: {path}")


def cmd_load(repl: "REPL", args: str):
    from ..config import GLOBAL_SESSIONS_DIR
    from ..client import Message
    filename = args.strip()
    if not filename:
        # List available sessions
        sessions = sorted(GLOBAL_SESSIONS_DIR.glob("*.json"))
        if not sessions:
            repl.ui.print_info("No saved sessions found.")
            return
        repl.ui.print_info("Saved sessions:")
        for s in sessions:
            repl.ui.console.print(f"  [dim]{s.name}[/]")
        return

    if not filename.endswith(".json"):
        filename += ".json"
    path = GLOBAL_SESSIONS_DIR / filename
    if not path.exists():
        repl.ui.print_error(f"Session file not found: {path}")
        return

    try:
        data = json.loads(path.read_text())
        repl.session.session_id = data.get("session_id", repl.session.session_id)
        repl.session.model = data.get("model", repl.session.model)
        repl.session.system_prompt = data.get("system_prompt", repl.session.system_prompt)
        repl.session.messages = []
        for m in data.get("messages", []):
            msg = Message(
                role=m["role"],
                content=m["content"],
                tool_calls=m.get("tool_calls", []),
                tool_name=m.get("tool_name"),
                timestamp=m.get("timestamp", time.time()),
            )
            repl.session.messages.append(msg)
        repl.ui.print_success(f"Session loaded: {filename} ({len(repl.session.messages)} messages)")
    except Exception as e:
        repl.ui.print_error(f"Failed to load session: {e}")


def cmd_compact(repl: "REPL", args: str):
    n = int(args.strip()) if args.strip().isdigit() else 20
    before = len(repl.session.messages)
    repl.session.compact(keep_last=n)
    after = len(repl.session.messages)
    repl.ui.print_success(f"Compacted: {before} → {after} messages kept")


def cmd_agents(repl: "REPL", args: str):
    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""

    if not sub or sub == "list":
        agents = repl.registry.list_all()
        repl.ui.print_agents(agents)
        return

    if sub == "run":
        # /agents run <agent_name> <task>
        run_parts = sub_args.split(None, 1)
        if len(run_parts) < 2:
            repl.ui.print_error("Usage: /agents run <agent_name> <task>")
            return
        agent_name, task = run_parts[0], run_parts[1]
        result = repl.orchestrator.run_agent(agent_name, task, parent_session=repl.session)
        if result.success:
            repl.ui.print_response(result.output)
        else:
            repl.ui.print_error(f"Agent failed: {result.error}")
        return

    if sub == "new":
        _create_agent_interactive(repl, sub_args)
        return

    if sub == "delete":
        name = sub_args.strip()
        if repl.registry.delete_agent(name):
            repl.ui.print_success(f"Deleted agent: {name}")
        else:
            repl.ui.print_error(f"Cannot delete agent: {name}")
        return

    if sub == "show":
        name = sub_args.strip()
        agent = repl.registry.get(name)
        if not agent:
            repl.ui.print_error(f"Agent not found: {name}")
            return
        from rich.panel import Panel
        from rich.text import Text
        t = Text()
        t.append(f"Name: {agent.name}\n", style="bold")
        t.append(f"Description: {agent.description}\n")
        t.append(f"Model: {agent.model or 'default'}\n")
        t.append(f"Tools: {', '.join(agent.tools) if agent.tools else 'all'}\n")
        t.append(f"Max turns: {agent.max_turns}\n")
        t.append(f"Scope: {agent.scope}\n\n")
        t.append("System Prompt:\n", style="bold")
        t.append(agent.system_prompt)
        repl.ui.console.print(Panel(t, title=f"Agent: {agent.name}", border_style="magenta"))
        return

    repl.ui.print_error(f"Unknown agents subcommand: {sub}")
    repl.ui.print_info("Usage: /agents [list|run|new|delete|show]")


def _create_agent_interactive(repl: "REPL", args: str):
    """Interactive agent creation wizard."""
    from ..config import AgentDefinition
    repl.ui.console.print("\n[bold magenta]Create New Agent[/]\n")

    try:
        name = input("  Agent name (e.g. 'my-coder'): ").strip()
        if not name:
            repl.ui.print_error("Name cannot be empty.")
            return
        description = input("  Description (when should this agent be used?): ").strip()
        system_prompt = input("  System prompt (or press Enter for default): ").strip()
        if not system_prompt:
            system_prompt = f"You are {name}, a specialized AI assistant."
        model = input(f"  Model (press Enter for default '{repl.config.model}'): ").strip()
        scope_input = input("  Scope [project/user] (default: user): ").strip().lower()
        scope = "user" if scope_input in ("", "user") else "project"

        agent = AgentDefinition(
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model or None,
            scope=scope,
        )
        repl.registry.save_agent(agent)
        repl.ui.print_success(f"Agent '{name}' created and saved.")
    except (EOFError, KeyboardInterrupt):
        repl.ui.print_info("Cancelled.")


def cmd_tools(repl: "REPL", args: str):
    tools = repl.tools.list_tools()
    repl.ui.print_tools(tools)


def cmd_run(repl: "REPL", args: str):
    """Run a shell command directly."""
    if not args.strip():
        repl.ui.print_error("Usage: /run <command>")
        return
    result = repl.tools.execute("run_shell", {"command": args})
    if result.success:
        repl.ui.console.print(result.output)
    else:
        repl.ui.print_error(result.error or "Command failed")
        if result.output:
            repl.ui.console.print(result.output)


def cmd_read(repl: "REPL", args: str):
    """Read a file and display it."""
    if not args.strip():
        repl.ui.print_error("Usage: /read <path>")
        return
    result = repl.tools.execute("read_file", {"path": args.strip()})
    if result.success:
        from rich.syntax import Syntax
        from rich.panel import Panel
        path = args.strip()
        ext = Path(path).suffix.lstrip(".")
        lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                    "rs": "rust", "go": "go", "sh": "bash", "md": "markdown",
                    "json": "json", "yaml": "yaml", "yml": "yaml",
                    "toml": "toml", "html": "html", "css": "css"}
        lang = lang_map.get(ext, "text")
        syntax = Syntax(
            result.output, lang,
            theme=repl.config.theme,
            line_numbers=True,
        )
        repl.ui.console.print(Panel(syntax, title=f"[dim]{path}[/]", border_style="dim"))
    else:
        repl.ui.print_error(result.error or "Failed to read file")


def cmd_write(repl: "REPL", args: str):
    """Write content to a file (opens $EDITOR or prompts)."""
    if not args.strip():
        repl.ui.print_error("Usage: /write <path>")
        return
    path = args.strip()
    editor = os.environ.get("EDITOR", "nano")
    repl.ui.print_info(f"Opening {path} in {editor}...")
    os.system(f"{editor} {path}")


def cmd_diff(repl: "REPL", args: str):
    """Show diff between two files."""
    parts = args.strip().split()
    if len(parts) < 2:
        repl.ui.print_error("Usage: /diff <file_a> <file_b>")
        return
    result = repl.tools.execute("diff_files", {"file_a": parts[0], "file_b": parts[1]})
    if result.success:
        repl.ui.print_diff(result.output)
    else:
        repl.ui.print_error(result.error or "Diff failed")


def cmd_ls(repl: "REPL", args: str):
    """List files in a directory."""
    path = args.strip() or "."
    result = repl.tools.execute("list_files", {"path": path})
    if result.success:
        repl.ui.console.print(result.output)
    else:
        repl.ui.print_error(result.error or "Failed to list files")


def cmd_grep(repl: "REPL", args: str):
    """Search for a pattern in files."""
    parts = args.strip().split(None, 1)
    if not parts:
        repl.ui.print_error("Usage: /grep <pattern> [path]")
        return
    kwargs = {"pattern": parts[0]}
    if len(parts) > 1:
        kwargs["path"] = parts[1]
    result = repl.tools.execute("grep_files", kwargs)
    if result.success:
        repl.ui.console.print(result.output)
    else:
        repl.ui.print_error(result.error or "Grep failed")


def cmd_search(repl: "REPL", args: str):
    """Search the web."""
    if not args.strip():
        repl.ui.print_error("Usage: /search <query>")
        return
    repl.ui.start_spinner("Searching...")
    result = repl.tools.execute("web_search", {"query": args.strip()})
    repl.ui.stop_spinner()
    if result.success:
        repl.ui.print_response(result.output)
    else:
        repl.ui.print_error(result.error or "Search failed")


def cmd_system(repl: "REPL", args: str):
    """View or set the system prompt."""
    args = args.strip()
    if not args:
        repl.ui.console.print(
            f"[dim]Current system prompt:[/]\n{repl.session.system_prompt}"
        )
        return
    repl.session.system_prompt = args
    repl.ui.print_success("System prompt updated.")


def cmd_think(repl: "REPL", args: str):
    """Toggle showing thinking tokens."""
    repl.config.show_thinking = not repl.config.show_thinking
    repl.config.save()
    state = "enabled" if repl.config.show_thinking else "disabled"
    repl.ui.print_success(f"Thinking display {state}.")


def cmd_safe(repl: "REPL", args: str):
    """Toggle safe mode (tool approval prompts)."""
    repl.config.safe_mode = not repl.config.safe_mode
    repl.tools.safe_mode = repl.config.safe_mode
    repl.config.save()
    state = "ON" if repl.config.safe_mode else "OFF"
    repl.ui.print_success(f"Safe mode {state}.")


def cmd_approve(repl: "REPL", args: str):
    """Toggle auto-approve for tools."""
    repl.config.auto_approve_tools = not repl.config.auto_approve_tools
    repl.tools.auto_approve = repl.config.auto_approve_tools
    repl.config.save()
    state = "ON" if repl.config.auto_approve_tools else "OFF"
    repl.ui.print_success(f"Auto-approve {state}.")


def cmd_status(repl: "REPL", args: str):
    """Check Ollama connection and model status."""
    repl.ui.start_spinner("Checking connection...")
    connected = repl.client.check_connection()
    repl.ui.stop_spinner()
    if connected:
        models = repl.client.list_models()
        repl.ui.print_success(f"Connected to Ollama at {repl.config.host}")
        repl.ui.print_models(models, repl.config.model)
    else:
        repl.ui.print_error(f"Cannot connect to Ollama at {repl.config.host}")
        repl.ui.print_info("Make sure Ollama is running: ollama serve")


def cmd_new(repl: "REPL", args: str):
    """Start a new session."""
    repl.session.clear()
    repl.session.session_id = f"session-{uuid.uuid4().hex[:8]}"
    repl.ui.print_success("New session started.")


def cmd_history(repl: "REPL", args: str):
    """Show conversation history."""
    if not repl.session.messages:
        repl.ui.print_info("No messages in current session.")
        return
    from rich.panel import Panel
    from rich.text import Text
    n = int(args.strip()) if args.strip().isdigit() else len(repl.session.messages)
    msgs = repl.session.messages[-n:]
    for msg in msgs:
        role_style = {
            "user": "bold bright_white",
            "assistant": "bold bright_cyan",
            "tool": "bold yellow",
            "system": "dim",
        }.get(msg.role, "white")
        content = msg.content[:500] + ("..." if len(msg.content) > 500 else "")
        repl.ui.console.print(f"[{role_style}]{msg.role.upper()}[/]: {content}")
        repl.ui.console.print()


def cmd_cd(repl: "REPL", args: str):
    """Change working directory."""
    path = args.strip() or str(Path.home())
    try:
        os.chdir(path)
        repl.ui.print_success(f"Changed to: {os.getcwd()}")
    except Exception as e:
        repl.ui.print_error(str(e))


def cmd_pwd(repl: "REPL", args: str):
    """Print current working directory."""
    repl.ui.console.print(os.getcwd())


def cmd_export(repl: "REPL", args: str):
    """Export conversation to markdown."""
    filename = args.strip() or f"conversation-{int(time.time())}.md"
    if not filename.endswith(".md"):
        filename += ".md"
    lines = [f"# OLCLI Conversation\n\nModel: {repl.session.model}\n\n---\n"]
    for msg in repl.session.messages:
        if msg.role == "user":
            lines.append(f"## User\n\n{msg.content}\n")
        elif msg.role == "assistant":
            lines.append(f"## Assistant\n\n{msg.content}\n")
        elif msg.role == "tool":
            lines.append(f"### Tool: {msg.tool_name}\n\n```\n{msg.content[:500]}\n```\n")
    Path(filename).write_text("\n".join(lines))
    repl.ui.print_success(f"Exported to: {filename}")


def cmd_multiline(repl: "REPL", args: str):
    """Enter multi-line input mode (end with a line containing only '.')."""
    repl.ui.print_info("Multi-line mode: enter your message, end with a line containing only '.'")
    lines = []
    try:
        while True:
            line = input("... ")
            if line == ".":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    if lines:
        repl._process_input("\n".join(lines))


# ── Build Registry ────────────────────────────────────────────────────────────
def build_command_registry() -> CommandRegistry:
    reg = CommandRegistry()

    commands = [
        Command("help", "Show all available commands", "/help", cmd_help, ["h"], "/help"),
        Command("exit", "Exit OLCLI", "/exit", cmd_exit, ["quit", "q"], "/exit"),
        Command("clear", "Clear conversation history", "/clear", cmd_clear, [], "/clear"),
        Command("cls", "Clear the terminal screen", "/cls", cmd_cls, [], "/cls"),
        Command("new", "Start a fresh session", "/new", cmd_new, [], "/new"),
        Command("model", "List or switch models", "/model [name]", cmd_model, [], "/model llama3.2"),
        Command("config", "View or set config", "/config [key] [value]", cmd_config, [], "/config temperature 0.5"),
        Command("session", "Show session info", "/session", cmd_session, [], "/session"),
        Command("history", "Show message history", "/history [n]", cmd_history, [], "/history 10"),
        Command("save", "Save session to file", "/save [filename]", cmd_save, [], "/save my-session"),
        Command("load", "Load a saved session", "/load [filename]", cmd_load, [], "/load my-session"),
        Command("compact", "Compact history to save context", "/compact [n]", cmd_compact, [], "/compact 20"),
        Command("export", "Export conversation to markdown", "/export [filename]", cmd_export, [], "/export chat.md"),
        Command("agents", "Manage and run sub-agents", "/agents [list|run|new|delete|show]", cmd_agents, [], "/agents run coder 'implement a sort function'"),
        Command("tools", "List available tools", "/tools", cmd_tools, [], "/tools"),
        Command("run", "Run a shell command", "/run <command>", cmd_run, [], "/run ls -la"),
        Command("read", "Read and display a file", "/read <path>", cmd_read, [], "/read main.py"),
        Command("write", "Open a file in editor", "/write <path>", cmd_write, [], "/write notes.md"),
        Command("diff", "Show diff between files", "/diff <file_a> <file_b>", cmd_diff, [], "/diff old.py new.py"),
        Command("ls", "List directory contents", "/ls [path]", cmd_ls, [], "/ls src/"),
        Command("grep", "Search files for pattern", "/grep <pattern> [path]", cmd_grep, [], "/grep 'def main' src/"),
        Command("search", "Search the web", "/search <query>", cmd_search, [], "/search python async generators"),
        Command("system", "View or set system prompt", "/system [prompt]", cmd_system, [], "/system You are a Rust expert"),
        Command("think", "Toggle thinking display", "/think", cmd_think, [], "/think"),
        Command("safe", "Toggle safe mode", "/safe", cmd_safe, [], "/safe"),
        Command("approve", "Toggle auto-approve tools", "/approve", cmd_approve, [], "/approve"),
        Command("status", "Check Ollama connection", "/status", cmd_status, [], "/status"),
        Command("cd", "Change working directory", "/cd [path]", cmd_cd, [], "/cd ~/projects"),
        Command("pwd", "Print working directory", "/pwd", cmd_pwd, [], "/pwd"),
        Command("multiline", "Enter multi-line input mode", "/multiline", cmd_multiline, ["ml"], "/multiline"),
    ]

    for cmd in commands:
        reg.register(cmd)

    return reg
