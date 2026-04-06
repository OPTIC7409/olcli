"""
OLCLI Ollama Client
Wraps the Ollama API with streaming, tool-call loop, and session management.
Automatically falls back to plain chat mode for models that don't support tools.
"""

import json
import time
from typing import Generator, Optional, Callable, Any
from dataclasses import dataclass, field

import ollama as _ollama

from .config import OlcliConfig
from .tools import ToolRegistry, ToolResult


# ── Message ───────────────────────────────────────────────────────────────────
@dataclass
class Message:
    role: str          # "user" | "assistant" | "tool" | "system"
    content: str
    tool_calls: list = field(default_factory=list)
    tool_name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_ollama(self) -> dict:
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.role == "tool" and self.tool_name:
            d["tool_name"] = self.tool_name
        return d


# ── Session ───────────────────────────────────────────────────────────────────
class Session:
    def __init__(self, session_id: str, model: str, system_prompt: str):
        self.session_id = session_id
        self.model = model
        self.system_prompt = system_prompt
        self.messages: list[Message] = []
        self.created_at = time.time()
        self.tool_calls_total = 0

    def add(self, role: str, content: str, tool_calls=None, tool_name=None):
        msg = Message(
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_name=tool_name,
        )
        self.messages.append(msg)
        return msg

    def to_ollama_messages(self) -> list[dict]:
        msgs = [{"role": "system", "content": self.system_prompt}]
        for m in self.messages:
            msgs.append(m.to_ollama())
        return msgs

    def clear(self):
        self.messages.clear()

    def token_estimate(self) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        total = len(self.system_prompt)
        for m in self.messages:
            total += len(m.content)
        return total // 4

    def compact(self, keep_last: int = 10):
        """Keep only the most recent messages to save context."""
        if len(self.messages) > keep_last:
            self.messages = self.messages[-keep_last:]


# ── Callbacks ─────────────────────────────────────────────────────────────────
@dataclass
class ClientCallbacks:
    on_token: Optional[Callable[[str], None]] = None
    on_tool_call: Optional[Callable[[str, dict], None]] = None
    on_tool_result: Optional[Callable[[str, ToolResult], None]] = None
    on_tool_approval: Optional[Callable[[str, dict], bool]] = None
    on_thinking: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None
    on_no_tools: Optional[Callable[[str], None]] = None  # called when model doesn't support tools


# ── OllamaClient ─────────────────────────────────────────────────────────────
class OllamaClient:
    # Class-level cache: model name -> supports_tools (bool)
    _tools_support_cache: dict[str, bool] = {}

    def __init__(self, config: OlcliConfig, tools: ToolRegistry,
                 callbacks: Optional[ClientCallbacks] = None):
        self.config = config
        self.tools = tools
        self.callbacks = callbacks or ClientCallbacks()
        self._client = _ollama.Client(host=config.host)

    def list_models(self) -> list[str]:
        try:
            resp = self._client.list()
            return [m.model for m in resp.models]
        except Exception:
            return []

    def check_connection(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def model_supports_tools(self, model: str) -> bool:
        """Return cached tool-support status for a model, or True if unknown."""
        return self._tools_support_cache.get(model, True)

    def _mark_no_tools(self, model: str):
        """Mark a model as not supporting tools and notify via callback."""
        self._tools_support_cache[model] = False
        if self.callbacks.on_no_tools:
            self.callbacks.on_no_tools(model)

    @staticmethod
    def _is_tools_unsupported_error(exc: Exception) -> bool:
        """Detect the Ollama 400 'does not support tools' error."""
        msg = str(exc).lower()
        return (
            "does not support tools" in msg
            or ("400" in msg and "tool" in msg)
            or "tool" in msg and "not support" in msg
        )

    def chat(
        self,
        session: Session,
        user_message: str,
        tools_allowed: Optional[list] = None,
        tools_disallowed: Optional[list] = None,
        max_iterations: int = None,
    ) -> str:
        """
        Send a user message and run the full tool-call loop.
        Falls back to plain chat if the model doesn't support tools.
        Returns the final assistant text response.
        """
        max_iter = max_iterations or self.config.max_tool_iterations
        session.add("user", user_message)

        # Only pass tools if the model is known to support them
        use_tools = self.model_supports_tools(session.model)
        tool_schemas = self.tools.get_schemas(
            allowed=tools_allowed,
            disallowed=tools_disallowed,
        ) if use_tools else []

        iteration = 0
        final_response = ""

        while iteration < max_iter:
            iteration += 1
            messages = session.to_ollama_messages()

            try:
                if self.config.stream:
                    response_text, tool_calls, thinking = self._stream_response(
                        session.model, messages, tool_schemas
                    )
                else:
                    response_text, tool_calls, thinking = self._blocking_response(
                        session.model, messages, tool_schemas
                    )
            except Exception as e:
                if self._is_tools_unsupported_error(e) and tool_schemas:
                    # Model doesn't support tools — disable and retry without them
                    self._mark_no_tools(session.model)
                    tool_schemas = []
                    # Retry this iteration without tools
                    try:
                        if self.config.stream:
                            response_text, tool_calls, thinking = self._stream_response(
                                session.model, messages, []
                            )
                        else:
                            response_text, tool_calls, thinking = self._blocking_response(
                                session.model, messages, []
                            )
                    except Exception as e2:
                        if self.callbacks.on_error:
                            self.callbacks.on_error(str(e2))
                        raise
                else:
                    raise

            if thinking and self.callbacks.on_thinking:
                self.callbacks.on_thinking(thinking)

            # If no tool calls, we're done
            if not tool_calls:
                session.add("assistant", response_text)
                final_response = response_text
                break

            # Handle tool calls
            session.add("assistant", response_text, tool_calls=tool_calls)

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})

                if self.callbacks.on_tool_call:
                    self.callbacks.on_tool_call(tool_name, tool_args)

                # Check approval
                if self.tools.requires_approval(tool_name):
                    approved = True
                    if self.callbacks.on_tool_approval:
                        approved = self.callbacks.on_tool_approval(tool_name, tool_args)
                    if not approved:
                        result = ToolResult(
                            success=False, output="",
                            error="Tool execution denied by user."
                        )
                    else:
                        result = self.tools.execute(tool_name, tool_args)
                else:
                    result = self.tools.execute(tool_name, tool_args)

                session.tool_calls_total += 1

                if self.callbacks.on_tool_result:
                    self.callbacks.on_tool_result(tool_name, result)

                session.add(
                    "tool",
                    result.to_str(),
                    tool_name=tool_name,
                )
        else:
            # Hit max iterations
            final_response = (
                f"[Reached maximum tool iterations ({max_iter}). "
                "Last response may be incomplete.]"
            )

        return final_response

    def _stream_response(
        self, model: str, messages: list[dict], tools: list[dict]
    ) -> tuple[str, list, str]:
        """Stream a response and collect text + tool calls."""
        text_parts = []
        thinking_parts = []
        tool_calls = []

        stream = self._client.chat(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            stream=True,
            options={
                "temperature": self.config.temperature,
                "num_ctx": self.config.context_length,
            },
        )

        for chunk in stream:
            msg = chunk.get("message", {})

            # Thinking tokens (for models that support it)
            thinking = msg.get("thinking", "")
            if thinking:
                thinking_parts.append(thinking)

            # Text content
            content = msg.get("content", "")
            if content:
                text_parts.append(content)
                if self.callbacks.on_token:
                    self.callbacks.on_token(content)

            # Tool calls in chunk
            chunk_tools = msg.get("tool_calls", [])
            if chunk_tools:
                for tc in chunk_tools:
                    # Normalize tool call format
                    if hasattr(tc, "function"):
                        tool_calls.append({
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        })
                    elif isinstance(tc, dict):
                        tool_calls.append(tc)

        return "".join(text_parts), tool_calls, "".join(thinking_parts)

    def _blocking_response(
        self, model: str, messages: list[dict], tools: list[dict]
    ) -> tuple[str, list, str]:
        """Non-streaming response."""
        resp = self._client.chat(
            model=model,
            messages=messages,
            tools=tools if tools else None,
            stream=False,
            options={
                "temperature": self.config.temperature,
                "num_ctx": self.config.context_length,
            },
        )
        msg = resp.get("message", {})
        text = msg.get("content", "")
        thinking = msg.get("thinking", "")
        tool_calls_raw = msg.get("tool_calls", [])

        tool_calls = []
        for tc in tool_calls_raw:
            if hasattr(tc, "function"):
                tool_calls.append({
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })
            elif isinstance(tc, dict):
                tool_calls.append(tc)

        if text and self.callbacks.on_token:
            self.callbacks.on_token(text)

        return text, tool_calls, thinking
