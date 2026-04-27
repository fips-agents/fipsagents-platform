"""REST API for cross-agent feedback.

Wraps ``fipsagents.server.feedback.FeedbackStore`` with the same wire shape
as the per-agent ``/v1/feedback`` endpoints in ``fipsagents.server.app``,
so an ``HttpFeedbackStore`` on the agent side is a drop-in replacement
for ``SqliteFeedbackStore``/``PostgresFeedbackStore``.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fipsagents.server.feedback import FeedbackRecord
from fipsagents.server.models import CreateFeedbackRequest, UpdateFeedbackRequest

from ..auth import require_user

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", status_code=201)
async def create_feedback(
    body: CreateFeedbackRequest,
    request: Request,
    user_id: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.feedback_store
    record = FeedbackRecord(
        feedback_id=_new_id("fb"),
        trace_id=body.trace_id or _new_id("trace"),
        session_id=body.session_id,
        rating=body.rating,
        comment=body.comment,
        correction=body.correction,
        model_id=body.model_id,
        latency_ms=body.latency_ms,
        turn_index=body.turn_index,
        agent_type=body.agent_type,
        created_at=_utc_now_iso(),
        user_id=user_id,
    )
    feedback_id = await store.add(record)
    return JSONResponse({"feedback_id": feedback_id}, status_code=201)


@router.patch("/{feedback_id}")
async def update_feedback(
    feedback_id: str,
    body: UpdateFeedbackRequest,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.feedback_store
    record = await store.update(
        feedback_id,
        rating=body.rating,
        comment=body.comment,
        correction=body.correction,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")
    return JSONResponse(asdict(record))


@router.get("/stats")
async def feedback_stats(
    request: Request,
    window: str = "day",
    agent_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    _user: str = Depends(require_user),
) -> JSONResponse:
    if window not in ("hour", "day", "week"):
        raise HTTPException(
            status_code=400,
            detail="window must be 'hour', 'day', or 'week'",
        )
    store = request.app.state.feedback_store
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    results = await store.stats(
        window=window,
        agent_type=agent_type,
        since=since_dt,
        until=until_dt,
    )
    return JSONResponse([asdict(r) for r in results])


@router.get("")
async def list_feedback(
    request: Request,
    trace_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.feedback_store
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    records = await store.query(
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        since=since_dt,
        until=until_dt,
        limit=min(limit, 1000),
        offset=max(offset, 0),
    )
    return JSONResponse([asdict(r) for r in records])


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: str,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.feedback_store
    record = await store.get(feedback_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")
    return JSONResponse(asdict(record))
