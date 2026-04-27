"""Shared pytest fixtures."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def sqlite_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Configure the platform service for SQLite-backed tests."""
    fd, path = tempfile.mkstemp(prefix="platform-test-", suffix=".db")
    os.close(fd)
    os.unlink(path)  # let the store recreate it

    monkeypatch.setenv("PLATFORM_BACKEND", "sqlite")
    monkeypatch.setenv("PLATFORM_SQLITE_PATH", path)
    monkeypatch.setenv("PLATFORM_AUTH_MODE", "none")

    # Force settings re-read for each test.
    from fipsagents_platform.config import reset_settings_for_tests

    reset_settings_for_tests()

    yield path

    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def client(sqlite_env: str) -> AsyncClient:
    """ASGI test client with lifespan triggered."""
    from fipsagents_platform.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://platform.test") as c:
        async with app.router.lifespan_context(app):
            yield c
