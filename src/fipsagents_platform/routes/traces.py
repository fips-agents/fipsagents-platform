"""REST API for cross-agent traces.

Wraps ``fipsagents.server.tracing.TraceStore`` with the same wire shape
as the per-agent ``/v1/traces`` endpoints in ``fipsagents.server.app``,
plus a ``POST /v1/traces`` write endpoint required for ``HttpTraceStore``
on the agent side to be a drop-in replacement for
``SqliteTraceStore``/``PostgresTraceStore``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fipsagents.server.tracing import Span, Trace
from pydantic import BaseModel, Field

from ..auth import require_user

router = APIRouter()


class SpanIn(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str = ""
    start_time: float = 0.0
    end_time: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class TraceIn(BaseModel):
    """Request body for POST /v1/traces. Mirrors the ``Trace`` dataclass."""

    trace_id: str
    started_at: str
    ended_at: str | None = None
    model: str | None = None
    session_id: str | None = None
    status: str = "ok"
    spans: list[SpanIn] = Field(default_factory=list)


def _trace_from_in(payload: TraceIn) -> Trace:
    return Trace(
        trace_id=payload.trace_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        model=payload.model,
        session_id=payload.session_id,
        status=payload.status,
        spans=[
            Span(
                trace_id=s.trace_id,
                span_id=s.span_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                start_time=s.start_time,
                end_time=s.end_time,
                status=s.status,
                attributes=s.attributes,
                events=s.events,
            )
            for s in payload.spans
        ],
    )


@router.post("", status_code=201)
async def save_trace(
    request: Request,
    body: TraceIn = Body(...),
    _user: str = Depends(require_user),
) -> JSONResponse:
    """Persist a completed trace.

    Required for ``HttpTraceStore`` on the agent side to delegate
    ``TraceStore.save_trace()`` over the wire. Upsert semantics:
    re-posting the same ``trace_id`` overwrites the prior record (matches
    ``SqliteTraceStore``/``PostgresTraceStore``).
    """
    store = request.app.state.trace_store
    await store.save_trace(_trace_from_in(body))
    return JSONResponse({"trace_id": body.trace_id, "saved": True}, status_code=201)


@router.get("")
async def list_traces(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.trace_store
    summaries = await store.list_traces(limit=limit, offset=offset)
    return JSONResponse([asdict(s) for s in summaries])


@router.get("/{trace_id}")
async def get_trace(
    trace_id: str,
    request: Request,
    _user: str = Depends(require_user),
) -> JSONResponse:
    store = request.app.state.trace_store
    trace = await store.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return JSONResponse(asdict(trace))
