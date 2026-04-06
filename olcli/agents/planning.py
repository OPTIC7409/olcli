"""
OLCLI Task Planning
Task decomposition, planning, and execution tracking for agents.
"""

import json
import uuid
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A single task in a plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    parent_id: Optional[str] = None
    subtasks: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_to: Optional[str] = None  # Agent name
    metadata: dict = field(default_factory=dict)
    
    @property
    def is_done(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds()
        return None


class TaskPlan:
    """A plan consisting of multiple tasks."""
    
    def __init__(self, goal: str):
        self.id = str(uuid.uuid4())[:8]
        self.goal = goal
        self.tasks: dict[str, Task] = {}
        self.root_task_ids: list[str] = []
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
    
    def add_task(self, description: str, parent_id: str = None,
                 dependencies: list = None, assigned_to: str = None) -> Task:
        """Add a new task to the plan."""
        task = Task(
            description=description,
            parent_id=parent_id,
            dependencies=dependencies or [],
            assigned_to=assigned_to,
        )
        self.tasks[task.id] = task
        
        if parent_id:
            parent = self.tasks.get(parent_id)
            if parent:
                parent.subtasks.append(task.id)
        else:
            self.root_task_ids.append(task.id)
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute (dependencies met)."""
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check dependencies
            deps_met = all(
                self.tasks.get(dep_id) and 
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            
            if deps_met:
                ready.append(task)
        
        return ready
    
    def start_task(self, task_id: str):
        """Mark a task as started."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
    
    def complete_task(self, task_id: str, result: str = None):
        """Mark a task as completed."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now().isoformat()
    
    def fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.error = error
            task.completed_at = datetime.now().isoformat()
    
    def block_task(self, task_id: str, reason: str):
        """Mark a task as blocked."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.BLOCKED
            task.error = reason
    
    @property
    def is_complete(self) -> bool:
        """Check if all tasks are done."""
        return all(t.is_done for t in self.tasks.values())
    
    @property
    def progress(self) -> dict:
        """Get completion progress."""
        total = len(self.tasks)
        if total == 0:
            return {"percent": 100, "completed": 0, "total": 0}
        
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS)
        
        return {
            "percent": (completed / total) * 100,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "total": total,
        }
    
    def to_dict(self) -> dict:
        """Serialize plan to dict."""
        return {
            "id": self.id,
            "goal": self.goal,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "tasks": {k: asdict(v) for k, v in self.tasks.items()},
        }
    
    def format_summary(self) -> str:
        """Format plan as a readable summary."""
        lines = [
            f"# Plan: {self.goal}",
            f"ID: {self.id} | Progress: {self.progress['percent']:.0f}%",
            "",
        ]
        
        def format_task(task: Task, depth: int = 0):
            indent = "  " * depth
            status_icon = {
                TaskStatus.PENDING: "○",
                TaskStatus.IN_PROGRESS: "◖",
                TaskStatus.COMPLETED: "✓",
                TaskStatus.FAILED: "✗",
                TaskStatus.BLOCKED: "■",
            }.get(task.status, "?")
            
            lines.append(f"{indent}{status_icon} {task.description}")
            
            if task.result and task.status == TaskStatus.COMPLETED:
                lines.append(f"{indent}  → {task.result[:100]}")
            if task.error and task.status == TaskStatus.FAILED:
                lines.append(f"{indent}  ✗ {task.error[:100]}")
            
            for subtask_id in task.subtasks:
                subtask = self.tasks.get(subtask_id)
                if subtask:
                    format_task(subtask, depth + 1)
        
        for root_id in self.root_task_ids:
            root = self.tasks.get(root_id)
            if root:
                format_task(root)
        
        return "\n".join(lines)


class TaskPlanner:
    """AI-powered task planning."""
    
    def __init__(self, client=None):
        self.client = client
        self.active_plans: dict[str, TaskPlan] = {}
    
    def create_plan(self, goal: str, context: str = None) -> TaskPlan:
        """Create a new plan for a goal."""
        plan = TaskPlan(goal)
        self.active_plans[plan.id] = plan
        return plan
    
    def decompose_task(self, goal: str, context: str = None) -> list[str]:
        """Decompose a goal into subtasks (AI-powered if client available)."""
        # Simple rule-based decomposition for now
        # Could be enhanced with LLM-based decomposition
        
        tasks = []
        goal_lower = goal.lower()
        
        # Common patterns
        if "implement" in goal_lower or "create" in goal_lower:
            tasks = [
                "Analyze requirements and existing code",
                "Design the solution",
                "Implement the core functionality",
                "Add tests",
                "Review and refine",
            ]
        elif "fix" in goal_lower or "debug" in goal_lower:
            tasks = [
                "Reproduce the issue",
                "Identify root cause",
                "Implement fix",
                "Verify the fix",
                "Add regression test",
            ]
        elif "refactor" in goal_lower:
            tasks = [
                "Analyze current implementation",
                "Identify improvement areas",
                "Plan refactoring steps",
                "Execute refactoring",
                "Verify functionality",
            ]
        elif "document" in goal_lower:
            tasks = [
                "Analyze code to document",
                "Identify key components",
                "Write documentation",
                "Add code examples",
                "Review for clarity",
            ]
        else:
            tasks = [
                f"Understand: {goal}",
                "Gather necessary information",
                "Execute the task",
                "Verify results",
            ]
        
        return tasks
    
    def execute_plan(self, plan: TaskPlan, executor: Callable[[Task], bool]) -> dict:
        """Execute a plan using the provided executor function."""
        while not plan.is_complete:
            ready = plan.get_ready_tasks()
            
            if not ready:
                # Check if there are blocked tasks
                blocked = [t for t in plan.tasks.values() if t.status == TaskStatus.BLOCKED]
                if blocked:
                    return {
                        "success": False,
                        "error": f"Tasks blocked: {[t.description for t in blocked]}",
                        "plan": plan.to_dict(),
                    }
                break
            
            for task in ready:
                plan.start_task(task.id)
                try:
                    success = executor(task)
                    if success:
                        plan.complete_task(task.id, "Completed successfully")
                    else:
                        plan.fail_task(task.id, "Executor returned failure")
                except Exception as e:
                    plan.fail_task(task.id, str(e))
        
        plan.completed_at = datetime.now().isoformat()
        
        failed = [t for t in plan.tasks.values() if t.status == TaskStatus.FAILED]
        return {
            "success": len(failed) == 0,
            "plan": plan.to_dict(),
            "failed_tasks": [t.description for t in failed],
        }


# â”€â”€ Tool Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_planner = TaskPlanner()
_plans: dict[str, TaskPlan] = {}


def create_plan(goal: str) -> dict:
    """Create a new task plan."""
    plan = _planner.create_plan(goal)
    _plans[plan.id] = plan
    
    # Auto-decompose
    subtasks = _planner.decompose_task(goal)
    for desc in subtasks:
        plan.add_task(desc)
    
    return {
        "success": True,
        "plan_id": plan.id,
        "goal": goal,
        "tasks": len(plan.tasks),
        "summary": plan.format_summary(),
    }


def add_task(plan_id: str, description: str, parent_id: str = None, 
             dependencies: list = None) -> dict:
    """Add a task to a plan."""
    plan = _plans.get(plan_id)
    if not plan:
        return {"success": False, "error": f"Plan {plan_id} not found"}
    
    task = plan.add_task(description, parent_id, dependencies)
    return {
        "success": True,
        "task_id": task.id,
        "plan_summary": plan.format_summary(),
    }


def update_task(plan_id: str, task_id: str, status: str, result: str = None) -> dict:
    """Update task status."""
    plan = _plans.get(plan_id)
    if not plan:
        return {"success": False, "error": f"Plan {plan_id} not found"}
    
    if status == "completed":
        plan.complete_task(task_id, result)
    elif status == "failed":
        plan.fail_task(task_id, result)
    elif status == "in_progress":
        plan.start_task(task_id)
    
    return {
        "success": True,
        "progress": plan.progress,
        "summary": plan.format_summary(),
    }


def get_plan(plan_id: str) -> dict:
    """Get plan details."""
    plan = _plans.get(plan_id)
    if not plan:
        return {"success": False, "error": f"Plan {plan_id} not found"}
    
    return {
        "success": True,
        "plan": plan.to_dict(),
        "summary": plan.format_summary(),
    }


def list_plans() -> dict:
    """List all active plans."""
    return {
        "success": True,
        "plans": [
            {
                "id": p.id,
                "goal": p.goal,
                "progress": p.progress,
                "is_complete": p.is_complete,
            }
            for p in _plans.values()
        ],
    }
