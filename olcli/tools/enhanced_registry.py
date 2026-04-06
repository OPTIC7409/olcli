"""
OLCLI Enhanced Tool Registry
Combines all tools: builtins, code analysis, git tools, and new advanced tools.
"""

import os
import re
import json
import ast
import subprocess
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

from .builtins import ToolRegistry as BaseToolRegistry, ToolResult
from .code_analysis import CodeAnalyzer, analyze_code_structure, find_symbol_definitions, extract_imports, get_function_call_graph
from .git_tools import git_status, git_log, git_diff, git_blame, git_branch_info, git_contributors
from .batch_ops import batch_read_files, batch_edit_files, batch_rename_files, find_and_replace_in_files, summarize_files
from .scaffolding import generate_from_template, scaffold_project, list_templates
from .workflows import WorkflowRunner, create_task_list, update_task_status, generate_checklist, list_workflows


class EnhancedToolRegistry(BaseToolRegistry):
    """Extended tool registry with all available tools."""
    
    def __init__(self, safe_mode: bool = True, auto_approve: bool = False):
        super().__init__(safe_mode, auto_approve)
        self._register_code_analysis_tools()
        self._register_git_tools()
        self._register_advanced_tools()
        self._register_batch_ops()
        self._register_scaffolding()
        self._register_workflow_tools()
    
    def _register_code_analysis_tools(self):
        """Register Python code analysis tools."""
        self.register(
            name="analyze_code",
            description="Analyze Python code structure: functions, classes, imports, complexity.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Path to Python file"},
                },
            },
            handler=self._analyze_code,
        )
        self.register(
            name="find_symbol",
            description="Find where a function or class is defined across the codebase.",
            parameters={
                "type": "object",
                "required": ["path", "symbol_name"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory to search"},
                    "symbol_name": {"type": "string", "description": "Name of function/class to find"},
                },
            },
            handler=self._find_symbol,
        )
        self.register(
            name="extract_imports",
            description="Extract and categorize all imports from Python files.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory to analyze"},
                },
            },
            handler=self._extract_imports,
        )
        self.register(
            name="call_graph",
            description="Build a function call graph showing what functions call what.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Python file to analyze"},
                    "function_name": {"type": "string", "description": "Specific function to analyze (optional)"},
                },
            },
            handler=self._call_graph,
        )
    
    def _register_git_tools(self):
        """Register git repository tools."""
        self.register(
            name="git_status",
            description="Get git status: staged, unstaged, and untracked files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path (default: current)"},
                },
            },
            handler=self._git_status,
        )
        self.register(
            name="git_log",
            description="Get git commit history with filtering options.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path"},
                    "n": {"type": "integer", "description": "Number of commits (default 10)"},
                    "author": {"type": "string", "description": "Filter by author"},
                    "since": {"type": "string", "description": "Show commits since date (e.g., '1 week ago')"},
                },
            },
            handler=self._git_log,
        )
        self.register(
            name="git_diff",
            description="Show git diff for changes.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path"},
                    "staged": {"type": "boolean", "description": "Show staged changes"},
                    "file": {"type": "string", "description": "Specific file to diff"},
                },
            },
            handler=self._git_diff,
        )
        self.register(
            name="git_blame",
            description="Show who wrote each line of a file.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "line_start": {"type": "integer", "description": "Starting line"},
                    "line_end": {"type": "integer", "description": "Ending line"},
                },
            },
            handler=self._git_blame,
        )
        self.register(
            name="git_branch_info",
            description="Get information about git branches.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path"},
                },
            },
            handler=self._git_branch_info,
        )
        self.register(
            name="git_contributors",
            description="Get top contributors to the repository.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path"},
                    "n": {"type": "integer", "description": "Number of contributors (default 10)"},
                },
            },
            handler=self._git_contributors,
        )
    
    def _register_advanced_tools(self):
        """Register new advanced tools."""
        self.register(
            name="count_lines",
            description="Count lines of code in files (SLOC, comments, blank lines).",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory"},
                    "pattern": {"type": "string", "description": "File pattern (e.g., '*.py')"},
                },
            },
            handler=self._count_lines,
        )
        self.register(
            name="find_todos",
            description="Find TODO, FIXME, HACK, XXX comments in code.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory"},
                    "pattern": {"type": "string", "description": "File pattern"},
                },
            },
            handler=self._find_todos,
        )
        self.register(
            name="check_syntax",
            description="Check Python syntax without executing.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Python file path"},
                },
            },
            handler=self._check_syntax,
        )
        self.register(
            name="get_dependencies",
            description="Extract dependencies from requirements.txt, pyproject.toml, package.json, etc.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Project directory"},
                },
            },
            handler=self._get_dependencies,
        )
        self.register(
            name="search_docs",
            description="Search documentation files (README, CHANGELOG, etc.).",
            parameters={
                "type": "object",
                "required": ["path", "query"],
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "query": {"type": "string", "description": "Search term"},
                },
            },
            handler=self._search_docs,
        )
        self.register(
            name="generate_summary",
            description="Generate a summary of project structure and key files.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Project directory"},
                    "max_depth": {"type": "integer", "description": "Max directory depth (default 3)"},
                },
            },
            handler=self._generate_summary,
        )
        self.register(
            name="compare_directories",
            description="Compare two directories and show differences.",
            parameters={
                "type": "object",
                "required": ["dir_a", "dir_b"],
                "properties": {
                    "dir_a": {"type": "string", "description": "First directory"},
                    "dir_b": {"type": "string", "description": "Second directory"},
                    "pattern": {"type": "string", "description": "File pattern to compare"},
                },
            },
            handler=self._compare_directories,
        )
        self.register(
            name="find_duplicate_code",
            description="Find potentially duplicate or similar code blocks.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "min_lines": {"type": "integer", "description": "Minimum lines to consider (default 5)"},
                },
            },
            handler=self._find_duplicate_code,
        )
        self.register(
            name="run_tests",
            description="Run tests using pytest or unittest and return results.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Test directory or file"},
                    "pattern": {"type": "string", "description": "Test pattern (e.g., 'test_*.py')"},
                    "verbose": {"type": "boolean", "description": "Verbose output"},
                },
            },
            handler=self._run_tests,
            requires_approval=True,
        )
        self.register(
            name="check_types",
            description="Run type checking with mypy if available.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory to check"},
                },
            },
            handler=self._check_types,
            requires_approval=True,
        )
        self.register(
            name="format_code",
            description="Format code with black or autopep8 if available.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory to format"},
                    "check": {"type": "boolean", "description": "Only check, don't format"},
                },
            },
            handler=self._format_code,
            requires_approval=True,
        )
        self.register(
            name="lint_code",
            description="Run pylint or flake8 on code.",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File or directory to lint"},
                },
            },
            handler=self._lint_code,
            requires_approval=True,
        )
    
    # â”€â”€ Tool Handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    
    def _analyze_code(self, path: str) -> ToolResult:
        return analyze_code_structure(path)
    
    def _find_symbol(self, path: str, symbol_name: str) -> ToolResult:
        return find_symbol_definitions(path, symbol_name)
    
    def _extract_imports(self, path: str) -> ToolResult:
        return extract_imports(path)
    
    def _call_graph(self, path: str, function_name: str = None) -> ToolResult:
        return get_function_call_graph(path, function_name)
    
    def _git_status(self, path: str = ".") -> ToolResult:
        return git_status(path)
    
    def _git_log(self, path: str = ".", n: int = 10, author: str = None, since: str = None) -> ToolResult:
        return git_log(path, n, author, since)
    
    def _git_diff(self, path: str = ".", staged: bool = False, file: str = None) -> ToolResult:
        return git_diff(path, staged, file)
    
    def _git_blame(self, path: str, line_start: int = None, line_end: int = None) -> ToolResult:
        return git_blame(path, line_start, line_end)
    
    def _git_branch_info(self, path: str = ".") -> ToolResult:
        return git_branch_info(path)
    
    def _git_contributors(self, path: str = ".", n: int = 10) -> ToolResult:
        return git_contributors(path, n)
    
    def _count_lines(self, path: str, pattern: str = None) -> ToolResult:
        """Count lines of code."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        total_stats = {"files": 0, "code": 0, "comments": 0, "blank": 0, "total": 0}
        
        if p.is_file():
            files = [p]
        else:
            glob_pat = f"**/{pattern}" if pattern else "**/*"
            files = [f for f in p.glob(glob_pat) if f.is_file()]
        
        for f in files[:1000]:  # Limit to prevent timeout
            try:
                content = f.read_text(errors="replace")
                lines = content.splitlines()
                stats = {"code": 0, "comments": 0, "blank": 0, "total": len(lines)}
                
                in_multiline_comment = False
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        stats["blank"] += 1
                    elif stripped.startswith("#") or in_multiline_comment:
                        stats["comments"] += 1
                        if '"""' in stripped or "'''" in stripped:
                            in_multiline_comment = not in_multiline_comment
                    elif '"""' in stripped or "'''" in stripped:
                        stats["comments"] += 1
                        in_multiline_comment = not in_multiline_comment
                    else:
                        stats["code"] += 1
                
                total_stats["files"] += 1
                for key in ["code", "comments", "blank", "total"]:
                    total_stats[key] += stats[key]
            except Exception:
                continue
        
        output = [
            f"# Line Count Summary",
            f"",
            f"Files analyzed: {total_stats['files']}",
            f"Total lines: {total_stats['total']:,}",
            f"Code lines: {total_stats['code']:,}",
            f"Comment lines: {total_stats['comments']:,}",
            f"Blank lines: {total_stats['blank']:,}",
        ]
        if total_stats['total'] > 0:
            code_pct = total_stats['code'] / total_stats['total'] * 100
            output.append(f"Code percentage: {code_pct:.1f}%")
        
        return ToolResult(
            success=True,
            output="\n".join(output),
            metadata=total_stats,
        )
    
    def _find_todos(self, path: str, pattern: str = None) -> ToolResult:
        """Find TODO/FIXME comments."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        todo_pattern = re.compile(r'(TODO|FIXME|HACK|XXX|BUG|NOTE)[\s:]*(.+)', re.IGNORECASE)
        todos = []
        
        if p.is_file():
            files = [p]
        else:
            glob_pat = f"**/{pattern}" if pattern else "**/*"
            files = [f for f in p.rglob(glob_pat) if f.is_file()]
        
        for f in files[:500]:
            try:
                content = f.read_text(errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    match = todo_pattern.search(line)
                    if match:
                        todos.append({
                            "file": str(f),
                            "line": i,
                            "type": match.group(1).upper(),
                            "text": match.group(2).strip()[:100],
                        })
            except Exception:
                continue
        
        if not todos:
            return ToolResult(success=True, output="No TODO/FIXME comments found.")
        
        lines = [f"# Found {len(todos)} TODOs/FIXMEs", ""]
        for t in todos[:50]:
            lines.append(f"[{t['type']}] {t['file']}:{t['line']}")
            lines.append(f"  {t['text']}")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"todos": todos},
        )
    
    def _check_syntax(self, path: str) -> ToolResult:
        """Check Python syntax."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            ast.parse(content)
            return ToolResult(success=True, output=f"âœ“ Syntax OK: {p.name}")
        except SyntaxError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Syntax error at line {e.lineno}, col {e.offset}: {e.msg}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _get_dependencies(self, path: str) -> ToolResult:
        """Extract project dependencies."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        deps = {}
        
        # requirements.txt
        req_file = p / "requirements.txt"
        if req_file.exists():
            deps["requirements.txt"] = [
                line.strip() for line in req_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]
        
        # pyproject.toml
        pyproject = p / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                    if "project" in data and "dependencies" in data["project"]:
                        deps["pyproject.toml"] = data["project"]["dependencies"]
            except Exception:
                pass
        
        # package.json
        pkg_json = p / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                deps["package.json"] = {
                    "dependencies": list(data.get("dependencies", {}).keys()),
                    "devDependencies": list(data.get("devDependencies", {}).keys()),
                }
            except Exception:
                pass
        
        lines = ["# Project Dependencies", ""]
        for source, items in deps.items():
            lines.append(f"## {source}")
            if isinstance(items, list):
                for item in items:
                    lines.append(f"- {item}")
            elif isinstance(items, dict):
                for key, values in items.items():
                    lines.append(f"### {key}")
                    for v in values:
                        lines.append(f"- {v}")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines) if len(lines) > 2 else "No dependency files found.",
            metadata=deps,
        )
    
    def _search_docs(self, path: str, query: str) -> ToolResult:
        """Search documentation files."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        doc_patterns = ["README*", "CHANGELOG*", "CONTRIBUTING*", "LICENSE*", "*.md", "*.rst", "*.txt"]
        matches = []
        
        for pattern in doc_patterns:
            for f in p.rglob(pattern):
                if f.is_file():
                    try:
                        content = f.read_text(errors="replace").lower()
                        if query.lower() in content:
                            # Find context
                            idx = content.find(query.lower())
                            start = max(0, idx - 50)
                            end = min(len(content), idx + len(query) + 50)
                            context = content[start:end]
                            matches.append({
                                "file": str(f),
                                "context": context.replace("\n", " "),
                            })
                    except Exception:
                        continue
        
        if not matches:
            return ToolResult(success=True, output=f"No matches for '{query}' in documentation.")
        
        lines = [f"# Documentation Search: '{query}'", ""]
        for m in matches[:20]:
            lines.append(f"## {m['file']}")
            lines.append(f"...{m['context']}...")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"matches": matches},
        )
    
    def _generate_summary(self, path: str, max_depth: int = 3) -> ToolResult:
        """Generate project summary."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        lines = [f"# Project Summary: {p.name}", ""]
        
        # Directory structure
        lines.append("## Directory Structure")
        lines.append("```")
        
        def add_tree(dir_path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return
            entries = sorted([e for e in dir_path.iterdir() if not e.name.startswith(".")][:30])
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "â””â”€â”€ " if is_last else "â”œâ”€â”€ "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir():
                    new_prefix = prefix + ("    " if is_last else "â”‚   ")
                    add_tree(entry, new_prefix, depth + 1)
        
        add_tree(p)
        lines.append("```")
        lines.append("")
        
        # Key files
        key_files = ["README.md", "pyproject.toml", "setup.py", "requirements.txt", 
                     "package.json", "Makefile", ".gitignore"]
        found = [f for f in key_files if (p / f).exists()]
        if found:
            lines.append("## Key Files")
            for f in found:
                lines.append(f"- {f}")
            lines.append("")
        
        # File counts by extension
        extensions = {}
        for f in p.rglob("*"):
            if f.is_file() and not any(part.startswith(".") for part in f.parts):
                ext = f.suffix or "(no extension)"
                extensions[ext] = extensions.get(ext, 0) + 1
        
        if extensions:
            lines.append("## File Types")
            for ext, count in sorted(extensions.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"- {ext}: {count} files")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"key_files": found, "extensions": extensions},
        )
    
    def _compare_directories(self, dir_a: str, dir_b: str, pattern: str = None) -> ToolResult:
        """Compare two directories."""
        a = Path(dir_a).expanduser()
        b = Path(dir_b).expanduser()
        
        if not a.exists() or not b.exists():
            return ToolResult(success=False, output="", error="One or both directories not found")
        
        files_a = set()
        files_b = set()
        
        glob_pat = f"**/{pattern}" if pattern else "**/*"
        
        for f in a.rglob(glob_pat):
            if f.is_file():
                files_a.add(f.relative_to(a))
        for f in b.rglob(glob_pat):
            if f.is_file():
                files_b.add(f.relative_to(b))
        
        only_in_a = files_a - files_b
        only_in_b = files_b - files_a
        in_both = files_a & files_b
        
        lines = [f"# Directory Comparison", f"", f"A: {a}", f"B: {b}", ""]
        
        lines.append(f"## Only in A ({len(only_in_a)} files)")
        for f in sorted(only_in_a)[:20]:
            lines.append(f"- {f}")
        if len(only_in_a) > 20:
            lines.append(f"... and {len(only_in_a) - 20} more")
        lines.append("")
        
        lines.append(f"## Only in B ({len(only_in_b)} files)")
        for f in sorted(only_in_b)[:20]:
            lines.append(f"- {f}")
        if len(only_in_b) > 20:
            lines.append(f"... and {len(only_in_b) - 20} more")
        lines.append("")
        
        lines.append(f"## In both ({len(in_both)} files)")
        for f in sorted(in_both)[:20]:
            lines.append(f"- {f}")
        if len(in_both) > 20:
            lines.append(f"... and {len(in_both) - 20} more")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={
                "only_in_a": len(only_in_a),
                "only_in_b": len(only_in_b),
                "in_both": len(in_both),
            },
        )
    
    def _find_duplicate_code(self, path: str, min_lines: int = 5) -> ToolResult:
        """Find duplicate code blocks."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        # Simple hash-based duplicate detection
        blocks = {}
        
        for f in p.rglob("*.py"):
            try:
                lines = f.read_text(errors="replace").splitlines()
                for i in range(len(lines) - min_lines + 1):
                    block = tuple(lines[i:i + min_lines])
                    block_hash = hash(block)
                    if block_hash not in blocks:
                        blocks[block_hash] = []
                    blocks[block_hash].append((str(f), i + 1))
            except Exception:
                continue
        
        duplicates = {h: locs for h, locs in blocks.items() if len(locs) > 1}
        
        if not duplicates:
            return ToolResult(success=True, output="No duplicate code blocks found.")
        
        lines = [f"# Potential Duplicates ({len(duplicates)} blocks)", ""]
        for h, locs in list(duplicates.items())[:20]:
            lines.append(f"## Block found {len(locs)} times:")
            for file, line in locs[:5]:
                lines.append(f"  - {file}:{line}")
            if len(locs) > 5:
                lines.append(f"  ... and {len(locs) - 5} more")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"duplicates": len(duplicates)},
        )
    
    def _run_tests(self, path: str = ".", pattern: str = None, verbose: bool = False) -> ToolResult:
        """Run tests with pytest."""
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Path not found: {path}")
        
        cmd = ["python", "-m", "pytest"] if self._has_pytest() else ["python", "-m", "unittest"]
        if pattern:
            cmd.extend(["-k", pattern] if "pytest" in cmd[-1] else [pattern])
        if verbose:
            cmd.append("-v")
        cmd.append(str(p))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout + (f"\n[stderr]\n{result.stderr}" if result.stderr else ""),
                error=None if result.returncode == 0 else f"Tests failed with code {result.returncode}",
                metadata={"returncode": result.returncode},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _check_types(self, path: str) -> ToolResult:
        """Run mypy type checking."""
        if not self._has_mypy():
            return ToolResult(success=False, output="", error="mypy not installed")
        
        try:
            result = subprocess.run(
                ["python", "-m", "mypy", path],
                capture_output=True, text=True, timeout=60
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout or "No type errors found!",
                error=None if result.returncode == 0 else "Type check failed",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _format_code(self, path: str, check: bool = False) -> ToolResult:
        """Format code with black."""
        if not self._has_black():
            return ToolResult(success=False, output="", error="black not installed")
        
        cmd = ["python", "-m", "black", "--check" if check else "", path]
        cmd = [c for c in cmd if c]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout or ("Would reformat files" if check else "Formatting complete"),
                error=None if result.returncode == 0 or check else "Formatting failed",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _lint_code(self, path: str) -> ToolResult:
        """Run pylint or flake8."""
        if self._has_pylint():
            cmd = ["python", "-m", "pylint", path]
        elif self._has_flake8():
            cmd = ["python", "-m", "flake8", path]
        else:
            return ToolResult(success=False, output="", error="No linter installed (pylint or flake8)")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout or "No linting issues!",
                error=None if result.returncode == 0 else "Linting found issues",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    # Helper methods
    def _has_pytest(self) -> bool:
        try:
            subprocess.run(["python", "-m", "pytest", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
    
    def _has_mypy(self) -> bool:
        try:
            subprocess.run(["python", "-m", "mypy", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
    
    def _has_black(self) -> bool:
        try:
            subprocess.run(["python", "-m", "black", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
    
    def _has_pylint(self) -> bool:
        try:
            subprocess.run(["python", "-m", "pylint", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
    
    def _has_flake8(self) -> bool:
        try:
            subprocess.run(["python", "-m", "flake8", "--version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def _register_batch_ops(self):
        """Register batch operation tools."""
        self.register(
            name="batch_read",
            description="Read multiple files at once with separators.",
            parameters={
                "type": "object",
                "required": ["paths"],
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths"},
                },
            },
            handler=self._batch_read,
        )
        self.register(
            name="batch_edit",
            description="Apply the same edit to multiple files.",
            parameters={
                "type": "object",
                "required": ["files"],
                "properties": {
                    "files": {"type": "array", "description": "List of {path, old_text, new_text} objects"},
                    "all_occurrences": {"type": "boolean", "description": "Replace all occurrences"},
                },
            },
            handler=self._batch_edit,
            requires_approval=True,
        )
        self.register(
            name="batch_rename",
            description="Rename multiple files at once.",
            parameters={
                "type": "object",
                "required": ["renames"],
                "properties": {
                    "renames": {"type": "array", "description": "List of {source, destination} objects"},
                },
            },
            handler=self._batch_rename,
            requires_approval=True,
        )
        self.register(
            name="find_and_replace",
            description="Find and replace text across multiple files.",
            parameters={
                "type": "object",
                "required": ["path", "find", "replace"],
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "find": {"type": "string", "description": "Text to find"},
                    "replace": {"type": "string", "description": "Replacement text"},
                    "pattern": {"type": "string", "description": "File pattern (default: *)"},
                    "case_sensitive": {"type": "boolean", "description": "Case sensitive search"},
                },
            },
            handler=self._find_and_replace,
            requires_approval=True,
        )
        self.register(
            name="summarize_files",
            description="Create a summary of multiple files (sizes, line counts).",
            parameters={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Directory to summarize"},
                    "pattern": {"type": "string", "description": "File pattern"},
                    "max_files": {"type": "integer", "description": "Max files to show (default 20)"},
                },
            },
            handler=self._summarize_files,
        )

    def _register_scaffolding(self):
        """Register scaffolding tools."""
        self.register(
            name="generate_template",
            description="Generate code from a template (python-class, python-test, dockerfile, etc.).",
            parameters={
                "type": "object",
                "required": ["template_name", "variables"],
                "properties": {
                    "template_name": {"type": "string", "description": "Template name"},
                    "variables": {"type": "object", "description": "Template variables"},
                },
            },
            handler=self._generate_template,
        )
        self.register(
            name="scaffold_project",
            description="Create a new project with standard structure.",
            parameters={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "Project name"},
                    "project_type": {"type": "string", "description": "Project type (default: python)"},
                    "path": {"type": "string", "description": "Parent directory (default: .)"},
                    "include_tests": {"type": "boolean", "description": "Include tests directory"},
                    "include_docs": {"type": "boolean", "description": "Include docs directory"},
                    "include_ci": {"type": "boolean", "description": "Include CI configuration"},
                },
            },
            handler=self._scaffold_project,
            requires_approval=True,
        )
        self.register(
            name="list_templates",
            description="List available code templates.",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=self._list_templates,
        )

    def _register_workflow_tools(self):
        """Register workflow automation tools."""
        self.register(
            name="create_task_list",
            description="Create a structured task list with status tracking.",
            parameters={
                "type": "object",
                "required": ["tasks"],
                "properties": {
                    "tasks": {"type": "array", "description": "List of {description, status, assignee} objects"},
                    "title": {"type": "string", "description": "List title"},
                },
            },
            handler=self._create_task_list,
        )
        self.register(
            name="generate_checklist",
            description="Generate a checklist for common tasks (pr-review, release, refactor, etc.).",
            parameters={
                "type": "object",
                "required": ["checklist_type"],
                "properties": {
                    "checklist_type": {"type": "string", "description": "Type of checklist"},
                    "items": {"type": "array", "description": "Custom items (optional)"},
                },
            },
            handler=self._generate_checklist,
        )
        self.register(
            name="list_workflows",
            description="List available predefined workflows.",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=self._list_workflows,
        )

    # Batch ops handlers
    def _batch_read(self, paths: list) -> ToolResult:
        return batch_read_files(paths)

    def _batch_edit(self, files: list, all_occurrences: bool = False) -> ToolResult:
        return batch_edit_files(files, all_occurrences)

    def _batch_rename(self, renames: list) -> ToolResult:
        return batch_rename_files(renames)

    def _find_and_replace(self, path: str, find: str, replace: str, 
                          pattern: str = "*", case_sensitive: bool = True) -> ToolResult:
        return find_and_replace_in_files(path, find, replace, pattern, case_sensitive)

    def _summarize_files(self, path: str, pattern: str = "*", max_files: int = 20) -> ToolResult:
        return summarize_files(path, pattern, max_files)

    # Scaffolding handlers
    def _generate_template(self, template_name: str, variables: dict) -> ToolResult:
        return generate_from_template(template_name, variables)

    def _scaffold_project(self, name: str, project_type: str = "python", path: str = ".",
                          include_tests: bool = True, include_docs: bool = True, 
                          include_ci: bool = False) -> ToolResult:
        return scaffold_project(name, project_type, path, include_tests, include_docs, include_ci)

    def _list_templates(self) -> ToolResult:
        return list_templates()

    # Workflow handlers
    def _create_task_list(self, tasks: list, title: str = "Task List") -> ToolResult:
        return create_task_list(tasks, title)

    def _generate_checklist(self, checklist_type: str, items: list = None) -> ToolResult:
        return generate_checklist(checklist_type, items)

    def _list_workflows(self) -> ToolResult:
        return list_workflows()
