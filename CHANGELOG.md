# Changelog

All notable changes to `fipsagents-platform` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
