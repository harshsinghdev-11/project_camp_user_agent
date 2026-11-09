"""Request/response schemas for the agent API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language user request")


class AgentRunResponse(BaseModel):
    ok: bool = True
    answer: str
    messages: list[dict[str, Any]] = Field(default_factory=list)


class AgentErrorResponse(BaseModel):
    ok: bool = False
    message: str


class HealthResponse(BaseModel):
    ok: bool = True
    status: str = "ok"
