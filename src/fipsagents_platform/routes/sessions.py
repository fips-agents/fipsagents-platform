"""REST API for cross-agent sessions (scaffolded -- proof point pending).

Returns 501 until the session-store proof point lands. See open issues
in this repo. The route is registered now so the URL surface is stable
and ``HttpSessionStore`` smoke tests on the agent side can hit a real
endpoint that returns a structured error rather than 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail=(
            "sessions endpoint not yet implemented; track progress at "
            "https://github.com/fips-agents/fipsagents-platform/issues"
        ),
    )


@router.post("")
async def create_session() -> dict:
    _not_implemented()


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    _not_implemented()


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    _not_implemented()
