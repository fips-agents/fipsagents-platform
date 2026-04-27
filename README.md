# fipsagents-platform

Cross-agent platform service for [fips-agents](https://github.com/fips-agents) deployments. Centralizes feedback, sessions, and traces so a multi-agent topology runs against one Postgres pool, one schema, one auth boundary, instead of fanning state ownership out to every agent.

Pairs with the per-agent stores already in `fipsagents.server` (Null/SQLite/Postgres) — this service exposes the same store semantics over REST, and `HttpFeedbackStore` / `HttpSessionStore` / `HttpTraceStore` in the agent talk to it.

Architecture decision: [agent-template#112](https://github.com/fips-agents/agent-template/issues/112). Rationale and tradeoffs are recorded in `agent-template/docs/architecture.md` § "Cross-Agent Platform Service".

## When you want this

You **don't** want this for a single-agent deployment. The existing per-agent SQLite/Postgres path is simpler and ships today.

You **do** want this when:

- Two or more agents share a gateway and you'd like cross-agent feedback dashboards without 10 client-side joins.
- You want one Postgres migration loop instead of N.
- You want an auth boundary between agents writing the same tables.
- You expect Cost Tracking ([agent-template#104](https://github.com/fips-agents/agent-template/issues/104)) to attach token usage to sessions across agents — the same `SessionStore.update()` flows here.

## What's in the box

- **FastAPI** service. One process, one Postgres pool.
- **Same store ABCs** as `fipsagents.server` (`FeedbackStore`, `SessionStore`, `TraceStore`). Reused, not reimplemented.
- **Three resource roots**: `/v1/feedback`, `/v1/sessions`, `/v1/traces`. Same shapes as the per-agent endpoints they replace.
- **Bearer-token auth** against the same Keycloak realm as the gateway. Tokens are gateway-issued; the platform validates them.
- **Helm chart** for OpenShift. UBI9 Python base image.

## Status

Early. The repo bootstraps with **feedback** as the proof point — full CRUD, stats, tests, deployable. **Sessions** and **traces** follow once the pattern lands.

See open issues for the roadmap.

## Documentation

- [Architecture](docs/architecture.md) — code layout, persistence reuse, auth modes, wire shape, topology
- [API Reference](docs/api.md) — endpoint summary (live OpenAPI at `/docs` when the service is running)
- [Deployment](docs/deployment.md) — Helm chart, env vars, Postgres considerations
- [CHANGELOG](CHANGELOG.md)

## Quickstart (dev)

```bash
make venv
make run        # binds 127.0.0.1:8080, SQLite backend, no auth
curl -X POST http://127.0.0.1:8080/v1/feedback \
  -H 'Content-Type: application/json' \
  -d '{"trace_id":"trace_abc","rating":1,"comment":"good"}'
curl http://127.0.0.1:8080/v1/feedback/stats
```

## Configuration

Environment variables (with defaults):

| Variable | Default | Notes |
| --- | --- | --- |
| `PLATFORM_BACKEND` | `sqlite` | `sqlite` or `postgres` |
| `PLATFORM_SQLITE_PATH` | `./platform.db` | SQLite-only |
| `PLATFORM_DATABASE_URL` | _(unset)_ | Postgres-only, eg `postgresql://...` |
| `PLATFORM_AUTH_MODE` | `none` | `none` or `keycloak` |
| `PLATFORM_KEYCLOAK_ISSUER` | _(unset)_ | required when `AUTH_MODE=keycloak` |
| `PLATFORM_KEYCLOAK_AUDIENCE` | _(unset)_ | required when `AUTH_MODE=keycloak` |
| `PLATFORM_LOG_LEVEL` | `INFO` |  |

## Deploying

Helm chart at `chart/fipsagents-platform/`. Targets OpenShift; UBI9 base.

```bash
helm install platform chart/fipsagents-platform \
  --set image.tag=latest \
  --set storage.backend=postgres \
  --set storage.databaseUrl=...
```

Postgres is **not** bundled. Bring your own (cluster operator, AWS RDS, etc).

## Companion repos

- [`fips-agents/agent-template`](https://github.com/fips-agents/agent-template) — agents that talk to this service via `HttpXStore` ([#114](https://github.com/fips-agents/agent-template/issues/114))
- [`fips-agents/gateway-template`](https://github.com/fips-agents/gateway-template) — gateway routing mode that proxies `/v1/sessions/*`, `/v1/feedback/*`, `/v1/traces/*` here ([#30](https://github.com/fips-agents/gateway-template/issues/30))

## License

Apache 2.0. See `LICENSE`.
