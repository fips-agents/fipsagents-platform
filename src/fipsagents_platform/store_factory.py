"""Construct fipsagents.server stores from platform config.

The platform service does not reimplement persistence -- it reuses the
SQLite/Postgres FeedbackStore/SessionStore/TraceStore from fipsagents.server
and exposes them over REST. This module is the seam.
"""

from __future__ import annotations

from fipsagents.server.feedback import FeedbackStore, create_feedback_store
from fipsagents.server.sessions import SessionStore, create_session_store
from fipsagents.server.tracing import TraceStore, create_trace_store

from .config import Settings


def build_feedback_store(settings: Settings) -> FeedbackStore:
    return create_feedback_store(
        backend=settings.backend,
        sqlite_path=settings.sqlite_path,
        database_url=settings.database_url,
    )


def build_session_store(settings: Settings) -> SessionStore:
    return create_session_store(
        backend=settings.backend,
        sqlite_path=settings.sqlite_path,
        database_url=settings.database_url,
    )


def build_trace_store(settings: Settings) -> TraceStore:
    return create_trace_store(
        backend=settings.backend,
        sqlite_path=settings.sqlite_path,
        database_url=settings.database_url,
    )
