"""Agent HTTP routes: healthcheck and tool-calling agent run."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from user_agent.agents.runner import run_agent
from user_agent.agents.tools import clear_access_token, set_access_token
from user_agent.api.schemas import (
    AgentErrorResponse,
    AgentRunRequest,
    AgentRunResponse,
    HealthResponse,
)

router = APIRouter()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization Bearer token is required",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be: Bearer <accessToken>",
        )
    return token.strip()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness probe (no JWT required)."""
    return HealthResponse()


@router.post(
    "/agent/run",
    response_model=AgentRunResponse,
    responses={
        401: {"model": AgentErrorResponse},
        500: {"model": AgentErrorResponse},
        502: {"model": AgentErrorResponse},
    },
)
def agent_run(
    body: AgentRunRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> AgentRunResponse:
    """Run the Groq tool-calling agent for one user query.

    Requires the user's Node.js access JWT in Authorization: Bearer <token>.
    The token is stored in context for tools and cleared after the run.
    """
    token = _extract_bearer_token(authorization)
    query = body.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="query must not be empty",
        )

    set_access_token(token)
    try:
        result = run_agent(query)
        return AgentRunResponse(
            ok=True,
            answer=result["answer"],
            messages=result.get("messages") or [],
        )
    except RuntimeError as exc:
        # Missing GROQ_API_KEY or similar configuration errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent run failed: {exc}",
        ) from exc
    finally:
        clear_access_token()
