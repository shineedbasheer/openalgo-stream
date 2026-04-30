# ZenOx POC Docker Container

Combined container image: **zenox-strategy-executor** (Java 21 / Quarkus) + **openalgo-stream** (Python 3.12 / Flask + WebSocket proxy).

Ticket: https://github.com/smarttouch-ai/zenox-trading-platform/issues/15

---

## Architecture

```
[supervisord PID 1]
  |
  +-- program:openalgo          priority=10  port 5000
  |    gunicorn --worker-class eventlet --bind 0.0.0.0:5000
  |
  +-- program:websocket-proxy   priority=10  port 8765
  |    python -m websocket_proxy.server (WEBSOCKET_HOST=0.0.0.0)
  |
  +-- program:strategy-executor priority=20  port 7012
       java -Dquarkus.profile=poc -jar /app/executor/app.jar

EXTERNAL (not in container):
  - Host MySQL  :3306           (via host.docker.internal)
  - Mock feed server            (pushes POST /api/marketdata/tick to :7012)
  - Zerodha / Upstox APIs       (outbound from openalgo broker modules)
  - Evermore on-premise server  (LAN/VPN required; see Broker Setup)
```

**Brokers active at runtime:** `VALID_BROKERS=zerodha,evermore,upstox`
All broker modules ship in the image; add/change a broker via one `.env.poc` edit + container restart (no rebuild).

---

## Prerequisites

1. **Docker Engine** (tested: 24+) and **Docker Compose** v2
2. **Host MySQL** running and accessible:
   ```sql
   CREATE DATABASE executor_poc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'executor'@'%' IDENTIFIED BY '<your-password>';
   GRANT ALL PRIVILEGES ON executor_poc.* TO 'executor'@'%';
   FLUSH PRIVILEGES;
   ```
3. **Java 21 JDK** on your build host (for step 1 of the build process)
4. **Maven Wrapper** (`mvnw`) — already in `zenox-strategy-executor/`

---

## Build & Run

### Step 1: Build the uber-jar and Docker image

```bash
# From repo root (parent of both zenox-strategy-executor and openalgo-stream)
cd zenox-strategy-executor
bash docker-build.sh
```

`docker-build.sh` does four things in order:
1. `mvn clean package -DskipTests -Dquarkus.package.jar.type=uber-jar` on the executor
2. Copies `target/zenox-strategy-executor-*-runner.jar` to `openalgo-stream/poc/executor/app.jar`
3. Runs `docker build -f poc/Dockerfile.poc -t zenox-poc:latest .` from `openalgo-stream/`
4. Prints the final image size (target: < 2 GB)

Expected build time: 8-15 minutes (first run; subsequent builds use Docker layer cache).

### Step 2: Configure environment

```bash
cd openalgo-stream
cp poc/.env.poc.template poc/.env.poc
```

Edit `poc/.env.poc` and fill in at minimum:

| Variable | Required | Notes |
|---|---|---|
| `APP_KEY` | YES | 64-char hex secret; run `python -c "import secrets; print(secrets.token_hex(32))"` |
| `API_KEY_PEPPER` | YES | Another 64-char hex secret |
| `BROKER_API_KEY` | YES | Zerodha or Upstox developer console key |
| `BROKER_API_SECRET` | YES | Matching secret |
| `EXECUTOR_MYSQL_PASS` | YES | MySQL password for `executor` user |
| `WEBSOCKET_HOST` | **MUST stay `0.0.0.0`** | Default `127.0.0.1` breaks host->container WebSocket |
| `VALID_BROKERS` | YES | `zerodha,evermore,upstox` |

### Step 3: Start the container

```bash
cd openalgo-stream
docker compose -f poc/docker-compose.poc.yml --env-file poc/.env.poc up -d
```

### Step 4: Verify startup

Container startup timeline:
- `t=5s`  — websocket-proxy RUNNING
- `t=10s` — openalgo RUNNING
- `t=30s` — strategy-executor RUNNING (if MySQL available)
- `t=90s` — Docker HEALTHCHECK first probe fires

```bash
# Check process status
docker exec zenox-poc supervisorctl status
# Expected:
# openalgo          RUNNING   pid NNN, uptime 0:01:XX
# websocket-proxy   RUNNING   pid NNN, uptime 0:01:XX
# strategy-executor RUNNING   pid NNN, uptime 0:01:XX

# Check healthcheck
docker inspect zenox-poc --format='{{.State.Health.Status}}'
# Expected: healthy (may show starting for first 90s)

# Check openalgo
curl http://localhost:5000/auth/check-setup
# Expected: HTTP 200

# Check executor
curl http://localhost:7012/health/ready
# Expected: {"status":"UP",...}

# Send a test tick
curl -X POST http://localhost:7012/api/marketdata/tick \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NIFTY","ltp":24500.0,"timestamp":1702901234567,"tokenNumber":26000}'
# Expected: HTTP 200 {"status":"success",...} or similar 2xx
```

---

## Broker Setup

### Zerodha
1. Go to https://kite.trade/developer and create an app
2. Note `API_KEY` and `API_SECRET`
3. Set `BROKER_NAME=zerodha`, `BROKER_API_KEY=<key>`, `BROKER_API_SECRET=<secret>`
4. Login via the openalgo UI at http://localhost:5000

### Upstox
1. Go to https://developer.upstox.com and create an app
2. Set Redirect URL to `http://localhost:5000/upstox/callback` in the developer console
3. Set `BROKER_NAME=upstox`, `BROKER_API_KEY=<key>`, `BROKER_API_SECRET=<secret>`, `REDIRECT_URL=http://localhost:5000/upstox/callback`
4. Login via the openalgo UI at http://localhost:5000

### Evermore
1. **LAN/VPN access required** to the Evermore on-premise server (`192.168.6.164:16006` default)
2. Set `EVERMORE_BASE_URL=http://<evermore-server>:<port>` in `.env.poc`
3. Set `BROKER_NAME=evermore`
4. Login via the openalgo UI at http://localhost:5000

---

## Mock Feed Integration

The strategy-executor tick endpoint is available at `POST http://localhost:7012/api/marketdata/tick`.
An external mock feed server can push ticks at any rate (up to ~100 ticks/s per BA NFR).

Sample tick payload:
```json
{
  "symbol": "NIFTY",
  "ltp": 24500.0,
  "timestamp": 1702901234567,
  "tokenNumber": 26000
}
```

For the mock feed server URL, set `MOCK_FEED_URL` in your environment (documentation only — the container does not read this variable).

---

## Logs

```bash
# All logs streamed to Docker
docker logs zenox-poc -f

# Per-process logs inside container
docker exec zenox-poc tail -f /app/logs/openalgo.log
docker exec zenox-poc tail -f /app/logs/executor.log
docker exec zenox-poc tail -f /app/logs/ws_proxy.log
docker exec zenox-poc tail -f /app/logs/supervisord.log
```

---

## Stopping

```bash
docker compose -f poc/docker-compose.poc.yml down
# Or to also remove volumes (resets all persistent state):
docker compose -f poc/docker-compose.poc.yml down -v
```

---

## Image Size Budget

Estimated layer breakdown:

| Layer | Size |
|---|---|
| python:3.12-slim-bullseye base | ~45 MB |
| apt-get (tzdata, curl, libs, supervisor) | ~30 MB |
| JRE from eclipse-temurin:21-jre-jammy | ~180 MB |
| Python venv (uv sync --no-dev + gunicorn) | ~500-600 MB |
| openalgo source (after .dockerignore) | ~15 MB |
| React frontend/dist | ~8 MB |
| executor uber-jar | ~88-180 MB |
| supervisord.conf + healthcheck | <1 MB |
| **Total estimate** | **~870-1060 MB** |

Target: < 2000 MB. If image exceeds 1800 MB, apply in order:
1. Add `numba`, `llvmlite`, `kaleido` to `.dockerignore` if strategies don't require them
2. Add `scipy`, `plotly` if not needed
3. Verify `install/`, `test/`, `docs/` are excluded via `.dockerignore`

---

## Troubleshooting

### strategy-executor BACKOFF in supervisorctl
MySQL is not reachable at startup. The executor has `autorestart=true` and will retry.
- Verify MySQL is running: `mysql -h 127.0.0.1 -u executor -p executor_poc`
- On Linux, verify `extra_hosts: host.docker.internal:host-gateway` in compose (already set)
- On Mac/Windows Docker Desktop, `host.docker.internal` resolves automatically

### WebSocket connections refused
`WEBSOCKET_HOST` is likely `127.0.0.1`. Confirm `.env.poc` has `WEBSOCKET_HOST=0.0.0.0`.

### host.docker.internal not resolved on Linux
The compose file already includes `extra_hosts: host-gateway`. If you run with `docker run` manually, add `--add-host=host.docker.internal:host-gateway`.

### OOM / JVM crash
Increase `-Xmx` in `supervisord.conf` (default: `-Xmx1g`). The container needs at least 4 GB host memory.

### Upstox OAuth redirect error
The `REDIRECT_URL` in `.env.poc` must exactly match the redirect URI registered in the Upstox developer console.

---

## Limitations (POC scope)

- MySQL is NOT bundled in the container — you must supply a host MySQL instance
- No Kafka required — REST-only tick ingestion path only
- Evermore requires LAN/VPN access to the on-premise server
- No `USER appuser` (supervisord requires root to manage child process groups) — acceptable for POC; not production-ready
- No TLS — all ports are plain HTTP inside the container
- No registry push — image is local only

---

## Known Manual Steps Before Gate 4 (Testu)

The Docker image build (`docker-build.sh`) was not executed in CI as Docker daemon was not available in the dev environment.

**Manual verification required before Testu:**
1. Run `bash zenox-strategy-executor/docker-build.sh` from a machine with Docker daemon
2. Confirm image size < 2000 MB
3. Run `docker compose -f poc/docker-compose.poc.yml --env-file poc/.env.poc up -d`
4. Run the validation checklist above (Steps 4a-4d)
5. Record actual observed startup times in this README (replace "30s JVM" with measured time)

---

*Devu — Stage 3b | Phase 3 | 2026-04-30*
