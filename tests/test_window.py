"""
Window consistency tests (INV-9).

test_window_config_consistency: no Redis needed.
test_rate_limit_window_s_10 and test_requests_within_window_counted:
  require the Redis container (integration).
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app import app
from limiter import _validate_window_config

LIMIT = 5


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def uid():
    return uuid.uuid4().hex


def post(client, user_id, limit=LIMIT):
    return client.post("/check-rate-limit", json={"user_id": user_id})


# ---------------------------------------------------------------------------
# INV-9: window_ms always derived from window_s, never set independently
# ---------------------------------------------------------------------------

def test_window_config_consistency(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_WINDOW_S", "45")
    window_s, window_ms = _validate_window_config()
    assert window_ms == window_s * 1000
    assert window_s == 45
    assert window_ms == 45000


# ---------------------------------------------------------------------------
# Window eviction: after window expires, count resets (integration)
# ---------------------------------------------------------------------------

def test_rate_limit_window_s_10(monkeypatch, client):
    monkeypatch.setenv("RATE_LIMIT_N", "5")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_S", "10")

    user = uid()

    # Exhaust the limit inside the window
    for _ in range(LIMIT):
        r = post(client, user)
        assert r.status_code == 200

    # N+1 is denied
    denied = post(client, user)
    assert denied.status_code == 429

    # Wait for the window to expire (window_s=10, sleep 11s)
    time.sleep(11)

    # First call after expiry must be allowed — window has reset
    after = post(client, user)
    assert after.status_code == 200
    assert after.json()["allowed"] is True


# ---------------------------------------------------------------------------
# Requests within window are all counted; N+1 is denied
# ---------------------------------------------------------------------------

def test_requests_within_window_counted(monkeypatch, client):
    monkeypatch.setenv("RATE_LIMIT_N", "5")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_S", "60")

    user = uid()

    responses = []
    for _ in range(LIMIT):
        r = post(client, user)
        responses.append(r)

    # All N calls within the window must be allowed
    assert all(r.status_code == 200 for r in responses)
    assert responses[-1].json()["remaining"] == 0

    # N+1 must be denied
    over = post(client, user)
    assert over.status_code == 429
    assert over.json()["detail"]["allowed"] is False
    assert over.json()["detail"]["remaining"] == 0
