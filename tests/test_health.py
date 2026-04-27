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
async def test_unimplemented_sessions(client) -> None:
    resp = await client.post("/v1/sessions")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_unimplemented_traces(client) -> None:
    resp = await client.get("/v1/traces")
    assert resp.status_code == 501
