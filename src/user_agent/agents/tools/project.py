"""LangChain tools for project management.

This module provides tools for creating, listing, reading, updating, and deleting
projects by interacting with the Node.js REST API (/api/v1/projects).

Authentication and permissions:
- Uses the shared HTTP client in `_api_client.py` which forwards the user's JWT.
- JWT is maintained in request context and is NEVER accepted as a tool parameter.
- Required project roles on the backend:
    * list_projects: Any authenticated user (returns user's project memberships).
    * get_project: Any project member.
    * create_project: Any authenticated user (creator automatically becomes admin).
    * update_project: admin only.
    * delete_project: admin only.

See AGENT_TOOLS_PLAN.md for full architectural design and specifications.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from ._api_client import request


@tool
def list_projects() -> dict[str, Any]:
    """List projects that the current authenticated user belongs to.

    Use this tool when the user asks what projects they have, or when you need
    to look up a project by name to find its MongoDB project_id before calling
    other project or task tools.

    Returns:
        A dict containing:
            - ok (bool): True if the request succeeded, False otherwise.
            - statusCode (int): HTTP status code from the server (200 on success).
            - message (str): Response message.
            - data (list): List of project objects with user roles and project metadata.
    """
    return request("GET", "/projects")


@tool
def get_project(project_id: str) -> dict[str, Any]:
    """Fetch details of a single project by its MongoDB project_id.

    Requires the user to be a member of the project (any role).

    Args:
        project_id: The MongoDB ObjectId string of the project.

    Returns:
        A dict containing:
            - ok (bool): True if the request succeeded, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 404 if not found).
            - message (str): Response message.
            - data (dict): The complete project details.
    """
    return request("GET", f"/projects/{project_id}")


@tool
def create_project(name: str, description: str | None = None) -> dict[str, Any]:
    """Create a new project. The caller automatically becomes the project admin.

    Also automatically creates a default general conversation for project chat.

    Args:
        name: Name of the project (required, cannot be empty).
        description: Optional description of the project.

    Returns:
        A dict containing:
            - ok (bool): True if created successfully, False otherwise.
            - statusCode (int): HTTP status code (201 on success).
            - message (str): Response message.
            - data (dict): The created project object.
    """
    body: dict[str, Any] = {"name": name}
    if description is not None:
        body["description"] = description
    return request("POST", "/projects", json=body)


@tool
def update_project(
    project_id: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Update a project's name and optional description by project_id.

    Requires the user to have the 'admin' role in the project.
    Note: The backend validator requires 'name' to be provided.

    Args:
        project_id: The MongoDB ObjectId string of the project to update.
        name: The updated name of the project (required by backend validator).
        description: Optional updated description of the project.

    Returns:
        A dict containing:
            - ok (bool): True if updated successfully, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 403 if unauthorized).
            - message (str): Response message.
            - data (dict): The updated project object.
    """
    body: dict[str, Any] = {"name": name}
    if description is not None:
        body["description"] = description
    return request("PUT", f"/projects/{project_id}", json=body)


@tool
def delete_project(project_id: str) -> dict[str, Any]:
    """Delete a project by its MongoDB project_id.

    Requires the user to have the 'admin' role in the project.
    Destructive operation: removes the project and its chat conversations and messages.

    Args:
        project_id: The MongoDB ObjectId string of the project to delete.

    Returns:
        A dict containing:
            - ok (bool): True if deleted successfully, False otherwise.
            - statusCode (int): HTTP status code (200 on success, 403 if unauthorized).
            - message (str): Response message.
            - data (dict): The deleted project document.
    """
    return request("DELETE", f"/projects/{project_id}")


PROJECT_TOOLS = [
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
]

