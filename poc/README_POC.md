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

| Layer | Size (measured) |
|---|---|
| python:3.11-slim-bullseye base | ~146 MB |
| apt-get (tzdata, curl, libopenblas0, libgomp1, libgfortran5, supervisor) | ~93 MB |
| JRE from eclipse-temurin:21-jre-jammy (COPY /opt/java/openjdk) | ~165 MB |
| Python venv (uv sync --no-dev + gunicorn + eventlet) | ~870 MB |
| openalgo source via source-prep stage | ~14 MB |
| React frontend/dist | omitted (POC tradeoff #8) |
| executor uber-jar | ~92 MB |
| supervisord.conf + healthcheck | <1 MB |
| **Total actual** | **1.84 GB** |

Target: < 2000 MB. **AC #1 satisfied.** Size optimized 2026-04-30 (was 2.02 GB).

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

Build and smoke validation completed locally 2026-04-30 on Docker Desktop (Windows). Image is reproducible end-to-end.

**Completed validation steps:**
1. `bash zenox-strategy-executor/docker-build.sh` — executor uber-jar built + image built
2. Image size confirmed: **1.84 GB** (< 2000 MB; AC #1 satisfied)
3. `docker compose -f poc/docker-compose.poc.yml --env-file poc/.env.poc up -d` — container started
4. Endpoint validation:
   - `http://localhost:5000/` — HTTP 200
   - `http://localhost:7012/` — HTTP 404 (executor root, correct)
   - `http://localhost:7012/api/marketdata/tick` (POST) — HTTP 200 (tick accepted)
   - `http://localhost:8765/` — HTTP 426 (WebSocket proxy, correct)
5. No `UnsatisfiedLinkError`, `NoClassDefFoundError`, or `ImportError` in container logs.

---

## POC-Mode Tradeoffs (deliberate; not for production)

These choices were made during local build-up validation on 2026-04-30. They are **safe for a local POC** but **must be revisited before any production-style deployment**. Reviewu / Localu must audit these.

| # | File | Choice | Why (POC) | Production must |
|---|---|---|---|---|
| 1 | `Dockerfile.poc` (both apt stages) | apt sources rewritten `http://deb.debian.org` → `https://deb.debian.org` via `sed` before `apt-get update` | Dev networks behind some firewalls/VPNs block port 80 egress from container bridge networks; HTTPS works because image pulls already use 443 | Keep — HTTPS mirror is strictly better; no downside |
| 2 | `Dockerfile.poc` python-builder + production stages | Bumped both base images from `python:3.12-…` to `python:3.11-…` | openalgo's `pyproject.toml` has `requires-python = "==3.11.*"` (strict). 3.12 caused uv to install its own bundled 3.11 at a path that doesn't exist in the slim final stage → venv resolves to a missing interpreter | Keep until openalgo upstream lifts the version pin |
| 3 | `Dockerfile.poc` python-builder | `WORKDIR /app/openalgo` (was `/app`) so the venv is built at the same absolute path it lives at in the final image | uv bakes absolute interpreter paths into venv script shebangs (`gunicorn`, `pip`, …). When the venv is built at `/app/.venv` and copied to `/app/openalgo/.venv`, every script's shebang points to a non-existent path | Keep |
| 4 | `application-poc.properties` (executor) | Added `marketdata.udp.network-interface=lo` and `marketdata.udp.interface-address=0.0.0.0` | Quarkus build-time validation of `@ConfigProperty` String fields requires the values to exist even when Aeron is set to `aeron:ipc` mode (no UDP) | Production should set real interface (e.g. `em1`) |
| 5 | `docker-compose.poc.yml` | Bind-mount `./.env.poc:/app/openalgo/.env:ro` | openalgo's startup validator reads `/app/openalgo/.env` from disk (not from process env), even when env vars are injected via `--env-file` | Production: bake env into image via secrets or materialize `/app/openalgo/.env` from env vars at startup |
| 6 | `supervisord.conf` + new `run_openalgo.py` | openalgo launched via `python /app/openalgo/poc/run_openalgo.py` instead of gunicorn | gunicorn 25.x + eventlet has a known incompat (`Control server error: asyncio.run() cannot be called from a running event loop`); also Flask-SocketIO 5.x raises `RuntimeError: The Werkzeug web server is not designed to run in production` whenever `sys.stdin.isatty()` is False (always under supervisord) | Production: pin `gunicorn<23` and revert `[program:openalgo]` to `gunicorn --worker-class eventlet -w 1 app:app` |
| 7 | `.env.poc` (gitignored, not committed) | `FLASK_ENV=development` + `EXECUTOR_MYSQL_USER=root` / `PASS=pass` | dev mode unblocks Werkzeug; root creds match the local `zenox-mysql` container | Production: dedicated MySQL user with least-privilege grants on `executor_poc` schema only; `FLASK_ENV=production` with proper WSGI |
| 8 | `Dockerfile.poc` + `.dockerignore` | `frontend-builder` stage dropped; `frontend/src/` and `frontend/public/` excluded from build context; compiled React `dist/` not included | POC acceptance criteria are backend-only (Strategy Executor + 3 brokers + openalgo streaming). Flask's Jinja2 templates continue to serve `http://localhost:5000/` (HTTP 200). Dropping the builder eliminates a ~4 MB `frontend/dist` COPY layer and prevents `frontend/src/` (2.6 MB) from entering the source COPY layer. Root cause of image exceeding 2 GB was `poc/executor/app.jar` (88 MB) landing in the source COPY layer twice; the `source-prep` intermediate stage plus this exclusion resolves it. | Production: restore `frontend-builder` stage, remove `frontend/src/` and `frontend/public/` from `.dockerignore`, add `COPY --from=frontend-builder /app/frontend/dist /app/openalgo/frontend/dist` back |

### Build-up validation log (2026-04-30, local Docker Desktop)

The first attempt to bring up the POC found **6 latent bugs** in Stage 3b's committed files plus **1 environmental issue**. All bugs are now fixed in the feature branch; the environmental issue (apt port-80 egress) is mitigated by the HTTPS mirror swap above.

Confirmed working endpoints:
- `http://localhost:5000/` — openalgo Flask UI/API → HTTP 200
- `http://localhost:7012/` — Quarkus executor → HTTP 404 (correct: `/` is unmapped, real routes work)
- `http://localhost:7012/api/marketdata/tick` (POST) → HTTP 400 on empty/bad body (endpoint registered)
- `http://localhost:8765/` — WebSocket proxy → HTTP 426 Upgrade Required (correct WS server response)

Image size: **1.84 GB** (2.02 GB → 1.84 GB after size-optimization pass on 2026-04-30; saves 180 MB; AC #1 satisfied).

Optimization summary:
- Root cause: `poc/executor/app.jar` (88 MB) landed twice in the image — once via `COPY . /app/openalgo/` (because `.dockerignore` negation `!poc/executor/app.jar` re-included it) and once via the explicit `COPY poc/executor/app.jar /app/executor/app.jar`. Fix: added `source-prep` intermediate stage that copies the source tree then `rm -rf poc/executor/`; final stage uses `COPY --from=source-prep` which sees the cleaned filesystem.
- Secondary: dropped `frontend-builder` stage (POC tradeoff #8) and excluded `frontend/src/` + `frontend/public/` from build context (saves ~7.5 MB additional).
- Attempt 3 (alpine JRE) evaluated and skipped: `/opt/java/openjdk` directory is 157 MB in both `eclipse-temurin:21-jre-jammy` and `eclipse-temurin:21-jre-alpine` — same JDK content, no saving in the COPY layer.

---

*Devu — Stage 3b | Phase 3 | 2026-04-30*
