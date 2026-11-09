"""LangChain tools for task management.

This module provides tools for creating, listing, reading, updating, and deleting
tasks by interacting with the Node.js REST API (/api/v1/tasks).

Authentication and permissions:
- Uses the shared HTTP client in `_api_client.py` which forwards the user's JWT.
- JWT is maintained in request context and is NEVER accepted as a tool parameter.
- Required project roles on the backend:
    * list_tasks: Any project member (admin, project_admin, member).
    * get_task: Any project member (admin, project_admin, member).
    * create_task: admin or project_admin.
    * update_task: admin or project_admin.
    * delete_task: admin or project_admin.

Allowed task status values (from backend TaskStatusEnum):
- "todo"
- "in_progress"
- "done"

Note on attachments:
Backend routes mount multer middleware for file attachments, but file persistence
is not supported for agent tools. Tools only send application/json bodies without attachments.

See AGENT_TOOLS_PLAN.md for full architectural design and specifications.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from ._api_client import request

VALID_TASK_STATUSES = {"todo", "in_progress", "done"}


@tool
def list_tasks(project_id: str) -> dict[str, Any]:
    """List all tasks in a project by its MongoDB project_id.

    Requires the user to be a member of the project (admin, project_admin, or member).
    Use this tool to view all tasks in a project or to resolve a task title
    to its MongoDB task_id before calling get_task, update_task, or delete_task.

    Args:
        project_id: The MongoDB ObjectId string of the project.

    Returns:
        A dict containing:
            - ok (bool): True if the request succeeded, False otherwise.
            - statusCode (int): HTTP status code (200 on success).
            - message (str): Response message.
            - data (list): List of tasks with populated assignee information.
    """
    return request("GET", f"/tasks/{project_id}")


@tool
def get_task(project_id: str, task_id: str) -> dict[str, Any]:
    """Fetch details of a single task by project_id and task_id.

    Requires the user to be a member of the project.
    Returns the task document with populated assignee and nested subtasks.

    Args:
        project_id: The MongoDB ObjectId string of the project.
        task_id: The MongoDB ObjectId string of the task.

    Returns:
        A dict containing:
            - ok (bool): True if the request succeeded, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 404 if not found).
            - message (str): Response message.
            - data (dict): The complete task details with subtasks and assignee.
    """
    return request("GET", f"/tasks/{project_id}/t/{task_id}")


@tool
def create_task(
    project_id: str,
    title: str,
    description: str | None = None,
    assigned_to: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Create a new task within a project.

    Requires the user to have an 'admin' or 'project_admin' role in the project.
    File attachments are not supported by the agent tool.

    Args:
        project_id: The MongoDB ObjectId string of the project.
        title: Title of the task (required, cannot be empty).
        description: Optional detailed description of the task.
        assigned_to: Optional MongoDB ObjectId string of the user assigned to this task.
        status: Optional initial status. Allowed values: 'todo', 'in_progress', 'done'.

    Returns:
        A dict containing:
            - ok (bool): True if created successfully, False otherwise.
            - statusCode (int): HTTP status code (201 on success, 403/422 on failure).
            - message (str): Response message.
            - data (dict): The created task object.
    """
    if status is not None and status not in VALID_TASK_STATUSES:
        return {
            "ok": False,
            "statusCode": 422,
            "message": (
                f"Invalid task status '{status}'. "
                f"Must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}."
            ),
            "errors": [{"status": "Invalid task status"}],
        }

    body: dict[str, Any] = {"title": title}
    if description is not None:
        body["description"] = description
    if assigned_to is not None:
        body["assignedTo"] = assigned_to
    if status is not None:
        body["status"] = status

    return request("POST", f"/tasks/{project_id}", json=body)


@tool
def update_task(
    project_id: str,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    assigned_to: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Update fields of an existing task.

    Requires the user to have an 'admin' or 'project_admin' role in the project.
    Only fields that are explicitly provided (not None) will be updated.
    File attachments are not supported by the agent tool.

    Args:
        project_id: The MongoDB ObjectId string of the project.
        task_id: The MongoDB ObjectId string of the task to update.
        title: Optional updated title for the task (cannot be empty if provided).
        description: Optional updated description for the task.
        assigned_to: Optional MongoDB ObjectId string of the assigned user.
        status: Optional updated status. Allowed values: 'todo', 'in_progress', 'done'.

    Returns:
        A dict containing:
            - ok (bool): True if updated successfully, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 403/404/422 on failure).
            - message (str): Response message.
            - data (dict): The updated task object.
    """
    if status is not None and status not in VALID_TASK_STATUSES:
        return {
            "ok": False,
            "statusCode": 422,
            "message": (
                f"Invalid task status '{status}'. "
                f"Must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}."
            ),
            "errors": [{"status": "Invalid task status"}],
        }

    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if assigned_to is not None:
        body["assignedTo"] = assigned_to
    if status is not None:
        body["status"] = status

    return request("PUT", f"/tasks/{project_id}/t/{task_id}", json=body)


@tool
def delete_task(project_id: str, task_id: str) -> dict[str, Any]:
    """Delete a task and its associated subtasks from a project.

    Requires the user to have an 'admin' or 'project_admin' role in the project.
    Destructive operation: permanently deletes the task and all associated subtasks.

    Args:
        project_id: The MongoDB ObjectId string of the project.
        task_id: The MongoDB ObjectId string of the task to delete.

    Returns:
        A dict containing:
            - ok (bool): True if deleted successfully, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 403/404 on failure).
            - message (str): Response message.
            - data (dict): The deleted task document.
    """
    return request("DELETE", f"/tasks/{project_id}/t/{task_id}")


TASK_TOOLS = [
    list_tasks,
    get_task,
    create_task,
    update_task,
    delete_task,
]
