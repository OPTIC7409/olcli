"""
OLCLI Configuration Management
Handles global config, per-project config, and agent definitions.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict


# ── Paths ────────────────────────────────────────────────────────────────────
HOME_DIR = Path.home()
GLOBAL_CONFIG_DIR = HOME_DIR / ".olcli"
GLOBAL_AGENTS_DIR = GLOBAL_CONFIG_DIR / "agents"
GLOBAL_COMMANDS_DIR = GLOBAL_CONFIG_DIR / "commands"
GLOBAL_MEMORY_DIR = GLOBAL_CONFIG_DIR / "memory"
GLOBAL_SESSIONS_DIR = GLOBAL_CONFIG_DIR / "sessions"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.json"

PROJECT_CONFIG_DIR = Path(".olcli")
PROJECT_AGENTS_DIR = PROJECT_CONFIG_DIR / "agents"
PROJECT_COMMANDS_DIR = PROJECT_CONFIG_DIR / "commands"

# Built-in agents directory (package bundled)
PACKAGE_DIR = Path(__file__).parent
BUILTIN_AGENTS_DIR = PACKAGE_DIR / "agents"


def ensure_dirs():
    """Create all required global directories."""
    for d in [
        GLOBAL_CONFIG_DIR, GLOBAL_AGENTS_DIR, GLOBAL_COMMANDS_DIR,
        GLOBAL_MEMORY_DIR, GLOBAL_SESSIONS_DIR
    ]:
        d.mkdir(parents=True, exist_ok=True)


# ── Config Dataclass ──────────────────────────────────────────────────────────
@dataclass
class OlcliConfig:
    model: str = "llama3"
    host: str = "http://localhost:11434"
    system_prompt: str = (
        "You are OLCLI, a powerful AI coding assistant running locally via Ollama. "
        "You help users with coding, file management, shell commands, and complex tasks. "
        "You have access to tools for reading/writing files, running shell commands, "
        "searching the web, and more. Be concise, accurate, and helpful."
    )
    temperature: float = 0.7
    context_length: int = 8192
    stream: bool = True
    auto_approve_tools: bool = False
    safe_mode: bool = True
    theme: str = "monokai"
    max_tool_iterations: int = 20
    show_thinking: bool = True
    compact_mode: bool = False
    yolo_mode: bool = False
    extra: dict = field(default_factory=dict)

    def save(self):
        ensure_dirs()
        data = asdict(self)
        GLOBAL_CONFIG_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "OlcliConfig":
        ensure_dirs()
        if GLOBAL_CONFIG_FILE.exists():
            try:
                data = json.loads(GLOBAL_CONFIG_FILE.read_text())
                known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                return cls(**known)
            except Exception:
                pass
        cfg = cls()
        cfg.save()
        return cfg

    def set(self, key: str, value: Any):
        if hasattr(self, key):
            # Cast to the right type
            current = getattr(self, key)
            if isinstance(current, bool):
                value = str(value).lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                value = int(value)
            elif isinstance(current, float):
                value = float(value)
            setattr(self, key, value)
            self.save()
            return True
        return False

    def get(self, key: str) -> Optional[Any]:
        return getattr(self, key, None)

    def as_dict(self) -> dict:
        return asdict(self)


# ── Agent Definition ──────────────────────────────────────────────────────────
@dataclass
class AgentDefinition:
    name: str
    description: str
    system_prompt: str
    model: Optional[str] = None
    tools: list = field(default_factory=list)           # allowed tools; empty = inherit all
    disallowed_tools: list = field(default_factory=list)
    max_turns: int = 50
    memory: bool = False
    color: str = "cyan"
    scope: str = "project"   # "project" | "user"
    source_file: Optional[str] = None

    @classmethod
    def from_markdown(cls, path: Path) -> "AgentDefinition":
        """Parse a .md file with YAML frontmatter."""
        text = path.read_text()
        frontmatter = {}
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()

        return cls(
            name=frontmatter.get("name", path.stem),
            description=frontmatter.get("description", ""),
            system_prompt=frontmatter.get("system_prompt", body),
            model=frontmatter.get("model"),
            tools=frontmatter.get("tools", []),
            disallowed_tools=frontmatter.get("disallowed_tools", []),
            max_turns=frontmatter.get("max_turns", 50),
            memory=frontmatter.get("memory", False),
            color=frontmatter.get("color", "cyan"),
            scope=frontmatter.get("scope", "project"),
            source_file=str(path),
        )

    def to_markdown(self) -> str:
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "tools": self.tools,
            "disallowed_tools": self.disallowed_tools,
            "max_turns": self.max_turns,
            "memory": self.memory,
            "color": self.color,
            "scope": self.scope,
        }
        fm_str = yaml.dump(frontmatter, default_flow_style=False).strip()
        return f"---\n{fm_str}\n---\n\n{self.system_prompt}\n"


# ── Agent Registry ────────────────────────────────────────────────────────────
class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentDefinition] = {}
        self._load_builtin()

    def _load_builtin(self):
        """Register built-in agents."""
        builtins = [
            AgentDefinition(
                name="explorer",
                description=(
                    "A fast read-only agent for searching and analyzing codebases. "
                    "Use when you need to explore files, search for patterns, or understand project structure."
                ),
                system_prompt=(
                    "You are Explorer, a read-only code analysis agent. Your job is to search, "
                    "read, and analyze files and codebases. You NEVER write or modify files. "
                    "Provide clear, structured findings."
                ),
                tools=["read_file", "list_files", "grep_files", "glob_files"],
                color="blue",
                scope="builtin",
            ),
            AgentDefinition(
                name="coder",
                description=(
                    "A coding specialist that writes, edits, and refactors code. "
                    "Use for implementing features, fixing bugs, or refactoring."
                ),
                system_prompt=(
                    "You are Coder, an expert software engineer. You write clean, efficient, "
                    "well-documented code. You follow best practices and explain your changes clearly. "
                    "Always read existing code before modifying it."
                ),
                tools=["read_file", "write_file", "edit_file", "list_files", "grep_files", "glob_files", "run_shell"],
                color="green",
                scope="builtin",
            ),
            AgentDefinition(
                name="researcher",
                description=(
                    "A web research agent that searches the internet and summarizes findings. "
                    "Use for gathering information, documentation lookups, or fact-checking."
                ),
                system_prompt=(
                    "You are Researcher, an expert at finding and synthesizing information. "
                    "You search the web, read documentation, and provide accurate, well-sourced answers. "
                    "Always cite your sources."
                ),
                tools=["web_search", "read_file"],
                color="yellow",
                scope="builtin",
            ),
            AgentDefinition(
                name="reviewer",
                description=(
                    "A code review agent that analyzes code quality, security, and best practices. "
                    "Use after writing code to get a thorough review."
                ),
                system_prompt=(
                    "You are Reviewer, a senior code reviewer. You analyze code for: "
                    "correctness, security vulnerabilities, performance issues, code style, "
                    "and best practices. Provide specific, actionable feedback with examples."
                ),
                tools=["read_file", "list_files", "grep_files", "glob_files"],
                color="magenta",
                scope="builtin",
            ),
            AgentDefinition(
                name="debugger",
                description=(
                    "A debugging specialist for diagnosing errors, test failures, and unexpected behavior. "
                    "Use when you have errors or bugs to investigate."
                ),
                system_prompt=(
                    "You are Debugger, an expert at diagnosing and fixing software issues. "
                    "You systematically analyze errors, trace execution paths, examine logs, "
                    "and identify root causes. You explain issues clearly and provide fixes."
                ),
                tools=["read_file", "write_file", "edit_file", "run_shell", "list_files", "grep_files"],
                color="red",
                scope="builtin",
            ),
            AgentDefinition(
                name="shell",
                description=(
                    "A shell operations agent for running commands, managing processes, and system tasks. "
                    "Use for build tasks, running tests, or system administration."
                ),
                system_prompt=(
                    "You are Shell, a system operations expert. You run shell commands safely, "
                    "manage files and processes, and automate system tasks. "
                    "Always explain what commands do before running them."
                ),
                tools=["run_shell", "read_file", "write_file", "list_files"],
                color="cyan",
                scope="builtin",
            ),
        ]
        for agent in builtins:
            self._agents[agent.name] = agent

    def load_from_dirs(self):
        """Load user, project, and built-in agents from disk."""
        dirs = []
        # Built-in agents from package (lowest priority)
        if BUILTIN_AGENTS_DIR.exists():
            dirs.append((BUILTIN_AGENTS_DIR, "builtin"))
        # User global agents
        if GLOBAL_AGENTS_DIR.exists():
            dirs.append((GLOBAL_AGENTS_DIR, "user"))
        # Project local agents (highest priority - can override)
        if PROJECT_AGENTS_DIR.exists():
            dirs.append((PROJECT_AGENTS_DIR, "project"))

        for dir_path, scope in dirs:
            for md_file in dir_path.glob("*.md"):
                try:
                    agent = AgentDefinition.from_markdown(md_file)
                    agent.scope = scope
                    agent.source_file = str(md_file)
                    self._agents[agent.name] = agent
                except Exception as e:
                    pass

    def get(self, name: str) -> Optional[AgentDefinition]:
        return self._agents.get(name)

    def list_all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def register(self, agent: AgentDefinition):
        self._agents[agent.name] = agent

    def save_agent(self, agent: AgentDefinition):
        """Save agent to disk."""
        if agent.scope == "user":
            path = GLOBAL_AGENTS_DIR / f"{agent.name}.md"
        else:
            PROJECT_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
            path = PROJECT_AGENTS_DIR / f"{agent.name}.md"
        path.write_text(agent.to_markdown())
        agent.source_file = str(path)
        self.register(agent)

    def delete_agent(self, name: str) -> bool:
        agent = self._agents.get(name)
        if not agent or agent.scope == "builtin":
            return False
        if agent.source_file and Path(agent.source_file).exists():
            Path(agent.source_file).unlink()
        del self._agents[name]
        return True
