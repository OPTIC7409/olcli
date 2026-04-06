"""
OLCLI Tools Package
All available tools for agents.
"""

from .enhanced_registry import EnhancedToolRegistry, ToolResult

# For backwards compatibility
ToolRegistry = EnhancedToolRegistry

__all__ = ['EnhancedToolRegistry', 'ToolRegistry', 'ToolResult']
