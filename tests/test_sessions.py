"""End-to-end tests for the sessions proof point.

Hits the live ASGI app with a real SQLite-backed SessionStore. Round-trips
through the full FastAPI -> fipsagents.server.sessions.SqliteSessionStore
path. No mocks.
"""

from __future__ import annotations

import json

import pytest


async def _read_cost_data(client, session_id: str) -> dict:
    """Read ``cost_data`` straight out of the SQLite store.

    The public ``GET /v1/sessions/{id}`` route only returns messages, but the
    PATCH route is about ``cost_data``. We peek at the underlying aiosqlite
    connection via ``app.state.session_store`` to confirm the merge happened.
    """
    store = client._test_app.state.session_store
    db = await store._get_db()
    cursor = await db.execute(
        "SELECT cost_data FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    row = await cursor.fetchone()
    assert row is not None, f"session {session_id!r} not found in store"
    return json.loads(row[0]) if row[0] else {}


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


# ---------------------------------------------------------------------------
# PATCH /v1/sessions/{session_id} — partial update for cost_data accumulator.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_session_updates_cost_data(client) -> None:
    """Two PATCH calls shallow-merge per top-level key (write-wins)."""
    sid = "patch-cost"
    await client.post("/v1/sessions", json={"session_id": sid})

    first = await client.patch(f"/v1/sessions/{sid}", json={"cost_data": {"a": 1}})
    assert first.status_code == 200
    body = first.json()
    assert body == {"session_id": sid, "messages": []}

    second = await client.patch(
        f"/v1/sessions/{sid}", json={"cost_data": {"b": 2, "a": 5}}
    )
    assert second.status_code == 200

    merged = await _read_cost_data(client, sid)
    assert merged == {"a": 5, "b": 2}


@pytest.mark.asyncio
async def test_patch_session_404_when_missing(client) -> None:
    resp = await client.patch(
        "/v1/sessions/never-existed", json={"cost_data": {"a": 1}}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_session_none_cost_data(client) -> None:
    """``cost_data: null`` is a no-op merge but still confirms existence."""
    sid = "patch-noop"
    await client.post("/v1/sessions", json={"session_id": sid})
    await client.patch(f"/v1/sessions/{sid}", json={"cost_data": {"seed": 1}})

    resp = await client.patch(f"/v1/sessions/{sid}", json={"cost_data": None})
    assert resp.status_code == 200

    # Existing accumulator state is left alone.
    assert await _read_cost_data(client, sid) == {"seed": 1}


@pytest.mark.asyncio
async def test_patch_session_404_when_missing_with_none_cost_data(client) -> None:
    """Even with ``cost_data: null`` the route must 404 for unknown sessions."""
    resp = await client.patch(
        "/v1/sessions/ghost", json={"cost_data": None}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_session_returns_messages(client) -> None:
    """PATCH echoes the persisted message history alongside the merge result."""
    sid = "patch-with-history"
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    await client.put(f"/v1/sessions/{sid}", json={"messages": messages})

    resp = await client.patch(
        f"/v1/sessions/{sid}", json={"cost_data": {"prompt_tokens": 42}}
    )
    assert resp.status_code == 200
    assert resp.json() == {"session_id": sid, "messages": messages}


# ---------------------------------------------------------------------------
# GET /v1/sessions/{session_id}/cost_data — read companion to PATCH.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cost_data_after_patches(client) -> None:
    """GET returns the cumulative shallow-merged cost_data."""
    sid = "cost-read"
    await client.post("/v1/sessions", json={"session_id": sid})
    await client.patch(f"/v1/sessions/{sid}", json={"cost_data": {"a": 1}})
    await client.patch(f"/v1/sessions/{sid}", json={"cost_data": {"b": 2, "a": 5}})

    resp = await client.get(f"/v1/sessions/{sid}/cost_data")
    assert resp.status_code == 200
    assert resp.json() == {"session_id": sid, "cost_data": {"a": 5, "b": 2}}


@pytest.mark.asyncio
async def test_get_cost_data_empty_when_no_writes(client) -> None:
    """Existing session with no PATCH writes returns 200 + empty dict."""
    sid = "cost-empty"
    await client.post("/v1/sessions", json={"session_id": sid})

    resp = await client.get(f"/v1/sessions/{sid}/cost_data")
    assert resp.status_code == 200
    assert resp.json() == {"session_id": sid, "cost_data": {}}


@pytest.mark.asyncio
async def test_get_cost_data_404_when_session_missing(client) -> None:
    resp = await client.get("/v1/sessions/never-existed/cost_data")
    assert resp.status_code == 404
