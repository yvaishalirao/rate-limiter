import time
import uuid
import pytest
from redis_client import r, registered_script

WINDOW_S = 60
WINDOW_MS = WINDOW_S * 1000
LIMIT = 5


def _call(key, window_ms=WINDOW_MS, limit=LIMIT, window_s=WINDOW_S):
    return registered_script(keys=[key], args=[window_ms, limit, window_s])


@pytest.fixture
def test_key():
    key = f"rate_limit:test:{uuid.uuid4().hex}"
    r.delete(key)
    yield key
    r.delete(key)


def test_first_call_count_is_1(test_key):
    result = _call(test_key)
    assert result[0] == 1


def test_count_increments(test_key):
    result = None
    for _ in range(5):
        result = _call(test_key)
    assert result[0] == 5


def test_zadd_fires_on_denied(test_key):
    # 6 calls with limit=5 — ZADD must run unconditionally on the 6th (INV-4)
    result = None
    for _ in range(6):
        result = _call(test_key)
    assert result[0] == 6  # count is 6, not 5


def test_ttl_set(test_key):
    _call(test_key)
    ttl = r.ttl(test_key)
    assert 0 < ttl <= WINDOW_S


def test_window_eviction(test_key):
    window_s = 2
    window_ms = window_s * 1000

    _call(test_key, window_ms=window_ms, limit=LIMIT, window_s=window_s)
    time.sleep(window_s + 1)

    result = _call(test_key, window_ms=window_ms, limit=LIMIT, window_s=window_s)
    assert result[0] == 1  # old entry evicted, count resets
