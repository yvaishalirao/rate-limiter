#!/bin/bash
# Multi-instance smoke test.
# Both API replicas share Redis — combined count must enforce the limit.
# Run after: docker compose up --build (deploy.replicas=2 in compose file)
set -e

LIMIT=5
USER="multi_test_$(date +%s)"

echo "--- Sending $LIMIT requests (all should be 200) ---"
for i in $(seq 1 $LIMIT); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    http://localhost:8000/check-rate-limit \
    -H 'Content-Type: application/json' \
    -d "{\"user_id\":\"$USER\"}")
  echo "Request $i: $CODE"
  if [ "$CODE" != "200" ]; then
    echo "FAIL: expected 200 on request $i, got $CODE"
    exit 1
  fi
done

echo "--- Sending N+1 request (must be 429) ---"
FINAL=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  http://localhost:8000/check-rate-limit \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$USER\"}")
echo "Final (should be 429): $FINAL"

[ "$FINAL" = "429" ] && echo "PASS" || { echo "FAIL"; exit 1; }
