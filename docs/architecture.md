# Architecture

The authoritative architecture document for the cross-agent platform service is in the `agent-template` repo:

**[agent-template/docs/architecture.md § "Cross-Agent Platform Service"](https://github.com/fips-agents/agent-template/blob/main/docs/architecture.md#cross-agent-platform-service)**

That section covers the design rationale, the four options that were considered, why Option 4 (remote-store adapter with a sibling platform service) was chosen, and the tradeoffs flagged for the initial extraction. The decision was recorded in [agent-template#112](https://github.com/fips-agents/agent-template/issues/112).

This document captures the implementation-level details specific to this repo. Read the agent-template document first.

## Code layout

```
src/fipsagents_platform/
  __init__.py
  __main__.py        # python -m fipsagents_platform entrypoint
  app.py             # FastAPI factory, lifespan, route registration
  config.py          # pydantic-settings, env-driven
  auth.py            # Bearer-token validation (none / keycloak modes)
  store_factory.py   # Builds fipsagents.server stores from config
  routes/
    feedback.py      # /v1/feedback proof point (live)
    sessions.py      # /v1/sessions (501 -- proof point pending)
    traces.py        # /v1/traces (501 -- proof point pending)
```

## Persistence

The platform service does **not** reimplement persistence. It depends on `fipsagents[feedback,server]>=0.12.0` and reuses the existing `FeedbackStore` / `SessionStore` / `TraceStore` ABCs:

- `fipsagents.server.feedback` -- `FeedbackStore`, `SqliteFeedbackStore`, `PostgresFeedbackStore`, `create_feedback_store()`
- `fipsagents.server.sessions` -- `SessionStore`, `SqliteSessionStore`, `PostgresSessionStore`
- `fipsagents.server.tracing` -- `TraceStore`, `SqliteTraceStore`, `PostgresTraceStore`

This is the deliberate design from agent-template#112: schema and migration logic stay in one place. The platform repo is a thin REST veneer.

## Auth model

Two modes, controlled by `PLATFORM_AUTH_MODE`:

- **`none`** -- the platform validates nothing. `user_id` defaults to `"anonymous"` on writes. Use this when a trusted gateway in front already enforces authn (the typical fips-agents topology) and the platform is reachable only via the cluster network.
- **`keycloak`** -- inbound `Authorization: Bearer <jwt>` is validated against a Keycloak issuer's JWKS. The same realm as the gateway, so tokens issued by `gateway-template`'s RFC 8693 exchange (gateway-template#27) validate here. The validated `sub` claim is recorded as `user_id` on the feedback record.

JWKS is cached for `PLATFORM_KEYCLOAK_JWKS_CACHE_SECONDS` (default 300). On a `kid` miss, the cache is busted once and the JWKS re-fetched -- this handles key rotation without bouncing the pod.

## Wire shape

All endpoints mirror `fipsagents.server.app`'s per-agent endpoints exactly. The point is that an `HttpFeedbackStore` on the agent side (agent-template#114) can route to either the per-agent endpoint or the platform endpoint with no contract difference.

| Endpoint | Status | Notes |
| --- | --- | --- |
| `POST /v1/feedback` | live | Returns `{"feedback_id": "fb_..."}` |
| `GET /v1/feedback` | live | Filters: `trace_id`, `session_id`, `user_id`, `since`, `until`, `limit`, `offset` |
| `GET /v1/feedback/{id}` | live | New endpoint -- not on the per-agent server. Used by the agent-side `HttpFeedbackStore.get()` |
| `PATCH /v1/feedback/{id}` | live | Partial update; `null` means "leave unchanged" |
| `GET /v1/feedback/stats` | live | Aggregations grouped by `agent_type` and time window |
| `POST /v1/sessions` | 501 | proof point pending |
| `GET /v1/sessions/{id}` | 501 | proof point pending |
| `DELETE /v1/sessions/{id}` | 501 | proof point pending |
| `GET /v1/traces` | 501 | proof point pending |
| `GET /v1/traces/{id}` | 501 | proof point pending |

## Topology

```
ui-template ──► gateway-template ──► agent  ──► fipsagents-platform
                       │                              │
                       └─────────► fipsagents-platform (direct, when
                                   gateway routing mode is enabled)
```

Two routing options for the `/v1/feedback`, `/v1/sessions`, `/v1/traces` paths, controlled by `gateway-template#30`'s routing-mode config:

1. **Per-agent fan-out** (default, backward-compatible) -- gateway forwards to the agent backend, which uses its local `SqliteFeedbackStore` or `PostgresFeedbackStore`. Each agent owns its data.
2. **Direct routing** -- gateway forwards to `fipsagents-platform`, which owns one Postgres pool, one schema, and one auth boundary across all agents.

When the agent is configured with `HttpFeedbackStore` (agent-template#114), the per-agent endpoint round-trips to the platform anyway, so option 1 with `Http*Store` is functionally equivalent to option 2. Option 2 just removes the extra network hop.
