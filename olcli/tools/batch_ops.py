"""
OLCLI Batch Operations Tools
Tools for working with multiple files simultaneously.
"""

import re
from pathlib import Path
from typing import List, Dict, Any
from .builtins import ToolResult


def batch_read_files(paths: List[str]) -> ToolResult:
    """Read multiple files and return combined content with separators."""
    contents = []
    errors = []
    
    for path in paths:
        p = Path(path).expanduser()
        if not p.exists():
            errors.append(f"Not found: {path}")
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            contents.append(f"=== {path} ===\n{content}\n")
        except Exception as e:
            errors.append(f"Error reading {path}: {e}")
    
    output = "\n".join(contents)
    if errors:
        output += "\n\n# Errors:\n" + "\n".join(errors)
    
    return ToolResult(
        success=len(errors) < len(paths),
        output=output,
        error="\n".join(errors) if errors else None,
        metadata={"read": len(contents), "errors": len(errors)}
    )


def batch_edit_files(files: List[Dict[str, str]], all_occurrences: bool = False) -> ToolResult:
    """Apply the same edit to multiple files.
    
    files: List of dicts with 'path', 'old_text', 'new_text'
    """
    results = []
    success_count = 0
    
    for item in files:
        path = item.get("path")
        old_text = item.get("old_text")
        new_text = item.get("new_text")
        
        p = Path(path).expanduser()
        if not p.exists():
            results.append(f"âœ— {path}: File not found")
            continue
        
        try:
            original = p.read_text(encoding="utf-8", errors="replace")
            if old_text not in original:
                results.append(f"âœ— {path}: Text not found")
                continue
            
            if all_occurrences:
                new_content = original.replace(old_text, new_text)
                count = original.count(old_text)
            else:
                new_content = original.replace(old_text, new_text, 1)
                count = 1
            
            p.write_text(new_content, encoding="utf-8")
            results.append(f"âœ“ {path}: {count} replacement(s)")
            success_count += 1
        except Exception as e:
            results.append(f"âœ— {path}: {e}")
    
    return ToolResult(
        success=success_count > 0,
        output="\n".join(results),
        metadata={"success": success_count, "total": len(files)}
    )


def batch_rename_files(renames: List[Dict[str, str]]) -> ToolResult:
    """Rename multiple files.
    
    renames: List of dicts with 'source' and 'destination'
    """
    results = []
    success_count = 0
    
    for item in renames:
        src = Path(item["source"]).expanduser()
        dst = Path(item["destination"]).expanduser()
        
        if not src.exists():
            results.append(f"âœ— {src}: Source not found")
            continue
        
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            results.append(f"âœ“ {src.name} â†’ {dst.name}")
            success_count += 1
        except Exception as e:
            results.append(f"âœ— {src}: {e}")
    
    return ToolResult(
        success=success_count > 0,
        output="\n".join(results),
        metadata={"success": success_count, "total": len(renames)}
    )


def find_and_replace_in_files(
    path: str,
    find: str,
    replace: str,
    pattern: str = "*",
    case_sensitive: bool = True
) -> ToolResult:
    """Find and replace text across multiple files."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(re.escape(find), flags)
    
    matches = []
    files_changed = 0
    total_replacements = 0
    
    for f in p.rglob(pattern):
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            new_content, count = regex.subn(replace, content)
            
            if count > 0:
                f.write_text(new_content, encoding="utf-8")
                matches.append(f"{f}: {count} replacement(s)")
                files_changed += 1
                total_replacements += count
        except Exception as e:
            matches.append(f"âœ— {f}: {e}")
    
    output = f"# Find and Replace Results\n\n"
    output += f"Pattern: '{find}' â†’ '{replace}'\n"
    output += f"Files changed: {files_changed}\n"
    output += f"Total replacements: {total_replacements}\n\n"
    output += "\n".join(matches[:50])
    if len(matches) > 50:
        output += f"\n... and {len(matches) - 50} more files"
    
    return ToolResult(
        success=files_changed > 0,
        output=output,
        metadata={"files_changed": files_changed, "replacements": total_replacements}
    )


def summarize_files(path: str, pattern: str = "*", max_files: int = 20) -> ToolResult:
    """Create a summary of multiple files (sizes, line counts)."""
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(success=False, output="", error=f"Path not found: {path}")
    
    files = []
    for f in p.rglob(pattern):
        if f.is_file():
            try:
                stat = f.stat()
                content = f.read_text(errors="replace")
                lines = len(content.splitlines())
                files.append({
                    "path": str(f.relative_to(p)),
                    "size": stat.st_size,
                    "lines": lines,
                })
            except Exception:
                pass
    
    # Sort by size
    files.sort(key=lambda x: x["size"], reverse=True)
    
    total_size = sum(f["size"] for f in files)
    total_lines = sum(f["lines"] for f in files)
    
    lines = [
        f"# File Summary",
        f"",
        f"Total files: {len(files)}",
        f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)",
        f"Total lines: {total_lines:,}",
        f"",
        f"## Largest Files",
    ]
    
    for f in files[:max_files]:
        size_kb = f["size"] / 1024
        lines.append(f"- {f['path']}: {size_kb:.1f} KB, {f['lines']} lines")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={
            "total_files": len(files),
            "total_size": total_size,
            "total_lines": total_lines,
        }
    )
