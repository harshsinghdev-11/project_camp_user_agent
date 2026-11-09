"""Groq-backed LangChain agent runner for project/task tools.

Builds a tool-calling agent with ALL_TOOLS and invokes it for a single user query.
JWT must already be set in context via set_access_token before calling run_agent.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_groq import ChatGroq

from user_agent.agents.tools import ALL_TOOLS

load_dotenv()

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a project management assistant for Project Camp.

You help users manage projects and tasks by calling the provided tools.
Those tools call the Node.js REST API on behalf of the authenticated user.

Rules:
1. Never invent MongoDB ObjectIds. Resolve names with list_projects / list_tasks / get_* first.
2. Task status values must be exactly: todo, in_progress, or done.
3. Do not ask for or invent authentication tokens; the runtime already authenticates the user.
4. If a tool returns ok=false (especially 401/403/404/422), explain the error clearly to the user.
5. Prefer the minimum number of tool calls needed to complete the request.
6. After mutations (create/update/delete), briefly confirm what changed using tool results.
7. Do not attempt file attachments; they are unsupported.
"""


@lru_cache(maxsize=1)
def build_agent():
    """Create (and cache) the Groq tool-calling agent."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the environment or .env file."
        )

    model_name = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    llm = ChatGroq(
        model=model_name,
        temperature=0,
        api_key=api_key,
    )
    return create_agent(
        model=llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def _message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return str(content)


def _serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Compact, JSON-serializable message summaries for debugging."""
    serialized: list[dict[str, Any]] = []
    for msg in messages:
        role = getattr(msg, "type", None) or getattr(msg, "role", msg.__class__.__name__)
        entry: dict[str, Any] = {
            "role": role,
            "content": _message_content_to_text(getattr(msg, "content", "")),
        }
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            entry["tool_calls"] = [
                {
                    "name": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None),
                    "args": tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None),
                    "id": tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None),
                }
                for tc in tool_calls
            ]
        name = getattr(msg, "name", None)
        if name:
            entry["name"] = name
        serialized.append(entry)
    return serialized


def run_agent(query: str) -> dict[str, Any]:
    """Run the agent for a single user query.

    Returns:
        dict with keys:
            - answer (str): final assistant text
            - messages (list): compact message trace
    """
    agent = build_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
    )
    messages = list(result.get("messages") or [])
    answer = ""
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", None)
        if msg_type == "ai":
            text = _message_content_to_text(getattr(msg, "content", ""))
            tool_calls = getattr(msg, "tool_calls", None) or []
            if text and not tool_calls:
                answer = text
                break
            if text and not answer:
                answer = text
    if not answer and messages:
        answer = _message_content_to_text(getattr(messages[-1], "content", ""))

    return {
        "answer": answer or "Done.",
        "messages": _serialize_messages(messages),
    }
