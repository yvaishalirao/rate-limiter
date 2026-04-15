import os
import redis
import pybreaker

REDIS_URL = os.getenv('REDIS_URL')
CB_FAIL_MAX = int(os.getenv('CB_FAIL_MAX', 3))
CB_RESET_TIMEOUT = int(os.getenv('CB_RESET_TIMEOUT', 10))

r = redis.from_url(REDIS_URL, decode_responses=True)

breaker = pybreaker.CircuitBreaker(
    fail_max=CB_FAIL_MAX,
    reset_timeout=CB_RESET_TIMEOUT
)

@breaker
def call_redis(script, keys, args):
    return script(keys=keys, args=args)