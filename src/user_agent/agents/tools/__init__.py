"""Agent tools package for project and task management.

This package exposes LangChain tools for interacting with the Node.js
REST API (/api/v1/projects and /api/v1/tasks).

See AGENT_TOOLS_PLAN.md for full architectural design and specifications.
"""

from ._api_client import (
    clear_access_token,
    get_access_token,
    get_base_url,
    request,
    set_access_token,
)
from .project import (
    PROJECT_TOOLS,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)
from .task import (
    TASK_TOOLS,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)

ALL_TOOLS = PROJECT_TOOLS + TASK_TOOLS

__all__ = [
    # Auth & client helpers
    "get_base_url",
    "set_access_token",
    "get_access_token",
    "clear_access_token",
    "request",
    # Project tools
    "list_projects",
    "get_project",
    "create_project",
    "update_project",
    "delete_project",
    "PROJECT_TOOLS",
    # Task tools
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "delete_task",
    "TASK_TOOLS",
    # All tools
    "ALL_TOOLS",
]

