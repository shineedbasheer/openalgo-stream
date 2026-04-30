#!/bin/bash
# POC container healthcheck — called by Docker HEALTHCHECK every 30s
set -euo pipefail

# Probe 1: openalgo Flask app (existing blueprint endpoint)
curl -sf --max-time 5 http://localhost:5000/auth/check-setup > /dev/null || exit 1

# Probe 2: strategy-executor Quarkus readiness
# Quarkus SmallRye Health readiness endpoint (includes auto-registered datasource check)
curl -sf --max-time 5 http://localhost:7012/health/ready | grep -q '"status":"UP"' || exit 1

exit 0
