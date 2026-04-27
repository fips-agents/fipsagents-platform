"""Smoke tests for healthz/readyz."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_healthz_ok(client) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_ok(client) -> None:
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_sessions_route_wired(client) -> None:
    """POST /v1/sessions creates a session (not a 501 stub anymore)."""
    resp = await client.post("/v1/sessions")
    assert resp.status_code == 201
    assert resp.json()["session_id"].startswith("sess_")


@pytest.mark.asyncio
async def test_traces_route_wired(client) -> None:
    """GET /v1/traces returns a list (not a 501 stub anymore)."""
    resp = await client.get("/v1/traces")
    assert resp.status_code == 200
    assert resp.json() == []
