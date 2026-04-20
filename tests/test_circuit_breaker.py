"""
Circuit breaker / fail-open tests.

Strategy: patch limiter.call_redis to raise exceptions on demand.
These tests are unit-level — no Redis container required.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pybreaker import CircuitBreakerError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app import app

FAIL_OPEN = {"allowed": True, "remaining": -1}

@pytest.fixture
def client():
    # raise_server_exceptions=False so 5xx surfaces as a response, not an exception
    return TestClient(app, raise_server_exceptions=False)


def post(client, user_id="cb_test_user"):
    return client.post("/check-rate-limit", json={"user_id": user_id})


# ---------------------------------------------------------------------------
# Fail-open on every error type (INV-6)
# ---------------------------------------------------------------------------

def test_fail_open_on_circuit_error(client):
    with patch("limiter.call_redis", side_effect=CircuitBreakerError()):
        resp = post(client)
    assert resp.status_code == 200
    assert resp.json() == FAIL_OPEN


def test_fail_open_on_connection_error(client):
    with patch("limiter.call_redis", side_effect=RedisConnectionError("host down")):
        resp = post(client)
    assert resp.status_code == 200  # never 500 (INV-6)
    assert resp.json() == FAIL_OPEN


def test_fail_open_on_timeout(client):
    with patch("limiter.call_redis", side_effect=RedisTimeoutError("timed out")):
        resp = post(client)
    assert resp.status_code == 200  # never 500 (INV-6)
    assert resp.json() == FAIL_OPEN


# ---------------------------------------------------------------------------
# Sentinel value
# ---------------------------------------------------------------------------

def test_remaining_minus_one_is_sentinel(client):
    with patch("limiter.call_redis", side_effect=CircuitBreakerError()):
        resp = post(client)
    assert resp.json()["remaining"] == -1


# ---------------------------------------------------------------------------
# Recovery: normal response once mock is removed
# ---------------------------------------------------------------------------

def test_normal_request_after_mock_restored(client):
    # Step 1 — mock as down, verify fail-open
    with patch("limiter.call_redis", side_effect=CircuitBreakerError()):
        down_resp = post(client, "recover_user")
    assert down_resp.json()["remaining"] == -1

    # Step 2 — mock healthy Redis returning count=1, limit=5
    with patch("limiter.call_redis", return_value=[1, 5]):
        up_resp = post(client, "recover_user")
    assert up_resp.status_code == 200
    assert up_resp.json()["allowed"] is True
    assert up_resp.json()["remaining"] == 4


# ---------------------------------------------------------------------------
# Generic (non-Redis) exception on /check-rate-limit → fail-open (INV-6)
# Exercises general_error_handler in app.py
# ---------------------------------------------------------------------------

def test_fail_open_on_generic_exception(client):
    with patch("limiter.call_redis", side_effect=RuntimeError("unexpected crash")):
        resp = post(client)
    assert resp.status_code == 200  # never 500 (INV-6)
    assert resp.json() == FAIL_OPEN


# ---------------------------------------------------------------------------
# Health route is independent of Redis (INV-6 scope is /check-rate-limit)
# ---------------------------------------------------------------------------

def test_health_unaffected_by_redis_failure(client):
    with patch("limiter.call_redis", side_effect=RedisConnectionError("host down")):
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
