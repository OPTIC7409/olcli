"""
OLCLI Memory and Context Management
Long-term memory, embeddings, and context retrieval for agents.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..config import GLOBAL_MEMORY_DIR


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    category: str = "general"  # "code", "fact", "task", "conversation"
    source: Optional[str] = None
    importance: int = 1  # 1-5
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: list = field(default_factory=list)
    embedding: Optional[list[float]] = None
    
    @property
    def id(self) -> str:
        """Generate a unique ID from content."""
        return hashlib.md5(f"{self.content}{self.timestamp}".encode()).hexdigest()[:12]


class MemoryStore:
    """Persistent memory storage with search capabilities."""
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._store: dict[str, MemoryEntry] = {}
        self._file = GLOBAL_MEMORY_DIR / f"{namespace}.json"
        self._load()
    
    def _load(self):
        """Load memories from disk."""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for entry_data in data.get("memories", []):
                    entry = MemoryEntry(**entry_data)
                    self._store[entry.id] = entry
            except Exception:
                pass
    
    def save(self):
        """Save memories to disk."""
        GLOBAL_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "namespace": self.namespace,
            "updated": datetime.now().isoformat(),
            "memories": [asdict(e) for e in self._store.values()],
        }
        self._file.write_text(json.dumps(data, indent=2))
    
    def add(self, content: str, category: str = "general", 
            source: str = None, importance: int = 1, tags: list = None) -> str:
        """Add a new memory."""
        entry = MemoryEntry(
            content=content,
            category=category,
            source=source,
            importance=importance,
            tags=tags or [],
        )
        self._store[entry.id] = entry
        self.save()
        return entry.id
    
    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID."""
        return self._store.get(memory_id)
    
    def search(self, query: str, category: str = None, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by content (simple keyword matching)."""
        query_lower = query.lower()
        results = []
        
        for entry in self._store.values():
            if category and entry.category != category:
                continue
            
            # Simple relevance scoring
            score = 0
            query_words = query_lower.split()
            content_lower = entry.content.lower()
            
            for word in query_words:
                if word in content_lower:
                    score += 1
                if word in [t.lower() for t in entry.tags]:
                    score += 2
            
            if score > 0:
                results.append((score, entry))
        
        # Sort by importance and score
        results.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
        return [r[1] for r in results[:limit]]
    
    def get_recent(self, n: int = 10, category: str = None) -> list[MemoryEntry]:
        """Get most recent memories."""
        entries = list(self._store.values())
        if category:
            entries = [e for e in entries if e.category == category]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:n]
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        if memory_id in self._store:
            del self._store[memory_id]
            self.save()
            return True
        return False
    
    def clear(self):
        """Clear all memories."""
        self._store.clear()
        self.save()
    
    def list_categories(self) -> list[str]:
        """List all categories."""
        return list(set(e.category for e in self._store.values()))
    
    def count(self) -> int:
        """Get total memory count."""
        return len(self._store)


class ContextManager:
    """Manage conversation context and relevant memories."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.memory = MemoryStore(namespace=session_id)
        self.short_term: list[dict] = []  # Recent context window
        self.max_short_term = 10
    
    def add_to_context(self, role: str, content: str, metadata: dict = None):
        """Add to short-term context."""
        self.short_term.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        })
        # Trim if needed
        if len(self.short_term) > self.max_short_term:
            self.short_term = self.short_term[-self.max_short_term:]
    
    def get_relevant_memories(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Get memories relevant to current context."""
        return self.memory.search(query, limit=limit)
    
    def build_system_context(self, base_prompt: str) -> str:
        """Build enhanced system prompt with relevant context."""
        lines = [base_prompt]
        
        # Add recent memories if any
        recent = self.memory.get_recent(n=5)
        if recent:
            lines.append("\n## Relevant Context")
            for mem in recent:
                lines.append(f"- [{mem.category}] {mem.content[:100]}...")
        
        return "\n".join(lines)
    
    def remember_interaction(self, user_msg: str, assistant_msg: str, 
                           tool_calls: list = None):
        """Store an interaction in long-term memory."""
        # Extract key facts
        self.memory.add(
            content=f"User asked: {user_msg[:200]}",
            category="conversation",
            importance=1,
        )
        
        if tool_calls:
            for call in tool_calls:
                self.memory.add(
                    content=f"Tool used: {call.get('name')} - {call.get('arguments')}",
                    category="task",
                    importance=2,
                )


class WorkingMemory:
    """Temporary working memory for the current task."""
    
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._notes: list[str] = []
    
    def set(self, key: str, value: Any):
        """Store a value."""
        self._data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value."""
        return self._data.get(key, default)
    
    def note(self, text: str):
        """Add a note."""
        self._notes.append(f"[{datetime.now().strftime('%H:%M')}] {text}")
    
    def get_notes(self) -> str:
        """Get all notes as a string."""
        return "\n".join(self._notes)
    
    def clear(self):
        """Clear working memory."""
        self._data.clear()
        self._notes.clear()
    
    def summarize(self) -> str:
        """Summarize working memory."""
        lines = ["## Working Memory"]
        for k, v in self._data.items():
            lines.append(f"- {k}: {str(v)[:100]}")
        if self._notes:
            lines.append("\n### Notes:")
            lines.extend(self._notes[-10:])  # Last 10 notes
        return "\n".join(lines)


# â”€â”€ Tool Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_memory_stores: dict[str, MemoryStore] = {}

def _get_store(namespace: str = "default") -> MemoryStore:
    if namespace not in _memory_stores:
        _memory_stores[namespace] = MemoryStore(namespace)
    return _memory_stores[namespace]


def memory_add(content: str, category: str = "general", 
               importance: int = 1, tags: str = None) -> dict:
    """Add a memory entry."""
    store = _get_store()
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    memory_id = store.add(content, category, importance=importance, tags=tag_list)
    return {
        "success": True,
        "memory_id": memory_id,
        "total_memories": store.count(),
    }


def memory_search(query: str, category: str = None, limit: int = 10) -> dict:
    """Search memories."""
    store = _get_store()
    results = store.search(query, category=category, limit=limit)
    return {
        "success": True,
        "count": len(results),
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "timestamp": r.timestamp,
            }
            for r in results
        ],
    }


def memory_recent(n: int = 10, category: str = None) -> dict:
    """Get recent memories."""
    store = _get_store()
    results = store.get_recent(n=n, category=category)
    return {
        "success": True,
        "results": [
            {
                "id": r.id,
                "content": r.content[:200],
                "category": r.category,
                "timestamp": r.timestamp,
            }
            for r in results
        ],
    }


def memory_delete(memory_id: str) -> dict:
    """Delete a memory."""
    store = _get_store()
    success = store.delete(memory_id)
    return {"success": success, "remaining": store.count()}


def memory_categories() -> dict:
    """List memory categories."""
    store = _get_store()
    return {
        "success": True,
        "categories": store.list_categories(),
        "total_memories": store.count(),
    }
