import hashlib

def make_key(identifier: str) -> str:
    """
    Hash the raw identifier with SHA-256, truncate to 16 hex chars,
    and return the Redis key. This is the ONLY place Redis keys are built.
    The raw identifier must never appear in the returned string.
    """
    digest = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f'rate_limit:{digest}'