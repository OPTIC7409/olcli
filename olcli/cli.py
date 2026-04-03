"""
OLCLI CLI Entry Point
Handles command-line arguments and launches the REPL or one-shot mode.
"""

import sys
import argparse
from pathlib import Path

from .config import OlcliConfig, AgentRegistry, ensure_dirs
from .repl import REPL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="olcli",
        description="OLCLI — Claude Code-style AI assistant for Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  olcli                          Start interactive REPL
  olcli -m llama3.2              Start with a specific model
  olcli -p "explain this code"   One-shot prompt (no REPL)
  olcli --agent coder "fix bug"  Run a specific agent directly
  olcli --list-models            List available Ollama models
  olcli --list-agents            List available agents
  olcli --no-tools               Disable all tools
  olcli --safe-off               Disable tool approval prompts
""",
    )

    parser.add_argument(
        "-m", "--model",
        metavar="MODEL",
        help="Ollama model to use (overrides config)",
    )
    parser.add_argument(
        "--host",
        metavar="URL",
        default=None,
        help="Ollama host URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "-p", "--prompt",
        metavar="TEXT",
        help="One-shot prompt: send a message and exit",
    )
    parser.add_argument(
        "--agent",
        metavar="NAME",
        help="Run a specific sub-agent directly",
    )
    parser.add_argument(
        "--system",
        metavar="PROMPT",
        help="Override system prompt for this session",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable all tools for this session",
    )
    parser.add_argument(
        "--safe-off",
        action="store_true",
        help="Disable tool approval prompts (auto-approve all)",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming responses",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available Ollama models and exit",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List available agents and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="OLCLI 1.0.0",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task to perform (used with --agent or as one-shot prompt)",
    )

    return parser


def main():
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args()

    # Load config
    config = OlcliConfig.load()

    # Apply CLI overrides
    if args.model:
        config.model = args.model
    if args.host:
        config.host = args.host
    if args.system:
        config.system_prompt = args.system
    if args.safe_off:
        config.auto_approve_tools = True
    if args.no_stream:
        config.stream = False

    # ── List models ───────────────────────────────────────────────────────────
    if args.list_models:
        from .client import OllamaClient
        from .tools.builtins import ToolRegistry
        from .ui.terminal import TerminalUI
        ui = TerminalUI(config)
        client = OllamaClient(config, ToolRegistry())
        models = client.list_models()
        if models:
            ui.print_models(models, config.model)
        else:
            ui.print_error("No models found. Is Ollama running?")
        return

    # ── List agents ───────────────────────────────────────────────────────────
    if args.list_agents:
        from .ui.terminal import TerminalUI
        ui = TerminalUI(config)
        registry = AgentRegistry()
        registry.load_from_dirs()
        ui.print_agents(registry.list_all())
        return

    # ── One-shot agent mode ───────────────────────────────────────────────────
    if args.agent:
        task = args.task or args.prompt
        if not task:
            print("Error: provide a task for the agent (positional argument or -p)")
            sys.exit(1)
        _run_agent_oneshot(config, args.agent, task, args.no_tools)
        return

    # ── One-shot prompt mode ──────────────────────────────────────────────────
    if args.prompt or (args.task and not args.agent):
        prompt = args.prompt or args.task
        _run_oneshot(config, prompt, args.no_tools)
        return

    # ── Interactive REPL ──────────────────────────────────────────────────────
    repl = REPL(config)
    if args.no_tools:
        repl.tools._tools.clear()
        repl.tools._handlers.clear()
    repl.run()


def _run_oneshot(config: OlcliConfig, prompt: str, no_tools: bool):
    """Run a single prompt and print the response."""
    import uuid
    from .client import OllamaClient, Session, ClientCallbacks
    from .tools.builtins import ToolRegistry
    from .ui.terminal import TerminalUI

    ui = TerminalUI(config)
    tools = ToolRegistry(safe_mode=False, auto_approve=True)
    if no_tools:
        tools._tools.clear()
        tools._handlers.clear()

    streaming = [False]

    def on_token(t):
        if not streaming[0]:
            streaming[0] = True
        print(t, end="", flush=True)

    def on_tool_call(name, args):
        import json
        print(f"\n[Tool: {name}] {json.dumps(args)[:200]}", flush=True)

    def on_tool_result(name, result):
        status = "✓" if result.success else "✗"
        print(f"[{status} {name}] {result.output[:200]}", flush=True)

    callbacks = ClientCallbacks(
        on_token=on_token,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
    )
    client = OllamaClient(config, tools, callbacks)
    session = Session(
        session_id=f"oneshot-{uuid.uuid4().hex[:8]}",
        model=config.model,
        system_prompt=config.system_prompt,
    )

    try:
        client.chat(session=session, user_message=prompt)
        if streaming[0]:
            print()  # final newline
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


def _run_agent_oneshot(config: OlcliConfig, agent_name: str, task: str, no_tools: bool):
    """Run a specific agent on a task and print the result."""
    from .tools.builtins import ToolRegistry
    from .agents.orchestrator import AgentOrchestrator
    from .ui.terminal import TerminalUI

    ui = TerminalUI(config)
    tools = ToolRegistry(safe_mode=False, auto_approve=True)
    if no_tools:
        tools._tools.clear()
        tools._handlers.clear()

    registry = AgentRegistry()
    registry.load_from_dirs()

    def on_token(name, token):
        print(token, end="", flush=True)

    orchestrator = AgentOrchestrator(
        config=config,
        registry=registry,
        tools=tools,
        on_agent_start=lambda n, t, s: print(f"[{n}] Starting: {t[:80]}..."),
        on_agent_end=lambda n, r: print(f"\n[{n}] Done ({r.duration:.1f}s)"),
        on_agent_token=on_token,
    )

    result = orchestrator.run_agent(agent_name, task)
    if result.success:
        print(result.output)
    else:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
