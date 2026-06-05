# Redis Environment Separation — Migration Proposal

## Problem

All three environments (development, Render.com, Fly.io) share a single Redis Cloud
free-tier instance (`front-abloom-whimsical-80203.db.redis.io:15241`). This means:

- Development activity (scripts, local runs) competes with production for
  memory (30 MB cap) and connections (maxclients=30).
- A developer running `redis_memory_audit.py` or `synthetic_market_shock.py`
  can push the instance over the plan limit and disrupt production.
- Production and development keys are intermingled in the same `db0`.
- The `APP_ENV=development` locally but `production` on Render/Fly means
  there is no data isolation, only a label.

## Recommended Architecture

### Phase 1 — Separate Development Redis (immediate)

```
Local docker-compose redis:7-alpine (existing config)
  - 512 MB maxmemory
  - allkeys-lru
  - No plan quota
  - Port 6379
  - Already defined in docker-compose.yml
```

The local `docker-compose.yml` already provisions `redis:7-alpine` on port
6379. The `.env` file's `REDIS_URL` currently overrides this to point to
the cloud instance. The fix:

1. Change `.env` to point to `localhost:6379` for local development.
2. Keep the cloud `REDIS_URL` as a Render/Fly.io secret only.

**Edge case**: The `_ws_redis_bridge` pub/sub and the Telegram bot require
a Redis instance the frontend can reach. For development, the local Redis
is sufficient.

### Phase 2 — Provision a dedicated production Redis (recommended)

Option A — **Redis Cloud Essentials 250 MB** (~$15/mo)
  - Single-zone, no replication
  - 256 concurrent connections
  - Sufficient for current workload with 5x headroom
  - Can be configured with `maxmemory-policy allkeys-lru` via console

Option B — **Redis Cloud Essentials 1 GB** (~$45/mo)
  - Same as above with more headroom
  - Recommended if stream growth accelerates or if shadow trading expands

After provisioning, create two Redis Cloud instances:
```
prod:   polymarket-prod-?????.db.redis.io:15241   (250 MB or 1 GB)
dev:    polymarket-dev-?????.db.redis.io:15241     (30 MB free tier or 100 MB)
```

### Phase 3 — Update deployment configs

| Deploy | Current | After Phase 1 | After Phase 2 |
|--------|---------|---------------|---------------|
| .env (local) | Points to cloud free tier | Points to localhost:6379 | Points to dev instance |
| Render.com | Shared cloud free tier (secret) | Same | Points to prod instance (secret) |
| Fly.io | Shared cloud free tier (secret) | Same | Points to prod instance (secret) |
| docker-compose.yml | Local redis:7-alpine | No change | No change |

Changes needed:

1. **`docker-compose.yml`**: Already correct — no changes required.

2. **`.env`**: Set `REDIS_URL=redis://localhost:6379/0` and
   `REDIS_PLAN_LIMIT_MB=0` (no plan limit on local Redis).

3. **Render.com**: Update the `REDIS_URL` secret to the new prod instance.
   Add `REDIS_PLAN_LIMIT_MB` as a secret matching the prod plan.

4. **Fly.io**: Same as Render — update secrets via `fly secrets set`.
   Change `REDIS_MAX_CONNECTIONS` from 10 to 15-20 if needed.

## Migration Steps

### Step 1 — Local only (can be done immediately)
```bash
# In .env, change:
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=10
REDIS_PLAN_LIMIT_MB=0

# Start local Redis
docker compose up -d redis

# Verify
python -c "from app.config import settings; print(settings.REDIS_URL)"
# Should show: redis://localhost:6379/0
```

### Step 2 — Provision prod Redis
1. Log into Redis Cloud console.
2. Create new subscription: Essentials 250 MB (or 1 GB).
3. Note the endpoint, port, and password.
4. (Optional) Set `maxmemory-policy allkeys-lru` in Redis Cloud console.

### Step 3 — Deploy to Render
```bash
# Update secrets in Render dashboard
# REDIS_URL -> new prod instance
# REDIS_PLAN_LIMIT_MB -> 250 (or 1000)
# REDIS_MAX_CONNECTIONS -> 15
```

### Step 4 — Deploy to Fly.io
```bash
fly secrets set \
  REDIS_URL=redis://... \
  REDIS_PLAN_LIMIT_MB=250 \
  REDIS_MAX_CONNECTIONS=15

fly deploy
```

### Step 5 — Decommission
Once both prod and dev are verified:
1. Delete old `front-abloom-whimsical-80203` subscription from Redis Cloud.
2. Remove the old `REDIS_URL` from `.env` (no longer needed).

## Verification

After each phase, verify:

```bash
# Check the /api/v1/system/redis endpoint returns:
#   provider_plan_limit_mb   = <expected value>
#   provider_utilization_pct = <expected value>
#   maxmemory_mb             = <expected value or 0>

# Check no data cross-contamination:
# Production Redis should NOT have dev keys like test:*
```

## Risks

- **Data loss during migration**: Redis streams and keys are ephemeral.
  Streams will rebuild from WS ingestion within minutes. No persistent
  data will be lost.
- **TypeScript bot downtime**: The Telegram bot connects at module load.
  If Redis is unavailable at startup, retry logic will reconnect within
  a few seconds.
- **Cost increase**: From free to $15-45/mo.

## Not In Scope

- Redis Cluster / sharding (not needed at current scale)
- Redis Sentinel / replication (Essentials includes HA on paid plans)
- Metric scraping to Prometheus (separate from this change)
