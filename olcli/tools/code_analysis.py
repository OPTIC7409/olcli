"""
OLCLI Code Analysis Tools
Advanced tools for code understanding, parsing, and analysis.
"""

import ast
import re
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

from .builtins import ToolResult


@dataclass
class CodeSymbol:
    name: str
    type: str  # "function", "class", "method", "variable", "import"
    line: int
    end_line: int
    docstring: Optional[str] = None
    signature: Optional[str] = None
    decorators: list = field(default_factory=list)
    parent: Optional[str] = None


class CodeAnalyzer:
    """Python code analysis utilities."""

    @staticmethod
    def parse_file(path: str) -> Optional[ast.AST]:
        try:
            content = Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
            return ast.parse(content)
        except Exception:
            return None

    @staticmethod
    def extract_symbols(tree: ast.AST) -> list[CodeSymbol]:
        symbols = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbol = CodeSymbol(
                    name=node.name,
                    type="method" if node.args.args and node.args.args[0].arg in ('self', 'cls') else "function",
                    line=node.lineno,
                    end_line=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    signature=CodeAnalyzer._get_signature(node),
                    decorators=[ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else [],
                )
                symbols.append(symbol)
                
            elif isinstance(node, ast.ClassDef):
                symbol = CodeSymbol(
                    name=node.name,
                    type="class",
                    line=node.lineno,
                    end_line=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    decorators=[ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else [],
                )
                symbols.append(symbol)
                
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.append(CodeSymbol(
                        name=alias.name,
                        type="import",
                        line=node.lineno,
                        end_line=node.lineno,
                    ))
                    
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    symbols.append(CodeSymbol(
                        name=f"{module}.{alias.name}",
                        type="import",
                        line=node.lineno,
                        end_line=node.lineno,
                    ))
        
        return symbols

    @staticmethod
    def _get_signature(node: ast.FunctionDef) -> str:
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation and hasattr(ast, 'unparse'):
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        
        # Handle *args and **kwargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
            
        return f"({', '.join(args)})"

    @staticmethod
    def calculate_complexity(tree: ast.AST) -> dict:
        """Calculate cyclomatic complexity."""
        complexity = 1
        function_complexity = {}
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, 
                                        ast.ExceptHandler, ast.With,
                                        ast.Assert, ast.comprehension)):
                        func_complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        func_complexity += len(child.values) - 1
                function_complexity[node.name] = func_complexity
                complexity += func_complexity - 1
                
        return {
            "total_complexity": complexity,
            "functions": function_complexity,
        }


# â”€â”€ Tool Handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def analyze_code_structure(path: str) -> ToolResult:
    """Analyze Python code structure and return symbols."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    
    tree = CodeAnalyzer.parse_file(str(p))
    if not tree:
        return ToolResult(success=False, output="", error="Failed to parse file")
    
    symbols = CodeAnalyzer.extract_symbols(tree)
    complexity = CodeAnalyzer.calculate_complexity(tree)
    
    # Group symbols by type
    functions = [s for s in symbols if s.type == "function"]
    methods = [s for s in symbols if s.type == "method"]
    classes = [s for s in symbols if s.type == "class"]
    imports = [s for s in symbols if s.type == "import"]
    
    lines = [
        f"# Code Analysis: {p.name}",
        "",
        f"**File**: {p}",
        f"**Total Complexity**: {complexity['total_complexity']}",
        "",
        "## Classes",
    ]
    
    for cls in classes:
        lines.append(f"- `{cls.name}` (lines {cls.line}-{cls.end_line})")
        if cls.docstring:
            lines.append(f"  > {cls.docstring.split(chr(10))[0][:80]}")
    
    lines.extend(["", "## Functions"])
    for func in functions:
        comp = complexity['functions'].get(func.name, 1)
        lines.append(f"- `{func.name}{func.signature or '()'}` (lines {func.line}-{func.end_line}, complexity: {comp})")
        if func.docstring:
            lines.append(f"  > {func.docstring.split(chr(10))[0][:80]}")
    
    if methods:
        lines.extend(["", "## Methods"])
        for method in methods:
            lines.append(f"- `{method.name}{method.signature or '()'}` (lines {method.line}-{method.end_line})")
    
    lines.extend(["", "## Imports"])
    for imp in imports[:20]:  # Limit imports
        lines.append(f"- `{imp.name}`")
    if len(imports) > 20:
        lines.append(f"- ... and {len(imports) - 20} more")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={
            "functions": len(functions),
            "methods": len(methods),
            "classes": len(classes),
            "imports": len(imports),
            "complexity": complexity,
        }
    )


def find_symbol_definitions(path: str, symbol_name: str) -> ToolResult:
    """Find where a symbol (function/class) is defined."""
    p = Path(path).expanduser()
    if p.is_file():
        files = [p]
    else:
        files = list(p.rglob("*.py"))
    
    matches = []
    for file in files:
        try:
            tree = CodeAnalyzer.parse_file(str(file))
            if not tree:
                continue
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if node.name == symbol_name:
                        docstring = ast.get_docstring(node)
                        matches.append({
                            "file": str(file),
                            "line": node.lineno,
                            "type": "class" if isinstance(node, ast.ClassDef) else "function",
                            "docstring": docstring.split("\n")[0] if docstring else None,
                        })
        except Exception:
            continue
    
    if not matches:
        return ToolResult(success=True, output=f"No definitions found for '{symbol_name}'")
    
    lines = [f"# Definitions of '{symbol_name}'", ""]
    for m in matches:
        lines.append(f"- `{m['type']}` in `{m['file']}`:{m['line']}")
        if m['docstring']:
            lines.append(f"  > {m['docstring']}")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"matches": matches},
    )


def extract_imports(path: str) -> ToolResult:
    """Extract all imports from a Python file or directory."""
    p = Path(path).expanduser()
    
    if p.is_file():
        files = [p]
    else:
        files = list(p.rglob("*.py"))
    
    all_imports = {}
    for file in files:
        try:
            tree = CodeAnalyzer.parse_file(str(file))
            if not tree:
                continue
            
            file_imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        file_imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            file_imports.append(module)
                        else:
                            file_imports.append(f"{module}.{alias.name}")
            
            if file_imports:
                all_imports[str(file)] = file_imports
        except Exception:
            continue
    
    # Aggregate
    standard_lib = []
    third_party = []
    local = []
    
    stdlib_modules = {
        "os", "sys", "json", "re", "pathlib", "typing", "dataclasses",
        "collections", "itertools", "functools", "datetime", "time",
        "math", "random", "hashlib", "base64", "urllib", "http",
        "socket", "subprocess", "tempfile", "shutil", "glob", "fnmatch",
        "inspect", "textwrap", "string", "enum", "abc", "copy", "pickle",
        "csv", "xml", "html", "sqlite3", "uuid", "warnings", "contextlib",
        "asyncio", "concurrent", "multiprocessing", "threading", "queue",
    }
    
    for file, imports in all_imports.items():
        for imp in imports:
            base = imp.split(".")[0]
            if base in stdlib_modules:
                standard_lib.append(imp)
            elif base.startswith(".") or "src" in imp:
                local.append(imp)
            else:
                third_party.append(imp)
    
    lines = [
        f"# Import Analysis",
        "",
        f"**Files analyzed**: {len(all_imports)}",
        "",
        "## Standard Library",
    ]
    for imp in sorted(set(standard_lib)):
        lines.append(f"- `{imp}`")
    
    lines.extend(["", "## Third Party"])
    for imp in sorted(set(third_party)):
        lines.append(f"- `{imp}`")
    
    if local:
        lines.extend(["", "## Local/Project"])
        for imp in sorted(set(local)):
            lines.append(f"- `{imp}`")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={
            "standard_lib": list(set(standard_lib)),
            "third_party": list(set(third_party)),
            "local": list(set(local)),
        }
    )


def get_function_call_graph(path: str, function_name: str = None) -> ToolResult:
    """Build a call graph for functions in a file."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    
    tree = CodeAnalyzer.parse_file(str(p))
    if not tree:
        return ToolResult(success=False, output="", error="Failed to parse file")
    
    # Build call graph
    calls = {}
    current_func = None
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            current_func = node.name
            calls[current_func] = []
        
        if isinstance(node, ast.Call) and current_func:
            if isinstance(node.func, ast.Name):
                calls[current_func].append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls[current_func].append(node.func.attr)
    
    lines = [f"# Call Graph: {p.name}", ""]
    
    if function_name:
        # Show just this function and what it calls
        if function_name in calls:
            lines.append(f"## `{function_name}` calls:")
            for call in set(calls[function_name]):
                lines.append(f"- `{call}`")
        else:
            lines.append(f"Function `{function_name}` not found")
    else:
        # Show all
        for func, called in calls.items():
            if called:
                lines.append(f"## `{func}`")
                for call in set(called):
                    lines.append(f"  â†’ `{call}`")
                lines.append("")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"call_graph": calls},
    )
