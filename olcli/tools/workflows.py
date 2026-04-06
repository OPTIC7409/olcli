"""
OLCLI Workflow Tools
Tools for automating multi-step tasks and workflows.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from .builtins import ToolResult


# Predefined workflows
WORKFLOWS = {
    "refactor-function": {
        "description": "Safely refactor a function with tests and validation",
        "steps": [
            "analyze_code",
            "find_symbol",
            "check_syntax",
            "run_tests",
        ],
    },
    "new-feature": {
        "description": "Add a new feature with scaffolding and tests",
        "steps": [
            "scaffold_project",
            "generate_from_template",
            "check_syntax",
            "run_tests",
        ],
    },
    "code-review": {
        "description": "Comprehensive code review workflow",
        "steps": [
            "analyze_code",
            "find_todos",
            "find_duplicate_code",
            "count_lines",
            "check_syntax",
            "lint_code",
        ],
    },
    "release-check": {
        "description": "Pre-release validation workflow",
        "steps": [
            "git_status",
            "run_tests",
            "check_types",
            "lint_code",
            "get_dependencies",
        ],
    },
}


class WorkflowRunner:
    """Execute multi-step workflows."""
    
    def __init__(self, tool_registry):
        self.tools = tool_registry
        self.results = []
    
    def run_workflow(self, workflow_name: str, context: Dict[str, Any]) -> ToolResult:
        """Run a predefined workflow."""
        if workflow_name not in WORKFLOWS:
            available = ", ".join(WORKFLOWS.keys())
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown workflow: {workflow_name}. Available: {available}"
            )
        
        workflow = WORKFLOWS[workflow_name]
        self.results = []
        
        lines = [f"# Workflow: {workflow_name}", f"", f"{workflow['description']}", ""]
        
        for step in workflow["steps"]:
            lines.append(f"## Step: {step}")
            
            # Map step to tool call
            tool_name, params = self._map_step(step, context)
            
            if tool_name:
                result = self.tools.execute(tool_name, params)
                self.results.append({"step": step, "tool": tool_name, "result": result})
                
                status = "âœ“" if result.success else "âœ—"
                lines.append(f"{status} {tool_name}")
                if result.output:
                    lines.append(f"```")
                    lines.append(result.output[:500])  # Truncate
                    lines.append(f"```")
                if result.error:
                    lines.append(f"Error: {result.error}")
                lines.append("")
            else:
                lines.append(f"âš Skipped (no mapping)")
                lines.append("")
        
        success = all(r["result"].success for r in self.results)
        
        return ToolResult(
            success=success,
            output="\n".join(lines),
            metadata={
                "workflow": workflow_name,
                "steps_completed": len(self.results),
                "success": success,
            }
        )
    
    def _map_step(self, step: str, context: Dict) -> tuple[Optional[str], Dict]:
        """Map workflow step to tool and parameters."""
        mappings = {
            "analyze_code": ("analyze_code", {"path": context.get("path")}),
            "find_symbol": ("find_symbol", {"path": context.get("path"), "symbol_name": context.get("symbol")}),
            "check_syntax": ("check_syntax", {"path": context.get("file")}),
            "run_tests": ("run_tests", {"path": context.get("test_path", ".")}),
            "find_todos": ("find_todos", {"path": context.get("path")}),
            "find_duplicate_code": ("find_duplicate_code", {"path": context.get("path")}),
            "count_lines": ("count_lines", {"path": context.get("path")}),
            "lint_code": ("lint_code", {"path": context.get("path")}),
            "check_types": ("check_types", {"path": context.get("path")}),
            "git_status": ("git_status", {"path": context.get("git_path", ".")}),
            "get_dependencies": ("get_dependencies", {"path": context.get("path")}),
        }
        return mappings.get(step, (None, {}))


def create_task_list(tasks: List[Dict[str, Any]], title: str = "Task List") -> ToolResult:
    """Create a structured task list with status tracking."""
    lines = [f"# {title}", ""]
    
    for i, task in enumerate(tasks, 1):
        status = task.get("status", "pending")
        desc = task.get("description", "No description")
        assignee = task.get("assignee", "")
        
        status_icon = {
            "done": "âœ“",
            "in_progress": "â—�",
            "blocked": "âœ—",
            "pending": "â—‹",
        }.get(status, "â—‹")
        
        assignee_str = f" (@{assignee})" if assignee else ""
        lines.append(f"{status_icon} {i}. {desc}{assignee_str}")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"total": len(tasks), "completed": sum(1 for t in tasks if t.get("status") == "done")}
    )


def update_task_status(tasks: List[Dict], task_id: int, new_status: str) -> ToolResult:
    """Update the status of a task."""
    if task_id < 1 or task_id > len(tasks):
        return ToolResult(success=False, output="", error=f"Invalid task ID: {task_id}")
    
    tasks[task_id - 1]["status"] = new_status
    
    return ToolResult(
        success=True,
        output=f"Task {task_id} updated to: {new_status}",
        metadata={"tasks": tasks}
    )


def generate_checklist(checklist_type: str, items: Optional[List[str]] = None) -> ToolResult:
    """Generate a checklist for common tasks."""
    checklists = {
        "pr-review": [
            "Code follows style guidelines",
            "Tests pass locally",
            "Documentation updated",
            "No breaking changes (or documented)",
            "Security considerations addressed",
            "Performance impact considered",
        ],
        "release": [
            "Version bumped",
            "Changelog updated",
            "Tests passing",
            "Documentation updated",
            "Dependencies updated",
            "Git tag created",
        ],
        "new-project": [
            "Project structure created",
            "README written",
            "Dependencies listed",
            "Basic tests added",
            "CI/CD configured",
            "License added",
        ],
        "refactor": [
            "Original code analyzed",
            "Tests exist and pass",
            "Refactoring plan documented",
            "Changes implemented",
            "Tests still pass",
            "Code reviewed",
        ],
    }
    
    if checklist_type not in checklists:
        available = ", ".join(checklists.keys())
        return ToolResult(
            success=False,
            output="",
            error=f"Unknown checklist type: {checklist_type}. Available: {available}"
        )
    
    items = items or checklists[checklist_type]
    
    lines = [f"# {checklist_type.replace('-', ' ').title()} Checklist", ""]
    for item in items:
        lines.append(f"- [ ] {item}")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"type": checklist_type, "items": items}
    )


def list_workflows() -> ToolResult:
    """List available workflows."""
    lines = ["# Available Workflows", ""]
    
    for name, info in WORKFLOWS.items():
        lines.append(f"## {name}")
        lines.append(f"{info['description']}")
        lines.append(f"Steps: {', '.join(info['steps'][:3])}...")
        lines.append("")
    
    return ToolResult(
        success=True,
        output="\n".join(lines),
        metadata={"workflows": list(WORKFLOWS.keys())}
    )
