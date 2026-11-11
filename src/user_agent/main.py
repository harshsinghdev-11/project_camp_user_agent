"""CLI entrypoint for the user-agent package."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Start the FastAPI agent server.

    Respects ``PORT`` (Render / cloud default) and enables reload only when
    ``RELOAD`` is truthy (``1`` / ``true`` / ``yes``) for local development.
    """
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "").strip().lower() in {"1", "true", "yes"}

    uvicorn.run(
        "user_agent.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
