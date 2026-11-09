"""Shared HTTP client and JWT context management for agent tools.

This module provides the HTTP transport and authentication layer for LangChain
tools interacting with the Node.js REST API (/api/v1/*).

Key Architectural Principles (see AGENT_TOOLS_PLAN.md):
1. Node.js is the authentication authority. It verifies user credentials/JWTs
   and forwards the user's access token when calling the agent.
2. Tools NEVER ask the LLM for authentication tokens. Instead, tokens are stored
   in request-scoped ContextVars (`set_access_token`) and forwarded as Bearer tokens.
3. Raw JWT tokens are NEVER logged.
4. If an access token is missing, tools return structured error dictionaries
   rather than raising fatal exceptions, allowing the agent/caller to handle it gracefully.
5. All responses are normalized into a consistent {ok, statusCode, message, data/errors} dict.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

import httpx

# Request-scoped ContextVar to store the user's JWT access token
_access_token_var: ContextVar[str | None] = ContextVar("access_token", default=None)

# Default Node API base URL
DEFAULT_NODE_API_BASE_URL = "http://localhost:3000/api/v1"


def get_base_url() -> str:
    """Retrieve the base URL for the Node.js API from environment variables.

    Defaults to 'http://localhost:3000/api/v1'.
    Trailing slashes are automatically stripped.
    """
    return os.getenv("NODE_API_BASE_URL", DEFAULT_NODE_API_BASE_URL).rstrip("/")


def set_access_token(token: str) -> None:
    """Set the user's JWT access token in the current async/thread context.

    Called by the FastAPI runtime when an incoming agentic request forwards
    the authenticated user's JWT.
    """
    _access_token_var.set(token)


def get_access_token() -> str | None:
    """Retrieve the current user's JWT access token from context."""
    return _access_token_var.get()


def clear_access_token() -> None:
    """Clear the JWT access token from the current context after an agent run."""
    _access_token_var.set(None)


def request(
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Execute an HTTP request to the Node.js REST API with forwarded Bearer auth.

    Args:
        method: HTTP method (e.g. 'GET', 'POST', 'PUT', 'DELETE').
        path: API path relative to the base URL (e.g. '/projects' or '/tasks/123').
        json: Optional JSON payload dict for POST/PUT requests.
        params: Optional query parameters dict.
        timeout: HTTP request timeout in seconds (default 30.0).

    Returns:
        dict: A normalized dictionary suitable for LLM reasoning:
            On success:
                {
                    "ok": True,
                    "statusCode": int,
                    "message": str,
                    "data": Any
                }
            On failure:
                {
                    "ok": False,
                    "statusCode": int,
                    "message": str,
                    "errors": list
                }
    """
    token = get_access_token()
    if not token:
        return {
            "ok": False,
            "statusCode": 401,
            "message": "Authentication token is missing. User must be authenticated to perform this action.",
            "errors": ["Missing access token in agent context"],
        }

    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if json is not None:
        headers["Content-Type"] = "application/json"

    # Ensure clean path resolution
    base_url = get_base_url()
    clean_path = path.lstrip("/")
    url = f"{base_url}/{clean_path}"

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json,
                params=params,
            )

        status_code = resp.status_code

        # Attempt to parse standardized JSON response (ApiResponse / ApiError)
        try:
            payload = resp.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            # Node backend conventions: ApiResponse has success: true, ApiError has success: false
            is_backend_success = payload.get("success")
            if is_backend_success is True or (is_backend_success is None and 200 <= status_code < 300):
                return {
                    "ok": True,
                    "statusCode": payload.get("statusCode", status_code),
                    "message": payload.get("message", "Success"),
                    "data": payload.get("data"),
                }
            else:
                return {
                    "ok": False,
                    "statusCode": payload.get("statusCode", status_code),
                    "message": payload.get("message", "Request failed"),
                    "errors": payload.get("errors", []),
                }

        # Non-JSON or fallback response
        is_ok = 200 <= status_code < 300
        return {
            "ok": is_ok,
            "statusCode": status_code,
            "message": resp.reason_phrase or ("Success" if is_ok else "Request failed"),
            "data" if is_ok else "errors": resp.text if is_ok else ([resp.text] if resp.text else []),
        }

    except httpx.RequestError as exc:
        return {
            "ok": False,
            "statusCode": 503,
            "message": f"Network error communicating with backend: {exc}",
            "errors": [str(exc)],
        }
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": 500,
            "message": f"Unexpected error executing request: {exc}",
            "errors": [str(exc)],
        }

