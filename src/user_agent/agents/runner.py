"""Groq-backed LangChain agent runner for project/task tools.

Builds a tool-calling agent with ALL_TOOLS and invokes it for a single user query.
JWT must already be set in context via set_access_token before calling run_agent.
"""

from __future__ import annotations

import ast
import json
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
1. Never invent MongoDB ObjectIds that did not come from tools, history tool results, or SHORT-TERM MEMORY.
2. If SHORT-TERM MEMORY specifies last_project and the user refers to "it", "that", "this project", or "the project" without providing a new project name, use last_project.id as the project_id.
3. If SHORT-TERM MEMORY specifies last_task and the user refers to "it" or "that task" in a task context, use last_task.id as the task_id.
4. If the user explicitly names a new project or task, resolve it with tools (e.g. list_projects, create_project, list_tasks) rather than assuming old memory.
5. Task status values must be exactly: todo, in_progress, or done.
6. Do not ask for or invent authentication tokens; the runtime already authenticates the user.
7. If a tool returns ok=false (especially 401/403/404/422), explain the error clearly to the user.
8. Prefer the minimum number of tool calls needed to complete the request.
9. After mutations (create/update/delete), briefly confirm what changed using tool results.
10. Do not attempt file attachments; they are unsupported.
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


def _history_messages(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Keep only user/assistant text turns. Current query is appended by the caller."""
    turns: list[dict[str, str]] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        turns.append({"role": role, "content": content})
    return turns


def _working_memory_message(working_memory: dict[str, Any] | None) -> dict[str, str] | None:
    """Format structured short-term memory as a trusted context message for the model."""
    if not working_memory or not isinstance(working_memory, dict):
        return None

    last_project = working_memory.get("last_project")
    last_task = working_memory.get("last_task")

    has_project = bool(
        last_project and isinstance(last_project, dict) and last_project.get("id")
    )
    has_task = bool(
        last_task and isinstance(last_task, dict) and last_task.get("id")
    )

    if not has_project and not has_task:
        return None

    lines = [
        "SHORT-TERM MEMORY (trusted server state; prefer this for pronouns like \"it\", \"that project\", \"that task\"):"
    ]
    if has_project:
        p_id = last_project["id"]
        p_name = last_project.get("name") or "unnamed"
        lines.append(f"- last_project: id={p_id}, name={p_name}")
    if has_task:
        t_id = last_task["id"]
        t_title = last_task.get("title") or "unnamed"
        t_proj = last_task.get("project_id") or ""
        lines.append(f"- last_task: id={t_id}, title={t_title}, project_id={t_proj}")

    lines.append('If the user refers to "it", "that", or "this project" without a new project name, use last_project.id as project_id.')
    lines.append('If the user refers to "that task" or "it" in a task context, use last_task.id as task_id.')
    lines.append("Do not ask which project if last_project is set, unless the user explicitly names a different project.")
    lines.append("ObjectIds from SHORT-TERM MEMORY and from prior tool results are allowed and trusted. Do not invent new ids.")

    return {"role": "system", "content": "\n".join(lines)}


def _parse_tool_content(content: Any) -> dict[str, Any] | None:
    """Safely parse tool message content into a dictionary."""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        s = content.strip()
        if not s:
            return None
        try:
            val = json.loads(s)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
        try:
            val = ast.literal_eval(s)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
    return None


def extract_working_memory_patch(messages: list[Any]) -> dict[str, Any]:
    """Inspect tool execution messages and extract updated entity focus (last_project, last_task)."""
    tool_calls_by_id: dict[str, dict[str, Any]] = {}
    last_project: dict[str, str] | None = None
    last_task: dict[str, str] | None = None

    for msg in messages:
        # 1. Map tool calls from AIMessages
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            tc_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            if tc_id and tc_name:
                tool_calls_by_id[tc_id] = {
                    "name": tc_name,
                    "args": tc_args if isinstance(tc_args, dict) else {},
                }

        # 2. Inspect ToolMessages
        msg_type = getattr(msg, "type", None) or getattr(msg, "role", "")
        if msg_type in ("tool", "ToolMessage") or msg.__class__.__name__ == "ToolMessage":
            tc_id = getattr(msg, "tool_call_id", None)
            tc_info = tool_calls_by_id.get(tc_id or "") or {}
            tool_name = getattr(msg, "name", None) or tc_info.get("name")
            tc_args = tc_info.get("args", {})

            payload = _parse_tool_content(getattr(msg, "content", None))
            if not payload or not isinstance(payload, dict):
                continue

            # Only extract from successful tool results
            if payload.get("ok") is not True and payload.get("success") is not True:
                continue

            data = payload.get("data")

            # Project operations: create_project, get_project, update_project
            if tool_name in ("create_project", "get_project", "update_project"):
                if isinstance(data, dict):
                    p_id = data.get("_id") or data.get("id")
                    if p_id:
                        p_name = data.get("name") or tc_args.get("name") or ""
                        last_project = {"id": str(p_id), "name": str(p_name)}

            # Task operations: create_task, get_task, update_task
            elif tool_name in ("create_task", "get_task", "update_task"):
                if isinstance(data, dict):
                    t_id = data.get("_id") or data.get("id")
                    if t_id:
                        t_title = data.get("title") or tc_args.get("title") or ""
                        p_ref = data.get("project") or tc_args.get("project_id")
                        p_id_str = ""
                        if isinstance(p_ref, dict):
                            p_id_str = str(p_ref.get("_id") or p_ref.get("id") or "")
                        elif p_ref:
                            p_id_str = str(p_ref)

                        last_task = {
                            "id": str(t_id),
                            "title": str(t_title),
                            "project_id": p_id_str,
                        }
                        if p_id_str:
                            if not last_project:
                                last_project = {"id": p_id_str, "name": ""}
                            elif last_project.get("id") != p_id_str:
                                last_project = {"id": p_id_str, "name": ""}

            # List tasks operations: if project_id was passed in args, keep project focus
            elif tool_name == "list_tasks":
                p_arg = tc_args.get("project_id")
                if p_arg:
                    if not last_project or last_project.get("id") != str(p_arg):
                        last_project = {"id": str(p_arg), "name": last_project.get("name", "") if last_project and last_project.get("id") == str(p_arg) else ""}

    patch: dict[str, Any] = {}
    if last_project:
        patch["last_project"] = last_project
    if last_task:
        patch["last_task"] = last_task
    return patch


def run_agent(
    query: str,
    history: list[dict[str, Any]] | None = None,
    working_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the agent for a single user query, with optional prior turns and working memory.

    Returns:
        dict with keys:
            - answer (str): final assistant text
            - messages (list): compact message trace
            - working_memory_patch (dict | None): updated working memory patch from tools
    """
    agent = build_agent()
    stm_msg = _working_memory_message(working_memory)

    messages = [
        *_history_messages(history),
    ]
    if stm_msg:
        messages.append(stm_msg)
    messages.append({"role": "user", "content": query})

    result = agent.invoke(
        {
            "messages": messages
        },
    )
    messages_out = list(result.get("messages") or [])
    answer = ""
    for msg in reversed(messages_out):
        msg_type = getattr(msg, "type", None)
        if msg_type == "ai":
            text = _message_content_to_text(getattr(msg, "content", ""))
            tool_calls = getattr(msg, "tool_calls", None) or []
            if text and not tool_calls:
                answer = text
                break
            if text and not answer:
                answer = text
    if not answer and messages_out:
        answer = _message_content_to_text(getattr(messages_out[-1], "content", ""))

    patch = extract_working_memory_patch(messages_out)

    return {
        "answer": answer or "Done.",
        "messages": _serialize_messages(messages_out),
        "working_memory_patch": patch or None,
    }
