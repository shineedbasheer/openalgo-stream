#!/bin/bash
# POC container healthcheck — called by Docker HEALTHCHECK every 30s
set -euo pipefail

# Probe 1: openalgo Flask app (existing blueprint endpoint)
curl -sf --max-time 5 http://localhost:5000/auth/check-setup > /dev/null || exit 1

# Probe 2: strategy-executor Quarkus HTTP liveness
# Uses the marketdata tick endpoint (POST → 200 means executor is up and accepting requests).
# Note: /health/ready requires quarkus-smallrye-health extension which is not in pom.xml;
# use the real REST endpoint instead. A 200 from a POST tick is the definitive alive check.
curl -sf --max-time 5 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"symbol":"healthcheck","ltp":1.0,"timestamp":1,"tokenNumber":1}' \
  http://localhost:7012/api/marketdata/tick > /dev/null || exit 1

exit 0
