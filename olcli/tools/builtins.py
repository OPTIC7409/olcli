"""
OLCLI Built-in Tools
All tools that agents can invoke: file ops, shell, search, glob/grep, diff.
"""

import os
import re
import glob
import json
import shlex
import difflib
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


# ── Tool Result ───────────────────────────────────────────────────────────────
@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_str(self) -> str:
        if self.success:
            return self.output
        return f"Error: {self.error}\n{self.output}".strip()


# ── Tool Registry ─────────────────────────────────────────────────────────────
class ToolRegistry:
    def __init__(self, safe_mode: bool = True, auto_approve: bool = False):
        self.safe_mode = safe_mode
        self.auto_approve = auto_approve
        self._tools: dict[str, dict] = {}
        self._handlers: dict[str, callable] = {}
        self._register_all()

    def _register_all(self):
        self.register(
            name="read_file",
            description="Read the contents of a file at the given path.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path to read"},
                    "start_line": {"type": "integer", "description": "First line to read (1-indexed, optional)"},
                    "end_line": {"type": "integer", "description": "Last line to read (inclusive, optional)"},
                },
            },
            handler=self._read_file,
        )
        self.register(
            name="write_file",
            description="Write content to a file, creating it if it doesn't exist.",
            parameters={
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "append": {"type": "boolean", "description": "Append instead of overwrite (default false)"},
                },
            },
            handler=self._write_file,
            requires_approval=True,
        )
        self.register(
            name="edit_file",
            description="Make targeted edits to a file by replacing specific text.",
            parameters={
                "type": "object",
                "required": ["path", "old_text", "new_text"],
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                    "all_occurrences": {"type": "boolean", "description": "Replace all occurrences (default false)"},
                },
            },
            handler=self._edit_file,
            requires_approval=True,
        )
        self.register(
            name="list_files",
            description="List files and directories at a given path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current directory)"},
                    "recursive": {"type": "boolean", "description": "List recursively (default false)"},
                    "pattern": {"type": "string", "description": "Filter by glob pattern (e.g. '*.py')"},
                },
            },
            handler=self._list_files,
        )
        self.register(
            name="glob_files",
            description="Find files matching a glob pattern.",
            parameters={
                "type": "object",
                "required": ["pattern"],
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/*.ts')"},
                    "base_dir": {"type": "string", "description": "Base directory for the search (default: cwd)"},
                },
            },
            handler=self._glob_files,
        )
        self.register(
            name="grep_files",
            description="Search for a regex pattern in files.",
            parameters={
                "type": "object",
                "required": ["pattern"],
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "path": {"type": "string", "description": "File or directory to search (default: cwd)"},
                    "file_pattern": {"type": "string", "description": "Only search files matching this glob (e.g. '*.py')"},
                    "case_insensitive": {"type": "boolean", "description": "Case-insensitive search (default false)"},
                    "context_lines": {"type": "integer", "description": "Lines of context around matches (default 2)"},
                    "max_results": {"type": "integer", "description": "Maximum results to return (default 50)"},
                },
            },
            handler=self._grep_files,
        )
        self.register(
            name="run_shell",
            description="Run a shell command and return its output. Use for build tasks, tests, git operations, etc.",
            parameters={
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "cwd": {"type": "string", "description": "Working directory (default: current directory)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                },
            },
            handler=self._run_shell,
            requires_approval=True,
        )
        self.register(
            name="web_search",
            description="Search the web for information using DuckDuckGo.",
            parameters={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum results (default 5)"},
                },
            },
            handler=self._web_search,
        )
        self.register(
            name="diff_files",
            description="Show the diff between two files or between original and new content.",
            parameters={
                "type": "object",
                "properties": {
                    "file_a": {"type": "string", "description": "Path to first file"},
                    "file_b": {"type": "string", "description": "Path to second file"},
                    "text_a": {"type": "string", "description": "Original text (alternative to file_a)"},
                    "text_b": {"type": "string", "description": "New text (alternative to file_b)"},
                    "context_lines": {"type": "integer", "description": "Context lines in diff (default 3)"},
                },
            },
            handler=self._diff_files,
        )
        self.register(
            name="get_file_info",
            description="Get metadata about a file: size, modification time, line count, etc.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
            },
            handler=self._get_file_info,
        )
        self.register(
            name="delete_file",
            description="Delete a file or empty directory.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"},
                },
            },
            handler=self._delete_file,
            requires_approval=True,
        )
        self.register(
            name="move_file",
            description="Move or rename a file or directory.",
            parameters={
                "type": "object",
                "required": ["source", "destination"],
                "properties": {
                    "source": {"type": "string", "description": "Source path"},
                    "destination": {"type": "string", "description": "Destination path"},
                },
            },
            handler=self._move_file,
            requires_approval=True,
        )
        self.register(
            name="make_directory",
            description="Create a directory (and parent directories as needed).",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Directory path to create"},
                },
            },
            handler=self._make_directory,
            requires_approval=True,
        )

    def register(self, name: str, description: str, parameters: dict,
                 handler: callable, requires_approval: bool = False):
        self._tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
            "requires_approval": requires_approval,
        }
        self._handlers[name] = handler

    def get_schemas(self, allowed: Optional[list] = None,
                    disallowed: Optional[list] = None) -> list[dict]:
        """Return tool schemas for Ollama, filtered by allowed/disallowed lists."""
        schemas = []
        for name, tool in self._tools.items():
            if allowed and name not in allowed:
                continue
            if disallowed and name in disallowed:
                continue
            schemas.append({
                "type": tool["type"],
                "function": tool["function"],
            })
        return schemas

    def requires_approval(self, name: str) -> bool:
        tool = self._tools.get(name)
        if not tool:
            return False
        return tool.get("requires_approval", False) and self.safe_mode and not self.auto_approve

    def execute(self, name: str, arguments: dict) -> ToolResult:
        handler = self._handlers.get(name)
        if not handler:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        try:
            return handler(**arguments)
        except TypeError as e:
            return ToolResult(success=False, output="", error=f"Invalid arguments for {name}: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": t["function"]["description"],
                "requires_approval": t.get("requires_approval", False),
            }
            for name, t in self._tools.items()
        ]

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _read_file(self, path: str, start_line: int = None,
                   end_line: int = None) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path}")
        try:
            content = p.read_text(errors="replace")
            lines = content.splitlines(keepends=True)
            total = len(lines)
            if start_line is not None or end_line is not None:
                s = (start_line or 1) - 1
                e = end_line or total
                lines = lines[s:e]
                content = "".join(lines)
                return ToolResult(
                    success=True,
                    output=content,
                    metadata={"path": str(p), "total_lines": total,
                               "shown_lines": f"{s+1}-{min(e, total)}"},
                )
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(p), "lines": total, "size": p.stat().st_size},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _write_file(self, path: str, content: str, append: bool = False) -> ToolResult:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        try:
            with open(p, mode, encoding="utf-8") as f:
                f.write(content)
            action = "Appended to" if append else "Wrote"
            return ToolResult(
                success=True,
                output=f"{action} {p} ({len(content)} bytes)",
                metadata={"path": str(p), "bytes": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _edit_file(self, path: str, old_text: str, new_text: str,
                   all_occurrences: bool = False) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        try:
            original = p.read_text(encoding="utf-8", errors="replace")
            if old_text not in original:
                return ToolResult(
                    success=False, output="",
                    error=f"Text not found in file:\n{old_text[:200]}"
                )
            if all_occurrences:
                new_content = original.replace(old_text, new_text)
                count = original.count(old_text)
            else:
                new_content = original.replace(old_text, new_text, 1)
                count = 1
            p.write_text(new_content, encoding="utf-8")
            # Generate a brief diff
            diff = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{p.name}",
                tofile=f"b/{p.name}",
                n=2,
            ))
            diff_str = "".join(diff[:40])
            return ToolResult(
                success=True,
                output=f"Edited {p} ({count} replacement(s))\n\n{diff_str}",
                metadata={"path": str(p), "replacements": count},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _list_files(self, path: str = ".", recursive: bool = False,
                    pattern: str = None) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        try:
            if recursive:
                glob_pat = f"**/{pattern}" if pattern else "**/*"
                entries = sorted(p.glob(glob_pat))
            else:
                if pattern:
                    entries = sorted(p.glob(pattern))
                else:
                    entries = sorted(p.iterdir())

            lines = []
            for entry in entries[:500]:
                rel = entry.relative_to(p) if entry.is_relative_to(p) else entry
                suffix = "/" if entry.is_dir() else ""
                size = ""
                if entry.is_file():
                    try:
                        size = f"  ({entry.stat().st_size:,} bytes)"
                    except Exception:
                        pass
                lines.append(f"{rel}{suffix}{size}")

            output = "\n".join(lines) if lines else "(empty)"
            return ToolResult(
                success=True,
                output=output,
                metadata={"path": str(p), "count": len(lines)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _glob_files(self, pattern: str, base_dir: str = ".") -> ToolResult:
        base = Path(base_dir).expanduser()
        try:
            matches = sorted(base.glob(pattern))
            if not matches:
                return ToolResult(success=True, output="No files matched.",
                                  metadata={"count": 0})
            lines = [str(m.relative_to(base) if m.is_relative_to(base) else m)
                     for m in matches[:500]]
            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"count": len(lines), "pattern": pattern},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _grep_files(self, pattern: str, path: str = ".",
                    file_pattern: str = None, case_insensitive: bool = False,
                    context_lines: int = 2, max_results: int = 50) -> ToolResult:
        p = Path(path).expanduser()
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

        results = []
        files_to_search = []

        if p.is_file():
            files_to_search = [p]
        else:
            glob_pat = file_pattern or "*"
            files_to_search = list(p.rglob(glob_pat))

        for fpath in files_to_search:
            if not fpath.is_file():
                continue
            try:
                lines = fpath.read_text(errors="replace").splitlines()
                for i, line in enumerate(lines):
                    if compiled.search(line):
                        ctx_start = max(0, i - context_lines)
                        ctx_end = min(len(lines), i + context_lines + 1)
                        snippet = []
                        for j in range(ctx_start, ctx_end):
                            prefix = ">" if j == i else " "
                            snippet.append(f"{prefix} {j+1:4d}: {lines[j]}")
                        rel = str(fpath.relative_to(p) if fpath.is_relative_to(p) else fpath)
                        results.append(f"{rel}:{i+1}\n" + "\n".join(snippet))
                        if len(results) >= max_results:
                            break
            except Exception:
                continue
            if len(results) >= max_results:
                break

        if not results:
            return ToolResult(success=True, output="No matches found.",
                              metadata={"count": 0})
        output = "\n\n".join(results)
        return ToolResult(
            success=True,
            output=output,
            metadata={"matches": len(results), "pattern": pattern},
        )

    def _run_shell(self, command: str, cwd: str = None,
                   timeout: int = 30) -> ToolResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or os.getcwd(),
                timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            return ToolResult(
                success=result.returncode == 0,
                output=output.strip(),
                error=None if result.returncode == 0 else f"Exit code {result.returncode}",
                metadata={"returncode": result.returncode, "command": command},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _web_search(self, query: str, max_results: int = 5) -> ToolResult:
        """Search using DuckDuckGo Instant Answer API."""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "OLCLI/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            lines = []
            # Abstract
            if data.get("AbstractText"):
                lines.append(f"**Summary**: {data['AbstractText']}")
                if data.get("AbstractURL"):
                    lines.append(f"Source: {data['AbstractURL']}")

            # Related topics
            topics = data.get("RelatedTopics", [])[:max_results]
            if topics:
                lines.append("\n**Related Results:**")
                for t in topics:
                    if isinstance(t, dict) and t.get("Text"):
                        lines.append(f"- {t['Text']}")
                        if t.get("FirstURL"):
                            lines.append(f"  {t['FirstURL']}")

            if not lines:
                # Fallback: try HTML search snippet via DuckDuckGo lite
                url2 = f"https://html.duckduckgo.com/html/?q={encoded}"
                req2 = urllib.request.Request(url2, headers={"User-Agent": "OLCLI/1.0"})
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    html = resp2.read().decode("utf-8", errors="replace")
                # Extract result snippets
                snippet_re = re.compile(
                    r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL
                )
                title_re = re.compile(
                    r'class="result__a"[^>]*>(.*?)</a>', re.DOTALL
                )
                snippets = snippet_re.findall(html)[:max_results]
                titles = title_re.findall(html)[:max_results]
                for i, (title, snip) in enumerate(zip(titles, snippets)):
                    clean_title = re.sub(r"<[^>]+>", "", title).strip()
                    clean_snip = re.sub(r"<[^>]+>", "", snip).strip()
                    lines.append(f"{i+1}. **{clean_title}**\n   {clean_snip}")

            output = "\n".join(lines) if lines else "No results found."
            return ToolResult(success=True, output=output,
                              metadata={"query": query})
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _diff_files(self, file_a: str = None, file_b: str = None,
                    text_a: str = None, text_b: str = None,
                    context_lines: int = 3) -> ToolResult:
        try:
            if file_a and file_b:
                pa, pb = Path(file_a).expanduser(), Path(file_b).expanduser()
                lines_a = pa.read_text(errors="replace").splitlines(keepends=True)
                lines_b = pb.read_text(errors="replace").splitlines(keepends=True)
                from_name, to_name = str(pa), str(pb)
            elif text_a is not None and text_b is not None:
                lines_a = text_a.splitlines(keepends=True)
                lines_b = text_b.splitlines(keepends=True)
                from_name, to_name = "original", "modified"
            else:
                return ToolResult(success=False, output="",
                                  error="Provide either (file_a, file_b) or (text_a, text_b)")

            diff = list(difflib.unified_diff(
                lines_a, lines_b,
                fromfile=from_name, tofile=to_name,
                n=context_lines,
            ))
            output = "".join(diff) if diff else "No differences found."
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _get_file_info(self, path: str) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        try:
            stat = p.stat()
            import datetime
            info = {
                "path": str(p.resolve()),
                "type": "directory" if p.is_dir() else "file",
                "size_bytes": stat.st_size,
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            }
            if p.is_file():
                try:
                    content = p.read_text(errors="replace")
                    info["line_count"] = len(content.splitlines())
                    info["encoding"] = "utf-8"
                except Exception:
                    info["line_count"] = "N/A (binary)"
            output = "\n".join(f"{k}: {v}" for k, v in info.items())
            return ToolResult(success=True, output=output, metadata=info)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _delete_file(self, path: str) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        try:
            if p.is_dir():
                p.rmdir()
            else:
                p.unlink()
            return ToolResult(success=True, output=f"Deleted: {p}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _move_file(self, source: str, destination: str) -> ToolResult:
        src = Path(source).expanduser()
        dst = Path(destination).expanduser()
        if not src.exists():
            return ToolResult(success=False, output="", error=f"Source not found: {source}")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return ToolResult(success=True, output=f"Moved: {src} -> {dst}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _make_directory(self, path: str) -> ToolResult:
        p = Path(path).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, output=f"Created directory: {p}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
