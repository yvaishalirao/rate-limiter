# Distributed Rate Limiter

A sliding-window rate limiter built with Python, FastAPI, and Redis. All counting logic runs in a single atomic Lua script on Redis, ensuring correctness under concurrent requests and across multiple API instances.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) v2.1+
- Python 3.11+ (only needed to run the test suite locally)
- `curl` or any HTTP client (for manual testing)

## Quickstart

```bash
git clone <repo-url>
cd ratelimit

cp .env.example .env          # edit limits and window as needed

docker compose up --build

# Health check
curl http://localhost:8000/

# Rate-limit check
curl -X POST http://localhost:8000/check-rate-limit \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "alice"}'
```

The API is served on `http://localhost:8000` via nginx, which load-balances across all API replicas.

## Configuration

All values are environment variables. Set them in `.env` or pass them to `docker compose`.

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_N` | `100` | Maximum requests allowed per window |
| `RATE_LIMIT_WINDOW_S` | `60` | Window duration in seconds. `window_ms` is always derived as `window_s × 1000` — never set independently |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL passed to the connection pool |
| `CB_FAIL_MAX` | `3` | Number of Redis failures before the circuit breaker opens |
| `CB_RESET_TIMEOUT` | `10` | Seconds before the circuit breaker probes Redis again after opening |

## API Reference

### `POST /check-rate-limit`

Check whether a request from the given user is within the rate limit.

**Request body**

```json
{ "user_id": "alice" }
```

`user_id` is hashed with SHA-256 before use — the raw identifier never reaches Redis.

**Responses**

| Status | Body | Meaning |
|--------|------|---------|
| `200 OK` | `{ "allowed": true,  "remaining": 4 }` | Request is within the limit |
| `429 Too Many Requests` | `{ "allowed": false, "remaining": 0 }` | Limit exceeded for this window |
| `200 OK` | `{ "allowed": true,  "remaining": -1 }` | Redis unreachable — fail-open (see below) |

**`remaining: -1` is the fail-open sentinel.** It means the count could not be checked, not that the user has unlimited quota.

### `GET /`

```json
{ "status": "ok" }
```

Health check. Always returns `200` regardless of Redis state.

## Scaling

The API is stateless — all rate-limit state lives in Redis. Run as many replicas as needed:

```bash
# Using the deploy.replicas setting in docker-compose.yml (default: 2)
docker compose up --build

# Or override at runtime
docker compose up --build --scale api=4
```

nginx round-robins requests across all replicas. Because the Lua script runs atomically on the shared Redis instance, the combined request count is always accurate regardless of which replica handles each request.

## Fail-open behaviour

If Redis becomes unreachable (connection error, timeout, or circuit breaker open), every request is **allowed** and the response contains `"remaining": -1`.

- `remaining: -1` is a sentinel value. It signals degraded mode, not a real count.
- The circuit breaker opens after `CB_FAIL_MAX` consecutive Redis failures and resets after `CB_RESET_TIMEOUT` seconds.
- No request is ever rejected with HTTP 500 due to a Redis failure.

This is an explicit trade-off: during an outage all traffic is allowed rather than all traffic being blocked.

## Running tests

Requires the Redis container to be running (`docker compose up -d redis`) for integration tests.

```bash
# Install dependencies
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# or: .venv/bin/pip install -r requirements.txt  # macOS/Linux

# Run the full suite
RATE_LIMIT_N=5 pytest tests/ -v --ignore=tests/test_multi_instance.sh

# With coverage
RATE_LIMIT_N=5 pytest tests/ -v --ignore=tests/test_multi_instance.sh \
  --cov=. --cov-report=term-missing

# Multi-instance smoke test (requires docker compose up --build first)
bash tests/test_multi_instance.sh
```

`RATE_LIMIT_N=5` sets a low limit so denial tests complete quickly. The live server must also be started with `RATE_LIMIT_N=5` for the `test_rate_limit.py` integration tests.

## Architecture notes

The rate limiter uses a **sliding window** algorithm implemented as a single atomic Lua script (`lua_script.lua`) executed on Redis. Each request performs one round-trip: `ZREMRANGEBYSCORE` prunes expired entries, `ZADD` records the current request, `ZCARD` returns the count, and `EXPIRE` refreshes the TTL — all within one script, enforcing strict atomicity. Identifiers are SHA-256 hashed in Python before being used as Redis keys so raw user IDs never appear in Redis. See [docs/architecture.md](docs/architecture.md) for a full breakdown of design decisions, invariants, and trade-offs.
