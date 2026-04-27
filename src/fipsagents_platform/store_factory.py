"""Construct fipsagents.server stores from platform config.

The platform service does not reimplement persistence -- it reuses the
SQLite/Postgres FeedbackStore/SessionStore/TraceStore from fipsagents.server
and exposes them over REST. This module is the seam.
"""

from __future__ import annotations

from fipsagents.server.feedback import FeedbackStore, create_feedback_store

from .config import Settings


def build_feedback_store(settings: Settings) -> FeedbackStore:
    return create_feedback_store(
        backend=settings.backend,
        sqlite_path=settings.sqlite_path,
        database_url=settings.database_url,
    )
