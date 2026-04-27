"""End-to-end tests for the sessions proof point.

Hits the live ASGI app with a real SQLite-backed SessionStore. Round-trips
through the full FastAPI -> fipsagents.server.sessions.SqliteSessionStore
path. No mocks.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_generates_id(client) -> None:
    resp = await client.post("/v1/sessions", json={})
    assert resp.status_code == 201
    sid = resp.json()["session_id"]
    assert sid.startswith("sess_")


@pytest.mark.asyncio
async def test_create_with_explicit_id(client) -> None:
    resp = await client.post("/v1/sessions", json={"session_id": "my-session-001"})
    assert resp.status_code == 201
    assert resp.json()["session_id"] == "my-session-001"


@pytest.mark.asyncio
async def test_create_rejects_invalid_id(client) -> None:
    resp = await client.post("/v1/sessions", json={"session_id": "bad id with spaces"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_after_create_returns_empty_messages(client) -> None:
    create = await client.post("/v1/sessions", json={"session_id": "fresh"})
    assert create.status_code == 201

    resp = await client.get("/v1/sessions/fresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "fresh"
    assert body["messages"] == []


@pytest.mark.asyncio
async def test_get_missing_session_404(client) -> None:
    resp = await client.get("/v1/sessions/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_removes_session(client) -> None:
    await client.post("/v1/sessions", json={"session_id": "doomed"})

    resp = await client.delete("/v1/sessions/doomed")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    resp = await client.get("/v1/sessions/doomed")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_missing_session_404(client) -> None:
    resp = await client.delete("/v1/sessions/never-existed")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_with_default_body(client) -> None:
    """POST with no body still creates a session (default factory)."""
    resp = await client.post("/v1/sessions")
    assert resp.status_code == 201
    assert resp.json()["session_id"].startswith("sess_")


@pytest.mark.asyncio
async def test_save_persists_messages(client) -> None:
    await client.post("/v1/sessions", json={"session_id": "save-roundtrip"})

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    resp = await client.put(
        "/v1/sessions/save-roundtrip", json={"messages": messages}
    )
    assert resp.status_code == 200
    assert resp.json() == {"session_id": "save-roundtrip", "saved": True}

    fetched = (await client.get("/v1/sessions/save-roundtrip")).json()
    assert fetched["messages"] == messages


@pytest.mark.asyncio
async def test_save_upserts_when_session_missing(client) -> None:
    """SessionStore.save() upserts; PUT must mirror that."""
    messages = [{"role": "user", "content": "first turn"}]
    resp = await client.put(
        "/v1/sessions/never-created", json={"messages": messages}
    )
    assert resp.status_code == 200
    fetched = (await client.get("/v1/sessions/never-created")).json()
    assert fetched["messages"] == messages


@pytest.mark.asyncio
async def test_save_overwrites_existing(client) -> None:
    sid = "overwrite-me"
    await client.post("/v1/sessions", json={"session_id": sid})
    await client.put(f"/v1/sessions/{sid}", json={"messages": [{"role": "user", "content": "v1"}]})
    await client.put(f"/v1/sessions/{sid}", json={"messages": [{"role": "user", "content": "v2"}]})

    fetched = (await client.get(f"/v1/sessions/{sid}")).json()
    assert fetched["messages"] == [{"role": "user", "content": "v2"}]


@pytest.mark.asyncio
async def test_save_accepts_empty_messages(client) -> None:
    resp = await client.put("/v1/sessions/empty", json={"messages": []})
    assert resp.status_code == 200
    fetched = (await client.get("/v1/sessions/empty")).json()
    assert fetched["messages"] == []


@pytest.mark.asyncio
async def test_head_existing_session_returns_200(client) -> None:
    await client.post("/v1/sessions", json={"session_id": "is-here"})

    resp = await client.head("/v1/sessions/is-here")
    assert resp.status_code == 200
    assert resp.content == b""


@pytest.mark.asyncio
async def test_head_missing_session_returns_404(client) -> None:
    resp = await client.head("/v1/sessions/not-here")
    assert resp.status_code == 404
    assert resp.content == b""
