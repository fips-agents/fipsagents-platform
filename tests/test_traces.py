"""End-to-end tests for the traces proof point.

Hits the live ASGI app with a real SQLite-backed TraceStore. Traces are
seeded via the store directly (the platform service has no POST trace
endpoint -- agents write traces in-process via TraceCollector). No mocks.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from fipsagents.server.tracing import Span, Trace


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_trace(
    trace_id: str,
    *,
    model: str | None = "gpt-oss-20b",
    session_id: str | None = "sess_xyz",
    status: str = "ok",
    n_tool_spans: int = 1,
    prompt_tokens: int | None = 120,
    completion_tokens: int | None = 80,
) -> Trace:
    """Build a minimal but realistic Trace object for seeding."""
    started_at = _utc_now_iso()
    t0 = time.monotonic()

    spans: list[Span] = [
        Span(
            trace_id=trace_id,
            span_id=f"{trace_id}_root",
            parent_span_id=None,
            name="request",
            start_time=t0,
            end_time=t0 + 0.250,
            status=status,
        ),
        Span(
            trace_id=trace_id,
            span_id=f"{trace_id}_model",
            parent_span_id=f"{trace_id}_root",
            name="model_call",
            start_time=t0 + 0.010,
            end_time=t0 + 0.200,
            attributes={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        ),
    ]
    for i in range(n_tool_spans):
        spans.append(
            Span(
                trace_id=trace_id,
                span_id=f"{trace_id}_tool_{i}",
                parent_span_id=f"{trace_id}_root",
                name=f"tool:demo_{i}",
                start_time=t0 + 0.050 + 0.010 * i,
                end_time=t0 + 0.060 + 0.010 * i,
            )
        )

    return Trace(
        trace_id=trace_id,
        started_at=started_at,
        ended_at=_utc_now_iso(),
        model=model,
        session_id=session_id,
        status=status,
        spans=spans,
    )


async def _seed(client, trace: Trace) -> None:
    store = client._test_app.state.trace_store
    await store.save_trace(trace)


@pytest.mark.asyncio
async def test_get_returns_full_trace(client) -> None:
    trace = _make_trace("trace_get_001")
    await _seed(client, trace)

    resp = await client.get("/v1/traces/trace_get_001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == "trace_get_001"
    assert body["model"] == "gpt-oss-20b"
    assert body["session_id"] == "sess_xyz"
    assert body["status"] == "ok"
    assert len(body["spans"]) == 3
    span_names = {s["name"] for s in body["spans"]}
    assert span_names == {"request", "model_call", "tool:demo_0"}


@pytest.mark.asyncio
async def test_get_missing_trace_404(client) -> None:
    resp = await client.get("/v1/traces/trace_does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_returns_summaries(client) -> None:
    for i in range(3):
        await _seed(client, _make_trace(f"trace_list_{i:03d}"))

    resp = await client.get("/v1/traces")
    assert resp.status_code == 200
    summaries = resp.json()
    assert len(summaries) >= 3

    # The summaries are descending by started_at; the latest seeded trace is first.
    first = summaries[0]
    assert first["trace_id"].startswith("trace_list_")
    assert first["span_count"] == 3
    assert first["tool_calls"] == 1
    assert first["prompt_tokens"] == 120
    assert first["completion_tokens"] == 80


@pytest.mark.asyncio
async def test_list_pagination(client) -> None:
    for i in range(5):
        await _seed(client, _make_trace(f"trace_page_{i:03d}"))

    page1 = (await client.get("/v1/traces", params={"limit": 2, "offset": 0})).json()
    page2 = (await client.get("/v1/traces", params={"limit": 2, "offset": 2})).json()

    assert len(page1) == 2
    assert len(page2) == 2
    page1_ids = {s["trace_id"] for s in page1}
    page2_ids = {s["trace_id"] for s in page2}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_list_rejects_bad_limit(client) -> None:
    resp = await client.get("/v1/traces", params={"limit": 0})
    assert resp.status_code == 422

    resp = await client.get("/v1/traces", params={"limit": 5000})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_rejects_negative_offset(client) -> None:
    resp = await client.get("/v1/traces", params={"offset": -1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /v1/traces — write endpoint for HttpTraceStore.
# ---------------------------------------------------------------------------


def _trace_payload(trace_id: str, **overrides) -> dict:
    started = _utc_now_iso()
    base = {
        "trace_id": trace_id,
        "started_at": started,
        "ended_at": _utc_now_iso(),
        "model": "gpt-oss-20b",
        "session_id": "sess_post",
        "status": "ok",
        "spans": [
            {
                "trace_id": trace_id,
                "span_id": f"{trace_id}_root",
                "parent_span_id": None,
                "name": "request",
                "start_time": 0.0,
                "end_time": 0.250,
                "status": "ok",
                "attributes": {},
                "events": [],
            },
            {
                "trace_id": trace_id,
                "span_id": f"{trace_id}_model",
                "parent_span_id": f"{trace_id}_root",
                "name": "model_call",
                "start_time": 0.010,
                "end_time": 0.200,
                "status": "ok",
                "attributes": {"prompt_tokens": 50, "completion_tokens": 25},
                "events": [],
            },
            {
                "trace_id": trace_id,
                "span_id": f"{trace_id}_tool",
                "parent_span_id": f"{trace_id}_root",
                "name": "tool:search",
                "start_time": 0.060,
                "end_time": 0.080,
                "status": "ok",
                "attributes": {},
                "events": [],
            },
        ],
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_post_persists_trace(client) -> None:
    payload = _trace_payload("trace_post_001")
    resp = await client.post("/v1/traces", json=payload)
    assert resp.status_code == 201
    assert resp.json() == {"trace_id": "trace_post_001", "saved": True}

    fetched = (await client.get("/v1/traces/trace_post_001")).json()
    assert fetched["trace_id"] == "trace_post_001"
    assert fetched["model"] == "gpt-oss-20b"
    assert len(fetched["spans"]) == 3


@pytest.mark.asyncio
async def test_post_appears_in_list(client) -> None:
    await client.post("/v1/traces", json=_trace_payload("trace_post_listed"))

    summaries = (await client.get("/v1/traces")).json()
    ids = {s["trace_id"] for s in summaries}
    assert "trace_post_listed" in ids


@pytest.mark.asyncio
async def test_post_upserts_existing_trace(client) -> None:
    """save_trace uses INSERT OR REPLACE; POST must mirror that."""
    await client.post("/v1/traces", json=_trace_payload("trace_upsert", status="ok"))
    await client.post("/v1/traces", json=_trace_payload("trace_upsert", status="error"))

    fetched = (await client.get("/v1/traces/trace_upsert")).json()
    assert fetched["status"] == "error"


@pytest.mark.asyncio
async def test_post_rejects_missing_required_fields(client) -> None:
    resp = await client.post("/v1/traces", json={"trace_id": "incomplete"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_accepts_trace_with_no_spans(client) -> None:
    payload = _trace_payload("trace_no_spans")
    payload["spans"] = []
    resp = await client.post("/v1/traces", json=payload)
    assert resp.status_code == 201

    fetched = (await client.get("/v1/traces/trace_no_spans")).json()
    assert fetched["spans"] == []
