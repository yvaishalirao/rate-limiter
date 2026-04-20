import hashlib
import os

from pybreaker import CircuitBreakerError

from redis_client import call_redis, registered_script


def make_key(identifier: str) -> str:
    """
    Hash the raw identifier with SHA-256, truncate to 16 hex chars,
    and return the Redis key. This is the ONLY place Redis keys are built.
    The raw identifier must never appear in the returned string.
    """
    digest = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f'rate_limit:{digest}'


def _validate_window_config():
    window_s = int(os.getenv('RATE_LIMIT_WINDOW_S', 60))
    window_ms = window_s * 1000
    # No independent window_ms env var allowed.
    # This function documents and enforces INV-9.
    return window_s, window_ms


def check_rate_limit(identifier: str) -> dict:
    limit = int(os.environ.get('RATE_LIMIT_N', 100))
    window_s, window_ms = _validate_window_config()

    key = make_key(identifier)

    try:
        result = call_redis(registered_script, keys=[key], args=[window_ms, limit, window_s])
        count, lim = int(result[0]), int(result[1])
    except CircuitBreakerError:
        return {'allowed': True, 'remaining': -1}

    allowed = count <= limit
    remaining = max(0, lim - count)
    return {'allowed': allowed, 'remaining': remaining}