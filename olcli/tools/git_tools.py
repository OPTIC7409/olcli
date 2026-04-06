"""
OLCLI Git Tools
Advanced git operations and repository analysis.
"""

import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from .builtins import ToolResult


def git_status(path: str = ".") -> ToolResult:
    """Get git status of a repository."""
    import subprocess
    
    p = Path(path).expanduser()
    if not (p / ".git").exists():
        return ToolResult(success=False, output="", error="Not a git repository")
    
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-b"],
            cwd=str(p),
            capture_output=True,
            text=True,
        )
        
        lines = result.stdout.strip().split("\n")
        
        # Parse branch info from first line
        branch_info = ""
        if lines and lines[0].startswith("##"):
            branch_info = lines[0][3:]
            lines = lines[1:]
        
        # Parse file statuses
        staged = []
        unstaged = []
        untracked = []
        
        for line in lines:
            if not line:
                continue
            status = line[:2]
            filename = line[3:]
            
            if status == "??":
                untracked.append(filename)
            elif status[0] != " ":
                staged.append((status[0], filename))
            if status[1] != " ":
                unstaged.append((status[1], filename))
        
        output_lines = [f"# Git Status: {branch_info}", ""]
        
        if staged:
            output_lines.append("## Staged Changes")
            for code, file in staged:
                output_lines.append(f"  [{code}] {file}")
            output_lines.append("")
        
        if unstaged:
            output_lines.append("## Unstaged Changes")
            for code, file in unstaged:
                output_lines.append(f"  [{code}] {file}")
            output_lines.append("")
        
        if untracked:
            output_lines.append(f"## Untracked Files ({len(untracked)})")
            for file in untracked[:20]:
                output_lines.append(f"  {file}")
            if len(untracked) > 20:
                output_lines.append(f"  ... and {len(untracked) - 20} more")
        
        if not any([staged, unstaged, untracked]):
            output_lines.append("Working tree clean!")
        
        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            metadata={
                "branch": branch_info,
                "staged_count": len(staged),
                "unstaged_count": len(unstaged),
                "untracked_count": len(untracked),
            }
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def git_log(path: str = ".", n: int = 10, author: str = None, since: str = None) -> ToolResult:
    """Get git commit history."""
    import subprocess
    
    p = Path(path).expanduser()
    if not (p / ".git").exists():
        return ToolResult(success=False, output="", error="Not a git repository")
    
    try:
        cmd = ["git", "log", f"-{n}", "--pretty=format:%H|%h|%an|%ae|%ad|%s", "--date=short"]
        if author:
            cmd.extend(["--author", author])
        if since:
            cmd.extend(["--since", since])
        
        result = subprocess.run(cmd, cwd=str(p), capture_output=True, text=True)
        
        lines = [f"# Git Log (last {n} commits)", ""]
        commits = []
        
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 5)
            if len(parts) == 6:
                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "author": parts[2],
                    "email": parts[3],
                    "date": parts[4],
                    "message": parts[5],
                })
        
        for c in commits:
            lines.append(f"**{c['short_hash']}** [{c['date']}] *{c['author']}*")
            lines.append(f"  {c['message']}")
            lines.append("")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"commits": commits},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def git_diff(path: str = ".", staged: bool = False, file: str = None) -> ToolResult:
    """Show git diff."""
    import subprocess
    
    p = Path(path).expanduser()
    if not (p / ".git").exists():
        return ToolResult(success=False, output="", error="Not a git repository")
    
    try:
        cmd = ["git", "diff", "--stat" if not file else ""]
        if staged:
            cmd.insert(2, "--staged")
        if file:
            cmd.append(file)
        
        cmd = [c for c in cmd if c]
        result = subprocess.run(cmd, cwd=str(p), capture_output=True, text=True)
        
        if result.returncode != 0:
            return ToolResult(success=False, output="", error=result.stderr)
        
        return ToolResult(
            success=True,
            output=f"# Git Diff\n\n```diff\n{result.stdout}\n```" if result.stdout else "No changes",
            metadata={"has_changes": bool(result.stdout)},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def git_blame(path: str, line_start: int = None, line_end: int = None) -> ToolResult:
    """Show git blame for a file."""
    import subprocess
    
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")
    
    # Check if in git repo
    git_dir = p.parent
    while git_dir != git_dir.parent:
        if (git_dir / ".git").exists():
            break
        git_dir = git_dir.parent
    else:
        return ToolResult(success=False, output="", error="Not in a git repository")
    
    try:
        cmd = ["git", "blame", "-l", str(p)]
        if line_start and line_end:
            cmd.extend(["-L", f"{line_start},{line_end}"])
        
        result = subprocess.run(cmd, cwd=str(git_dir), capture_output=True, text=True)
        
        if result.returncode != 0:
            return ToolResult(success=False, output="", error=result.stderr)
        
        # Parse blame output
        lines = [f"# Git Blame: {p.name}", ""]
        blame_data = []
        
        for line in result.stdout.strip().split("\n"):
            # Format: hash (author date time tz line) code
            match = re.match(r"^([a-f0-9]+)\s+\((.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}).*?\s+(\d+)\)\s(.*)$", line)
            if match:
                hash_full, author, date, time, lineno, code = match.groups()
                blame_data.append({
                    "hash": hash_full[:8],
                    "author": author.strip(),
                    "date": date,
                    "line": int(lineno),
                    "code": code,
                })
        
        # Group consecutive lines by same author
        current_author = None
        current_date = None
        block_start = 0
        
        for i, entry in enumerate(blame_data):
            if entry["author"] != current_author or entry["date"] != current_date:
                if current_author:
                    lines.append(f"[{current_author} @ {current_date}]")
                    for e in blame_data[block_start:i]:
                        lines.append(f"  {e['line']:4d}: {e['code'][:80]}")
                    lines.append("")
                current_author = entry["author"]
                current_date = entry["date"]
                block_start = i
        
        # Print last block
        if current_author:
            lines.append(f"[{current_author} @ {current_date}]")
            for e in blame_data[block_start:]:
                lines.append(f"  {e['line']:4d}: {e['code'][:80]}")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"blame": blame_data},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def git_branch_info(path: str = ".") -> ToolResult:
    """Get information about branches."""
    import subprocess
    
    p = Path(path).expanduser()
    if not (p / ".git").exists():
        return ToolResult(success=False, output="", error="Not a git repository")
    
    try:
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(p),
            capture_output=True,
            text=True,
        )
        current = result.stdout.strip()
        
        # Get all branches
        result = subprocess.run(
            ["git", "branch", "-vv"],
            cwd=str(p),
            capture_output=True,
            text=True,
        )
        
        lines = [f"# Branches (current: {current})", ""]
        
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Remove leading spaces and asterisk
            clean = line.strip().lstrip("* ")
            is_current = line.strip().startswith("*")
            
            if is_current:
                lines.append(f"> **{clean}**")
            else:
                lines.append(f"  {clean}")
        
        # Get remote info
        result = subprocess.run(
            ["git", "remote", "-v"],
            cwd=str(p),
            capture_output=True,
            text=True,
        )
        
        if result.stdout.strip():
            lines.extend(["", "## Remotes"])
            for line in result.stdout.strip().split("\n"):
                lines.append(f"  {line}")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"current_branch": current},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def git_contributors(path: str = ".", n: int = 10) -> ToolResult:
    """Get top contributors to the repository."""
    import subprocess
    
    p = Path(path).expanduser()
    if not (p / ".git").exists():
        return ToolResult(success=False, output="", error="Not a git repository")
    
    try:
        result = subprocess.run(
            ["git", "shortlog", "-sn", "HEAD"],
            cwd=str(p),
            capture_output=True,
            text=True,
        )
        
        lines = ["# Top Contributors", ""]
        contributors = []
        
        for line in result.stdout.strip().split("\n")[:n]:
            if not line:
                continue
            # Format:    123  Author Name
            match = re.match(r"^\s*(\d+)\s+(.+)$", line)
            if match:
                count, name = match.groups()
                contributors.append({"name": name, "commits": int(count)})
                lines.append(f"- {count} commits: {name}")
        
        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"contributors": contributors},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))
