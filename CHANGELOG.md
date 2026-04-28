# Changelog

All notable changes to `fipsagents-platform` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.1] - 2026-04-28

Cumulative-cost read companion for `PATCH /v1/sessions/{id}`. Closes the HTTP-backend cumulative gap that the 0.14.1 cluster smoke spotlighted: without a read endpoint, agent-side `_persist_cost_data` could only write deltas (last-write-wins per top-level key). Tracked as [fipsagents-platform#4](https://github.com/fips-agents/fipsagents-platform/issues/4).

### Added

- **`GET /v1/sessions/{session_id}/cost_data`.** Returns `{"session_id": ..., "cost_data": {...}}` for existing sessions; 404 when the session is missing. Uses `store.exists()` to distinguish a missing session from one with empty accumulator state. Auth identical to the existing GET. 3 new tests; suite total 46.

### Notes

- Pairs with `fipsagents>=0.14.2` on the agent side, where `HttpSessionStore.get_cost_data` consumes this endpoint. Older agents (<=0.14.1) are unaffected — they never call it. Older platforms (<=0.2.0) paired with newer agents 404 cleanly and degrade to last-write-wins.

## [0.2.0] - 2026-04-27

Sessions and traces proof points. Closes [#1](https://github.com/fips-agents/fipsagents-platform/issues/1)'s remaining checkboxes — the platform service is feature-complete instead of "feedback only," and the wire shape is wide enough to fully back an agent-side `HttpSessionStore` / `HttpTraceStore` (agent-template#114).

### Added

- **Sessions endpoints (full ABC coverage).** `POST /v1/sessions` (create), `GET /v1/sessions/{session_id}` (load), `PUT /v1/sessions/{session_id}` (save, upsert), `HEAD /v1/sessions/{session_id}` (exists), `DELETE /v1/sessions/{session_id}`. Wraps `fipsagents.server.sessions.SessionStore` (SQLite + Postgres backends).
- **Traces endpoints (full ABC coverage).** `POST /v1/traces` (save_trace, upsert), `GET /v1/traces` (`limit`/`offset` paged summaries), `GET /v1/traces/{trace_id}` (full trace with all spans). Wraps `fipsagents.server.tracing.TraceStore`.
- **Tests.** 25 new end-to-end tests against a real SQLite-backed `SessionStore` / `TraceStore`. No mocks. Total suite: 38 tests.
- **Store factories.** `build_session_store()` and `build_trace_store()` in `store_factory.py`, mirroring the existing `build_feedback_store()`.

### Changed

- The `/v1/sessions` and `/v1/traces` endpoints no longer return `501 Not Implemented`. The wire shape is now a superset of the per-agent endpoints in `fipsagents.server.app` — it adds `PUT /v1/sessions/{id}`, `HEAD /v1/sessions/{id}`, and `POST /v1/traces` so an agent-side `HttpSessionStore` / `HttpTraceStore` can be a drop-in replacement for the in-process SQLite/Postgres backends.
- `create_app()` reads its FastAPI `version` from `version.py` instead of a hardcoded literal, so `release.sh`'s version bump is the single source of truth.

## [0.1.0] - 2026-04-27

Initial release. Bootstrap commit for the cross-agent platform service decided in [agent-template#112](https://github.com/fips-agents/agent-template/issues/112).

### Added

- **FastAPI service skeleton.** `/healthz`, `/readyz`, OpenAPI at `/docs`, route stubs for sessions and traces returning 501 with a tracking-issue pointer.
- **Feedback proof point.** `POST /v1/feedback`, `GET /v1/feedback`, `GET /v1/feedback/{id}`, `PATCH /v1/feedback/{id}`, `GET /v1/feedback/stats`. Same wire shape as the per-agent endpoints in `fipsagents.server.app`, so an `HttpFeedbackStore` on the agent side is a drop-in replacement for `SqliteFeedbackStore` / `PostgresFeedbackStore`.
- **Reused persistence.** Wraps `fipsagents.server.feedback.FeedbackStore` (SQLite + Postgres backends) — no parallel persistence implementation.
- **Bearer-token auth.** Two modes: `none` (anonymous-by-default; intended behind a trusted gateway) and `keycloak` (validates inbound JWTs against the same realm as the gateway, so RFC 8693 exchange tokens validate here).
- **Helm chart.** UBI9 Python image, ConfigMap-driven, optional PVC for SQLite mode, optional OpenShift Route. `helm lint` clean.
- **Tests.** 13 end-to-end tests against a real SQLite-backed store. No mocks.

### Known limitations

- **Sessions and traces return 501.** Their proof points follow once the feedback pattern proves out. Tracked in [#1](https://github.com/fips-agents/fipsagents-platform/issues/1).
- **`fipsagents>=0.12.0` is required.** When 0.12.0 is not yet published to PyPI, install from local source: `pip install -e ../agent-template/packages/fipsagents[feedback,server]`.
- **No image publishing.** Build with `make container` locally; tag-driven container builds will land in a follow-up.
- **No API stability policy yet.** The HTTP surface is informally stable (mirrors `fipsagents.server.app`) but a deprecation policy is queued in [#1](https://github.com/fips-agents/fipsagents-platform/issues/1) before any external consumer.
