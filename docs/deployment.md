# Deployment

## Prerequisites

- OpenShift 4.12+ (or vanilla Kubernetes; UBI9 base image is the only Red Hat-specific bit).
- A Postgres instance for any non-trivial deployment. SQLite mode is for dev/edge only -- it does not survive a pod restart unless a PVC is attached, and it cannot scale beyond one replica.
- (optional) Keycloak realm shared with `gateway-template`, when running with `auth.mode=keycloak`.

## Build the image

Locally on Linux x86_64:

```bash
podman build -t fipsagents-platform:0.1.0 -f Containerfile .
```

On macOS for OpenShift:

```bash
podman build --platform linux/amd64 -t fipsagents-platform:0.1.0 -f Containerfile . --no-cache
```

Or use OpenShift BuildConfig with binary builds (preferred when the cluster is available).

## Deploy with Helm

### Single-replica dev (SQLite, no auth)

```bash
helm install platform chart/ \
  --set image.repository=quay.io/your-org/fipsagents-platform \
  --set image.tag=0.1.0 \
  --set storage.backend=sqlite \
  --set persistence.enabled=true
```

The PVC is mounted at `/data` and SQLite writes to `/data/platform.db`.

### Multi-replica production (Postgres, Keycloak)

```bash
oc create secret generic platform-db \
  --from-literal=PLATFORM_DATABASE_URL='postgresql://user:pass@host:5432/platform' \
  -n my-namespace

helm install platform chart/ \
  --set image.repository=quay.io/your-org/fipsagents-platform \
  --set image.tag=0.1.0 \
  --set replicaCount=2 \
  --set storage.backend=postgres \
  --set storage.databaseUrlSecretRef.name=platform-db \
  --set auth.mode=keycloak \
  --set auth.keycloakIssuer=https://keycloak.apps.cluster.example.com/realms/agents \
  --set auth.keycloakAudience=fipsagents-platform \
  --set route.enabled=true \
  --set route.host=platform.apps.cluster.example.com \
  -n my-namespace
```

## Configuration reference

All configuration is driven by environment variables. The Helm chart's ConfigMap is the canonical place to set them.

| Variable | Default | Notes |
| --- | --- | --- |
| `PLATFORM_BACKEND` | `sqlite` | `sqlite` or `postgres` |
| `PLATFORM_SQLITE_PATH` | `./platform.db` | SQLite-only; Helm sets `/data/platform.db` |
| `PLATFORM_DATABASE_URL` | _(unset)_ | Postgres-only |
| `PLATFORM_AUTH_MODE` | `none` | `none` or `keycloak` |
| `PLATFORM_KEYCLOAK_ISSUER` | _(unset)_ | required when `AUTH_MODE=keycloak` |
| `PLATFORM_KEYCLOAK_AUDIENCE` | _(unset)_ | required when `AUTH_MODE=keycloak` |
| `PLATFORM_KEYCLOAK_JWKS_CACHE_SECONDS` | `300` | JWKS TTL; auto-busts on `kid` miss |
| `PLATFORM_LOG_LEVEL` | `INFO` | Python logging level |
| `PLATFORM_HOST` | `0.0.0.0` | uvicorn bind address |
| `PLATFORM_PORT` | `8080` | uvicorn port |

## Wiring the agent and gateway

Once the platform is reachable, the rest of the stack opts in:

1. **Agent (agent-template#114, future).** Set `agent.yaml` to use `feedback.backend: http` (and `sessions.backend: http`, `traces.backend: http` once those proof points land), with `platform.url=https://platform.apps.cluster.example.com`.
2. **Gateway (gateway-template#30, future).** Set `platform.url` on the gateway. The gateway routes `/v1/feedback/*`, `/v1/sessions/*`, `/v1/traces/*` directly to the platform instead of fanning out to per-agent endpoints.

Both are config-only. No code changes per agent.

## Postgres considerations

- **One pool, one schema.** The platform service expects to be the only writer of the `feedback`, `sessions`, and `traces` tables. Pointing multiple platform instances at the same Postgres requires no extra coordination; pointing both a per-agent `PostgresFeedbackStore` and the platform at the same database does -- avoid that.
- **Migrations.** `CREATE TABLE IF NOT EXISTS` is idempotent and runs at startup. The schema lives in `fipsagents.server.feedback` (and the future sessions/traces equivalents) -- this repo carries no parallel schema. Bumping `fipsagents` to a version with a column migration applies the migration when the service starts.
- **HA.** Single-replica platform is fine for `auth.mode=none` deployments. With `auth.mode=keycloak`, the JWKS cache is per-pod, so multi-replica deployments take slightly longer to converge after key rotation -- acceptable.

## Backup and retention

Out of scope for this service. Use your cluster's existing Postgres backup story (CronJob with `pg_dump`, operator-managed snapshots, etc). Retention windows for feedback and session data should be enforced by a scheduled job calling `DELETE FROM feedback WHERE created_at < ...` -- the `delete_before(cutoff)` method on each store is what `fipsagents.server`'s housekeeping loop already uses, and a CronJob can call it via SQL or via a small admin endpoint if we add one in a follow-up.
