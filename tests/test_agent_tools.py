"""Unit tests for agent project and task tools."""

import os
import unittest
from unittest.mock import MagicMock, patch

import httpx
from user_agent.agents.tools import (
    ALL_TOOLS,
    PROJECT_TOOLS,
    TASK_TOOLS,
    clear_access_token,
    create_project,
    create_task,
    delete_project,
    delete_task,
    get_access_token,
    get_base_url,
    get_project,
    get_task,
    list_projects,
    list_tasks,
    request,
    set_access_token,
    update_project,
    update_task,
)


class TestApiClient(unittest.TestCase):
    def setUp(self):
        clear_access_token()

    def tearDown(self):
        clear_access_token()

    def test_token_context(self):
        self.assertIsNone(get_access_token())
        set_access_token("test-jwt-token")
        self.assertEqual(get_access_token(), "test-jwt-token")
        clear_access_token()
        self.assertIsNone(get_access_token())

    def test_base_url_default_and_env(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_base_url(), "http://localhost:3000/api/v1")

        with patch.dict(os.environ, {"NODE_API_BASE_URL": "http://api.example.com/api/v1/"}):
            self.assertEqual(get_base_url(), "http://api.example.com/api/v1")

    def test_request_missing_token(self):
        res = request("GET", "/projects")
        self.assertFalse(res["ok"])
        self.assertEqual(res["statusCode"], 401)
        self.assertIn("missing", res["message"].lower())
        self.assertIn("Missing access token", res["errors"][0])

    @patch("httpx.Client.request")
    def test_request_success_normalization(self, mock_request):
        set_access_token("valid-jwt")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "statusCode": 200,
            "data": [{"_id": "proj-1", "name": "Marketing"}],
            "message": "Projects fetched successfully",
            "success": True,
        }
        mock_request.return_value = mock_resp

        res = request("GET", "/projects")

        self.assertTrue(res["ok"])
        self.assertEqual(res["statusCode"], 200)
        self.assertEqual(res["message"], "Projects fetched successfully")
        self.assertEqual(len(res["data"]), 1)
        self.assertEqual(res["data"][0]["name"], "Marketing")

        # Verify Bearer header
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer valid-jwt")
        self.assertEqual(call_kwargs["headers"]["Accept"], "application/json")

    @patch("httpx.Client.request")
    def test_request_error_normalization(self, mock_request):
        set_access_token("valid-jwt")
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {
            "statusCode": 403,
            "message": "You do not have permission to perform this action",
            "errors": [],
            "success": False,
        }
        mock_request.return_value = mock_resp

        res = request("DELETE", "/projects/123")

        self.assertFalse(res["ok"])
        self.assertEqual(res["statusCode"], 403)
        self.assertEqual(res["message"], "You do not have permission to perform this action")
        self.assertEqual(res["errors"], [])

    @patch("httpx.Client.request")
    def test_request_network_error(self, mock_request):
        set_access_token("valid-jwt")
        mock_request.side_effect = httpx.ConnectError("Connection refused")

        res = request("GET", "/projects")

        self.assertFalse(res["ok"])
        self.assertEqual(res["statusCode"], 503)
        self.assertIn("Network error", res["message"])


class TestProjectTools(unittest.TestCase):
    def setUp(self):
        set_access_token("jwt-token")

    def tearDown(self):
        clear_access_token()

    def test_tool_registries(self):
        self.assertEqual(len(PROJECT_TOOLS), 5)
        self.assertEqual(len(TASK_TOOLS), 5)
        self.assertEqual(len(ALL_TOOLS), 10)

        names = [t.name for t in PROJECT_TOOLS]
        self.assertIn("list_projects", names)
        self.assertIn("get_project", names)
        self.assertIn("create_project", names)
        self.assertIn("update_project", names)
        self.assertIn("delete_project", names)

    @patch("user_agent.agents.tools.project.request")
    def test_list_projects(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": []}
        res = list_projects.invoke({})
        mock_req.assert_called_once_with("GET", "/projects")
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.project.request")
    def test_get_project(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": {"_id": "p1"}}
        res = get_project.invoke({"project_id": "p1"})
        mock_req.assert_called_once_with("GET", "/projects/p1")
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.project.request")
    def test_create_project(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 201, "data": {"_id": "p1", "name": "App"}}
        res = create_project.invoke({"name": "App", "description": "Mobile app"})
        mock_req.assert_called_once_with(
            "POST", "/projects", json={"name": "App", "description": "Mobile app"}
        )
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.project.request")
    def test_update_project(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": {"_id": "p1", "name": "New App"}}
        res = update_project.invoke({"project_id": "p1", "name": "New App"})
        mock_req.assert_called_once_with(
            "PUT", "/projects/p1", json={"name": "New App"}
        )
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.project.request")
    def test_delete_project(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200}
        res = delete_project.invoke({"project_id": "p1"})
        mock_req.assert_called_once_with("DELETE", "/projects/p1")
        self.assertTrue(res["ok"])


class TestTaskTools(unittest.TestCase):
    def setUp(self):
        set_access_token("jwt-token")

    def tearDown(self):
        clear_access_token()

    def test_tool_registries(self):
        names = [t.name for t in TASK_TOOLS]
        self.assertIn("list_tasks", names)
        self.assertIn("get_task", names)
        self.assertIn("create_task", names)
        self.assertIn("update_task", names)
        self.assertIn("delete_task", names)

    @patch("user_agent.agents.tools.task.request")
    def test_list_tasks(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": []}
        res = list_tasks.invoke({"project_id": "p1"})
        mock_req.assert_called_once_with("GET", "/tasks/p1")
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.task.request")
    def test_get_task(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": {"_id": "t1"}}
        res = get_task.invoke({"project_id": "p1", "task_id": "t1"})
        mock_req.assert_called_once_with("GET", "/tasks/p1/t/t1")
        self.assertTrue(res["ok"])

    @patch("user_agent.agents.tools.task.request")
    def test_create_task_valid(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 201, "data": {"_id": "t1"}}
        res = create_task.invoke({
            "project_id": "p1",
            "title": "Build UI",
            "description": "Login page",
            "assigned_to": "u1",
            "status": "todo",
        })
        mock_req.assert_called_once_with(
            "POST",
            "/tasks/p1",
            json={
                "title": "Build UI",
                "description": "Login page",
                "assignedTo": "u1",
                "status": "todo",
            },
        )
        self.assertTrue(res["ok"])

    def test_create_task_invalid_status(self):
        res = create_task.invoke({
            "project_id": "p1",
            "title": "Build UI",
            "status": "invalid_status",
        })
        self.assertFalse(res["ok"])
        self.assertEqual(res["statusCode"], 422)
        self.assertIn("Invalid task status", res["message"])

    @patch("user_agent.agents.tools.task.request")
    def test_update_task_partial(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200, "data": {"_id": "t1"}}
        res = update_task.invoke({
            "project_id": "p1",
            "task_id": "t1",
            "status": "in_progress",
        })
        mock_req.assert_called_once_with(
            "PUT",
            "/tasks/p1/t/t1",
            json={"status": "in_progress"},
        )
        self.assertTrue(res["ok"])

    def test_update_task_invalid_status(self):
        res = update_task.invoke({
            "project_id": "p1",
            "task_id": "t1",
            "status": "blocked",
        })
        self.assertFalse(res["ok"])
        self.assertEqual(res["statusCode"], 422)

    @patch("user_agent.agents.tools.task.request")
    def test_delete_task(self, mock_req):
        mock_req.return_value = {"ok": True, "statusCode": 200}
        res = delete_task.invoke({"project_id": "p1", "task_id": "t1"})
        mock_req.assert_called_once_with("DELETE", "/tasks/p1/t/t1")
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main()
