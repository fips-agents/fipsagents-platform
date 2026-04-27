# API Reference

OpenAPI spec is served live at `GET /docs` (Swagger UI) and `GET /openapi.json` when the service is running.

This page is a hand-written summary for offline reference. The live OpenAPI is authoritative.

## Health

### `GET /healthz`

Liveness probe. Returns `{"status": "ok"}`.

### `GET /readyz`

Readiness probe. Returns `{"status": "ready"}` once the lifespan handler has built the feedback store.

## Feedback

### `POST /v1/feedback`

Create a feedback record.

**Request body** (matches `fipsagents.server.models.CreateFeedbackRequest`):

```json
{
  "rating": 1,
  "trace_id": "trace_abc",
  "session_id": "sess_xyz",
  "comment": "looks good",
  "correction": null,
  "model_id": "Qwen/Qwen3-32B",
  "latency_ms": 1234.5,
  "turn_index": 0,
  "agent_type": "calculus"
}
```

- `rating` is required, must be `1` (thumbs-up) or `-1` (thumbs-down).
- `trace_id` is optional; the server synthesises one when omitted so feedback works even if tracing is sampled out.
- All other fields are optional metadata.

**Response** `201 Created`:

```json
{ "feedback_id": "fb_a1b2c3d4e5f6g7h8" }
```

### `GET /v1/feedback`

List feedback records with filters.

Query parameters:

| Parameter | Type | Notes |
| --- | --- | --- |
| `trace_id` | string | exact match |
| `session_id` | string | exact match |
| `user_id` | string | exact match (gateway-issued subject) |
| `since` | ISO 8601 | `created_at >= since` |
| `until` | ISO 8601 | `created_at < until` |
| `limit` | int | default 50, max 1000 |
| `offset` | int | default 0 |

Returns a JSON array of records ordered by `created_at` descending.

### `GET /v1/feedback/{feedback_id}`

Retrieve a single record by ID. `404` when not found.

### `PATCH /v1/feedback/{feedback_id}`

Mutate `rating`, `comment`, or `correction`. Omitted fields are left unchanged. `404` when not found.

### `GET /v1/feedback/stats`

Aggregated counts grouped by `agent_type` and time window.

Query parameters:

| Parameter | Type | Notes |
| --- | --- | --- |
| `window` | string | `hour`, `day` (default), or `week` |
| `agent_type` | string | optional filter |
| `since` | ISO 8601 | optional |
| `until` | ISO 8601 | optional |

Returns an array of `{window_start, window_end, agent_type, thumbs_up, thumbs_down, total}`.

## Sessions (proof point pending)

`POST /v1/sessions`, `GET /v1/sessions/{session_id}`, `DELETE /v1/sessions/{session_id}` — all return `501 Not Implemented`. Tracked in [#1](https://github.com/fips-agents/fipsagents-platform/issues/1).

## Traces (proof point pending)

`GET /v1/traces`, `GET /v1/traces/{trace_id}` — return `501 Not Implemented`. Tracked in [#1](https://github.com/fips-agents/fipsagents-platform/issues/1).

## Auth

When `PLATFORM_AUTH_MODE=keycloak`, every endpoint listed above requires `Authorization: Bearer <jwt>`. When the mode is `none` (default), no auth is enforced and writes attribute to `"anonymous"` unless an `X-Auth-Subject` header is provided by a trusted gateway (handling for that header is on the agent-template side, not here).
