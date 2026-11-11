"""Request/response schemas for the agent API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkingMemoryProject(BaseModel):
    id: str = Field(..., description="Project MongoDB ObjectId string")
    name: str = Field(default="", description="Project name")


class WorkingMemoryTask(BaseModel):
    id: str = Field(..., description="Task MongoDB ObjectId string")
    title: str = Field(default="", description="Task title")
    project_id: str = Field(default="", description="Project MongoDB ObjectId string")


class WorkingMemory(BaseModel):
    last_project: WorkingMemoryProject | None = None
    last_task: WorkingMemoryTask | None = None


class WorkingMemoryPatch(BaseModel):
    last_project: WorkingMemoryProject | None = None
    last_task: WorkingMemoryTask | None = None


class AgentHistoryTurn(BaseModel):
    role: str = Field(..., description="Prior turn role: user or assistant")
    content: str = Field(..., description="Prior turn text")


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language user request")
    history: list[AgentHistoryTurn] = Field(
        default_factory=list,
        description="Prior user/assistant turns. Does not include the current query.",
    )
    working_memory: WorkingMemory | None = Field(
        default=None,
        description="Structured short-term working memory holding last_project and last_task.",
    )


class AgentRunResponse(BaseModel):
    ok: bool = True
    answer: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    working_memory_patch: WorkingMemoryPatch | None = Field(
        default=None,
        description="Updated working memory patch extracted from successful tool executions.",
    )


class AgentErrorResponse(BaseModel):
    ok: bool = False
    message: str


class HealthResponse(BaseModel):
    ok: bool = True
    status: str = "ok"
