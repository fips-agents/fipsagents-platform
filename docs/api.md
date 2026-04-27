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

## Sessions

### POST /v1/sessions

Body (all fields optional):

```json
{ "session_id": "my-session-001" }
```

`session_id` must be 1-128 characters: letters, digits, hyphens, underscores. When omitted, the server generates `sess_<16-hex>`. Returns `201 Created` with `{"session_id": "..."}`.

### GET /v1/sessions/{session_id}

Returns `{"session_id", "messages"}` where `messages` is the persisted message history (empty array for a freshly-created session). `404 Not Found` if the session does not exist.

### PUT /v1/sessions/{session_id}

Persist the message history for a session. Upsert semantics — if the session does not exist, it is created.

Body:

```json
{ "messages": [ {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."} ] }
```

Returns `{"session_id": "...", "saved": true}`. This endpoint is the extension over the per-agent server's wire shape — required for an agent-side `HttpSessionStore` to delegate `SessionStore.save()` over the wire.

### HEAD /v1/sessions/{session_id}

Existence probe. `200 OK` if the session exists, `404 Not Found` if not. No response body.

### DELETE /v1/sessions/{session_id}

Returns `{"deleted": true}`. `404 Not Found` if the session does not exist.

## Traces

### POST /v1/traces

Persist a completed trace. Upsert semantics — re-posting the same `trace_id` overwrites the prior record (matches `SqliteTraceStore.save_trace()` / `PostgresTraceStore.save_trace()`).

Body mirrors the `Trace` dataclass:

```json
{
  "trace_id": "trace_...",
  "started_at": "2026-04-27T18:00:00+00:00",
  "ended_at": "2026-04-27T18:00:01+00:00",
  "model": "gpt-oss-20b",
  "session_id": "sess_...",
  "status": "ok",
  "spans": [
    {
      "trace_id": "trace_...",
      "span_id": "...",
      "parent_span_id": null,
      "name": "request",
      "start_time": 0.0,
      "end_time": 0.250,
      "status": "ok",
      "attributes": {},
      "events": []
    }
  ]
}
```

Returns `{"trace_id": "...", "saved": true}`. This endpoint is the extension over the per-agent server's wire shape — required for an agent-side `HttpTraceStore` to delegate `TraceStore.save_trace()` over the wire.

### GET /v1/traces

Query parameters:

| Field | Type | Required |
| --- | --- | --- |
| `limit` | int (1-1000) | optional, default 50 |
| `offset` | int (≥0) | optional, default 0 |

Returns an array of `TraceSummary` objects: `{trace_id, started_at, ended_at, model, session_id, status, duration_ms, span_count, tool_calls, prompt_tokens, completion_tokens}`. Ordered descending by `started_at`.

### GET /v1/traces/{trace_id}

Returns the full `Trace` including every `Span`: `{trace_id, started_at, ended_at, model, session_id, status, spans}`. `404 Not Found` if the trace does not exist.

## Auth

When `PLATFORM_AUTH_MODE=keycloak`, every endpoint listed above requires `Authorization: Bearer <jwt>`. When the mode is `none` (default), no auth is enforced and writes attribute to `"anonymous"` unless an `X-Auth-Subject` header is provided by a trusted gateway (handling for that header is on the agent-template side, not here).
