"""CLI entrypoint for the user-agent package."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start the FastAPI agent server (default :8000)."""
    uvicorn.run(
        "user_agent.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
