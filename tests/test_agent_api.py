"""Unit tests for FastAPI agent routes (mocked runner; no live Groq)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from user_agent.api.app import app


class TestAgentApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "ok")

    def test_agent_run_missing_bearer(self):
        res = self.client.post("/agent/run", json={"query": "List my projects"})
        self.assertEqual(res.status_code, 401)

    def test_agent_run_empty_bearer(self):
        res = self.client.post(
            "/agent/run",
            json={"query": "List my projects"},
            headers={"Authorization": "Bearer "},
        )
        self.assertEqual(res.status_code, 401)

    def test_agent_run_empty_query_body(self):
        res = self.client.post(
            "/agent/run",
            json={"query": ""},
            headers={"Authorization": "Bearer test-jwt"},
        )
        self.assertEqual(res.status_code, 422)

    def test_agent_run_whitespace_query(self):
        res = self.client.post(
            "/agent/run",
            json={"query": "   "},
            headers={"Authorization": "Bearer test-jwt"},
        )
        self.assertEqual(res.status_code, 422)

    @patch("user_agent.api.routes.agent.run_agent")
    @patch("user_agent.api.routes.agent.set_access_token")
    @patch("user_agent.api.routes.agent.clear_access_token")
    def test_agent_run_success(self, mock_clear, mock_set, mock_run):
        mock_run.return_value = {
            "answer": "You have 1 project: Marketing.",
            "messages": [{"role": "ai", "content": "You have 1 project: Marketing."}],
            "working_memory_patch": {
                "last_project": {"id": "proj-123", "name": "Marketing"}
            },
        }

        res = self.client.post(
            "/agent/run",
            json={"query": "List my projects"},
            headers={"Authorization": "Bearer user-jwt-token"},
        )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["answer"], "You have 1 project: Marketing.")
        self.assertEqual(len(body["messages"]), 1)
        self.assertEqual(body["working_memory_patch"]["last_project"]["id"], "proj-123")
        self.assertEqual(body["working_memory_patch"]["last_project"]["name"], "Marketing")

        mock_set.assert_called_once_with("user-jwt-token")
        mock_run.assert_called_once_with("List my projects", [], None)
        mock_clear.assert_called_once()

    @patch("user_agent.api.routes.agent.run_agent")
    @patch("user_agent.api.routes.agent.set_access_token")
    @patch("user_agent.api.routes.agent.clear_access_token")
    def test_agent_run_clears_token_on_failure(self, mock_clear, mock_set, mock_run):
        mock_run.side_effect = Exception("groq down")

        res = self.client.post(
            "/agent/run",
            json={"query": "List my projects"},
            headers={"Authorization": "Bearer user-jwt-token"},
        )

        self.assertEqual(res.status_code, 502)
        mock_set.assert_called_once_with("user-jwt-token")
        mock_run.assert_called_once_with("List my projects", [], None)
        mock_clear.assert_called_once()

    @patch("user_agent.api.routes.agent.run_agent")
    @patch("user_agent.api.routes.agent.set_access_token")
    @patch("user_agent.api.routes.agent.clear_access_token")
    def test_agent_run_forwards_history_and_working_memory(self, mock_clear, mock_set, mock_run):
        mock_run.return_value = {
            "answer": "Added task syntax.",
            "messages": [],
            "working_memory_patch": {
                "last_task": {"id": "t-1", "title": "syntax", "project_id": "p-1"}
            },
        }

        res = self.client.post(
            "/agent/run",
            json={
                "query": "Add a task to that project named syntax",
                "history": [
                    {"role": "user", "content": "Create a project called Marketing"},
                    {"role": "assistant", "content": "Created Marketing."},
                ],
                "working_memory": {
                    "last_project": {"id": "p-1", "name": "Marketing"},
                    "last_task": None,
                },
            },
            headers={"Authorization": "Bearer user-jwt-token"},
        )

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["working_memory_patch"]["last_task"]["id"], "t-1")
        mock_run.assert_called_once_with(
            "Add a task to that project named syntax",
            [
                {"role": "user", "content": "Create a project called Marketing"},
                {"role": "assistant", "content": "Created Marketing."},
            ],
            {
                "last_project": {"id": "p-1", "name": "Marketing"},
                "last_task": None,
            },
        )
        mock_clear.assert_called_once()


if __name__ == "__main__":
    unittest.main()
