"""FastAPI application entry for the user agent service."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from user_agent.api.routes.agent import router as agent_router

load_dotenv()

app = FastAPI(
    title="Project Camp User Agent",
    version="0.1.0",
    description="Groq-powered agent that calls Node.js project/task APIs via LangChain tools.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
