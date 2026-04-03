"""
OLCLI Sub-Agent Orchestrator
Manages spawning, running, and coordinating sub-agents.
"""

import time
import uuid
from typing import Optional, Callable
from dataclasses import dataclass, field

from ..config import OlcliConfig, AgentDefinition, AgentRegistry
from ..client import OllamaClient, Session, ClientCallbacks
from ..tools.builtins import ToolRegistry


# ── Agent Run Result ──────────────────────────────────────────────────────────
@dataclass
class AgentRunResult:
    agent_name: str
    task: str
    output: str
    success: bool
    duration: float
    tool_calls: int
    session_id: str
    error: Optional[str] = None


# ── Orchestrator ──────────────────────────────────────────────────────────────
class AgentOrchestrator:
    def __init__(
        self,
        config: OlcliConfig,
        registry: AgentRegistry,
        tools: ToolRegistry,
        on_agent_start: Optional[Callable] = None,
        on_agent_end: Optional[Callable] = None,
        on_agent_token: Optional[Callable] = None,
        on_agent_tool: Optional[Callable] = None,
    ):
        self.config = config
        self.registry = registry
        self.tools = tools
        self.on_agent_start = on_agent_start
        self.on_agent_end = on_agent_end
        self.on_agent_token = on_agent_token
        self.on_agent_tool = on_agent_tool
        self._active_agents: dict[str, Session] = {}

    def run_agent(
        self,
        agent_name: str,
        task: str,
        context: Optional[str] = None,
        parent_session: Optional[Session] = None,
    ) -> AgentRunResult:
        """
        Spawn and run a sub-agent for a specific task.
        Returns the result when the agent completes.
        """
        agent_def = self.registry.get(agent_name)
        if not agent_def:
            return AgentRunResult(
                agent_name=agent_name,
                task=task,
                output="",
                success=False,
                duration=0,
                tool_calls=0,
                session_id="",
                error=f"Agent '{agent_name}' not found.",
            )

        model = agent_def.model or self.config.model
        session_id = f"agent-{agent_name}-{uuid.uuid4().hex[:8]}"

        # Build system prompt with optional context
        system_prompt = agent_def.system_prompt
        if context:
            system_prompt += f"\n\n## Context from parent session:\n{context}"

        session = Session(
            session_id=session_id,
            model=model,
            system_prompt=system_prompt,
        )
        self._active_agents[session_id] = session

        if self.on_agent_start:
            self.on_agent_start(agent_name, task, session_id)

        start = time.time()
        error = None
        output = ""

        try:
            callbacks = ClientCallbacks(
                on_token=lambda t: self.on_agent_token(agent_name, t) if self.on_agent_token else None,
                on_tool_call=lambda n, a: self.on_agent_tool(agent_name, n, a) if self.on_agent_tool else None,
                on_tool_approval=self._make_approval_handler(agent_def),
            )
            client = OllamaClient(self.config, self.tools, callbacks)

            output = client.chat(
                session=session,
                user_message=task,
                tools_allowed=agent_def.tools if agent_def.tools else None,
                tools_disallowed=agent_def.disallowed_tools if agent_def.disallowed_tools else None,
                max_iterations=agent_def.max_turns,
            )
            success = True
        except Exception as e:
            output = ""
            error = str(e)
            success = False

        duration = time.time() - start
        del self._active_agents[session_id]

        result = AgentRunResult(
            agent_name=agent_name,
            task=task,
            output=output,
            success=success,
            duration=duration,
            tool_calls=session.tool_calls_total,
            session_id=session_id,
            error=error,
        )

        if self.on_agent_end:
            self.on_agent_end(agent_name, result)

        return result

    def _make_approval_handler(self, agent_def: AgentDefinition):
        """Sub-agents in auto mode skip approval; otherwise inherit parent behavior."""
        def handler(tool_name: str, args: dict) -> bool:
            # For now, sub-agents auto-approve if safe_mode is off
            return not self.tools.safe_mode or self.tools.auto_approve
        return handler

    def list_active(self) -> list[str]:
        return list(self._active_agents.keys())

    def auto_delegate(
        self,
        task: str,
        parent_session: Session,
    ) -> Optional[AgentRunResult]:
        """
        Automatically pick the best agent for a task based on descriptions.
        Returns None if no suitable agent is found.
        """
        agents = self.registry.list_all()
        if not agents:
            return None

        # Build a simple scoring: check if task keywords match agent description
        task_lower = task.lower()
        best_agent = None
        best_score = 0

        keywords_map = {
            "explorer": ["search", "find", "explore", "look", "where", "list files", "grep", "locate"],
            "coder": ["write", "implement", "create", "code", "function", "class", "fix", "refactor", "add feature"],
            "researcher": ["research", "what is", "how does", "explain", "documentation", "learn about"],
            "reviewer": ["review", "check", "audit", "quality", "security", "best practice"],
            "debugger": ["debug", "error", "bug", "crash", "fail", "exception", "traceback", "broken"],
            "shell": ["run", "execute", "build", "test", "install", "deploy", "command"],
        }

        for agent in agents:
            score = 0
            kws = keywords_map.get(agent.name, [])
            for kw in kws:
                if kw in task_lower:
                    score += 1
            # Also check agent description
            desc_words = agent.description.lower().split()
            for word in task_lower.split():
                if word in desc_words:
                    score += 0.5
            if score > best_score:
                best_score = score
                best_agent = agent

        if best_agent and best_score >= 1:
            return self.run_agent(
                best_agent.name,
                task,
                parent_session=parent_session,
            )
        return None
