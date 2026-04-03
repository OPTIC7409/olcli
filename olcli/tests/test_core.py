"""
OLCLI Core Tests
Tests for config, tools, agents, and commands.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from olcli.config import OlcliConfig, AgentDefinition, AgentRegistry
from olcli.tools.builtins import ToolRegistry, ToolResult
from olcli.commands.registry import build_command_registry


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = OlcliConfig()
        self.assertEqual(cfg.model, "llama3.2")
        self.assertEqual(cfg.host, "http://localhost:11434")
        self.assertTrue(cfg.stream)
        self.assertTrue(cfg.safe_mode)

    def test_set_get(self):
        cfg = OlcliConfig()
        result = cfg.set("temperature", "0.3")
        self.assertTrue(result)
        self.assertAlmostEqual(cfg.temperature, 0.3)

    def test_set_bool(self):
        cfg = OlcliConfig()
        cfg.set("stream", "false")
        self.assertFalse(cfg.stream)
        cfg.set("stream", "true")
        self.assertTrue(cfg.stream)

    def test_unknown_key(self):
        cfg = OlcliConfig()
        result = cfg.set("nonexistent_key", "value")
        self.assertFalse(result)

    def test_as_dict(self):
        cfg = OlcliConfig()
        d = cfg.as_dict()
        self.assertIn("model", d)
        self.assertIn("temperature", d)


class TestAgentDefinition(unittest.TestCase):
    def test_from_markdown(self):
        md = """---
name: test-agent
description: A test agent
model: llama3.2
tools:
  - read_file
  - run_shell
max_turns: 25
color: blue
scope: user
---

You are a test agent. Be helpful.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(md)
            f.flush()
            agent = AgentDefinition.from_markdown(Path(f.name))

        self.assertEqual(agent.name, "test-agent")
        self.assertEqual(agent.description, "A test agent")
        self.assertEqual(agent.model, "llama3.2")
        self.assertIn("read_file", agent.tools)
        self.assertEqual(agent.max_turns, 25)
        self.assertIn("You are a test agent", agent.system_prompt)
        os.unlink(f.name)

    def test_to_markdown(self):
        agent = AgentDefinition(
            name="my-agent",
            description="Test",
            system_prompt="You are helpful.",
            tools=["read_file"],
        )
        md = agent.to_markdown()
        self.assertIn("---", md)
        self.assertIn("name: my-agent", md)
        self.assertIn("You are helpful.", md)


class TestAgentRegistry(unittest.TestCase):
    def test_builtin_agents(self):
        reg = AgentRegistry()
        agents = reg.list_all()
        names = [a.name for a in agents]
        self.assertIn("explorer", names)
        self.assertIn("coder", names)
        self.assertIn("researcher", names)
        self.assertIn("reviewer", names)
        self.assertIn("debugger", names)
        self.assertIn("shell", names)

    def test_get_agent(self):
        reg = AgentRegistry()
        agent = reg.get("coder")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "coder")

    def test_get_nonexistent(self):
        reg = AgentRegistry()
        agent = reg.get("nonexistent")
        self.assertIsNone(agent)

    def test_register_custom(self):
        reg = AgentRegistry()
        custom = AgentDefinition(
            name="custom-test",
            description="Custom test agent",
            system_prompt="You are custom.",
        )
        reg.register(custom)
        retrieved = reg.get("custom-test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "custom-test")


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.tools = ToolRegistry(safe_mode=False, auto_approve=True)
        self.tmpdir = tempfile.mkdtemp()

    def test_list_tools(self):
        tools = self.tools.list_tools()
        names = [t["name"] for t in tools]
        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertIn("edit_file", names)
        self.assertIn("run_shell", names)
        self.assertIn("web_search", names)
        self.assertIn("glob_files", names)
        self.assertIn("grep_files", names)

    def test_read_file(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("line1\nline2\nline3\n")
        result = self.tools.execute("read_file", {"path": path})
        self.assertTrue(result.success)
        self.assertIn("line1", result.output)

    def test_read_file_range(self):
        path = os.path.join(self.tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("line1\nline2\nline3\n")
        result = self.tools.execute("read_file", {"path": path, "start_line": 2, "end_line": 2})
        self.assertTrue(result.success)
        self.assertIn("line2", result.output)
        self.assertNotIn("line1", result.output)

    def test_read_nonexistent(self):
        result = self.tools.execute("read_file", {"path": "/nonexistent/path.txt"})
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_write_file(self):
        path = os.path.join(self.tmpdir, "write_test.txt")
        result = self.tools.execute("write_file", {"path": path, "content": "Hello, OLCLI!"})
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            self.assertEqual(f.read(), "Hello, OLCLI!")

    def test_write_file_append(self):
        path = os.path.join(self.tmpdir, "append_test.txt")
        self.tools.execute("write_file", {"path": path, "content": "line1\n"})
        self.tools.execute("write_file", {"path": path, "content": "line2\n", "append": True})
        with open(path) as f:
            content = f.read()
        self.assertIn("line1", content)
        self.assertIn("line2", content)

    def test_edit_file(self):
        path = os.path.join(self.tmpdir, "edit_test.txt")
        with open(path, "w") as f:
            f.write("Hello World\nHello Again\n")
        result = self.tools.execute("edit_file", {
            "path": path, "old_text": "Hello World", "new_text": "Goodbye World"
        })
        self.assertTrue(result.success)
        with open(path) as f:
            content = f.read()
        self.assertIn("Goodbye World", content)
        self.assertIn("Hello Again", content)

    def test_edit_file_not_found_text(self):
        path = os.path.join(self.tmpdir, "edit_test2.txt")
        with open(path, "w") as f:
            f.write("Some content\n")
        result = self.tools.execute("edit_file", {
            "path": path, "old_text": "NONEXISTENT", "new_text": "replacement"
        })
        self.assertFalse(result.success)

    def test_list_files(self):
        result = self.tools.execute("list_files", {"path": self.tmpdir})
        self.assertTrue(result.success)

    def test_glob_files(self):
        # Create some test files
        for name in ["a.py", "b.py", "c.txt"]:
            open(os.path.join(self.tmpdir, name), "w").close()
        result = self.tools.execute("glob_files", {"pattern": "*.py", "base_dir": self.tmpdir})
        self.assertTrue(result.success)
        self.assertIn("a.py", result.output)
        self.assertIn("b.py", result.output)
        self.assertNotIn("c.txt", result.output)

    def test_grep_files(self):
        path = os.path.join(self.tmpdir, "grep_test.py")
        with open(path, "w") as f:
            f.write("def hello():\n    return 'world'\n\ndef goodbye():\n    return 'bye'\n")
        result = self.tools.execute("grep_files", {"pattern": "def ", "path": path})
        self.assertTrue(result.success)
        self.assertIn("def hello", result.output)
        self.assertIn("def goodbye", result.output)

    def test_run_shell(self):
        result = self.tools.execute("run_shell", {"command": "echo 'test output'"})
        self.assertTrue(result.success)
        self.assertIn("test output", result.output)

    def test_run_shell_failure(self):
        result = self.tools.execute("run_shell", {"command": "exit 1"})
        self.assertFalse(result.success)

    def test_diff_files(self):
        path_a = os.path.join(self.tmpdir, "a.txt")
        path_b = os.path.join(self.tmpdir, "b.txt")
        with open(path_a, "w") as f:
            f.write("line1\nline2\nline3\n")
        with open(path_b, "w") as f:
            f.write("line1\nmodified\nline3\n")
        result = self.tools.execute("diff_files", {"file_a": path_a, "file_b": path_b})
        self.assertTrue(result.success)
        self.assertIn("-line2", result.output)
        self.assertIn("+modified", result.output)

    def test_diff_text(self):
        result = self.tools.execute("diff_files", {
            "text_a": "hello\nworld\n",
            "text_b": "hello\npython\n",
        })
        self.assertTrue(result.success)
        self.assertIn("-world", result.output)
        self.assertIn("+python", result.output)

    def test_get_file_info(self):
        path = os.path.join(self.tmpdir, "info_test.txt")
        with open(path, "w") as f:
            f.write("test content\n")
        result = self.tools.execute("get_file_info", {"path": path})
        self.assertTrue(result.success)
        self.assertIn("size_bytes", result.output)
        self.assertIn("line_count", result.output)

    def test_make_directory(self):
        new_dir = os.path.join(self.tmpdir, "new", "nested", "dir")
        result = self.tools.execute("make_directory", {"path": new_dir})
        self.assertTrue(result.success)
        self.assertTrue(os.path.isdir(new_dir))

    def test_move_file(self):
        src = os.path.join(self.tmpdir, "move_src.txt")
        dst = os.path.join(self.tmpdir, "move_dst.txt")
        with open(src, "w") as f:
            f.write("content")
        result = self.tools.execute("move_file", {"source": src, "destination": dst})
        self.assertTrue(result.success)
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))

    def test_delete_file(self):
        path = os.path.join(self.tmpdir, "delete_test.txt")
        with open(path, "w") as f:
            f.write("to delete")
        result = self.tools.execute("delete_file", {"path": path})
        self.assertTrue(result.success)
        self.assertFalse(os.path.exists(path))

    def test_unknown_tool(self):
        result = self.tools.execute("nonexistent_tool", {})
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error)

    def test_get_schemas(self):
        schemas = self.tools.get_schemas()
        self.assertGreater(len(schemas), 0)
        for s in schemas:
            self.assertIn("type", s)
            self.assertIn("function", s)
            self.assertIn("name", s["function"])

    def test_get_schemas_filtered(self):
        schemas = self.tools.get_schemas(allowed=["read_file", "write_file"])
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("read_file", names)
        self.assertIn("write_file", names)
        self.assertNotIn("run_shell", names)

    def test_requires_approval(self):
        self.tools.safe_mode = True
        self.tools.auto_approve = False
        self.assertTrue(self.tools.requires_approval("write_file"))
        self.assertTrue(self.tools.requires_approval("run_shell"))
        self.assertFalse(self.tools.requires_approval("read_file"))
        self.assertFalse(self.tools.requires_approval("list_files"))


class TestCommandRegistry(unittest.TestCase):
    def test_build_registry(self):
        reg = build_command_registry()
        cmds = reg.list_unique()
        self.assertGreater(len(cmds), 20)

    def test_get_command(self):
        reg = build_command_registry()
        cmd = reg.get("help")
        self.assertIsNotNone(cmd)

    def test_get_alias(self):
        reg = build_command_registry()
        cmd = reg.get("q")  # alias for exit
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "exit")  # name without slash

    def test_get_nonexistent(self):
        reg = build_command_registry()
        cmd = reg.get("nonexistent_command_xyz")
        self.assertIsNone(cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
