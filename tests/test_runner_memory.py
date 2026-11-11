"""Unit tests for short-term working memory prompt injection and patch extraction."""

from __future__ import annotations

import json
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from user_agent.agents.runner import (
    _working_memory_message,
    extract_working_memory_patch,
)


class TestRunnerMemory(unittest.TestCase):
    def test_working_memory_message_empty(self):
        self.assertIsNone(_working_memory_message(None))
        self.assertIsNone(_working_memory_message({}))
        self.assertIsNone(_working_memory_message({"last_project": None, "last_task": None}))
        self.assertIsNone(_working_memory_message({"last_project": {}, "last_task": {}}))

    def test_working_memory_message_project_only(self):
        mem = {
            "last_project": {"id": "672e1234567890abcdef1234", "name": "python learning"},
            "last_task": None,
        }
        msg = _working_memory_message(mem)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["role"], "system")
        content = msg["content"]
        self.assertIn("672e1234567890abcdef1234", content)
        self.assertIn("python learning", content)
        self.assertIn("SHORT-TERM MEMORY", content)
        self.assertIn('If the user refers to "it"', content)

    def test_working_memory_message_task_and_project(self):
        mem = {
            "last_project": {"id": "proj-1", "name": "Project Camp"},
            "last_task": {"id": "task-1", "title": "syntax", "project_id": "proj-1"},
        }
        msg = _working_memory_message(mem)
        self.assertIsNotNone(msg)
        content = msg["content"]
        self.assertIn("proj-1", content)
        self.assertIn("task-1", content)
        self.assertIn("syntax", content)

    def test_extract_patch_empty_or_failed(self):
        self.assertEqual(extract_working_memory_patch([]), {})

        # Failed tool execution should be ignored
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "create_project", "args": {"name": "Fail"}}],
        )
        tool_msg = ToolMessage(
            tool_call_id="call_1",
            content=json.dumps({"ok": False, "statusCode": 400, "message": "Name taken"}),
        )
        self.assertEqual(extract_working_memory_patch([ai_msg, tool_msg]), {})

    def test_extract_patch_create_project(self):
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "call_p1", "name": "create_project", "args": {"name": "python learning"}}
            ],
        )
        tool_msg = ToolMessage(
            tool_call_id="call_p1",
            name="create_project",
            content=json.dumps(
                {
                    "ok": True,
                    "statusCode": 201,
                    "data": {"_id": "proj-987", "name": "python learning"},
                }
            ),
        )
        patch = extract_working_memory_patch([ai_msg, tool_msg])
        self.assertEqual(
            patch,
            {"last_project": {"id": "proj-987", "name": "python learning"}},
        )

    def test_extract_patch_create_task(self):
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_t1",
                    "name": "create_task",
                    "args": {"project_id": "proj-987", "title": "syntax"},
                }
            ],
        )
        tool_msg = ToolMessage(
            tool_call_id="call_t1",
            name="create_task",
            content={
                "ok": True,
                "statusCode": 201,
                "data": {
                    "_id": "task-555",
                    "title": "syntax",
                    "project": "proj-987",
                },
            },
        )
        patch = extract_working_memory_patch([ai_msg, tool_msg])
        self.assertIn("last_task", patch)
        self.assertEqual(patch["last_task"]["id"], "task-555")
        self.assertEqual(patch["last_task"]["title"], "syntax")
        self.assertEqual(patch["last_task"]["project_id"], "proj-987")
        self.assertIn("last_project", patch)
        self.assertEqual(patch["last_project"]["id"], "proj-987")


if __name__ == "__main__":
    unittest.main()

