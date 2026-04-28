"""REST API for cross-agent sessions.

Wraps ``fipsagents.server.sessions.SessionStore`` with the same wire shape
as the per-agent ``/v1/sessions`` endpoints in ``fipsagents.server.app``,
so an ``HttpSessionStore`` on the agent side is a drop-in replacement
for ``SqliteSessionStore``/``PostgresSessionStore``.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fipsagents.server.models import CreateSessionRequest
from pydantic import BaseModel, Field

from ..auth import require_user

router = APIRouter()


class SaveSessionRequest(BaseModel):
    """Request body for PUT /v1/sessions/{session_id}."""

    messages: list[dict] = Field(default_factory=list)


class UpdateSessionRequest(BaseModel):
    """Request body for PATCH /v1/sessions/{session_id}.

    Partial update — only the fields present are touched. ``cost_data`` is
    shallow-merged with any existing cost data on the platform side
    (write-wins per top-level key), matching ``SessionStore.update()``.
    """

    cost_data: dict | None = None


@router.post("", status_code=201)
async def create_session(
    request: Request,
    body: CreateSessionRequest = Body(default_factory=CreateSessionRequest),
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.session_store
    sid = await store.create(body.session_id)
    return JSONResponse({"session_id": sid}, status_code=201)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.session_store
    messages = await store.load(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return JSONResponse({"session_id": session_id, "messages": messages})


@router.put("/{session_id}")
async def save_session(
    session_id: str,
    body: SaveSessionRequest,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    """Persist message history for a session.

    Upsert semantics, mirroring ``SessionStore.save()``: if the session does
    not yet exist, it is created. Required for ``HttpSessionStore`` to be a
    drop-in for ``SqliteSessionStore``/``PostgresSessionStore``.
    """
    store = request.app.state.session_store
    await store.save(session_id, body.messages)
    return JSONResponse({"session_id": session_id, "saved": True})


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    """Partial update for a session (currently: ``cost_data``).

    Delegates to ``SessionStore.update()`` which shallow-merges the supplied
    ``cost_data`` with any existing accumulator state. Returns the full
    session shape so the agent side can observe the merged result.
    """
    store = request.app.state.session_store
    updated = await store.update(session_id, cost_data=body.cost_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    messages = await store.load(session_id)
    return JSONResponse({
        "session_id": session_id,
        "messages": messages or [],
    })


@router.head("/{session_id}")
async def session_exists(
    session_id: str,
    request: Request,
    _user: str = Depends(require_user),
) -> Response:
    """Existence probe; 200 if present, 404 if not. No body."""
    store = request.app.state.session_store
    exists = await store.exists(session_id)
    return Response(status_code=200 if exists else 404)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.session_store
    existed = await store.delete(session_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return JSONResponse({"deleted": True})
