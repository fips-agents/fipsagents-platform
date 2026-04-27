"""End-to-end tests for the feedback proof point.

Hits the live ASGI app with a real SQLite-backed FeedbackStore. Round-trips
through the full FastAPI -> fipsagents.server.feedback.SqliteFeedbackStore
path. No mocks.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_and_get(client) -> None:
    body = {
        "rating": 1,
        "trace_id": "trace_test_001",
        "comment": "looks good",
        "agent_type": "calculus",
    }
    resp = await client.post("/v1/feedback", json=body)
    assert resp.status_code == 201
    fb_id = resp.json()["feedback_id"]
    assert fb_id.startswith("fb_")

    resp = await client.get(f"/v1/feedback/{fb_id}")
    assert resp.status_code == 200
    record = resp.json()
    assert record["feedback_id"] == fb_id
    assert record["trace_id"] == "trace_test_001"
    assert record["rating"] == 1
    assert record["comment"] == "looks good"
    assert record["user_id"] == "anonymous"


@pytest.mark.asyncio
async def test_create_without_trace_id_synthesises_one(client) -> None:
    resp = await client.post("/v1/feedback", json={"rating": -1})
    assert resp.status_code == 201
    fb_id = resp.json()["feedback_id"]
    record = (await client.get(f"/v1/feedback/{fb_id}")).json()
    assert record["trace_id"].startswith("trace_")


@pytest.mark.asyncio
async def test_invalid_rating_rejected(client) -> None:
    resp = await client.post("/v1/feedback", json={"rating": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_missing_feedback_404(client) -> None:
    resp = await client.get("/v1/feedback/fb_does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_updates_comment(client) -> None:
    create = await client.post("/v1/feedback", json={"rating": 1, "comment": "v1"})
    fb_id = create.json()["feedback_id"]
    patch = await client.patch(f"/v1/feedback/{fb_id}", json={"comment": "v2"})
    assert patch.status_code == 200
    assert patch.json()["comment"] == "v2"


@pytest.mark.asyncio
async def test_patch_missing_404(client) -> None:
    resp = await client.patch("/v1/feedback/fb_missing", json={"comment": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_query_filters(client) -> None:
    await client.post("/v1/feedback", json={"rating": 1, "trace_id": "trace_a"})
    await client.post("/v1/feedback", json={"rating": -1, "trace_id": "trace_a"})
    await client.post("/v1/feedback", json={"rating": 1, "trace_id": "trace_b"})

    resp = await client.get("/v1/feedback", params={"trace_id": "trace_a"})
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) == 2
    assert {r["rating"] for r in records} == {1, -1}


@pytest.mark.asyncio
async def test_stats_aggregates(client) -> None:
    for _ in range(3):
        await client.post(
            "/v1/feedback",
            json={"rating": 1, "agent_type": "calculus", "trace_id": "t"},
        )
    await client.post(
        "/v1/feedback",
        json={"rating": -1, "agent_type": "calculus", "trace_id": "t"},
    )

    resp = await client.get("/v1/feedback/stats", params={"window": "day"})
    assert resp.status_code == 200
    stats = resp.json()
    assert len(stats) >= 1
    bucket = stats[-1]
    assert bucket["thumbs_up"] == 3
    assert bucket["thumbs_down"] == 1
    assert bucket["total"] == 4


@pytest.mark.asyncio
async def test_stats_rejects_bad_window(client) -> None:
    resp = await client.get("/v1/feedback/stats", params={"window": "century"})
    assert resp.status_code == 400
