"""
OLCLI Terminal UI
Rich-powered terminal interface with syntax highlighting, panels, and diff views.
Compact tool output with optional expansion; YOLO mode indicator.
"""

import os
import sys
import time
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.rule import Rule
from rich.columns import Columns
from rich import box
from rich.style import Style
from rich.theme import Theme

from ..config import OlcliConfig, AgentDefinition
from ..tools.builtins import ToolResult


# ── Theme ─────────────────────────────────────────────────────────────────────
OLCLI_THEME = Theme({
    "user":       "bold bright_white",
    "assistant":  "bright_cyan",
    "tool.name":  "bold yellow",
    "tool.args":  "dim yellow",
    "tool.ok":    "bold green",
    "tool.err":   "bold red",
    "agent.name": "bold magenta",
    "agent.task": "italic dim",
    "thinking":   "dim italic cyan",
    "prompt":     "bold bright_cyan",
    "info":       "dim white",
    "warning":    "bold yellow",
    "error":      "bold red",
    "success":    "bold green",
    "header":     "bold bright_white on dark_blue",
    "cmd":        "bold bright_yellow",
    "dim":        "dim",
    "yolo":       "bold bright_red",
})

# Agent color map
AGENT_COLORS = {
    "explorer": "blue",
    "coder": "green",
    "researcher": "yellow",
    "reviewer": "magenta",
    "debugger": "red",
    "shell": "cyan",
}

# Tools that are "write" operations — shown with a pencil icon
WRITE_TOOLS = {"write_file", "edit_file", "delete_file", "move_file", "make_directory", "run_shell"}


def _short_arg(val, max_len: int = 60) -> str:
    """Return a short single-line representation of an argument value."""
    s = str(val).replace("\n", "↵ ").strip()
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s


class TerminalUI:
    def __init__(self, config: OlcliConfig):
        self.config = config
        self.console = Console(theme=OLCLI_THEME, highlight=True)
        self._live: Optional[Live] = None
        self._streaming_text = ""
        self._spinner: Optional[Live] = None

        # Collapsible tool log: list of (tool_name, args, result_or_None)
        # Each entry is rendered as a compact one-liner; user can /expand N to see details.
        self._tool_log: list[dict] = []

    # ── Banner ────────────────────────────────────────────────────────────────

    def print_banner(self, model: str, host: str):
        banner = Text()
        banner.append("  ██████╗ ██╗      ██████╗██╗     ██╗\n", style="bold bright_cyan")
        banner.append(" ██╔═══██╗██║     ██╔════╝██║     ██║\n", style="bold bright_cyan")
        banner.append(" ██║   ██║██║     ██║     ██║     ██║\n", style="bold cyan")
        banner.append(" ██║   ██║██║     ██║     ██║     ██║\n", style="bold cyan")
        banner.append(" ╚██████╔╝███████╗╚██████╗███████╗██║\n", style="bold blue")
        banner.append("  ╚═════╝ ╚══════╝ ╚═════╝╚══════╝╚═╝\n", style="bold blue")

        info = Table.grid(padding=(0, 2))
        info.add_column(style="dim")
        info.add_column(style="bright_white")
        info.add_row("Model", f"[bold bright_cyan]{model}[/]")
        info.add_row("Host", f"[dim]{host}[/]")
        info.add_row("Version", "[dim]1.0.0[/]")
        info.add_row("Type", "[bold yellow]/help[/] for commands")

        panel = Panel(
            Columns([banner, info], equal=False, expand=False),
            border_style="bright_blue",
            padding=(0, 1),
        )
        self.console.print(panel)
        self.console.print()

    # ── Prompts ───────────────────────────────────────────────────────────────

    def print_user_prompt(self):
        self.console.print()

    def print_assistant_header(self, model: str = None):
        label = f"[assistant]OLCLI[/]"
        if model:
            label += f" [dim]({model})[/]"
        if self.config.yolo_mode:
            label += " [yolo]⚡ YOLO[/]"
        self.console.print(f"\n{label}")

    # ── Streaming ─────────────────────────────────────────────────────────────

    def start_stream(self):
        """Begin streaming output."""
        self._streaming_text = ""
        self.console.print()

    def stream_token(self, token: str):
        """Print a streaming token directly."""
        self.console.print(token, end="", markup=False, highlight=False)
        self._streaming_text += token

    def end_stream(self):
        """Finalize streaming and render markdown."""
        self.console.print()  # newline after stream
        # Re-render the accumulated text as markdown
        if self._streaming_text.strip():
            self.console.print()
            try:
                md = Markdown(self._streaming_text, code_theme=self.config.theme)
                self.console.print(md)
            except Exception:
                pass  # already printed raw
        self._streaming_text = ""

    def print_response(self, text: str):
        """Print a complete (non-streaming) response."""
        self.console.print()
        try:
            md = Markdown(text, code_theme=self.config.theme)
            self.console.print(md)
        except Exception:
            self.console.print(text)

    # ── Thinking ──────────────────────────────────────────────────────────────

    def print_thinking(self, thinking: str):
        if not self.config.show_thinking or not thinking.strip():
            return
        panel = Panel(
            Text(thinking.strip(), style="thinking"),
            title="[dim]Thinking[/]",
            border_style="dim",
            padding=(0, 1),
        )
        self.console.print(panel)

    # ── Tool Calls (compact) ──────────────────────────────────────────────────

    def print_tool_call(self, tool_name: str, args: dict):
        """Print a compact one-line tool call indicator."""
        import json

        # Build a short summary of the most important arg
        summary = ""
        if args:
            # Pick the first meaningful arg value
            for key in ("path", "command", "query", "pattern", "file_a", "content"):
                if key in args:
                    summary = _short_arg(args[key], 55)
                    break
            if not summary:
                first_val = next(iter(args.values()), "")
                summary = _short_arg(first_val, 55)

        icon = "✏" if tool_name in WRITE_TOOLS else "⚙"
        idx = len(self._tool_log)
        self._tool_log.append({"tool": tool_name, "args": args, "result": None})

        summary_part = f"  [dim]{summary}[/dim]" if summary else ""
        self.console.print(
            f" [bold yellow]{icon} {tool_name}[/bold yellow]{summary_part}"
            f"  [dim](#{idx}  /expand {idx})[/dim]"
        )

    def print_tool_result(self, tool_name: str, result: ToolResult):
        """Update the last tool log entry and print a compact result line."""
        # Update log
        if self._tool_log:
            self._tool_log[-1]["result"] = result

        if result.success:
            icon = "✓"
            color = "green"
            preview = result.output.strip().replace("\n", " ")
            if len(preview) > 70:
                preview = preview[:70] + "…"
            suffix = f"  [dim]{preview}[/dim]" if preview else ""
        else:
            icon = "✗"
            color = "red"
            err = (result.error or "failed").strip()
            suffix = f"  [bold red]{err[:70]}[/bold red]"

        self.console.print(
            f"   [bold {color}]{icon} {tool_name}[/bold {color}]{suffix}"
        )

    def print_tool_approval(self, tool_name: str, args: dict) -> bool:
        """Ask user to approve a tool call. Returns True if approved."""
        import json
        # Build compact summary
        summary = ""
        if args:
            for key in ("path", "command", "query", "pattern", "content"):
                if key in args:
                    summary = _short_arg(args[key], 80)
                    break
            if not summary:
                summary = _short_arg(next(iter(args.values()), ""), 80)

        self.console.print()
        self.console.print(
            f"[warning]⚠ Approval:[/] [bold yellow]{tool_name}[/]  [dim]{summary}[/]  "
            f"[dim](use /yolo to skip all approvals)[/]"
        )
        try:
            answer = input("  Allow? [y/N/a=always] ").strip().lower()
            return answer in ("y", "yes", "a", "always")
        except (EOFError, KeyboardInterrupt):
            return False

    def print_tool_expand(self, idx: int):
        """Print full details for a logged tool call."""
        import json
        if idx < 0 or idx >= len(self._tool_log):
            self.console.print(f"[error]No tool call #{idx} in this session.[/]")
            return

        entry = self._tool_log[idx]
        tool_name = entry["tool"]
        args = entry["args"]
        result: Optional[ToolResult] = entry["result"]

        args_str = json.dumps(args, indent=2) if args else "{}"

        table = Table.grid(padding=(0, 1))
        table.add_column(style="tool.name", width=14)
        table.add_column(style="tool.args")
        table.add_row("⚙ Tool:", f"[tool.name]{tool_name}[/]")
        if args:
            for k, v in args.items():
                v_str = str(v)
                if len(v_str) > 300:
                    v_str = v_str[:300] + "..."
                table.add_row(f"  {k}:", f"[dim]{v_str}[/]")

        self.console.print(
            Panel(table, title=f"[dim]Tool #{idx} — {tool_name}[/]",
                  border_style="yellow", padding=(0, 1))
        )

        if result is not None:
            output = result.output
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"

            if output.startswith("---") or output.startswith("+++"):
                content = Syntax(output, "diff", theme=self.config.theme, line_numbers=False)
            elif tool_name in ("run_shell",) and output:
                content = Syntax(output, "bash", theme=self.config.theme, line_numbers=False)
            else:
                content = Text(output)

            border = "green" if result.success else "red"
            status = "[tool.ok]✓[/]" if result.success else "[tool.err]✗[/]"
            self.console.print(
                Panel(content, title=f"{status} Result", border_style=border, padding=(0, 1))
            )

    # ── Agent UI ──────────────────────────────────────────────────────────────

    def print_agent_start(self, agent_name: str, task: str, session_id: str):
        color = AGENT_COLORS.get(agent_name, "magenta")
        # Compact one-liner for agent start
        task_short = task[:80] + ("…" if len(task) > 80 else "")
        self.console.print(
            f"[{color}]▶ agent:{agent_name}[/]  [dim]{task_short}[/]"
        )

    def print_agent_end(self, agent_name: str, result):
        color = AGENT_COLORS.get(agent_name, "magenta")
        status = "[success]✓[/]" if result.success else "[error]✗[/]"
        self.console.print(
            f"[{color}]◀ agent:{agent_name}[/]  {status}  "
            f"[dim]{result.duration:.1f}s · {result.tool_calls} tool calls[/]"
        )

    def print_agent_token(self, agent_name: str, token: str):
        color = AGENT_COLORS.get(agent_name, "magenta")
        self.console.print(
            f"[{color}][{agent_name}][/] {token}",
            end="",
            markup=True,
            highlight=False,
        )

    # ── Spinner ───────────────────────────────────────────────────────────────

    def start_spinner(self, message: str = "Thinking..."):
        self._spinner = Live(
            Spinner("dots", text=f"[dim]{message}[/]"),
            console=self.console,
            refresh_per_second=10,
        )
        self._spinner.start()

    def stop_spinner(self):
        if self._spinner:
            self._spinner.stop()
            self._spinner = None

    # ── Commands & Help ───────────────────────────────────────────────────────

    def print_help(self, commands: list[dict]):
        table = Table(
            title="OLCLI Commands",
            box=box.ROUNDED,
            border_style="bright_blue",
            header_style="bold bright_white",
            show_header=True,
        )
        table.add_column("Command", style="cmd", min_width=20)
        table.add_column("Description", style="white")
        table.add_column("Example", style="dim")

        for cmd in commands:
            table.add_row(
                cmd.get("name", ""),
                cmd.get("description", ""),
                cmd.get("example", ""),
            )
        self.console.print(table)

    def print_models(self, models: list[str], current: str):
        table = Table(
            title="Available Models",
            box=box.SIMPLE,
            border_style="bright_blue",
        )
        table.add_column("Model", style="bright_cyan")
        table.add_column("Status", style="dim")
        for m in models:
            status = "[success]● active[/]" if m == current else ""
            table.add_row(m, status)
        self.console.print(table)

    def print_agents(self, agents: list):
        table = Table(
            title="Available Agents",
            box=box.ROUNDED,
            border_style="magenta",
            header_style="bold bright_white",
        )
        table.add_column("Name", style="bold magenta", min_width=12)
        table.add_column("Scope", style="dim", min_width=8)
        table.add_column("Model", style="cyan", min_width=12)
        table.add_column("Tools", style="dim")
        table.add_column("Description", style="white")

        for a in agents:
            color = AGENT_COLORS.get(a.name, "magenta")
            tools_str = ", ".join(a.tools[:4]) if a.tools else "all"
            if a.tools and len(a.tools) > 4:
                tools_str += f" +{len(a.tools)-4}"
            table.add_row(
                f"[{color}]{a.name}[/]",
                a.scope,
                a.model or "default",
                tools_str,
                a.description[:80] + ("..." if len(a.description) > 80 else ""),
            )
        self.console.print(table)

    def print_tools(self, tools: list[dict]):
        table = Table(
            title="Available Tools",
            box=box.ROUNDED,
            border_style="yellow",
            header_style="bold bright_white",
        )
        table.add_column("Tool", style="tool.name", min_width=16)
        table.add_column("Approval", style="dim", min_width=10)
        table.add_column("Description", style="white")

        for t in tools:
            approval = "[warning]required[/]" if t.get("requires_approval") else "[dim]auto[/]"
            table.add_row(
                t["name"],
                approval,
                t["description"][:80],
            )
        self.console.print(table)

    def print_config(self, config_dict: dict):
        table = Table(
            title="Configuration",
            box=box.SIMPLE,
            border_style="bright_blue",
        )
        table.add_column("Key", style="bold bright_cyan", min_width=20)
        table.add_column("Value", style="white")
        for k, v in config_dict.items():
            if k == "extra":
                continue
            table.add_row(str(k), str(v))
        self.console.print(table)

    def print_session_info(self, session):
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim")
        table.add_column(style="bright_white")
        table.add_row("Session ID", session.session_id)
        table.add_row("Model", session.model)
        table.add_row("Messages", str(len(session.messages)))
        table.add_row("Tool calls", str(session.tool_calls_total))
        table.add_row("~Tokens", str(session.token_estimate()))
        self.console.print(
            Panel(table, title="[dim]Session Info[/]", border_style="dim")
        )

    # ── Diff ──────────────────────────────────────────────────────────────────

    def print_diff(self, diff_text: str):
        syntax = Syntax(
            diff_text,
            "diff",
            theme=self.config.theme,
            line_numbers=True,
        )
        self.console.print(Panel(syntax, title="Diff", border_style="yellow"))

    # ── Misc ──────────────────────────────────────────────────────────────────

    def print_info(self, msg: str):
        self.console.print(f"[info]ℹ {msg}[/]")

    def print_success(self, msg: str):
        self.console.print(f"[success]✓ {msg}[/]")

    def print_warning(self, msg: str):
        self.console.print(f"[warning]⚠ {msg}[/]")

    def print_error(self, msg: str):
        self.console.print(f"[error]✗ {msg}[/]")

    def print_rule(self, title: str = ""):
        self.console.print(Rule(title, style="dim"))

    def clear(self):
        self.console.clear()
