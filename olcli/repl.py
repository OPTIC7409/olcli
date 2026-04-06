"""
OLCLI REPL
The main interactive read-eval-print loop.

Key features:
  - YOLO mode  (/yolo): auto-approves all tools, no interruptions
  - Non-blocking input: type your next prompt while the AI is still running;
    it is queued and executed immediately after the current turn ends
  - Compact tool output: tool calls/results are one-liners; use /expand N to
    see full details for tool call #N
"""

import os
import sys
import uuid
import asyncio
import threading
from collections import deque
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

from .config import OlcliConfig, AgentRegistry, GLOBAL_CONFIG_DIR
from .client import OllamaClient, Session, ClientCallbacks
from .tools.builtins import ToolRegistry
from .agents.orchestrator import AgentOrchestrator
from .commands.registry import CommandRegistry, build_command_registry
from .ui.terminal import TerminalUI


# ── Prompt Toolkit Style ──────────────────────────────────────────────────────
PT_STYLE = PTStyle.from_dict({
    "prompt":       "#00d7ff bold",
    "path":         "#888888",
    "model":        "#00ff87",
    "yolo":         "#ff2222 bold",
    "dim":          "#666666",
})


class REPL:
    def __init__(self, config: OlcliConfig):
        self.config = config
        self.running = True

        # Core components
        self.ui = TerminalUI(config)
        self.tools = ToolRegistry(
            safe_mode=config.safe_mode,
            auto_approve=config.auto_approve_tools or config.yolo_mode,
        )
        self.registry = AgentRegistry()
        self.registry.load_from_dirs()

        # Session
        self.session = Session(
            session_id=f"session-{uuid.uuid4().hex[:8]}",
            model=config.model,
            system_prompt=config.system_prompt,
        )

        # Callbacks for the client
        self._streaming = False
        callbacks = ClientCallbacks(
            on_token=self._on_token,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
            on_tool_approval=self._on_tool_approval,
            on_thinking=self._on_thinking,
            on_error=self._on_error,
            on_no_tools=self._on_no_tools,
        )
        self.client = OllamaClient(config, self.tools, callbacks)

        # Orchestrator
        self.orchestrator = AgentOrchestrator(
            config=config,
            registry=self.registry,
            tools=self.tools,
            on_agent_start=self.ui.print_agent_start,
            on_agent_end=self.ui.print_agent_end,
            on_agent_token=self.ui.print_agent_token,
            on_agent_tool=lambda name, tool, args: self.ui.print_tool_call(tool, args),
        )

        # Commands
        self.commands: CommandRegistry = build_command_registry()

        # Prompt toolkit session
        history_file = GLOBAL_CONFIG_DIR / "history"
        self._pt_session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self._build_completer(),
            style=PT_STYLE,
            key_bindings=self._build_keybindings(),
        )

        # ── Non-blocking input queue ──────────────────────────────────────────
        # While the AI is processing, the user can still type. Inputs are
        # collected here and drained one-by-one after each turn completes.
        self._input_queue: deque[str] = deque()
        self._busy = False           # True while AI is processing a turn
        self._busy_lock = threading.Lock()

    # ── YOLO helpers ─────────────────────────────────────────────────────────

    def _sync_yolo(self):
        """Sync YOLO mode into the tool registry and save config."""
        if self.config.yolo_mode:
            self.tools.safe_mode = False
            self.tools.auto_approve = True
        else:
            self.tools.safe_mode = self.config.safe_mode
            self.tools.auto_approve = self.config.auto_approve_tools
        self.config.save()

    # ── Completer / Keybindings ───────────────────────────────────────────────

    def _build_completer(self) -> WordCompleter:
        slash_cmds = [f"/{c.name}" for c in self.commands.list_unique()]
        agent_names = [f"/agents run {a.name}" for a in self.registry.list_all()]
        return WordCompleter(
            slash_cmds + agent_names,
            ignore_case=True,
            sentence=True,
        )

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            event.app.exit(exception=KeyboardInterrupt)

        return kb

    def _get_prompt(self) -> HTML:
        cwd = os.path.basename(os.getcwd()) or "/"
        model = self.config.model
        yolo_tag = " <yolo>⚡YOLO</yolo>" if self.config.yolo_mode else ""
        busy_tag = " <dim>(running…)</dim>" if self._busy else ""
        return HTML(
            f'<prompt>olcli</prompt>'
            f'<path> {cwd}</path>'
            f' <model>({model})</model>'
            f'{yolo_tag}'
            f'{busy_tag}'
            f'<prompt> ❯ </prompt>'
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_token(self, token: str):
        if not self._streaming:
            self._streaming = True
            self.ui.start_stream()
        self.ui.stream_token(token)

    def _on_tool_call(self, tool_name: str, args: dict):
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        self.ui.print_tool_call(tool_name, args)

    def _on_tool_result(self, tool_name: str, result):
        self.ui.print_tool_result(tool_name, result)

    def _on_tool_approval(self, tool_name: str, args: dict) -> bool:
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        # In YOLO mode, always approve silently
        if self.config.yolo_mode:
            return True
        return self.ui.print_tool_approval(tool_name, args)

    def _on_thinking(self, thinking: str):
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        self.ui.print_thinking(thinking)

    def _on_error(self, error: str):
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        self.ui.print_error(error)

    def _on_no_tools(self, model: str):
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        self.ui.print_warning(
            f"[bold]{model}[/] does not support tool calling — "
            "switching to plain chat mode for this session."
        )

    # ── Input Processing ──────────────────────────────────────────────────────

    def _process_input(self, user_input: str):
        """Process a single user input (command or chat message)."""
        user_input = user_input.strip()
        if not user_input:
            return

        # Slash commands
        if user_input.startswith("/") or user_input.startswith("!"):
            if user_input.startswith("!"):
                user_input = "/run " + user_input[1:]
            handled = self.commands.execute(self, user_input)
            if not handled:
                self.ui.print_error(
                    f"Unknown command: {user_input.split()[0]}. "
                    "Type /help for available commands."
                )
            return

        # Regular chat — mark busy so the prompt shows (running…)
        with self._busy_lock:
            self._busy = True

        self._streaming = False
        self.ui.print_assistant_header(self.session.model)

        try:
            response = self.client.chat(
                session=self.session,
                user_message=user_input,
            )
        except KeyboardInterrupt:
            if self._streaming:
                self.ui.end_stream()
                self._streaming = False
            self.ui.print_warning("Interrupted.")
            return
        except Exception as e:
            if self._streaming:
                self.ui.end_stream()
                self._streaming = False
            self.ui.print_error(f"Error: {e}")
            return
        finally:
            with self._busy_lock:
                self._busy = False

        # Finalize streaming
        if self._streaming:
            self.ui.end_stream()
            self._streaming = False
        elif response:
            self.ui.print_response(response)

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def _input_loop(self):
        """
        Async REPL loop.

        Each user input is dispatched to a thread-pool executor so the AI can
        run without blocking the event loop.  This keeps prompt_toolkit's async
        input responsive (the user can type while the AI is working) without
        needing patch_stdout, which conflicts with Rich's Console on Windows and
        causes raw ANSI escape codes to appear in the terminal.
        """
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                user_input = await self._pt_session.prompt_async(
                    self._get_prompt,
                )
            except KeyboardInterrupt:
                self.ui.print_info("Use /exit to quit.")
                continue
            except EOFError:
                self.ui.print_info("Goodbye!")
                self.running = False
                break

            if not user_input.strip():
                continue

            with self._busy_lock:
                busy = self._busy

            if busy:
                # Queue the input for after the current turn
                self._input_queue.append(user_input)
                self.ui.print_info(
                    f"Queued (AI is running): {user_input[:60]}"
                )
            else:
                # Run in a thread so the event loop stays free for input
                await loop.run_in_executor(
                    None, self._process_input, user_input
                )
                # Drain any queued inputs sequentially
                while self._input_queue and self.running:
                    next_input = self._input_queue.popleft()
                    self.ui.print_info(f"Running queued: {next_input[:60]}")
                    await loop.run_in_executor(
                        None, self._process_input, next_input
                    )

    async def run_async(self):
        """Async REPL loop."""
        self.ui.print_banner(self.config.model, self.config.host)

        if not self.client.check_connection():
            self.ui.print_warning(
                f"Cannot connect to Ollama at {self.config.host}. "
                "Make sure Ollama is running with: [bold]ollama serve[/]"
            )

        await self._input_loop()

    def run(self):
        """Synchronous entry point."""
        asyncio.run(self.run_async())
